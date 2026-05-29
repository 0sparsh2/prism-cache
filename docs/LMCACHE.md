# Phase F — LMCache (deferred)

PRISM **Phase F** applies when you **self-host inference** (vLLM, TensorRT-LLM, etc.), not when using hosted APIs (Gemini, NIM, OpenAI).

## What LMCache adds

| Layer | Scope |
|-------|--------|
| **PRISM Tier 4** | Tracks provider `cache_read_input_tokens` / Gemini `cachedContentTokenCount` in app metrics |
| **LMCache** | Distributes **KV tensors** across GPU workers for identical prefixes at inference time |

LMCache does **not** replace Tier 1–3 (FAQ exact/semantic, retrieval). It complements Tier 4 when you own the model runtime.

## When to adopt

- Multiple vLLM replicas serving the same long system+RAG prefix
- Prefix identical across users (Tier 4 audit passes)
- GPU memory pressure from repeated prefill

## When to skip (current setup)

- API-only stack via LiteLLM → Gemini / NIM
- No vLLM deployment

## Sketch integration (future)

```text
Client → LiteLLM (routing) → vLLM + LMCache sidecar
                ↑
         PRISM app (Tier 3 retrieval, Tier 4 prompt assembly)
```

1. PRISM `rag_prepare()` builds stable prefix + `cache_control` (Anthropic) or implicit prefix (Gemini).
2. vLLM request includes LMCache connector config (see [LMCache docs](https://arxiv.org/pdf/2510.09665)).
3. `record_prefix_cache_usage()` remains the app-level dashboard; LMCache ops metrics live in inference stack.

Track implementation in [ROADMAP.md](../ROADMAP.md) when vLLM is in scope.
