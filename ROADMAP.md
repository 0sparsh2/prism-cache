# Build roadmap — PRIME-CACHE

Research is complete under [`research/`](research/). Implementation phases below.

## Phase A — Foundation (Week 0–1)

- [ ] Cache lane taxonomy (`user-private`, `team`, `org-static`) in config
- [ ] Tier 0: normalization spec + PII scrub hook (DLP or rules)
- [ ] Key schema: `org_id`, `lane`, `sensitivity`, `corpus_version`, `model_id`
- [ ] Metrics: hit rate, latency, tokens avoided, by tier and lane
- [ ] Security review template for cross-user writes

## Phase B — Tier 3 retrieval cache (Week 1–2) ⭐

- [ ] Redis (or Valkey) layer in front of vector DB
- [ ] Corpus version service (tie to CMS / doc pipeline)
- [ ] Integration with existing RAG path (embed → lookup → skip ANN on hit)
- [ ] Load tests with synthetic duplicate queries across “users”

## Phase C — Tier 4 prefix optimization (Week 3–4)

- [ ] Prompt template audit: stable prefix, variable suffix
- [ ] Provider `cache_control` markers
- [ ] Dashboard for `cache_read_input_tokens` / creation tokens

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

## Out of scope (v1)

- Org-wide semantic cache for open-ended HR/legal chat
- Caching raw coding assistant buffers without repo-scoped keys
