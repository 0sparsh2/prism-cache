#!/usr/bin/env python3
"""Demonstrate route → lane resolution and audit events (no LiteLLM required)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prism_cache.models import CacheTier  # noqa: E402
from prism_cache.proxy_enforcement import (  # noqa: E402
    PRISM_ROUTE_HEADER,
    PrismAuditEvent,
    classify_query_lane,
    inject_litellm_metadata,
    resolve_from_headers,
    resolve_route_context,
)


def main() -> int:
    print("PRISM proxy enforcement prototype\n")

    for route in ("coding-assistant", "internal-faq-bot", "program-rag"):
        ctx = resolve_route_context(route, user_id="alice")
        print(f"route={route:20} lane={ctx.lane.value:12} tier2={ctx.tier2_enabled}")

    headers = {
        PRISM_ROUTE_HEADER: "program-rag",
        "x-prism-user-id": "employee-0042",
    }
    ctx = resolve_from_headers(headers)
    query = "Explain policy for john.doe@acme.com"
    effective_lane = classify_query_lane(query, ctx)
    print(f"\nPII downgrade: route=program-rag → effective_lane={effective_lane.value}")

    body = inject_litellm_metadata(
        {"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": query}]},
        ctx,
    )
    print(f"LiteLLM metadata: {body['metadata']}")

    audit = PrismAuditEvent.now(
        ctx=ctx,
        tier=CacheTier.TIER3,
        event="miss",
    )
    print(f"Audit JSONL: {audit.to_json_line()}")

    print("\nEnable callback: PYTHONPATH=src:gateway make gateway-prism")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
