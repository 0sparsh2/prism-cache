"""Tests for Gemini cache usage parsing used by gemini_cache_probe."""

from prism_cache.prefix_metrics import PrefixCacheMetricsRegistry, PrefixCacheUsage


def test_gemini_explicit_cache_usage_shape():
    """Documented Gemini generateContent usageMetadata after cache hit."""
    usage = PrefixCacheUsage.from_gemini(
        {
            "promptTokenCount": 2060,
            "candidatesTokenCount": 22,
            "cachedContentTokenCount": 2048,
        }
    )
    assert usage.cache_read_input_tokens == 2048
    assert usage.had_cache_read

    reg = PrefixCacheMetricsRegistry()
    reg.record(usage, model_id="gemini-2.5-flash-lite", prefix_fingerprint="fp1")
    snap = reg.snapshot()["totals"]
    assert snap["cache_read_hits"] == 1
    assert snap["cache_read_input_tokens"] == 2048
