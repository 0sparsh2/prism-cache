import pytest

from prism_cache.models import CacheLane, Sensitivity
from prism_cache.tier0 import hash_query, normalize_query, process_tier0, scrub_pii


def test_normalize_collapses_whitespace_and_case():
    a = normalize_query("What is  Boeing's Q3 process?")
    b = normalize_query("what is boeing's q3 process")
    assert a == b


def test_same_hash_after_normalization():
    a = process_tier0("What is Boeing Q3?")
    b = process_tier0("  what is boeing q3?  ")
    assert a.query_hash == b.query_hash


def test_pii_downgrades_to_user_private():
    result = process_tier0(
        "Explain policy for john.doe@acme.com",
        requested_lane=CacheLane.ORG_STATIC,
    )
    assert result.pii_detected
    assert result.lane == CacheLane.USER_PRIVATE
    assert result.blocked_shared_write


def test_coding_route_hint_private():
    result = process_tier0(
        "fix my function",
        requested_lane=CacheLane.ORG_STATIC,
        route_hint="coding",
    )
    assert result.lane == CacheLane.USER_PRIVATE


def test_scrub_replaces_email():
    scrubbed, detected = scrub_pii("contact me at secret@corp.com please")
    assert detected
    assert "secret@corp.com" not in scrubbed
    assert "[EMAIL]" in scrubbed


def test_hash_stable():
    assert hash_query("hello") == hash_query("hello")
    assert hash_query("hello") != hash_query("world")
