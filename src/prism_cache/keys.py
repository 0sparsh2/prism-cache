from __future__ import annotations

import hashlib
from typing import Any

from prism_cache.models import CacheContext, CacheLane, CacheTier
from prism_cache.tier0 import stable_json
from prism_cache.tier0 import stable_json


def build_cache_key(
    ctx: CacheContext,
    tier: CacheTier,
    *,
    parts: dict[str, Any],
) -> str:
    """Deterministic Redis key: prism:{org}:{lane}:{tier}:{hash}."""
    material = {
        "org_id": ctx.org_id,
        "lane": ctx.lane.value,
        "sensitivity": ctx.sensitivity.value,
        "corpus_version": ctx.corpus_version,
        "clearance": ctx.clearance,
        "model_id": ctx.model_id,
        "tier": tier.value,
        "user_id": ctx.user_id if ctx.lane == CacheLane.USER_PRIVATE else None,
        "team_id": ctx.team_id if ctx.lane == CacheLane.TEAM else None,
        **parts,
    }
    digest = hashlib.sha256(stable_json(material).encode("utf-8")).hexdigest()
    return f"prism:{ctx.org_id}:{ctx.lane.value}:{tier.value}:{digest[:32]}"


def build_tier1_key_parts(*, query_hash: str, model_id: str) -> dict[str, str]:
    return {"query_hash": query_hash, "model_id": model_id or "default"}


def build_tier3_key_parts(
    *,
    query_hash: str,
    embed_model_id: str,
    top_k: int,
    filters: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "query_hash": query_hash,
        "embed_model_id": embed_model_id,
        "top_k": top_k,
        "filters": filters or {},
    }


def build_tier2_bucket_key(ctx: CacheContext, *, model_id: str) -> str:
    """Namespace for semantic answer entries (many queries per bucket)."""
    material = {
        "org_id": ctx.org_id,
        "lane": ctx.lane.value,
        "sensitivity": ctx.sensitivity.value,
        "corpus_version": ctx.corpus_version,
        "clearance": ctx.clearance,
        "model_id": model_id or "default",
        "tier": CacheTier.TIER2.value,
    }
    digest = hashlib.sha256(stable_json(material).encode("utf-8")).hexdigest()
    return f"prism:{ctx.org_id}:{ctx.lane.value}:tier2:{digest[:24]}"
