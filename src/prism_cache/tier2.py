from __future__ import annotations

import json
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

from prism_cache.keys import build_tier2_bucket_key
from prism_cache.metrics import MetricsRegistry
from prism_cache.models import CacheContext, CacheLookupResult, CacheTier, Tier0Result
from prism_cache.policy import allows_tier2_shared_write, write_policy_denial_reason
from prism_cache.tier1 import CachedAnswer, GenerateFn

EmbedFn = Callable[[str], tuple[float, ...]]


def cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def hash_bag_embed(text: str, *, dims: int = 256) -> tuple[float, ...]:
    """Deterministic bag-of-words embedder for tests and local dev (no ML deps)."""
    vec = [0.0] * dims
    for token in text.split():
        idx = hash(token) % dims
        vec[idx] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return tuple(x / norm for x in vec)


@dataclass(frozen=True)
class SemanticEntry:
    embedding: tuple[float, ...]
    query_text: str
    answer: CachedAnswer
    similarity_threshold: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "embedding": list(self.embedding),
            "query_text": self.query_text,
            "answer": self.answer.to_dict(),
            "similarity_threshold": self.similarity_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticEntry:
        return cls(
            embedding=tuple(float(x) for x in data["embedding"]),
            query_text=str(data["query_text"]),
            answer=CachedAnswer.from_dict(data["answer"]),
            similarity_threshold=(
                float(data["similarity_threshold"])
                if data.get("similarity_threshold") is not None
                else None
            ),
        )


@dataclass
class Tier2LookupResult(CacheLookupResult):
    answer: CachedAnswer | None = None
    similarity: float = 0.0
    matched_query: str | None = None


class SemanticAnswerStore(ABC):
    @abstractmethod
    def list_entries(self, bucket_key: str) -> list[SemanticEntry]: ...

    @abstractmethod
    def append(self, bucket_key: str, entry: SemanticEntry) -> None: ...

    @abstractmethod
    def replace_bucket(self, bucket_key: str, entries: list[SemanticEntry]) -> None: ...


class InMemorySemanticStore(SemanticAnswerStore):
    def __init__(self) -> None:
        self._buckets: dict[str, list[SemanticEntry]] = {}

    def list_entries(self, bucket_key: str) -> list[SemanticEntry]:
        return list(self._buckets.get(bucket_key, []))

    def append(self, bucket_key: str, entry: SemanticEntry) -> None:
        self._buckets.setdefault(bucket_key, []).append(entry)

    def replace_bucket(self, bucket_key: str, entries: list[SemanticEntry]) -> None:
        self._buckets[bucket_key] = list(entries)


class RedisSemanticStore(SemanticAnswerStore):
    def __init__(self, redis_url: str, *, key_prefix: str = "prism:t2") -> None:
        import redis

        self._client = redis.from_url(redis_url, decode_responses=True)
        self._prefix = key_prefix

    def _full(self, bucket_key: str) -> str:
        return f"{self._prefix}:{bucket_key}"

    def list_entries(self, bucket_key: str) -> list[SemanticEntry]:
        raw = self._client.get(self._full(bucket_key))
        if not raw:
            return []
        return [SemanticEntry.from_dict(item) for item in json.loads(raw)]

    def append(self, bucket_key: str, entry: SemanticEntry) -> None:
        entries = self.list_entries(bucket_key)
        entries.append(entry)
        self._client.set(self._full(bucket_key), json.dumps([e.to_dict() for e in entries]))

    def replace_bucket(self, bucket_key: str, entries: list[SemanticEntry]) -> None:
        payload = json.dumps([e.to_dict() for e in entries])
        self._client.set(self._full(bucket_key), payload)


class Tier2SemanticCache:
    """
    Tier 2 — paraphrase → full answer cache (org-static FAQ lane only).

    Lookup embeds the normalized query and returns the best prior answer when
    cosine similarity ≥ threshold (default 0.95). Optional per-entry thresholds
    support vCache-style stricter gates on sensitive entries.
    """

    def __init__(
        self,
        store: SemanticAnswerStore,
        embed: EmbedFn,
        *,
        metrics: MetricsRegistry | None = None,
        default_threshold: float = 0.95,
        default_ttl_seconds: int | None = None,
    ) -> None:
        self._store = store
        self._embed = embed
        self._metrics = metrics or MetricsRegistry()
        self._default_threshold = default_threshold
        self._default_ttl = default_ttl_seconds

    def _bucket(self, ctx: CacheContext, *, model_id: str) -> str:
        return build_tier2_bucket_key(ctx, model_id=model_id)

    def lookup(
        self,
        ctx: CacheContext,
        tier0: Tier0Result,
        *,
        model_id: str,
        threshold: float | None = None,
    ) -> Tier2LookupResult:
        start = time.perf_counter()
        bucket = self._bucket(ctx, model_id=model_id)
        query_vec = self._embed(tier0.normalized_query)
        min_score = threshold if threshold is not None else self._default_threshold

        best: SemanticEntry | None = None
        best_score = 0.0
        for entry in self._store.list_entries(bucket):
            score = cosine_similarity(query_vec, entry.embedding)
            entry_threshold = (
                entry.similarity_threshold
                if entry.similarity_threshold is not None
                else min_score
            )
            if score >= entry_threshold and score > best_score:
                best = entry
                best_score = score

        latency_ms = (time.perf_counter() - start) * 1000
        hit = best is not None
        self._metrics.record_lookup(CacheTier.TIER2, ctx.lane, hit=hit, latency_ms=latency_ms)
        return Tier2LookupResult(
            tier=CacheTier.TIER2,
            hit=hit,
            answer=best.answer if best else None,
            similarity=best_score,
            matched_query=best.query_text if best else None,
            cache_key=bucket,
            latency_ms=latency_ms,
        )

    def store(
        self,
        ctx: CacheContext,
        tier0: Tier0Result,
        answer_text: str,
        *,
        model_id: str,
        similarity_threshold: float | None = None,
        ttl_seconds: int | None = None,
    ) -> tuple[bool, str | None]:
        if not allows_tier2_shared_write(ctx, tier0):
            reason = write_policy_denial_reason(ctx, tier0, CacheTier.TIER2)
            self._metrics.record_write(CacheTier.TIER2, ctx.lane, allowed=False)
            return False, reason

        bucket = self._bucket(ctx, model_id=model_id)
        entry = SemanticEntry(
            embedding=self._embed(tier0.normalized_query),
            query_text=tier0.normalized_query,
            answer=CachedAnswer(text=answer_text, model_id=model_id),
            similarity_threshold=similarity_threshold,
        )
        self._store.append(bucket, entry)
        _ = ttl_seconds if ttl_seconds is not None else self._default_ttl
        self._metrics.record_write(CacheTier.TIER2, ctx.lane, allowed=True)
        return True, None

    def lookup_or_generate(
        self,
        ctx: CacheContext,
        tier0: Tier0Result,
        generate: GenerateFn,
        *,
        model_id: str,
        threshold: float | None = None,
        query_for_generate: str | None = None,
    ) -> tuple[str, Tier2LookupResult]:
        lookup = self.lookup(ctx, tier0, model_id=model_id, threshold=threshold)
        if lookup.hit and lookup.answer:
            return lookup.answer.text, lookup

        text = generate(query_for_generate or tier0.normalized_query)
        self.store(ctx, tier0, text, model_id=model_id)
        return text, lookup
