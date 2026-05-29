#!/usr/bin/env python3
"""
Production-shaped FAQ service: Redis + config + LiteLLM (optional).

  REDIS_URL=redis://localhost:6379/0 python examples/production_app.py --dry-run
  python examples/production_app.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prism_cache.factory import create_pipeline  # noqa: E402
from prism_cache.litellm_client import LiteLLMClient, load_dotenv  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--config",
        default=str(ROOT / "config" / "prism.production.yaml"),
    )
    args = parser.parse_args()

    load_dotenv(str(ROOT / ".env"))
    pipeline = create_pipeline(
        config_path=args.config,
        use_litellm_embed=not args.dry_run,
    )

    if args.dry_run:
        generate = lambda q: f"[production dry-run] Answer for: {q}"
        print("Mode: in-memory embed, no LiteLLM chat\n")
    else:
        client = LiteLLMClient.from_env()
        if not client.health_check():
            print("LiteLLM not reachable; use --dry-run or start docker-compose.prod.yml", file=sys.stderr)
            return 1
        generate = client.make_generate_fn(system="You are internal IT support.", max_tokens=150)
        print(f"Mode: Redis + LiteLLM chat={client.chat_model} embed={client.embed_model}\n")

    for user, question in [
        ("u1", "how do I reset my password?"),
        ("u2", "how do I reset my login password?"),
    ]:
        result = pipeline.faq_answer(
            question,
            "internal-faq-bot",
            generate,
            user_id=user,
        )
        tier = result.cache_tier.value if result.cache_tier else "miss"
        print(f"user={user} tier={tier} from_cache={result.from_cache}")

    print("\nMetrics:", pipeline.metrics_snapshot())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
