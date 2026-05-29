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

```bash
pip install litellm redis
docker compose up -d redis

export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export LITELLM_MASTER_KEY=sk-local-dev

litellm --config gateway/litellm.prism.yaml --port 4000
```

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
