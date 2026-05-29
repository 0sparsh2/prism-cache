#!/usr/bin/env python3
"""Run PRISM eval benchmarks and print a GitHub-friendly summary table."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from eval.benchmarks import run_all_benchmarks  # noqa: E402


def _markdown_table(report) -> str:
    lines = [
        "| Benchmark | Metric | Value | Target | Pass |",
        "|-----------|--------|-------|--------|------|",
    ]
    for row in report.rows:
        mark = "yes" if row.passed else "**no**"
        val = f"{row.value:.4f}" if isinstance(row.value, float) else str(row.value)
        lines.append(
            f"| {row.name} | {row.metric} | {val} | {row.target} | {mark} |"
        )
    return "\n".join(lines)


def _load_live_embed_fn():
    from prism_cache.litellm_client import LiteLLMClient, load_dotenv

    load_dotenv(str(ROOT / ".env"))
    client = LiteLLMClient.from_env()
    if not client.health_check():
        raise RuntimeError(
            "LiteLLM not reachable — start: make gateway (or skip --live)"
        )
    return client.make_embed_fn(), client.embed_model


def main() -> int:
    parser = argparse.ArgumentParser(description="PRISM governance + retrieval benchmarks")
    parser.add_argument(
        "--json-out",
        default=str(ROOT / "eval" / "results" / "latest.json"),
        help="Write machine-readable results",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Add live Tier 2 embedding rows via LiteLLM (requires gateway + keys)",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    live_embed = None
    embed_model = None
    if args.live:
        live_embed, embed_model = _load_live_embed_fn()

    report = run_all_benchmarks(include_live=args.live, live_embed_fn=live_embed)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "live": args.live,
        "embed_model": embed_model,
        **report.to_dict(),
    }

    out_path = Path(args.json_out)
    if args.live and out_path.name == "latest.json":
        out_path = out_path.parent / "latest_live.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n")

    if not args.quiet:
        title = "PRISM eval benchmarks" + (" (offline + live)" if args.live else "")
        print(title)
        print("=" * len(title))
        print(_markdown_table(report))
        print()
        for row in report.rows:
            if row.notes:
                print(f"  {row.name}: {row.notes}")
        print()
        print(f"Results: {out_path}")
        print(f"Overall: {'PASS' if report.all_passed() else 'FAIL'}")

    return 0 if report.all_passed() else 1


if __name__ == "__main__":
    raise SystemExit(main())
