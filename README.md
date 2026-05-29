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
├── README.md
├── ROADMAP.md
├── pyproject.toml
├── src/prism_cache/          ← library (v0.4)
├── tests/
├── examples/
├── config/prism.example.yaml
├── gateway/                  ← LiteLLM YAML configs
├── docs/
│   ├── ARCHITECTURE.md
│   ├── BUILD.md
│   ├── GATEWAY.md
│   ├── LMCACHE.md
│   └── SECURITY_REVIEW.md
├── research/                 ← deep-research artifacts
└── LICENSE
```

## Quick start (v0.4)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,gateway,redis]"
cp .env.example .env   # add keys; PRISM_CHAT_MODEL=deepseek-v4-flash if Gemini quota is out

make test
make demo-tier2          # Tier 1 + 2, no API
make redis-up && make gateway   # terminal 2: proxy on :4000
make demo-faq-dry        # or make demo-faq when proxy + keys ready
```

```python
from prism_cache import create_pipeline, LiteLLMClient

pipeline = create_pipeline(config_path="config/prism.example.yaml", use_litellm_embed=True)
client = LiteLLMClient.from_env()
pipeline.faq_answer("how do I reset my login password?", "internal-faq-bot",
                    client.make_generate_fn(), user_id="bob")
```

Guides: [`docs/BUILD.md`](docs/BUILD.md) · [`docs/GATEWAY.md`](docs/GATEWAY.md) · [`docs/OPERATIONS.md`](docs/OPERATIONS.md) · [`CHANGELOG.md`](CHANGELOG.md)

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

## Build phase

**v0.4 shipped:** Tier 0–4 + **Tier 1 FAQ**, **Tier 2 semantic FAQ**, route rules, LiteLLM gateway config.

Next up ([ROADMAP.md](ROADMAP.md)):

1. ~~Phases A–E~~ ✅  
2. **Phase F** — LMCache (optional, self-hosted)  

Track progress in [ROADMAP.md](ROADMAP.md). Contributions welcome.

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

**PRISM-Cache v0.5** · Phases A–F (API + LMCache scaffold) · [Production](docs/PRODUCTION.md)
