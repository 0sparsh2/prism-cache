"""
Reproducible PRISM eval workloads — governance + retrieval-first proof.

Run: python -m eval.run_benchmarks
CI:  pytest tests/test_benchmarks.py
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from prism_cache.models import CacheContext, CacheLane, CacheTier, ChunkResult, Sensitivity
from prism_cache.policy import write_policy_denial_reason
from prism_cache.tier0 import process_tier0
from prism_cache.tier2 import InMemorySemanticStore, Tier2SemanticCache, hash_bag_embed
from prism_cache.tier3 import InMemoryRetrievalStore, Tier3RetrievalCache

# --- Tier 2: near-intent pairs that must NOT semantic-hit at default threshold ---

NEAR_INTENT_TIER2_MUST_MISS = [
    ("how do I cancel my subscription?", "how do I pause my subscription?"),
    ("terminate an employee for cause", "suspend an employee pending review"),
    ("refund my last payment", "dispute a charge on my account"),
    ("delete my account permanently", "deactivate my account temporarily"),
]

# Orthogonal intents (different topics) — also must miss
ORTHOGONAL_TIER2_MUST_MISS = [
    ("how do I reset my password?", "what is the parental leave policy?"),
    ("expense report deadline?", "how do I enroll in health insurance?"),
]

# --- Tier 3: safe paraphrases — cached chunks must match fresh retrieval ---

TIER3_SAFE_PARAPHRASES = [
    ("what is the expense policy for meals?", "What is the EXPENSE policy for meals?"),
    ("how do I submit travel reimbursement?", "How do I submit TRAVEL reimbursement?"),
    ("security training requirements?", "What are the security training requirements?"),
]

# --- Tier 3: near-intent — report chunk overlap (informational risk signal) ---

NEAR_INTENT_TIER3_OVERLAP = [
    ("how do I cancel my subscription?", "how do I pause my subscription?"),
    ("terminate employee workflow", "suspend employee workflow"),
]

# --- Policy: contexts that must deny cross-user writes ---

POLICY_MUST_DENY = [
    (
        CacheContext(
            org_id="acme",
            lane=CacheLane.TEAM,
            sensitivity=Sensitivity.MEDIUM,
            corpus_version="v1",
        ),
        process_tier0("team roadmap question"),
        CacheTier.TIER2,
        "policy_denied",
    ),
    (
        CacheContext(
            org_id="acme",
            lane=CacheLane.USER_PRIVATE,
            sensitivity=Sensitivity.HIGH,
            corpus_version="v1",
            user_id="alice",
        ),
        process_tier0("my case emp #12345", requested_lane=CacheLane.ORG_STATIC),
        CacheTier.TIER2,
        "pii_detected",
    ),
]

ORG_CTX = CacheContext(
    org_id="acme",
    lane=CacheLane.ORG_STATIC,
    sensitivity=Sensitivity.LOW,
    corpus_version="v1",
)


@dataclass
class BenchmarkRow:
    name: str
    metric: str
    value: float
    target: str
    passed: bool
    notes: str = ""


@dataclass
class BenchmarkReport:
    rows: list[BenchmarkRow] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": [asdict(r) for r in self.rows],
            "passed": self.all_passed(),
        }

    def all_passed(self) -> bool:
        return all(r.passed for r in self.rows)


def _topic_retriever(corpus: dict[str, list[ChunkResult]]) -> Callable[..., list[ChunkResult]]:
    def retriever(query: str, *, top_k: int, filters) -> list[ChunkResult]:
        q = query.lower()
        for topic, chunks in corpus.items():
            if topic in q:
                return chunks[:top_k]
        return [ChunkResult("doc-general", 0.5)][:top_k]

    return retriever


def run_tier2_near_intent_fpr(
    *,
    threshold: float = 0.95,
    embed_fn=hash_bag_embed,
) -> BenchmarkRow:
    store = InMemorySemanticStore()
    cache = Tier2SemanticCache(store, embed_fn, default_threshold=threshold)
    pairs = NEAR_INTENT_TIER2_MUST_MISS + ORTHOGONAL_TIER2_MUST_MISS
    false_positives = 0
    for seed, probe in pairs:
        t0_seed = process_tier0(seed)
        t0_probe = process_tier0(probe)
        cache.store(ORG_CTX, t0_seed, "cached answer", model_id="eval")
        lookup = cache.lookup(ORG_CTX, t0_probe, model_id="eval")
        if lookup.hit:
            false_positives += 1
    rate = false_positives / len(pairs) if pairs else 0.0
    return BenchmarkRow(
        name="tier2_near_intent",
        metric="false_positive_rate",
        value=rate,
        target="= 0.0",
        passed=rate == 0.0,
        notes=f"{false_positives}/{len(pairs)} adversarial pairs hit at threshold={threshold}",
    )


def run_tier3_retrieval_equivalence(*, embed_model_id: str = "eval-embed") -> BenchmarkRow:
    store = InMemoryRetrievalStore()
    cache = Tier3RetrievalCache(store, embed_model_id=embed_model_id)
    corpus = {
        "expense": [ChunkResult("doc-expense-2", 0.96), ChunkResult("doc-expense-4", 0.91)],
        "travel": [ChunkResult("doc-travel-1", 0.94)],
        "security": [ChunkResult("doc-security-1", 0.93)],
    }
    retriever = _topic_retriever(corpus)
    mismatches = 0
    for seed, paraphrase in TIER3_SAFE_PARAPHRASES:
        t0_a = process_tier0(seed)
        t0_b = process_tier0(paraphrase)
        fresh_a, _ = cache.retrieve_or_fetch(ORG_CTX, t0_a, retriever, top_k=2)
        fresh_b_direct, _ = cache.retrieve_or_fetch(ORG_CTX, t0_b, retriever, top_k=2)
        ids_a = [c.chunk_id for c in fresh_a]
        ids_b = [c.chunk_id for c in fresh_b_direct]
        if ids_a != ids_b:
            mismatches += 1
    precision = 1.0 - (mismatches / len(TIER3_SAFE_PARAPHRASES))
    return BenchmarkRow(
        name="tier3_retrieval_equivalence",
        metric="precision",
        value=precision,
        target="= 1.0",
        passed=precision == 1.0,
        notes=f"{len(TIER3_SAFE_PARAPHRASES) - mismatches}/{len(TIER3_SAFE_PARAPHRASES)} paraphrase pairs matched chunk sets",
    )


def run_tier3_near_intent_overlap(*, embed_model_id: str = "eval-embed") -> BenchmarkRow:
    """Informational: overlapping chunks on adjacent intents (governance risk signal)."""
    store = InMemoryRetrievalStore()
    cache = Tier3RetrievalCache(store, embed_model_id=embed_model_id)
    corpus = {
        "cancel": [ChunkResult("doc-billing-cancel", 0.95)],
        "pause": [ChunkResult("doc-billing-cancel", 0.94), ChunkResult("doc-billing-pause", 0.92)],
        "terminate": [ChunkResult("doc-hr-terminate", 0.95)],
        "suspend": [ChunkResult("doc-hr-terminate", 0.93), ChunkResult("doc-hr-suspend", 0.91)],
    }
    retriever = _topic_retriever(corpus)
    overlaps = 0
    for a, b in NEAR_INTENT_TIER3_OVERLAP:
        t0_a = process_tier0(a)
        t0_b = process_tier0(b)
        chunks_a, _ = cache.retrieve_or_fetch(ORG_CTX, t0_a, retriever, top_k=2)
        chunks_b, _ = cache.retrieve_or_fetch(ORG_CTX, t0_b, retriever, top_k=2)
        set_a = {c.chunk_id for c in chunks_a}
        set_b = {c.chunk_id for c in chunks_b}
        if set_a & set_b:
            overlaps += 1
    rate = overlaps / len(NEAR_INTENT_TIER3_OVERLAP)
    return BenchmarkRow(
        name="tier3_near_intent_overlap",
        metric="chunk_overlap_rate",
        value=rate,
        target="report only",
        passed=True,
        notes="Informational — documents synthesis risk when intents differ but chunks overlap",
    )


def run_policy_denial_rate() -> BenchmarkRow:
    denied = 0
    for ctx, t0, tier, expected in POLICY_MUST_DENY:
        reason = write_policy_denial_reason(ctx, t0, tier)
        if reason == expected:
            denied += 1
    rate = denied / len(POLICY_MUST_DENY)
    return BenchmarkRow(
        name="policy_governance",
        metric="denial_accuracy",
        value=rate,
        target="= 1.0",
        passed=rate == 1.0,
        notes=f"{int(rate * len(POLICY_MUST_DENY))}/{len(POLICY_MUST_DENY)} expected denials",
    )


def run_lane_isolation() -> BenchmarkRow:
    store = InMemoryRetrievalStore()
    cache = Tier3RetrievalCache(store)
    private_ctx = CacheContext(
        org_id="acme",
        lane=CacheLane.USER_PRIVATE,
        sensitivity=Sensitivity.HIGH,
        corpus_version="v1",
        user_id="alice",
    )
    org_ctx = CacheContext(
        org_id="acme",
        lane=CacheLane.ORG_STATIC,
        sensitivity=Sensitivity.LOW,
        corpus_version="v1",
    )
    secret = [ChunkResult("secret-chunk", 0.99)]

    def retriever(query: str, *, top_k: int, filters):
        return secret[:top_k]

    t0_alice = process_tier0("my termination case emp #12345", requested_lane=CacheLane.ORG_STATIC)
    cache.retrieve_or_fetch(private_ctx, t0_alice, retriever, top_k=1)
    t0_bob = process_tier0("my termination case emp #99999")
    _, lookup = cache.retrieve_or_fetch(org_ctx, t0_bob, retriever, top_k=1)
    return BenchmarkRow(
        name="lane_isolation",
        metric="cross_lane_leak_rate",
        value=0.0 if not lookup.hit else 1.0,
        target="= 0.0",
        passed=not lookup.hit,
        notes="user-private retrieval must not appear in org-static lookup",
    )


def run_cross_user_hit_rate(*, users: int = 50, queries: int = 10) -> BenchmarkRow:
    store = InMemoryRetrievalStore()
    cache = Tier3RetrievalCache(store)
    vector_calls = {"n": 0}

    def retriever(query: str, *, top_k: int, filters):
        vector_calls["n"] += 1
        return [ChunkResult(f"chunk-{query[:12]}", 0.9)]

    query_list = [f"what is policy section {i}?" for i in range(queries)]
    hits = 0
    total = users * len(query_list)
    for u in range(users):
        for q in query_list:
            t0 = process_tier0(q)
            _, lookup = cache.retrieve_or_fetch(ORG_CTX, t0, retriever, top_k=1)
            if lookup.hit:
                hits += 1
    hit_rate = hits / total if total else 0.0
    expected_vector = queries
    passed = vector_calls["n"] == expected_vector and hit_rate > 0.9
    return BenchmarkRow(
        name="cross_user_tier3",
        metric="hit_rate",
        value=hit_rate,
        target="> 0.9",
        passed=passed,
        notes=f"vector_calls={vector_calls['n']} (expect {expected_vector}) over {users} users × {queries} queries",
    )


def run_all_benchmarks() -> BenchmarkReport:
    report = BenchmarkReport()
    report.rows.extend(
        [
            run_tier3_retrieval_equivalence(),
            run_cross_user_hit_rate(),
            run_lane_isolation(),
            run_policy_denial_rate(),
            run_tier2_near_intent_fpr(),
            run_tier3_near_intent_overlap(),
        ]
    )
    return report
