#!/usr/bin/env python3
"""Load route rules from config/prism.example.yaml and print resolved lanes."""

from pathlib import Path

from prism_cache.routes import default_routes
from prism_cache.settings import load_settings

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    settings = load_settings(ROOT / "config" / "prism.example.yaml")
    routes = settings.routes or default_routes()
    print(f"org_id={settings.org_id} corpus={settings.corpus_id}")
    print(f"redis={settings.redis.url}")
    print()
    for name in ("coding-assistant", "internal-faq-bot", "program-rag", "unknown-route"):
        rule = routes.resolve(name)
        print(
            f"  {name:22} lane={rule.lane.value:12} tier1={rule.tier1_enabled} "
            f"hint={rule.route_hint}"
        )


if __name__ == "__main__":
    main()
