from prism_cache.models import CacheLane
from prism_cache.routes import RouteRegistry, default_routes


def test_coding_route_is_user_private_no_tier1():
    rule = default_routes().resolve("coding-assistant")
    assert rule.lane == CacheLane.USER_PRIVATE
    assert rule.route_hint == "coding"
    assert rule.tier1_enabled is False


def test_faq_route_org_static_tier1():
    rule = default_routes().resolve("internal-faq-bot")
    assert rule.lane == CacheLane.ORG_STATIC
    assert rule.tier1_enabled is True
    assert rule.tier2_enabled is True


def test_from_mapping():
    reg = RouteRegistry.from_mapping(
        {"my-bot": {"lane": "team", "sensitivity": "medium", "tier1_enabled": False}}
    )
    rule = reg.resolve("my-bot")
    assert rule.lane.value == "team"
    assert rule.tier1_enabled is False
