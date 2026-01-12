"""
Unit tests for telemetry events module.

Tests all ID generators, factory functions, and utility functions.
These tests are PURE - no mocks, no I/O, no database.

Coverage target: >95%
"""

import re
from dataclasses import FrozenInstanceError

import pytest

from raxe.domain.telemetry.events import (
    EventType,
    TelemetryEvent,
    create_activation_event,
    create_config_changed_event,
    create_error_event,
    create_feature_usage_event,
    create_heartbeat_event,
    create_installation_event,
    create_key_upgrade_event,
    create_performance_event,
    create_prompt_hash,
    create_scan_event,
    create_session_end_event,
    create_session_start_event,
    event_to_dict,
    generate_batch_id,
    generate_event_id,
    generate_installation_id,
    generate_session_id,
)

# =============================================================================
# Test Markers
# =============================================================================
pytestmark = [pytest.mark.unit, pytest.mark.domain, pytest.mark.telemetry]


# =============================================================================
# ID Generator Tests
# =============================================================================
class TestIdGenerators:
    """Test all ID generator functions."""

    def test_generate_event_id_has_correct_prefix(self) -> None:
        """Event ID should start with 'evt_' prefix."""
        event_id = generate_event_id()
        assert event_id.startswith("evt_")

    def test_generate_event_id_has_correct_length(self) -> None:
        """Event ID should have 16 hex chars after prefix (20 total)."""
        event_id = generate_event_id()
        assert len(event_id) == 20  # "evt_" (4) + 16 hex chars

    def test_generate_event_id_is_valid_hex(self) -> None:
        """Event ID suffix should be valid hexadecimal."""
        event_id = generate_event_id()
        suffix = event_id[4:]  # Remove "evt_" prefix
        # Should match hex pattern
        assert re.match(r"^[a-f0-9]{16}$", suffix)

    def test_generate_event_id_is_unique(self) -> None:
        """Each call should generate a unique ID."""
        ids = {generate_event_id() for _ in range(100)}
        assert len(ids) == 100

    def test_generate_installation_id_has_correct_prefix(self) -> None:
        """Installation ID should start with 'inst_' prefix."""
        installation_id = generate_installation_id()
        assert installation_id.startswith("inst_")

    def test_generate_installation_id_has_correct_length(self) -> None:
        """Installation ID should have 16 hex chars after prefix (21 total)."""
        installation_id = generate_installation_id()
        assert len(installation_id) == 21  # "inst_" (5) + 16 hex chars

    def test_generate_installation_id_is_valid_hex(self) -> None:
        """Installation ID suffix should be valid hexadecimal."""
        installation_id = generate_installation_id()
        suffix = installation_id[5:]  # Remove "inst_" prefix
        assert re.match(r"^[a-f0-9]{16}$", suffix)

    def test_generate_installation_id_is_unique(self) -> None:
        """Each call should generate a unique ID."""
        ids = {generate_installation_id() for _ in range(100)}
        assert len(ids) == 100

    def test_generate_session_id_has_correct_prefix(self) -> None:
        """Session ID should start with 'sess_' prefix."""
        session_id = generate_session_id()
        assert session_id.startswith("sess_")

    def test_generate_session_id_has_correct_length(self) -> None:
        """Session ID should have 16 hex chars after prefix (21 total)."""
        session_id = generate_session_id()
        assert len(session_id) == 21  # "sess_" (5) + 16 hex chars

    def test_generate_session_id_is_valid_hex(self) -> None:
        """Session ID suffix should be valid hexadecimal."""
        session_id = generate_session_id()
        suffix = session_id[5:]  # Remove "sess_" prefix
        assert re.match(r"^[a-f0-9]{16}$", suffix)

    def test_generate_session_id_is_unique(self) -> None:
        """Each call should generate a unique ID."""
        ids = {generate_session_id() for _ in range(100)}
        assert len(ids) == 100

    def test_generate_batch_id_has_correct_prefix(self) -> None:
        """Batch ID should start with 'batch_' prefix."""
        batch_id = generate_batch_id()
        assert batch_id.startswith("batch_")

    def test_generate_batch_id_has_correct_length(self) -> None:
        """Batch ID should have 16 hex chars after prefix (22 total)."""
        batch_id = generate_batch_id()
        assert len(batch_id) == 22  # "batch_" (6) + 16 hex chars

    def test_generate_batch_id_is_valid_hex(self) -> None:
        """Batch ID suffix should be valid hexadecimal."""
        batch_id = generate_batch_id()
        suffix = batch_id[6:]  # Remove "batch_" prefix
        assert re.match(r"^[a-f0-9]{16}$", suffix)

    def test_generate_batch_id_is_unique(self) -> None:
        """Each call should generate a unique ID."""
        ids = {generate_batch_id() for _ in range(100)}
        assert len(ids) == 100


# =============================================================================
# EventType Enum Tests
# =============================================================================
class TestEventType:
    """Test EventType enumeration."""

    def test_event_type_has_all_12_types(self) -> None:
        """EventType should have exactly 12 event types."""
        assert len(EventType) == 12

    @pytest.mark.parametrize(
        "event_type,expected_value",
        [
            (EventType.INSTALLATION, "installation"),
            (EventType.ACTIVATION, "activation"),
            (EventType.SESSION_START, "session_start"),
            (EventType.SESSION_END, "session_end"),
            (EventType.SCAN, "scan"),
            (EventType.ERROR, "error"),
            (EventType.PERFORMANCE, "performance"),
            (EventType.FEATURE_USAGE, "feature_usage"),
            (EventType.HEARTBEAT, "heartbeat"),
            (EventType.KEY_UPGRADE, "key_upgrade"),
            (EventType.CONFIG_CHANGED, "config_changed"),
        ],
    )
    def test_event_type_values(self, event_type: EventType, expected_value: str) -> None:
        """Each EventType should have the correct string value."""
        assert event_type.value == expected_value

    def test_event_type_is_str_enum(self) -> None:
        """EventType should be usable as a string."""
        assert isinstance(EventType.SCAN.value, str)
        assert EventType.SCAN == "scan"


# =============================================================================
# TelemetryEvent Dataclass Tests
# =============================================================================
class TestTelemetryEvent:
    """Test TelemetryEvent dataclass."""

    def test_telemetry_event_is_frozen(self) -> None:
        """TelemetryEvent should be immutable (frozen)."""
        event = TelemetryEvent(
            event_id="evt_1234567890abcdef",
            event_type="scan",
            timestamp="2025-01-26T10:00:00Z",
            priority="standard",
            payload={"key": "value"},
        )
        with pytest.raises(FrozenInstanceError):
            event.event_id = "new_id"  # type: ignore[misc]

    def test_telemetry_event_stores_all_fields(self) -> None:
        """TelemetryEvent should store all provided fields."""
        event = TelemetryEvent(
            event_id="evt_1234567890abcdef",
            event_type="scan",
            timestamp="2025-01-26T10:00:00Z",
            priority="critical",
            payload={"prompt_hash": "a" * 64},
        )
        assert event.event_id == "evt_1234567890abcdef"
        assert event.event_type == "scan"
        assert event.timestamp == "2025-01-26T10:00:00Z"
        assert event.priority == "critical"
        assert event.payload == {"prompt_hash": "a" * 64}

    def test_telemetry_event_equality(self) -> None:
        """Two TelemetryEvents with same fields should be equal."""
        event1 = TelemetryEvent(
            event_id="evt_1234567890abcdef",
            event_type="scan",
            timestamp="2025-01-26T10:00:00Z",
            priority="standard",
            payload={"key": "value"},
        )
        event2 = TelemetryEvent(
            event_id="evt_1234567890abcdef",
            event_type="scan",
            timestamp="2025-01-26T10:00:00Z",
            priority="standard",
            payload={"key": "value"},
        )
        assert event1 == event2


# =============================================================================
# Installation Event Tests
# =============================================================================
class TestCreateInstallationEvent:
    """Test create_installation_event factory function."""

    def test_creates_valid_installation_event(self) -> None:
        """Should create installation event with required fields."""
        event = create_installation_event(
            installation_id="inst_1234567890abcdef",
            client_version="0.0.1",
            python_version="3.11.5",
            platform="darwin",
            install_method="pip",
        )

        assert event.event_type == "installation"
        assert event.priority == "critical"
        assert event.payload["installation_id"] == "inst_1234567890abcdef"
        assert event.payload["client_version"] == "0.0.1"
        assert event.payload["python_version"] == "3.11.5"
        assert event.payload["platform"] == "darwin"
        assert event.payload["install_method"] == "pip"
        # key_type defaults to "temp"
        assert event.payload["key_type"] == "temp"
        # acquisition_source defaults to "unknown"
        assert event.payload["acquisition_source"] == "unknown"

    def test_creates_event_with_optional_fields(self) -> None:
        """Should include optional fields when provided."""
        event = create_installation_event(
            installation_id="inst_1234567890abcdef",
            client_version="0.0.1",
            python_version="3.11.5",
            platform="darwin",
            install_method="pip",
            ml_available=True,
            installed_extras=["ml", "openai"],
            platform_version="14.0.0",
            acquisition_source="pip_install",
        )

        assert event.payload["ml_available"] is True
        assert event.payload["installed_extras"] == ["ml", "openai"]
        assert event.payload["platform_version"] == "14.0.0"
        assert event.payload["acquisition_source"] == "pip_install"

    def test_excludes_none_optional_fields(self) -> None:
        """Should not include optional fields when None."""
        event = create_installation_event(
            installation_id="inst_1234567890abcdef",
            client_version="0.0.1",
            python_version="3.11.5",
            platform="darwin",
            install_method="pip",
        )

        assert "ml_available" not in event.payload
        assert "installed_extras" not in event.payload
        assert "platform_version" not in event.payload

    def test_event_id_is_generated(self) -> None:
        """Should generate a unique event ID."""
        event = create_installation_event(
            installation_id="inst_1234567890abcdef",
            client_version="0.0.1",
            python_version="3.11.5",
            platform="darwin",
            install_method="pip",
        )

        assert event.event_id.startswith("evt_")

    def test_timestamp_is_iso_format(self) -> None:
        """Should generate ISO 8601 timestamp."""
        event = create_installation_event(
            installation_id="inst_1234567890abcdef",
            client_version="0.0.1",
            python_version="3.11.5",
            platform="darwin",
            install_method="pip",
        )

        # ISO 8601 pattern: YYYY-MM-DDTHH:MM:SS...
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", event.timestamp)

    @pytest.mark.parametrize("platform", ["darwin", "linux", "win32"])
    def test_accepts_valid_platforms(self, platform: str) -> None:
        """Should accept all valid platform values."""
        event = create_installation_event(
            installation_id="inst_1234567890abcdef",
            client_version="0.0.1",
            python_version="3.11.5",
            platform=platform,  # type: ignore[arg-type]
            install_method="pip",
        )
        assert event.payload["platform"] == platform

    @pytest.mark.parametrize(
        "method", ["pip", "uv", "pipx", "poetry", "conda", "source", "unknown"]
    )
    def test_accepts_valid_install_methods(self, method: str) -> None:
        """Should accept all valid install method values."""
        event = create_installation_event(
            installation_id="inst_1234567890abcdef",
            client_version="0.0.1",
            python_version="3.11.5",
            platform="darwin",
            install_method=method,  # type: ignore[arg-type]
        )
        assert event.payload["install_method"] == method

    @pytest.mark.parametrize(
        "source",
        [
            "pip_install",
            "github_release",
            "docker",
            "homebrew",
            "website_download",
            "referral",
            "enterprise_deploy",
            "ci_integration",
            "unknown",
        ],
    )
    def test_accepts_valid_acquisition_sources(self, source: str) -> None:
        """Should accept all valid acquisition source values."""
        event = create_installation_event(
            installation_id="inst_1234567890abcdef",
            client_version="0.0.1",
            python_version="3.11.5",
            platform="darwin",
            install_method="pip",
            acquisition_source=source,  # type: ignore[arg-type]
        )
        assert event.payload["acquisition_source"] == source

    def test_acquisition_source_always_in_payload(self) -> None:
        """acquisition_source should always be included (not optional)."""
        event = create_installation_event(
            installation_id="inst_1234567890abcdef",
            client_version="0.0.1",
            python_version="3.11.5",
            platform="darwin",
            install_method="pip",
        )
        # acquisition_source is always present, defaults to "unknown"
        assert "acquisition_source" in event.payload
        assert event.payload["acquisition_source"] == "unknown"

    @pytest.mark.parametrize(
        "key_type",
        ["temp", "community", "pro", "enterprise"],
    )
    def test_accepts_valid_key_types(self, key_type: str) -> None:
        """Should accept all valid key_type values."""
        event = create_installation_event(
            installation_id="inst_1234567890abcdef",
            client_version="0.0.1",
            python_version="3.11.5",
            platform="darwin",
            install_method="pip",
            key_type=key_type,  # type: ignore[arg-type]
        )
        assert event.payload["key_type"] == key_type

    def test_key_type_always_in_payload(self) -> None:
        """key_type should always be included (not optional)."""
        event = create_installation_event(
            installation_id="inst_1234567890abcdef",
            client_version="0.0.1",
            python_version="3.11.5",
            platform="darwin",
            install_method="pip",
        )
        # key_type is always present, defaults to "temp"
        assert "key_type" in event.payload
        assert event.payload["key_type"] == "temp"


# =============================================================================
# Activation Event Tests
# =============================================================================
class TestCreateActivationEvent:
    """Test create_activation_event factory function."""

    def test_creates_valid_activation_event(self) -> None:
        """Should create activation event with required fields."""
        event = create_activation_event(
            feature="first_scan",
            seconds_since_install=120.5,
        )

        assert event.event_type == "activation"
        assert event.priority == "critical"
        assert event.payload["feature"] == "first_scan"
        assert event.payload["seconds_since_install"] == 120.5

    def test_includes_activation_context(self) -> None:
        """Should include activation context when provided."""
        event = create_activation_event(
            feature="first_scan",
            seconds_since_install=120.5,
            activation_context={"entry_point": "cli"},
        )

        assert event.payload["activation_context"] == {"entry_point": "cli"}

    def test_excludes_none_activation_context(self) -> None:
        """Should not include activation_context when None."""
        event = create_activation_event(
            feature="first_scan",
            seconds_since_install=120.5,
        )

        assert "activation_context" not in event.payload

    @pytest.mark.parametrize(
        "feature",
        [
            "first_scan",
            "first_threat",
            "first_block",
            "first_cli",
            "first_sdk",
            "first_decorator",
            "first_wrapper",
            "first_langchain",
            "first_l2_detection",
            "first_custom_rule",
        ],
    )
    def test_accepts_valid_features(self, feature: str) -> None:
        """Should accept all valid feature values (canonical backend values)."""
        event = create_activation_event(
            feature=feature,  # type: ignore[arg-type]
            seconds_since_install=0.0,
        )
        assert event.payload["feature"] == feature

    def test_accepts_zero_seconds_since_install(self) -> None:
        """Should accept zero seconds since install."""
        event = create_activation_event(
            feature="first_scan",
            seconds_since_install=0.0,
        )
        assert event.payload["seconds_since_install"] == 0.0


# =============================================================================
# Session Start Event Tests
# =============================================================================
class TestCreateSessionStartEvent:
    """Test create_session_start_event factory function."""

    def test_creates_valid_session_start_event(self) -> None:
        """Should create session start event with required fields."""
        event = create_session_start_event(
            session_id="sess_1234567890abcdef",
            session_number=5,
        )

        assert event.event_type == "session_start"
        assert event.priority == "standard"
        assert event.payload["session_id"] == "sess_1234567890abcdef"
        assert event.payload["session_number"] == 5

    def test_includes_optional_fields(self) -> None:
        """Should include optional fields when provided."""
        event = create_session_start_event(
            session_id="sess_1234567890abcdef",
            session_number=5,
            entry_point="cli",
            previous_session_gap_hours=24.5,
            environment={"is_ci": False, "is_interactive": True},
        )

        assert event.payload["entry_point"] == "cli"
        assert event.payload["previous_session_gap_hours"] == 24.5
        assert event.payload["environment"] == {"is_ci": False, "is_interactive": True}

    def test_excludes_none_optional_fields(self) -> None:
        """Should not include optional fields when None."""
        event = create_session_start_event(
            session_id="sess_1234567890abcdef",
            session_number=5,
        )

        assert "entry_point" not in event.payload
        assert "previous_session_gap_hours" not in event.payload
        assert "environment" not in event.payload

    @pytest.mark.parametrize("entry_point", ["cli", "sdk", "wrapper", "integration", "repl"])
    def test_accepts_valid_entry_points(self, entry_point: str) -> None:
        """Should accept all valid entry point values."""
        event = create_session_start_event(
            session_id="sess_1234567890abcdef",
            session_number=1,
            entry_point=entry_point,  # type: ignore[arg-type]
        )
        assert event.payload["entry_point"] == entry_point


# =============================================================================
# Session End Event Tests
# =============================================================================
class TestCreateSessionEndEvent:
    """Test create_session_end_event factory function."""

    def test_creates_valid_session_end_event(self) -> None:
        """Should create session end event with required fields."""
        event = create_session_end_event(
            session_id="sess_1234567890abcdef",
            duration_seconds=3600.0,
            scans_in_session=50,
            threats_in_session=3,
        )

        assert event.event_type == "session_end"
        assert event.priority == "critical"
        assert event.payload["session_id"] == "sess_1234567890abcdef"
        assert event.payload["duration_seconds"] == 3600.0
        assert event.payload["scans_in_session"] == 50
        assert event.payload["threats_in_session"] == 3

    def test_includes_optional_fields(self) -> None:
        """Should include optional fields when provided."""
        event = create_session_end_event(
            session_id="sess_1234567890abcdef",
            duration_seconds=3600.0,
            scans_in_session=50,
            threats_in_session=3,
            end_reason="normal",
            peak_memory_mb=150.5,
            features_used=["cli", "explain"],
        )

        assert event.payload["end_reason"] == "normal"
        assert event.payload["peak_memory_mb"] == 150.5
        assert event.payload["features_used"] == ["cli", "explain"]

    def test_excludes_none_optional_fields(self) -> None:
        """Should not include optional fields when None."""
        event = create_session_end_event(
            session_id="sess_1234567890abcdef",
            duration_seconds=3600.0,
            scans_in_session=50,
            threats_in_session=3,
        )

        assert "end_reason" not in event.payload
        assert "peak_memory_mb" not in event.payload
        assert "features_used" not in event.payload

    @pytest.mark.parametrize("end_reason", ["normal", "error", "timeout", "interrupt", "unknown"])
    def test_accepts_valid_end_reasons(self, end_reason: str) -> None:
        """Should accept all valid end reason values."""
        event = create_session_end_event(
            session_id="sess_1234567890abcdef",
            duration_seconds=100.0,
            scans_in_session=10,
            threats_in_session=0,
            end_reason=end_reason,  # type: ignore[arg-type]
        )
        assert event.payload["end_reason"] == end_reason


# =============================================================================
# Scan Event Tests
# =============================================================================
class TestCreateScanEvent:
    """Test create_scan_event factory function."""

    def test_creates_valid_scan_event(self) -> None:
        """Should create scan event with required fields."""
        event = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=False,
            scan_duration_ms=4.5,
        )

        assert event.event_type == "scan"
        assert event.payload["prompt_hash"] == "a" * 64
        assert event.payload["threat_detected"] is False
        assert event.payload["scan_duration_ms"] == 4.5

    def test_standard_priority_for_clean_scan(self) -> None:
        """Clean scans should have standard priority."""
        event = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=False,
            scan_duration_ms=4.5,
        )

        assert event.priority == "standard"

    def test_standard_priority_for_low_severity(self) -> None:
        """Scans with LOW severity should have standard priority."""
        event = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=True,
            scan_duration_ms=4.5,
            highest_severity="low",
        )

        assert event.priority == "standard"

    def test_standard_priority_for_medium_severity(self) -> None:
        """Scans with MEDIUM severity should have standard priority."""
        event = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=True,
            scan_duration_ms=4.5,
            highest_severity="medium",
        )

        assert event.priority == "standard"

    def test_critical_priority_for_high_severity(self) -> None:
        """Scans with high severity should have critical priority."""
        event = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=True,
            scan_duration_ms=4.5,
            highest_severity="high",
        )

        assert event.priority == "critical"

    def test_critical_priority_for_critical_severity(self) -> None:
        """Scans with critical severity should have critical priority."""
        event = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=True,
            scan_duration_ms=4.5,
            highest_severity="critical",
        )

        assert event.priority == "critical"

    def test_includes_all_optional_fields(self) -> None:
        """Should include all optional fields when provided."""
        event = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=True,
            scan_duration_ms=4.5,
            detection_count=2,
            highest_severity="high",
            rule_ids=["pi-001", "pi-002"],
            families=["PI"],
            l1_duration_ms=1.5,
            l2_duration_ms=3.0,
            l1_hit=True,
            l2_hit=True,
            l2_enabled=True,
            prompt_length=100,
            action_taken="block",
            entry_point="cli",
            wrapper_type="openai",
        )

        assert event.payload["detection_count"] == 2
        assert event.payload["highest_severity"] == "high"
        assert event.payload["rule_ids"] == ["pi-001", "pi-002"]
        assert event.payload["families"] == ["PI"]
        assert event.payload["l1_duration_ms"] == 1.5
        assert event.payload["l2_duration_ms"] == 3.0
        assert event.payload["l1_hit"] is True
        assert event.payload["l2_hit"] is True
        assert event.payload["l2_enabled"] is True
        assert event.payload["prompt_length"] == 100
        assert event.payload["action_taken"] == "block"
        assert event.payload["entry_point"] == "cli"
        assert event.payload["wrapper_type"] == "openai"

    def test_limits_rule_ids_to_10(self) -> None:
        """Should limit rule_ids to 10 entries."""
        rule_ids = [f"pi-{i:03d}" for i in range(15)]
        event = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=True,
            scan_duration_ms=4.5,
            rule_ids=rule_ids,
        )

        assert len(event.payload["rule_ids"]) == 10
        assert event.payload["rule_ids"] == rule_ids[:10]

    @pytest.mark.parametrize(
        "severity,expected_priority",
        [
            ("none", "standard"),
            ("low", "standard"),
            ("medium", "standard"),
            ("high", "critical"),
            ("critical", "critical"),
        ],
    )
    def test_priority_by_severity(self, severity: str, expected_priority: str) -> None:
        """Test priority assignment for each severity level."""
        event = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=True,
            scan_duration_ms=4.5,
            highest_severity=severity,  # type: ignore[arg-type]
        )
        assert event.priority == expected_priority


# =============================================================================
# Error Event Tests
# =============================================================================
class TestCreateErrorEvent:
    """Test create_error_event factory function."""

    def test_creates_valid_error_event(self) -> None:
        """Should create error event with required fields."""
        event = create_error_event(
            error_type="validation_error",
            error_code="RAXE_001",
            component="engine",
        )

        assert event.event_type == "error"
        assert event.priority == "critical"
        assert event.payload["error_type"] == "validation_error"
        assert event.payload["error_code"] == "RAXE_001"
        assert event.payload["component"] == "engine"

    def test_includes_optional_fields(self) -> None:
        """Should include optional fields when provided."""
        event = create_error_event(
            error_type="validation_error",
            error_code="RAXE_001",
            component="engine",
            error_message_hash="b" * 64,
            operation="scan",
            is_recoverable=True,
            stack_trace_hash="c" * 64,
            context={"python_version": "3.11.5"},
        )

        assert event.payload["error_message_hash"] == "b" * 64
        assert event.payload["operation"] == "scan"
        assert event.payload["is_recoverable"] is True
        assert event.payload["stack_trace_hash"] == "c" * 64
        assert event.payload["context"] == {"python_version": "3.11.5"}

    @pytest.mark.parametrize(
        "error_type",
        [
            "validation_error",
            "configuration_error",
            "rule_loading_error",
            "ml_model_error",
            "network_error",
            "permission_error",
            "timeout_error",
            "internal_error",
        ],
    )
    def test_accepts_valid_error_types(self, error_type: str) -> None:
        """Should accept all valid error type values."""
        event = create_error_event(
            error_type=error_type,  # type: ignore[arg-type]
            error_code="RAXE_001",
            component="engine",
        )
        assert event.payload["error_type"] == error_type

    @pytest.mark.parametrize(
        "component",
        ["cli", "sdk", "engine", "ml", "rules", "config", "telemetry", "wrapper"],
    )
    def test_accepts_valid_components(self, component: str) -> None:
        """Should accept all valid component values."""
        event = create_error_event(
            error_type="internal_error",
            error_code="RAXE_001",
            component=component,  # type: ignore[arg-type]
        )
        assert event.payload["component"] == component


# =============================================================================
# Performance Event Tests
# =============================================================================
class TestCreatePerformanceEvent:
    """Test create_performance_event factory function."""

    def test_creates_valid_performance_event(self) -> None:
        """Should create performance event with required fields."""
        event = create_performance_event(
            period_start="2025-01-22T10:00:00Z",
            period_end="2025-01-22T11:00:00Z",
            scan_count=1000,
        )

        assert event.event_type == "performance"
        assert event.priority == "standard"
        assert event.payload["period_start"] == "2025-01-22T10:00:00Z"
        assert event.payload["period_end"] == "2025-01-22T11:00:00Z"
        assert event.payload["scan_count"] == 1000

    def test_includes_optional_fields(self) -> None:
        """Should include optional fields when provided."""
        event = create_performance_event(
            period_start="2025-01-22T10:00:00Z",
            period_end="2025-01-22T11:00:00Z",
            scan_count=1000,
            latency_percentiles={"p50_ms": 2.5, "p95_ms": 8.0, "p99_ms": 12.0},
            l1_latency_percentiles={"p50_ms": 1.0, "p95_ms": 3.0},
            l2_latency_percentiles={"p50_ms": 10.0, "p95_ms": 30.0},
            memory_usage={"current_mb": 100.0, "peak_mb": 150.0},
            threat_detection_rate=0.05,
            rules_loaded=460,
            l2_enabled=True,
        )

        assert event.payload["latency_percentiles"] == {
            "p50_ms": 2.5,
            "p95_ms": 8.0,
            "p99_ms": 12.0,
        }
        assert event.payload["l1_latency_percentiles"] == {"p50_ms": 1.0, "p95_ms": 3.0}
        assert event.payload["l2_latency_percentiles"] == {"p50_ms": 10.0, "p95_ms": 30.0}
        assert event.payload["memory_usage"] == {"current_mb": 100.0, "peak_mb": 150.0}
        assert event.payload["threat_detection_rate"] == 0.05
        assert event.payload["rules_loaded"] == 460
        assert event.payload["l2_enabled"] is True


# =============================================================================
# Feature Usage Event Tests
# =============================================================================
class TestCreateFeatureUsageEvent:
    """Test create_feature_usage_event factory function."""

    def test_creates_valid_feature_usage_event(self) -> None:
        """Should create feature usage event with required fields."""
        event = create_feature_usage_event(
            feature="cli_scan",
            action="completed",
        )

        assert event.event_type == "feature_usage"
        assert event.priority == "standard"
        assert event.payload["feature"] == "cli_scan"
        assert event.payload["action"] == "completed"

    def test_includes_optional_fields(self) -> None:
        """Should include optional fields when provided."""
        event = create_feature_usage_event(
            feature="cli_scan",
            action="completed",
            duration_ms=150.5,
            success=True,
            metadata={"output_format": "json"},
        )

        assert event.payload["duration_ms"] == 150.5
        assert event.payload["success"] is True
        assert event.payload["metadata"] == {"output_format": "json"}

    @pytest.mark.parametrize("action", ["invoked", "completed", "failed", "cancelled"])
    def test_accepts_valid_actions(self, action: str) -> None:
        """Should accept all valid action values."""
        event = create_feature_usage_event(
            feature="cli_scan",
            action=action,  # type: ignore[arg-type]
        )
        assert event.payload["action"] == action


# =============================================================================
# Heartbeat Event Tests
# =============================================================================
class TestCreateHeartbeatEvent:
    """Test create_heartbeat_event factory function."""

    def test_creates_valid_heartbeat_event(self) -> None:
        """Should create heartbeat event with required fields."""
        event = create_heartbeat_event(
            uptime_seconds=3600.0,
            scans_since_last_heartbeat=100,
        )

        assert event.event_type == "heartbeat"
        assert event.priority == "standard"
        assert event.payload["uptime_seconds"] == 3600.0
        assert event.payload["scans_since_last_heartbeat"] == 100

    def test_includes_optional_fields(self) -> None:
        """Should include optional fields when provided."""
        event = create_heartbeat_event(
            uptime_seconds=3600.0,
            scans_since_last_heartbeat=100,
            threats_since_last_heartbeat=5,
            memory_mb=120.5,
            queue_depths={"critical": 0, "standard": 10, "dlq": 2},
            circuit_breaker_state="closed",
            last_successful_ship="2025-01-26T10:00:00Z",
        )

        assert event.payload["threats_since_last_heartbeat"] == 5
        assert event.payload["memory_mb"] == 120.5
        assert event.payload["queue_depths"] == {
            "critical": 0,
            "standard": 10,
            "dlq": 2,
        }
        assert event.payload["circuit_breaker_state"] == "closed"
        assert event.payload["last_successful_ship"] == "2025-01-26T10:00:00Z"

    @pytest.mark.parametrize("state", ["closed", "open", "half_open"])
    def test_accepts_valid_circuit_breaker_states(self, state: str) -> None:
        """Should accept all valid circuit breaker states."""
        event = create_heartbeat_event(
            uptime_seconds=100.0,
            scans_since_last_heartbeat=10,
            circuit_breaker_state=state,  # type: ignore[arg-type]
        )
        assert event.payload["circuit_breaker_state"] == state


# =============================================================================
# Key Upgrade Event Tests
# =============================================================================
class TestCreateKeyUpgradeEvent:
    """Test create_key_upgrade_event factory function."""

    def test_creates_valid_key_upgrade_event(self) -> None:
        """Should create key upgrade event with required fields."""
        event = create_key_upgrade_event(
            previous_key_type="temp",
            new_key_type="community",
        )

        assert event.event_type == "key_upgrade"
        assert event.priority == "critical"
        assert event.payload["previous_key_type"] == "temp"
        assert event.payload["new_key_type"] == "community"

    def test_includes_optional_fields(self) -> None:
        """Should include optional fields when provided."""
        event = create_key_upgrade_event(
            previous_key_type="temp",
            new_key_type="community",
            days_on_previous=7,
            scans_on_previous=500,
            threats_on_previous=25,
            conversion_trigger="trial_expiry",
        )

        assert event.payload["days_on_previous"] == 7
        assert event.payload["scans_on_previous"] == 500
        assert event.payload["threats_on_previous"] == 25
        assert event.payload["conversion_trigger"] == "trial_expiry"

    @pytest.mark.parametrize(
        "trigger",
        ["trial_expiry", "rate_limit_hit", "feature_needed", "manual_upgrade", "promo_code"],
    )
    def test_accepts_valid_conversion_triggers(self, trigger: str) -> None:
        """Should accept all valid conversion trigger values."""
        event = create_key_upgrade_event(
            previous_key_type="temp",
            new_key_type="pro",
            conversion_trigger=trigger,  # type: ignore[arg-type]
        )
        assert event.payload["conversion_trigger"] == trigger

    def test_includes_key_ids_when_provided(self) -> None:
        """Should include previous_key_id and new_key_id when provided."""
        event = create_key_upgrade_event(
            previous_key_type="temp",
            new_key_type="community",
            previous_key_id="key_23cc2f9f21f9",
            new_key_id="key_7ce219b525f1",
        )

        assert event.payload["previous_key_id"] == "key_23cc2f9f21f9"
        assert event.payload["new_key_id"] == "key_7ce219b525f1"

    def test_excludes_key_ids_when_none(self) -> None:
        """Should not include key IDs when not provided."""
        event = create_key_upgrade_event(
            previous_key_type="temp",
            new_key_type="community",
        )

        assert "previous_key_id" not in event.payload
        assert "new_key_id" not in event.payload

    def test_includes_only_new_key_id_when_previous_is_none(self) -> None:
        """Should include only new_key_id when previous is not available."""
        event = create_key_upgrade_event(
            previous_key_type="temp",
            new_key_type="community",
            new_key_id="key_7ce219b525f1",
        )

        assert "previous_key_id" not in event.payload
        assert event.payload["new_key_id"] == "key_7ce219b525f1"

    def test_includes_all_fields_together(self) -> None:
        """Should include all optional fields including key IDs."""
        event = create_key_upgrade_event(
            previous_key_type="temp",
            new_key_type="community",
            previous_key_id="key_23cc2f9f21f9",
            new_key_id="key_7ce219b525f1",
            days_on_previous=7,
            scans_on_previous=500,
            threats_on_previous=25,
            conversion_trigger="manual_upgrade",
            org_id="org_123",
            team_id="team_456",
        )

        assert event.payload["previous_key_id"] == "key_23cc2f9f21f9"
        assert event.payload["new_key_id"] == "key_7ce219b525f1"
        assert event.payload["days_on_previous"] == 7
        assert event.payload["scans_on_previous"] == 500
        assert event.payload["threats_on_previous"] == 25
        assert event.payload["conversion_trigger"] == "manual_upgrade"
        assert event.org_id == "org_123"
        assert event.team_id == "team_456"


# =============================================================================
# Config Changed Event Tests
# =============================================================================
class TestCreateConfigChangedEvent:
    """Test create_config_changed_event factory function."""

    def test_creates_valid_config_changed_event(self) -> None:
        """Should create config changed event with required fields."""
        event = create_config_changed_event(
            changed_via="cli",
            changes=[{"key": "detection.l2_enabled", "old_value": True, "new_value": False}],
        )

        assert event.event_type == "config_changed"
        assert event.payload["changed_via"] == "cli"
        assert event.payload["changes"] == [
            {"key": "detection.l2_enabled", "old_value": True, "new_value": False}
        ]

    def test_standard_priority_for_normal_config_change(self) -> None:
        """Normal config changes should have standard priority."""
        event = create_config_changed_event(
            changed_via="cli",
            changes=[{"key": "detection.l2_enabled", "old_value": True, "new_value": False}],
        )

        assert event.priority == "standard"

    def test_critical_priority_for_telemetry_disable(self) -> None:
        """Disabling telemetry should have critical priority (is_final_event)."""
        event = create_config_changed_event(
            changed_via="cli",
            changes=[{"key": "telemetry.enabled", "old_value": True, "new_value": False}],
            is_final_event=True,
        )

        assert event.priority == "critical"
        assert event.payload["is_final_event"] is True

    def test_excludes_is_final_event_when_false(self) -> None:
        """Should not include is_final_event when False."""
        event = create_config_changed_event(
            changed_via="cli",
            changes=[],
            is_final_event=False,
        )

        assert "is_final_event" not in event.payload

    @pytest.mark.parametrize("changed_via", ["cli", "sdk", "config_file", "env_var"])
    def test_accepts_valid_changed_via_values(self, changed_via: str) -> None:
        """Should accept all valid changed_via values."""
        event = create_config_changed_event(
            changed_via=changed_via,  # type: ignore[arg-type]
            changes=[],
        )
        assert event.payload["changed_via"] == changed_via


# =============================================================================
# Utility Function Tests
# =============================================================================
class TestCreatePromptHash:
    """Test create_prompt_hash utility function."""

    def test_returns_sha256_hash(self) -> None:
        """Should return a 71-character prefixed SHA-256 hash."""
        hash_value = create_prompt_hash("Hello, world!")
        assert len(hash_value) == 71
        assert hash_value.startswith("sha256:")
        assert re.match(r"^sha256:[a-f0-9]{64}$", hash_value)

    def test_is_deterministic(self) -> None:
        """Same input should always produce same hash."""
        prompt = "Test prompt"
        hash1 = create_prompt_hash(prompt)
        hash2 = create_prompt_hash(prompt)
        assert hash1 == hash2

    def test_different_inputs_produce_different_hashes(self) -> None:
        """Different inputs should produce different hashes."""
        hash1 = create_prompt_hash("Hello")
        hash2 = create_prompt_hash("World")
        assert hash1 != hash2

    def test_empty_string_produces_valid_hash(self) -> None:
        """Empty string should produce valid prefixed SHA-256 hash."""
        hash_value = create_prompt_hash("")
        assert len(hash_value) == 71
        # SHA-256 of empty string with prefix
        assert (
            hash_value == "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_unicode_handling(self) -> None:
        """Should handle unicode strings correctly."""
        hash_value = create_prompt_hash("Hello, \u4e16\u754c!")
        assert len(hash_value) == 71
        assert hash_value.startswith("sha256:")


class TestEventToDict:
    """Test event_to_dict utility function."""

    def test_converts_event_to_dict(self) -> None:
        """Should convert TelemetryEvent to dictionary."""
        event = create_heartbeat_event(
            uptime_seconds=100.0,
            scans_since_last_heartbeat=5,
        )
        result = event_to_dict(event)

        assert isinstance(result, dict)
        assert result["event_id"] == event.event_id
        assert result["event_type"] == "heartbeat"
        assert result["timestamp"] == event.timestamp
        assert result["priority"] == "standard"
        assert result["payload"] == event.payload

    def test_dict_contains_all_fields(self) -> None:
        """Resulting dict should contain all event fields."""
        event = TelemetryEvent(
            event_id="evt_1234567890abcdef",
            event_type="scan",
            timestamp="2025-01-26T10:00:00Z",
            priority="critical",
            payload={"prompt_hash": "a" * 64},
        )
        result = event_to_dict(event)

        assert set(result.keys()) == {
            "event_id",
            "event_type",
            "timestamp",
            "priority",
            "payload",
        }


# =============================================================================
# Pure Function Verification Tests
# =============================================================================
class TestPureFunctions:
    """Verify that all factory functions are pure (no I/O)."""

    def test_installation_event_is_pure(self) -> None:
        """create_installation_event should be a pure function."""
        # Pure function: same inputs -> same output structure (except generated IDs)
        event1 = create_installation_event(
            installation_id="inst_fixed",
            client_version="0.0.1",
            python_version="3.11.5",
            platform="darwin",
            install_method="pip",
        )
        event2 = create_installation_event(
            installation_id="inst_fixed",
            client_version="0.0.1",
            python_version="3.11.5",
            platform="darwin",
            install_method="pip",
        )
        # Payloads should be identical
        assert event1.payload == event2.payload
        assert event1.event_type == event2.event_type
        assert event1.priority == event2.priority

    def test_create_prompt_hash_is_pure(self) -> None:
        """create_prompt_hash should be deterministic."""
        # Pure function: same input -> same output
        result1 = create_prompt_hash("test")
        result2 = create_prompt_hash("test")
        assert result1 == result2

    def test_event_to_dict_is_pure(self) -> None:
        """event_to_dict should be deterministic."""
        event = TelemetryEvent(
            event_id="evt_fixed",
            event_type="test",
            timestamp="2025-01-26T10:00:00Z",
            priority="standard",
            payload={"key": "value"},
        )
        result1 = event_to_dict(event)
        result2 = event_to_dict(event)
        assert result1 == result2


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_scan_event_with_empty_prompt_hash(self) -> None:
        """Should handle empty prompt hash."""
        event = create_scan_event(
            prompt_hash="",
            threat_detected=False,
            scan_duration_ms=1.0,
        )
        assert event.payload["prompt_hash"] == ""

    def test_session_with_zero_duration(self) -> None:
        """Should handle zero session duration."""
        event = create_session_end_event(
            session_id="sess_1234567890abcdef",
            duration_seconds=0.0,
            scans_in_session=0,
            threats_in_session=0,
        )
        assert event.payload["duration_seconds"] == 0.0

    def test_scan_with_zero_duration(self) -> None:
        """Should handle zero scan duration."""
        event = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=False,
            scan_duration_ms=0.0,
        )
        assert event.payload["scan_duration_ms"] == 0.0

    def test_performance_event_with_zero_scans(self) -> None:
        """Should handle zero scan count."""
        event = create_performance_event(
            period_start="2025-01-26T10:00:00Z",
            period_end="2025-01-26T10:01:00Z",
            scan_count=0,
        )
        assert event.payload["scan_count"] == 0

    def test_heartbeat_with_zero_uptime(self) -> None:
        """Should handle zero uptime."""
        event = create_heartbeat_event(
            uptime_seconds=0.0,
            scans_since_last_heartbeat=0,
        )
        assert event.payload["uptime_seconds"] == 0.0

    def test_config_changed_with_empty_changes(self) -> None:
        """Should handle empty changes list."""
        event = create_config_changed_event(
            changed_via="cli",
            changes=[],
        )
        assert event.payload["changes"] == []

    def test_scan_event_with_empty_rule_ids(self) -> None:
        """Should handle empty rule_ids list."""
        event = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=False,
            scan_duration_ms=1.0,
            rule_ids=[],
        )
        assert event.payload["rule_ids"] == []

    def test_negative_values_are_accepted(self) -> None:
        """Factory functions should accept negative values (no validation)."""
        # This tests that domain layer doesn't enforce constraints
        # Validation is done at infrastructure/API layer
        event = create_session_end_event(
            session_id="sess_1234567890abcdef",
            duration_seconds=-1.0,  # Negative duration
            scans_in_session=-5,  # Negative count
            threats_in_session=-2,
        )
        assert event.payload["duration_seconds"] == -1.0
        assert event.payload["scans_in_session"] == -5


# =============================================================================
# Org and Team Context Tests
# =============================================================================
class TestOrgTeamContext:
    """Test org_id and team_id parameters in all factory functions."""

    def test_telemetry_event_stores_org_and_team_ids(self) -> None:
        """TelemetryEvent should store org_id and team_id."""
        event = TelemetryEvent(
            event_id="evt_1234567890abcdef",
            event_type="scan",
            timestamp="2025-01-26T10:00:00Z",
            priority="standard",
            payload={"key": "value"},
            org_id="org_123",
            team_id="team_456",
        )
        assert event.org_id == "org_123"
        assert event.team_id == "team_456"

    def test_telemetry_event_defaults_to_none(self) -> None:
        """TelemetryEvent should default org_id and team_id to None."""
        event = TelemetryEvent(
            event_id="evt_1234567890abcdef",
            event_type="scan",
            timestamp="2025-01-26T10:00:00Z",
            priority="standard",
            payload={"key": "value"},
        )
        assert event.org_id is None
        assert event.team_id is None

    def test_installation_event_with_org_team(self) -> None:
        """create_installation_event should accept org_id and team_id."""
        event = create_installation_event(
            installation_id="inst_1234567890abcdef",
            client_version="0.0.1",
            python_version="3.11.5",
            platform="darwin",
            install_method="pip",
            org_id="org_123",
            team_id="team_456",
        )
        assert event.org_id == "org_123"
        assert event.team_id == "team_456"

    def test_activation_event_with_org_team(self) -> None:
        """create_activation_event should accept org_id and team_id."""
        event = create_activation_event(
            feature="first_scan",
            seconds_since_install=120.5,
            org_id="org_123",
            team_id="team_456",
        )
        assert event.org_id == "org_123"
        assert event.team_id == "team_456"

    def test_session_start_event_with_org_team(self) -> None:
        """create_session_start_event should accept org_id and team_id."""
        event = create_session_start_event(
            session_id="sess_1234567890abcdef",
            session_number=5,
            org_id="org_123",
            team_id="team_456",
        )
        assert event.org_id == "org_123"
        assert event.team_id == "team_456"

    def test_session_end_event_with_org_team(self) -> None:
        """create_session_end_event should accept org_id and team_id."""
        event = create_session_end_event(
            session_id="sess_1234567890abcdef",
            duration_seconds=3600.0,
            scans_in_session=50,
            threats_in_session=3,
            org_id="org_123",
            team_id="team_456",
        )
        assert event.org_id == "org_123"
        assert event.team_id == "team_456"

    def test_scan_event_with_org_team(self) -> None:
        """create_scan_event should accept org_id and team_id."""
        event = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=False,
            scan_duration_ms=4.5,
            org_id="org_123",
            team_id="team_456",
        )
        assert event.org_id == "org_123"
        assert event.team_id == "team_456"

    def test_error_event_with_org_team(self) -> None:
        """create_error_event should accept org_id and team_id."""
        event = create_error_event(
            error_type="validation_error",
            error_code="RAXE_001",
            component="engine",
            org_id="org_123",
            team_id="team_456",
        )
        assert event.org_id == "org_123"
        assert event.team_id == "team_456"

    def test_performance_event_with_org_team(self) -> None:
        """create_performance_event should accept org_id and team_id."""
        event = create_performance_event(
            period_start="2025-01-22T10:00:00Z",
            period_end="2025-01-22T11:00:00Z",
            scan_count=1000,
            org_id="org_123",
            team_id="team_456",
        )
        assert event.org_id == "org_123"
        assert event.team_id == "team_456"

    def test_feature_usage_event_with_org_team(self) -> None:
        """create_feature_usage_event should accept org_id and team_id."""
        event = create_feature_usage_event(
            feature="cli_scan",
            action="completed",
            org_id="org_123",
            team_id="team_456",
        )
        assert event.org_id == "org_123"
        assert event.team_id == "team_456"

    def test_heartbeat_event_with_org_team(self) -> None:
        """create_heartbeat_event should accept org_id and team_id."""
        event = create_heartbeat_event(
            uptime_seconds=3600.0,
            scans_since_last_heartbeat=100,
            org_id="org_123",
            team_id="team_456",
        )
        assert event.org_id == "org_123"
        assert event.team_id == "team_456"

    def test_key_upgrade_event_with_org_team(self) -> None:
        """create_key_upgrade_event should accept org_id and team_id."""
        event = create_key_upgrade_event(
            previous_key_type="temp",
            new_key_type="community",
            org_id="org_123",
            team_id="team_456",
        )
        assert event.org_id == "org_123"
        assert event.team_id == "team_456"

    def test_config_changed_event_with_org_team(self) -> None:
        """create_config_changed_event should accept org_id and team_id."""
        event = create_config_changed_event(
            changed_via="cli",
            changes=[],
            org_id="org_123",
            team_id="team_456",
        )
        assert event.org_id == "org_123"
        assert event.team_id == "team_456"

    def test_event_to_dict_includes_org_team_when_present(self) -> None:
        """event_to_dict should include org_id and team_id when present."""
        event = create_heartbeat_event(
            uptime_seconds=100.0,
            scans_since_last_heartbeat=5,
            org_id="org_123",
            team_id="team_456",
        )
        result = event_to_dict(event)

        assert "org_id" in result
        assert "team_id" in result
        assert result["org_id"] == "org_123"
        assert result["team_id"] == "team_456"

    def test_event_to_dict_excludes_org_team_when_none(self) -> None:
        """event_to_dict should not include org_id and team_id when None."""
        event = create_heartbeat_event(
            uptime_seconds=100.0,
            scans_since_last_heartbeat=5,
        )
        result = event_to_dict(event)

        assert "org_id" not in result
        assert "team_id" not in result

    def test_event_to_dict_includes_org_only_when_team_none(self) -> None:
        """event_to_dict should include only org_id when team_id is None."""
        event = create_heartbeat_event(
            uptime_seconds=100.0,
            scans_since_last_heartbeat=5,
            org_id="org_123",
        )
        result = event_to_dict(event)

        assert "org_id" in result
        assert result["org_id"] == "org_123"
        assert "team_id" not in result

    def test_event_to_dict_includes_team_only_when_org_none(self) -> None:
        """event_to_dict should include only team_id when org_id is None."""
        event = create_heartbeat_event(
            uptime_seconds=100.0,
            scans_since_last_heartbeat=5,
            team_id="team_456",
        )
        result = event_to_dict(event)

        assert "team_id" in result
        assert result["team_id"] == "team_456"
        assert "org_id" not in result
