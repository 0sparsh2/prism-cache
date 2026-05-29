# Production deployment

API-first production path: **Redis-backed PRISM tiers** + **LiteLLM** as the org LLM entry. Phase F (vLLM + LMCache) is a separate GPU stack — [LMCACHE.md](LMCACHE.md).

## Architecture

```text
Apps (FAQ bot, RAG service)
    │
    ├─► PRISM library (Tier 0–4, policy lanes)
    │       └─► Redis (Tier 1 exact, Tier 2 semantic, Tier 3 retrieval)
    │
    └─► LiteLLM :4000 (chat + embeddings)
            ├─► NIM / OpenAI / Anthropic / Gemini (your keys)
            └─► Redis namespace prism:litellm (identical HTTP bodies)
```

## 1. Configure

```bash
cp .env.example .env
```

Required for live FAQ + Tier 2 embeddings:

```bash
LITELLM_MASTER_KEY=...
REDIS_URL=redis://localhost:6379/0
NVIDIA_NIM_API_KEY=...          # or use Gemini with billing
PRISM_CHAT_MODEL=deepseek-v4-flash
GEMINI_EMBED_MODEL=gemini-embed
GEMINI_API_KEY=...              # Tier 2 embeddings via proxy
LITELLM_BASE_URL=http://localhost:4000
```

Copy `config/prism.production.yaml` and set `org_id`.

## 2. Start stack

```bash
docker compose -f docker-compose.prod.yml up -d
```

Or local dev: `make redis-up && make gateway`.

## 3. Application code

```python
from prism_cache import create_pipeline, LiteLLMClient

pipeline = create_pipeline(
    config_path="config/prism.production.yaml",
    use_litellm_embed=True,
)
client = LiteLLMClient.from_env()

answer = pipeline.faq_answer(
    "how do I reset my login password?",
    "internal-faq-bot",
    client.make_generate_fn(system="You are IT support."),
    user_id="user-123",
    model_id="deepseek-v4-flash",
)
```

`create_pipeline()` reads `REDIS_URL` and wires **Redis** stores for Tier 1/2/3 automatically.

Run the reference app:

```bash
python examples/production_app.py
python examples/production_app.py --dry-run
```

## 4. Corpus invalidation

On document publish:

```python
pipeline.invalidate_corpus()
```

Bump CMS webhook → `corpus_version` changes → Tier 3 misses; refresh Tier 1/2 FAQ entries manually or flush `prism:t1:*` / `prism:t2:*` if content changed materially.

## 5. Observability

```python
print(pipeline.metrics_snapshot())
print(pipeline.prefix_cache_dashboard())
```

Export to Prometheus/Grafana in your app layer from `metrics_snapshot()` JSON.

## 6. Security checklist

- [ ] `.env` never in git
- [ ] `user-private` route for coding tools (`tier1_enabled` / `tier2_enabled` false)
- [ ] PII scrub (Tier 0) before any cross-user write
- [ ] Separate Redis DB or key prefixes per environment

See [SECURITY_REVIEW.md](SECURITY_REVIEW.md).
