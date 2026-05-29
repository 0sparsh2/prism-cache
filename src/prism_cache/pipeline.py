from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from prism_cache.corpus import CorpusVersionProvider, InMemoryCorpusVersionProvider
from prism_cache.metrics import MetricsRegistry
from prism_cache.models import (
    CacheContext,
    CacheLane,
    CacheLookupResult,
    ChunkResult,
    Sensitivity,
    Tier0Result,
)
from prism_cache.prefix_metrics import PrefixCacheMetricsRegistry, PrefixCacheUsage
from prism_cache.prompt_audit import PromptAuditResult, audit_assembled
from prism_cache.tier0 import process_tier0
from prism_cache.tier3 import InMemoryRetrievalStore, Retriever, RetrievalStore, Tier3RetrievalCache
from prism_cache.tier4 import AssembledPrompt, ChunkTextResolver, assemble_rag_prompt, anthropic_request_body


@dataclass
class PrismConfig:
    org_id: str
    corpus_id: str = "default"
    default_lane: CacheLane = CacheLane.ORG_STATIC
    default_sensitivity: Sensitivity = Sensitivity.LOW
    embed_model_id: str = "text-embedding-3-small"
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


class PrismPipeline:
    """Orchestrates Tier 0 prep, Tier 3 retrieval cache, and Tier 4 prefix assembly."""

    def __init__(
        self,
        config: PrismConfig,
        *,
        store: RetrievalStore | None = None,
        corpus: CorpusVersionProvider | None = None,
        metrics: MetricsRegistry | None = None,
        prefix_metrics: PrefixCacheMetricsRegistry | None = None,
    ) -> None:
        self.config = config
        self.corpus = corpus or InMemoryCorpusVersionProvider()
        self.metrics = metrics or MetricsRegistry()
        self.prefix_metrics = prefix_metrics or PrefixCacheMetricsRegistry()
        self.tier3 = Tier3RetrievalCache(
            store or InMemoryRetrievalStore(),
            embed_model_id=config.embed_model_id,
            metrics=self.metrics,
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
    ) -> tuple[list[ChunkResult], Tier0Result, CacheContext, CacheLookupResult]:
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
        """Assemble cache-friendly RAG prompt and Anthropic API body."""
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
        system_prompt: str | None = None,
        model_id: str = "claude-sonnet-4-20250514",
        max_tokens: int = 1024,
    ) -> RagPromptBundle:
        """Tier 3 retrieve + Tier 4 prefix assembly + audit."""
        chunks, tier0, ctx, lookup = self.rag_retrieve(
            query,
            retriever,
            top_k=top_k,
            filters=filters,
            user_id=user_id,
            team_id=team_id,
            route_hint=route_hint,
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
        """Record cache_read_input_tokens / cache_creation_input_tokens from LLM response."""
        if isinstance(usage, dict):
            if provider == "openai":
                parsed = PrefixCacheUsage.from_openai(usage)
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
        """Bump corpus version so new keys miss old entries."""
        return self.corpus.bump(self.config.org_id, self.config.corpus_id)

    def metrics_snapshot(self) -> dict[str, Any]:
        return {
            "tiers": self.metrics.snapshot(),
            "prefix_cache": self.prefix_metrics.snapshot(),
        }

    def prefix_cache_dashboard(self) -> str:
        return self.prefix_metrics.dashboard_text()
