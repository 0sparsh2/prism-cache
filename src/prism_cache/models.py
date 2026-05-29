from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CacheLane(str, Enum):
    """Who may read a cached entry."""

    USER_PRIVATE = "user-private"
    TEAM = "team"
    ORG_STATIC = "org-static"


class Sensitivity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CacheTier(str, Enum):
    TIER0 = "tier0"
    TIER1 = "tier1"
    TIER2 = "tier2"
    TIER3 = "tier3"
    TIER4 = "tier4"


@dataclass(frozen=True)
class CacheContext:
    """Dimensions included in every org-scoped cache key."""

    org_id: str
    lane: CacheLane
    sensitivity: Sensitivity
    corpus_version: str
    clearance: str = "default"
    model_id: str = ""
    user_id: str | None = None
    team_id: str | None = None


@dataclass(frozen=True)
class Tier0Result:
    normalized_query: str
    query_hash: str
    lane: CacheLane
    sensitivity: Sensitivity
    pii_detected: bool
    blocked_shared_write: bool


@dataclass(frozen=True)
class ChunkResult:
    chunk_id: str
    score: float
    text_hash: str | None = None


@dataclass(frozen=True)
class RetrievalHit:
    chunk_ids: tuple[str, ...]
    scores: tuple[float, ...]
    text_hashes: tuple[str | None, ...] = field(default_factory=tuple)

    @classmethod
    def from_chunks(cls, chunks: list[ChunkResult]) -> RetrievalHit:
        return cls(
            chunk_ids=tuple(c.chunk_id for c in chunks),
            scores=tuple(c.score for c in chunks),
            text_hashes=tuple(c.text_hash for c in chunks),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_ids": list(self.chunk_ids),
            "scores": list(self.scores),
            "text_hashes": list(self.text_hashes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetrievalHit:
        ids = data["chunk_ids"]
        scores = data["scores"]
        raw_hashes = data.get("text_hashes")
        if not raw_hashes:
            raw_hashes = [None] * len(ids)
        return cls(
            chunk_ids=tuple(ids),
            scores=tuple(float(s) for s in scores),
            text_hashes=tuple(raw_hashes),
        )


@dataclass
class CacheLookupResult:
    tier: CacheTier
    hit: bool
    retrieval: RetrievalHit | None = None
    cache_key: str | None = None
    latency_ms: float = 0.0
