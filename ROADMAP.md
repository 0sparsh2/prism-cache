# Build roadmap — PRISM-Cache

Research is complete under [`research/`](research/). Implementation phases below.

## Phase A — Foundation (Week 0–1)

- [x] Cache lane taxonomy (`user-private`, `team`, `org-static`) in config
- [x] Tier 0: normalization spec + PII scrub hook (DLP or rules)
- [x] Key schema: `org_id`, `lane`, `sensitivity`, `corpus_version`, `model_id`
- [x] Metrics: hit rate, latency, tokens avoided, by tier and lane
- [x] Security review template for cross-user writes

## Phase B — Tier 3 retrieval cache (Week 1–2) ⭐

- [x] Redis (or Valkey) layer in front of vector DB
- [x] Corpus version service (tie to CMS / doc pipeline)
- [x] Integration with existing RAG path (embed → lookup → skip ANN on hit)
- [x] Load tests with synthetic duplicate queries across “users”

## Phase C — Tier 4 prefix optimization (Week 3–4)

- [x] Prompt template audit: stable prefix, variable suffix
- [x] Provider `cache_control` markers
- [x] Dashboard for `cache_read_input_tokens` / creation tokens

## Phase D — Gateway + Tier 1 (Month 2)

- [x] LiteLLM (or Portkey) as org-wide OpenAI-compatible entry
- [x] Exact cache for `org-static` FAQ lane only
- [x] Route rules: coding tools → `user-private` by default

## Phase E — Tier 2 semantic (Month 3+, gated)

- [x] Semantic cache on FAQ lane only; threshold ≥ 0.95–0.97 (configurable)
- [x] Optional: vCache-style per-entry thresholds (`similarity_threshold` on store)
- [x] Red-team paraphrase suite before widening lanes (`tests/test_tier2_redteam.py`)

## Phase F — Self-hosted inference (scaffold)

**Status: scaffold shipped** — run when you have GPUs. API path uses [docs/PRODUCTION.md](docs/PRODUCTION.md).

- [x] `lmcache_integration.py` — vLLM KV transfer config + launch spec from Tier 4 prompt
- [x] `docker-compose.vllm-lmcache.yml`, `deploy/lmcache-config.yaml`
- [x] `examples/phase_f_rag_vllm.py`, [docs/LMCACHE.md](docs/LMCACHE.md)
- [ ] Production GPU fleet tuning (remote_url, multi-replica router)

## Integration order (decision)

| Priority | Work | Why |
|----------|------|-----|
| **1 — done** | Tier 2 + LiteLLM + Gemini (`litellm_client.py`, `faq_litellm_gemini.py`) | Closes the loop on your current `.env`; real embeddings + chat through one proxy |
| **2 — done** | `factory.create_pipeline`, Redis backends, Makefile, `rag_litellm_demo.py` | One-liner setup from config + `.env` |
| **3 — done** | [Production](docs/PRODUCTION.md) + Phase F scaffold | Redis compose, `create_production_pipeline`, vLLM+LMCache compose |
| **4 — done** | [Org scenario](docs/ORG_SCENARIO.md) + proxy enforcement docs | 500-employee Tier 3 narrative, `make scenario-org`, GATEWAY lane rules |

Do **not** enable LiteLLM `redis-semantic` for FAQ until PRISM policy lanes are mirrored at the proxy — PRISM Tier 2 is lane-gated; proxy semantic cache is not.

## v0.4 shipped (`src/prism_cache/`)

| Module | Purpose |
|--------|---------|
| `tier2.py` | Semantic FAQ answer cache (org-static, gated threshold) |
| `tier1.py` | Exact FAQ answer cache (org-static lane) |
| `routes.py` | Route → lane rules (coding → user-private) |
| `settings.py` | Load `config/prism.example.yaml` |
| `litellm_config.py` | Generate LiteLLM proxy + Redis config |
| `gateway/litellm.prism.yaml` | Ready-to-run proxy config |

Prior modules: `tier0`, `tier3`, `tier4`, `pipeline`, `policy`, `metrics`, `corpus`, `keys`, `prompt_audit`, `prefix_metrics`.

See [`docs/BUILD.md`](docs/BUILD.md) and [`docs/GATEWAY.md`](docs/GATEWAY.md).

## Next (v0.6 candidates)

- [x] `eval --live` — Gemini-embed near-intent FPR alongside offline suite
- [x] LiteLLM pre-call hook prototype for route → lane assignment
- [ ] Phase F GPU fleet tuning (remote_url, multi-replica router)

## Out of scope (v1)

- Org-wide semantic cache for open-ended HR/legal chat
- Caching raw coding assistant buffers without repo-scoped keys
