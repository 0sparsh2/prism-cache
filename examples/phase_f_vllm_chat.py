#!/usr/bin/env python3
"""
Phase F live probe: PRISM rag_prepare → vLLM OpenAI server (:8000).

  python examples/phase_f_vllm_chat.py              # health check only
  python examples/phase_f_vllm_chat.py --chat       # POST chat/completions if vLLM up
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prism_cache.factory import create_pipeline  # noqa: E402
from prism_cache.litellm_client import load_dotenv  # noqa: E402
from prism_cache.lmcache_integration import openai_messages_for_vllm  # noqa: E402
from prism_cache.models import ChunkResult  # noqa: E402

CHUNKS = [ChunkResult("policy-1", 0.95)]
TEXT = {"policy-1": "All employees must complete security training annually."}


def vllm_base_url() -> str:
    return os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1").rstrip("/")


def vllm_health() -> bool:
    try:
        req = urllib.request.Request(f"{vllm_base_url()}/models", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return False


def vllm_chat(messages: list[dict[str, str]], *, model: str, max_tokens: int = 120) -> str:
    body = json.dumps(
        {"model": model, "messages": messages, "max_tokens": max_tokens}
    ).encode()
    req = urllib.request.Request(
        f"{vllm_base_url()}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.load(resp)
    return str(data["choices"][0]["message"]["content"]).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat", action="store_true", help="Send chat request when vLLM is up")
    parser.add_argument("--model", default=os.environ.get("VLLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct"))
    args = parser.parse_args()

    load_dotenv(str(ROOT / ".env"))
    pipeline = create_pipeline(
        config_path=ROOT / "config" / "prism.example.yaml",
        redis_url="",
    )
    bundle = pipeline.rag_prepare(
        "what is the security training requirement?",
        lambda q, *, top_k, filters: CHUNKS,
        lambda cid: TEXT[cid],
        user_id="phase-f-probe",
        route_name="program-rag",
        top_k=1,
    )
    messages = openai_messages_for_vllm(bundle.prompt)

    print(f"vLLM base: {vllm_base_url()}")
    print(f"Prefix fingerprint: {bundle.prompt.prefix_fingerprint[:16]}…")
    print(f"Tier 4 audit ok: {bundle.audit.ok}")

    if not vllm_health():
        print("\nvLLM not reachable — start GPU stack:")
        print("  export HF_TOKEN=...")
        print("  docker compose -f docker-compose.vllm-lmcache.yml up")
        return 0 if not args.chat else 1

    print("vLLM: OK")
    if not args.chat:
        print("Run with --chat to POST /v1/chat/completions")
        return 0

    answer = vllm_chat(messages, model=args.model)
    print(f"\nAnswer: {answer[:400]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
