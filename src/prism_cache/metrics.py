from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from prism_cache.models import CacheLane, CacheTier


@dataclass
class TierMetrics:
    hits: int = 0
    misses: int = 0
    writes: int = 0
    write_denied: int = 0
    latency_ms_total: float = 0.0
    lookups: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.latency_ms_total / self.lookups if self.lookups else 0.0


@dataclass
class MetricsRegistry:
    """In-process metrics; export to Prometheus/OTel in production."""

    _lock: Lock = field(default_factory=Lock, repr=False)
    by_tier_lane: dict[tuple[str, str], TierMetrics] = field(default_factory=dict)

    def _bucket(self, tier: CacheTier, lane: CacheLane) -> TierMetrics:
        key = (tier.value, lane.value)
        if key not in self.by_tier_lane:
            self.by_tier_lane[key] = TierMetrics()
        return self.by_tier_lane[key]

    def record_lookup(
        self,
        tier: CacheTier,
        lane: CacheLane,
        *,
        hit: bool,
        latency_ms: float,
    ) -> None:
        with self._lock:
            m = self._bucket(tier, lane)
            m.lookups += 1
            m.latency_ms_total += latency_ms
            if hit:
                m.hits += 1
            else:
                m.misses += 1

    def record_write(self, tier: CacheTier, lane: CacheLane, *, allowed: bool) -> None:
        with self._lock:
            m = self._bucket(tier, lane)
            if allowed:
                m.writes += 1
            else:
                m.write_denied += 1

    def snapshot(self) -> dict[str, dict[str, float | int]]:
        with self._lock:
            out: dict[str, dict[str, float | int]] = {}
            for (tier, lane), m in self.by_tier_lane.items():
                out[f"{tier}:{lane}"] = {
                    "hits": m.hits,
                    "misses": m.misses,
                    "writes": m.writes,
                    "write_denied": m.write_denied,
                    "hit_rate": round(m.hit_rate, 4),
                    "avg_latency_ms": round(m.avg_latency_ms, 3),
                }
            return out
