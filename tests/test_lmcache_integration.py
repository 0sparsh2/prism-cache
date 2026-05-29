import json

from prism_cache.lmcache_integration import (
    build_vllm_spec,
    kv_transfer_config_json,
    render_lmcache_config_yaml,
)
from prism_cache.tier4 import assemble_rag_prompt


def test_kv_transfer_config():
    cfg = json.loads(kv_transfer_config_json())
    assert cfg["kv_connector"] == "LMCacheConnectorV1"
    assert cfg["kv_role"] == "kv_both"


def test_build_vllm_spec_from_prompt():
    prompt = assemble_rag_prompt(
        system_prompt="You are helpful.",
        chunks=[],
        user_query="hello",
        resolve_chunk_text=lambda _: "",
    )
    spec = build_vllm_spec(prompt, model="meta-llama/Llama-3.1-8B-Instruct")
    assert spec.prefix_fingerprint == prompt.prefix_fingerprint
    assert "LMCacheConnectorV1" in spec.kv_transfer_config_json


def test_render_lmcache_config():
    yaml_text = render_lmcache_config_yaml(remote_url="lm://host:65432")
    assert "remote_url" in yaml_text
    assert "chunk_size" in yaml_text
