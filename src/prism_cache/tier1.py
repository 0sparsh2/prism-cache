from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

from prism_cache.keys import build_cache_key, build_tier1_key_parts
from prism_cache.metrics import MetricsRegistry
from prism_cache.models import CacheContext, CacheLane, CacheLookupResult, CacheTier, Tier0Result
from prism_cache.policy import allows_tier1_write, write_policy_denial_reason


@dataclass(frozen=True)
class CachedAnswer:
    text: str
    model_id: str

    def to_dict(self) -> dict[str, str]:
        return {"text": self.text, "model_id": self.model_id}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CachedAnswer:
        return cls(text=str(data["text"]), model_id=str(data.get("model_id") or "default"))


@dataclass
class Tier1LookupResult(CacheLookupResult):
    answer: CachedAnswer | None = None


class ExactAnswerStore(ABC):
    @abstractmethod
    def get(self, key: str) -> CachedAnswer | None: ...

    @abstractmethod
    def set(self, key: str, value: CachedAnswer, *, ttl_seconds: int | None = None) -> None: ...


class InMemoryExactStore(ExactAnswerStore):
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def get(self, key: str) -> CachedAnswer | None:
        raw = self._data.get(key)
        return CachedAnswer.from_dict(json.loads(raw)) if raw else None

    def set(self, key: str, value: CachedAnswer, *, ttl_seconds: int | None = None) -> None:
        self._data[key] = json.dumps(value.to_dict())


class RedisExactStore(ExactAnswerStore):
    def __init__(self, redis_url: str, *, key_prefix: str = "prism:t1") -> None:
        import redis

        self._client = redis.from_url(redis_url, decode_responses=True)
        self._prefix = key_prefix

    def _full(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    def get(self, key: str) -> CachedAnswer | None:
        raw = self._client.get(self._full(key))
        return CachedAnswer.from_dict(json.loads(raw)) if raw else None

    def set(self, key: str, value: CachedAnswer, *, ttl_seconds: int | None = None) -> None:
        full = self._full(key)
        payload = json.dumps(value.to_dict())
        if ttl_seconds:
            self._client.setex(full, ttl_seconds, payload)
        else:
            self._client.set(full, payload)


GenerateFn = Callable[[str], str]


class Tier1ExactCache:
    """Exact-match FAQ answer cache (org-static lane by default)."""

    def __init__(
        self,
        store: ExactAnswerStore,
        *,
        metrics: MetricsRegistry | None = None,
        default_ttl_seconds: int | None = None,
    ) -> None:
        self._store = store
        self._metrics = metrics or MetricsRegistry()
        self._default_ttl = default_ttl_seconds

    def _key(self, ctx: CacheContext, tier0: Tier0Result, *, model_id: str) -> str:
        parts = build_tier1_key_parts(query_hash=tier0.query_hash, model_id=model_id)
        ctx_with_model = CacheContext(
            org_id=ctx.org_id,
            lane=ctx.lane,
            sensitivity=ctx.sensitivity,
            corpus_version=ctx.corpus_version,
            clearance=ctx.clearance,
            model_id=model_id,
            user_id=ctx.user_id,
            team_id=ctx.team_id,
        )
        return build_cache_key(ctx_with_model, CacheTier.TIER1, parts=parts)

    def lookup(
        self,
        ctx: CacheContext,
        tier0: Tier0Result,
        *,
        model_id: str,
    ) -> Tier1LookupResult:
        start = time.perf_counter()
        key = self._key(ctx, tier0, model_id=model_id)
        answer = self._store.get(key)
        latency_ms = (time.perf_counter() - start) * 1000
        hit = answer is not None
        self._metrics.record_lookup(CacheTier.TIER1, ctx.lane, hit=hit, latency_ms=latency_ms)
        return Tier1LookupResult(
            tier=CacheTier.TIER1,
            hit=hit,
            answer=answer,
            cache_key=key,
            latency_ms=latency_ms,
        )

    def store(
        self,
        ctx: CacheContext,
        tier0: Tier0Result,
        answer_text: str,
        *,
        model_id: str,
        ttl_seconds: int | None = None,
    ) -> tuple[bool, str | None]:
        if not allows_tier1_write(ctx, tier0):
            reason = write_policy_denial_reason(ctx, tier0, CacheTier.TIER1)
            self._metrics.record_write(CacheTier.TIER1, ctx.lane, allowed=False)
            return False, reason

        key = self._key(ctx, tier0, model_id=model_id)
        self._store.set(
            key,
            CachedAnswer(text=answer_text, model_id=model_id),
            ttl_seconds=ttl_seconds if ttl_seconds is not None else self._default_ttl,
        )
        self._metrics.record_write(CacheTier.TIER1, ctx.lane, allowed=True)
        return True, None

    def lookup_or_generate(
        self,
        ctx: CacheContext,
        tier0: Tier0Result,
        generate: GenerateFn,
        *,
        model_id: str,
        query_for_generate: str | None = None,
    ) -> tuple[str, Tier1LookupResult]:
        lookup = self.lookup(ctx, tier0, model_id=model_id)
        if lookup.hit and lookup.answer:
            return lookup.answer.text, lookup

        text = generate(query_for_generate or tier0.normalized_query)
        self.store(ctx, tier0, text, model_id=model_id)
        return text, lookup
