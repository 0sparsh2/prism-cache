"""
Phase F — LMCache + vLLM integration helpers (self-hosted inference).

Use when PRISM Tier 4 has assembled a stable RAG prefix and you serve the model
with vLLM + LMCache. Does not apply to hosted APIs (Gemini, NIM, OpenAI).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from prism_cache.tier4 import AssembledPrompt

# vLLM 0.6+ / LMCache connector (see docs/LMCACHE.md)
DEFAULT_KV_TRANSFER_CONFIG: dict[str, str] = {
    "kv_connector": "LMCacheConnectorV1",
    "kv_role": "kv_both",
}


@dataclass(frozen=True)
class VllmLmcacheLaunchSpec:
    """Arguments to pass when starting vLLM with LMCache enabled."""

    model: str
    kv_transfer_config_json: str
    lmcache_env: dict[str, str]
    prefix_fingerprint: str
    docker_image: str = "lmcache/vllm-openai:latest"
    extra_cli: tuple[str, ...] = ()

    def vllm_command_tail(self) -> list[str]:
        """CLI args after model name (for docker run / vllm serve)."""
        return [
            "--kv-transfer-config",
            self.kv_transfer_config_json,
            *self.extra_cli,
        ]


def kv_transfer_config_json(
    *,
    connector: str = "LMCacheConnectorV1",
    kv_role: str = "kv_both",
) -> str:
    return json.dumps({"kv_connector": connector, "kv_role": kv_role})


def lmcache_cpu_env(
    *,
    chunk_size: int = 256,
    max_local_cpu_gb: float = 5.0,
    config_file: str | None = None,
) -> dict[str, str]:
    """Environment variables for local CPU LMCache tier (single-node dev)."""
    env = {
        "LMCACHE_CHUNK_SIZE": str(chunk_size),
        "LMCACHE_LOCAL_CPU": "True",
        "LMCACHE_MAX_LOCAL_CPU_SIZE": str(max_local_cpu_gb),
    }
    if config_file:
        env["LMCACHE_CONFIG_FILE"] = config_file
    return env


def build_vllm_spec(
    prompt: AssembledPrompt,
    *,
    model: str,
    config_file: str | None = None,
    max_local_cpu_gb: float = 5.0,
) -> VllmLmcacheLaunchSpec:
    """
    Build vLLM + LMCache launch spec from a PRISM Tier 4 assembled prompt.

    The prefix_fingerprint ties PRISM metrics to LMCache reuse of the same bytes.
    """
    return VllmLmcacheLaunchSpec(
        model=model,
        kv_transfer_config_json=kv_transfer_config_json(),
        lmcache_env=lmcache_cpu_env(
            config_file=config_file,
            max_local_cpu_gb=max_local_cpu_gb,
        ),
        prefix_fingerprint=prompt.prefix_fingerprint,
    )


def openai_messages_for_vllm(prompt: AssembledPrompt) -> list[dict[str, str]]:
    """Map PRISM assembled prompt to OpenAI-style messages for vLLM OpenAI server."""
    return [
        {"role": "system", "content": prompt.system_prompt + "\n\n" + prompt.context_block},
        {"role": "user", "content": prompt.user_query},
    ]


def render_lmcache_config_yaml(
    *,
    chunk_size: int = 256,
    local_cpu: bool = True,
    max_local_cpu_size: float = 5.0,
    remote_url: str | None = None,
) -> str:
    """Minimal LMCache YAML for deploy/lmcache-config.yaml."""
    lines = [
        f"chunk_size: {chunk_size}",
        f"local_cpu: {str(local_cpu).lower()}",
        f"max_local_cpu_size: {max_local_cpu_size}",
    ]
    if remote_url:
        lines.append(f'remote_url: "{remote_url}"')
        lines.append('remote_serde: "cachegen"')
    return "\n".join(lines) + "\n"


def docker_run_example(spec: VllmLmcacheLaunchSpec, *, hf_token_env: str = "HF_TOKEN") -> str:
    """Shell snippet for documentation (not executed)."""
    env_lines = " \\\n  ".join(f'-e {k}={v}' for k, v in spec.lmcache_env.items())
    tail = " ".join(spec.vllm_command_tail())
    return (
        f"docker run --gpus all --network host \\\n"
        f"  -e {hf_token_env}=$HF_TOKEN \\\n"
        f"  {env_lines} \\\n"
        f"  {spec.docker_image} \\\n"
        f"  {spec.model} {tail}"
    )
