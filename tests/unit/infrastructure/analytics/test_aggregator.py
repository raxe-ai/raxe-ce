"""
Unit tests for data aggregator.

Tests the data aggregation functionality including:
- Daily rollups
- Hourly patterns
- Detection breakdown
- Performance trends
- L1/L2 breakdown
"""

import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from raxe.infrastructure.analytics.aggregator import (
    DailyRollup,
    DataAggregator,
    DetectionBreakdown,
    HourlyPattern,
)
from raxe.infrastructure.database.models import TelemetryEvent


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def aggregator(temp_db):
    """Create data aggregator with temporary database."""
    agg = DataAggregator(db_path=temp_db)
    yield agg
    agg.close()


@pytest.fixture
def sample_events(aggregator):
    """Create sample telemetry events spanning multiple days and hours."""
    session = aggregator._get_session()

    now = datetime.now(timezone.utc)
    events = []

    # Create events over 7 days with varied patterns
    for day in range(7):
        day_start = now - timedelta(days=6-day)

        # Create events at different hours
        for hour in [8, 12, 16, 20]:  # Morning, noon, afternoon, evening
            for i in range(5):  # 5 scans per hour
                event_time = day_start.replace(hour=hour, minute=i*10, second=0)

                event = TelemetryEvent(
                    event_id=f"event_{day}_{hour}_{i}",
                    event_type="scan_performed",
                    customer_id=f"user_{i % 3}",  # 3 different users
                    api_key_id=f"key_{i % 3}",
                    text_hash=f"hash_{day}_{hour}_{i}",
                    text_length=100,
                    detection_count=1 if (day + hour + i) % 4 == 0 else 0,  # ~25% detection
                    highest_severity="high" if (day + hour + i) % 4 == 0 else None,
                    l1_inference_ms=5.0 + (i * 0.5),
                    l2_inference_ms=12.0 if i % 2 == 0 else None,  # 50% L2 usage
                    total_latency_ms=18.0 if i % 2 == 0 else 7.0,
                    policy_action="allow",
                    sdk_version="1.0.0",
                    environment="production",
                    timestamp=event_time
                )
                events.append(event)

    session.add_all(events)
    session.commit()
    session.close()

    return events


class TestDataAggregator:
    """Test suite for DataAggregator."""

    def test_aggregator_initialization(self, temp_db):
        """Test aggregator initializes correctly."""
        agg = DataAggregator(db_path=temp_db)
        assert agg.db_path == temp_db
        assert temp_db.exists()
        agg.close()

    def test_get_daily_rollup_no_data(self, aggregator):
        """Test daily rollup with no data."""
        start_date = date.today() - timedelta(days=60)
        end_date = date.today() - timedelta(days=30)

        rollups = aggregator.get_daily_rollup(start_date, end_date)

        # Should return rollups for all days, even with no data
        assert len(rollups) == 31
        assert all(r.total_scans == 0 for r in rollups)

    def test_get_daily_rollup_with_data(self, aggregator, sample_events):
        """Test daily rollup with sample data."""
        start_date = date.today() - timedelta(days=6)
        end_date = date.today()

        rollups = aggregator.get_daily_rollup(start_date, end_date)

        assert len(rollups) == 7

        # Each day should have data (4 hours * 5 scans = 20 scans per day)
        for rollup in rollups:
            if rollup.total_scans > 0:  # Days with data
                assert rollup.total_scans == 20
                assert rollup.total_threats > 0  # ~25% detection rate
                assert rollup.avg_duration_ms > 0
                assert rollup.unique_users > 0

    def test_daily_rollup_metrics(self, aggregator, sample_events):
        """Test daily rollup calculates correct metrics."""
        today = date.today()
        rollups = aggregator.get_daily_rollup(today, today)

        if rollups and rollups[0].total_scans > 0:
            rollup = rollups[0]
            assert rollup.detection_rate >= 0.0
            assert rollup.detection_rate <= 100.0
            assert rollup.max_duration_ms >= rollup.avg_duration_ms

    def test_get_hourly_patterns_no_data(self, aggregator):
        """Test hourly patterns with no data."""
        patterns = aggregator.get_hourly_patterns(days=30)

        # Should return pattern for all 24 hours
        assert len(patterns) == 24
        assert all(p.scan_count == 0 for p in patterns)

    def test_get_hourly_patterns_with_data(self, aggregator, sample_events):
        """Test hourly patterns with sample data."""
        patterns = aggregator.get_hourly_patterns(days=7)

        assert len(patterns) == 24

        # Hours 8, 12, 16, 20 should have scans
        active_hours = [8, 12, 16, 20]
        for pattern in patterns:
            if pattern.hour in active_hours:
                assert pattern.scan_count > 0
                assert pattern.avg_duration_ms > 0
            # Other hours might have 0 scans

    def test_hourly_pattern_metrics(self, aggregator, sample_events):
        """Test hourly patterns calculate correct metrics."""
        patterns = aggregator.get_hourly_patterns(days=7)

        # Find an active hour
        active_pattern = next((p for p in patterns if p.scan_count > 0), None)
        if active_pattern:
            assert active_pattern.threat_count >= 0
            assert active_pattern.threat_count <= active_pattern.scan_count
            assert active_pattern.avg_duration_ms > 0

    def test_get_detection_breakdown_no_data(self, aggregator):
        """Test detection breakdown with no data."""
        breakdown = aggregator.get_detection_breakdown(days=30)

        assert len(breakdown) == 0

    def test_get_detection_breakdown_with_data(self, aggregator, sample_events):
        """Test detection breakdown with sample data."""
        breakdown = aggregator.get_detection_breakdown(days=7)

        # Should have at least one severity level
        assert len(breakdown) > 0

        # Check breakdown structure
        for item in breakdown:
            assert item.severity in ["critical", "high", "medium", "low", "info"]
            assert item.count > 0
            assert 0 <= item.percentage <= 100

        # Percentages should sum to ~100
        total_percentage = sum(item.percentage for item in breakdown)
        assert 99 <= total_percentage <= 101  # Allow for rounding

    def test_detection_breakdown_sorted(self, aggregator, sample_events):
        """Test detection breakdown is sorted by count."""
        breakdown = aggregator.get_detection_breakdown(days=7)

        if len(breakdown) > 1:
            # Check descending order
            for i in range(len(breakdown) - 1):
                assert breakdown[i].count >= breakdown[i+1].count

    def test_get_performance_trends_no_data(self, aggregator):
        """Test performance trends with no data."""
        trends = aggregator.get_performance_trends(days=30)

        assert trends["avg_latency_ms"] == 0.0
        assert trends["sample_size"] == 0
        assert trends["trend"] == "stable"

    def test_get_performance_trends_with_data(self, aggregator, sample_events):
        """Test performance trends with sample data."""
        trends = aggregator.get_performance_trends(days=7)

        assert trends["avg_latency_ms"] > 0
        assert trends["min_latency_ms"] > 0
        assert trends["max_latency_ms"] >= trends["avg_latency_ms"]
        assert trends["p50_latency_ms"] > 0
        assert trends["p95_latency_ms"] >= trends["p50_latency_ms"]
        assert trends["p99_latency_ms"] >= trends["p95_latency_ms"]
        assert trends["trend"] in ["improving", "stable", "degrading"]
        assert trends["sample_size"] > 0

    def test_performance_percentiles(self, aggregator, sample_events):
        """Test performance percentiles are calculated correctly."""
        trends = aggregator.get_performance_trends(days=7)

        # P50 should be <= P95 <= P99
        assert trends["p50_latency_ms"] <= trends["p95_latency_ms"]
        assert trends["p95_latency_ms"] <= trends["p99_latency_ms"]

        # All percentiles should be within min/max range
        assert trends["min_latency_ms"] <= trends["p50_latency_ms"]
        assert trends["p99_latency_ms"] <= trends["max_latency_ms"]

    def test_get_l1_vs_l2_breakdown_no_data(self, aggregator):
        """Test L1 vs L2 breakdown with no data."""
        breakdown = aggregator.get_l1_vs_l2_breakdown(days=30)

        assert breakdown["total_scans"] == 0
        assert breakdown["l1_only"] == 0
        assert breakdown["l2_used"] == 0
        assert breakdown["l2_usage_rate"] == 0.0

    def test_get_l1_vs_l2_breakdown_with_data(self, aggregator, sample_events):
        """Test L1 vs L2 breakdown with sample data."""
        breakdown = aggregator.get_l1_vs_l2_breakdown(days=7)

        assert breakdown["total_scans"] > 0
        assert breakdown["l1_only"] >= 0
        assert breakdown["l2_used"] >= 0
        assert breakdown["l1_only"] + breakdown["l2_used"] == breakdown["total_scans"]

        # Should have ~50% L2 usage based on sample data
        assert 40 <= breakdown["l2_usage_rate"] <= 60

        assert breakdown["avg_l1_ms"] > 0
        if breakdown["l2_used"] > 0:
            assert breakdown["avg_l2_ms"] > 0


class TestDailyRollup:
    """Test suite for DailyRollup dataclass."""

    def test_daily_rollup_creation(self):
        """Test creating DailyRollup object."""
        rollup = DailyRollup(
            date=date.today(),
            total_scans=100,
            total_threats=25,
            avg_duration_ms=10.5,
            max_duration_ms=50.0,
            unique_users=10,
            detection_rate=25.0
        )

        assert rollup.total_scans == 100
        assert rollup.total_threats == 25
        assert rollup.detection_rate == 25.0


class TestHourlyPattern:
    """Test suite for HourlyPattern dataclass."""

    def test_hourly_pattern_creation(self):
        """Test creating HourlyPattern object."""
        pattern = HourlyPattern(
            hour=14,
            scan_count=50,
            threat_count=10,
            avg_duration_ms=8.5
        )

        assert pattern.hour == 14
        assert pattern.scan_count == 50
        assert pattern.threat_count == 10


class TestDetectionBreakdown:
    """Test suite for DetectionBreakdown dataclass."""

    def test_detection_breakdown_creation(self):
        """Test creating DetectionBreakdown object."""
        breakdown = DetectionBreakdown(
            severity="high",
            count=50,
            percentage=45.5
        )

        assert breakdown.severity == "high"
        assert breakdown.count == 50
        assert breakdown.percentage == 45.5
