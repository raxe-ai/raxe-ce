"""
Unit tests for analytics engine.

Tests the analytics calculation engine including:
- Retention calculations
- User statistics
- Global statistics
- Report generation
"""

import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from raxe.infrastructure.analytics.engine import (
    AnalyticsEngine,
    InstallationMetrics,
    PerformanceMetrics,
    RetentionMetrics,
    UsageMetrics,
    UserStats,
)
from raxe.infrastructure.database.models import TelemetryEvent


@pytest.fixture(autouse=True)
def isolate_scan_history():
    """Isolate tests from global scan_history.db by temporarily hiding it."""
    global_scan_history = Path.home() / ".raxe" / "scan_history.db"
    backup_path = None

    if global_scan_history.exists():
        # Temporarily rename the global database
        backup_path = global_scan_history.with_suffix(".db.test_backup")
        global_scan_history.rename(backup_path)

    yield

    # Restore the global database
    if backup_path and backup_path.exists():
        backup_path.rename(global_scan_history)


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
def analytics_engine(temp_db):
    """Create analytics engine with temporary database."""
    engine = AnalyticsEngine(db_path=temp_db)
    yield engine
    engine.close()


@pytest.fixture
def sample_events(analytics_engine):
    """Create sample telemetry events for testing."""
    session = analytics_engine._get_session()

    # Create events for 3 users over 30 days
    now = datetime.now(timezone.utc)
    events = []

    # User 1: Active user with scans every day
    for i in range(30):
        event = TelemetryEvent(
            event_id=f"event_1_{i}",
            event_type="scan_performed",
            customer_id="user_1",
            api_key_id="key_1",
            text_hash=f"hash_1_{i}",
            text_length=100,
            detection_count=1 if i % 5 == 0 else 0,  # 20% detection rate
            highest_severity="high" if i % 5 == 0 else None,
            l1_inference_ms=5.0,
            l2_inference_ms=None,
            total_latency_ms=8.0,
            policy_action="allow",
            sdk_version="1.0.0",
            environment="production",
            timestamp=now - timedelta(days=30-i)
        )
        events.append(event)

    # User 2: Moderate user with scans every 3 days
    for i in range(10):
        event = TelemetryEvent(
            event_id=f"event_2_{i}",
            event_type="scan_performed",
            customer_id="user_2",
            api_key_id="key_2",
            text_hash=f"hash_2_{i}",
            text_length=150,
            detection_count=1 if i % 3 == 0 else 0,
            highest_severity="medium" if i % 3 == 0 else None,
            l1_inference_ms=4.0,
            l2_inference_ms=10.0 if i % 2 == 0 else None,
            total_latency_ms=15.0 if i % 2 == 0 else 6.0,
            policy_action="allow",
            sdk_version="1.0.0",
            environment="production",
            timestamp=now - timedelta(days=30-i*3)
        )
        events.append(event)

    # User 3: Light user with only 3 scans
    for i in range(3):
        event = TelemetryEvent(
            event_id=f"event_3_{i}",
            event_type="scan_performed",
            customer_id="user_3",
            api_key_id="key_3",
            text_hash=f"hash_3_{i}",
            text_length=200,
            detection_count=0,
            highest_severity=None,
            l1_inference_ms=3.0,
            l2_inference_ms=None,
            total_latency_ms=5.0,
            policy_action="allow",
            sdk_version="1.0.0",
            environment="production",
            timestamp=now - timedelta(days=30-i*10)
        )
        events.append(event)

    session.add_all(events)
    session.commit()
    session.close()

    return events


class TestAnalyticsEngine:
    """Test suite for AnalyticsEngine."""

    def test_engine_initialization(self, temp_db):
        """Test engine initializes correctly."""
        engine = AnalyticsEngine(db_path=temp_db)
        assert engine.db_path == temp_db
        assert temp_db.exists()
        engine.close()

    def test_calculate_retention_no_cohort(self, analytics_engine):
        """Test retention calculation with no users in cohort."""
        cohort_date = date.today() - timedelta(days=60)
        retention = analytics_engine.calculate_retention(cohort_date)

        assert retention["cohort_size"] == 0
        assert retention["day_1"] == 0.0
        assert retention["day_7"] == 0.0
        assert retention["day_30"] == 0.0

    def test_calculate_retention_with_cohort(self, analytics_engine, sample_events):
        """Test retention calculation with sample cohort."""
        # Use cohort from 30 days ago (when sample events started)
        cohort_date = (datetime.now(timezone.utc) - timedelta(days=30)).date()
        retention = analytics_engine.calculate_retention(cohort_date)

        # All 3 users should be in cohort
        assert retention["cohort_size"] == 3
        assert retention["cohort_date"] == cohort_date.isoformat()

        # Retention rates should be calculated
        assert isinstance(retention["day_1"], float)
        assert isinstance(retention["day_7"], float)
        assert isinstance(retention["day_30"], float)

    def test_get_user_stats_nonexistent(self, analytics_engine):
        """Test getting stats for nonexistent user."""
        stats = analytics_engine.get_user_stats("nonexistent_user")

        assert stats.installation_id == "nonexistent_user"
        assert stats.total_scans == 0
        assert stats.threats_detected == 0
        assert stats.installation_date is None

    def test_get_user_stats_with_data(self, analytics_engine, sample_events):
        """Test getting stats for user with data."""
        stats = analytics_engine.get_user_stats("user_1")

        assert stats.installation_id == "user_1"
        assert stats.total_scans == 30
        assert stats.threats_detected == 6  # 20% of 30
        assert stats.detection_rate == 20.0
        assert stats.avg_scan_time_ms == 8.0
        assert stats.current_streak > 0  # Should have active streak
        assert stats.longest_streak >= stats.current_streak

    def test_streak_calculation(self, analytics_engine, sample_events):
        """Test streak calculation logic."""
        stats = analytics_engine.get_user_stats("user_1")

        # User 1 scans every day, should have max streak
        assert stats.current_streak >= 1
        assert stats.longest_streak >= stats.current_streak

        # User 2 scans every 3 days
        stats_2 = analytics_engine.get_user_stats("user_2")
        assert stats_2.current_streak >= 0

    def test_get_global_stats_empty(self, analytics_engine):
        """Test global stats with no data."""
        stats = analytics_engine.get_global_stats()

        assert stats["community"]["total_users"] == 0
        assert stats["community"]["total_scans"] == 0
        assert stats["threats"]["total_detected"] == 0

    def test_get_global_stats_with_data(self, analytics_engine, sample_events):
        """Test global stats with sample data."""
        stats = analytics_engine.get_global_stats()

        # Should have 3 users
        assert stats["community"]["total_users"] == 3

        # Should have 43 total scans (30 + 10 + 3)
        assert stats["community"]["total_scans"] == 43

        # Should have some threats detected
        assert stats["threats"]["total_detected"] > 0
        assert stats["threats"]["detection_rate"] > 0

        # Performance metrics should be calculated
        assert stats["performance"]["avg_scan_time_ms"] > 0
        assert stats["performance"]["p95_latency_ms"] >= stats["performance"]["avg_scan_time_ms"]

    def test_generate_report(self, analytics_engine, sample_events):
        """Test report generation."""
        start_date = date.today() - timedelta(days=30)
        end_date = date.today()

        report = analytics_engine.generate_report(start_date, end_date)

        assert report["period"]["start_date"] == start_date.isoformat()
        assert report["period"]["end_date"] == end_date.isoformat()
        assert report["period"]["days"] == 31

        assert report["overview"]["total_scans"] > 0
        assert report["overview"]["unique_users"] == 3
        assert report["overview"]["threats_detected"] > 0

        assert report["performance"]["avg_total_latency_ms"] > 0

    def test_l1_l2_detection_tracking(self, analytics_engine, sample_events):
        """Test L1 vs L2 detection tracking."""
        stats = analytics_engine.get_user_stats("user_2")

        # User 2 has mixed L1/L2 usage
        assert stats.l1_detections + stats.l2_detections == stats.total_scans
        assert stats.l2_detections > 0  # User 2 uses L2

        # User 1 only uses L1
        stats_1 = analytics_engine.get_user_stats("user_1")
        assert stats_1.l2_detections == 0
        assert stats_1.l1_detections == stats_1.total_scans


class TestUserStats:
    """Test suite for UserStats dataclass."""

    def test_user_stats_creation(self):
        """Test creating UserStats object."""
        stats = UserStats(
            installation_id="test_id",
            total_scans=100,
            threats_detected=10,
            detection_rate=10.0
        )

        assert stats.installation_id == "test_id"
        assert stats.total_scans == 100
        assert stats.threats_detected == 10
        assert stats.detection_rate == 10.0


class TestMetricsDataclasses:
    """Test suite for metrics dataclasses."""

    def test_installation_metrics(self):
        """Test InstallationMetrics creation."""
        metrics = InstallationMetrics(
            total_installations=100,
            installations_by_os={"linux": 50, "darwin": 30, "windows": 20}
        )

        assert metrics.total_installations == 100
        assert metrics.installations_by_os["linux"] == 50

    def test_usage_metrics(self):
        """Test UsageMetrics creation."""
        metrics = UsageMetrics(
            total_scans=1000,
            scans_per_user_p50=10.0,
            scans_per_user_p95=50.0,
            threats_detected=100,
            detection_rate=10.0
        )

        assert metrics.total_scans == 1000
        assert metrics.threats_detected == 100
        assert metrics.detection_rate == 10.0

    def test_retention_metrics(self):
        """Test RetentionMetrics creation."""
        metrics = RetentionMetrics(
            dau=100,
            wau=500,
            mau=1000,
            day1_retention=80.0,
            day7_retention=50.0,
            day30_retention=30.0
        )

        assert metrics.dau == 100
        assert metrics.mau == 1000
        assert metrics.day30_retention == 30.0

    def test_performance_metrics(self):
        """Test PerformanceMetrics creation."""
        metrics = PerformanceMetrics(
            p50_latency_ms=5.0,
            p95_latency_ms=10.0,
            p99_latency_ms=15.0,
            avg_l1_latency_ms=4.0,
            avg_l2_latency_ms=12.0
        )

        assert metrics.p50_latency_ms == 5.0
        assert metrics.p95_latency_ms == 10.0
        assert metrics.avg_l1_latency_ms == 4.0
