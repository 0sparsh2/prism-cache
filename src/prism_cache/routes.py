from __future__ import annotations

from dataclasses import dataclass, field

from prism_cache.models import CacheLane, Sensitivity


@dataclass(frozen=True)
class RouteRule:
    name: str
    lane: CacheLane
    sensitivity: Sensitivity = Sensitivity.LOW
    route_hint: str | None = None
    tier1_enabled: bool = True


@dataclass
class RouteRegistry:
    """Maps application routes (chatbot, coding tool, etc.) to cache lanes."""

    routes: dict[str, RouteRule] = field(default_factory=dict)
    default: RouteRule | None = None

    def resolve(self, route_name: str | None) -> RouteRule:
        if route_name and route_name in self.routes:
            return self.routes[route_name]
        if self.default:
            return self.default
        return RouteRule(name="default", lane=CacheLane.ORG_STATIC)

    @classmethod
    def from_mapping(cls, routes: dict[str, dict[str, str | bool]]) -> RouteRegistry:
        parsed: dict[str, RouteRule] = {}
        for name, spec in routes.items():
            hint = spec.get("route_hint")
            parsed[name] = RouteRule(
                name=name,
                lane=CacheLane(spec.get("lane", "org-static")),
                sensitivity=Sensitivity(spec.get("sensitivity", "low")),
                route_hint=str(hint) if hint else None,
                tier1_enabled=bool(spec.get("tier1_enabled", True)),
            )
        default = parsed.pop("default", None)
        registry = cls(routes=parsed, default=default)
        return registry


def default_routes() -> RouteRegistry:
    return RouteRegistry.from_mapping(
        {
            "coding-assistant": {
                "lane": "user-private",
                "route_hint": "coding",
                "tier1_enabled": False,
            },
            "internal-faq-bot": {
                "lane": "org-static",
                "sensitivity": "low",
                "tier1_enabled": True,
            },
            "program-rag": {
                "lane": "team",
                "sensitivity": "medium",
                "tier1_enabled": False,
            },
        }
    )
