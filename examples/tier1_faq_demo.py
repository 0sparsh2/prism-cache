#!/usr/bin/env python3
"""Tier 1 FAQ demo: exact cache on org-static route, no cross-user cache for coding."""

from prism_cache.pipeline import PrismConfig, PrismPipeline


def fake_llm(query: str) -> str:
    return (
        "Reset your password at https://portal.example.com/reset. "
        "Use your corporate email and complete MFA."
    )


def main() -> None:
    pipeline = PrismPipeline(PrismConfig(org_id="demo-corp"))
    llm_calls = 0

    def counting_llm(q: str) -> str:
        nonlocal llm_calls
        llm_calls += 1
        return fake_llm(q)

    scenarios = [
        ("internal-faq-bot", "alice", "how do I reset my password?"),
        ("internal-faq-bot", "bob", "How do I reset my password??"),
        ("coding-assistant", "alice", "fix null pointer in my handler"),
        ("coding-assistant", "bob", "fix null pointer in my handler"),
    ]

    for route, user, question in scenarios:
        result = pipeline.faq_answer(question, route, counting_llm, user_id=user)
        cache = "HIT" if result.from_cache else "MISS"
        print(
            f"[T1 {cache}] route={route:20} user={user:5} lane={result.ctx.lane.value:12} "
            f"tier1={'on' if result.tier1 else 'off'}"
        )

    print()
    print(f"LLM calls: {llm_calls} (FAQ shared once; coding never cached org-wide)")
    print("Tier metrics:", pipeline.metrics_snapshot()["tiers"])


if __name__ == "__main__":
    main()
