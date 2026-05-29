from __future__ import annotations

import re
from dataclasses import dataclass, field

from prism_cache.tier4 import AssembledPrompt


@dataclass
class PromptAuditFinding:
    level: str  # error | warning
    code: str
    message: str


@dataclass
class PromptAuditResult:
    ok: bool
    findings: list[PromptAuditFinding] = field(default_factory=list)

    def add(self, level: str, code: str, message: str) -> None:
        self.findings.append(PromptAuditFinding(level=level, code=code, message=message))
        if level == "error":
            self.ok = False


_VOLATILE_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", "timestamp_iso", "ISO timestamp in prompt breaks prefix cache"),
    (r"\b(?:today|now|current time|as of now)\b", "volatile_time", "Time-relative wording in shared prefix"),
    (r"\{\{?\s*(?:user|employee|session)[^}]*\}\}?", "unresolved_placeholder", "Unresolved user/session placeholder"),
    (r"\buser_id\s*[:=]", "user_id_in_prefix", "User identifier in shared prefix"),
)


def audit_shared_prefix(
    *,
    system_prompt: str,
    context_block: str,
    user_query: str,
) -> PromptAuditResult:
    """
    Prompt template audit for Tier 4 prefix caching.

    Validates that volatile or user-specific content stays out of the cacheable prefix.
    """
    result = PromptAuditResult(ok=True)
    shared = f"{system_prompt}\n{context_block}"

    if user_query.strip() and user_query.strip() in system_prompt:
        result.add("error", "query_in_system", "User query appears inside system prompt")

    if user_query.strip() and user_query.strip() in context_block:
        result.add("error", "query_in_context", "User query appears inside retrieved context block")

    for pattern, code, msg in _VOLATILE_PATTERNS:
        if re.search(pattern, shared, re.I):
            result.add("warning", code, msg)

    if not system_prompt.strip():
        result.add("error", "empty_system", "System prompt is empty")

    if not context_block.strip():
        result.add("warning", "empty_context", "Empty context block — prefix cache benefit will be low")

    return result


def audit_assembled(assembled: AssembledPrompt) -> PromptAuditResult:
    return audit_shared_prefix(
        system_prompt=assembled.system_prompt,
        context_block=assembled.context_block,
        user_query=assembled.user_query,
    )
