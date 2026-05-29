"""
LiteLLM CustomLogger — attach PRISM route/lane metadata at pre-call.

Enable in gateway YAML (from repo root, venv with litellm[proxy]):

  litellm_settings:
    callbacks: prism_callback.prism_handler

Run:
  PYTHONPATH=src:. litellm --config gateway/litellm.multi.yaml --port 4000

Clients send:
  x-prism-route: program-rag
  x-prism-user-id: employee-0042
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from litellm.integrations.custom_logger import CustomLogger  # noqa: E402

from prism_cache.proxy_enforcement import (  # noqa: E402
    inject_litellm_metadata,
    resolve_from_headers,
)

logger = logging.getLogger("prism.gateway")


class PrismLaneCallback(CustomLogger):
    """Resolve x-prism-route → lane metadata before upstream LLM call."""

    async def async_pre_call_hook(
        self,
        user_api_key_dict: dict,
        cache: Any,
        data: dict,
        call_type: str,
    ) -> dict:
        headers = {}
        proxy_req = data.get("proxy_server_request") or {}
        if isinstance(proxy_req, dict):
            raw_headers = proxy_req.get("headers") or {}
            if isinstance(raw_headers, dict):
                headers = {str(k): str(v) for k, v in raw_headers.items()}

        ctx = resolve_from_headers(headers)
        data = inject_litellm_metadata(data, ctx)
        logger.info(
            "prism_route=%s prism_lane=%s call_type=%s user=%s",
            ctx.route_name,
            ctx.lane.value,
            call_type,
            ctx.user_id or "-",
        )
        return data


prism_handler = PrismLaneCallback()
