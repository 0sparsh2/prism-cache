#!/usr/bin/env python3
"""
500-employee handbook RAG scenario — Tier 3 cross-user reuse at org scale.

Simulates 500 employees each asking the same 40 paraphrased policy questions.
PRISM caches retrieval (chunk IDs) under team lane + corpus_version — not answers.

  python examples/org_scenario_tier3.py
  python examples/org_scenario_tier3.py --users 500 --json-out eval/results/org_scenario.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prism_cache.factory import create_pipeline  # noqa: E402
from prism_cache.models import ChunkResult  # noqa: E402
from prism_cache.tier0 import hash_query, normalize_query, process_tier0  # noqa: E402

# 40 paraphrases across 4 published handbook topics (10 each).
PARAPHRASES: list[tuple[str, str]] = [
    # Travel (10)
    ("travel", "what is the international travel approval process?"),
    ("travel", "What is the INTERNATIONAL travel approval process?"),
    ("travel", "how do i get vp approval for international travel?"),
    ("travel", "international travel — who must approve in workday?"),
    ("travel", "policy for overseas business travel approval"),
    ("travel", "do i need vp sign off for international trips?"),
    ("travel", "workday steps for international travel requests"),
    ("travel", "travel outside the US approval requirements"),
    ("travel", "how does international travel approval work?"),
    ("travel", "what approvals are required for global travel?"),
    # Expense (10)
    ("expense", "what is the expense policy for meals over $75?"),
    ("expense", "What is the EXPENSE policy for meals over 75 dollars?"),
    ("expense", "meal receipt rules for expense reports"),
    ("expense", "when do i need itemized receipts for meals?"),
    ("expense", "per diem and meal expense limits"),
    ("expense", "gsa per diem for meal expenses"),
    ("expense", "expense report deadline for meals"),
    ("expense", "how to submit meal expenses over seventy five dollars"),
    ("expense", "itemized receipt requirement for large meal charges"),
    ("expense", "what meal expenses require manager approval?"),
    # Security (10)
    ("security", "what are the annual security training requirements?"),
    ("security", "What are the ANNUAL security training requirements?"),
    ("security", "when is security awareness training due?"),
    ("security", "how often must employees complete security training?"),
    ("security", "mandatory security training completion deadline"),
    ("security", "security training requirements for new hires"),
    ("security", "annual infosec training policy"),
    ("security", "do i need to finish security training every year?"),
    ("security", "workday security course completion rules"),
    ("security", "what happens if i miss security training?"),
    # Leave (10)
    ("leave", "what is the parental leave policy?"),
    ("leave", "What is the PARENTAL leave policy?"),
    ("leave", "how many weeks of paid parental leave?"),
    ("leave", "parental leave eligibility and duration"),
    ("leave", "paid leave for new parents policy"),
    ("leave", "maternity and paternity leave benefits"),
    ("leave", "how to request parental leave in workday"),
    ("leave", "parental leave paid weeks company policy"),
    ("leave", "leave policy for birth or adoption"),
    ("leave", "how long is paid parental leave?"),
]

HANDBOOK_CHUNKS: dict[str, list[ChunkResult]] = {
    "travel": [ChunkResult("hb-travel-intl-1", 0.96), ChunkResult("hb-travel-workday-2", 0.91)],
    "expense": [ChunkResult("hb-expense-meals-1", 0.95), ChunkResult("hb-expense-perdiem-2", 0.89)],
    "security": [ChunkResult("hb-security-annual-1", 0.94), ChunkResult("hb-security-deadline-2", 0.88)],
    "leave": [ChunkResult("hb-leave-parental-1", 0.93), ChunkResult("hb-leave-workday-2", 0.87)],
}


@dataclass
class ScenarioResult:
    org_id: str
    employees: int
    paraphrases: int
    unique_normalized_queries: int
    total_rag_requests: int
    vector_db_calls: int
    tier3_hits: int
    tier3_misses: int
    tier3_hit_rate: float
    vector_calls_avoided: int
    vector_reduction_pct: float
    simulated_vector_latency_ms: float
    elapsed_ms: float
    corpus_version: str
    lane: str

    def to_dict(self) -> dict:
        return asdict(self)


def _unique_normalized_count() -> int:
    return len({hash_query(normalize_query(q)) for _, q in PARAPHRASES})


def run_scenario(
    *,
    employees: int,
    vector_latency_ms: float,
    config_path: Path,
) -> tuple[ScenarioResult, object]:
    pipeline = create_pipeline(config_path=config_path, redis_url="")
    vector_calls = 0

    def retriever(query: str, *, top_k: int, filters):
        nonlocal vector_calls
        vector_calls += 1
        if vector_latency_ms > 0:
            time.sleep(vector_latency_ms / 1000.0)
        q = query.lower()
        for topic, chunks in HANDBOOK_CHUNKS.items():
            if topic in q:
                return chunks[:top_k]
        return [ChunkResult("hb-general-0", 0.5)][:top_k]

    start = time.perf_counter()
    for user_idx in range(employees):
        user_id = f"employee-{user_idx:04d}"
        for _topic, question in PARAPHRASES:
            pipeline.rag_retrieve(
                question,
                retriever,
                user_id=user_id,
                top_k=2,
                route_name="program-rag",
            )

    elapsed_ms = (time.perf_counter() - start) * 1000
    snap = pipeline.metrics_snapshot()
    tier3 = snap.get("tiers", {}).get("tier3:team", {})
    hits = int(tier3.get("hits", 0))
    misses = int(tier3.get("misses", 0))
    total = hits + misses
    hit_rate = hits / total if total else 0.0
    avoided = total - vector_calls if total else 0
    reduction = (avoided / total * 100) if total else 0.0

    result = ScenarioResult(
        org_id=pipeline.config.org_id,
        employees=employees,
        paraphrases=len(PARAPHRASES),
        unique_normalized_queries=_unique_normalized_count(),
        total_rag_requests=total,
        vector_db_calls=vector_calls,
        tier3_hits=hits,
        tier3_misses=misses,
        tier3_hit_rate=hit_rate,
        vector_calls_avoided=avoided,
        vector_reduction_pct=reduction,
        simulated_vector_latency_ms=vector_latency_ms,
        elapsed_ms=round(elapsed_ms, 2),
        corpus_version=pipeline.corpus_version(),
        lane="team",
    )
    return result, snap


def main() -> int:
    parser = argparse.ArgumentParser(description="500-employee Tier 3 org scenario")
    parser.add_argument("--users", type=int, default=500, help="Number of employees")
    parser.add_argument(
        "--vector-latency-ms",
        type=float,
        default=50.0,
        help="Simulated vector DB latency per miss (0 for CI speed)",
    )
    parser.add_argument(
        "--config",
        default=str(ROOT / "config" / "prism.example.yaml"),
    )
    parser.add_argument(
        "--json-out",
        default=str(ROOT / "eval" / "results" / "org_scenario.json"),
    )
    args = parser.parse_args()

    result, snap = run_scenario(
        employees=args.users,
        vector_latency_ms=args.vector_latency_ms,
        config_path=Path(args.config),
    )

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "scenario": result.to_dict(),
        "metrics": snap,
    }
    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")

    s = result
    print("PRISM org scenario — handbook RAG @ scale")
    print("==========================================")
    print(f"Employees:              {s.employees}")
    print(f"Paraphrases / employee: {s.paraphrases} (4 handbook topics)")
    print(f"Unique normalized Q:    {s.unique_normalized_queries} (Tier 0 hashes)")
    print(f"Total RAG requests:     {s.total_rag_requests:,}")
    print(f"Vector DB calls:        {s.vector_db_calls:,}  (expected ≈ {s.unique_normalized_queries})")
    print(f"Tier 3 hit rate:        {s.tier3_hit_rate:.2%}")
    print(f"Vector calls avoided:   {s.vector_calls_avoided:,}  ({s.vector_reduction_pct:.1f}% reduction)")
    if s.simulated_vector_latency_ms > 0:
        naive_ms = s.total_rag_requests * s.simulated_vector_latency_ms
        actual_ms = s.vector_db_calls * s.simulated_vector_latency_ms
        print(
            f"Simulated vector time:  {actual_ms/1000:.1f}s vs {naive_ms/1000:.1f}s naive "
            f"(saved ~{(naive_ms-actual_ms)/1000:.1f}s @ {s.simulated_vector_latency_ms}ms/call)"
        )
    print(f"Wall time (in-process): {s.elapsed_ms/1000:.2f}s")
    print(f"Lane / corpus:          {s.lane} / {s.corpus_version}")
    print(f"\nResults: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
