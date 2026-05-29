"""Paraphrase cases that must not produce Tier 2 semantic hits at default threshold."""

import pytest

from prism_cache.models import CacheContext, CacheLane, Sensitivity
from prism_cache.tier0 import process_tier0
from prism_cache.tier2 import InMemorySemanticStore, Tier2SemanticCache, hash_bag_embed

PARAPHRASE_MISS_PAIRS = [
    ("how do I reset my password?", "what is the parental leave policy?"),
    ("how do I reset my password?", "book a conference room for tomorrow"),
    ("expense report deadline?", "how do I enroll in health insurance?"),
]


@pytest.mark.parametrize("seed,probe", PARAPHRASE_MISS_PAIRS)
def test_redteam_different_intent_no_semantic_hit(seed, probe):
    store = InMemorySemanticStore()
    cache = Tier2SemanticCache(store, hash_bag_embed, default_threshold=0.95)
    ctx = CacheContext(
        org_id="acme",
        lane=CacheLane.ORG_STATIC,
        sensitivity=Sensitivity.LOW,
        corpus_version="1",
    )
    t0_seed = process_tier0(seed)
    t0_probe = process_tier0(probe)
    cache.store(ctx, t0_seed, "seed answer", model_id="gpt-4o-mini")
    lookup = cache.lookup(ctx, t0_probe, model_id="gpt-4o-mini")
    assert lookup.hit is False, f"false positive: {seed!r} ~ {probe!r} sim={lookup.similarity:.3f}"
