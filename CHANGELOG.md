# Changelog

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
