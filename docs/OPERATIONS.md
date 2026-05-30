# Operations runbook

## One-command verification

```bash
source .venv/bin/activate
cp .env.example .env          # once; never commit .env
make prod-redis               # optional: persistent Tier 1/2/3
make gateway                  # terminal 2: LiteLLM :4000
make run-all                  # tests + eval + demos (FAQ tolerates quota/timeout)
make run-all-cold             # FLUSHDB first — miss→write→hit arc
```

## Environment

| Variable | Required | Purpose |
|----------|----------|---------|
| `LITELLM_MASTER_KEY` | Yes (live) | Proxy auth |
| `REDIS_URL` | Recommended | `redis://localhost:6379/0` |
| `NVIDIA_NIM_API_KEY` | For NIM chat | `PRISM_CHAT_MODEL=deepseek-v4-flash` |
| `GEMINI_API_KEY` | For Gemini embed/chat | Quota-sensitive on free tier |
| `PRISM_CHAT_MODEL` | No | Overrides `GEMINI_MODEL` for chat |
| `VLLM_BASE_URL` | Phase F | `http://localhost:8000/v1` when GPU stack up |
| `HF_TOKEN` | Phase F | Hugging Face model access for vLLM |

## Makefile targets

| Target | Purpose |
|--------|---------|
| `make test` | 59 pytest cases |
| `make eval` | Offline governance benchmarks (CI gate) |
| `make eval-live` | + Gemini embed near-intent table |
| `make scenario-org` | 500-employee Tier 3 narrative |
| `make demo-proxy` | Route → lane resolution (offline) |
| `make gateway-prism` | LiteLLM + PRISM callback |
| `make gateway-full` | NIM + Gemini + vLLM route + callback |
| `make phase-f-up` | Docker vLLM+LMCache (GPU + `HF_TOKEN`) |
| `make demo-phase-f-chat` | POST to vLLM when :8000 is up |

## Gemini free tier

~20 `generate_content` requests/day per model on `gemini-2.5-flash-lite`. Use NIM for chat or `--dry-run` for cache demos. FAQ demo continues on timeout/quota errors. See [GATEWAY.md](GATEWAY.md).

## Invalidate handbook / RAG corpus

```python
pipeline.invalidate_corpus()  # bumps corpus_version; Tier 3 keys miss
```

Tier 1/2 FAQ buckets are separate; flush Redis `prism:t1:*` / `prism:t2:*` if content changed materially.

## Health checks

```bash
curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" http://localhost:4000/v1/models | head
redis-cli ping
curl -s ${VLLM_BASE_URL:-http://localhost:8000/v1}/models | head   # Phase F
```

## Phase F (self-hosted GPU)

```bash
export HF_TOKEN=...
export VLLM_BASE_URL=http://localhost:8000/v1
make phase-f-up
PYTHONPATH=src:gateway make gateway-full
make demo-phase-f-chat
```

See [LMCACHE.md](LMCACHE.md) · [ORG_SCENARIO.md](ORG_SCENARIO.md) · [BENCHMARKS.md](BENCHMARKS.md)
