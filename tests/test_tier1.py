from prism_cache.models import CacheContext, CacheLane, Sensitivity
from prism_cache.tier0 import process_tier0
from prism_cache.tier1 import InMemoryExactStore, Tier1ExactCache


def test_cross_user_exact_faq_hit():
    store = InMemoryExactStore()
    cache = Tier1ExactCache(store)
    ctx = CacheContext(
        org_id="acme",
        lane=CacheLane.ORG_STATIC,
        sensitivity=Sensitivity.LOW,
        corpus_version="1",
    )
    t0a = process_tier0("how do I reset my password?")
    t0b = process_tier0("How do I reset my password??")

    calls = {"n": 0}

    def gen(q: str) -> str:
        calls["n"] += 1
        return "Go to portal.example.com/reset"

    text1, l1 = cache.lookup_or_generate(ctx, t0a, gen, model_id="gpt-4o-mini")
    text2, l2 = cache.lookup_or_generate(ctx, t0b, gen, model_id="gpt-4o-mini")

    assert calls["n"] == 1
    assert l1.hit is False
    assert l2.hit is True
    assert text1 == text2


def test_pii_not_stored_org_static():
    store = InMemoryExactStore()
    cache = Tier1ExactCache(store)
    ctx = CacheContext(
        org_id="acme",
        lane=CacheLane.ORG_STATIC,
        sensitivity=Sensitivity.LOW,
        corpus_version="1",
    )
    t0 = process_tier0(
        "help for john.doe@acme.com",
        requested_lane=CacheLane.ORG_STATIC,
    )
    ok, reason = cache.store(ctx, t0, "answer", model_id="m")
    assert not ok
    assert reason == "pii_detected"
