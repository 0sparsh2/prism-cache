# Organizational scenario — 500 employees, handbook RAG

Pilot narrative and **reproducible numbers** for Tier 3 governed reuse at org scale. This is the story infra buyers repeat: not “we cache answers,” but “we skip redundant vector searches across employees under lane policy.”

## Scenario

**Acme Corp** has **500 employees** using an internal handbook RAG bot (`program-rag` route → **`team`** lane). Each employee asks the same **40 paraphrased** questions across four published topics:

| Topic | Example paraphrase |
|-------|-------------------|
| Travel | “how do i get vp approval for international travel?” |
| Expense | “meal receipt rules for expense reports” |
| Security | “when is security awareness training due?” |
| Leave | “how many weeks of paid parental leave?” |

**What PRISM reuses:** chunk IDs from retrieval (Tier 3), keyed by `org_id`, lane, clearance, **`corpus_version`**, and Tier 0 normalized query hash — **not** another employee’s generated answer.

**What PRISM does not claim:** final-answer correctness on near-intent overlap (see [BENCHMARKS.md](BENCHMARKS.md) `tier3_near_intent_overlap`).

## Results (reproducible)

Run locally:

```bash
make scenario-org
# or: python examples/org_scenario_tier3.py --users 500 --vector-latency-ms 50
```

Latest offline run (`--vector-latency-ms 0`, in-memory store):

| Metric | Value |
|--------|-------|
| Employees | 500 |
| Paraphrases per employee | 40 |
| **Total RAG requests** | **20,000** |
| Unique Tier 0 query hashes | 37 (of 40 phrasings; 3 collapse via normalization) |
| **Vector DB calls** | **37** |
| **Tier 3 hit rate** | **99.81%** |
| Vector calls avoided | 19,963 (**99.8%** reduction) |

### Simulated latency (@ 50 ms / vector call)

| Path | Vector time |
|------|-------------|
| Naive (no PRISM) | 20,000 × 50 ms ≈ **1,000 s** (~16.7 min) |
| With PRISM Tier 3 | 37 × 50 ms ≈ **1.9 s** |
| **Estimated savings** | **~998 s** of vector DB / embedding search |

Numbers assume a cold Tier 3 cache; first employee to ask each normalized phrasing pays one miss. All subsequent employees hit the shared retrieval entry.

Machine-readable output: [`eval/results/org_scenario.json`](../eval/results/org_scenario.json).

## Architecture in this scenario

```text
500 employees → program-rag (team lane, corpus_version from CMS)
                    │
                    ▼
              PRISM Tier 0 normalize + classify
                    │
                    ▼
              Tier 3 lookup (Redis in production)
                 hit │ miss
                     │    └──► vector DB (37 calls total)
                     ▼
              Same chunk IDs → RAG prompt → LLM (per user)
```

Cross-user reuse is **safe by construction** relative to Tier 2: you reuse **which documents were retrieved**, not **what someone else was told**.

## Compare to FAQ semantic cache (Tier 2)

| | Tier 3 (this scenario) | Tier 2 FAQ |
|--|------------------------|------------|
| Reuses | Chunk IDs | Full answer text |
| Cross-user default | `team` / `org-static` with policy | `org-static` FAQ only, high threshold |
| Failure mode | Wrong synthesis from shared context | Wrong cached sentence |
| Marketing role | **Lead** | Optional accelerator |

## Production path

With Redis persistence (`make prod-redis`, `REDIS_URL` in `.env`), Tier 3 entries survive process restarts until `corpus_version` bumps invalidate them.

```bash
make prod-redis
make scenario-org   # add --config config/prism.production.yaml when wired
```

## Related

- [BENCHMARKS.md](BENCHMARKS.md) — governance eval gate (`make eval`)
- [GATEWAY.md](GATEWAY.md) — proxy lanes vs naive semantic cache
- [ARCHITECTURE.md](ARCHITECTURE.md) — tier model
