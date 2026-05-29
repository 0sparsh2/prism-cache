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
