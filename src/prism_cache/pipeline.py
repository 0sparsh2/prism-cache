from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from prism_cache.corpus import CorpusVersionProvider, InMemoryCorpusVersionProvider
from prism_cache.metrics import MetricsRegistry
from prism_cache.models import (
    CacheContext,
    CacheLane,
    CacheLookupResult,
    CacheTier,
    ChunkResult,
    Sensitivity,
    Tier0Result,
)
from prism_cache.prefix_metrics import PrefixCacheMetricsRegistry, PrefixCacheUsage
from prism_cache.prompt_audit import PromptAuditResult, audit_assembled
from prism_cache.routes import RouteRegistry, default_routes
from prism_cache.tier0 import process_tier0
from prism_cache.tier1 import InMemoryExactStore, Tier1ExactCache, Tier1LookupResult
from prism_cache.tier2 import EmbedFn, InMemorySemanticStore, Tier2LookupResult, Tier2SemanticCache, hash_bag_embed
from prism_cache.tier3 import InMemoryRetrievalStore, Retriever, RetrievalStore, Tier3RetrievalCache
from prism_cache.tier4 import AssembledPrompt, ChunkTextResolver, assemble_rag_prompt, anthropic_request_body


@dataclass
class PrismConfig:
    org_id: str
    corpus_id: str = "default"
    default_lane: CacheLane = CacheLane.ORG_STATIC
    default_sensitivity: Sensitivity = Sensitivity.LOW
    embed_model_id: str = "text-embedding-3-small"
    tier2_similarity_threshold: float = 0.95
    default_system_prompt: str = (
        "You are a helpful assistant. Answer using only the provided documents."
    )


@dataclass
class RagPromptBundle:
    chunks: list[ChunkResult]
    tier0: Tier0Result
    ctx: CacheContext
    tier3_lookup: CacheLookupResult
    prompt: AssembledPrompt
    audit: PromptAuditResult
    anthropic_body: dict[str, Any] | None = None


@dataclass
class FaqAnswerResult:
    text: str
    from_cache: bool
    cache_tier: CacheTier | None
    tier1: Tier1LookupResult | None
    tier2: Tier2LookupResult | None
    tier0: Tier0Result
    ctx: CacheContext


GenerateFn = Callable[[str], str]


class PrismPipeline:
    """Orchestrates Tier 0–4: exact FAQ, retrieval, prefix assembly, route rules."""

    def __init__(
        self,
        config: PrismConfig,
        *,
        store: RetrievalStore | None = None,
        exact_store: InMemoryExactStore | None = None,
        semantic_store: InMemorySemanticStore | None = None,
        corpus: CorpusVersionProvider | None = None,
        metrics: MetricsRegistry | None = None,
        prefix_metrics: PrefixCacheMetricsRegistry | None = None,
        routes: RouteRegistry | None = None,
        tier1_ttl_seconds: int | None = None,
        tier2_embed: EmbedFn | None = None,
        tier2_threshold: float | None = None,
    ) -> None:
        self.config = config
        self.corpus = corpus or InMemoryCorpusVersionProvider()
        self.metrics = metrics or MetricsRegistry()
        self.prefix_metrics = prefix_metrics or PrefixCacheMetricsRegistry()
        self.routes = routes or default_routes()
        self.tier3 = Tier3RetrievalCache(
            store or InMemoryRetrievalStore(),
            embed_model_id=config.embed_model_id,
            metrics=self.metrics,
        )
        self.tier1 = Tier1ExactCache(
            exact_store or InMemoryExactStore(),
            metrics=self.metrics,
            default_ttl_seconds=tier1_ttl_seconds,
        )
        self.tier2 = Tier2SemanticCache(
            semantic_store or InMemorySemanticStore(),
            tier2_embed or hash_bag_embed,
            metrics=self.metrics,
            default_threshold=tier2_threshold or config.tier2_similarity_threshold,
        )

    def corpus_version(self) -> str:
        return self.corpus.current_version(self.config.org_id, self.config.corpus_id)

    def prepare(
        self,
        query: str,
        *,
        lane: CacheLane | None = None,
        sensitivity: Sensitivity | None = None,
        user_id: str | None = None,
        team_id: str | None = None,
        clearance: str = "default",
        model_id: str = "",
        route_hint: str | None = None,
    ) -> tuple[Tier0Result, CacheContext]:
        tier0 = process_tier0(
            query,
            requested_lane=lane or self.config.default_lane,
            sensitivity=sensitivity or self.config.default_sensitivity,
            route_hint=route_hint,
        )
        ctx = CacheContext(
            org_id=self.config.org_id,
            lane=tier0.lane,
            sensitivity=tier0.sensitivity,
            corpus_version=self.corpus_version(),
            clearance=clearance,
            model_id=model_id,
            user_id=user_id,
            team_id=team_id,
        )
        return tier0, ctx

    def prepare_for_route(
        self,
        query: str,
        route_name: str,
        *,
        user_id: str | None = None,
        team_id: str | None = None,
        clearance: str = "default",
        model_id: str = "",
    ) -> tuple[Tier0Result, CacheContext]:
        rule = self.routes.resolve(route_name)
        return self.prepare(
            query,
            lane=rule.lane,
            sensitivity=rule.sensitivity,
            route_hint=rule.route_hint,
            user_id=user_id,
            team_id=team_id,
            clearance=clearance,
            model_id=model_id,
        )

    def faq_answer(
        self,
        query: str,
        route_name: str,
        generate: GenerateFn,
        *,
        model_id: str = "gpt-4o-mini",
        user_id: str | None = None,
        team_id: str | None = None,
    ) -> FaqAnswerResult:
        """
        FAQ answer path: Tier 1 exact → Tier 2 semantic → generate.

        Coding routes disable Tier 1/2 and always call `generate`.
        """
        rule = self.routes.resolve(route_name)
        tier0, ctx = self.prepare_for_route(
            query,
            route_name,
            user_id=user_id,
            team_id=team_id,
            model_id=model_id,
        )

        if not rule.tier1_enabled and not rule.tier2_enabled:
            text = generate(tier0.normalized_query)
            return FaqAnswerResult(
                text=text,
                from_cache=False,
                cache_tier=None,
                tier1=None,
                tier2=None,
                tier0=tier0,
                ctx=ctx,
            )

        if rule.tier1_enabled:
            t1 = self.tier1.lookup(ctx, tier0, model_id=model_id)
            if t1.hit and t1.answer:
                return FaqAnswerResult(
                    text=t1.answer.text,
                    from_cache=True,
                    cache_tier=CacheTier.TIER1,
                    tier1=t1,
                    tier2=None,
                    tier0=tier0,
                    ctx=ctx,
                )

        if rule.tier2_enabled:
            t2 = self.tier2.lookup(ctx, tier0, model_id=model_id)
            if t2.hit and t2.answer:
                return FaqAnswerResult(
                    text=t2.answer.text,
                    from_cache=True,
                    cache_tier=CacheTier.TIER2,
                    tier1=None,
                    tier2=t2,
                    tier0=tier0,
                    ctx=ctx,
                )

        text = generate(tier0.normalized_query)
        if rule.tier1_enabled:
            self.tier1.store(ctx, tier0, text, model_id=model_id)
        if rule.tier2_enabled:
            self.tier2.store(ctx, tier0, text, model_id=model_id)

        return FaqAnswerResult(
            text=text,
            from_cache=False,
            cache_tier=None,
            tier1=None,
            tier2=None,
            tier0=tier0,
            ctx=ctx,
        )

    def rag_retrieve(
        self,
        query: str,
        retriever: Retriever,
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        user_id: str | None = None,
        team_id: str | None = None,
        route_hint: str | None = None,
        route_name: str | None = None,
    ) -> tuple[list[ChunkResult], Tier0Result, CacheContext, CacheLookupResult]:
        if route_name:
            tier0, ctx = self.prepare_for_route(
                query,
                route_name,
                user_id=user_id,
                team_id=team_id,
            )
        else:
            tier0, ctx = self.prepare(
                query,
                user_id=user_id,
                team_id=team_id,
                route_hint=route_hint,
            )
        chunks, lookup = self.tier3.retrieve_or_fetch(
            ctx,
            tier0,
            retriever,
            top_k=top_k,
            filters=filters,
        )
        return chunks, tier0, ctx, lookup

    def build_tier4_prompt(
        self,
        *,
        user_query: str,
        chunks: list[ChunkResult],
        resolve_chunk_text: ChunkTextResolver,
        system_prompt: str | None = None,
        model_id: str = "claude-sonnet-4-20250514",
        max_tokens: int = 1024,
    ) -> tuple[AssembledPrompt, PromptAuditResult, dict[str, Any]]:
        assembled = assemble_rag_prompt(
            system_prompt=system_prompt or self.config.default_system_prompt,
            chunks=chunks,
            user_query=user_query,
            resolve_chunk_text=resolve_chunk_text,
        )
        audit = audit_assembled(assembled)
        body = anthropic_request_body(assembled, model=model_id, max_tokens=max_tokens)
        return assembled, audit, body

    def rag_prepare(
        self,
        query: str,
        retriever: Retriever,
        resolve_chunk_text: ChunkTextResolver,
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        user_id: str | None = None,
        team_id: str | None = None,
        route_hint: str | None = None,
        route_name: str | None = None,
        system_prompt: str | None = None,
        model_id: str = "claude-sonnet-4-20250514",
        max_tokens: int = 1024,
    ) -> RagPromptBundle:
        chunks, tier0, ctx, lookup = self.rag_retrieve(
            query,
            retriever,
            top_k=top_k,
            filters=filters,
            user_id=user_id,
            team_id=team_id,
            route_hint=route_hint,
            route_name=route_name,
        )
        prompt, audit, body = self.build_tier4_prompt(
            user_query=query,
            chunks=chunks,
            resolve_chunk_text=resolve_chunk_text,
            system_prompt=system_prompt,
            model_id=model_id,
            max_tokens=max_tokens,
        )
        return RagPromptBundle(
            chunks=chunks,
            tier0=tier0,
            ctx=ctx,
            tier3_lookup=lookup,
            prompt=prompt,
            audit=audit,
            anthropic_body=body,
        )

    def record_prefix_cache_usage(
        self,
        usage: dict[str, Any] | PrefixCacheUsage,
        *,
        model_id: str,
        prefix_fingerprint: str,
        provider: str = "anthropic",
    ) -> None:
        if isinstance(usage, dict):
            if provider == "openai":
                parsed = PrefixCacheUsage.from_openai(usage)
            elif provider == "gemini":
                parsed = PrefixCacheUsage.from_gemini(usage)
            else:
                parsed = PrefixCacheUsage.from_anthropic(usage)
        else:
            parsed = usage
        self.prefix_metrics.record(
            parsed,
            model_id=model_id,
            prefix_fingerprint=prefix_fingerprint,
        )

    def invalidate_corpus(self) -> str:
        return self.corpus.bump(self.config.org_id, self.config.corpus_id)

    def metrics_snapshot(self) -> dict[str, Any]:
        return {
            "tiers": self.metrics.snapshot(),
            "prefix_cache": self.prefix_metrics.snapshot(),
        }

    def prefix_cache_dashboard(self) -> str:
        return self.prefix_metrics.dashboard_text()
