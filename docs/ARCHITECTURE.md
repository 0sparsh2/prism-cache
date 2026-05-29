# Architecture: PRIME-CACHE

**P**rompt **R**euse **I**n **M**ulti-tier **E**nterprise — builder-oriented view of the cache plane.

For evidence, sources, and per-component analysis, see [`research/report.md`](../research/report.md).

## Problem

Thousands of employees use LLMs through different surfaces (chatbots, coding assistants, internal doc search). They repeat the same **intent** with different wording. **Per-user KV / prefix cache** only helps the same person when the prompt prefix is byte-identical—it does not help the next employee.

The goal is **cross-user reuse** with **compliance**: no PII leakage, no wrong answers from over-aggressive semantic matching.

## Cache lanes (governance first)

| Lane | Cross-user | Typical content |
|------|------------|-----------------|
| `user-private` | Never | Chat history, HR/legal one-offs, proprietary code snippets |
| `team` | Same clearance + corpus | Program-specific RAG, project docs |
| `org-static` | Yes, scrubbed | IT FAQ, published policies, shared retrieval keys |

Every cache key should include: `org_id`, `lane`, `sensitivity`, `corpus_version`, `model_id` (where applicable).

## Tier model

```
Request
  │
  ▼
┌─────────────────────────────────────┐
│ Tier 0  Normalize · scrub · classify │
└─────────────────────────────────────┘
  │
  ▼
┌─────────┐   miss    ┌─────────┐   miss    ┌─────────┐
│ Tier 1  │──────────▶│ Tier 2  │──────────▶│ Tier 3  │
│ Exact   │           │ Semantic│           │Retrieve │
│ hash    │           │ answer  │           │ chunks  │
└─────────┘           └─────────┘           └─────────┘
  │ hit                 │ hit                 │ hit
  ▼                     ▼                     ▼
 return               return              RAG + generate
                                              │
                                              ▼
                                        ┌─────────┐
                                        │ Tier 4  │
                                        │ Prefix  │
                                        │ KV      │
                                        └─────────┘
                                              │
                                              ▼
                                         Full LLM
                                              │
                                              ▼
                                    Async write-back
                                    (allowed tiers only)
```

| Tier | Reuses | Cross-user default | Risk |
|------|--------|-------------------|------|
| **0** | Nothing (prep) | N/A | Bad scrub → store PII |
| **1** | Full answer, exact text | FAQ lane only | Stale FAQ |
| **2** | Full answer, similar meaning | FAQ lane only | False positive, leakage |
| **3** | Retrieval results (chunk IDs) | **Recommended** | Wrong chunks if key too loose |
| **4** | Model KV on identical prefix | When prefix is shared | Broken if user text in prefix |

### Tier 3 key (reference)

```
cache_key = H(
  lane,
  corpus_version,
  clearance,
  embed_model_id,
  top_k,
  filter_dict,
  query_embedding_or_normalized_text_hash
)
value = { chunk_ids[], scores[], optional text_hashes[] }
```

Invalidate when `corpus_version` changes—not only TTL.

### Tier 4 prompt layout (RAG)

```
[ system prompt — stable, cacheable ]
[ retrieved context — stable per retrieval hit ]
[ user query — variable, NOT cached ]
```

Use provider `cache_control` / equivalent on the last block of the shared prefix.

## What we are building

**PRIME-CACHE** = gateway + policy engine + Tier 3 service + observability—not a single Redis plugin.

See [ROADMAP.md](../ROADMAP.md) for implementation phases.
