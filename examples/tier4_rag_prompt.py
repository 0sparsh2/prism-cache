#!/usr/bin/env python3
"""Tier 4 demo: Tier 3 retrieval + cache-friendly Anthropic prompt + metrics dashboard."""

from prism_cache.models import ChunkResult
from prism_cache.pipeline import PrismConfig, PrismPipeline
from prism_cache.prefix_metrics import PrefixCacheUsage

CORPUS = {
    "travel-1": "International travel requires VP approval.",
    "travel-2": "Economy class is standard for flights under 6 hours.",
}

INDEX = {
    "travel": [ChunkResult("travel-2", 0.92), ChunkResult("travel-1", 0.88)],
}


def retriever(query: str, *, top_k: int, filters) -> list[ChunkResult]:
    for key, chunks in INDEX.items():
        if key in query:
            return chunks[:top_k]
    return []


def main() -> None:
    pipeline = PrismPipeline(
        PrismConfig(
            org_id="demo-corp",
            default_system_prompt="Answer only from the documents below.",
        )
    )

    users = [
        ("alice", "what is the travel policy?"),
        ("bob", "What is the TRAVEL policy?"),
        ("carol", "explain travel policy for flights"),
    ]

    for user_id, question in users:
        bundle = pipeline.rag_prepare(
            question,
            retriever,
            lambda cid: CORPUS[cid],
            user_id=user_id,
        )
        t3 = "HIT" if bundle.tier3_lookup.hit else "MISS"
        print(
            f"[T3 {t3}] user={user_id} prefix={bundle.prompt.prefix_fingerprint[:12]}… "
            f"audit_ok={bundle.audit.ok}"
        )

    # Simulate Anthropic usage after LLM calls (first write, then reads)
    fp = pipeline.rag_prepare(
        "what is the travel policy?",
        retriever,
        lambda cid: CORPUS[cid],
    ).prompt.prefix_fingerprint

    pipeline.record_prefix_cache_usage(
        {
            "input_tokens": 8000,
            "output_tokens": 150,
            "cache_creation_input_tokens": 7500,
            "cache_read_input_tokens": 0,
        },
        model_id="claude-sonnet-4-20250514",
        prefix_fingerprint=fp,
    )
    for _ in range(4):
        pipeline.record_prefix_cache_usage(
            {
                "input_tokens": 8100,
                "output_tokens": 140,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 7500,
            },
            model_id="claude-sonnet-4-20250514",
            prefix_fingerprint=fp,
        )

    print()
    print(pipeline.prefix_cache_dashboard())


if __name__ == "__main__":
    main()
