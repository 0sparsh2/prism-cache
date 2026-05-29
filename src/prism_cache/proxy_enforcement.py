"""
Route → lane resolution and audit helpers for LiteLLM / app middleware.

Prototype for proxy-level enforcement: classify requests before PRISM write-back.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from prism_cache.models import CacheLane, CacheTier, Sensitivity
from prism_cache.routes import RouteRegistry, RouteRule, default_routes
from prism_cache.tier0 import process_tier0

PRISM_ROUTE_HEADER = "x-prism-route"
PRISM_USER_HEADER = "x-prism-user-id"


@dataclass(frozen=True)
class PrismRequestContext:
    route_name: str
    lane: CacheLane
    sensitivity: Sensitivity
    tier1_enabled: bool
    tier2_enabled: bool
    user_id: str | None = None
    route_hint: str | None = None

    def to_metadata(self) -> dict[str, str]:
        return {
            "prism_route": self.route_name,
            "prism_lane": self.lane.value,
            "prism_sensitivity": self.sensitivity.value,
            "prism_tier1": str(self.tier1_enabled).lower(),
            "prism_tier2": str(self.tier2_enabled).lower(),
            **({"prism_user_id": self.user_id} if self.user_id else {}),
        }


def resolve_route_context(
    route_name: str,
    *,
    user_id: str | None = None,
    routes: RouteRegistry | None = None,
) -> PrismRequestContext:
    rule = (routes or default_routes()).resolve(route_name)
    return PrismRequestContext(
        route_name=rule.name,
        lane=rule.lane,
        sensitivity=rule.sensitivity,
        tier1_enabled=rule.tier1_enabled,
        tier2_enabled=rule.tier2_enabled,
        user_id=user_id,
        route_hint=rule.route_hint,
    )


def resolve_from_headers(
    headers: dict[str, str] | None,
    *,
    routes: RouteRegistry | None = None,
    default_route: str = "internal-faq-bot",
) -> PrismRequestContext:
    """Read PRISM route/user from HTTP headers (case-insensitive keys)."""
    normalized = {k.lower(): v for k, v in (headers or {}).items()}
    route_name = normalized.get(PRISM_ROUTE_HEADER, default_route)
    user_id = normalized.get(PRISM_USER_HEADER)
    return resolve_route_context(route_name, user_id=user_id, routes=routes)


def classify_query_lane(
    query: str,
    ctx: PrismRequestContext,
) -> CacheLane:
    """Tier 0 downgrade (PII, coding hint) applied to resolved route lane."""
    tier0 = process_tier0(
        query,
        requested_lane=ctx.lane,
        sensitivity=ctx.sensitivity,
        route_hint=ctx.route_hint,
    )
    return tier0.lane


@dataclass(frozen=True)
class PrismAuditEvent:
    ts_ms: int
    route: str
    lane: str
    tier: str
    event: str  # hit | miss | write | write_denied
    user_id: str | None = None
    denial_reason: str | None = None
    cache_key_hash: str | None = None

    def to_json_line(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def now(
        cls,
        *,
        ctx: PrismRequestContext,
        tier: CacheTier,
        event: str,
        denial_reason: str | None = None,
        cache_key_hash: str | None = None,
    ) -> PrismAuditEvent:
        return cls(
            ts_ms=int(time.time() * 1000),
            route=ctx.route_name,
            lane=ctx.lane.value,
            tier=tier.value,
            event=event,
            user_id=ctx.user_id,
            denial_reason=denial_reason,
            cache_key_hash=cache_key_hash,
        )


def inject_litellm_metadata(
    request_data: dict[str, Any],
    ctx: PrismRequestContext,
) -> dict[str, Any]:
    """Merge PRISM lane metadata into a LiteLLM/OpenAI request body."""
    meta = dict(request_data.get("metadata") or {})
    meta.update(ctx.to_metadata())
    out = dict(request_data)
    out["metadata"] = meta
    return out
