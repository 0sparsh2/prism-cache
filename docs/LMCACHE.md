# Phase F — LMCache + vLLM

Self-hosted **KV tensor reuse** across GPU workers. Complements PRISM Tier 4 (prefix assembly + metrics); does not replace Tier 1–3.

## When to use

| Use LMCache | Skip LMCache |
|-------------|--------------|
| vLLM on your GPUs | API-only (Gemini, NIM, OpenAI via LiteLLM) |
| Same long system+RAG prefix across users | Short or unique prompts every request |
| Tier 4 audit `ok` on shared prefix | Volatile timestamps in prefix |

## Stack diagram

```text
                    ┌─────────────────┐
  FAQ / RAG app ───►│ PRISM (Tier 0–4)│──► Redis (T1/T2/T3)
                    └────────┬────────┘
                             │ rag_prepare() → stable prefix
                             ▼
                    ┌─────────────────┐
                    │ vLLM + LMCache  │ :8000  (OpenAI-compatible)
                    └─────────────────┘
```

Hosted APIs: keep using [PRODUCTION.md](PRODUCTION.md) (LiteLLM + Redis).

## Quick start (GPU machine)

```bash
export HF_TOKEN=...
docker compose -f docker-compose.vllm-lmcache.yml up
```

Default model in compose: `meta-llama/Llama-3.1-8B-Instruct` — change in `docker-compose.vllm-lmcache.yml`.

## PRISM → vLLM bridge

```bash
python examples/phase_f_rag_vllm.py
```

```python
from prism_cache import create_pipeline
from prism_cache.lmcache_integration import build_vllm_spec, openai_messages_for_vllm

pipeline = create_pipeline(config_path="config/prism.example.yaml")
bundle = pipeline.rag_prepare(query, retriever, resolve_chunk_text, route_name="program-rag")

spec = build_vllm_spec(bundle.prompt, model="meta-llama/Llama-3.1-8B-Instruct")
messages = openai_messages_for_vllm(bundle.prompt)
# POST messages to http://localhost:8000/v1/chat/completions
# record_prefix_cache_usage() for app metrics; LMCache handles GPU KV
```

Library helpers: `src/prism_cache/lmcache_integration.py`

| Function | Purpose |
|----------|---------|
| `build_vllm_spec()` | KV transfer JSON + LMCache env from `AssembledPrompt` |
| `openai_messages_for_vllm()` | OpenAI message list for vLLM server |
| `render_lmcache_config_yaml()` | Generate `deploy/lmcache-config.yaml` |
| `docker_run_example()` | Printable `docker run` snippet |

## Configuration files

| File | Role |
|------|------|
| `deploy/lmcache-config.yaml` | LMCache CPU / remote tier |
| `docker-compose.vllm-lmcache.yml` | Single-GPU vLLM + LMCache |
| `docker-compose.prod.yml` | Redis only (API production path) |

## Multi-node

For shared LMCache across vLLM replicas, run `lmcache_server` and set in `deploy/lmcache-config.yaml`:

```yaml
local_cpu: false
remote_url: "lm://lmcache-server:65432"
remote_serde: "cachegen"
```

See [LMCache Docker deployment](https://docs.lmcache.ai/production/docker_deployment.html).

## LiteLLM routing to vLLM (optional)

Add to `gateway/litellm.multi.yaml`:

```yaml
  - model_name: llama-3.1-8b
    litellm_params:
      model: openai/meta-llama/Llama-3.1-8B-Instruct
      api_base: http://host.docker.internal:8000/v1
      api_key: os.environ/LITELLM_MASTER_KEY
```

PRISM stays in-process; LiteLLM becomes a router to your GPU fleet.

## References

- [LMCache paper](https://arxiv.org/pdf/2510.09665)
- [lmcache/vllm-openai image](https://hub.docker.com/r/lmcache/vllm-openai)
