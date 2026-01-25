"""Tests for dashboard data provider."""

from __future__ import annotations

from datetime import datetime, timezone

from raxe.cli.dashboard.data_provider import (
    AlertItem,
    DashboardData,
    DashboardDataProvider,
)


class TestAlertItem:
    """Tests for AlertItem dataclass."""

    def test_alert_item_creation(self):
        """Test AlertItem can be created with required fields."""
        now = datetime.now(timezone.utc)
        alert = AlertItem(
            scan_id=1,
            timestamp=now,
            severity="HIGH",
            rule_ids=["pi-001"],
            detection_count=1,
            prompt_preview="Test prompt...",
            prompt_hash="sha256:abc123",
        )

        assert alert.scan_id == 1
        assert alert.severity == "HIGH"
        assert alert.rule_ids == ["pi-001"]
        assert alert.confidence == 0.0  # Default

    def test_alert_item_with_optional_fields(self):
        """Test AlertItem with all fields."""
        now = datetime.now(timezone.utc)
        alert = AlertItem(
            scan_id=1,
            timestamp=now,
            severity="CRITICAL",
            rule_ids=["pi-001", "pi-002"],
            detection_count=2,
            prompt_preview="Test prompt...",
            prompt_hash="sha256:abc123",
            confidence=0.95,
            prompt_text="Full prompt text here",
            event_id="evt_123",
            descriptions=["Rule 1", "Rule 2"],
            l1_detections=1,
            l2_detections=1,
        )

        assert alert.confidence == 0.95
        assert alert.prompt_text == "Full prompt text here"
        assert len(alert.descriptions) == 2


class TestDashboardData:
    """Tests for DashboardData dataclass."""

    def test_dashboard_data_defaults(self):
        """Test DashboardData has sensible defaults."""
        now = datetime.now(timezone.utc)
        data = DashboardData(last_refresh=now)

        assert data.total_scans_today == 0
        assert data.total_threats_today == 0
        assert isinstance(data.threats_by_severity, dict)
        assert data.recent_alerts == []
        # Hourly lists default to 24 zeros (one per hour)
        assert len(data.hourly_scans) == 24
        assert len(data.hourly_threats) == 24

    def test_dashboard_data_with_values(self):
        """Test DashboardData with real values."""
        now = datetime.now(timezone.utc)
        data = DashboardData(
            total_scans_today=100,
            total_threats_today=5,
            threats_by_severity={"CRITICAL": 1, "HIGH": 2, "MEDIUM": 2},
            recent_alerts=[],
            hourly_scans=[10] * 24,
            hourly_threats=[1] * 24,
            avg_latency_ms=5.5,
            p95_latency_ms=12.0,
            l1_avg_ms=3.0,
            l2_avg_ms=8.0,
            rules_loaded=462,
            ml_model_loaded=True,
            last_refresh=now,
        )

        assert data.total_scans_today == 100
        assert data.avg_latency_ms == 5.5
        assert data.ml_model_loaded is True


class TestDashboardDataProvider:
    """Tests for DashboardDataProvider."""

    def test_provider_initialization(self):
        """Test provider can be initialized."""
        provider = DashboardDataProvider()
        assert provider is not None

    def test_provider_get_data(self):
        """Test provider returns DashboardData."""
        provider = DashboardDataProvider()
        data = provider.get_data()

        assert isinstance(data, DashboardData)
        assert data.last_refresh is not None

    def test_provider_caching(self):
        """Test provider caches data."""
        provider = DashboardDataProvider()

        # First call
        data1 = provider.get_data()
        # Second call (should be cached)
        data2 = provider.get_data()

        # Both should be the same object if cached
        assert data1.last_refresh == data2.last_refresh

    def test_provider_force_refresh(self):
        """Test provider can force refresh."""
        provider = DashboardDataProvider()

        data1 = provider.get_data()
        provider.force_refresh()
        data2 = provider.get_data(force_refresh=True)

        # Force refresh should update the data
        assert data2.last_refresh >= data1.last_refresh

    def test_provider_get_alert_details(self):
        """Test provider can get alert details."""
        provider = DashboardDataProvider()
        data = provider.get_data()

        if data.recent_alerts:
            # If there are alerts, we should be able to get details
            alert = provider.get_alert_details(data.recent_alerts[0].scan_id)
            assert alert is not None
            assert alert.scan_id == data.recent_alerts[0].scan_id

    def test_provider_get_alert_details_invalid_id(self):
        """Test provider returns None for invalid alert ID."""
        provider = DashboardDataProvider()

        # Very unlikely to exist
        alert = provider.get_alert_details(999999999)
        assert alert is None
