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
from prism_cache.proxy_enforcement import (
    PRISM_ROUTE_HEADER,
    PRISM_USER_HEADER,
    PrismAuditEvent,
    PrismRequestContext,
    classify_query_lane,
    inject_litellm_metadata,
    resolve_from_headers,
    resolve_route_context,
)
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
    "PrismAuditEvent",
    "PrismRequestContext",
    "PRISM_ROUTE_HEADER",
    "PRISM_USER_HEADER",
    "RouteRegistry",
    "RouteRule",
    "Sensitivity",
    "anthropic_request_body",
    "assemble_rag_prompt",
    "audit_assembled",
    "audit_shared_prefix",
    "classify_query_lane",
    "default_routes",
    "inject_litellm_metadata",
    "load_settings",
    "parse_settings",
    "resolve_from_headers",
    "resolve_route_context",
]

__version__ = "0.6.0"
