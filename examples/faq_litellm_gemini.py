#!/usr/bin/env python3
"""
FAQ path: PRISM Tier 1 + Tier 2 → LiteLLM proxy → Gemini (chat + embeddings).

Prerequisites:
  set -a && source .env && set +a
  docker compose up -d redis
  litellm --config gateway/litellm.multi.yaml --port 4000

  python examples/faq_litellm_gemini.py
  python examples/faq_litellm_gemini.py --dry-run   # hash_bag only, no proxy
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prism_cache.litellm_client import LiteLLMClient, load_dotenv  # noqa: E402
from prism_cache.models import CacheTier  # noqa: E402
from prism_cache.pipeline import PrismConfig, PrismPipeline  # noqa: E402
from prism_cache.tier2 import hash_bag_embed  # noqa: E402

FAQ_SYSTEM = (
    "You are an internal IT FAQ assistant. Answer in 2-3 short sentences. "
    "If unsure, say you do not know."
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use hash_bag_embed instead of Gemini embeddings (no proxy)",
    )
    args = parser.parse_args()

    load_dotenv(str(ROOT / ".env"))

    embed_fn = hash_bag_embed
    generate_fn = lambda q: f"[dry-run] Answer for: {q}"

    if not args.dry_run:
        try:
            client = LiteLLMClient.from_env()
        except KeyError as exc:
            print(f"Missing env var: {exc}", file=sys.stderr)
            return 1
        if not client.health_check():
            print(
                "LiteLLM proxy not reachable at "
                f"{client.base_url} — start gateway/litellm.multi.yaml or use --dry-run",
                file=sys.stderr,
            )
            return 1
        embed_fn = client.make_embed_fn()
        generate_fn = client.make_generate_fn(system=FAQ_SYSTEM, max_tokens=120)
        print(f"Proxy OK — chat={client.chat_model} embed={client.embed_model}\n")

    pipeline = PrismPipeline(
        PrismConfig(org_id="demo-corp", tier2_similarity_threshold=0.92),
        tier2_embed=embed_fn,
    )

    scenarios = [
        ("alice", "how do I reset my password?"),
        ("bob", "How do I reset my password??"),
        ("carol", "how do I reset my login password?"),
        ("dan", "what is the parental leave policy?"),
    ]

    for i, (user, question) in enumerate(scenarios):
        if i and not args.dry_run:
            time.sleep(1.5)
        try:
            result = pipeline.faq_answer(
                question,
                "internal-faq-bot",
                generate_fn,
                user_id=user,
                model_id="gemini-2.5-flash-lite",
            )
        except (TimeoutError, RuntimeError, urllib.error.URLError) as exc:
            print(f"[ERROR             ] user={user:5} q={question[:40]:40} → {exc}")
            continue
        if result.from_cache:
            tier = result.cache_tier.value if result.cache_tier else "?"
            extra = ""
            if result.cache_tier == CacheTier.TIER2 and result.tier2:
                extra = f" sim={result.tier2.similarity:.2f}"
            label = f"HIT/{tier}{extra}"
        else:
            label = "MISS"
        snippet = result.text.replace("\n", " ")[:70]
        print(f"[{label:20}] user={user:5} q={question[:40]:40} → {snippet}…")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
