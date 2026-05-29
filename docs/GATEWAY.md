# PRISM-Cache + LiteLLM gateway

Phase D adds an **org-wide LLM entry point** (LiteLLM) alongside **PRISM Tier 1** exact FAQ cache in the application layer.

## Architecture

```text
Chatbot / IDE / RAG app
        │
        ├─► PRISM Tier 1 (exact FAQ, org-static lane)     ← app library
        ├─► PRISM Tier 3 (retrieval) + Tier 4 (prefix)   ← app library
        │
        └─► LiteLLM proxy :4000/v1                       ← all LLM HTTP calls
                └─► Redis namespace prism:litellm         ← proxy-level exact cache
```

**Two cache layers, different jobs:**

| Layer | What it caches | Scope |
|-------|----------------|--------|
| PRISM Tier 1 | Normalized FAQ question → full answer | Org-static lane, policy-governed |
| LiteLLM Redis | Identical HTTP request bodies | Proxy-wide, all routes |

Route rules (`config/prism.example.yaml`) send **coding tools → `user-private`** so they never write org-wide Tier 1 entries.

## Run LiteLLM locally

**Use the project venv** (Python **3.11–3.13**). LiteLLM does not install on **Python 3.14** yet (orjson build). Do not use a global `litellm` from Python 3.9.

### Option A — one venv on Python 3.12 (recommended)

```bash
cd "/Users/sparshnagpal/Desktop/projects/Distributed Prompt Caching"
deactivate 2>/dev/null || true
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,gateway]"

docker compose up -d redis

export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export LITELLM_MASTER_KEY=sk-local-dev

litellm --config gateway/litellm.prism.yaml --port 4000
```

### Option B — keep PRISM on 3.14, separate gateway venv

```bash
python3.12 -m venv .venv-gateway
source .venv-gateway/bin/activate
pip install 'litellm[proxy]' redis
litellm --config gateway/litellm.prism.yaml --port 4000
```

Verify which binary runs:

```bash
which litellm          # should be inside your activated venv, not .../Python/3.9/...
python --version       # 3.11–3.13 for LiteLLM
```

### Troubleshooting

| Error | Cause | Fix |
|-------|--------|-----|
| `No module named 'fastapi_sso'` | Installed `litellm` without proxy extras | `pip install 'litellm[proxy]'` in **venv** |
| `unsupported operand type(s) for \|` | Python 3.9 global `litellm` | Use venv on 3.11–3.13 |
| `Failed building wheel for orjson` | Python 3.14 venv | Recreate venv with `python3.12` |
| Redis connection errors | Redis not running | `docker compose up -d redis` |

Point clients at `http://localhost:4000/v1` with `Authorization: Bearer $LITELLM_MASTER_KEY`.

## Environment variables (`.env`)

Copy the template and load it before starting the proxy:

```bash
cp .env.example .env
# edit .env — set LITELLM_MASTER_KEY (any secret you choose) and provider keys

set -a && source .env && set +a
litellm --config gateway/litellm.prism.yaml --port 4000
```

| Variable | Used by | Notes |
|----------|---------|--------|
| `LITELLM_MASTER_KEY` | All gateway configs | **Self-chosen** proxy password, not from a vendor |
| `OPENAI_API_KEY` | `litellm.prism.yaml` | OpenAI models |
| `ANTHROPIC_API_KEY` | `litellm.prism.yaml` | Anthropic models (prefix KV metrics in PRISM Tier 4) |
| `NVIDIA_NIM_API_KEY` | `litellm.nim.yaml` | From [build.nvidia.com](https://build.nvidia.com) |
| `NVIDIA_NIM_API_BASE` | `litellm.nim.yaml` | Default: `https://integrate.api.nvidia.com/v1` |
| `NVIDIA_MODEL` | Reference only | Document which NIM model you configured in YAML |
| `GEMINI_API_KEY` | `litellm.gemini.yaml`, `litellm.multi.yaml` | From [Google AI Studio](https://aistudio.google.com/apikey) |
| `GEMINI_EMBED_MODEL` | `litellm.multi.yaml` | Proxy alias (default `gemini-embed` → `gemini/gemini-embedding-001`) |
| `LITELLM_BASE_URL` | `litellm_client.py` | Default `http://localhost:4000` |

Use unquoted values in `.env` (`GEMINI_API_KEY=AIza...`, not `"AIza..."`) — quotes become part of the value for some loaders.

## NVIDIA NIM gateway

Hosted NIM does not expose Anthropic-style prefix KV token fields. You still get **PRISM Tier 1/3** (app) and **LiteLLM Redis** (identical HTTP bodies). For provider KV dashboards, use Anthropic/OpenAI via `litellm.prism.yaml` and `pipeline.record_prefix_cache_usage(..., provider="anthropic"|"openai")`.

```bash
set -a && source .env && set +a
docker compose up -d redis
litellm --config gateway/litellm.nim.yaml --port 4000
```

Test:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hello"}]}'
```

To use a different NIM model, edit `model_list` in `gateway/litellm.nim.yaml` (`nvidia_nim/<org>/<model>`) and update `NVIDIA_MODEL` in `.env` for your notes.

## Gemini context-cache probe (correct test)

Short `"hello"` curls **cannot** show KV cache — prompts are too small and LiteLLM strips `cachedContentTokenCount`.

Run the probe (direct Gemini API + PRISM Tier 4):

```bash
set -a && source .env && set +a
python examples/gemini_cache_probe.py
```

What it does:

1. Builds a **≥2048-token** handbook corpus (Gemini minimum for flash-lite)
2. Attempts **explicit** `CachedContent` create + generate (needs **billed** Gemini; free tier returns `limit=0`)
3. **Implicit** cache — identical large prompts ×3 with backoff
4. Compares **LiteLLM proxy** `usage` (no cache field) vs direct `usageMetadata`
5. **Simulated** documented `cachedContentTokenCount` → PRISM dashboard (proves Tier 4 parsing)

## Google Gemini gateway

Gemini 2.5+ supports **implicit context caching** and reports hits in `usage_metadata.cached_content_token_count`. PRISM Tier 4 can track this:

```python
pipeline.record_prefix_cache_usage(
    response.usage_metadata,  # or dict from REST usageMetadata
    model_id="gemini-2.5-flash-lite",
    prefix_fingerprint=fp,
    provider="gemini",
)
print(pipeline.prefix_cache_dashboard())
```

```bash
set -a && source .env && set +a
litellm --config gateway/litellm.gemini.yaml --port 4000
```

Test:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-2.5-flash-lite","messages":[{"role":"user","content":"hello"}]}'
```

**NIM + Gemini together:** `gateway/litellm.multi.yaml` exposes chat + `gemini-embed` (Tier 2 embeddings). Restart the proxy after changing this file.

## PRISM Tier 2 + LiteLLM + Gemini

Policy-governed semantic FAQ cache lives in **PRISM** (not LiteLLM `redis-semantic`).

```bash
set -a && source .env && set +a
litellm --config gateway/litellm.multi.yaml --port 4000
python examples/faq_litellm_gemini.py
```

```python
from prism_cache.litellm_client import LiteLLMClient

client = LiteLLMClient.from_env()
pipeline = PrismPipeline(
    PrismConfig(org_id="acme", tier2_similarity_threshold=0.92),
    tier2_embed=client.make_embed_fn(),
)
pipeline.faq_answer(
    "how do I reset my login password?",
    "internal-faq-bot",
    client.make_generate_fn(system="You are IT support."),
    user_id="bob",
)
```

Dry run without proxy: `python examples/faq_litellm_gemini.py --dry-run`

### Gemini free-tier 429 / quota

If LiteLLM logs `GenerateRequestsPerDayPerProjectPerModel-FreeTier` with `quotaValue: 20`, you hit the **daily** cap for `gemini-2.5-flash-lite`, not a proxy bug. Our probes + FAQ demo burn through that quickly.

| Workaround | Command / config |
|------------|------------------|
| No API calls | `python examples/faq_litellm_gemini.py --dry-run` |
| Use NIM for chat | `PRISM_CHAT_MODEL=deepseek-v4-flash` in `.env` (embeddings can stay `gemini-embed`) |
| Wait | Quota resets daily (Pacific time for Google AI Studio) |
| Production | Enable billing on [Google AI Studio](https://aistudio.google.com) |

PRISM Tier 1/2 still help after the first answer is cached — later users avoid `generate` calls.

## Proxy enforcement — lanes before write-back

**Do not** enable LiteLLM `redis-semantic` for org FAQ/RAG until PRISM lane policy is mirrored at the proxy. Proxy semantic cache has **no** concept of `user-private` / `team` / `org-static` — it keys on raw HTTP bodies only.

### Correct split today

| Enforcement point | Responsibility |
|-------------------|----------------|
| **Application** (PRISM library) | Tier 0 classify → route → lane; `write_policy_denial_reason`; Tier 3/2/1 keys include `org_id`, lane, `corpus_version` |
| **LiteLLM proxy** | Provider routing, auth, optional **exact** HTTP body cache (`prism:litellm` namespace) |
| **Not yet** | Automatic lane assignment inside LiteLLM pre-call hooks |

### Request flow (target architecture)

```text
Client → LiteLLM :4000/v1
            │
            ▼
     App middleware (your service)
            │
            ├─► route_name → routes.yaml lane (coding → user-private)
            ├─► PRISM Tier 3 retrieve (shared chunk IDs if allowed)
            ├─► LLM generate via LiteLLM
            └─► PRISM async write-back ONLY if allows_tier*_write(ctx, tier0)
```

### Rules of thumb

1. **Coding tools** → `coding-assistant` route → **`user-private`** — never org-wide Tier 1/2 writes.
2. **Handbook RAG** → `program-rag` → **`team`** lane + `corpus_version` — Tier 3 lead path ([ORG_SCENARIO.md](ORG_SCENARIO.md)).
3. **IT FAQ** → `internal-faq-bot` → **`org-static`** — Tier 1 exact; Tier 2 optional and threshold-gated.
4. **Audit** — log tier, lane, hit/miss, denial reason; avoid raw PII prompts in logs (`prompt_audit.py`).

Until proxy hooks ship, **call PRISM in application code before/after LiteLLM** — the library enforces policy; the proxy alone does not.

See [ROADMAP.md](../ROADMAP.md): do not enable proxy semantic FAQ cache without lane mirroring.

## Generate config from PRISM settings

```python
from prism_cache.litellm_config import build_litellm_config, render_litellm_yaml
from prism_cache.settings import load_settings

settings = load_settings("config/prism.example.yaml")
print(render_litellm_yaml(build_litellm_config(redis_url=settings.redis.url)))
```

## Application integration

```python
from prism_cache import PrismPipeline, PrismConfig
from prism_cache.routes import default_routes

pipeline = PrismPipeline(PrismConfig(org_id="acme"), routes=default_routes())

answer, lookup = pipeline.faq_answer(
    "how do I reset my password?",
    route_name="internal-faq-bot",
    generate=lambda q: call_litellm(q),
    model_id="gpt-4o-mini",
    user_id="alice",
)
```

See `examples/tier1_faq_demo.py`.
