"""PRISM-Cache — Prompt Reuse & Inference Sharing Mesh."""

from prism_cache.factory import create_pipeline, create_production_pipeline
from prism_cache.lmcache_integration import (
    VllmLmcacheLaunchSpec,
    build_vllm_spec,
    kv_transfer_config_json,
)
from prism_cache.litellm_client import LiteLLMClient, load_dotenv
from prism_cache.models import CacheContext, CacheLane, CacheTier, RetrievalHit, Sensitivity
from prism_cache.pipeline import FaqAnswerResult, PrismConfig, PrismPipeline, RagPromptBundle
from prism_cache.prefix_metrics import PrefixCacheUsage
from prism_cache.prompt_audit import PromptAuditResult, audit_assembled, audit_shared_prefix
from prism_cache.routes import RouteRegistry, RouteRule, default_routes
from prism_cache.settings import PrismSettings, load_settings, parse_settings
from prism_cache.tier4 import AssembledPrompt, assemble_rag_prompt, anthropic_request_body

__all__ = [
    "AssembledPrompt",
    "CacheContext",
    "CacheLane",
    "CacheTier",
    "create_pipeline",
    "create_production_pipeline",
    "build_vllm_spec",
    "kv_transfer_config_json",
    "VllmLmcacheLaunchSpec",
    "FaqAnswerResult",
    "LiteLLMClient",
    "load_dotenv",
    "PrefixCacheUsage",
    "PrismConfig",
    "PrismPipeline",
    "PrismSettings",
    "PromptAuditResult",
    "RagPromptBundle",
    "RetrievalHit",
    "RouteRegistry",
    "RouteRule",
    "Sensitivity",
    "anthropic_request_body",
    "assemble_rag_prompt",
    "audit_assembled",
    "audit_shared_prefix",
    "default_routes",
    "load_settings",
    "parse_settings",
]

__version__ = "0.5.0"
