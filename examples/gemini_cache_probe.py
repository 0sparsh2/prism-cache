#!/usr/bin/env python3
"""
Probe Gemini context caching the right way:

1. Explicit cache — create CachedContent (needs paid tier + ≥2048 tokens on flash-lite),
   then generate and read usageMetadata.cachedContentTokenCount
2. Implicit cache — ≥2048-token shared prefix, identical requests with backoff
3. LiteLLM proxy — shows normalized usage (no cachedContentTokenCount)
4. PRISM Tier 4 — record raw usageMetadata with provider="gemini"

Requires GEMINI_API_KEY and GEMINI_MODEL in .env.

  python examples/gemini_cache_probe.py
  python examples/gemini_cache_probe.py --skip-implicit   # faster, explicit + sim only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prism_cache.pipeline import PrismConfig, PrismPipeline  # noqa: E402
from prism_cache.prefix_metrics import PrefixCacheUsage  # noqa: E402

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
HANDBOOK_SENTENCE = (
    "Section 4.2 Travel and expenses: International travel requires VP approval "
    "documented in Workday at least ten business days before departure. Economy class "
    "is standard for flights under six hours; business class requires CFO approval. "
    "Per diem follows GSA rates; receipts over seventy-five dollars must be itemized. "
)


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _model_resource(model: str) -> str:
    return model if model.startswith("models/") else f"models/{model}"


def _short_model(model: str) -> str:
    return model.removeprefix("models/")


def _post_json(url: str, body: dict[str, Any], *, timeout: int = 120) -> dict[str, Any]:
    payload = json.dumps(body).encode()
    last_error: urllib.error.HTTPError | None = None
    for attempt in range(5):
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429 and attempt < 4:
                wait = 2 ** attempt + 1
                print(f"  rate limited — retry in {wait}s…")
                time.sleep(wait)
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("unreachable")


def _delete(url: str) -> None:
    req = urllib.request.Request(url, method="DELETE")
    try:
        urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError:
        pass


def _usage_line(label: str, usage: dict[str, Any] | None) -> str:
    if not usage:
        return f"{label}: (no usage)"
    cached = usage.get("cachedContentTokenCount") or 0
    prompt = usage.get("promptTokenCount") or 0
    out = usage.get("candidatesTokenCount") or 0
    hit = "HIT" if cached else "miss"
    return (
        f"{label}: prompt={prompt} output={out} "
        f"cachedContentTokenCount={cached} ({hit})"
    )


def _handbook(repeats: int) -> str:
    return HANDBOOK_SENTENCE * repeats


def _measure_prompt_tokens(api_key: str, model: str, text: str) -> int:
    resp = generate_direct(api_key, model, user_text=text)
    um = resp.get("usageMetadata") or {}
    return int(um.get("promptTokenCount") or 0)


def _corpus_for_min_tokens(
    api_key: str,
    model: str,
    *,
    min_tokens: int = 2048,
    start_repeats: int = 40,
) -> tuple[str, int]:
    """Grow handbook until a probe request reports >= min_tokens."""
    repeats = start_repeats
    while repeats <= 200:
        corpus = _handbook(repeats)
        probe = f"{corpus}\n\nProbe: reply with the word OK."
        tokens = _measure_prompt_tokens(api_key, model, probe)
        print(f"  corpus repeats={repeats} → promptTokenCount={tokens}")
        if tokens >= min_tokens:
            return corpus, tokens
        repeats += 20
        time.sleep(1.5)
    raise RuntimeError(f"Could not reach {min_tokens} prompt tokens (last={tokens})")


def generate_direct(
    api_key: str,
    model: str,
    *,
    user_text: str,
    cached_content: str | None = None,
) -> dict[str, Any]:
    url = f"{GEMINI_BASE}/{_model_resource(model)}:generateContent?key={api_key}"
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
    }
    if cached_content:
        body["cachedContent"] = cached_content
    return _post_json(url, body)


def create_explicit_cache(
    api_key: str,
    model: str,
    *,
    system_instruction: str,
    corpus: str,
    ttl: str = "600s",
) -> dict[str, Any]:
    url = f"{GEMINI_BASE}/cachedContents?key={api_key}"
    body = {
        "model": _model_resource(model),
        "displayName": "prism-cache-probe",
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": corpus}]}],
        "ttl": ttl,
    }
    return _post_json(url, body)


def generate_litellm(
    *,
    model: str,
    user_text: str,
    master_key: str,
    base_url: str = "http://localhost:4000",
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    body = {
        "model": _short_model(model),
        "messages": [{"role": "user", "content": user_text}],
        "max_tokens": 64,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {master_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def test_simulated_prism(pipeline: PrismPipeline, model: str, corpus_tokens: int) -> bool:
    """Prove PRISM Tier 4 path when Google returns cachedContentTokenCount (documented shape)."""
    print("\n=== 1b) PRISM Tier 4 with documented usageMetadata shape (simulated) ===")
    fp = hashlib.sha256(b"explicit-cache-fingerprint").hexdigest()[:16]
    samples = [
        {
            "promptTokenCount": corpus_tokens + 12,
            "candidatesTokenCount": 24,
            "cachedContentTokenCount": 0,
        },
        {
            "promptTokenCount": corpus_tokens + 12,
            "candidatesTokenCount": 18,
            "cachedContentTokenCount": corpus_tokens,
        },
    ]
    for i, um in enumerate(samples, 1):
        print(_usage_line(f"  simulated generate #{i}", um))
        pipeline.record_prefix_cache_usage(
            um,
            model_id=_short_model(model),
            prefix_fingerprint=fp,
            provider="gemini",
        )
    snap = pipeline.prefix_metrics.snapshot()["totals"]
    ok = snap["cache_read_hits"] >= 1 and snap["cache_read_input_tokens"] >= corpus_tokens
    print(
        f"PASS — PRISM parsed cachedContentTokenCount "
        f"(read_hits={snap['cache_read_hits']}, read_tokens={snap['cache_read_input_tokens']})"
        if ok
        else "FAIL — PRISM did not record simulated cache read"
    )
    return ok


def test_explicit_cache(
    api_key: str,
    model: str,
    pipeline: PrismPipeline,
    corpus: str,
    corpus_tokens: int,
) -> bool:
    print("\n=== 1) Explicit context cache (Google CachedContent API) ===")
    system = (
        "You are an internal HR assistant. Answer only from the handbook corpus "
        "provided in the cache. Be concise."
    )
    fp = hashlib.sha256((system + corpus).encode()).hexdigest()[:16]

    try:
        cache = create_explicit_cache(
            api_key,
            model,
            system_instruction=system,
            corpus=corpus,
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        if "FreeTier" in body or "limit=0" in body:
            print(
                "SKIP — explicit CachedContent storage is not available on your "
                "Gemini free tier (limit=0). Billing-enabled projects can run this section."
            )
            print(f"  API: {body[:280]}")
            return False
        print(f"FAILED to create cache: {body[:400]}")
        return False

    cache_name = cache.get("name", "")
    print(f"Created cache: {cache_name}")
    print(_usage_line("  cache create", cache.get("usageMetadata")))

    saw_cache_read = False
    for i, q in enumerate(
        [
            "What approval is needed for international travel?",
            "When is business class allowed on flights?",
        ],
        1,
    ):
        time.sleep(1.5)
        resp = generate_direct(api_key, model, user_text=q, cached_content=cache_name)
        um = resp.get("usageMetadata") or {}
        text = (
            resp.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
        print(_usage_line(f"  generate #{i}", um))
        print(f"    answer: {text[:100]}{'…' if len(text) > 100 else ''}")
        pipeline.record_prefix_cache_usage(
            um,
            model_id=_short_model(model),
            prefix_fingerprint=fp,
            provider="gemini",
        )
        if um.get("cachedContentTokenCount"):
            saw_cache_read = True

    if cache_name:
        _delete(f"{GEMINI_BASE}/{cache_name}?key={api_key}")
        print(f"Deleted cache: {cache_name}")

    if saw_cache_read:
        print("PASS — live explicit cache returned cachedContentTokenCount.")
    return saw_cache_read


def test_implicit_cache(
    api_key: str,
    model: str,
    pipeline: PrismPipeline,
    corpus: str,
) -> bool:
    print("\n=== 2) Implicit context cache (identical large prompts) ===")
    fp = hashlib.sha256(corpus.encode()).hexdigest()[:16]
    prompt = (
        f"{corpus}\n\n"
        "Question: Summarize international travel approval in one short sentence."
    )

    results: list[int] = []
    for i in range(1, 4):
        if i > 1:
            time.sleep(2.0)
        resp = generate_direct(api_key, model, user_text=prompt)
        um = resp.get("usageMetadata") or {}
        cached = um.get("cachedContentTokenCount") or 0
        results.append(cached)
        print(_usage_line(f"  identical request #{i}", um))
        pipeline.record_prefix_cache_usage(
            um,
            model_id=_short_model(model),
            prefix_fingerprint=fp,
            provider="gemini",
        )

    if any(results):
        print(f"PASS — implicit cache hit (counts={results}).")
        return True
    print(
        "INFO — no implicit cachedContentTokenCount (best-effort; not guaranteed). "
        "Use explicit CachedContent on a billed project for deterministic metrics."
    )
    return False


def test_litellm_proxy(model: str) -> None:
    print("\n=== 3) LiteLLM proxy (usage shape comparison) ===")
    master = os.environ.get("LITELLM_MASTER_KEY")
    if not master:
        print("SKIP — LITELLM_MASTER_KEY not set.")
        return
    try:
        resp = generate_litellm(
            model=model,
            user_text="Reply with exactly: PROXY_OK",
            master_key=master,
        )
    except urllib.error.URLError as exc:
        print(f"SKIP — proxy not reachable on :4000 ({exc}).")
        return

    usage = resp.get("usage") or {}
    reply = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
    print(f"  reply: {reply.strip()[:60]}")
    print(f"  proxy usage: {json.dumps(usage)}")
    print(f"  cached_tokens field: {cached if cached is not None else 'not present'}")
    print(
        "  → Tier 4 KV metrics need direct Gemini usageMetadata, not LiteLLM usage."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Gemini context cache probe for PRISM")
    parser.add_argument("--skip-implicit", action="store_true")
    parser.add_argument("--min-tokens", type=int, default=2048)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("GEMINI_API_KEY")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
    if not api_key:
        print("Set GEMINI_API_KEY in .env or environment.", file=sys.stderr)
        return 1

    print("PRISM Gemini context-cache probe")
    print(f"Model: {_model_resource(model)}")
    print(f"Building corpus with ≥{args.min_tokens} prompt tokens…")

    pipeline = PrismPipeline(PrismConfig(org_id="gemini-probe"))
    try:
        corpus, corpus_tokens = _corpus_for_min_tokens(
            api_key, model, min_tokens=args.min_tokens
        )
    except RuntimeError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"Using corpus with ~{corpus_tokens} prompt tokens.\n")

    explicit_live = test_explicit_cache(api_key, model, pipeline, corpus, corpus_tokens)
    prism_ok = test_simulated_prism(pipeline, model, corpus_tokens)

    implicit_live = False
    if not args.skip_implicit:
        implicit_live = test_implicit_cache(api_key, model, pipeline, corpus)
    test_litellm_proxy(model)

    print("\n=== 4) PRISM Tier 4 dashboard ===")
    print(pipeline.prefix_cache_dashboard())

    if explicit_live:
        print("\nOverall: LIVE explicit cache verified.")
        return 0
    if implicit_live:
        print(
            "\nOverall: LIVE implicit cache verified (cachedContentTokenCount on repeat). "
            "Explicit CachedContent needs a billed Gemini project."
        )
        return 0
    if prism_ok:
        print(
            "\nOverall: PRISM Tier 4 verified (simulated). "
            "Live explicit cache requires a billed Gemini project."
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
