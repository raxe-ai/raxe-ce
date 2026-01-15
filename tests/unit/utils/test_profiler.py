"""Tests for performance profiler.

Tests the ScanProfiler and related classes.
"""

from unittest.mock import Mock

import pytest

from raxe.domain.engine.executor import RuleExecutor
from raxe.domain.rules.models import Pattern, Rule, RuleExamples, RuleFamily, RuleMetrics, Severity
from raxe.utils.profiler import LayerProfile, ProfileResult, RuleProfile, ScanProfiler


@pytest.fixture
def test_rules():
    """Create test rules."""
    return [
        Rule(
            rule_id="fast-rule",
            version="1.0.0",
            family=RuleFamily.PI,
            sub_family="test",
            name="Fast Rule",
            description="Fast matching rule",
            severity=Severity.HIGH,
            confidence=0.9,
            patterns=[Pattern(pattern=r"fast", flags=[], timeout=5.0)],
            examples=RuleExamples(),
            metrics=RuleMetrics(),
        ),
        Rule(
            rule_id="slow-rule",
            version="1.0.0",
            family=RuleFamily.PI,
            sub_family="test",
            name="Slow Rule",
            description="Slower matching rule",
            severity=Severity.MEDIUM,
            confidence=0.8,
            patterns=[Pattern(pattern=r"slow.*pattern", flags=[], timeout=5.0)],
            examples=RuleExamples(),
            metrics=RuleMetrics(),
        ),
    ]


def test_profile_scan_basic(test_rules):
    """Test basic scan profiling."""
    executor = RuleExecutor()
    profiler = ScanProfiler(executor, l2_detector=None)

    text = "This is a test text for profiling"

    profile = profiler.profile_scan(text, test_rules, include_l2=False)

    # Basic checks
    assert profile.total_time_ms > 0
    assert profile.text_length == len(text)
    assert profile.l1_profile is not None
    assert profile.l2_profile is None  # L2 disabled
    assert profile.overhead_ms >= 0


def test_layer_profile_properties():
    """Test LayerProfile computed properties."""
    rule_profiles = [
        RuleProfile(
            rule_id="rule-001",
            execution_time_ms=2.0,
            matched=True,
            cache_hit=False,
        ),
        RuleProfile(
            rule_id="rule-002",
            execution_time_ms=0.5,
            matched=False,
            cache_hit=True,
        ),
        RuleProfile(
            rule_id="rule-003",
            execution_time_ms=1.5,
            matched=True,
            cache_hit=False,
        ),
    ]

    layer_profile = LayerProfile(
        layer_name="L1",
        total_time_ms=4.0,
        rule_profiles=rule_profiles,
        cache_hits=1,
        cache_misses=2,
    )

    # Test cache hit rate
    assert layer_profile.cache_hit_rate == pytest.approx(1 / 3)

    # Test average rule time
    assert layer_profile.average_rule_time_ms == pytest.approx(4.0 / 3)

    # Test slowest rules
    slowest = layer_profile.slowest_rules
    assert len(slowest) == 3
    assert slowest[0].rule_id == "rule-001"  # 2.0ms
    assert slowest[1].rule_id == "rule-003"  # 1.5ms
    assert slowest[2].rule_id == "rule-002"  # 0.5ms


def test_profile_result_percentages():
    """Test ProfileResult percentage calculations."""
    l1_profile = LayerProfile(
        layer_name="L1",
        total_time_ms=6.0,
        rule_profiles=[],
        cache_hits=5,
        cache_misses=5,
    )

    l2_profile = LayerProfile(
        layer_name="L2",
        total_time_ms=4.0,
        rule_profiles=[],
        cache_hits=0,
        cache_misses=0,
    )

    profile = ProfileResult(
        total_time_ms=12.0,
        text_length=100,
        l1_profile=l1_profile,
        l2_profile=l2_profile,
        overhead_ms=2.0,
        timestamp="2025-01-01T00:00:00Z",
    )

    # Test percentages
    assert profile.l1_percentage == pytest.approx(50.0)
    assert profile.l2_percentage == pytest.approx(33.33, abs=0.01)
    assert profile.overhead_percentage == pytest.approx(16.67, abs=0.01)


def test_identify_bottlenecks_l1_heavy():
    """Test bottleneck identification when L1 is slow."""
    # Create slow rule profile
    slow_rule = RuleProfile(
        rule_id="slow-rule",
        execution_time_ms=5.0,
        matched=True,
        cache_hit=False,
    )

    l1_profile = LayerProfile(
        layer_name="L1",
        total_time_ms=8.0,
        rule_profiles=[slow_rule],
        cache_hits=2,
        cache_misses=8,  # Low hit rate
    )

    profile = ProfileResult(
        total_time_ms=10.0,
        text_length=100,
        l1_profile=l1_profile,
        l2_profile=None,
        overhead_ms=2.0,
        timestamp="2025-01-01T00:00:00Z",
    )

    bottlenecks = profile.identify_bottlenecks()

    # Should identify L1 as bottleneck (80% of time)
    assert any("L1 detection" in b for b in bottlenecks)

    # Should identify slow rule
    assert any("slow-rule" in b for b in bottlenecks)

    # Should identify low cache hit rate (20%)
    assert any("cache hit rate" in b for b in bottlenecks)


def test_identify_bottlenecks_l2_heavy():
    """Test bottleneck identification when L2 is slow."""
    l1_profile = LayerProfile(
        layer_name="L1",
        total_time_ms=2.0,
        rule_profiles=[],
        cache_hits=8,
        cache_misses=2,
    )

    l2_profile = LayerProfile(
        layer_name="L2",
        total_time_ms=70.0,
        rule_profiles=[],
        cache_hits=0,
        cache_misses=0,
    )

    profile = ProfileResult(
        total_time_ms=100.0,
        text_length=100,
        l1_profile=l1_profile,
        l2_profile=l2_profile,
        overhead_ms=28.0,
        timestamp="2025-01-01T00:00:00Z",
    )

    bottlenecks = profile.identify_bottlenecks()

    # Should identify L2 as bottleneck (70% of time)
    assert any("L2 inference" in b for b in bottlenecks)


def test_get_recommendations_fast_mode():
    """Test recommendations suggest fast mode for slow L2."""
    l1_profile = LayerProfile(
        layer_name="L1",
        total_time_ms=3.0,
        rule_profiles=[],
        cache_hits=5,
        cache_misses=5,
    )

    l2_profile = LayerProfile(
        layer_name="L2",
        total_time_ms=70.0,
        rule_profiles=[],
        cache_hits=0,
        cache_misses=0,
    )

    profile = ProfileResult(
        total_time_ms=100.0,
        text_length=100,
        l1_profile=l1_profile,
        l2_profile=l2_profile,
        overhead_ms=27.0,
        timestamp="2025-01-01T00:00:00Z",
    )

    recommendations = profile.get_recommendations()

    # Should recommend fast mode
    assert any("fast" in r.lower() for r in recommendations)


def test_get_recommendations_excellent_performance():
    """Test recommendations for excellent performance."""
    l1_profile = LayerProfile(
        layer_name="L1",
        total_time_ms=2.0,
        rule_profiles=[],
        cache_hits=10,
        cache_misses=0,
    )

    profile = ProfileResult(
        total_time_ms=2.5,
        text_length=100,
        l1_profile=l1_profile,
        l2_profile=None,
        overhead_ms=0.5,
        timestamp="2025-01-01T00:00:00Z",
    )

    recommendations = profile.get_recommendations()

    # Should say performance is excellent
    assert any("excellent" in r.lower() or "optimized" in r.lower() for r in recommendations)


def test_profiler_with_l2_detector():
    """Test profiler with L2 detector."""
    from raxe.domain.ml.protocol import L2Detector

    executor = RuleExecutor()
    l2_detector = Mock(spec=L2Detector)
    l2_detector.analyze.return_value = None

    profiler = ScanProfiler(executor, l2_detector=l2_detector)

    text = "Test text"
    rules = []

    profile = profiler.profile_scan(text, rules, include_l2=True)

    # L2 should be profiled
    assert profile.l2_profile is not None
    assert profile.l2_profile.layer_name == "L2"
    assert profile.l2_profile.total_time_ms >= 0


def test_profiler_without_l2():
    """Test profiler without L2 detector."""
    executor = RuleExecutor()
    profiler = ScanProfiler(executor, l2_detector=None)

    text = "Test text"
    rules = []

    profile = profiler.profile_scan(text, rules, include_l2=True)

    # L2 should not be profiled
    assert profile.l2_profile is None


def test_profile_cache_heuristic():
    """Test cache hit heuristic (fast rules are likely cached)."""
    executor = RuleExecutor()
    profiler = ScanProfiler(executor, l2_detector=None)

    # Small rule set that should execute quickly
    rules = [
        Rule(
            rule_id="test-rule",
            version="1.0.0",
            family=RuleFamily.PI,
            sub_family="test",
            name="Test Rule",
            description="Test",
            severity=Severity.MEDIUM,
            confidence=0.8,
            patterns=[Pattern(pattern=r"x", flags=[], timeout=5.0)],
            examples=RuleExamples(),
            metrics=RuleMetrics(),
        ),
    ]

    profile = profiler.profile_scan("test", rules, include_l2=False)

    # Should have cache statistics
    assert profile.l1_profile.cache_hits >= 0
    assert profile.l1_profile.cache_misses >= 0


def test_overhead_calculation():
    """Test overhead calculation."""
    l1_profile = LayerProfile(
        layer_name="L1",
        total_time_ms=5.0,
        rule_profiles=[],
        cache_hits=5,
        cache_misses=5,
    )

    # Total time is 10ms, detection is 5ms, so overhead should be 5ms
    profile = ProfileResult(
        total_time_ms=10.0,
        text_length=100,
        l1_profile=l1_profile,
        l2_profile=None,
        overhead_ms=5.0,
        timestamp="2025-01-01T00:00:00Z",
    )

    assert profile.overhead_ms == 5.0
    assert profile.overhead_percentage == 50.0


def test_slowest_rules_limit():
    """Test that slowest_rules returns max 5 rules."""
    # Create 10 rule profiles
    rule_profiles = [
        RuleProfile(
            rule_id=f"rule-{i:03d}",
            execution_time_ms=float(i),
            matched=False,
            cache_hit=False,
        )
        for i in range(10)
    ]

    layer_profile = LayerProfile(
        layer_name="L1",
        total_time_ms=45.0,
        rule_profiles=rule_profiles,
        cache_hits=0,
        cache_misses=10,
    )

    slowest = layer_profile.slowest_rules

    # Should return only 5 slowest
    assert len(slowest) == 5
    assert slowest[0].rule_id == "rule-009"  # Slowest
    assert slowest[4].rule_id == "rule-005"  # 5th slowest
