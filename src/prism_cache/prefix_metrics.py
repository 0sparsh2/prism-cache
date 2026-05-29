from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class PrefixCacheUsage:
    """Normalized usage fields from Anthropic/OpenAI responses."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @classmethod
    def from_anthropic(cls, usage: dict[str, Any]) -> PrefixCacheUsage:
        return cls(
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            cache_creation_input_tokens=int(usage.get("cache_creation_input_tokens") or 0),
            cache_read_input_tokens=int(usage.get("cache_read_input_tokens") or 0),
        )

    @classmethod
    def from_openai(cls, usage: dict[str, Any]) -> PrefixCacheUsage:
        details = usage.get("prompt_tokens_details") or {}
        cached = int(details.get("cached_tokens") or 0)
        return cls(
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            cache_read_input_tokens=cached,
        )

    @property
    def had_cache_read(self) -> bool:
        return self.cache_read_input_tokens > 0

    @property
    def had_cache_write(self) -> bool:
        return self.cache_creation_input_tokens > 0


@dataclass
class PrefixCacheMetrics:
    requests: int = 0
    cache_read_hits: int = 0
    cache_write_events: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    by_fingerprint: dict[str, int] = field(default_factory=dict)


@dataclass
class PrefixCacheMetricsRegistry:
    """Track provider prefix cache token metrics (Tier 4 dashboard)."""

    _lock: Lock = field(default_factory=Lock, repr=False)
    totals: PrefixCacheMetrics = field(default_factory=PrefixCacheMetrics)
    by_model: dict[str, PrefixCacheMetrics] = field(default_factory=dict)

    def _bucket(self, model_id: str) -> PrefixCacheMetrics:
        if model_id not in self.by_model:
            self.by_model[model_id] = PrefixCacheMetrics()
        return self.by_model[model_id]

    def record(
        self,
        usage: PrefixCacheUsage,
        *,
        model_id: str,
        prefix_fingerprint: str | None = None,
    ) -> None:
        with self._lock:
            for bucket in (self.totals, self._bucket(model_id)):
                bucket.requests += 1
                bucket.input_tokens += usage.input_tokens
                bucket.output_tokens += usage.output_tokens
                bucket.cache_creation_input_tokens += usage.cache_creation_input_tokens
                bucket.cache_read_input_tokens += usage.cache_read_input_tokens
                if usage.had_cache_read:
                    bucket.cache_read_hits += 1
                if usage.had_cache_write:
                    bucket.cache_write_events += 1
                if prefix_fingerprint:
                    bucket.by_fingerprint[prefix_fingerprint] = (
                        bucket.by_fingerprint.get(prefix_fingerprint, 0) + 1
                    )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "totals": _metrics_to_dict(self.totals),
                "by_model": {m: _metrics_to_dict(v) for m, v in self.by_model.items()},
            }

    def dashboard_text(self) -> str:
        snap = self.snapshot()
        t = snap["totals"]
        lines = [
            "PRISM Tier 4 — Prefix cache dashboard",
            "=" * 44,
            f"Requests:              {t['requests']}",
            f"Cache read hits:         {t['cache_read_hits']} ({t['cache_read_hit_rate']:.1%})",
            f"Cache write events:      {t['cache_write_events']}",
            f"Input tokens:            {t['input_tokens']}",
            f"Cache creation tokens:   {t['cache_creation_input_tokens']}",
            f"Cache read tokens:       {t['cache_read_input_tokens']}",
            f"Est. prefix reuse ratio: {t['cache_read_token_ratio']:.1%} of input from cache",
            f"Output tokens:           {t['output_tokens']}",
        ]
        if snap["by_model"]:
            lines.append("")
            lines.append("By model:")
            for model, m in snap["by_model"].items():
                lines.append(
                    f"  {model}: read_hits={m['cache_read_hits']}/{m['requests']} "
                    f"read_tokens={m['cache_read_input_tokens']}"
                )
        top_fp = sorted(t.get("top_fingerprints", []), key=lambda x: x["count"], reverse=True)[:5]
        if top_fp:
            lines.append("")
            lines.append("Top prefix fingerprints (reuse):")
            for row in top_fp:
                lines.append(f"  {row['fingerprint'][:16]}…  count={row['count']}")
        return "\n".join(lines)


def _metrics_to_dict(m: PrefixCacheMetrics) -> dict[str, Any]:
    req = m.requests or 1
    inp = m.input_tokens or 1
    top_fp = [{"fingerprint": k, "count": v} for k, v in m.by_fingerprint.items()]
    return {
        "requests": m.requests,
        "cache_read_hits": m.cache_read_hits,
        "cache_read_hit_rate": round(m.cache_read_hits / req, 4),
        "cache_write_events": m.cache_write_events,
        "input_tokens": m.input_tokens,
        "output_tokens": m.output_tokens,
        "cache_creation_input_tokens": m.cache_creation_input_tokens,
        "cache_read_input_tokens": m.cache_read_input_tokens,
        "cache_read_token_ratio": round(m.cache_read_input_tokens / inp, 4),
        "top_fingerprints": top_fp,
    }
