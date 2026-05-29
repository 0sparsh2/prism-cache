#!/usr/bin/env python3
"""
RAG + Tier 3 retrieval cache; optional LiteLLM chat for the final answer.

  python examples/rag_litellm_demo.py
  python examples/rag_litellm_demo.py --no-llm   # retrieval cache only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prism_cache.factory import create_pipeline  # noqa: E402
from prism_cache.litellm_client import LiteLLMClient  # noqa: E402
from prism_cache.models import ChunkResult  # noqa: E402

INDEX = {
    "expense": [ChunkResult("doc-expense-2", 0.96), ChunkResult("doc-expense-4", 0.91)],
    "travel": [ChunkResult("doc-travel-1", 0.94)],
}
CHUNK_TEXT = {
    "doc-expense-2": "Meals over $75 require itemized receipts.",
    "doc-expense-4": "Per diem follows GSA rates.",
    "doc-travel-1": "International travel requires VP approval in Workday.",
    "doc-general-0": "See the employee handbook.",
}


def retriever(query: str, *, top_k: int, filters) -> list[ChunkResult]:
    for key, chunks in INDEX.items():
        if key in query:
            return chunks[:top_k]
    return [ChunkResult("doc-general-0", 0.5)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true", help="Skip final chat completion")
    parser.add_argument("--config", default=str(ROOT / "config" / "prism.example.yaml"))
    args = parser.parse_args()

    pipeline = create_pipeline(config_path=args.config, env_path=ROOT / ".env")
    llm: LiteLLMClient | None = None
    if not args.no_llm:
        try:
            llm = LiteLLMClient.from_env()
            if not llm.health_check():
                llm = None
        except KeyError:
            llm = None

    questions = [
        ("alice", "what is the expense policy for meals?"),
        ("bob", "What is the EXPENSE policy for meals?"),
        ("carol", "what is the travel policy?"),
    ]

    for user_id, question in questions:
        bundle = pipeline.rag_prepare(
            question,
            retriever,
            lambda cid: CHUNK_TEXT.get(cid, ""),
            user_id=user_id,
            top_k=2,
            route_name="program-rag",
        )
        status = "HIT" if bundle.tier3_lookup.hit else "MISS"
        print(
            f"[T3 {status}] user={user_id} chunks={[c.chunk_id for c in bundle.chunks]} "
            f"prefix_fp={bundle.prompt.prefix_fingerprint[:12]}…"
        )
        if llm:
            answer = llm.chat(
                f"Context:\n{bundle.prompt.prefix_text}\n\nQuestion: {question}",
                max_tokens=120,
            )
            print(f"         answer: {answer[:100]}…")

    print("\nMetrics:", pipeline.metrics_snapshot())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
