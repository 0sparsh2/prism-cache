#!/usr/bin/env python3
"""Synthetic load test: duplicate queries across simulated users."""

from __future__ import annotations

import argparse
import time

from prism_cache.models import ChunkResult
from prism_cache.pipeline import PrismConfig, PrismPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="PRISM Tier 3 load smoke test")
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--queries", type=int, default=10)
    args = parser.parse_args()

    pipeline = PrismPipeline(PrismConfig(org_id="loadtest"))
    vector_calls = 0

    def retriever(query: str, *, top_k: int, filters):
        nonlocal vector_calls
        vector_calls += 1
        time.sleep(0.001)
        return [ChunkResult(f"{query[:8]}-1", 0.92)]

    queries = [f"what is policy section {i}?" for i in range(args.queries)]
    start = time.perf_counter()

    for user in range(args.users):
        for q in queries:
            pipeline.rag_retrieve(q, retriever, user_id=f"user-{user}")

    elapsed = time.perf_counter() - start
    snap = pipeline.metrics_snapshot()
    tier3 = snap.get("tier3:org-static", {})

    print(f"Users: {args.users}, unique queries: {args.queries}")
    print(f"Total RAG calls: {args.users * args.queries}")
    print(f"Vector DB calls (expected ~{args.queries}): {vector_calls}")
    print(f"Tier 3 hit rate: {tier3.get('hit_rate', 0):.2%}")
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Metrics: {snap}")


if __name__ == "__main__":
    main()
