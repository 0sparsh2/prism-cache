#!/usr/bin/env python3
"""Generate Phase 3 report.md from outline + results JSON."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTLINE = ROOT / "outline.yaml"
RESULTS = ROOT / "results"
REPORT = ROOT / "report.md"

# Map outline item names to result filenames
NAME_TO_FILE = {
    "Problem and opportunity": "Problem_and_opportunity.json",
    "Cross-user shared cache safety model": "Cross-user_shared_cache_safety_model.json",
    "Multi-tier reference architecture": "Multi-tier_reference_architecture.json",
    "Tier 0 query normalization": "Tier_0_query_normalization.json",
    "Tier 1 exact hash cache": "Tier_1_exact_hash_cache.json",
    "Tier 2 semantic response cache": "Tier_2_semantic_response_cache.json",
    "Tier 3 RAG retrieval cache": "Tier_3_RAG_retrieval_cache.json",
    "Tier 4 provider prefix KV cache": "Tier_4_provider_prefix_KV_cache.json",
    "GPTCache": "GPTCache.json",
    "LiteLLM proxy caching": "LiteLLM_proxy_caching.json",
    "Portkey AI gateway": "Portkey_AI_gateway.json",
    "Redis LangCache and langchain-redis": "Redis_LangCache_and_langchain_redis.json",
    "LMCache and distributed KV reuse": "LMCache_and_distributed_KV_reuse.json",
    "RAG chunk KV research": "RAG_chunk_KV_research.json",
    "Carbon and sustainability": "Carbon_and_sustainability.json",
    "Enterprise governance and risks": "Enterprise_governance_and_risks.json",
    "Build vs buy and rollout priority": "Build_vs_buy_and_rollout_priority.json",
}

SECTIONS = [
    ("Basic Info", ["name", "category", "official_url"]),
    ("Exists today", ["already_exists", "existence_evidence", "gap_vs_vision"]),
    ("Technical", ["summary", "how_it_works", "integration_points", "correctness_risks"]),
    ("Economics and impact", ["cost_latency_impact", "environmental_impact"]),
    (
        "Enterprise fit",
        [
            "cross_user_sharing",
            "pii_and_compliance_controls",
            "org_scale_patterns",
            "rollout_priority",
            "makes_sense_verdict",
            "makes_sense_rationale",
        ],
    ),
    ("Sources", ["primary_sources"]),
]


def slug(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def load_outline_items():
    import yaml

    data = yaml.safe_load(OUTLINE.read_text(encoding="utf-8"))
    return data["topic"], data["items"]


def is_uncertain(data: dict, key: str) -> bool:
    uncertain = data.get("uncertain") or []
    if key in uncertain:
        return True
    val = data.get(key)
    if isinstance(val, str) and "[uncertain]" in val:
        return True
    return False


def fmt_field(key: str, val) -> str:
    label = key.replace("_", " ").title()
    if val is None or val == "":
        return ""
    if isinstance(val, list):
        if not val:
            return ""
        if key == "primary_sources":
            lines = [f"- [{s.get('title', 'Source')}]({s.get('url', '')})" for s in val if isinstance(s, dict)]
            return f"**{label}**\n\n" + "\n".join(lines)
        return f"**{label}:** {val}"
    return f"**{label}:** {val}"


def render_item(data: dict) -> str:
    parts = []
    for section_title, keys in SECTIONS:
        section_bits = []
        for key in keys:
            if is_uncertain(data, key):
                continue
            block = fmt_field(key, data.get(key))
            if block:
                section_bits.append(block)
        if section_bits:
            parts.append(f"#### {section_title}\n\n" + "\n\n".join(section_bits))
    uncertain = data.get("uncertain") or []
    if uncertain:
        parts.append(
            "#### Notes\n\n"
            f"*Fields omitted or deferred due to uncertainty:* {', '.join(f'`{u}`' for u in uncertain)}."
        )
    return "\n\n".join(parts)


def main():
    topic, items = load_outline_items()
    lines = [
        f"# {topic}",
        "",
        "## Methodology",
        "",
        "This report was produced with the **deep-research** workflow (Phase 3 synthesis),",
        "inspired by [Weizhena/Deep-Research-skills](https://github.com/Weizhena/Deep-Research-skills)",
        "and structured evidence gathering aligned with [RhinoInsight](https://arxiv.org/html/2511.18743v1).",
        "",
        "- **Phase 1:** Research outline and field schema (`outline.yaml`, `fields.yaml`).",
        "- **Phase 2:** One validated JSON artifact per item under `results/`, including",
        "  cross-user sharing and PII/compliance controls.",
        "- **Phase 3:** This document — synthesized findings with sources, omitting fields",
        "  marked uncertain in source JSON.",
        "",
        "**Problem framing (clarified):** One organization with thousands of users across",
        "chatbots, coding assistants, and document/RAG search. Per-user KV cache does not help",
        "the next employee. The goal is **cross-user reuse** with **compliance** and **no PII leakage**.",
        "",
        "## Executive summary",
        "",
        "| Finding | Conclusion |",
        "|---------|------------|",
        "| Does a unified product exist? | **No** — fragments (gateways, Redis, GPTCache, LMCache, provider prefix cache). |",
        "| Is the idea viable? | **Yes** — as a **policy-aware multi-tier platform**, not a single semantic switch. |",
        "| Best cross-user tier | **Tier 3 (retrieval cache)** — reuse doc chunks, not personal answers. |",
        "| Highest risk tier | **Tier 2 (semantic full answer)** — false positives and PII leakage across users. |",
        "| Recommended stack | **LiteLLM (or Portkey) + Redis/Qdrant + custom Tier 3 + provider prefix (Tier 4).** |",
        "| Rollout | Lanes/DLP → Tier 3 → Tier 4 → Tier 1 FAQ → Tier 2 (gated) → LMCache if self-hosted. |",
        "",
        "### Request flow (tiers)",
        "",
        "```",
        "User query → Tier 0 normalize/scrub/classify",
        "          → Tier 1 exact hit? → return",
        "          → Tier 2 semantic hit? (guarded lane) → return",
        "          → Tier 3 retrieval hit? → generate with cached chunks",
        "          → Tier 4 prefix KV hit? → cheaper generation",
        "          → full LLM → async write-back to allowed tiers",
        "```",
        "",
        "## Table of contents",
        "",
    ]
    for item in items:
        name = item["name"]
        lines.append(f"- [{name}](#{slug(name)})")
    lines.append("")
    lines.append("---")
    lines.append("")

    for item in items:
        name = item["name"]
        fname = NAME_TO_FILE[name]
        data = json.loads((RESULTS / fname).read_text(encoding="utf-8"))
        lines.append(f"## {name}")
        lines.append("")
        if item.get("description"):
            lines.append(f"*{item['description'].strip()}*")
            lines.append("")
        lines.append(render_item(data))
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Appendix: Validator")
    lines.append("")
    lines.append("Re-validate Phase 2 artifacts:")
    lines.append("")
    lines.append("```bash")
    lines.append("python3 ~/.cursor/skills/deep-research/scripts/validate_json.py \\")
    lines.append("  -f research/fields.yaml \\")
    lines.append("  -j research/results/*.json")
    lines.append("```")
    lines.append("")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
