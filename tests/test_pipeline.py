from prism_cache.models import ChunkResult
from prism_cache.pipeline import PrismConfig, PrismPipeline


def test_pipeline_corpus_bump_changes_miss():
    pipeline = PrismPipeline(PrismConfig(org_id="acme", corpus_id="handbook"))
    calls = {"n": 0}

    def retriever(query: str, *, top_k: int, filters):
        calls["n"] += 1
        return [ChunkResult(f"chunk-{calls['n']}", 0.9)]

    q = "how do I submit expenses?"
    pipeline.rag_retrieve(q, retriever, user_id="u1")
    pipeline.rag_retrieve(q, retriever, user_id="u2")
    assert calls["n"] == 1

    pipeline.invalidate_corpus()
    pipeline.rag_retrieve(q, retriever, user_id="u3")
    assert calls["n"] == 2


def test_pipeline_metrics_export():
    pipeline = PrismPipeline(PrismConfig(org_id="acme"))

    def retriever(query: str, *, top_k: int, filters):
        return [ChunkResult("c1", 0.9)]

    pipeline.rag_retrieve("policy question", retriever)
    snap = pipeline.metrics_snapshot()
    assert "tier3:org-static" in snap
