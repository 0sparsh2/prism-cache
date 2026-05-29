# Security review — cross-user cache write

Use this checklist before enabling **shared cache writes** for a new route or lane.

## Route metadata

| Field | Value |
|-------|--------|
| Application / route name | |
| Owner team | |
| Default lane | `user-private` / `team` / `org-static` |
| Tiers enabled | Tier 1 / 2 / 3 / 4 |
| Corpus ID + version source | |

## Data classification

- [ ] Prompts may contain PII (names, IDs, health, financial)? If yes → `user-private` only.
- [ ] Cached **values** contain user-specific narrative (not just public doc IDs)?
- [ ] Coding route — repo secrets possible? → `user-private` + no Tier 2 org-wide.
- [ ] Legal/HR one-off queries blocked from `org-static`?

## Tier-specific

### Tier 3 (retrieval)

- [ ] Cache key includes `corpus_version`, `clearance`, `lane` — not raw user text.
- [ ] Invalidation tested on doc publish pipeline.
- [ ] Cross-user hit tested: User B does not receive User A's private query text.

### Tier 2 (semantic answer)

- [ ] Approved only for FAQ / low sensitivity.
- [ ] Similarity threshold ≥ 0.95 documented.
- [ ] Red-team paraphrase set run; false positive rate acceptable. → `make eval` ([BENCHMARKS.md](BENCHMARKS.md))

### Tier 1 (exact)

- [ ] Only post–Tier 0 scrubbed queries in `org-static` lane.

## Compliance

- [ ] Retention / TTL aligned with records policy.
- [ ] Encryption at rest for Redis.
- [ ] Audit logs: cache key hash, lane, tier, hit/miss — not full PII prompts.
- [ ] DPIA or equivalent signed off.

## Sign-off

| Role | Name | Date |
|------|------|------|
| Security | | |
| Legal / Privacy | | |
| Platform owner | | |
