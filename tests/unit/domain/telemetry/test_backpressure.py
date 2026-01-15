"""
Unit tests for telemetry backpressure calculation module.

Tests backpressure calculation at different fill levels.
These tests are PURE - no mocks, no I/O, no database.

Coverage target: >95%
"""

import pytest

from raxe.domain.telemetry.backpressure import (
    DEFAULT_THRESHOLDS,
    BackpressureDecision,
    BackpressureThresholds,
    QueueMetrics,
    calculate_backpressure,
    calculate_effective_sample_rate,
    should_sample_event,
)

# =============================================================================
# Test Markers
# =============================================================================
pytestmark = [pytest.mark.unit, pytest.mark.domain, pytest.mark.telemetry]


# =============================================================================
# QueueMetrics Tests
# =============================================================================
class TestQueueMetrics:
    """Test QueueMetrics dataclass."""

    def test_creates_valid_queue_metrics(self) -> None:
        """Should create QueueMetrics with valid values."""
        metrics = QueueMetrics(
            critical_queue_size=100,
            standard_queue_size=1000,
        )
        assert metrics.critical_queue_size == 100
        assert metrics.standard_queue_size == 1000
        assert metrics.critical_queue_max == 10_000
        assert metrics.standard_queue_max == 50_000
        assert metrics.dlq_size == 0

    def test_creates_with_all_parameters(self) -> None:
        """Should accept all parameters."""
        metrics = QueueMetrics(
            critical_queue_size=500,
            standard_queue_size=25000,
            critical_queue_max=5000,
            standard_queue_max=100000,
            dlq_size=10,
        )
        assert metrics.critical_queue_size == 500
        assert metrics.standard_queue_size == 25000
        assert metrics.critical_queue_max == 5000
        assert metrics.standard_queue_max == 100000
        assert metrics.dlq_size == 10

    def test_rejects_negative_critical_queue_size(self) -> None:
        """Should reject negative critical_queue_size."""
        with pytest.raises(ValueError, match="critical_queue_size cannot be negative"):
            QueueMetrics(critical_queue_size=-1, standard_queue_size=0)

    def test_rejects_negative_standard_queue_size(self) -> None:
        """Should reject negative standard_queue_size."""
        with pytest.raises(ValueError, match="standard_queue_size cannot be negative"):
            QueueMetrics(critical_queue_size=0, standard_queue_size=-1)

    def test_rejects_zero_critical_queue_max(self) -> None:
        """Should reject zero critical_queue_max."""
        with pytest.raises(ValueError, match="critical_queue_max must be positive"):
            QueueMetrics(
                critical_queue_size=0,
                standard_queue_size=0,
                critical_queue_max=0,
            )

    def test_rejects_negative_critical_queue_max(self) -> None:
        """Should reject negative critical_queue_max."""
        with pytest.raises(ValueError, match="critical_queue_max must be positive"):
            QueueMetrics(
                critical_queue_size=0,
                standard_queue_size=0,
                critical_queue_max=-1,
            )

    def test_rejects_zero_standard_queue_max(self) -> None:
        """Should reject zero standard_queue_max."""
        with pytest.raises(ValueError, match="standard_queue_max must be positive"):
            QueueMetrics(
                critical_queue_size=0,
                standard_queue_size=0,
                standard_queue_max=0,
            )

    def test_rejects_negative_standard_queue_max(self) -> None:
        """Should reject negative standard_queue_max."""
        with pytest.raises(ValueError, match="standard_queue_max must be positive"):
            QueueMetrics(
                critical_queue_size=0,
                standard_queue_size=0,
                standard_queue_max=-1,
            )

    def test_rejects_negative_dlq_size(self) -> None:
        """Should reject negative dlq_size."""
        with pytest.raises(ValueError, match="dlq_size cannot be negative"):
            QueueMetrics(
                critical_queue_size=0,
                standard_queue_size=0,
                dlq_size=-1,
            )

    def test_critical_queue_fill_ratio(self) -> None:
        """Should calculate correct critical queue fill ratio."""
        metrics = QueueMetrics(
            critical_queue_size=5000,
            standard_queue_size=0,
            critical_queue_max=10000,
        )
        assert metrics.critical_queue_fill_ratio == 0.5

    def test_standard_queue_fill_ratio(self) -> None:
        """Should calculate correct standard queue fill ratio."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=25000,
            standard_queue_max=50000,
        )
        assert metrics.standard_queue_fill_ratio == 0.5

    @pytest.mark.parametrize(
        "size,max_size,expected_ratio",
        [
            (0, 10000, 0.0),
            (5000, 10000, 0.5),
            (8000, 10000, 0.8),
            (9000, 10000, 0.9),
            (10000, 10000, 1.0),
            (15000, 10000, 1.5),  # Over capacity
        ],
    )
    def test_fill_ratio_calculations(self, size: int, max_size: int, expected_ratio: float) -> None:
        """Test fill ratio calculations at various levels."""
        metrics = QueueMetrics(
            critical_queue_size=size,
            standard_queue_size=0,
            critical_queue_max=max_size,
        )
        assert metrics.critical_queue_fill_ratio == expected_ratio

    def test_queue_metrics_is_frozen(self) -> None:
        """QueueMetrics should be immutable."""
        metrics = QueueMetrics(critical_queue_size=0, standard_queue_size=0)
        with pytest.raises(AttributeError):
            metrics.critical_queue_size = 100  # type: ignore[misc]


# =============================================================================
# BackpressureThresholds Tests
# =============================================================================
class TestBackpressureThresholds:
    """Test BackpressureThresholds dataclass."""

    def test_creates_with_default_values(self) -> None:
        """Should create with default threshold values."""
        thresholds = BackpressureThresholds()
        assert thresholds.elevated_threshold == 0.8
        assert thresholds.critical_threshold == 0.9
        assert thresholds.elevated_sample_rate == 0.5
        assert thresholds.critical_sample_rate == 0.2

    def test_creates_with_custom_values(self) -> None:
        """Should accept custom threshold values."""
        thresholds = BackpressureThresholds(
            elevated_threshold=0.7,
            critical_threshold=0.85,
            elevated_sample_rate=0.6,
            critical_sample_rate=0.3,
        )
        assert thresholds.elevated_threshold == 0.7
        assert thresholds.critical_threshold == 0.85
        assert thresholds.elevated_sample_rate == 0.6
        assert thresholds.critical_sample_rate == 0.3

    def test_rejects_elevated_threshold_zero(self) -> None:
        """Should reject elevated_threshold of 0."""
        with pytest.raises(ValueError, match="elevated_threshold must be between 0 and 1"):
            BackpressureThresholds(elevated_threshold=0.0)

    def test_rejects_elevated_threshold_one(self) -> None:
        """Should reject elevated_threshold of 1."""
        with pytest.raises(ValueError, match="elevated_threshold must be between 0 and 1"):
            BackpressureThresholds(elevated_threshold=1.0)

    def test_rejects_elevated_threshold_negative(self) -> None:
        """Should reject negative elevated_threshold."""
        with pytest.raises(ValueError, match="elevated_threshold must be between 0 and 1"):
            BackpressureThresholds(elevated_threshold=-0.1)

    def test_rejects_critical_threshold_zero(self) -> None:
        """Should reject critical_threshold of 0."""
        with pytest.raises(ValueError, match="critical_threshold must be between 0 and 1"):
            BackpressureThresholds(elevated_threshold=0.5, critical_threshold=0.0)

    def test_rejects_critical_threshold_over_one(self) -> None:
        """Should reject critical_threshold over 1."""
        with pytest.raises(ValueError, match="critical_threshold must be between 0 and 1"):
            BackpressureThresholds(critical_threshold=1.1)

    def test_rejects_elevated_greater_than_critical(self) -> None:
        """Should reject if elevated_threshold >= critical_threshold."""
        with pytest.raises(
            ValueError, match="elevated_threshold .* must be less than critical_threshold"
        ):
            BackpressureThresholds(elevated_threshold=0.9, critical_threshold=0.8)

    def test_rejects_elevated_equal_to_critical(self) -> None:
        """Should reject if elevated_threshold == critical_threshold."""
        with pytest.raises(
            ValueError, match="elevated_threshold .* must be less than critical_threshold"
        ):
            BackpressureThresholds(elevated_threshold=0.85, critical_threshold=0.85)

    def test_rejects_elevated_sample_rate_zero(self) -> None:
        """Should reject elevated_sample_rate of 0."""
        with pytest.raises(ValueError, match="elevated_sample_rate must be between 0 and 1"):
            BackpressureThresholds(elevated_sample_rate=0.0)

    def test_rejects_elevated_sample_rate_over_one(self) -> None:
        """Should reject elevated_sample_rate over 1."""
        with pytest.raises(ValueError, match="elevated_sample_rate must be between 0 and 1"):
            BackpressureThresholds(elevated_sample_rate=1.1)

    def test_rejects_critical_sample_rate_zero(self) -> None:
        """Should reject critical_sample_rate of 0."""
        with pytest.raises(ValueError, match="critical_sample_rate must be between 0 and 1"):
            BackpressureThresholds(critical_sample_rate=0.0)

    def test_rejects_critical_sample_rate_over_one(self) -> None:
        """Should reject critical_sample_rate over 1."""
        with pytest.raises(ValueError, match="critical_sample_rate must be between 0 and 1"):
            BackpressureThresholds(critical_sample_rate=1.1)

    def test_default_thresholds_constant(self) -> None:
        """DEFAULT_THRESHOLDS should be properly initialized."""
        assert DEFAULT_THRESHOLDS is not None
        assert isinstance(DEFAULT_THRESHOLDS, BackpressureThresholds)
        assert DEFAULT_THRESHOLDS.elevated_threshold == 0.8
        assert DEFAULT_THRESHOLDS.critical_threshold == 0.9


# =============================================================================
# BackpressureDecision Tests
# =============================================================================
class TestBackpressureDecision:
    """Test BackpressureDecision dataclass."""

    def test_creates_valid_decision(self) -> None:
        """Should create valid decision with all fields."""
        decision = BackpressureDecision(
            should_queue=True,
            sample_rate=0.5,
            pressure_level="elevated",
            reason="Test reason",
        )
        assert decision.should_queue is True
        assert decision.sample_rate == 0.5
        assert decision.pressure_level == "elevated"
        assert decision.reason == "Test reason"

    def test_rejects_negative_sample_rate(self) -> None:
        """Should reject negative sample_rate."""
        with pytest.raises(ValueError, match="sample_rate must be between 0 and 1"):
            BackpressureDecision(
                should_queue=True,
                sample_rate=-0.1,
                pressure_level="normal",
                reason="Test",
            )

    def test_rejects_sample_rate_over_one(self) -> None:
        """Should reject sample_rate over 1."""
        with pytest.raises(ValueError, match="sample_rate must be between 0 and 1"):
            BackpressureDecision(
                should_queue=True,
                sample_rate=1.1,
                pressure_level="normal",
                reason="Test",
            )

    def test_accepts_boundary_sample_rates(self) -> None:
        """Should accept sample_rate of 0 and 1."""
        decision_zero = BackpressureDecision(
            should_queue=False,
            sample_rate=0.0,
            pressure_level="critical",
            reason="Dropped",
        )
        assert decision_zero.sample_rate == 0.0

        decision_one = BackpressureDecision(
            should_queue=True,
            sample_rate=1.0,
            pressure_level="normal",
            reason="Normal",
        )
        assert decision_one.sample_rate == 1.0

    def test_decision_is_frozen(self) -> None:
        """BackpressureDecision should be immutable."""
        decision = BackpressureDecision(
            should_queue=True,
            sample_rate=1.0,
            pressure_level="normal",
            reason="Test",
        )
        with pytest.raises(AttributeError):
            decision.should_queue = False  # type: ignore[misc]


# =============================================================================
# calculate_backpressure Tests - Critical Events
# =============================================================================
class TestCalculateBackpressureCriticalEvents:
    """Test backpressure calculation for critical events."""

    def test_critical_event_always_queued_at_0_percent(self) -> None:
        """Critical events should always be queued at 0% fill."""
        metrics = QueueMetrics(critical_queue_size=0, standard_queue_size=0)
        decision = calculate_backpressure(metrics, is_critical_event=True)

        assert decision.should_queue is True
        assert decision.sample_rate == 1.0
        assert decision.pressure_level == "normal"

    def test_critical_event_always_queued_at_50_percent(self) -> None:
        """Critical events should always be queued at 50% fill."""
        metrics = QueueMetrics(
            critical_queue_size=5000,
            standard_queue_size=0,
            critical_queue_max=10000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=True)

        assert decision.should_queue is True
        assert decision.sample_rate == 1.0
        assert decision.pressure_level == "normal"

    def test_critical_event_always_queued_at_80_percent(self) -> None:
        """Critical events should always be queued at 80% (elevated threshold)."""
        metrics = QueueMetrics(
            critical_queue_size=8000,
            standard_queue_size=0,
            critical_queue_max=10000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=True)

        assert decision.should_queue is True
        assert decision.sample_rate == 1.0
        assert decision.pressure_level == "elevated"

    def test_critical_event_always_queued_at_90_percent(self) -> None:
        """Critical events should always be queued at 90% (critical threshold)."""
        metrics = QueueMetrics(
            critical_queue_size=9000,
            standard_queue_size=0,
            critical_queue_max=10000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=True)

        assert decision.should_queue is True
        assert decision.sample_rate == 1.0
        assert decision.pressure_level == "critical"

    def test_critical_event_always_queued_at_100_percent(self) -> None:
        """Critical events should always be queued at 100% (full)."""
        metrics = QueueMetrics(
            critical_queue_size=10000,
            standard_queue_size=0,
            critical_queue_max=10000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=True)

        assert decision.should_queue is True
        assert decision.sample_rate == 1.0
        assert decision.pressure_level == "critical"
        assert "queue overflow" in decision.reason.lower()

    def test_critical_event_always_queued_over_capacity(self) -> None:
        """Critical events should always be queued even over capacity."""
        metrics = QueueMetrics(
            critical_queue_size=15000,
            standard_queue_size=0,
            critical_queue_max=10000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=True)

        assert decision.should_queue is True
        assert decision.sample_rate == 1.0


# =============================================================================
# calculate_backpressure Tests - Standard Events
# =============================================================================
class TestCalculateBackpressureStandardEvents:
    """Test backpressure calculation for standard events."""

    def test_standard_event_queued_normally_at_0_percent(self) -> None:
        """Standard events should be queued normally at 0% fill."""
        metrics = QueueMetrics(critical_queue_size=0, standard_queue_size=0)
        decision = calculate_backpressure(metrics, is_critical_event=False)

        assert decision.should_queue is True
        assert decision.sample_rate == 1.0
        assert decision.pressure_level == "normal"
        assert "normally" in decision.reason.lower()

    def test_standard_event_queued_normally_at_50_percent(self) -> None:
        """Standard events should be queued normally at 50% fill."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=25000,
            standard_queue_max=50000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False)

        assert decision.should_queue is True
        assert decision.sample_rate == 1.0
        assert decision.pressure_level == "normal"

    def test_standard_event_queued_normally_just_below_80_percent(self) -> None:
        """Standard events should be queued normally just below 80%."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=39999,
            standard_queue_max=50000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False)

        assert decision.should_queue is True
        assert decision.sample_rate == 1.0
        assert decision.pressure_level == "normal"

    def test_standard_event_sampled_at_80_percent(self) -> None:
        """Standard events should be sampled at 0.5 at 80% fill."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=40000,
            standard_queue_max=50000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False)

        assert decision.should_queue is True
        assert decision.sample_rate == 0.5
        assert decision.pressure_level == "elevated"
        assert "50%" in decision.reason

    def test_standard_event_sampled_at_85_percent(self) -> None:
        """Standard events should be sampled at 0.5 at 85% fill."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=42500,
            standard_queue_max=50000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False)

        assert decision.should_queue is True
        assert decision.sample_rate == 0.5
        assert decision.pressure_level == "elevated"

    def test_standard_event_sampled_at_90_percent(self) -> None:
        """Standard events should be sampled at 0.2 at 90% fill."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=45000,
            standard_queue_max=50000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False)

        assert decision.should_queue is True
        assert decision.sample_rate == 0.2
        assert decision.pressure_level == "critical"
        assert "20%" in decision.reason

    def test_standard_event_sampled_at_95_percent(self) -> None:
        """Standard events should be sampled at 0.2 at 95% fill."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=47500,
            standard_queue_max=50000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False)

        assert decision.should_queue is True
        assert decision.sample_rate == 0.2
        assert decision.pressure_level == "critical"

    def test_standard_event_dropped_at_100_percent(self) -> None:
        """Standard events should be dropped at 100% fill."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=50000,
            standard_queue_max=50000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False)

        assert decision.should_queue is False
        assert decision.sample_rate == 0.0
        assert decision.pressure_level == "critical"
        assert "dropped" in decision.reason.lower()

    def test_standard_event_dropped_over_capacity(self) -> None:
        """Standard events should be dropped when over capacity."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=60000,
            standard_queue_max=50000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False)

        assert decision.should_queue is False
        assert decision.sample_rate == 0.0


# =============================================================================
# calculate_backpressure Tests - Custom Thresholds
# =============================================================================
class TestCalculateBackpressureCustomThresholds:
    """Test backpressure calculation with custom thresholds."""

    def test_custom_elevated_threshold(self) -> None:
        """Should use custom elevated threshold."""
        thresholds = BackpressureThresholds(
            elevated_threshold=0.5,  # Lower than default 0.8
            critical_threshold=0.9,
        )
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=30000,  # 60% - above custom elevated
            standard_queue_max=50000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False, thresholds=thresholds)

        assert decision.pressure_level == "elevated"
        assert decision.sample_rate == 0.5

    def test_custom_critical_threshold(self) -> None:
        """Should use custom critical threshold."""
        thresholds = BackpressureThresholds(
            elevated_threshold=0.6,
            critical_threshold=0.7,  # Lower than default 0.9
        )
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=40000,  # 80% - above custom critical
            standard_queue_max=50000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False, thresholds=thresholds)

        assert decision.pressure_level == "critical"
        assert decision.sample_rate == 0.2

    def test_custom_sample_rates(self) -> None:
        """Should use custom sample rates."""
        thresholds = BackpressureThresholds(
            elevated_threshold=0.8,
            critical_threshold=0.9,
            elevated_sample_rate=0.7,  # Different from default 0.5
            critical_sample_rate=0.3,  # Different from default 0.2
        )

        # Test elevated sample rate
        metrics_elevated = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=42500,  # 85%
            standard_queue_max=50000,
        )
        decision_elevated = calculate_backpressure(
            metrics_elevated, is_critical_event=False, thresholds=thresholds
        )
        assert decision_elevated.sample_rate == 0.7

        # Test critical sample rate
        metrics_critical = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=47500,  # 95%
            standard_queue_max=50000,
        )
        decision_critical = calculate_backpressure(
            metrics_critical, is_critical_event=False, thresholds=thresholds
        )
        assert decision_critical.sample_rate == 0.3


# =============================================================================
# should_sample_event Tests
# =============================================================================
class TestShouldSampleEvent:
    """Test should_sample_event function."""

    def test_always_keeps_with_sample_rate_1(self) -> None:
        """Sample rate of 1.0 should always keep events."""
        assert should_sample_event(1.0, "abc123") is True
        assert should_sample_event(1.0, "xyz789") is True
        assert should_sample_event(1.0, "any_hash") is True

    def test_always_drops_with_sample_rate_0(self) -> None:
        """Sample rate of 0.0 should always drop events."""
        assert should_sample_event(0.0, "abc123") is False
        assert should_sample_event(0.0, "xyz789") is False
        assert should_sample_event(0.0, "any_hash") is False

    def test_is_deterministic(self) -> None:
        """Same hash should always produce same result."""
        hash_value = "a1b2c3d4e5f67890"
        result1 = should_sample_event(0.5, hash_value)
        result2 = should_sample_event(0.5, hash_value)
        result3 = should_sample_event(0.5, hash_value)
        assert result1 == result2 == result3

    def test_different_hashes_may_produce_different_results(self) -> None:
        """Different hashes with 0.5 rate should produce ~50% True."""
        results = [should_sample_event(0.5, f"hash_{i:08x}") for i in range(1000)]
        true_count = sum(results)
        # With 1000 samples at 50%, expect roughly 400-600 True
        assert 350 < true_count < 650

    def test_rejects_negative_sample_rate(self) -> None:
        """Should reject negative sample rate."""
        with pytest.raises(ValueError, match="sample_rate must be between 0 and 1"):
            should_sample_event(-0.1, "abc123")

    def test_rejects_sample_rate_over_1(self) -> None:
        """Should reject sample rate over 1."""
        with pytest.raises(ValueError, match="sample_rate must be between 0 and 1"):
            should_sample_event(1.1, "abc123")

    def test_rejects_empty_hash(self) -> None:
        """Should reject empty event hash."""
        with pytest.raises(ValueError, match="event_hash cannot be empty"):
            should_sample_event(0.5, "")

    def test_handles_short_hash(self) -> None:
        """Should handle hash shorter than 8 characters."""
        # Should not raise
        result = should_sample_event(0.5, "abc")
        assert isinstance(result, bool)

    def test_handles_non_hex_hash(self) -> None:
        """Should handle non-hexadecimal hash as fallback."""
        # Non-hex characters - uses fallback sum of ord() values
        result = should_sample_event(0.5, "not-hex-hash-xyz")
        assert isinstance(result, bool)

    def test_handles_long_hash(self) -> None:
        """Should handle hash longer than 8 characters."""
        # SHA-256 is 64 hex chars
        long_hash = "a" * 64
        result = should_sample_event(0.5, long_hash)
        assert isinstance(result, bool)

    @pytest.mark.parametrize(
        "sample_rate",
        [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
    )
    def test_sampling_roughly_matches_rate(self, sample_rate: float) -> None:
        """Sampling should roughly match the sample rate."""
        results = [should_sample_event(sample_rate, f"hash_{i:016x}") for i in range(1000)]
        actual_rate = sum(results) / len(results)
        # Allow 10% tolerance
        assert abs(actual_rate - sample_rate) < 0.1


# =============================================================================
# calculate_effective_sample_rate Tests
# =============================================================================
class TestCalculateEffectiveSampleRate:
    """Test calculate_effective_sample_rate convenience function."""

    def test_returns_1_for_normal_pressure(self) -> None:
        """Should return 1.0 for normal pressure."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=10000,
            standard_queue_max=50000,
        )
        rate = calculate_effective_sample_rate(metrics, is_critical_event=False)
        assert rate == 1.0

    def test_returns_elevated_rate_for_elevated_pressure(self) -> None:
        """Should return elevated sample rate for elevated pressure."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=42500,  # 85%
            standard_queue_max=50000,
        )
        rate = calculate_effective_sample_rate(metrics, is_critical_event=False)
        assert rate == 0.5

    def test_returns_critical_rate_for_critical_pressure(self) -> None:
        """Should return critical sample rate for critical pressure."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=47500,  # 95%
            standard_queue_max=50000,
        )
        rate = calculate_effective_sample_rate(metrics, is_critical_event=False)
        assert rate == 0.2

    def test_returns_0_for_full_queue(self) -> None:
        """Should return 0 for full queue (standard events)."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=50000,
            standard_queue_max=50000,
        )
        rate = calculate_effective_sample_rate(metrics, is_critical_event=False)
        assert rate == 0.0

    def test_critical_events_always_return_1(self) -> None:
        """Critical events should always have sample rate of 1.0."""
        metrics = QueueMetrics(
            critical_queue_size=9500,  # 95%
            standard_queue_size=0,
            critical_queue_max=10000,
        )
        rate = calculate_effective_sample_rate(metrics, is_critical_event=True)
        assert rate == 1.0

    def test_with_custom_thresholds(self) -> None:
        """Should use custom thresholds."""
        thresholds = BackpressureThresholds(
            elevated_threshold=0.5,
            critical_threshold=0.7,
            elevated_sample_rate=0.6,
            critical_sample_rate=0.3,
        )
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=30000,  # 60% - above custom elevated
            standard_queue_max=50000,
        )
        rate = calculate_effective_sample_rate(
            metrics, is_critical_event=False, thresholds=thresholds
        )
        assert rate == 0.6


# =============================================================================
# Integration Tests - Critical vs Standard Events
# =============================================================================
class TestBackpressureCriticalVsStandard:
    """Test differences between critical and standard events."""

    @pytest.mark.parametrize(
        "fill_percent",
        [0, 50, 80, 90, 100, 150],
    )
    def test_critical_events_never_dropped(self, fill_percent: int) -> None:
        """Critical events should never be dropped at any fill level."""
        size = (fill_percent * 10000) // 100
        metrics = QueueMetrics(
            critical_queue_size=size,
            standard_queue_size=0,
            critical_queue_max=10000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=True)
        assert decision.should_queue is True
        assert decision.sample_rate == 1.0

    @pytest.mark.parametrize(
        "fill_percent,expected_queued",
        [
            (0, True),
            (50, True),
            (79, True),
            (80, True),  # Sampled but queued
            (90, True),  # Sampled but queued
            (99, True),  # Sampled but queued
            (100, False),  # Dropped
            (150, False),  # Dropped
        ],
    )
    def test_standard_event_queuing(self, fill_percent: int, expected_queued: bool) -> None:
        """Standard events should be queued/dropped based on fill level."""
        size = (fill_percent * 50000) // 100
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=size,
            standard_queue_max=50000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False)
        assert decision.should_queue is expected_queued


# =============================================================================
# Pure Function Verification Tests
# =============================================================================
class TestPureFunctions:
    """Verify that all functions are pure (no I/O)."""

    def test_calculate_backpressure_is_deterministic(self) -> None:
        """calculate_backpressure should be deterministic."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=45000,
            standard_queue_max=50000,
        )
        decision1 = calculate_backpressure(metrics, is_critical_event=False)
        decision2 = calculate_backpressure(metrics, is_critical_event=False)
        assert decision1.should_queue == decision2.should_queue
        assert decision1.sample_rate == decision2.sample_rate
        assert decision1.pressure_level == decision2.pressure_level

    def test_should_sample_event_is_deterministic(self) -> None:
        """should_sample_event should be deterministic for same inputs."""
        result1 = should_sample_event(0.5, "test_hash_123")
        result2 = should_sample_event(0.5, "test_hash_123")
        assert result1 == result2

    def test_calculate_effective_sample_rate_is_deterministic(self) -> None:
        """calculate_effective_sample_rate should be deterministic."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=42500,
            standard_queue_max=50000,
        )
        rate1 = calculate_effective_sample_rate(metrics, is_critical_event=False)
        rate2 = calculate_effective_sample_rate(metrics, is_critical_event=False)
        assert rate1 == rate2


# =============================================================================
# Edge Cases Tests
# =============================================================================
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exactly_at_elevated_threshold(self) -> None:
        """Test exactly at elevated threshold boundary."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=40000,  # Exactly 80%
            standard_queue_max=50000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False)
        assert decision.pressure_level == "elevated"
        assert decision.sample_rate == 0.5

    def test_just_below_elevated_threshold(self) -> None:
        """Test just below elevated threshold boundary."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=39999,  # Just below 80%
            standard_queue_max=50000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False)
        assert decision.pressure_level == "normal"
        assert decision.sample_rate == 1.0

    def test_exactly_at_critical_threshold(self) -> None:
        """Test exactly at critical threshold boundary."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=45000,  # Exactly 90%
            standard_queue_max=50000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False)
        assert decision.pressure_level == "critical"
        assert decision.sample_rate == 0.2

    def test_just_below_critical_threshold(self) -> None:
        """Test just below critical threshold boundary."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=44999,  # Just below 90%
            standard_queue_max=50000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False)
        assert decision.pressure_level == "elevated"
        assert decision.sample_rate == 0.5

    def test_minimal_queue_capacity(self) -> None:
        """Test with minimal queue capacity."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=9,
            critical_queue_max=1,
            standard_queue_max=10,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False)
        assert decision.pressure_level == "critical"

    def test_large_queue_numbers(self) -> None:
        """Test with large queue numbers."""
        metrics = QueueMetrics(
            critical_queue_size=0,
            standard_queue_size=4_000_000,
            standard_queue_max=5_000_000,
        )
        decision = calculate_backpressure(metrics, is_critical_event=False)
        assert decision.pressure_level == "elevated"
        assert decision.sample_rate == 0.5

    def test_hash_with_all_zeros(self) -> None:
        """Test sampling with hash of all zeros."""
        result = should_sample_event(0.5, "00000000")
        assert isinstance(result, bool)
        # All zeros -> hash_value = 0 -> bucket = 0 -> 0 < 500 -> True
        assert result is True

    def test_hash_with_all_fs(self) -> None:
        """Test sampling with hash of all F's (max hex value)."""
        result = should_sample_event(0.5, "ffffffff")
        assert isinstance(result, bool)
