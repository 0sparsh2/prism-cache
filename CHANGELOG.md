# Changelog

## [0.6.2] — 2026-05-29

### Fixed

- FAQ demo continues on LiteLLM timeout/quota errors; `make run-all` no longer aborts

### Changed

- CI: offline eval gate + org scenario smoke (10 users)
- `docs/OPERATIONS.md` — full runbook with all Makefile targets

## [0.6.1] — 2026-05-29

### Added

- **`gateway/litellm.full.yaml`** — NIM + Gemini + vLLM route + PRISM callback
- **`examples/phase_f_vllm_chat.py`** — vLLM health probe and optional live chat
- **`docker-compose.vllm-lmcache-cluster.yml`** — multi-node LMCache scaffold
- Makefile: `gateway-full`, `check-vllm`, `phase-f-up`, `demo-phase-f-chat`; expanded `run-demos`

## [0.6.0] — 2026-05-29

### Added

- **`eval --live`** / `make eval-live` — live Gemini-embed near-intent + safe paraphrase rows
- **`proxy_enforcement.py`** — route → lane resolution, audit JSONL, LiteLLM metadata injection
- **`gateway/prism_callback.py`** + `litellm.prism.yaml` — LiteLLM pre-call hook prototype
- `examples/proxy_lane_demo.py`, `make gateway-prism`, `make demo-proxy`

### Changed

- ROADMAP: eval-live and proxy hook marked done; Phase F GPU fleet remains open

## [0.5.2] — 2026-05-29

### Added

- **Org scenario**: `examples/org_scenario_tier3.py`, `docs/ORG_SCENARIO.md`, `make scenario-org`
- **`make run-all-cold`** — `FLUSHDB` before demos for miss→write→hit arc
- Proxy enforcement section in `docs/GATEWAY.md`

### Changed

- ROADMAP next steps: `eval --live`, proxy lane hooks, Phase F fleet

## [0.5.1] — 2026-05-29

### Added

- **`eval/`** governance benchmarks: Tier 3 retrieval equivalence, lane isolation, policy denials, Tier 2 near-intent FPR
- `make eval`, `make run-all`, `make demo-production-live`; `docs/BENCHMARKS.md`
- CI gate: `tests/test_benchmarks.py` (50 tests)

### Changed

- README repositioned: Tier 3 hero path, eval badge, governance-first positioning
- `.env.example`: default `REDIS_URL` for production demos

## [0.5.0] — 2026-05-29

### Added

- **Production**: `config/prism.production.yaml`, `docker-compose.prod.yml`, `docs/PRODUCTION.md`
- `create_production_pipeline()`, `examples/production_app.py`
- **Phase F scaffold**: `lmcache_integration.py`, `docker-compose.vllm-lmcache.yml`, `examples/phase_f_rag_vllm.py`

## [0.4.0] — 2026-05-29

### Added

- **Tier 2** semantic FAQ cache (`tier2.py`) with policy gates and red-team tests
- **LiteLLM integration** (`litellm_client.py`, `gateway/litellm.{multi,gemini,nim}.yaml`)
- Examples: `tier2_faq_demo.py`, `faq_litellm_gemini.py`, `gemini_cache_probe.py`
- **Gemini** `from_gemini()` prefix metrics; **factory** `create_pipeline()` with Redis backends
- `.env.example`, Makefile dev targets, `docs/LMCACHE.md` (Phase F placeholder)

### Changed

- `faq_answer()` flow: Tier 1 exact → Tier 2 semantic → generate
- `internal-faq-bot` route enables `tier2_enabled`
- Version bump; README/ROADMAP/GATEWAY docs updated

## [0.3.0]

- Tier 1 FAQ exact cache, routes, LiteLLM gateway config, settings loader

## [0.1.0]

- Tier 0–4 core, Tier 3 retrieval cache, research artifacts
