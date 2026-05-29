from prism_cache.models import CacheTier
from prism_cache.pipeline import PrismConfig, PrismPipeline


def test_faq_semantic_paraphrase_cross_user():
    pipeline = PrismPipeline(PrismConfig(org_id="acme", tier2_similarity_threshold=0.85))
    calls = {"n": 0}

    def fake_llm(q: str) -> str:
        calls["n"] += 1
        return "Reset at portal.example.com/reset with MFA."

    r1 = pipeline.faq_answer(
        "how do I reset my password?",
        "internal-faq-bot",
        fake_llm,
        user_id="alice",
    )
    r2 = pipeline.faq_answer(
        "how do I reset my login password?",
        "internal-faq-bot",
        fake_llm,
        user_id="bob",
    )

    assert calls["n"] == 1
    assert r1.from_cache is False
    assert r2.from_cache is True
    assert r2.cache_tier == CacheTier.TIER2
    assert r2.tier2 is not None
    assert r2.tier2.similarity >= 0.85


def test_faq_cross_user_cache():
    pipeline = PrismPipeline(PrismConfig(org_id="acme"))
    calls = {"n": 0}

    def fake_llm(q: str) -> str:
        calls["n"] += 1
        return f"Answer for: {q}"

    r1 = pipeline.faq_answer(
        "how do I reset password?",
        "internal-faq-bot",
        fake_llm,
        user_id="alice",
    )
    r2 = pipeline.faq_answer(
        "How do I reset PASSWORD?",
        "internal-faq-bot",
        fake_llm,
        user_id="bob",
    )

    assert calls["n"] == 1
    assert r1.from_cache is False
    assert r2.from_cache is True
    assert r2.cache_tier == CacheTier.TIER1
    assert r1.text == r2.text
    assert r1.ctx.lane.value == "org-static"


def test_coding_route_no_tier1_sharing():
    pipeline = PrismPipeline(PrismConfig(org_id="acme"))
    calls = {"n": 0}

    def fake_llm(q: str) -> str:
        calls["n"] += 1
        return "code help"

    pipeline.faq_answer("fix my bug", "coding-assistant", fake_llm, user_id="alice")
    pipeline.faq_answer("fix my bug", "coding-assistant", fake_llm, user_id="bob")

    assert calls["n"] == 2
    rule = pipeline.routes.resolve("coding-assistant")
    assert rule.tier1_enabled is False
    assert rule.tier2_enabled is False
