"""Tests for ArcSight adapter.

ArcSight extends CEF with SmartConnector-specific fields.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raxe.domain.siem.config import SIEMConfig, SIEMType
from raxe.infrastructure.siem.cef.arcsight_adapter import ArcSightAdapter


@pytest.fixture
def arcsight_config() -> SIEMConfig:
    """ArcSight configuration for testing."""
    return SIEMConfig(
        siem_type=SIEMType.ARCSIGHT,
        endpoint_url="https://arcsight.example.com/receiver/v1/events",
        auth_token="test-token",
        extra={
            "smart_connector_id": "sc-001",
            "device_vendor": "RAXE",
            "device_product": "ThreatDetection",
        },
    )


@pytest.fixture
def sample_raxe_event() -> dict:
    """Sample RAXE scan event with PI threat."""
    return {
        "event_type": "scan",
        "event_id": "evt_test123",
        "timestamp": "2024-01-15T10:30:00.000Z",
        "_metadata": {
            "installation_id": "inst_abc123",
            "version": "0.9.0",
        },
        "payload": {
            "threat_detected": True,
            "prompt_hash": "sha256:abc123def456",
            "prompt_length": 156,
            "action_taken": "block",
            "mssp_id": "mssp_test",
            "customer_id": "cust_test",
            "l1": {
                "hit": True,
                "highest_severity": "CRITICAL",
                "families": ["PI"],
                "detections": [{"rule_id": "pi-001", "severity": "CRITICAL"}],
            },
        },
    }


class TestArcSightAdapterProperties:
    """Test adapter properties."""

    def test_name_is_arcsight(self, arcsight_config: SIEMConfig) -> None:
        """Adapter name is 'arcsight'."""
        adapter = ArcSightAdapter(arcsight_config)
        assert adapter.name == "arcsight"

    def test_display_name_includes_arcsight(self, arcsight_config: SIEMConfig) -> None:
        """Display name mentions ArcSight."""
        adapter = ArcSightAdapter(arcsight_config)
        assert "ArcSight" in adapter.display_name


class TestArcSightExtensions:
    """Test ArcSight-specific CEF extensions."""

    def test_includes_device_direction(
        self,
        arcsight_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """ArcSight events include deviceDirection."""
        adapter = ArcSightAdapter(arcsight_config)
        result = adapter.transform_event(sample_raxe_event)

        assert "deviceDirection=" in result["cef_message"]

    def test_includes_category(
        self,
        arcsight_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """ArcSight events include ArcSight category."""
        adapter = ArcSightAdapter(arcsight_config)
        result = adapter.transform_event(sample_raxe_event)

        # PI family maps to /Security/Attack/Injection
        assert "cat=" in result["cef_message"]

    def test_category_maps_pi_to_injection(
        self,
        arcsight_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """PI family maps to /Security/Attack/Injection."""
        adapter = ArcSightAdapter(arcsight_config)
        result = adapter.transform_event(sample_raxe_event)

        assert "/Security/Attack/Injection" in result["cef_message"]

    def test_includes_device_host(
        self,
        arcsight_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """ArcSight events include device host info."""
        adapter = ArcSightAdapter(arcsight_config)
        result = adapter.transform_event(sample_raxe_event)

        # Should include dvchost or dvc
        cef = result["cef_message"]
        assert "dvchost=" in cef or "dvc=" in cef


class TestArcSightFamilyMapping:
    """Test threat family to ArcSight category mapping."""

    def test_jailbreak_maps_correctly(self, arcsight_config: SIEMConfig) -> None:
        """JB family maps to /Security/Attack/Jailbreak."""
        event = {
            "event_type": "scan",
            "timestamp": "2024-01-15T10:30:00.000Z",
            "payload": {
                "threat_detected": True,
                "l1": {
                    "highest_severity": "HIGH",
                    "families": ["JB"],
                    "detections": [{"rule_id": "jb-001"}],
                },
            },
        }
        adapter = ArcSightAdapter(arcsight_config)
        result = adapter.transform_event(event)

        assert "/Security/Attack/Jailbreak" in result["cef_message"]

    def test_data_exfil_maps_correctly(self, arcsight_config: SIEMConfig) -> None:
        """DE family maps to /Security/DataLoss/Exfiltration."""
        event = {
            "event_type": "scan",
            "timestamp": "2024-01-15T10:30:00.000Z",
            "payload": {
                "threat_detected": True,
                "l1": {
                    "highest_severity": "HIGH",
                    "families": ["DE"],
                    "detections": [{"rule_id": "de-001"}],
                },
            },
        }
        adapter = ArcSightAdapter(arcsight_config)
        result = adapter.transform_event(event)

        assert "/Security/DataLoss/Exfiltration" in result["cef_message"]


class TestArcSightHTTPSend:
    """Test HTTP sending with ArcSight specifics."""

    @patch("requests.Session")
    def test_send_uses_http(
        self,
        mock_session_class: MagicMock,
        arcsight_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """ArcSight adapter sends via HTTP."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        adapter = ArcSightAdapter(arcsight_config)
        transformed = adapter.transform_event(sample_raxe_event)
        result = adapter.send_event(transformed)

        assert result.success is True
        mock_session.post.assert_called_once()


class TestArcSightConfiguration:
    """Test ArcSight-specific configuration."""

    def test_uses_smart_connector_id(self, arcsight_config: SIEMConfig) -> None:
        """Adapter uses SmartConnector ID from config."""
        adapter = ArcSightAdapter(arcsight_config)
        assert adapter.smart_connector_id == "sc-001"

    def test_uses_custom_device_vendor(self) -> None:
        """Adapter uses custom device vendor."""
        config = SIEMConfig(
            siem_type=SIEMType.ARCSIGHT,
            endpoint_url="https://arcsight.example.com/",
            auth_token="test",
            extra={"device_vendor": "CustomVendor"},
        )
        adapter = ArcSightAdapter(config)

        event = {
            "event_type": "scan",
            "timestamp": "2024-01-15T10:30:00.000Z",
            "payload": {"l1": {"highest_severity": "HIGH"}},
        }
        result = adapter.transform_event(event)

        assert "|CustomVendor|" in result["cef_message"]

    def test_inherits_from_cef_http(self, arcsight_config: SIEMConfig) -> None:
        """ArcSight adapter extends CEF HTTP adapter."""
        from raxe.infrastructure.siem.cef.http_adapter import CEFHTTPAdapter

        adapter = ArcSightAdapter(arcsight_config)
        assert isinstance(adapter, CEFHTTPAdapter)
