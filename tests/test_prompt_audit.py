from prism_cache.prompt_audit import audit_shared_prefix


def test_audit_passes_clean_prefix():
    result = audit_shared_prefix(
        system_prompt="You answer from documents only.",
        context_block="<document id=\"1\">Policy text</document>",
        user_query="what is the policy?",
    )
    assert result.ok


def test_audit_fails_query_in_system():
    result = audit_shared_prefix(
        system_prompt="Answer: what is the policy?",
        context_block="docs",
        user_query="what is the policy?",
    )
    assert not result.ok
    assert any(f.code == "query_in_system" for f in result.findings)


def test_audit_warns_timestamp():
    result = audit_shared_prefix(
        system_prompt="Today is 2026-05-29T12:00:00",
        context_block="docs",
        user_query="q",
    )
    assert any(f.code == "timestamp_iso" for f in result.findings)
