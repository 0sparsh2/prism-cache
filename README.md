# PRISM-Cache

**prism-cache** — *Prompt Reuse & Inference Sharing Mesh* for the enterprise.

Policy-aware, multi-tier LLM caching: reuse prompts, retrieval, and inference **across users** (chat, RAG, coding tools) without treating compliance as an afterthought.

> Per-user KV cache saves one person’s next turn. **PRISM** saves the *next employee* asking the same thing — when it is safe to share.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Research](https://img.shields.io/badge/docs-research%20report-green)](research/report.md)
[![Roadmap](https://img.shields.io/badge/status-build%20phase-orange)](ROADMAP.md)

---

## What PRISM means

| | |
|---|---|
| **P** | **Prompt** normalization, exact match, semantic similarity |
| **R** | **Reuse** across users, tools, and sessions |
| **I** | **Inference** savings (retrieval, prefix KV, full generation) |
| **S** | **Sharing** mesh — one governed cache plane for the org |
| **M** | **Mesh** of tiers (0–4) and **lanes** (`user-private`, `team`, `org-static`) |

GitHub repo: [`prism-cache`](https://github.com/0sparsh2/prism-cache)

---

## Why this exists

Enterprises run thousands of LLM requests per day across:

- Internal chatbots and copilots  
- Coding assistants (Cursor, Copilot, custom agents)  
- RAG / “search our docs with AI”  

The same questions appear again and again — different people, different wording. **Provider prefix caching** and **session KV cache** do not solve that. You need a **shared cache plane** with:

- **Cross-user reuse** where intent overlaps  
- **Cache lanes** so HR, code, and public FAQ never share one bucket  
- **Version-aware invalidation** when policies and contracts change  

This repository captures **deep research (2025–2026)** on what already exists, what to build, and a **concrete build roadmap** for PRISM-Cache.

---

## The idea in 30 seconds

| Tier | What gets reused | Cross-user? |
|------|------------------|-------------|
| **0** | *(prep)* normalize, scrub PII, pick lane | — |
| **1** | Exact same question → full answer | FAQ lane only |
| **2** | Similar question → full answer | **High risk** — gated |
| **3** | Same doc search → chunk IDs | **Best org-wide win** |
| **4** | Same prompt prefix → KV / cheaper prefill | When prefix is identical |

```text
Query → Tier 0 → T1 exact? → T2 semantic? → T3 retrieval? → T4 prefix KV? → LLM
                                                                    ↓
                                                          async write-back (allowed lanes)
```

Full diagram: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## Research conclusions

| Question | Answer |
|----------|--------|
| Is there one product that does all of this? | **No** — gateways, Redis, GPTCache, LMCache, and cloud prefix cache are **fragments**. |
| Is it worth building? | **Yes** — PRISM is **integration + policy + Tier 3**, not “turn on semantic cache.” |
| Safest cross-user tier | **Tier 3** (retrieval cache keyed by `corpus_version` + clearance) |
| Riskiest cross-user tier | **Tier 2** (full answer semantic cache) |
| Suggested stack | LiteLLM or Portkey + Redis/Qdrant + **custom Tier 3** + provider prefix (Tier 4) |

**Read the full report:** [`research/report.md`](research/report.md) (~17 topics, sources, compliance notes)

---

## Repository layout

```text
prism-cache/
├── README.md                 ← you are here
├── ROADMAP.md                ← implementation checklist (build phase)
├── docs/
│   └── ARCHITECTURE.md       ← tier + lane model for builders
├── research/
│   ├── report.md             ← Phase 3 synthesis
│   ├── outline.yaml          ← research scope
│   ├── fields.yaml           ← JSON schema
│   ├── results/*.json        ← per-topic evidence (Phase 2)
│   └── scripts/              ← validate / regenerate artifacts
└── LICENSE
```

`src/` and runtime code will land in the **build phase** ([ROADMAP.md](ROADMAP.md)).

---

## Cache lanes (compliance)

Before any cross-user **write**, classify the request:

| Lane | Who can read | Example |
|------|----------------|---------|
| `user-private` | Same user only | Personal chat, code with secrets |
| `team` | Same clearance + corpus | Program RAG, project wiki |
| `org-static` | Org-wide (scrubbed) | IT FAQ, published policy retrieval |

**Never** org-cache raw prompts containing PII. **Prefer Tier 3** (which docs were retrieved) over Tier 2 (a full answer written for someone else).

---

## Quick start (research artifacts)

```bash
git clone https://github.com/0sparsh2/prism-cache.git
cd prism-cache

# Optional: validate Phase 2 JSON
python3 -m venv .venv && .venv/bin/pip install pyyaml
.venv/bin/python ~/.cursor/skills/deep-research/scripts/validate_json.py \
  -f research/fields.yaml \
  -j research/results/*.json

# Regenerate report from JSON
.venv/bin/python research/scripts/generate_report.py
```

---

## Build phase (next)

We are moving from research → implementation. Planned order:

1. **Lanes + Tier 0** (normalize, scrub, classify)  
2. **Tier 3** retrieval cache in front of your vector DB  
3. **Tier 4** prompt structure + provider prefix markers  
4. **Gateway** (LiteLLM) + **Tier 1** FAQ exact cache  
5. **Tier 2** semantic — FAQ lane only, after security sign-off  

Track progress in [ROADMAP.md](ROADMAP.md). Contributions welcome once `src/` lands.

---

## Related work

- [GPTCache](https://github.com/zilliztech/gptcache) — library semantic cache  
- [LiteLLM proxy caching](https://docs.litellm.ai/docs/proxy/caching) — gateway exact + semantic  
- [LMCache](https://arxiv.org/pdf/2510.09665) — distributed KV for inference  
- [vCache](https://arxiv.org/abs/2502.03771) — verified semantic thresholds  
- [Anthropic prompt caching](https://github.com/anthropics/skills/blob/main/skills/claude-api/shared/prompt-caching.md) — Tier 4 on Claude API  

---

## Methodology

Research produced with a structured **deep-research** workflow ([Weizhena/Deep-Research-skills](https://github.com/Weizhena/Deep-Research-skills), [RhinoInsight](https://arxiv.org/html/2511.18743v1)): outline → validated JSON per topic → synthesized report.

---

## License

[MIT](LICENSE) — use, fork, and build on it.

---

**PRISM-Cache** · Research complete · **Build phase starting** · Issues and PRs welcome
