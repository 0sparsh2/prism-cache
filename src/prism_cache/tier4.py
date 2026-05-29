from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from prism_cache.models import ChunkResult

ProviderName = Literal["anthropic", "openai"]

ChunkTextResolver = Callable[[str], str]


@dataclass(frozen=True)
class AssembledPrompt:
    """RAG prompt with stable cacheable prefix and variable user suffix."""

    system_prompt: str
    context_block: str
    user_query: str
    prefix_text: str
    prefix_fingerprint: str
    sorted_chunk_ids: tuple[str, ...]
    anthropic_system: list[dict[str, Any]]
    anthropic_messages: list[dict[str, Any]]
    openai_messages: list[dict[str, Any]]
    cache_breakpoint: str = "last_context_block"


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def format_context_block(chunks: list[ChunkResult], resolve_text: ChunkTextResolver) -> str:
    """Deterministic chunk order (by chunk_id) for cross-user prefix cache hits."""
    ordered = sorted(chunks, key=lambda c: c.chunk_id)
    parts: list[str] = []
    for chunk in ordered:
        body = resolve_text(chunk.chunk_id)
        parts.append(f"<document id=\"{chunk.chunk_id}\">\n{body}\n</document>")
    return "\n\n".join(parts)


def assemble_rag_prompt(
    *,
    system_prompt: str,
    chunks: list[ChunkResult],
    user_query: str,
    resolve_chunk_text: ChunkTextResolver,
    provider: ProviderName = "anthropic",
    cache_ttl: Literal["ephemeral", "ephemeral_1h"] = "ephemeral",
) -> AssembledPrompt:
    """
    Build [system][retrieved context][user query] with cache markers on shared prefix.

    User query is always the uncached suffix. Context order is sorted by chunk_id so
    two users with the same Tier 3 hit produce an identical provider prefix.
    """
    context_block = format_context_block(chunks, resolve_chunk_text)
    prefix_text = f"{system_prompt.rstrip()}\n\n---\n\n{context_block}"
    fingerprint = _fingerprint(prefix_text)
    cache_control = {"type": cache_ttl}

    anthropic_system = [
        {
            "type": "text",
            "text": system_prompt.rstrip(),
        }
    ]
    anthropic_messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": context_block,
                    "cache_control": cache_control,
                },
                {
                    "type": "text",
                    "text": user_query.strip(),
                },
            ],
        }
    ]

    openai_messages = [
        {"role": "system", "content": system_prompt.rstrip()},
        {
            "role": "user",
            "content": f"{context_block}\n\n---\n\nQuestion: {user_query.strip()}",
        },
    ]

    return AssembledPrompt(
        system_prompt=system_prompt.rstrip(),
        context_block=context_block,
        user_query=user_query.strip(),
        prefix_text=prefix_text,
        prefix_fingerprint=fingerprint,
        sorted_chunk_ids=tuple(c.chunk_id for c in sorted(chunks, key=lambda c: c.chunk_id)),
        anthropic_system=anthropic_system,
        anthropic_messages=anthropic_messages,
        openai_messages=openai_messages,
    )


def anthropic_request_body(
    assembled: AssembledPrompt,
    *,
    model: str,
    max_tokens: int = 1024,
    **kwargs: Any,
) -> dict[str, Any]:
    """Ready-to-send Anthropic Messages API body with cache_control on shared prefix."""
    return {
        "model": model,
        "max_tokens": max_tokens,
        "system": assembled.anthropic_system,
        "messages": assembled.anthropic_messages,
        **kwargs,
    }
