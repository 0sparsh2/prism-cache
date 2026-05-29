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

- [ ] LiteLLM (or Portkey) as org-wide OpenAI-compatible entry
- [ ] Exact cache for `org-static` FAQ lane only
- [ ] Route rules: coding tools → `user-private` by default

## Phase E — Tier 2 semantic (Month 3+, gated)

- [ ] Semantic cache on FAQ lane only; threshold ≥ 0.95–0.97
- [ ] Optional: vCache-style per-entry thresholds
- [ ] Red-team paraphrase suite before widening lanes

## Phase F — Self-hosted inference (optional)

- [ ] LMCache + vLLM for cross-node KV if not API-only

## v0.2 shipped (`src/prism_cache/`)

| Module | Purpose |
|--------|---------|
| `tier0.py` | Normalize, scrub PII, classify lane |
| `tier3.py` | Retrieval cache + memory/Redis stores |
| `tier4.py` | RAG prefix assembly + Anthropic `cache_control` |
| `prompt_audit.py` | Template audit for cache-safe prefixes |
| `prefix_metrics.py` | Tier 4 token dashboard |
| `pipeline.py` | `rag_prepare()` — Tier 3 + Tier 4 |
| `keys.py` | Deterministic cache keys |
| `policy.py` | Cross-user write rules |
| `metrics.py` | Hit rate / latency registry |
| `corpus.py` | Version bump / invalidation |

See [`docs/BUILD.md`](docs/BUILD.md) for install and usage.

## Out of scope (v1)

- Org-wide semantic cache for open-ended HR/legal chat
- Caching raw coding assistant buffers without repo-scoped keys
