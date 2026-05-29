from prism_cache.factory import create_pipeline


def test_create_pipeline_from_config(tmp_path):
    cfg = tmp_path / "prism.yaml"
    cfg.write_text(
        """
org_id: test-org
corpus_id: hb
defaults:
  tier2_similarity_threshold: 0.9
routes:
  internal-faq-bot:
    lane: org-static
    tier1_enabled: true
    tier2_enabled: true
""",
        encoding="utf-8",
    )
    pipeline = create_pipeline(config_path=cfg)
    assert pipeline.config.org_id == "test-org"
    assert pipeline.config.tier2_similarity_threshold == 0.9


def test_create_pipeline_redis_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    pipeline = create_pipeline(config_path=None)
    from prism_cache.tier1 import RedisExactStore

    assert isinstance(pipeline.tier1._store, RedisExactStore)


def test_create_pipeline_redis_url_empty_disables_env(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    pipeline = create_pipeline(config_path=None, redis_url="")
    from prism_cache.tier1 import InMemoryExactStore

    assert isinstance(pipeline.tier1._store, InMemoryExactStore)
