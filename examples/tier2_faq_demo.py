#!/usr/bin/env python3
"""Tier 2 demo: semantic FAQ cache catches paraphrases Tier 1 misses."""

from prism_cache.models import CacheTier
from prism_cache.pipeline import PrismConfig, PrismPipeline


def fake_llm(query: str) -> str:
    return (
        "Reset your password at https://portal.example.com/reset. "
        "Use your corporate email and complete MFA."
    )


def main() -> None:
    pipeline = PrismPipeline(PrismConfig(org_id="demo-corp", tier2_similarity_threshold=0.85))
    llm_calls = 0

    def counting_llm(q: str) -> str:
        nonlocal llm_calls
        llm_calls += 1
        return fake_llm(q)

    scenarios = [
        ("internal-faq-bot", "alice", "how do I reset my password?"),
        ("internal-faq-bot", "bob", "How do I reset my password??"),  # Tier 1 exact
        ("internal-faq-bot", "carol", "how do I reset my login password?"),  # Tier 2 semantic
        ("internal-faq-bot", "dan", "what is the parental leave policy?"),  # miss → new LLM call
        ("coding-assistant", "eve", "fix null pointer in my handler"),
    ]

    for route, user, question in scenarios:
        result = pipeline.faq_answer(question, route, counting_llm, user_id=user)
        if result.from_cache:
            tier = result.cache_tier.value if result.cache_tier else "?"
            sim = f" sim={result.tier2.similarity:.2f}" if result.tier2 else ""
            cache = f"HIT/{tier}{sim}"
        else:
            cache = "MISS"
        print(
            f"[{cache:18}] route={route:20} user={user:5} "
            f"q={question[:42]}{'…' if len(question) > 42 else ''}"
        )

    print()
    print(f"LLM calls: {llm_calls} (exact + semantic reuse across users)")
    snap = pipeline.metrics_snapshot()["tiers"]
    print(f"Tier 1 lookups: {snap.get('tier1', {})}")
    print(f"Tier 2 lookups: {snap.get('tier2', {})}")


if __name__ == "__main__":
    main()
