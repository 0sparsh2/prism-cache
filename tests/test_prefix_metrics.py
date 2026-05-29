from prism_cache.prefix_metrics import PrefixCacheMetricsRegistry, PrefixCacheUsage


def test_record_anthropic_usage_and_dashboard():
    reg = PrefixCacheMetricsRegistry()
    write = PrefixCacheUsage(
        input_tokens=5000,
        output_tokens=200,
        cache_creation_input_tokens=4000,
        cache_read_input_tokens=0,
    )
    read = PrefixCacheUsage(
        input_tokens=5200,
        output_tokens=180,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=4000,
    )
    reg.record(write, model_id="claude-sonnet", prefix_fingerprint="abc")
    reg.record(read, model_id="claude-sonnet", prefix_fingerprint="abc")
    reg.record(read, model_id="claude-sonnet", prefix_fingerprint="abc")

    snap = reg.snapshot()
    assert snap["totals"]["requests"] == 3
    assert snap["totals"]["cache_read_hits"] == 2
    assert snap["totals"]["cache_write_events"] == 1

    text = reg.dashboard_text()
    assert "Tier 4" in text
    assert "Cache read hits" in text


def test_from_gemini_usage_metadata():
    usage = PrefixCacheUsage.from_gemini(
        {
            "promptTokenCount": 5000,
            "candidatesTokenCount": 120,
            "cachedContentTokenCount": 4096,
        }
    )
    assert usage.input_tokens == 5000
    assert usage.output_tokens == 120
    assert usage.cache_read_input_tokens == 4096
    assert usage.had_cache_read

    sdk_usage = PrefixCacheUsage.from_gemini(
        {
            "prompt_token_count": 3000,
            "candidates_token_count": 80,
            "cached_content_token_count": 2048,
        }
    )
    assert sdk_usage.cache_read_input_tokens == 2048
