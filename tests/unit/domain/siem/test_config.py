"""Tests for SIEM configuration models."""

import pytest

from raxe.domain.siem.config import SIEMConfig, SIEMType


class TestSIEMType:
    """Tests for SIEMType enum."""

    def test_valid_types(self):
        """Test all valid SIEM types."""
        assert SIEMType.SPLUNK.value == "splunk"
        assert SIEMType.CROWDSTRIKE.value == "crowdstrike"
        assert SIEMType.SENTINEL.value == "sentinel"
        assert SIEMType.CUSTOM.value == "custom"

    def test_from_string_lowercase(self):
        """Test creating from lowercase string."""
        assert SIEMType.from_string("splunk") == SIEMType.SPLUNK
        assert SIEMType.from_string("crowdstrike") == SIEMType.CROWDSTRIKE
        assert SIEMType.from_string("sentinel") == SIEMType.SENTINEL

    def test_from_string_case_insensitive(self):
        """Test case insensitivity."""
        assert SIEMType.from_string("SPLUNK") == SIEMType.SPLUNK
        assert SIEMType.from_string("Splunk") == SIEMType.SPLUNK
        assert SIEMType.from_string("CrowdStrike") == SIEMType.CROWDSTRIKE

    def test_from_string_invalid(self):
        """Test error on invalid type."""
        with pytest.raises(ValueError, match="Invalid SIEM type"):
            SIEMType.from_string("invalid")


class TestSIEMConfig:
    """Tests for SIEMConfig dataclass."""

    def test_create_valid_config(self):
        """Test creating valid configuration."""
        config = SIEMConfig(
            siem_type=SIEMType.SPLUNK,
            endpoint_url="https://splunk.example.com:8088/services/collector/event",
            auth_token="test-token",
        )

        assert config.siem_type == SIEMType.SPLUNK
        assert config.endpoint_url == "https://splunk.example.com:8088/services/collector/event"
        assert config.auth_token == "test-token"
        assert config.enabled is True
        assert config.batch_size == 100
        assert config.flush_interval_seconds == 10
        assert config.retry_count == 3
        assert config.timeout_seconds == 30

    def test_create_with_custom_values(self):
        """Test creating with custom configuration values."""
        config = SIEMConfig(
            siem_type=SIEMType.CROWDSTRIKE,
            endpoint_url="https://logscale.example.com/api/v1/ingest/hec",
            auth_token="token",
            enabled=False,
            batch_size=50,
            flush_interval_seconds=5,
            retry_count=5,
            timeout_seconds=60,
        )

        assert config.enabled is False
        assert config.batch_size == 50
        assert config.flush_interval_seconds == 5
        assert config.retry_count == 5
        assert config.timeout_seconds == 60

    def test_https_required_for_production(self):
        """Test that HTTPS is required for non-localhost URLs."""
        with pytest.raises(ValueError, match="must use HTTPS"):
            SIEMConfig(
                siem_type=SIEMType.SPLUNK,
                endpoint_url="http://splunk.example.com/event",
                auth_token="token",
            )

    def test_localhost_http_allowed(self):
        """Test that HTTP is allowed for localhost."""
        # Should not raise
        config = SIEMConfig(
            siem_type=SIEMType.SPLUNK,
            endpoint_url="http://localhost:8088/services/collector/event",
            auth_token="token",
        )
        assert config.endpoint_url.startswith("http://localhost")

    def test_127_0_0_1_http_allowed(self):
        """Test that HTTP is allowed for 127.0.0.1."""
        config = SIEMConfig(
            siem_type=SIEMType.SPLUNK,
            endpoint_url="http://127.0.0.1:8088/services/collector/event",
            auth_token="token",
        )
        assert "127.0.0.1" in config.endpoint_url

    def test_empty_endpoint_url_rejected(self):
        """Test that empty endpoint URL is rejected."""
        with pytest.raises(ValueError, match="endpoint_url is required"):
            SIEMConfig(
                siem_type=SIEMType.SPLUNK,
                endpoint_url="",
                auth_token="token",
            )

    def test_empty_auth_token_rejected(self):
        """Test that empty auth token is rejected."""
        with pytest.raises(ValueError, match="auth_token is required"):
            SIEMConfig(
                siem_type=SIEMType.SPLUNK,
                endpoint_url="https://splunk.example.com/event",
                auth_token="",
            )

    def test_batch_size_validation(self):
        """Test batch_size bounds validation."""
        with pytest.raises(ValueError, match="batch_size must be between"):
            SIEMConfig(
                siem_type=SIEMType.SPLUNK,
                endpoint_url="https://splunk.example.com/event",
                auth_token="token",
                batch_size=0,
            )

        with pytest.raises(ValueError, match="batch_size must be between"):
            SIEMConfig(
                siem_type=SIEMType.SPLUNK,
                endpoint_url="https://splunk.example.com/event",
                auth_token="token",
                batch_size=1001,
            )

    def test_flush_interval_validation(self):
        """Test flush_interval_seconds bounds validation."""
        with pytest.raises(ValueError, match="flush_interval_seconds must be between"):
            SIEMConfig(
                siem_type=SIEMType.SPLUNK,
                endpoint_url="https://splunk.example.com/event",
                auth_token="token",
                flush_interval_seconds=0,
            )

    def test_retry_count_validation(self):
        """Test retry_count bounds validation."""
        with pytest.raises(ValueError, match="retry_count must be between"):
            SIEMConfig(
                siem_type=SIEMType.SPLUNK,
                endpoint_url="https://splunk.example.com/event",
                auth_token="token",
                retry_count=11,
            )

    def test_timeout_validation(self):
        """Test timeout_seconds bounds validation."""
        with pytest.raises(ValueError, match="timeout_seconds must be between"):
            SIEMConfig(
                siem_type=SIEMType.SPLUNK,
                endpoint_url="https://splunk.example.com/event",
                auth_token="token",
                timeout_seconds=3,
            )


class TestSIEMConfigSplunkProperties:
    """Tests for Splunk-specific configuration properties."""

    def test_splunk_defaults(self):
        """Test default Splunk properties."""
        config = SIEMConfig(
            siem_type=SIEMType.SPLUNK,
            endpoint_url="https://splunk.example.com/event",
            auth_token="token",
        )

        assert config.splunk_index is None
        assert config.splunk_source == "raxe:security"
        assert config.splunk_sourcetype == "raxe:scan"

    def test_splunk_custom_values(self):
        """Test custom Splunk properties via extra."""
        config = SIEMConfig(
            siem_type=SIEMType.SPLUNK,
            endpoint_url="https://splunk.example.com/event",
            auth_token="token",
            extra={
                "index": "security_alerts",
                "source": "raxe-agent",
                "sourcetype": "raxe:threat",
            },
        )

        assert config.splunk_index == "security_alerts"
        assert config.splunk_source == "raxe-agent"
        assert config.splunk_sourcetype == "raxe:threat"


class TestSIEMConfigCrowdStrikeProperties:
    """Tests for CrowdStrike-specific configuration properties."""

    def test_crowdstrike_defaults(self):
        """Test default CrowdStrike properties."""
        config = SIEMConfig(
            siem_type=SIEMType.CROWDSTRIKE,
            endpoint_url="https://logscale.example.com/api/v1/ingest/hec",
            auth_token="token",
        )

        assert config.crowdstrike_repository is None
        assert config.crowdstrike_parser == "raxe"

    def test_crowdstrike_custom_values(self):
        """Test custom CrowdStrike properties via extra."""
        config = SIEMConfig(
            siem_type=SIEMType.CROWDSTRIKE,
            endpoint_url="https://logscale.example.com/api/v1/ingest/hec",
            auth_token="token",
            extra={
                "repository": "security-events",
                "parser": "raxe-threat",
            },
        )

        assert config.crowdstrike_repository == "security-events"
        assert config.crowdstrike_parser == "raxe-threat"


class TestSIEMConfigSentinelProperties:
    """Tests for Sentinel-specific configuration properties."""

    def test_sentinel_defaults(self):
        """Test default Sentinel properties."""
        config = SIEMConfig(
            siem_type=SIEMType.SENTINEL,
            endpoint_url="https://workspace.ods.opinsights.azure.com/api/logs",
            auth_token="shared-key",
        )

        assert config.sentinel_workspace_id is None
        assert config.sentinel_log_type == "RaxeThreatDetection"

    def test_sentinel_custom_values(self):
        """Test custom Sentinel properties via extra."""
        config = SIEMConfig(
            siem_type=SIEMType.SENTINEL,
            endpoint_url="https://workspace.ods.opinsights.azure.com/api/logs",
            auth_token="shared-key",
            extra={
                "workspace_id": "abc-123-def",
                "log_type": "RaxeSecurityAlerts",
            },
        )

        assert config.sentinel_workspace_id == "abc-123-def"
        assert config.sentinel_log_type == "RaxeSecurityAlerts"


class TestSIEMConfigSerialization:
    """Tests for SIEMConfig serialization."""

    def test_to_dict(self):
        """Test converting to dictionary."""
        config = SIEMConfig(
            siem_type=SIEMType.SPLUNK,
            endpoint_url="https://splunk.example.com/event",
            auth_token="token",
            batch_size=50,
            extra={"index": "test"},
        )

        data = config.to_dict()

        assert data["siem_type"] == "splunk"
        assert data["endpoint_url"] == "https://splunk.example.com/event"
        assert data["auth_token"] == "token"
        assert data["batch_size"] == 50
        assert data["extra"]["index"] == "test"

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "siem_type": "crowdstrike",
            "endpoint_url": "https://logscale.example.com/api/v1/ingest/hec",
            "auth_token": "token",
            "enabled": False,
            "batch_size": 75,
            "extra": {"repository": "security"},
        }

        config = SIEMConfig.from_dict(data)

        assert config.siem_type == SIEMType.CROWDSTRIKE
        assert config.endpoint_url == "https://logscale.example.com/api/v1/ingest/hec"
        assert config.enabled is False
        assert config.batch_size == 75
        assert config.crowdstrike_repository == "security"

    def test_round_trip_serialization(self):
        """Test that to_dict -> from_dict preserves data."""
        original = SIEMConfig(
            siem_type=SIEMType.SENTINEL,
            endpoint_url="https://workspace.ods.opinsights.azure.com/api/logs",
            auth_token="key",
            enabled=True,
            batch_size=200,
            flush_interval_seconds=15,
            retry_count=5,
            timeout_seconds=45,
            extra={"workspace_id": "ws-123", "log_type": "Custom"},
        )

        data = original.to_dict()
        restored = SIEMConfig.from_dict(data)

        assert restored.siem_type == original.siem_type
        assert restored.endpoint_url == original.endpoint_url
        assert restored.auth_token == original.auth_token
        assert restored.enabled == original.enabled
        assert restored.batch_size == original.batch_size
        assert restored.flush_interval_seconds == original.flush_interval_seconds
        assert restored.retry_count == original.retry_count
        assert restored.timeout_seconds == original.timeout_seconds
        assert restored.extra == original.extra
