from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

from prism_cache.models import CacheContext, CacheLane, Sensitivity, Tier0Result

_NORM_VERSION = "v1"

# Lightweight PII patterns — replace with enterprise DLP hook in production.
_PII_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b(?:employee|emp)\s*#?\s*\d+\b", re.I), "[EMP_ID]"),
)


def normalize_query(text: str) -> str:
    """Tier 0: lowercase, NFKC, collapse whitespace, strip outer punctuation."""
    text = unicodedata.normalize("NFKC", text.strip())
    text = text.lower()
    text = re.sub(r"[^\w\s'@./-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def scrub_pii(text: str) -> tuple[str, bool]:
    """Redact common PII patterns. Returns (scrubbed_text, pii_detected)."""
    scrubbed = text
    detected = False
    for pattern, replacement in _PII_PATTERNS:
        if pattern.search(scrubbed):
            detected = True
            scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed, detected


def hash_query(text: str) -> str:
    payload = f"{_NORM_VERSION}:{text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def classify_lane(
    *,
    requested_lane: CacheLane,
    pii_detected: bool,
    sensitivity: Sensitivity,
    route_hint: str | None = None,
) -> CacheLane:
    """Downgrade lane when PII or high sensitivity would unsafe cross-user reuse."""
    if pii_detected or sensitivity == Sensitivity.HIGH:
        return CacheLane.USER_PRIVATE
    if route_hint == "coding":
        return CacheLane.USER_PRIVATE
    if requested_lane == CacheLane.ORG_STATIC and sensitivity == Sensitivity.MEDIUM:
        return CacheLane.TEAM
    return requested_lane


def process_tier0(
    query: str,
    *,
    requested_lane: CacheLane = CacheLane.ORG_STATIC,
    sensitivity: Sensitivity = Sensitivity.LOW,
    route_hint: str | None = None,
) -> Tier0Result:
    normalized = normalize_query(query)
    scrubbed, pii_detected = scrub_pii(normalized)
    lane = classify_lane(
        requested_lane=requested_lane,
        pii_detected=pii_detected,
        sensitivity=sensitivity,
        route_hint=route_hint,
    )
    blocked_shared = lane == CacheLane.USER_PRIVATE and requested_lane != CacheLane.USER_PRIVATE
    return Tier0Result(
        normalized_query=scrubbed,
        query_hash=hash_query(scrubbed),
        lane=lane,
        sensitivity=sensitivity,
        pii_detected=pii_detected,
        blocked_shared_write=blocked_shared,
    )


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))
