from pathlib import Path

from prism_cache.litellm_config import build_litellm_config
from prism_cache.settings import load_settings


def test_load_settings_and_routes():
    root = Path(__file__).resolve().parents[1]
    settings = load_settings(root / "config" / "prism.example.yaml")
    assert settings.org_id == "demo-corp"
    assert settings.routes is not None
    coding = settings.routes.resolve("coding-assistant")
    assert coding.tier1_enabled is False


def test_litellm_config_structure():
    cfg = build_litellm_config(redis_url="redis://localhost:6379/0")
    assert cfg["litellm_settings"]["cache"] is True
    assert cfg["litellm_settings"]["cache_params"]["namespace"] == "prism:litellm"
    assert len(cfg["model_list"]) >= 2
