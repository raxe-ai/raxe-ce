"""Tests for SIEM adapter implementations."""

from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from raxe.domain.siem.config import SIEMConfig, SIEMType
from raxe.infrastructure.siem import (
    CrowdStrikeAdapter,
    SentinelAdapter,
    SplunkHECAdapter,
    create_siem_adapter,
)


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
                "voting": {"confidence": 0.85},
            },
            "_mssp_data": {
                "prompt_text": "Test prompt",
                "matched_text": ["match1"],
            },
        },
        "_metadata": {
            "version": "0.5.0",
            "installation_id": "inst_xyz",
        },
    }


class TestSplunkHECAdapter:
    """Tests for Splunk HEC adapter."""

    @pytest.fixture
    def splunk_config(self) -> SIEMConfig:
        """Create Splunk configuration."""
        return SIEMConfig(
            siem_type=SIEMType.SPLUNK,
            endpoint_url="https://splunk.example.com:8088/services/collector/event",
            auth_token="test-hec-token",
            extra={
                "index": "security",
                "source": "raxe-agent",
                "sourcetype": "raxe:scan",
            },
        )

    @pytest.fixture
    def adapter(self, splunk_config: SIEMConfig) -> SplunkHECAdapter:
        """Create Splunk adapter."""
        return SplunkHECAdapter(splunk_config)

    def test_adapter_properties(self, adapter: SplunkHECAdapter):
        """Test adapter name and display name."""
        assert adapter.name == "splunk"
        assert adapter.display_name == "Splunk (HEC)"

    def test_transform_event_structure(self, adapter: SplunkHECAdapter, sample_event: dict):
        """Test event transformation to Splunk HEC format."""
        transformed = adapter.transform_event(sample_event)

        # Check HEC envelope
        assert "time" in transformed
        assert "host" in transformed
        assert "source" in transformed
        assert "sourcetype" in transformed
        assert "event" in transformed
        assert "index" in transformed

        # Check time is epoch
        assert isinstance(transformed["time"], float)
        assert 1705314500 < transformed["time"] < 1705314700

        # Check source fields
        assert transformed["source"] == "raxe-agent"
        assert transformed["sourcetype"] == "raxe:scan"
        assert transformed["index"] == "security"

    def test_transform_event_content(self, adapter: SplunkHECAdapter, sample_event: dict):
        """Test event content in Splunk format."""
        transformed = adapter.transform_event(sample_event)
        event_data = transformed["event"]

        assert event_data["event_type"] == "scan"
        assert event_data["event_id"] == "evt_abc123"
        assert event_data["severity"] == "HIGH"
        assert event_data["threat_detected"] is True
        assert event_data["rule_ids"] == ["pi-001", "jb-002"]
        assert event_data["families"] == ["PI", "JB"]
        assert event_data["mssp_id"] == "mssp_test"
        assert event_data["customer_id"] == "cust_123"

    def test_transform_event_includes_mssp_data(
        self, adapter: SplunkHECAdapter, sample_event: dict
    ):
        """Test that MSSP data is included when present."""
        transformed = adapter.transform_event(sample_event)
        assert "_mssp_data" in transformed["event"]
        assert transformed["event"]["_mssp_data"]["prompt_text"] == "Test prompt"

    def test_transform_event_no_index(self, sample_event: dict):
        """Test transformation when no index is configured."""
        config = SIEMConfig(
            siem_type=SIEMType.SPLUNK,
            endpoint_url="https://splunk.example.com:8088/services/collector/event",
            auth_token="token",
        )
        adapter = SplunkHECAdapter(config)
        transformed = adapter.transform_event(sample_event)

        assert "index" not in transformed

    @patch("raxe.infrastructure.siem.splunk.requests.Session")
    def test_send_event_success(
        self, mock_session_class: Mock, adapter: SplunkHECAdapter, sample_event: dict
    ):
        """Test successful event sending."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        transformed = adapter.transform_event(sample_event)
        result = adapter.send_event(transformed)

        assert result.success is True
        assert result.status_code == 200
        assert result.events_accepted == 1

    @patch("raxe.infrastructure.siem.splunk.requests.Session")
    def test_send_batch_success(
        self, mock_session_class: Mock, adapter: SplunkHECAdapter, sample_event: dict
    ):
        """Test successful batch sending."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        events = [adapter.transform_event(sample_event) for _ in range(5)]
        result = adapter.send_batch(events)

        assert result.success is True
        assert result.events_accepted == 5

    @patch("raxe.infrastructure.siem.splunk.requests.Session")
    def test_send_event_error(
        self, mock_session_class: Mock, adapter: SplunkHECAdapter, sample_event: dict
    ):
        """Test error handling on send failure."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"text": "Invalid format", "code": 6}
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        transformed = adapter.transform_event(sample_event)
        result = adapter.send_event(transformed)

        assert result.success is False
        assert result.status_code == 400
        assert "Invalid format" in result.error_message

    @patch("raxe.infrastructure.siem.splunk.requests.Session")
    def test_send_event_timeout(
        self, mock_session_class: Mock, adapter: SplunkHECAdapter, sample_event: dict
    ):
        """Test timeout handling."""
        import requests

        mock_session = MagicMock()
        mock_session.post.side_effect = requests.Timeout("Connection timed out")
        mock_session_class.return_value = mock_session

        transformed = adapter.transform_event(sample_event)
        result = adapter.send_event(transformed)

        assert result.success is False
        assert "timeout" in result.error_message.lower()

    @patch("raxe.infrastructure.siem.splunk.requests.Session")
    def test_health_check_success(self, mock_session_class: Mock, adapter: SplunkHECAdapter):
        """Test health check when endpoint is healthy."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        assert adapter.health_check() is True


class TestCrowdStrikeAdapter:
    """Tests for CrowdStrike Falcon LogScale adapter."""

    @pytest.fixture
    def crowdstrike_config(self) -> SIEMConfig:
        """Create CrowdStrike configuration."""
        return SIEMConfig(
            siem_type=SIEMType.CROWDSTRIKE,
            endpoint_url="https://cloud.us.humio.com/api/v1/ingest/hec",
            auth_token="test-ingest-token",
            extra={
                "repository": "security-events",
                "parser": "raxe-threat",
            },
        )

    @pytest.fixture
    def adapter(self, crowdstrike_config: SIEMConfig) -> CrowdStrikeAdapter:
        """Create CrowdStrike adapter."""
        return CrowdStrikeAdapter(crowdstrike_config)

    def test_adapter_properties(self, adapter: CrowdStrikeAdapter):
        """Test adapter name and display name."""
        assert adapter.name == "crowdstrike"
        assert adapter.display_name == "CrowdStrike Falcon LogScale"

    def test_transform_event_structure(self, adapter: CrowdStrikeAdapter, sample_event: dict):
        """Test event transformation to LogScale format."""
        transformed = adapter.transform_event(sample_event)

        # Check HEC envelope
        assert "time" in transformed
        assert "source" in transformed
        assert "sourcetype" in transformed
        assert "event" in transformed

        # Check time is epoch milliseconds
        assert isinstance(transformed["time"], int)
        assert 1705314500000 < transformed["time"] < 1705314700000

    def test_transform_event_content(self, adapter: CrowdStrikeAdapter, sample_event: dict):
        """Test event content in LogScale format."""
        transformed = adapter.transform_event(sample_event)
        event_data = transformed["event"]

        # Check parser tags
        assert "@tags" in event_data
        assert "raxe-threat" in event_data["@tags"]

        # Check nested structure
        assert event_data["severity"] == "high"  # Mapped to LogScale format
        assert event_data["mssp"]["mssp_id"] == "mssp_test"
        assert event_data["l1"]["hit"] is True
        assert event_data["l2"]["confidence"] == 0.85

    def test_severity_mapping(self, adapter: CrowdStrikeAdapter):
        """Test RAXE to CrowdStrike severity mapping."""
        assert adapter.SEVERITY_MAP["none"] == "informational"
        assert adapter.SEVERITY_MAP["LOW"] == "low"
        assert adapter.SEVERITY_MAP["MEDIUM"] == "medium"
        assert adapter.SEVERITY_MAP["HIGH"] == "high"
        assert adapter.SEVERITY_MAP["CRITICAL"] == "critical"

    @patch("raxe.infrastructure.siem.crowdstrike.requests.Session")
    def test_send_batch_success(
        self, mock_session_class: Mock, adapter: CrowdStrikeAdapter, sample_event: dict
    ):
        """Test successful batch sending to LogScale."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        events = [adapter.transform_event(sample_event) for _ in range(3)]
        result = adapter.send_batch(events)

        assert result.success is True
        assert result.events_accepted == 3


class TestSentinelAdapter:
    """Tests for Microsoft Sentinel adapter."""

    @pytest.fixture
    def sentinel_config(self) -> SIEMConfig:
        """Create Sentinel configuration."""
        return SIEMConfig(
            siem_type=SIEMType.SENTINEL,
            endpoint_url="https://workspace123.ods.opinsights.azure.com/api/logs",
            auth_token="dGVzdC1zaGFyZWQta2V5",  # base64 encoded test key
            extra={
                "workspace_id": "workspace123",
                "log_type": "RaxeThreatDetection",
            },
        )

    @pytest.fixture
    def adapter(self, sentinel_config: SIEMConfig) -> SentinelAdapter:
        """Create Sentinel adapter."""
        return SentinelAdapter(sentinel_config)

    def test_adapter_properties(self, adapter: SentinelAdapter):
        """Test adapter name and display name."""
        assert adapter.name == "sentinel"
        assert adapter.display_name == "Microsoft Sentinel"

    def test_transform_event_structure(self, adapter: SentinelAdapter, sample_event: dict):
        """Test event transformation to Sentinel format."""
        transformed = adapter.transform_event(sample_event)

        # Check required fields
        assert "TimeGenerated" in transformed
        assert "EventType" in transformed
        assert "EventId" in transformed

        # Sentinel uses flat structure with PascalCase
        assert "ThreatDetected" in transformed
        assert "Severity" in transformed
        assert "MsspId" in transformed

    def test_transform_event_content(self, adapter: SentinelAdapter, sample_event: dict):
        """Test event content in Sentinel format."""
        transformed = adapter.transform_event(sample_event)

        assert transformed["TimeGenerated"] == "2024-01-15T10:30:00Z"
        assert transformed["EventType"] == "scan"
        assert transformed["ThreatDetected"] is True
        assert transformed["Severity"] == "HIGH"
        assert transformed["MsspId"] == "mssp_test"
        assert transformed["L1Hit"] is True
        assert transformed["L2Confidence"] == 0.85

    def test_transform_event_json_fields(self, adapter: SentinelAdapter, sample_event: dict):
        """Test that complex fields are JSON serialized."""
        import json

        transformed = adapter.transform_event(sample_event)

        # RuleIds and Families should be JSON strings
        rule_ids = json.loads(transformed["RuleIds"])
        assert rule_ids == ["pi-001", "jb-002"]

        families = json.loads(transformed["Families"])
        assert families == ["PI", "JB"]

    def test_build_signature(self, adapter: SentinelAdapter):
        """Test Azure SharedKey signature building."""
        date = "Mon, 15 Jan 2024 10:30:00 GMT"
        signature = adapter._build_signature(date=date, content_length=100)

        # Should start with SharedKey format
        assert signature.startswith("SharedKey workspace123:")
        # Should have base64 encoded signature
        assert len(signature.split(":")[1]) > 20

    @patch("raxe.infrastructure.siem.sentinel.requests.post")
    def test_send_batch_success(
        self, mock_post: Mock, adapter: SentinelAdapter, sample_event: dict
    ):
        """Test successful batch sending to Sentinel."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        events = [adapter.transform_event(sample_event) for _ in range(3)]
        result = adapter.send_batch(events)

        assert result.success is True
        assert result.events_accepted == 3

        # Verify request headers
        call_args = mock_post.call_args
        headers = call_args.kwargs["headers"]
        assert "Authorization" in headers
        assert headers["Log-Type"] == "RaxeThreatDetection"
        assert "x-ms-date" in headers

    @patch("raxe.infrastructure.siem.sentinel.requests.post")
    def test_send_batch_unauthorized(
        self, mock_post: Mock, adapter: SentinelAdapter, sample_event: dict
    ):
        """Test unauthorized response handling."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid authorization"
        mock_post.return_value = mock_response

        events = [adapter.transform_event(sample_event)]
        result = adapter.send_batch(events)

        assert result.success is False
        assert result.status_code == 401


class TestCreateSIEMAdapter:
    """Tests for SIEM adapter factory function."""

    def test_create_splunk_adapter(self):
        """Test creating Splunk adapter."""
        config = SIEMConfig(
            siem_type=SIEMType.SPLUNK,
            endpoint_url="https://splunk.example.com:8088/services/collector/event",
            auth_token="token",
        )
        adapter = create_siem_adapter(config)

        assert isinstance(adapter, SplunkHECAdapter)
        assert adapter.name == "splunk"

    def test_create_crowdstrike_adapter(self):
        """Test creating CrowdStrike adapter."""
        config = SIEMConfig(
            siem_type=SIEMType.CROWDSTRIKE,
            endpoint_url="https://humio.example.com/api/v1/ingest/hec",
            auth_token="token",
        )
        adapter = create_siem_adapter(config)

        assert isinstance(adapter, CrowdStrikeAdapter)
        assert adapter.name == "crowdstrike"

    def test_create_sentinel_adapter(self):
        """Test creating Sentinel adapter."""
        config = SIEMConfig(
            siem_type=SIEMType.SENTINEL,
            endpoint_url="https://workspace.ods.opinsights.azure.com/api/logs",
            auth_token="c2hhcmVkLWtleQ==",
            extra={"workspace_id": "test"},
        )
        adapter = create_siem_adapter(config)

        assert isinstance(adapter, SentinelAdapter)
        assert adapter.name == "sentinel"

    def test_create_unsupported_type(self):
        """Test error on unsupported SIEM type."""
        config = SIEMConfig(
            siem_type=SIEMType.CUSTOM,
            endpoint_url="https://custom.example.com/events",
            auth_token="token",
        )

        with pytest.raises(ValueError, match="Unsupported SIEM type"):
            create_siem_adapter(config)
