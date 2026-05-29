from prism_cache.models import CacheLane, CacheTier
from prism_cache.proxy_enforcement import (
    PRISM_ROUTE_HEADER,
    PRISM_USER_HEADER,
    PrismAuditEvent,
    classify_query_lane,
    inject_litellm_metadata,
    resolve_from_headers,
    resolve_route_context,
)


def test_coding_route_is_user_private():
    ctx = resolve_route_context("coding-assistant")
    assert ctx.lane == CacheLane.USER_PRIVATE
    assert ctx.tier1_enabled is False


def test_faq_route_enables_tier2():
    ctx = resolve_route_context("internal-faq-bot")
    assert ctx.lane == CacheLane.ORG_STATIC
    assert ctx.tier2_enabled is True


def test_headers_resolve_route():
    ctx = resolve_from_headers(
        {PRISM_ROUTE_HEADER: "program-rag", PRISM_USER_HEADER: "u1"}
    )
    assert ctx.route_name == "program-rag"
    assert ctx.lane == CacheLane.TEAM
    assert ctx.user_id == "u1"


def test_pii_downgrades_lane():
    ctx = resolve_route_context("program-rag")
    lane = classify_query_lane("email me at secret@acme.com about travel", ctx)
    assert lane == CacheLane.USER_PRIVATE


def test_inject_litellm_metadata():
    ctx = resolve_route_context("internal-faq-bot", user_id="bob")
    body = inject_litellm_metadata({"model": "m", "messages": []}, ctx)
    assert body["metadata"]["prism_lane"] == "org-static"
    assert body["metadata"]["prism_user_id"] == "bob"


def test_audit_event_json():
    ctx = resolve_route_context("program-rag")
    line = PrismAuditEvent.now(
        ctx=ctx, tier=CacheTier.TIER3, event="write_denied", denial_reason="pii_detected"
    ).to_json_line()
    assert "write_denied" in line
    assert "program-rag" in line
