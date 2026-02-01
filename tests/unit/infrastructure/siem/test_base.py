"""Tests for SIEM base adapter."""

from typing import Any

import pytest

from raxe.domain.siem.config import SIEMConfig, SIEMType
from raxe.infrastructure.siem.base import (
    BaseSIEMAdapter,
    SIEMAdapter,
    SIEMDeliveryResult,
)


class TestSIEMDeliveryResult:
    """Tests for SIEMDeliveryResult dataclass."""

    def test_success_result(self):
        """Test successful delivery result."""
        result = SIEMDeliveryResult(
            success=True,
            status_code=200,
            events_accepted=10,
        )

        assert result.success is True
        assert result.status_code == 200
        assert result.events_accepted == 10
        assert result.events_rejected == 0
        assert result.error_message is None

    def test_failure_result(self):
        """Test failed delivery result."""
        result = SIEMDeliveryResult(
            success=False,
            status_code=500,
            error_message="Internal server error",
        )

        assert result.success is False
        assert result.status_code == 500
        assert result.error_message == "Internal server error"

    def test_partial_success_result(self):
        """Test partial success (some events rejected)."""
        result = SIEMDeliveryResult(
            success=True,
            status_code=200,
            events_accepted=8,
            events_rejected=2,
        )

        assert result.success is True
        assert result.events_accepted == 8
        assert result.events_rejected == 2

    def test_rate_limited_result(self):
        """Test rate limiting with retry_after."""
        result = SIEMDeliveryResult(
            success=False,
            status_code=429,
            retry_after=60,
            error_message="Rate limited",
        )

        assert result.success is False
        assert result.retry_after == 60

    def test_result_is_frozen(self):
        """Test that result is immutable (frozen dataclass)."""
        result = SIEMDeliveryResult(success=True)
        with pytest.raises(AttributeError):
            result.success = False


class ConcreteSIEMAdapter(BaseSIEMAdapter):
    """Concrete implementation for testing."""

    @property
    def name(self) -> str:
        return "test"

    @property
    def display_name(self) -> str:
        return "Test SIEM"

    def transform_event(self, event: dict[str, Any]) -> dict[str, Any]:
        return {"transformed": True, "original": event}

    def send_event(self, event: dict[str, Any]) -> SIEMDeliveryResult:
        return SIEMDeliveryResult(success=True, events_accepted=1)

    def send_batch(self, events: list[dict[str, Any]]) -> SIEMDeliveryResult:
        return SIEMDeliveryResult(success=True, events_accepted=len(events))

    def health_check(self) -> bool:
        return True


@pytest.fixture
def sample_config() -> SIEMConfig:
    """Create sample SIEM configuration."""
    return SIEMConfig(
        siem_type=SIEMType.SPLUNK,
        endpoint_url="https://splunk.example.com:8088/services/collector/event",
        auth_token="test-token",
    )


@pytest.fixture
def adapter(sample_config: SIEMConfig) -> ConcreteSIEMAdapter:
    """Create test adapter instance."""
    return ConcreteSIEMAdapter(sample_config)


@pytest.fixture
def sample_event() -> dict[str, Any]:
    """Create sample RAXE telemetry event."""
    return {
        "event_id": "evt_abc123",
        "event_type": "scan",
        "timestamp": "2024-01-15T10:30:00Z",
        "priority": "critical",
        "payload": {
            "prompt_hash": "sha256:abc123",
            "prompt_length": 100,
            "threat_detected": True,
            "scan_duration_ms": 5.2,
            "action_taken": "block",
            "entry_point": "sdk",
            "mssp_id": "mssp_test",
            "customer_id": "cust_123",
            "agent_id": "agent_456",
            "l1": {
                "hit": True,
                "highest_severity": "HIGH",
                "families": ["PI", "JB"],
                "detection_count": 2,
                "detections": [
                    {"rule_id": "pi-001", "severity": "HIGH"},
                    {"rule_id": "jb-002", "severity": "MEDIUM"},
                ],
            },
            "l2": {
                "hit": False,
                "severity": "none",
            },
        },
        "_metadata": {
            "version": "0.5.0",
            "installation_id": "inst_xyz",
        },
    }


class TestBaseSIEMAdapter:
    """Tests for BaseSIEMAdapter."""

    def test_adapter_properties(self, adapter: ConcreteSIEMAdapter):
        """Test adapter property accessors."""
        assert adapter.name == "test"
        assert adapter.display_name == "Test SIEM"

    def test_config_accessible(self, adapter: ConcreteSIEMAdapter, sample_config: SIEMConfig):
        """Test config is accessible."""
        assert adapter.config == sample_config

    def test_initial_stats(self, adapter: ConcreteSIEMAdapter):
        """Test initial statistics are zero."""
        stats = adapter.stats
        assert stats["events_sent"] == 0
        assert stats["events_failed"] == 0
        assert stats["batches_sent"] == 0
        assert stats["last_error"] is None

    def test_context_manager(self, sample_config: SIEMConfig):
        """Test context manager protocol."""
        with ConcreteSIEMAdapter(sample_config) as adapter:
            assert adapter.name == "test"
        # Should not raise after exit


class TestBaseSIEMAdapterHelpers:
    """Tests for BaseSIEMAdapter helper methods."""

    def test_extract_timestamp_epoch(self, adapter: ConcreteSIEMAdapter, sample_event: dict):
        """Test timestamp extraction."""
        epoch = adapter._extract_timestamp_epoch(sample_event)

        # 2024-01-15T10:30:00Z should be around 1705314600
        assert 1705314500 < epoch < 1705314700

    def test_extract_timestamp_fallback(self, adapter: ConcreteSIEMAdapter):
        """Test fallback to current time for invalid timestamp."""
        import time

        event = {"timestamp": "invalid"}
        epoch = adapter._extract_timestamp_epoch(event)

        # Should be close to current time
        assert abs(epoch - time.time()) < 5

    def test_extract_severity_l1(self, adapter: ConcreteSIEMAdapter, sample_event: dict):
        """Test severity extraction from L1."""
        severity = adapter._extract_severity(sample_event)
        assert severity == "HIGH"

    def test_extract_severity_l2_higher(self, adapter: ConcreteSIEMAdapter):
        """Test severity uses highest from L1 and L2."""
        event = {
            "payload": {
                "l1": {"highest_severity": "MEDIUM"},
                "l2": {"severity": "CRITICAL"},
            }
        }
        severity = adapter._extract_severity(event)
        assert severity == "CRITICAL"

    def test_extract_severity_none(self, adapter: ConcreteSIEMAdapter):
        """Test severity defaults to none."""
        event = {"payload": {}}
        severity = adapter._extract_severity(event)
        assert severity == "none"

    def test_extract_rule_ids(self, adapter: ConcreteSIEMAdapter, sample_event: dict):
        """Test rule ID extraction."""
        rule_ids = adapter._extract_rule_ids(sample_event)
        assert rule_ids == ["pi-001", "jb-002"]

    def test_extract_rule_ids_empty(self, adapter: ConcreteSIEMAdapter):
        """Test empty rule ID extraction."""
        event = {"payload": {"l1": {"detections": []}}}
        rule_ids = adapter._extract_rule_ids(event)
        assert rule_ids == []

    def test_extract_families(self, adapter: ConcreteSIEMAdapter, sample_event: dict):
        """Test family extraction."""
        families = adapter._extract_families(sample_event)
        assert families == ["PI", "JB"]

    def test_extract_mssp_context(self, adapter: ConcreteSIEMAdapter, sample_event: dict):
        """Test MSSP context extraction."""
        context = adapter._extract_mssp_context(sample_event)
        assert context["mssp_id"] == "mssp_test"
        assert context["customer_id"] == "cust_123"
        assert context["agent_id"] == "agent_456"


class TestBaseSIEMAdapterStats:
    """Tests for statistics tracking."""

    def test_update_stats_success(self, adapter: ConcreteSIEMAdapter):
        """Test stats update on success."""
        result = SIEMDeliveryResult(success=True, events_accepted=5)
        adapter._update_stats(result, batch_size=5)

        assert adapter.stats["events_sent"] == 5
        assert adapter.stats["events_failed"] == 0

    def test_update_stats_failure(self, adapter: ConcreteSIEMAdapter):
        """Test stats update on failure."""
        result = SIEMDeliveryResult(success=False, error_message="Connection failed")
        adapter._update_stats(result, batch_size=3)

        assert adapter.stats["events_sent"] == 0
        assert adapter.stats["events_failed"] == 3
        assert adapter.stats["last_error"] == "Connection failed"

    def test_update_stats_partial(self, adapter: ConcreteSIEMAdapter):
        """Test stats update on partial success."""
        result = SIEMDeliveryResult(success=True, events_accepted=8, events_rejected=2)
        adapter._update_stats(result, batch_size=10)

        assert adapter.stats["events_sent"] == 8
        assert adapter.stats["events_failed"] == 2

    def test_update_stats_batch_counter(self, adapter: ConcreteSIEMAdapter):
        """Test batch counter increments for batches."""
        result = SIEMDeliveryResult(success=True, events_accepted=5)
        adapter._update_stats(result, batch_size=5)

        assert adapter.stats["batches_sent"] == 1

        adapter._update_stats(result, batch_size=5)
        assert adapter.stats["batches_sent"] == 2

    def test_update_stats_single_no_batch_count(self, adapter: ConcreteSIEMAdapter):
        """Test single event doesn't increment batch counter."""
        result = SIEMDeliveryResult(success=True, events_accepted=1)
        adapter._update_stats(result, batch_size=1)

        assert adapter.stats["batches_sent"] == 0


class TestSIEMAdapterInterface:
    """Tests for SIEM adapter interface compliance."""

    def test_cannot_instantiate_abstract(self):
        """Test that abstract base cannot be instantiated."""
        with pytest.raises(TypeError):
            SIEMAdapter()

    def test_concrete_implementation_works(self, sample_config: SIEMConfig):
        """Test that concrete implementation can be instantiated."""
        adapter = ConcreteSIEMAdapter(sample_config)
        assert adapter.name == "test"

    def test_transform_event(self, adapter: ConcreteSIEMAdapter, sample_event: dict):
        """Test event transformation."""
        transformed = adapter.transform_event(sample_event)
        assert transformed["transformed"] is True
        assert transformed["original"] == sample_event

    def test_send_event(self, adapter: ConcreteSIEMAdapter, sample_event: dict):
        """Test single event sending."""
        transformed = adapter.transform_event(sample_event)
        result = adapter.send_event(transformed)
        assert result.success is True

    def test_send_batch(self, adapter: ConcreteSIEMAdapter, sample_event: dict):
        """Test batch event sending."""
        events = [adapter.transform_event(sample_event) for _ in range(5)]
        result = adapter.send_batch(events)
        assert result.success is True
        assert result.events_accepted == 5

    def test_health_check(self, adapter: ConcreteSIEMAdapter):
        """Test health check."""
        assert adapter.health_check() is True
