# PRISM eval benchmarks

Reproducible proof artifacts for **governance-aware organizational reuse** — not generic semantic-cache hit rates.

These workloads answer what infra buyers ask in the first ten seconds:

1. **Tier 3** — do paraphrased queries reuse the same retrieval candidates across users?
2. **Policy** — are unsafe writes denied by lane?
3. **Tier 2** — what is the near-intent false-positive rate at the default threshold?
4. **Isolation** — does `user-private` content leak into `org-static` lookups?

## Run locally

```bash
make eval          # offline proof (CI gate)
make eval-live     # + Gemini embed near-intent table (needs gateway)
make test          # includes offline eval gate in CI
```

Or:

```bash
python -m eval.run_benchmarks
```

## Latest results (deterministic, offline)

| Benchmark | Metric | Value | Target | Pass |
|-----------|--------|-------|--------|------|
| tier3_retrieval_equivalence | precision | 1.0000 | = 1.0 | yes |
| cross_user_tier3 | hit_rate | 0.9800 | > 0.9 | yes |
| lane_isolation | cross_lane_leak_rate | 0.0000 | = 0.0 | yes |
| policy_governance | denial_accuracy | 1.0000 | = 1.0 | yes |
| tier2_near_intent | false_positive_rate | 0.0000 | = 0.0 | yes |
| tier3_near_intent_overlap | chunk_overlap_rate | 1.0000 | report only | yes |

Machine-readable: [`eval/results/latest.json`](../eval/results/latest.json). Regenerate: `make eval`.

## How to read each benchmark

### Tier 3 retrieval equivalence

**Question:** On a cache miss path, does User B’s paraphrase return the **same chunk IDs** User A would get from a full retrieval?

This is the **infra-grade** metric for governed reuse. It does not claim final-answer correctness (your generator still owns synthesis risk).

### Cross-user Tier 3 hit rate

Synthetic org traffic: 50 users × 10 unique policy queries. Expect vector DB calls ≈ unique queries and hit rate >90% on repeats.

### Lane isolation

Alice’s PII-heavy query stored under `user-private` must **not** appear when Bob queries under `org-static`.

### Policy governance

Tier 2 writes denied on `team` lane and PII-downgraded prompts — expected denial reasons must match policy code.

### Tier 2 near-intent false positive rate

Adversarial pairs (cancel/pause, terminate/suspend, etc.) at threshold **0.95** with deterministic embedder. Target: **0% false hits**.

Uses `hash_bag_embed` for reproducibility without API keys. Live embedding FPR:

```bash
make eval-live     # writes eval/results/latest_live.json
```

Live rows (`tier2_near_intent_live`, `tier2_safe_paraphrase_live`) are **report-only** — they document production conservatism under real embeddings and do not gate CI.

Example live run (Gemini `gemini-embed`, threshold 0.95):

| Row | Value | Notes |
|-----|-------|-------|
| tier2_near_intent_live | FPR 0.0 | max_sim=0.746 on cancel/pause pairs — below threshold |
| tier2_safe_paraphrase_live | avg_sim 0.85 | “login password” paraphrase — also below 0.95 (matches live FAQ carol MISS) |

### Tier 3 near-intent chunk overlap (informational)

Same adjacent-intent pairs may retrieve **overlapping** chunks. This is expected and documents **synthesis risk** — reuse of retrieval candidates, not wrong cached sentences.

Mitigations: topic gates, stricter filters, human review lanes — see [ARCHITECTURE.md](ARCHITECTURE.md).

## What this is not

- Not a Percona-style cost/latency marketing benchmark (add separately with live LLM traffic).
- Not proof of proxy-level lane enforcement (library-only today) — see [ROADMAP.md](../ROADMAP.md).
- Not streaming cache behavior — out of scope for v1 eval.

## Files

```text
eval/
├── benchmarks.py       # workload definitions
├── run_benchmarks.py   # CLI + JSON output
└── results/latest.json # last run (gitignored if regenerated in CI only)
```
