from prism_cache.models import ChunkResult
from prism_cache.pipeline import PrismConfig, PrismPipeline


def test_rag_prepare_same_prefix_across_users():
    texts = {
        "expense-1": "Meals are reimbursed up to $75.",
        "expense-2": "Submit receipts within 30 days.",
    }
    index = {
        "expense": [
            ChunkResult("expense-2", 0.9),
            ChunkResult("expense-1", 0.85),
        ]
    }

    def retriever(query: str, *, top_k: int, filters):
        for key, chunks in index.items():
            if key in query:
                return chunks[:top_k]
        return []

    pipeline = PrismPipeline(PrismConfig(org_id="demo"))

    b1 = pipeline.rag_prepare(
        "what is the expense policy?",
        retriever,
        lambda cid: texts[cid],
        user_id="alice",
    )
    b2 = pipeline.rag_prepare(
        "What IS the expense POLICY?",
        retriever,
        lambda cid: texts[cid],
        user_id="bob",
    )

    assert b1.prompt.prefix_fingerprint == b2.prompt.prefix_fingerprint
    assert b1.audit.ok and b2.audit.ok
    assert b1.tier3_lookup.hit is False
    assert b2.tier3_lookup.hit is True
    assert b1.anthropic_body is not None
    cache_blocks = b1.anthropic_body["messages"][0]["content"]
    assert cache_blocks[0]["cache_control"] == {"type": "ephemeral"}


def test_pipeline_metrics_snapshot():
    pipeline = PrismPipeline(PrismConfig(org_id="acme"))

    def retriever(query: str, *, top_k: int, filters):
        return [ChunkResult("c1", 0.9)]

    pipeline.rag_retrieve("policy question", retriever)
    snap = pipeline.metrics_snapshot()
    assert "tiers" in snap
    assert "prefix_cache" in snap
    assert "tier3:org-static" in snap["tiers"]
