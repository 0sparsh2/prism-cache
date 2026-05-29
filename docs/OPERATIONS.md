# Operations runbook

## Daily dev

```bash
source .venv/bin/activate
cp .env.example .env          # once; never commit .env
make redis-up                 # optional: persistent Tier 1/2/3
make gateway                  # LiteLLM on :4000
make demo-faq-dry             # no provider quota
```

## Environment

| Variable | Required | Purpose |
|----------|----------|---------|
| `LITELLM_MASTER_KEY` | Yes (live) | Proxy auth |
| `NVIDIA_NIM_API_KEY` | For NIM chat | `PRISM_CHAT_MODEL=deepseek-v4-flash` |
| `GEMINI_API_KEY` | For Gemini embed/chat | Quota-sensitive on free tier |
| `PRISM_CHAT_MODEL` | No | Overrides `GEMINI_MODEL` for chat |
| `REDIS_URL` | No | `redis://localhost:6379/0` for `create_pipeline()` |

## Gemini free tier

~20 `generate_content` requests/day per model on `gemini-2.5-flash-lite`. Use NIM for chat or `--dry-run` for cache demos. See [GATEWAY.md](GATEWAY.md).

## Invalidate handbook / RAG corpus

```python
pipeline.invalidate_corpus()  # bumps corpus_version; Tier 3 keys miss
```

Tier 1/2 FAQ buckets are separate; restart process or flush Redis `prism:t1:*` / `prism:t2:*` if needed.

## Health checks

```bash
curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" http://localhost:4000/v1/models | head
curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-embed","input":"ping"}' \
  http://localhost:4000/v1/embeddings | head
```

## Phase F (self-hosted)

When vLLM is deployed, see [LMCACHE.md](LMCACHE.md).
