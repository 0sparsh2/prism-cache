from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Protocol

from prism_cache.keys import build_cache_key, build_tier3_key_parts
from prism_cache.metrics import MetricsRegistry
from prism_cache.models import (
    CacheContext,
    CacheLookupResult,
    CacheTier,
    ChunkResult,
    RetrievalHit,
    Tier0Result,
)
from prism_cache.policy import allows_tier3_shared_write, write_policy_denial_reason


class RetrievalStore(ABC):
    @abstractmethod
    def get(self, key: str) -> RetrievalHit | None: ...

    @abstractmethod
    def set(self, key: str, value: RetrievalHit, *, ttl_seconds: int | None = None) -> None: ...

    @abstractmethod
    def delete_by_corpus_prefix(self, org_id: str, corpus_version: str) -> int: ...


class InMemoryRetrievalStore(RetrievalStore):
    """For tests and local dev without Redis."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float | None]] = {}

    def get(self, key: str) -> RetrievalHit | None:
        entry = self._data.get(key)
        if not entry:
            return None
        payload, _expires = entry
        return RetrievalHit.from_dict(json.loads(payload))

    def set(self, key: str, value: RetrievalHit, *, ttl_seconds: int | None = None) -> None:
        expires = time.time() + ttl_seconds if ttl_seconds else None
        self._data[key] = (json.dumps(value.to_dict()), expires)

    def delete_by_corpus_prefix(self, org_id: str, corpus_version: str) -> int:
        prefix = f"prism:{org_id}:"
        removed = 0
        for key in list(self._data):
            if key.startswith(prefix) and corpus_version in key:
                del self._data[key]
                removed += 1
        return removed


class RedisRetrievalStore(RetrievalStore):
    """Production Tier 3 backend. Requires redis package."""

    def __init__(self, redis_url: str, *, key_prefix: str = "prism:t3") -> None:
        import redis

        self._client = redis.from_url(redis_url, decode_responses=True)
        self._key_prefix = key_prefix

    def _full_key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"

    def get(self, key: str) -> RetrievalHit | None:
        raw = self._client.get(self._full_key(key))
        if not raw:
            return None
        return RetrievalHit.from_dict(json.loads(raw))

    def set(self, key: str, value: RetrievalHit, *, ttl_seconds: int | None = None) -> None:
        full = self._full_key(key)
        if ttl_seconds:
            self._client.setex(full, ttl_seconds, json.dumps(value.to_dict()))
        else:
            self._client.set(full, json.dumps(value.to_dict()))

    def delete_by_corpus_prefix(self, org_id: str, corpus_version: str) -> int:
        pattern = f"{self._key_prefix}:prism:{org_id}:*"
        removed = 0
        for key in self._client.scan_iter(match=pattern, count=500):
            if corpus_version in key:
                self._client.delete(key)
                removed += 1
        return removed


class Retriever(Protocol):
    def __call__(
        self,
        query: str,
        *,
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[ChunkResult]: ...


class Tier3RetrievalCache:
    """Cache retrieval results (chunk IDs + scores) for cross-user RAG reuse."""

    def __init__(
        self,
        store: RetrievalStore,
        *,
        embed_model_id: str = "default",
        metrics: MetricsRegistry | None = None,
        default_ttl_seconds: int | None = None,
    ) -> None:
        self._store = store
        self._embed_model_id = embed_model_id
        self._metrics = metrics or MetricsRegistry()
        self._default_ttl = default_ttl_seconds

    @property
    def metrics(self) -> MetricsRegistry:
        return self._metrics

    def _key(
        self,
        ctx: CacheContext,
        tier0: Tier0Result,
        *,
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> str:
        parts = build_tier3_key_parts(
            query_hash=tier0.query_hash,
            embed_model_id=self._embed_model_id,
            top_k=top_k,
            filters=filters,
        )
        return build_cache_key(ctx, CacheTier.TIER3, parts=parts)

    def lookup(
        self,
        ctx: CacheContext,
        tier0: Tier0Result,
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> CacheLookupResult:
        start = time.perf_counter()
        key = self._key(ctx, tier0, top_k=top_k, filters=filters)
        hit = self._store.get(key)
        latency_ms = (time.perf_counter() - start) * 1000
        self._metrics.record_lookup(
            CacheTier.TIER3,
            ctx.lane,
            hit=hit is not None,
            latency_ms=latency_ms,
        )
        return CacheLookupResult(
            tier=CacheTier.TIER3,
            hit=hit is not None,
            retrieval=hit,
            cache_key=key,
            latency_ms=latency_ms,
        )

    def store(
        self,
        ctx: CacheContext,
        tier0: Tier0Result,
        chunks: list[ChunkResult],
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> tuple[bool, str | None]:
        allowed = allows_tier3_shared_write(ctx, tier0)
        if not allowed:
            reason = write_policy_denial_reason(ctx, tier0, CacheTier.TIER3)
            self._metrics.record_write(CacheTier.TIER3, ctx.lane, allowed=False)
            return False, reason

        key = self._key(ctx, tier0, top_k=top_k, filters=filters)
        self._store.set(
            key,
            RetrievalHit.from_chunks(chunks),
            ttl_seconds=ttl_seconds if ttl_seconds is not None else self._default_ttl,
        )
        self._metrics.record_write(CacheTier.TIER3, ctx.lane, allowed=True)
        return True, None

    def retrieve_or_fetch(
        self,
        ctx: CacheContext,
        tier0: Tier0Result,
        retriever: Retriever,
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        write_on_miss: bool = True,
    ) -> tuple[list[ChunkResult], CacheLookupResult]:
        """Primary RAG integration: lookup → skip vector DB on hit."""
        lookup = self.lookup(ctx, tier0, top_k=top_k, filters=filters)
        if lookup.hit and lookup.retrieval:
            chunks = [
                ChunkResult(chunk_id=cid, score=score, text_hash=th)
                for cid, score, th in zip(
                    lookup.retrieval.chunk_ids,
                    lookup.retrieval.scores,
                    lookup.retrieval.text_hashes or [None] * len(lookup.retrieval.chunk_ids),
                    strict=True,
                )
            ]
            return chunks, lookup

        chunks = retriever(tier0.normalized_query, top_k=top_k, filters=filters)
        if write_on_miss:
            self.store(ctx, tier0, chunks, top_k=top_k, filters=filters)
        return chunks, lookup
