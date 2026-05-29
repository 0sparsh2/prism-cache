from prism_cache.keys import build_cache_key, build_tier3_key_parts
from prism_cache.models import CacheContext, CacheLane, CacheTier, Sensitivity


def test_tier3_key_stable():
    ctx = CacheContext(
        org_id="acme",
        lane=CacheLane.ORG_STATIC,
        sensitivity=Sensitivity.LOW,
        corpus_version="42",
        clearance="internal",
    )
    parts = build_tier3_key_parts(
        query_hash="abc123",
        embed_model_id="embed-v1",
        top_k=5,
        filters={"program": "x"},
    )
    k1 = build_cache_key(ctx, CacheTier.TIER3, parts=parts)
    k2 = build_cache_key(ctx, CacheTier.TIER3, parts=parts)
    assert k1 == k2
    assert k1.startswith("prism:acme:org-static:tier3:")


def test_user_private_key_includes_user():
    ctx_shared = CacheContext(
        org_id="acme",
        lane=CacheLane.ORG_STATIC,
        sensitivity=Sensitivity.LOW,
        corpus_version="1",
        user_id="u1",
    )
    ctx_private = CacheContext(
        org_id="acme",
        lane=CacheLane.USER_PRIVATE,
        sensitivity=Sensitivity.HIGH,
        corpus_version="1",
        user_id="u1",
    )
    parts = build_tier3_key_parts(
        query_hash="same",
        embed_model_id="e",
        top_k=3,
        filters={},
    )
    k_shared = build_cache_key(ctx_shared, CacheTier.TIER3, parts=parts)
    k_private = build_cache_key(ctx_private, CacheTier.TIER3, parts=parts)
    assert k_shared != k_private


def test_corpus_version_changes_key():
    base = dict(
        org_id="acme",
        lane=CacheLane.ORG_STATIC,
        sensitivity=Sensitivity.LOW,
        clearance="default",
    )
    parts = build_tier3_key_parts(
        query_hash="q",
        embed_model_id="e",
        top_k=5,
        filters={},
    )
    k_v1 = build_cache_key(
        CacheContext(corpus_version="1", **base),
        CacheTier.TIER3,
        parts=parts,
    )
    k_v2 = build_cache_key(
        CacheContext(corpus_version="2", **base),
        CacheTier.TIER3,
        parts=parts,
    )
    assert k_v1 != k_v2
