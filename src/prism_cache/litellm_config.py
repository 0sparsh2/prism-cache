from __future__ import annotations

from typing import Any


def build_litellm_config(
    *,
    redis_url: str = "redis://localhost:6379/0",
    openai_api_key_env: str = "OPENAI_API_KEY",
    anthropic_api_key_env: str = "ANTHROPIC_API_KEY",
    models: list[str] | None = None,
    cache_ttl: int = 3600,
) -> dict[str, Any]:
    """
    LiteLLM proxy config skeleton for org-wide LLM entry + Redis exact cache.

    PRISM Tier 1/3 caches live in the application layer; LiteLLM cache complements
    identical proxy payloads. Point all internal tools at this proxy base URL.
    """
    models = models or ["gpt-4o-mini", "claude-sonnet-4-20250514"]
    model_list = []
    for name in models:
        if name.startswith("claude"):
            model_list.append(
                {
                    "model_name": name,
                    "litellm_params": {
                        "model": name,
                        "api_key": f"os.environ/{anthropic_api_key_env}",
                    },
                }
            )
        else:
            model_list.append(
                {
                    "model_name": name,
                    "litellm_params": {
                        "model": name,
                        "api_key": f"os.environ/{openai_api_key_env}",
                    },
                }
            )

    return {
        "model_list": model_list,
        "litellm_settings": {
            "cache": True,
            "cache_params": {
                "type": "redis",
                "host": _redis_host(redis_url),
                "port": _redis_port(redis_url),
                "password": "os.environ/REDIS_PASSWORD",
                "namespace": "prism:litellm",
                "default_in_redis_ttl": cache_ttl,
            },
            "set_verbose": False,
        },
        "general_settings": {
            "master_key": "os.environ/LITELLM_MASTER_KEY",
        },
    }


def _redis_host(redis_url: str) -> str:
    # redis://host:port/db
    without_scheme = redis_url.split("://", 1)[-1]
    host_port = without_scheme.split("/", 1)[0]
    return host_port.rsplit("@", 1)[-1].split(":")[0]


def _redis_port(redis_url: str) -> str:
    without_scheme = redis_url.split("://", 1)[-1]
    host_port = without_scheme.split("/", 1)[0]
    host_port = host_port.rsplit("@", 1)[-1]
    if ":" in host_port:
        return host_port.split(":")[1]
    return "6379"


def render_litellm_yaml(config: dict[str, Any]) -> str:
    import yaml

    return yaml.dump(config, default_flow_style=False, sort_keys=False)
