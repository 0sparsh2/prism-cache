from __future__ import annotations

from prism_cache.models import CacheContext, CacheLane, CacheTier, Tier0Result


def allows_cross_user_read(ctx: CacheContext) -> bool:
    return ctx.lane in (CacheLane.TEAM, CacheLane.ORG_STATIC)


def allows_tier3_shared_write(ctx: CacheContext, tier0: Tier0Result) -> bool:
    if tier0.blocked_shared_write or tier0.pii_detected:
        return False
    if ctx.lane == CacheLane.USER_PRIVATE:
        return ctx.user_id is not None
    return allows_cross_user_read(ctx) or ctx.lane == CacheLane.TEAM


def allows_tier1_write(ctx: CacheContext, tier0: Tier0Result) -> bool:
    """Tier 1 exact FAQ — org-static cross-user; user-private per user_id only."""
    if tier0.pii_detected:
        return False
    if ctx.lane == CacheLane.ORG_STATIC:
        return True
    if ctx.lane == CacheLane.USER_PRIVATE and ctx.user_id:
        return True
    return False


def allows_tier2_shared_write(ctx: CacheContext, tier0: Tier0Result) -> bool:
    """Tier 2 (full answer semantic) — org-static FAQ only in v1."""
    if not allows_tier3_shared_write(ctx, tier0):
        return False
    return ctx.lane == CacheLane.ORG_STATIC and tier0.sensitivity.value == "low"


def write_policy_denial_reason(
    ctx: CacheContext,
    tier0: Tier0Result,
    tier: CacheTier,
) -> str | None:
    if tier == CacheTier.TIER3 and allows_tier3_shared_write(ctx, tier0):
        return None
    if tier == CacheTier.TIER2 and allows_tier2_shared_write(ctx, tier0):
        return None
    if tier == CacheTier.TIER1 and allows_tier1_write(ctx, tier0):
        return None
    if tier0.pii_detected:
        return "pii_detected"
    if tier0.blocked_shared_write:
        return "lane_downgraded"
    return "policy_denied"
