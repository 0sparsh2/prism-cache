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
from prism_cache.tier0 import process_tier0
from prism_cache.tier3 import InMemoryRetrievalStore, Retriever, RetrievalStore, Tier3RetrievalCache


@dataclass
class PrismConfig:
    org_id: str
    corpus_id: str = "default"
    default_lane: CacheLane = CacheLane.ORG_STATIC
    default_sensitivity: Sensitivity = Sensitivity.LOW
    embed_model_id: str = "text-embedding-3-small"


class PrismPipeline:
    """Orchestrates Tier 0 prep + Tier 3 retrieval cache."""

    def __init__(
        self,
        config: PrismConfig,
        *,
        store: RetrievalStore | None = None,
        corpus: CorpusVersionProvider | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self.config = config
        self.corpus = corpus or InMemoryCorpusVersionProvider()
        self.metrics = metrics or MetricsRegistry()
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

    def invalidate_corpus(self) -> str:
        """Bump corpus version so new keys miss old entries."""
        return self.corpus.bump(self.config.org_id, self.config.corpus_id)

    def metrics_snapshot(self) -> dict[str, dict[str, float | int]]:
        return self.metrics.snapshot()
