from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prism_cache.models import CacheLane, Sensitivity
from prism_cache.pipeline import PrismConfig
from prism_cache.routes import RouteRegistry


@dataclass
class RedisSettings:
    url: str = "redis://localhost:6379/0"
    tier1_key_prefix: str = "prism:t1"
    tier3_key_prefix: str = "prism:t3"
    ttl_seconds: int | None = None


@dataclass
class PrismSettings:
    org_id: str
    corpus_id: str = "default"
    default_lane: CacheLane = CacheLane.ORG_STATIC
    default_sensitivity: Sensitivity = Sensitivity.LOW
    embed_model_id: str = "text-embedding-3-small"
    redis: RedisSettings = field(default_factory=RedisSettings)
    routes: RouteRegistry | None = None

    def to_pipeline_config(self) -> PrismConfig:
        return PrismConfig(
            org_id=self.org_id,
            corpus_id=self.corpus_id,
            default_lane=self.default_lane,
            default_sensitivity=self.default_sensitivity,
            embed_model_id=self.embed_model_id,
        )


def parse_settings(data: dict[str, Any]) -> PrismSettings:
    defaults = data.get("defaults") or {}
    redis_raw = data.get("redis") or {}
    routes_raw = data.get("routes")

    routes = RouteRegistry.from_mapping(routes_raw) if routes_raw else None

    return PrismSettings(
        org_id=str(data["org_id"]),
        corpus_id=str(data.get("corpus_id") or "default"),
        default_lane=CacheLane(defaults.get("lane", "org-static")),
        default_sensitivity=Sensitivity(defaults.get("sensitivity", "low")),
        embed_model_id=str(defaults.get("embed_model_id") or "text-embedding-3-small"),
        redis=RedisSettings(
            url=str(redis_raw.get("url") or "redis://localhost:6379/0"),
            tier1_key_prefix=str(redis_raw.get("tier1_key_prefix") or "prism:t1"),
            tier3_key_prefix=str(redis_raw.get("tier3_key_prefix") or "prism:t3"),
            ttl_seconds=redis_raw.get("ttl_seconds"),
        ),
        routes=routes,
    )


def load_settings(path: str | Path) -> PrismSettings:
    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return parse_settings(data)
