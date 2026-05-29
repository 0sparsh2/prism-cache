from prism_cache.models import CacheContext, CacheLane, Sensitivity
from prism_cache.tier0 import process_tier0
from prism_cache.tier2 import (
    InMemorySemanticStore,
    Tier2SemanticCache,
    cosine_similarity,
    hash_bag_embed,
)
import pytest


def _ctx() -> CacheContext:
    return CacheContext(
        org_id="acme",
        lane=CacheLane.ORG_STATIC,
        sensitivity=Sensitivity.LOW,
        corpus_version="1",
    )


def test_semantic_paraphrase_hit():
    store = InMemorySemanticStore()
    cache = Tier2SemanticCache(store, hash_bag_embed, default_threshold=0.85)
    ctx = _ctx()
    t0a = process_tier0("how do I reset my password?")
    t0b = process_tier0("how do I reset my login password?")

    calls = {"n": 0}

    def gen(q: str) -> str:
        calls["n"] += 1
        return "Visit portal.example.com/reset and complete MFA."

    text1, l1 = cache.lookup_or_generate(ctx, t0a, gen, model_id="gpt-4o-mini")
    text2, l2 = cache.lookup_or_generate(ctx, t0b, gen, model_id="gpt-4o-mini")

    assert calls["n"] == 1
    assert l1.hit is False
    assert l2.hit is True
    assert l2.similarity >= 0.85
    assert text1 == text2


def test_semantic_different_intent_miss():
    store = InMemorySemanticStore()
    cache = Tier2SemanticCache(store, hash_bag_embed, default_threshold=0.95)
    ctx = _ctx()
    t0a = process_tier0("how do I reset my password?")
    t0b = process_tier0("what is the parental leave policy?")

    def gen(q: str) -> str:
        return f"answer:{q[:20]}"

    cache.lookup_or_generate(ctx, t0a, gen, model_id="m")
    lookup = cache.lookup(ctx, t0b, model_id="m")
    assert lookup.hit is False


def test_pii_blocks_tier2_store():
    store = InMemorySemanticStore()
    cache = Tier2SemanticCache(store, hash_bag_embed)
    ctx = CacheContext(
        org_id="acme",
        lane=CacheLane.USER_PRIVATE,
        sensitivity=Sensitivity.HIGH,
        corpus_version="1",
        user_id="u1",
    )
    t0 = process_tier0(
        "help for john.doe@acme.com",
        requested_lane=CacheLane.ORG_STATIC,
    )
    ok, reason = cache.store(ctx, t0, "answer", model_id="m")
    assert not ok
    assert reason == "pii_detected"


def test_cosine_identical_vectors():
    v = hash_bag_embed("reset password portal")
    assert cosine_similarity(v, v) == pytest.approx(1.0)
