from prism_cache.models import CacheContext, CacheLane, CacheTier, Sensitivity, Tier0Result
from prism_cache.policy import (
    allows_tier2_shared_write,
    allows_tier3_shared_write,
    write_policy_denial_reason,
)


def _tier0(**kwargs) -> Tier0Result:
    defaults = dict(
        normalized_query="q",
        query_hash="h",
        lane=CacheLane.ORG_STATIC,
        sensitivity=Sensitivity.LOW,
        pii_detected=False,
        blocked_shared_write=False,
    )
    defaults.update(kwargs)
    return Tier0Result(**defaults)


def test_org_static_allows_tier3():
    ctx = CacheContext(
        org_id="o",
        lane=CacheLane.ORG_STATIC,
        sensitivity=Sensitivity.LOW,
        corpus_version="1",
    )
    assert allows_tier3_shared_write(ctx, _tier0())


def test_pii_blocks_shared_tier3():
    ctx = CacheContext(
        org_id="o",
        lane=CacheLane.USER_PRIVATE,
        sensitivity=Sensitivity.HIGH,
        corpus_version="1",
        user_id="u1",
    )
    t0 = _tier0(pii_detected=True, lane=CacheLane.USER_PRIVATE, blocked_shared_write=True)
    assert not allows_tier3_shared_write(ctx, t0)
    assert write_policy_denial_reason(ctx, t0, CacheTier.TIER3) == "pii_detected"


def test_tier2_only_org_static_low():
    ctx = CacheContext(
        org_id="o",
        lane=CacheLane.TEAM,
        sensitivity=Sensitivity.LOW,
        corpus_version="1",
        team_id="t1",
    )
    assert allows_tier3_shared_write(ctx, _tier0(lane=CacheLane.TEAM))
    assert not allows_tier2_shared_write(ctx, _tier0(lane=CacheLane.TEAM))
