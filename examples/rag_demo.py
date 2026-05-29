#!/usr/bin/env python3
"""Minimal RAG integration with PRISM Tier 3 retrieval cache."""

from prism_cache.models import ChunkResult
from prism_cache.pipeline import PrismConfig, PrismPipeline

# Simulated vector DB
FAKE_INDEX = {
    "expense policy": [ChunkResult("doc-expense-§2", 0.96), ChunkResult("doc-expense-§4", 0.91)],
    "travel policy": [ChunkResult("doc-travel-§1", 0.94)],
}


def fake_vector_search(query: str, *, top_k: int, filters) -> list[ChunkResult]:
    for key, chunks in FAKE_INDEX.items():
        if key in query:
            return chunks[:top_k]
    return [ChunkResult("doc-general-§0", 0.5)]


def main() -> None:
    pipeline = PrismPipeline(
        PrismConfig(org_id="demo-corp", corpus_id="employee-handbook"),
    )

    questions = [
        ("alice", "what is the expense policy for meals?"),
        ("bob", "What is the EXPENSE policy for meals?"),
        ("carol", "explain travel policy"),
    ]

    for user_id, question in questions:
        chunks, tier0, ctx, lookup = pipeline.rag_retrieve(
            question,
            fake_vector_search,
            user_id=user_id,
            top_k=2,
        )
        status = "HIT" if lookup.hit else "MISS"
        print(f"[{status}] user={user_id} lane={ctx.lane.value} chunks={[c.chunk_id for c in chunks]}")

    print("\nMetrics:", pipeline.metrics_snapshot())


if __name__ == "__main__":
    main()
