from prism_cache.models import CacheContext, CacheLane, ChunkResult, Sensitivity
from prism_cache.tier0 import process_tier0
from prism_cache.tier3 import InMemoryRetrievalStore, Tier3RetrievalCache


def _fake_retriever(chunks: list[ChunkResult]):
    calls = {"n": 0}

    def retriever(query: str, *, top_k: int, filters):
        calls["n"] += 1
        return chunks[:top_k]

    retriever.calls = calls
    return retriever


def test_cross_user_tier3_hit_skips_retriever():
    store = InMemoryRetrievalStore()
    cache = Tier3RetrievalCache(store, embed_model_id="test-embed")
    chunks = [ChunkResult("c1", 0.95), ChunkResult("c2", 0.88)]

    ctx = CacheContext(
        org_id="acme",
        lane=CacheLane.ORG_STATIC,
        sensitivity=Sensitivity.LOW,
        corpus_version="v1",
    )
    tier0_alice = process_tier0("what is the expense policy?")
    tier0_bob = process_tier0("What IS the expense policy??")

    assert tier0_alice.query_hash == tier0_bob.query_hash

    retriever = _fake_retriever(chunks)
    out1, lookup1 = cache.retrieve_or_fetch(ctx, tier0_alice, retriever, top_k=2)
    assert lookup1.hit is False
    assert retriever.calls["n"] == 1
    assert len(out1) == 2

    out2, lookup2 = cache.retrieve_or_fetch(ctx, tier0_bob, retriever, top_k=2)
    assert lookup2.hit is True
    assert retriever.calls["n"] == 1
    assert [c.chunk_id for c in out2] == ["c1", "c2"]


def test_pii_query_not_written_to_org_cache():
    store = InMemoryRetrievalStore()
    cache = Tier3RetrievalCache(store)
    chunks = [ChunkResult("secret-chunk", 0.9)]

    ctx = CacheContext(
        org_id="acme",
        lane=CacheLane.USER_PRIVATE,
        sensitivity=Sensitivity.HIGH,
        corpus_version="1",
        user_id="alice",
    )
    tier0 = process_tier0(
        "my termination case emp #12345",
        requested_lane=CacheLane.ORG_STATIC,
    )
    retriever = _fake_retriever(chunks)
    cache.retrieve_or_fetch(ctx, tier0, retriever, top_k=1)

    tier0_bob = process_tier0("my termination case emp #99999")
    ctx_org = CacheContext(
        org_id="acme",
        lane=CacheLane.ORG_STATIC,
        sensitivity=Sensitivity.LOW,
        corpus_version="1",
    )
    _, lookup = cache.retrieve_or_fetch(ctx_org, tier0_bob, retriever, top_k=1)
    assert lookup.hit is False


def test_metrics_hit_rate():
    store = InMemoryRetrievalStore()
    cache = Tier3RetrievalCache(store)
    ctx = CacheContext(
        org_id="o",
        lane=CacheLane.ORG_STATIC,
        sensitivity=Sensitivity.LOW,
        corpus_version="1",
    )
    t0 = process_tier0("faq question")
    retriever = _fake_retriever([ChunkResult("c1", 1.0)])

    cache.retrieve_or_fetch(ctx, t0, retriever)
    cache.retrieve_or_fetch(ctx, t0, retriever)

    snap = cache.metrics.snapshot()
    key = "tier3:org-static"
    assert snap[key]["hits"] == 1
    assert snap[key]["misses"] == 1
    assert snap[key]["hit_rate"] == 0.5
