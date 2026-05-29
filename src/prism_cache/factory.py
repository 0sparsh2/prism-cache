from __future__ import annotations

import os
from pathlib import Path

from prism_cache.litellm_client import LiteLLMClient, load_dotenv
from prism_cache.pipeline import PrismConfig, PrismPipeline
from prism_cache.routes import RouteRegistry, default_routes
from prism_cache.settings import PrismSettings, load_settings
from prism_cache.tier1 import InMemoryExactStore, RedisExactStore
from prism_cache.tier2 import EmbedFn, InMemorySemanticStore, RedisSemanticStore, hash_bag_embed
from prism_cache.tier3 import InMemoryRetrievalStore, RedisRetrievalStore


def create_pipeline(
    *,
    config_path: str | Path | None = None,
    env_path: str | Path | None = None,
    redis_url: str | None = None,
    routes: RouteRegistry | None = None,
    tier2_embed: EmbedFn | None = None,
    use_litellm_embed: bool = False,
) -> PrismPipeline:
    """
    Build a PrismPipeline from config file and/or environment.

    Set `redis_url` or `REDIS_URL` for persistent Tier 1/2/3 stores.
    Set `use_litellm_embed=True` (requires proxy + GEMINI_EMBED_MODEL) for production Tier 2 vectors.
    """
    if env_path:
        load_dotenv(str(env_path))
    elif Path(".env").exists():
        load_dotenv(".env")

    settings: PrismSettings | None = None
    if config_path:
        settings = load_settings(config_path)

    redis_url = redis_url if redis_url is not None else os.environ.get("REDIS_URL")
    if redis_url == "":
        redis_url = None
    cfg = settings.to_pipeline_config() if settings else PrismConfig(org_id="demo-corp")
    route_reg = routes or (settings.routes if settings and settings.routes else default_routes())

    exact_store = InMemoryExactStore()
    semantic_store = InMemorySemanticStore()
    retrieval_store = InMemoryRetrievalStore()
    if redis_url:
        prefix = settings.redis if settings else None
        t1 = prefix.tier1_key_prefix if prefix else "prism:t1"
        t2 = prefix.tier2_key_prefix if prefix else "prism:t2"
        t3 = prefix.tier3_key_prefix if prefix else "prism:t3"
        exact_store = RedisExactStore(redis_url, key_prefix=t1)
        semantic_store = RedisSemanticStore(redis_url, key_prefix=t2)
        retrieval_store = RedisRetrievalStore(redis_url, key_prefix=t3)

    embed = tier2_embed
    if embed is None and use_litellm_embed:
        embed = LiteLLMClient.from_env().make_embed_fn()

    return PrismPipeline(
        cfg,
        store=retrieval_store,
        exact_store=exact_store,
        semantic_store=semantic_store,
        routes=route_reg,
        tier2_embed=embed or hash_bag_embed,
        tier1_ttl_seconds=settings.redis.ttl_seconds if settings and settings.redis else None,
    )


def create_production_pipeline(
    *,
    config_path: str | Path | None = None,
    env_path: str | Path | None = None,
    redis_url: str | None = None,
    use_litellm_embed: bool = True,
) -> PrismPipeline:
    """Production defaults: prism.production.yaml + Redis + LiteLLM embeddings."""
    default_cfg = Path(__file__).resolve().parents[2] / "config" / "prism.production.yaml"
    return create_pipeline(
        config_path=config_path or default_cfg,
        env_path=env_path,
        redis_url=redis_url,
        use_litellm_embed=use_litellm_embed,
    )
