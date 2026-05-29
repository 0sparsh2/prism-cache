#!/usr/bin/env python3
"""
Phase F demo: PRISM rag_prepare → vLLM+LMCache launch spec (no GPU required to print).

  python examples/phase_f_rag_vllm.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prism_cache.factory import create_pipeline  # noqa: E402
from prism_cache.lmcache_integration import (  # noqa: E402
    build_vllm_spec,
    docker_run_example,
    openai_messages_for_vllm,
)
from prism_cache.models import ChunkResult  # noqa: E402

CHUNKS = [ChunkResult("policy-1", 0.95)]
TEXT = {"policy-1": "All employees must complete security training annually."}


def main() -> None:
    pipeline = create_pipeline(config_path=ROOT / "config" / "prism.example.yaml")
    bundle = pipeline.rag_prepare(
        "what is the security training requirement?",
        lambda q, *, top_k, filters: CHUNKS,
        lambda cid: TEXT[cid],
        user_id="demo",
        route_name="program-rag",
        top_k=1,
    )

    model = os.environ.get("VLLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    spec = build_vllm_spec(
        bundle.prompt,
        model=model,
        config_file="/app/lmcache-config.yaml",
    )

    print("PRISM Tier 4 prefix fingerprint:", bundle.prompt.prefix_fingerprint)
    print("Tier 4 audit ok:", bundle.audit.ok)
    print()
    print("OpenAI messages for vLLM:")
    for m in openai_messages_for_vllm(bundle.prompt):
        print(f"  [{m['role']}] {m['content'][:80]}…")
    print()
    print("LMCache env:", spec.lmcache_env)
    print("vLLM tail:", spec.vllm_command_tail())
    print()
    print("Docker example:")
    print(docker_run_example(spec))
    print()
    print("Start GPU stack: docker compose -f docker-compose.vllm-lmcache.yml up")
    print("Docs: docs/LMCACHE.md")


if __name__ == "__main__":
    main()
