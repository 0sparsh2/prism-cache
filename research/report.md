# Distributed prompt caching for enterprise LLM/RAG workloads (2025–2026)

## Methodology

This report was produced with the **deep-research** workflow (Phase 3 synthesis),
inspired by [Weizhena/Deep-Research-skills](https://github.com/Weizhena/Deep-Research-skills)
and structured evidence gathering aligned with [RhinoInsight](https://arxiv.org/html/2511.18743v1).

- **Phase 1:** Research outline and field schema (`outline.yaml`, `fields.yaml`).
- **Phase 2:** One validated JSON artifact per item under `results/`, including
  cross-user sharing and PII/compliance controls.
- **Phase 3:** This document — synthesized findings with sources, omitting fields
  marked uncertain in source JSON.

**Problem framing (clarified):** One organization with thousands of users across
chatbots, coding assistants, and document/RAG search. Per-user KV cache does not help
the next employee. The goal is **cross-user reuse** with **compliance** and **no PII leakage**.

## Executive summary

| Finding | Conclusion |
|---------|------------|
| Does a unified product exist? | **No** — fragments (gateways, Redis, GPTCache, LMCache, provider prefix cache). |
| Is the idea viable? | **Yes** — as a **policy-aware multi-tier platform**, not a single semantic switch. |
| Best cross-user tier | **Tier 3 (retrieval cache)** — reuse doc chunks, not personal answers. |
| Highest risk tier | **Tier 2 (semantic full answer)** — false positives and PII leakage across users. |
| Recommended stack | **LiteLLM (or Portkey) + Redis/Qdrant + custom Tier 3 + provider prefix (Tier 4).** |
| Rollout | Lanes/DLP → Tier 3 → Tier 4 → Tier 1 FAQ → Tier 2 (gated) → LMCache if self-hosted. |

### Request flow (tiers)

```
User query → Tier 0 normalize/scrub/classify
          → Tier 1 exact hit? → return
          → Tier 2 semantic hit? (guarded lane) → return
          → Tier 3 retrieval hit? → generate with cached chunks
          → Tier 4 prefix KV hit? → cheaper generation
          → full LLM → async write-back to allowed tiers
```

## Table of contents

- [Problem and opportunity](#problem-and-opportunity)
- [Cross-user shared cache safety model](#cross-user-shared-cache-safety-model)
- [Multi-tier reference architecture](#multi-tier-reference-architecture)
- [Tier 0 query normalization](#tier-0-query-normalization)
- [Tier 1 exact hash cache](#tier-1-exact-hash-cache)
- [Tier 2 semantic response cache](#tier-2-semantic-response-cache)
- [Tier 3 RAG retrieval cache](#tier-3-rag-retrieval-cache)
- [Tier 4 provider prefix KV cache](#tier-4-provider-prefix-kv-cache)
- [GPTCache](#gptcache)
- [LiteLLM proxy caching](#litellm-proxy-caching)
- [Portkey AI gateway](#portkey-ai-gateway)
- [Redis LangCache and langchain-redis](#redis-langcache-and-langchain-redis)
- [LMCache and distributed KV reuse](#lmcache-and-distributed-kv-reuse)
- [RAG chunk KV research](#rag-chunk-kv-research)
- [Carbon and sustainability](#carbon-and-sustainability)
- [Enterprise governance and risks](#enterprise-governance-and-risks)
- [Build vs buy and rollout priority](#build-vs-buy-and-rollout-priority)

---

## Problem and opportunity

*One org, thousands of users (chatbots, coding assistants, doc/RAG search) repeating the same or similar prompts across people; per-user/session KV cache does not help the next employee. Need cross-user reuse with compliance and zero PII leakage.*

#### Basic Info

**Name:** Problem and opportunity

**Category:** Landscape

#### Exists today

**Already Exists:** partial_fragment

**Existence Evidence:** Per-user/session KV and provider prefix caching are production features (Anthropic prompt caching, vLLM/LMCache). Org-wide semantic and retrieval caches exist as gateway features (Portkey, LiteLLM) and libraries (GPTCache) but not as a unified compliance-aware cross-user product. Enterprises report 40-80% potential cost reduction from semantic caching in repetitive workloads (industry blogs and Percona benchmarks).

**Gap Vs Vision:** The vision is thousands of employees across chatbots, coding tools, and doc search reusing safe work across users. Today most caching is per-session, per-app, or ungoverned shared Redis. Missing: central policy lanes, clearance-tier keys, coordinated invalidation on doc version, and audit proving User B never received User A's PII.

#### Technical

**Summary:** Large organizations pay repeatedly for the same LLM work: similar questions, same handbook chunks, identical system prompts. Single-user KV cache only helps the same person on the next turn with an identical prefix. Cross-user reuse requires deliberate cache classes and governance, not flipping one semantic-cache switch.

**How It Works:** Workload pattern: high duplicate intent, low duplicate bytes. Employees paraphrase FAQs, policy, and engineering docs. Without org cache: every user triggers full embed-retrieve-generate. With org cache: shared tiers (retrieval, exact FAQ, guarded semantic) keyed by corpus version and sensitivity tier.

**Integration Points:** Sits above all AI surfaces: API gateway (LiteLLM/Portkey), RAG services (Qdrant), identity/clearance from IAM, DLP on ingress, async write-back workers, observability for hit rate and leakage incidents.

**Correctness Risks:** Treating org cache as one global bucket causes wrong answers and regulatory breach. Under-caching leaves money and carbon on the table.

#### Economics and impact

**Cost Latency Impact:** Industry reports: semantic hits can be 250x faster than full LLM calls; 40-80% cost reduction possible on repetitive traffic at 60% hit rates (vendor/anecdotal—varies by workload). Cross-user retrieval cache often yields large savings with lower risk than answer cache.

**Environmental Impact:** Fewer tokens and GPU cycles reduce operational carbon; shared caching amplifies savings vs per-user-only reuse.

#### Enterprise fit

**Cross User Sharing:** org_wide_with_guards — only via tiered lanes; never one undifferentiated pool

**Pii And Compliance Controls:** Mandatory: partition by org_id + sensitivity + corpus_version; scrub before hash/embed; block high-PII prompts from shared lanes; audit hits without logging raw PII.

**Org Scale Patterns:** Single logical cache plane, many physical namespaces (faq, team-project, user-private). All tools route through gateway or shared SDK enforcing same key schema.

**Rollout Priority:** Foundation: define lanes and metrics before enabling cross-user writes

**Makes Sense Verdict:** strong_yes

**Makes Sense Rationale:** Problem is real, measurable, and aligned with cost/ESG goals. Exists as fragments; integrator opportunity is compliance-safe cross-user reuse.

#### Sources

**Primary Sources**

- [Anthropic prompt caching overview](https://github.com/anthropics/skills/blob/main/skills/claude-api/shared/prompt-caching.md)
- [Percona semantic caching benchmarks](https://www.percona.com/blog/semantic-caching-for-llm-apps-reduce-costs-by-40-80-and-speed-up-by-250x/)
- [LMCache enterprise KV layer](https://arxiv.org/pdf/2510.09665)

---

## Cross-user shared cache safety model

*When answers may be shared org-wide vs per-team vs never; cache key design, redaction, tenancy, audit, and what must stay user-private (coding context, HR, etc.).*

#### Basic Info

**Name:** Cross-user shared cache safety model

**Category:** Governance

#### Exists today

**Already Exists:** partial_fragment

**Existence Evidence:** Gateways offer org-level caching (Portkey) but rarely ship complete ABAC+DLP+lane models. Cloud providers offer encryption and tenant IDs; enterprises implement classification via internal policy engines. vCache and similar research address correctness bounds, not HR/legal tenancy.

**Gap Vs Vision:** No standard SKU for 'safe cross-user LLM cache.' Organizations must define lanes: user-private, team+clearance, org-static FAQ. Vision adds write/read policy, erasure, and prohibited content classes per lane.

#### Technical

**Summary:** Framework for when User B may receive cached artifacts derived from User A's traffic. Separates cacheable public intent from personal context (HR, health, proprietary code, named individuals).

**How It Works:** Lanes: (1) user-private—no cross-user reads; (2) team/project—shared if same clearance+corpus; (3) org-static—scrubbed FAQs and retrieval-only keys. Keys include org_id, lane, sensitivity, corpus_version, model_id. Write path: classify prompt, scrub, reject or route. Read path: match lane+clearance+version. Optional LLM judge on grey-zone semantic hits.

**Integration Points:** Gateway middleware, RAG preprocessor, SIEM/audit bus, IAM attributes, DLP/NER services, legal retention policies.

**Correctness Risks:** Semantic false positive across users is a data breach and wrong decision. Coding tools leaking snippets across repos. Stale policy docs after version bump.

#### Economics and impact

**Cost Latency Impact:** Governance adds milliseconds (classification) vs dollars saved on hits; net positive when hit rate >5-10% on shared lanes.

**Environmental Impact:** Indirect: safer sharing enables broader reuse and fewer redundant GPU jobs.

#### Enterprise fit

**Cross User Sharing:** org_wide_with_guards — lane-dependent

**Pii And Compliance Controls:** Normalize+hash only after redaction; never key on raw employee identifiers; encrypt at rest; TTL and legal hold; right-to-erasure deletes by key prefix; log cache_key_hash not plaintext.

**Org Scale Patterns:** Central policy service consumed by all AI tools; forbidden to bypass with per-team Redis without taxonomy.

**Rollout Priority:** Week 0–1: design lanes before any cross-user cache writes

**Makes Sense Verdict:** strong_yes

**Makes Sense Rationale:** Without this model, cross-user caching is unacceptable for regulated enterprises; with it, Tier 3 and gated Tier 1 become deployable.

#### Sources

**Primary Sources**

- [vCache verified semantic cache](https://arxiv.org/abs/2502.03771)
- [Portkey semantic threshold guidance](https://portkey.ai/blog/semantic-caching-thresholds/)

#### Notes

*Fields omitted or deferred due to uncertainty:* `official_url`.

---

## Multi-tier reference architecture

*Claude-proposed stack (normalization → exact → semantic → retrieval → provider KV); how tiers compose, invalidate, and write back.*

#### Basic Info

**Name:** Multi-tier reference architecture

**Category:** Architecture

#### Exists today

**Already Exists:** partial_fragment

**Existence Evidence:** Each tier has independent products (Redis, Qdrant, GPTCache, LMCache, provider APIs). Introl and ZeroEntropy document multi-tier prefix+semantic patterns in 2025. No single vendor bundles all five tiers with unified invalidation.

**Gap Vs Vision:** Unified write-back to all tiers async, single doc_corpus_version invalidating T1-T3 together, and cross-tool gateway enforcement.

#### Technical

**Summary:** Composable pipeline: Tier 0 normalize → T1 exact → T2 semantic answer → T3 retrieval → T4 prefix KV → LLM; async populate allowed tiers on miss.

**How It Works:** Request flows cheapest-first. Misses fall through. Response worker writes to tiers permitted by classification. Invalidation: model change busts all; corpus_version busts T1-T3; prefix break busts T4 only.

**Integration Points:** Ingress gateway, RAG service, vector DB, Redis, inference engine, message queue for write-back and audit.

**Correctness Risks:** Tier ordering wrong (semantic before retrieval) wastes money. Writing personal answers to org lane.

#### Economics and impact

**Cost Latency Impact:** Stacking tiers compounds hit probability; T3+T4 often dominate RAG savings with lower risk than T2 alone.

**Environmental Impact:** Multi-tier maximizes compute avoidance per request.

#### Enterprise fit

**Cross User Sharing:** org_wide_with_guards — per-tier policy

**Pii And Compliance Controls:** Per-tier write matrix: T3 org-wide ok with version keys; T2 requires scrub+lane; T4 only if prefix has no user-specific bytes.

**Org Scale Patterns:** One architecture diagram, many deployables; shared observability dashboard for hit rate by tier and lane.

**Rollout Priority:** Design all tiers; ship T3+T4 first, then T1, then T2

**Makes Sense Verdict:** strong_yes

**Makes Sense Rationale:** Matches industry direction and user clarification; integration is the product.

#### Sources

**Primary Sources**

- [Prompt caching infrastructure guide](https://introl.com/blog/prompt-caching-infrastructure-llm-cost-latency-reduction-guide-2025)
- [ZeroEntropy prompt caching concepts](https://zeroentropy.dev/concepts/prompt-caching/)

#### Notes

*Fields omitted or deferred due to uncertainty:* `official_url`.

---

## Tier 0 query normalization

*Deterministic keys, hashing, embedding order, pitfalls (locale, PII, attachments).*

#### Basic Info

**Name:** Tier 0 query normalization

**Category:** Architecture

#### Exists today

**Already Exists:** partial_fragment

**Existence Evidence:** Exact caches implicitly normalize in some gateways; GPTCache and blogs recommend normalization for hit rate. DLP/NER scrubbing is enterprise-standard but not part of cache libraries by default.

**Gap Vs Vision:** Coupled normalize+classify+route-to-lane as mandatory pre-cache step for cross-user keys.

#### Technical

**Summary:** Pre-cache hygiene: lowercase, whitespace, punctuation rules, optional stemming; SHA-256 for Tier 1; embedding for Tier 2/3 after scrub.

**How It Works:** Pipeline: raw query → locale rules → PII detect/redact → optional attachment strip → hash string + embed vector. Order: hash check before embed to save embedding cost on exact hits.

**Integration Points:** First hop in gateway or RAG API; shared library for all internal AI tools.

**Correctness Risks:** Over-aggressive normalization merges distinct intents; under-normalization splits hits. Redaction alters meaning for legal queries.

#### Economics and impact

**Cost Latency Impact:** Hash nearly free; embedding costs tokens/API—defer until T1 miss. Scrub adds 10-50ms depending on DLP.

#### Enterprise fit

**Cross User Sharing:** org_wide_with_guards — output of Tier 0 feeds only approved lanes

**Pii And Compliance Controls:** Block or downgrade to user-private lane when PII detectors fire; never org-cache raw prompts with emails/SSN/names.

**Org Scale Patterns:** Single normalization spec versioned (norm_v3) included in cache keys.

**Rollout Priority:** Week 1 — prerequisite for safe T1 and cross-user keys

**Makes Sense Verdict:** strong_yes

**Makes Sense Rationale:** Cheap, mandatory for cross-user exact cache and compliance.

#### Sources

**Primary Sources**

- [GPTCache semantic cache design](https://github.com/zilliztech/gptcache)

#### Notes

*Fields omitted or deferred due to uncertainty:* `official_url`, `environmental_impact`.

---

## Tier 1 exact hash cache

*Redis/exact-match patterns, TTL vs version tags, org-wide key namespaces.*

#### Basic Info

**Name:** Tier 1 exact hash cache

**Category:** Architecture

**Official Url:** https://redis.io/docs/latest/develop/ai/redisvl/user_guide/langcache_semantic_cache/

#### Exists today

**Already Exists:** full_product

**Existence Evidence:** Redis, Portkey simple cache, LiteLLM redis cache, LangChain RedisCache—all production. Sub-millisecond GET latency typical.

**Gap Vs Vision:** Org namespaces with clearance and corpus_version in key; central FAQ allowlist; no raw-user-keyed entries in org pool.

#### Technical

**Summary:** Key = hash(normalized_query + lane + corpus_version + model_id); value = response metadata and text; TTL or version-based expiry.

**How It Works:** SHA-256 or similar on normalized string. Redis GET; on miss continue pipeline. Invalidate on corpus_version or model bump. Hit counter for analytics.

**Integration Points:** Redis/Valkey cluster shared by gateway; optional per-region replicas.

**Correctness Risks:** Low for exact match if normalization stable. Stale FAQ if version tag omitted.

#### Economics and impact

**Cost Latency Impact:** ~100µs–2ms latency; saves full LLM cost on hit. Hit rates highest on IT/HR FAQs (10-40% of traffic in repetitive orgs—estimate, workload-dependent).

**Environmental Impact:** High savings per hit—no GPU for cached answer.

#### Enterprise fit

**Cross User Sharing:** org_wide_static_only — for scrubbed FAQ lane; else same_tenant_only

**Pii And Compliance Controls:** Only cache if post-Tier-0 classification allows org:faq lane; key must not include user id.

**Org Scale Patterns:** Redis cluster with key prefix org:{id}:lane:faq:v{corpus}:sha256(...)

**Rollout Priority:** Month 2 — after log analysis identifies top exact repeats

**Makes Sense Verdict:** yes_with_caveats

**Makes Sense Rationale:** Easy win for FAQ traffic cross-user; limited value for paraphrased enterprise questions without Tier 2/3.

#### Sources

**Primary Sources**

- [Portkey simple cache docs](https://docs.portkey.ai/docs/product/ai-gateway/cache-simple-and-semantic)
- [LangChain Redis cache](https://docs.langchain.com/oss/python/integrations/caches/redis_llm_caching)

---

## Tier 2 semantic response cache

*Vector similarity caches, thresholds, false positives, verified caches (vCache).*

#### Basic Info

**Name:** Tier 2 semantic response cache

**Category:** Architecture

**Official Url:** https://arxiv.org/abs/2502.03771

#### Exists today

**Already Exists:** partial_fragment

**Existence Evidence:** GPTCache, Portkey semantic (enterprise), LiteLLM redis-semantic/qdrant-semantic, Redis LangCache. vCache adds per-entry thresholds and error bounds (research/productionizing). Portkey cites ~0.95 similarity and 99% accuracy targets on large traffic.

**Gap Vs Vision:** Cross-user answer store with lane policy, vCache-style guarantees, and prohibition on open-ended HR/legal/coding lanes org-wide.

#### Technical

**Summary:** Store query embedding + full model response; ANN lookup; return if similarity > threshold (often 0.95-0.97 for enterprise).

**How It Works:** On miss: generate answer, async embed query, upsert vector DB with metadata (lane, corpus_version, model). On hit: return cached response if similarity and policy checks pass. Staleness: reject if doc_corpus_version mismatch.

**Integration Points:** Qdrant/Milvus/Pinecone/Redis vector; embedding API; gateway or GPTCache in app.

**Correctness Risks:** False positives—wrong answer confidently. Static global thresholds suboptimal (vCache paper). Cross-user leakage if personal context embedded in cached query.

#### Economics and impact

**Cost Latency Impact:** Embedding cost on miss (~23ms cited in benchmarks) vs seconds for LLM. Hit saves output tokens and latency. Threshold too low increases errors; too low hit rate.

**Environmental Impact:** Strong operational savings when hits are safe and frequent.

#### Enterprise fit

**Cross User Sharing:** org_wide_with_guards — FAQ lane only by default; user-private otherwise

**Pii And Compliance Controls:** Never org-cache raw prompts; scrub before embed; optional secondary verifier on hits; separate indexes per sensitivity tier.

**Org Scale Patterns:** Gateway-enforced semantic mode per route; coding chat routes disable org-wide semantic.

**Rollout Priority:** Month 3+ — after T3/T4/T1 and safety model proven

**Makes Sense Verdict:** yes_with_caveats

**Makes Sense Rationale:** High ROI on repetitive low-risk queries; unacceptable as default org-wide without governance.

#### Sources

**Primary Sources**

- [vCache paper](https://arxiv.org/abs/2502.03771)
- [GPTCache](https://github.com/zilliztech/gptcache)
- [Portkey semantic caching](https://docs.portkey.ai/docs/product/ai-gateway/cache-simple-and-semantic)

---

## Tier 3 RAG retrieval cache

*Caching embeddings + chunk IDs + filters; doc-corpus versioning; overlap with chunk-KV research.*

#### Basic Info

**Name:** Tier 3 RAG retrieval cache

**Category:** Architecture

#### Exists today

**Already Exists:** partial_fragment

**Existence Evidence:** DIY pattern documented in RAG blogs; not a named feature in most gateways. Research: TurboRAG, CacheBlend, Cache-Craft precompute/reuse chunk KV and retrieval state. LMCache ecosystem for KV reuse adjacent to retrieval.

**Gap Vs Vision:** First-class product feature: hash(embed_bytes + filter + top_k + corpus_version + clearance) → chunk_ids with gateway integration and cross-user defaults on.

#### Technical

**Summary:** Cache the expensive retrieval step—embedding query, vector search, top-K chunk IDs/scores—not necessarily the final natural language answer.

**How It Works:** Key includes query embedding fingerprint (or hash of normalized text used for embed), retrieval filters, k, corpus_version, clearance. Value: chunk_ids, scores, optional chunk text hashes. On hit: skip Qdrant ANN; assemble prompt; still run generation (allows per-user question suffix). Invalidate when corpus_version changes.

**Integration Points:** RAG service between embed and LLM; Redis for hot keys; ties to document CMS version API.

**Correctness Risks:** Lower than T2—users get fresh answers from same evidence. Wrong chunks if embed similar but intent differs—mitigate with stricter key or re-rank on hit.

#### Economics and impact

**Cost Latency Impact:** Eliminates duplicate ANN and chunk fetch for N analysts on same contract section—often large in enterprise RAG. Embedding still needed unless query text hash hits.

**Environmental Impact:** Reduces embed API calls and vector DB load; generation still runs.

#### Enterprise fit

**Cross User Sharing:** org_wide_with_guards — best cross-user tier when keyed by corpus+clearance not user

**Pii And Compliance Controls:** Do not store user text in key; clearance in key; retrieval filters enforce ABAC; no chunk from restricted docs in shared entry.

**Org Scale Patterns:** Shared Redis layer in front of Qdrant for all RAG apps; metrics on retrieval hit rate.

**Rollout Priority:** Week 1–2 — highest priority per architecture review

**Makes Sense Verdict:** strong_yes

**Makes Sense Rationale:** Core fit for thousands of users searching same docs; safest major cross-user win.

#### Sources

**Primary Sources**

- [TurboRAG EMNLP 2025](https://aclanthology.org/anthology-files/anthology-files/pdf/emnlp/2025.emnlp-main.334.pdf)
- [Cache-Craft SIGMOD 2025](https://skejriwal44.github.io/docs/CacheCraft_SIGMOD_2025.pdf)

#### Notes

*Fields omitted or deferred due to uncertainty:* `official_url`.

---

## Tier 4 provider prefix KV cache

*Anthropic/OpenAI/Google prompt caching; prefix structure for RAG; limits and billing.*

#### Basic Info

**Name:** Tier 4 provider prefix KV cache

**Category:** Architecture

**Official Url:** https://github.com/anthropics/skills/blob/main/skills/claude-api/shared/prompt-caching.md

#### Exists today

**Already Exists:** full_product

**Existence Evidence:** Anthropic cache_control ephemeral (5m TTL, 1h option); OpenAI and Google analogous features. LMCache for self-hosted cross-request KV. Requires byte-identical prefix; min token thresholds (e.g. 1024 Sonnet).

**Gap Vs Vision:** Cross-user only when many users share identical assembled prefix (same system + same retrieved bundle). Org must standardize prompt assembly across tools.

#### Technical

**Summary:** Provider or inference engine reuses KV states for identical leading tokens; user query must be suffix; structure [system][retrieved context][user query].

**How It Works:** Mark cache_control on last block of shared prefix. cache_read_input_tokens billed ~10% of input. Writes cost premium (~125%). Breakpoints (up to 4 on Anthropic) for layered invalidation. Model switch invalidates.

**Integration Points:** API client libraries; prompt templates in RAG; vLLM+LMCache for on-prem.

**Correctness Risks:** Single byte change invalidates prefix. Timestamps in system prompt kill hits. User-specific text before shared context prevents cross-user benefit.

#### Economics and impact

**Cost Latency Impact:** 25-35% total cost reduction possible when large prefix reused (production reports); 80-90% on cached input token portion. Latency drops on prefill skip.

**Environmental Impact:** Major GPU/API energy reduction on cache reads.

#### Enterprise fit

**Cross User Sharing:** org_wide_static_only — when prefix identical for all users in cohort

**Pii And Compliance Controls:** Never put PII in cached prefix; user message after breakpoint; audit cache_read tokens per request.

**Org Scale Patterns:** Shared prompt templates; retrieved bundle hash in observability; warm cache for popular doc clusters.

**Rollout Priority:** Week 3–4 — prompt audit and cache_control markers

**Makes Sense Verdict:** strong_yes

**Makes Sense Rationale:** Free/low-integration win for API users; complements but does not replace cross-user semantic/retrieval tiers.

#### Sources

**Primary Sources**

- [Anthropic prompt caching skill](https://github.com/anthropics/skills/blob/main/skills/claude-api/shared/prompt-caching.md)
- [LMCache paper](https://arxiv.org/pdf/2510.09665)

---

## GPTCache

*Zilliz library-level semantic cache; modules, backends, LangChain integration.*

#### Basic Info

**Name:** GPTCache

**Category:** Products and OSS

**Official Url:** https://github.com/zilliztech/gptcache

#### Exists today

**Already Exists:** full_product

**Existence Evidence:** Open-source Zilliz project; LangChain/LlamaIndex integrations; pluggable embedders, vector stores (Milvus, FAISS, Redis, Qdrant), SQLite/Postgres response store. Active ecosystem though maintenance varies.

**Gap Vs Vision:** Library per app—not org gateway with IAM lanes. Teams must implement cross-user policy themselves.

#### Technical

**Summary:** Python semantic cache framework: embed query, similarity search, return stored LLM response on match.

**How It Works:** Modular: embedding function, vector store, similarity evaluator, cache storage, optional pre/post processors. Configurable threshold and eviction.

**Integration Points:** Application code or LangChain set_llm_cache; can back with Qdrant matching org stack.

**Correctness Risks:** DIY thresholds; no built-in corpus versioning or clearance; false positive rate team-owned.

#### Economics and impact

**Cost Latency Impact:** Documented 2-10x faster on hits vs OpenAI round-trip in project materials; depends on embed model choice.

**Environmental Impact:** Reduces API calls on hits.

#### Enterprise fit

**Cross User Sharing:** same_tenant_only — unless app wraps with org key schema

**Pii And Compliance Controls:** Not built-in; must wrap writes with scrubbing and lane keys.

**Org Scale Patterns:** Multiple services each running GPTCache → fragmented; prefer gateway unless RAG-specific Tier 3 logic here.

**Rollout Priority:** Optional for RAG service Tier 2 prototype

**Makes Sense Verdict:** yes_with_caveats

**Makes Sense Rationale:** Good for controlled pilots; not sufficient alone for enterprise-wide compliance story.

#### Sources

**Primary Sources**

- [GPTCache GitHub](https://github.com/zilliztech/gptcache)

---

## LiteLLM proxy caching

*Gateway exact + redis-semantic + qdrant-semantic; Redis Stack requirements.*

#### Basic Info

**Name:** LiteLLM proxy caching

**Category:** Products and OSS

**Official Url:** https://docs.litellm.ai/docs/proxy/caching

#### Exists today

**Already Exists:** full_product

**Existence Evidence:** Supports in-memory, disk, Redis, S3, GCS; redis-semantic and qdrant-semantic with similarity_threshold; Redis Stack/RediSearch required for semantic (common ops friction). Redis+Qdrant recipe from Redis developer relations.

**Gap Vs Vision:** No native retrieval-tier or clearance keys; cross-user safe only with config discipline and external policy layer.

#### Technical

**Summary:** OpenAI-compatible proxy caching all org LLM traffic—exact and semantic at ingress.

**How It Works:** config.yaml litellm_settings.cache=true; cache_params type redis|redis-semantic|qdrant-semantic; optional TTL and namespace.

**Integration Points:** Central proxy for chatbots, IDE plugins pointing to proxy, cost tracking.

**Correctness Risks:** Semantic threshold 0.8 default in docs may be too loose for enterprise; shared cache without namespace leaks across envs.

#### Economics and impact

**Cost Latency Impact:** Org-wide hit rate aggregation possible; one place to measure savings.

**Environmental Impact:** Centralized reduction of duplicate calls.

#### Enterprise fit

**Cross User Sharing:** org_wide_with_guards — requires custom key namespace + route rules

**Pii And Compliance Controls:** Add gateway hook for scrub/classify before cache; separate Redis DB per sensitivity.

**Org Scale Patterns:** Single LiteLLM deployment HA pair; Redis cluster backend.

**Rollout Priority:** Week 2–4 for gateway + Redis exact; semantic after policy

**Makes Sense Verdict:** strong_yes

**Makes Sense Rationale:** Best OSS fit for multi-tool org entry point per tool-discovery; pair with custom Tier 3.

#### Sources

**Primary Sources**

- [LiteLLM caching docs](https://docs.litellm.ai/docs/proxy/caching)
- [Redis LiteLLM recipe](https://redis.io/blog/scale-your-llm-gateway/)

---

## Portkey AI gateway

*Enterprise simple + semantic cache, observability, threshold philosophy.*

#### Basic Info

**Name:** Portkey AI gateway

**Category:** Products and OSS

**Official Url:** https://docs.portkey.ai/docs/product/ai-gateway/cache-simple-and-semantic

#### Exists today

**Already Exists:** full_product

**Existence Evidence:** Simple cache all plans; semantic enterprise with Milvus/Pinecone; SEMANTIC_CACHE_SIMILARITY_THRESHOLD default 0.95; analytics on hit rate and cost savings; customer claims of $500K+ savings at scale.

**Gap Vs Vision:** Semantic cache enterprise-only; no retrieval-tier; cross-user compliance is customer-configured not opinionated lanes.

#### Technical

**Summary:** Managed/self-hosted AI gateway with exact and semantic caching plus observability and guardrails.

**How It Works:** Per-request cache mode simple|semantic; env vars for embed provider and vector DB; internal threshold tuning marketed at 99% accuracy on validated traffic.

**Integration Points:** Drop-in OpenAI-compatible endpoint; virtual keys; audit logs.

**Correctness Risks:** Opaque threshold—less control than vCache DIY; vendor lock-in for semantic plane.

#### Economics and impact

**Cost Latency Impact:** Strong for teams wanting managed ops; semantic needs vector DB cost.

**Environmental Impact:** Indirect via reduced LLM calls.

#### Enterprise fit

**Cross User Sharing:** org_wide_with_guards — shared gateway cache pool per deployment

**Pii And Compliance Controls:** Guardrails PII filters exist; must configure not to semantic-cache sensitive routes.

**Org Scale Patterns:** SOC2/HIPAA options; good for regulated buyers preferring vendor ops.

**Rollout Priority:** Alternative to LiteLLM if budget for enterprise

**Makes Sense Verdict:** yes_with_caveats

**Makes Sense Rationale:** Strong buy path if self-hosting Redis Stack is undesirable; still need Tier 3 in RAG.

#### Sources

**Primary Sources**

- [Portkey cache docs](https://docs.portkey.ai/docs/product/ai-gateway/cache-simple-and-semantic)
- [Portkey semantic thresholds blog](https://portkey.ai/blog/semantic-caching-thresholds/)

---

## Redis LangCache and langchain-redis

*RedisSemanticCache, managed LangCache, org-distributed cache backing.*

#### Basic Info

**Name:** Redis LangCache and langchain-redis

**Category:** Products and OSS

**Official Url:** https://redis.io/docs/latest/develop/ai/redisvl/user_guide/langcache_semantic_cache/

#### Exists today

**Already Exists:** full_product

**Existence Evidence:** langchain-redis: RedisCache, RedisSemanticCache (Redis Stack), LangCacheSemanticCache managed API. Redis positions LangCache as managed semantic cache with server-side embeddings.

**Gap Vs Vision:** Cache backend not full org policy layer; LangChain-centric vs all coding tools unless proxied.

#### Technical

**Summary:** Redis-backed exact and semantic LLM caches with optional fully managed LangCache service.

**How It Works:** RedisSemanticCache: client embeds, RediSearch vector index. LangCache: cache_id + api_key, server-side embed, distance_threshold on check.

**Integration Points:** LangChain apps; can sit behind custom gateway wrapping same Redis keys.

**Correctness Risks:** Redis Stack module missing breaks semantic (common LiteLLM issue). Managed LangCache less control over embed model.

#### Economics and impact

**Cost Latency Impact:** Sub-ms vector search cited in industry posts; managed service adds vendor fee.

**Environmental Impact:** Standard cache benefits.

#### Enterprise fit

**Cross User Sharing:** org_wide_with_guards — shared Redis with key prefixes

**Pii And Compliance Controls:** Use Redis ACLs + key taxonomy; LangCache attributes for pre-configured filters only.

**Org Scale Patterns:** Enterprise Redis cluster many teams already operate; LangCache if avoid ops.

**Rollout Priority:** Backend choice for LiteLLM redis-semantic or LangChain services

**Makes Sense Verdict:** yes_with_caveats

**Makes Sense Rationale:** Natural store for T1 and T2 if already Redis-heavy; pair with gateway for non-LangChain tools.

#### Sources

**Primary Sources**

- [LangCache user guide](https://redis.io/docs/latest/develop/ai/redisvl/user_guide/langcache_semantic_cache/)
- [langchain-redis](https://github.com/langchain-ai/langchain-redis)

---

## LMCache and distributed KV reuse

*Cross-node KV, PD disaggregation, Momento integration; inference-layer caching.*

#### Basic Info

**Name:** LMCache and distributed KV reuse

**Category:** Products and OSS

**Official Url:** https://arxiv.org/pdf/2510.09665

#### Exists today

**Already Exists:** full_product

**Existence Evidence:** LMCache OSS widely adopted for enterprise KV layer; CPU offload, hierarchical storage, PD disaggregation; Momento integration reports >50% TTFT reduction on cold start with distributed cache. Complements vLLM/SGLang.

**Gap Vs Vision:** Inference-layer KV reuse across requests/nodes—not semantic cross-user answer cache. Helps when prefix identical (including shared RAG context), not paraphrased queries.

#### Technical

**Summary:** Treats KV cache as first-class reusable object across machines and storage tiers for self-hosted LLMs.

**How It Works:** Store/move KV blocks; prefix matching; integrate with paged attention engines; optional remote storage (S3 tiering with Momento MAX).

**Integration Points:** vLLM, SGLang, on-prem GPU clusters; not Claude API unless hybrid architecture.

**Correctness Risks:** Chunk ordering and cross-attention issues similar to CacheBlend research when naively concatenating KVs.

#### Economics and impact

**Cost Latency Impact:** Significant throughput and TTFT gains in cited deployments; storage and network costs.

**Environmental Impact:** GreenCache paper: KV storage has embodied carbon; net benefit when hit rate high and CI high.

#### Enterprise fit

**Cross User Sharing:** org_wide_static_only — when different users share exact same context bytes

**Pii And Compliance Controls:** KV blocks may contain attention state derived from private text—treat shared KV as sensitive as source prefix; isolate by tenant on GPU cluster.

**Org Scale Patterns:** Platform team running internal model serving; pairs with Tier 4 prompt design.

**Rollout Priority:** If self-hosting LLMs; parallel to API prompt caching

**Makes Sense Verdict:** yes_with_caveats

**Makes Sense Rationale:** Essential for on-prem inference scale; orthogonal to semantic org cache for API-only shops.

#### Sources

**Primary Sources**

- [LMCache arXiv](https://arxiv.org/pdf/2510.09665)
- [Momento LMCache blog](https://www.gomomento.com/blog/reduce-ttft-by-50-with-lmcache-momento/)

---

## RAG chunk KV research

*TurboRAG, CacheBlend, Cache-Craft, CacheClip, KVLink, SmartCache, RAGCache.*

#### Basic Info

**Name:** RAG chunk KV research

**Category:** Research

**Official Url:** https://arxiv.org/html/2510.10129v2

#### Exists today

**Already Exists:** research_only

**Existence Evidence:** TurboRAG (precomputed chunk KV, 9.4x TTFT); CacheBlend/LMCache (partial KV recompute); Cache-Craft (chunk-cache manager, 51% less redundant compute vs prefix); CacheClip, KVLink, SmartCache (NeurIPS 2025). Production adoption partial via LMCache lineage.

**Gap Vs Vision:** Academic systems lack enterprise compliance lanes; inform Tier 3/4 engineering not buy-ready org product.

#### Technical

**Summary:** Research on reusing per-chunk KV states and retrieval results instead of full prefill per query.

**How It Works:** Offline precompute KV per passage; online stitch/reorder/recompute subset for cross-chunk attention; selective token recompute (CacheClip) or positional re-encoding (KVLink).

**Integration Points:** Future RAG inference engines; LMCache codebase for CacheBlend.

**Correctness Risks:** Naive KV concat drops quality; systems add recompute or fine-tuning to recover.

#### Economics and impact

**Cost Latency Impact:** 2-9x TTFT improvements in papers; throughput 1.6-5x in Cache-Craft production-style evals.

**Environmental Impact:** Large GPU savings if deployed at scale.

#### Enterprise fit

**Cross User Sharing:** org_wide_with_guards — chunk KV tied to public corpus chunks not user text

**Pii And Compliance Controls:** Only precompute KV for approved corpus chunks; never from user-uploaded ephemeral context.

**Org Scale Patterns:** Watch LMCache/CacheBlend for productionizable Tier 3+4 merge.

**Rollout Priority:** Monitor 6-12mo; implement simple retrieval cache now

**Makes Sense Verdict:** yes_with_caveats

**Makes Sense Rationale:** Validates Tier 3 priority; full chunk-KV reuse is engineering-heavy for v1.

#### Sources

**Primary Sources**

- [CacheClip](https://arxiv.org/html/2510.10129v2)
- [TurboRAG](https://aclanthology.org/anthology-files/anthology-files/pdf/emnlp/2025.emnlp-main.334.pdf)
- [SmartCache NeurIPS 2025](https://neurips.cc/virtual/2025/poster/116287)

---

## Carbon and sustainability

*Operational vs embodied carbon (GreenCache); when caching helps the environment.*

#### Basic Info

**Name:** Carbon and sustainability

**Category:** Impact

**Official Url:** https://arxiv.org/html/2505.23970v2

#### Exists today

**Already Exists:** research_only

**Existence Evidence:** GreenCache (Cache Your Prompt When It's Green): operational carbon down from avoided compute; embodied carbon from SSD cache storage; 12-25% net carbon reduction in evaluated scenarios with adaptive sizing.

**Gap Vs Vision:** No mainstream gateway exposes carbon-aware cache sizing; org should track tokens avoided not only dollars.

#### Technical

**Summary:** Caching reduces inference energy; large persistent KV/semantic stores add storage manufacturing emissions—net benefit depends on hit rate, cache size, grid carbon intensity.

**How It Works:** GreenCache resizes cache based on load and carbon intensity (CI); high CI favors larger cache; low CI favors smaller cache to limit embodied cost.

**Integration Points:** Platform SRE, sustainability reporting, LMCache storage tier choices.

#### Economics and impact

**Cost Latency Impact:** Aligned with cost savings—fewer tokens computed.

**Environmental Impact:** Cross-user caching multiplies avoided compute per stored entry; measure tokens_saved and estimate kg CO2e via grid factors.

#### Enterprise fit

**Cross User Sharing:** org_wide_with_guards — more users per entry improves carbon amortization

**Pii And Compliance Controls:** N/A to carbon; don't skip compliance for green claims.

**Org Scale Patterns:** Report cache hit rate alongside estimated emissions avoided in ESG dashboards.

**Rollout Priority:** Ongoing metrics after cache live

**Makes Sense Verdict:** yes_with_caveats

**Makes Sense Rationale:** Supports business case beyond cost; quantify after deployment.

#### Sources

**Primary Sources**

- [GreenCache paper](https://arxiv.org/html/2505.23970v2)

#### Notes

*Fields omitted or deferred due to uncertainty:* `correctness_risks`.

---

## Enterprise governance and risks

*Staleness, compliance, PII in shared cache, audit logs, multi-tenant isolation.*

#### Basic Info

**Name:** Enterprise governance and risks

**Category:** Governance

#### Exists today

**Already Exists:** partial_fragment

**Existence Evidence:** Gateways offer audit logs, RBAC, PII guardrails (Portkey, etc.). GDPR erasure and SOC2 are organizational processes—not cache-specific products. Semantic cache false positives documented in GPTCache benchmarks and vCache paper.

**Gap Vs Vision:** Unified governance plane for all tiers and tools with prohibited cross-user answer sharing by default.

#### Technical

**Summary:** Risk register for org-wide LLM caching: staleness, leakage, regulatory, model drift, insider data in coding assistants.

**How It Works:** Policies: classification mandatory, retention limits, incident response for bad cache hit, periodic cache purge on corpus update, red team paraphrase tests near semantic threshold.

**Integration Points:** Legal, security, IAM, DLP, SIEM, model risk management.

**Correctness Risks:** Highest: Tier 2 cross-user; medium: Tier 3 wrong chunks; lower: Tier 1 stale FAQ.

#### Economics and impact

**Cost Latency Impact:** Governance overhead small vs breach or wrong contract advice cost.

#### Enterprise fit

**Cross User Sharing:** org_wide_with_guards — default deny, explicit allow per route

**Pii And Compliance Controls:** Data minimization in cache values; encryption; access logs; DPIA before org-wide semantic; regional residency for Redis.

**Org Scale Patterns:** Cache governance board; align with existing records retention; separate prod/stage cache namespaces.

**Rollout Priority:** Week 0 parallel with architecture

**Makes Sense Verdict:** strong_yes

**Makes Sense Rationale:** Enabler for allowed cross-user reuse; not optional for regulated orgs.

#### Sources

**Primary Sources**

- [vCache correctness](https://arxiv.org/abs/2502.03771)
- [Portkey governance features](https://portkey.ai/features/ai-gateway)

#### Notes

*Fields omitted or deferred due to uncertainty:* `official_url`, `environmental_impact`.

---

## Build vs buy and rollout priority

*Does a unified "distributed prompt cache" product exist; recommended ship order for RAG platforms.*

#### Basic Info

**Name:** Build vs buy and rollout priority

**Category:** Strategy

#### Exists today

**Already Exists:** partial_fragment

**Existence Evidence:** Buy: Portkey/LiteLLM gateway caches, Redis LangCache. Build: Tier 3 retrieval keys, lane policy, normalization. No unified 'distributed prompt cache' SKU found in 2025-2026 market scan.

**Gap Vs Vision:** The product is integration + policy + Tier 3, not a new algorithm.

#### Technical

**Summary:** Recommended sequence for enterprise RAG with thousands of users and compliance needs.

**How It Works:** Phase 0: lanes + DLP. Phase 1 (wk1-2): Tier 3 retrieval cache + metrics. Phase 2 (wk3-4): Tier 4 prompt structure + provider cache_control. Phase 3 (mo2): Tier 1 exact FAQ via gateway Redis. Phase 4 (mo3+): Tier 2 semantic on faq lane only. Self-host: add LMCache if internal models.

**Integration Points:** LiteLLM or Portkey + Qdrant + Redis + corpus version service.

**Correctness Risks:** Skipping phases and enabling org-wide semantic first.

#### Economics and impact

**Cost Latency Impact:** Early phases capture majority of low-risk savings.

**Environmental Impact:** Tracks cost phase—report after Phase 1.

#### Enterprise fit

**Cross User Sharing:** org_wide_with_guards — phased widen lanes as proven

**Pii And Compliance Controls:** Gate each phase on security sign-off for cross-user writes.

**Org Scale Patterns:** Central platform team owns schema; product teams consume via gateway.

**Rollout Priority:** See how_it_works phases

**Makes Sense Verdict:** strong_yes

**Makes Sense Rationale:** Build-vs-buy split is clear; buy gateway+Redis, build Tier3+policy.

#### Sources

**Primary Sources**

- [LiteLLM caching](https://docs.litellm.ai/docs/proxy/caching)
- [Tool discovery synthesis (internal Phase 1)](https://github.com/zilliztech/gptcache)

#### Notes

*Fields omitted or deferred due to uncertainty:* `official_url`.

---

## Appendix: Validator

Re-validate Phase 2 artifacts:

```bash
python3 ~/.cursor/skills/deep-research/scripts/validate_json.py \
  -f research/fields.yaml \
  -j research/results/*.json
```
