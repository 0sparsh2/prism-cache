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
