"""Tests for CEF formatter.

CEF (Common Event Format) is the universal security event format.
These tests verify proper formatting according to ArcSight CEF specification.
"""

from __future__ import annotations

import pytest

from raxe.infrastructure.siem.cef.formatter import CEFFormatter


class TestCEFEscaping:
    """Test CEF character escaping rules."""

    def test_escape_cef_header_pipe(self) -> None:
        """Pipe in header must be escaped as \\|."""
        formatter = CEFFormatter()
        result = formatter._escape_header("Pipe|Test")
        assert result == "Pipe\\|Test"

    def test_escape_cef_header_backslash(self) -> None:
        """Backslash in header must be escaped as \\\\."""
        formatter = CEFFormatter()
        result = formatter._escape_header("Back\\Slash")
        assert result == "Back\\\\Slash"

    def test_escape_cef_header_multiple(self) -> None:
        """Multiple special chars in header are all escaped."""
        formatter = CEFFormatter()
        result = formatter._escape_header("A|B\\C|D")
        assert result == "A\\|B\\\\C\\|D"

    def test_escape_cef_extension_equals(self) -> None:
        """Equals in extension must be escaped as \\=."""
        formatter = CEFFormatter()
        result = formatter._escape_extension("a=b")
        assert result == "a\\=b"

    def test_escape_cef_extension_newline(self) -> None:
        """Newline in extension must be escaped as \\n."""
        formatter = CEFFormatter()
        result = formatter._escape_extension("line1\nline2")
        assert result == "line1\\nline2"

    def test_escape_cef_extension_backslash(self) -> None:
        """Backslash in extension must be escaped as \\\\."""
        formatter = CEFFormatter()
        result = formatter._escape_extension("path\\to\\file")
        assert result == "path\\\\to\\\\file"

    def test_escape_cef_extension_carriage_return(self) -> None:
        """Carriage return in extension must be escaped as \\r."""
        formatter = CEFFormatter()
        result = formatter._escape_extension("line1\rline2")
        assert result == "line1\\rline2"

    def test_escape_empty_string(self) -> None:
        """Empty strings are returned unchanged."""
        formatter = CEFFormatter()
        assert formatter._escape_header("") == ""
        assert formatter._escape_extension("") == ""


class TestCEFSeverityMapping:
    """Test RAXE severity to CEF severity mapping."""

    def test_severity_none_maps_to_0(self) -> None:
        """None/unknown severity maps to CEF 0."""
        formatter = CEFFormatter()
        assert formatter.map_severity("none") == 0

    def test_severity_low_maps_to_3(self) -> None:
        """LOW severity maps to CEF 3."""
        formatter = CEFFormatter()
        assert formatter.map_severity("LOW") == 3

    def test_severity_medium_maps_to_5(self) -> None:
        """MEDIUM severity maps to CEF 5."""
        formatter = CEFFormatter()
        assert formatter.map_severity("MEDIUM") == 5

    def test_severity_high_maps_to_7(self) -> None:
        """HIGH severity maps to CEF 7."""
        formatter = CEFFormatter()
        assert formatter.map_severity("HIGH") == 7

    def test_severity_critical_maps_to_10(self) -> None:
        """CRITICAL severity maps to CEF 10."""
        formatter = CEFFormatter()
        assert formatter.map_severity("CRITICAL") == 10

    def test_severity_case_insensitive(self) -> None:
        """Severity mapping is case-insensitive."""
        formatter = CEFFormatter()
        assert formatter.map_severity("critical") == 10
        assert formatter.map_severity("Critical") == 10
        assert formatter.map_severity("CRITICAL") == 10

    def test_unknown_severity_defaults_to_0(self) -> None:
        """Unknown severity values default to 0."""
        formatter = CEFFormatter()
        assert formatter.map_severity("unknown") == 0
        assert formatter.map_severity("INVALID") == 0


class TestCEFSyslogSeverityMapping:
    """Test CEF to syslog severity mapping."""

    def test_cef_0_maps_to_informational(self) -> None:
        """CEF 0 maps to syslog 6 (informational)."""
        formatter = CEFFormatter()
        assert formatter.map_cef_to_syslog_severity(0) == 6

    def test_cef_3_maps_to_notice(self) -> None:
        """CEF 3 (LOW) maps to syslog 5 (notice)."""
        formatter = CEFFormatter()
        assert formatter.map_cef_to_syslog_severity(3) == 5

    def test_cef_5_maps_to_warning(self) -> None:
        """CEF 5 (MEDIUM) maps to syslog 4 (warning)."""
        formatter = CEFFormatter()
        assert formatter.map_cef_to_syslog_severity(5) == 4

    def test_cef_7_maps_to_error(self) -> None:
        """CEF 7 (HIGH) maps to syslog 3 (error)."""
        formatter = CEFFormatter()
        assert formatter.map_cef_to_syslog_severity(7) == 3

    def test_cef_10_maps_to_critical(self) -> None:
        """CEF 10 (CRITICAL) maps to syslog 2 (critical)."""
        formatter = CEFFormatter()
        assert formatter.map_cef_to_syslog_severity(10) == 2


class TestCEFHeaderFormatting:
    """Test CEF header building."""

    def test_build_cef_header_basic(self) -> None:
        """CEF header has correct format: CEF:0|vendor|product|version|sig|name|sev|."""
        formatter = CEFFormatter(
            device_vendor="RAXE",
            device_product="ThreatDetection",
            device_version="1.0.0",
        )
        header = formatter._build_header(
            signature_id="pi-001",
            event_name="Prompt Injection Detected",
            severity=7,
        )
        assert header == "CEF:0|RAXE|ThreatDetection|1.0.0|pi-001|Prompt Injection Detected|7|"

    def test_build_cef_header_escapes_special_chars(self) -> None:
        """CEF header escapes pipes and backslashes."""
        formatter = CEFFormatter(
            device_vendor="RAXE|Inc",
            device_product="Threat\\Detection",
            device_version="1.0",
        )
        header = formatter._build_header(
            signature_id="rule|001",
            event_name="Test|Event",
            severity=5,
        )
        assert "RAXE\\|Inc" in header
        assert "Threat\\\\Detection" in header
        assert "rule\\|001" in header


class TestCEFExtensionFormatting:
    """Test CEF extension (key=value pairs) building."""

    def test_build_extension_single_field(self) -> None:
        """Single field formatted as key=value."""
        formatter = CEFFormatter()
        ext = formatter._build_extension({"msg": "Test message"})
        assert ext == "msg=Test message"

    def test_build_extension_multiple_fields(self) -> None:
        """Multiple fields are space-separated."""
        formatter = CEFFormatter()
        ext = formatter._build_extension(
            {
                "src": "192.168.1.1",
                "dst": "10.0.0.1",
            }
        )
        # Order may vary, check both fields present
        assert "src=192.168.1.1" in ext
        assert "dst=10.0.0.1" in ext
        assert " " in ext  # Space separator

    def test_build_extension_escapes_values(self) -> None:
        """Extension values with special chars are escaped."""
        formatter = CEFFormatter()
        ext = formatter._build_extension({"msg": "a=b\nc=d"})
        assert ext == "msg=a\\=b\\nc\\=d"

    def test_build_extension_skips_none_values(self) -> None:
        """None values are skipped."""
        formatter = CEFFormatter()
        ext = formatter._build_extension(
            {
                "msg": "test",
                "empty": None,
            }
        )
        assert "msg=test" in ext
        assert "empty" not in ext

    def test_build_extension_empty_dict(self) -> None:
        """Empty dict returns empty string."""
        formatter = CEFFormatter()
        assert formatter._build_extension({}) == ""


class TestCEFEventFormatting:
    """Test full CEF event formatting."""

    @pytest.fixture
    def sample_raxe_event(self) -> dict:
        """Sample RAXE scan event for testing."""
        return {
            "event_type": "scan",
            "event_id": "evt_test123",
            "priority": "critical",
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
                "scan_duration_ms": 12.5,
                "mssp_id": "mssp_test",
                "customer_id": "cust_test",
                "agent_id": "inst_abc123",
                "l1": {
                    "hit": True,
                    "highest_severity": "CRITICAL",
                    "detection_count": 1,
                    "families": ["PI"],
                    "detections": [
                        {
                            "rule_id": "pi-001",
                            "severity": "CRITICAL",
                            "confidence": 0.95,
                        }
                    ],
                },
                "l2": {
                    "hit": False,
                    "enabled": True,
                },
            },
        }

    def test_format_event_returns_cef_string(self, sample_raxe_event: dict) -> None:
        """format_event returns a valid CEF string."""
        formatter = CEFFormatter()
        result = formatter.format_event(sample_raxe_event)

        assert result.startswith("CEF:0|")
        assert "|RAXE|" in result
        assert "|ThreatDetection|" in result

    def test_format_event_includes_signature_id(self, sample_raxe_event: dict) -> None:
        """CEF includes rule ID as signature ID."""
        formatter = CEFFormatter()
        result = formatter.format_event(sample_raxe_event)

        assert "|pi-001|" in result

    def test_format_event_includes_severity(self, sample_raxe_event: dict) -> None:
        """CEF includes mapped severity."""
        formatter = CEFFormatter()
        result = formatter.format_event(sample_raxe_event)

        # CRITICAL = 10
        assert "|10|" in result

    def test_format_event_includes_extensions(self, sample_raxe_event: dict) -> None:
        """CEF includes extension fields."""
        formatter = CEFFormatter()
        result = formatter.format_event(sample_raxe_event)

        # Check for expected extension fields
        assert "suser=" in result  # agent_id
        assert "cs5=" in result  # mssp_id
        assert "cs6=" in result  # customer_id
        assert "act=" in result  # action_taken
        assert "cn1=" in result  # prompt_length

    def test_format_event_includes_timestamp(self, sample_raxe_event: dict) -> None:
        """CEF includes receipt time (rt)."""
        formatter = CEFFormatter()
        result = formatter.format_event(sample_raxe_event)

        assert "rt=" in result

    def test_format_event_no_threat(self) -> None:
        """CEF handles events with no threat detected."""
        formatter = CEFFormatter()
        event = {
            "event_type": "scan",
            "event_id": "evt_safe",
            "timestamp": "2024-01-15T10:30:00.000Z",
            "_metadata": {"installation_id": "inst_123"},
            "payload": {
                "threat_detected": False,
                "prompt_hash": "sha256:safe123",
                "prompt_length": 50,
                "l1": {
                    "hit": False,
                    "highest_severity": "none",
                },
            },
        }
        result = formatter.format_event(event)

        # Severity should be 0 for no threat
        assert "|0|" in result or "|none|" in result.lower()


class TestCEFFormatterConfiguration:
    """Test CEF formatter configuration options."""

    def test_custom_device_vendor(self) -> None:
        """Custom device vendor is used in header."""
        formatter = CEFFormatter(device_vendor="CustomVendor")
        event = {
            "event_type": "scan",
            "timestamp": "2024-01-15T10:30:00.000Z",
            "payload": {"l1": {"highest_severity": "HIGH"}},
        }
        result = formatter.format_event(event)
        assert "|CustomVendor|" in result

    def test_custom_device_product(self) -> None:
        """Custom device product is used in header."""
        formatter = CEFFormatter(device_product="CustomProduct")
        event = {
            "event_type": "scan",
            "timestamp": "2024-01-15T10:30:00.000Z",
            "payload": {"l1": {"highest_severity": "HIGH"}},
        }
        result = formatter.format_event(event)
        assert "|CustomProduct|" in result

    def test_custom_device_version(self) -> None:
        """Custom device version is used in header."""
        formatter = CEFFormatter(device_version="2.0.0-custom")
        event = {
            "event_type": "scan",
            "timestamp": "2024-01-15T10:30:00.000Z",
            "payload": {"l1": {"highest_severity": "HIGH"}},
        }
        result = formatter.format_event(event)
        assert "|2.0.0-custom|" in result
