"""
Unit tests for telemetry priority classification module.

Tests the priority classification logic for all 11 event types.
These tests are PURE - no mocks, no I/O, no database.

Coverage target: >95%
"""
import pytest

from raxe.domain.telemetry.priority import (
    DEFAULT_PRIORITY_CONFIG,
    PriorityConfig,
    classify_priority,
    is_critical_event_type,
    is_standard_event_type,
)


# =============================================================================
# Test Markers
# =============================================================================
pytestmark = [pytest.mark.unit, pytest.mark.domain, pytest.mark.telemetry]


# =============================================================================
# PriorityConfig Tests
# =============================================================================
class TestPriorityConfig:
    """Test PriorityConfig dataclass."""

    def test_default_config_has_critical_severities(self) -> None:
        """Default config should have CRITICAL, HIGH, MEDIUM as critical severities."""
        config = PriorityConfig()
        assert config.critical_severities == frozenset({"CRITICAL", "HIGH", "MEDIUM"})

    def test_default_config_has_always_critical_types(self) -> None:
        """Default config should list always-critical event types."""
        config = PriorityConfig()
        expected = frozenset({
            "installation",
            "activation",
            "session_end",
            "error",
            "key_upgrade",
        })
        assert config.always_critical_types == expected

    def test_default_config_has_always_standard_types(self) -> None:
        """Default config should list always-standard event types."""
        config = PriorityConfig()
        expected = frozenset({
            "session_start",
            "performance",
            "feature_usage",
            "heartbeat",
        })
        assert config.always_standard_types == expected

    def test_priority_config_is_frozen(self) -> None:
        """PriorityConfig should be immutable."""
        config = PriorityConfig()
        # frozenset is immutable by nature
        assert isinstance(config.critical_severities, frozenset)
        assert isinstance(config.always_critical_types, frozenset)
        assert isinstance(config.always_standard_types, frozenset)

    def test_custom_priority_config(self) -> None:
        """Should allow custom priority configuration."""
        config = PriorityConfig(
            critical_severities=frozenset({"CRITICAL"}),
            always_critical_types=frozenset({"error"}),
            always_standard_types=frozenset({"heartbeat"}),
        )
        assert config.critical_severities == frozenset({"CRITICAL"})
        assert config.always_critical_types == frozenset({"error"})
        assert config.always_standard_types == frozenset({"heartbeat"})

    def test_default_priority_config_constant(self) -> None:
        """DEFAULT_PRIORITY_CONFIG should be properly initialized."""
        assert DEFAULT_PRIORITY_CONFIG is not None
        assert isinstance(DEFAULT_PRIORITY_CONFIG, PriorityConfig)


# =============================================================================
# Always Critical Event Types Tests
# =============================================================================
class TestAlwaysCriticalEventTypes:
    """Test event types that are always classified as critical."""

    @pytest.mark.parametrize(
        "event_type",
        [
            "installation",
            "activation",
            "session_end",
            "error",
            "key_upgrade",
        ],
    )
    def test_always_critical_types_return_critical(
        self, event_type: str
    ) -> None:
        """Always-critical event types should return 'critical' priority."""
        result = classify_priority(event_type, {})
        assert result == "critical"

    @pytest.mark.parametrize(
        "event_type",
        [
            "installation",
            "activation",
            "session_end",
            "error",
            "key_upgrade",
        ],
    )
    def test_always_critical_ignores_payload(
        self, event_type: str
    ) -> None:
        """Always-critical types should ignore payload content."""
        # Even with a payload that might suggest standard priority
        payload = {"threat_detected": False, "highest_severity": "LOW"}
        result = classify_priority(event_type, payload)
        assert result == "critical"

    @pytest.mark.parametrize(
        "event_type",
        [
            "INSTALLATION",  # Uppercase
            "Installation",  # Title case
            " installation ",  # With whitespace
            "ERROR",
            " error ",
        ],
    )
    def test_always_critical_case_insensitive(
        self, event_type: str
    ) -> None:
        """Classification should be case-insensitive."""
        result = classify_priority(event_type, {})
        assert result == "critical"


# =============================================================================
# Always Standard Event Types Tests
# =============================================================================
class TestAlwaysStandardEventTypes:
    """Test event types that are always classified as standard."""

    @pytest.mark.parametrize(
        "event_type",
        [
            "session_start",
            "performance",
            "feature_usage",
            "heartbeat",
        ],
    )
    def test_always_standard_types_return_standard(
        self, event_type: str
    ) -> None:
        """Always-standard event types should return 'standard' priority."""
        result = classify_priority(event_type, {})
        assert result == "standard"

    @pytest.mark.parametrize(
        "event_type",
        [
            "session_start",
            "performance",
            "feature_usage",
            "heartbeat",
        ],
    )
    def test_always_standard_ignores_payload(
        self, event_type: str
    ) -> None:
        """Always-standard types should ignore payload content."""
        # Even with a payload that might suggest critical priority
        payload = {"threat_detected": True, "highest_severity": "CRITICAL"}
        result = classify_priority(event_type, payload)
        assert result == "standard"

    @pytest.mark.parametrize(
        "event_type",
        [
            "SESSION_START",  # Uppercase
            "Session_Start",  # Title case
            " session_start ",  # With whitespace
            "HEARTBEAT",
            " heartbeat ",
        ],
    )
    def test_always_standard_case_insensitive(
        self, event_type: str
    ) -> None:
        """Classification should be case-insensitive."""
        result = classify_priority(event_type, {})
        assert result == "standard"


# =============================================================================
# Scan Event Priority Tests
# =============================================================================
class TestScanEventPriority:
    """Test priority classification for scan events."""

    def test_scan_no_threat_is_standard(self) -> None:
        """Scan without threat should have standard priority."""
        payload = {"threat_detected": False}
        result = classify_priority("scan", payload)
        assert result == "standard"

    def test_scan_threat_no_severity_is_standard(self) -> None:
        """Scan with threat but no severity should have standard priority."""
        payload = {"threat_detected": True}
        result = classify_priority("scan", payload)
        assert result == "standard"

    @pytest.mark.parametrize(
        "severity,expected_priority",
        [
            ("CRITICAL", "critical"),
            ("HIGH", "critical"),
            ("MEDIUM", "critical"),
            ("LOW", "standard"),
            ("INFO", "standard"),
            ("NONE", "standard"),
        ],
    )
    def test_scan_priority_by_severity(
        self, severity: str, expected_priority: str
    ) -> None:
        """Scan priority should depend on highest_severity when threat detected."""
        payload = {"threat_detected": True, "highest_severity": severity}
        result = classify_priority("scan", payload)
        assert result == expected_priority

    def test_scan_empty_payload_is_standard(self) -> None:
        """Scan with empty payload should have standard priority."""
        result = classify_priority("scan", {})
        assert result == "standard"

    @pytest.mark.parametrize(
        "severity",
        ["critical", "CRITICAL", "Critical", " CRITICAL "],
    )
    def test_scan_severity_case_insensitive(self, severity: str) -> None:
        """Severity comparison should be case-insensitive."""
        payload = {"threat_detected": True, "highest_severity": severity}
        result = classify_priority("scan", payload)
        assert result == "critical"

    def test_scan_threat_false_with_high_severity_is_standard(self) -> None:
        """Scan with threat_detected=False should be standard even with high severity."""
        payload = {"threat_detected": False, "highest_severity": "CRITICAL"}
        result = classify_priority("scan", payload)
        assert result == "standard"

    def test_scan_with_only_severity_no_threat_is_standard(self) -> None:
        """Scan with only severity (no threat_detected) should be standard."""
        payload = {"highest_severity": "CRITICAL"}
        result = classify_priority("scan", payload)
        assert result == "standard"

    def test_scan_type_case_insensitive(self) -> None:
        """Scan event type should be case-insensitive."""
        payload = {"threat_detected": True, "highest_severity": "HIGH"}
        assert classify_priority("SCAN", payload) == "critical"
        assert classify_priority("Scan", payload) == "critical"
        assert classify_priority(" scan ", payload) == "critical"


# =============================================================================
# Config Changed Event Priority Tests
# =============================================================================
class TestConfigChangedEventPriority:
    """Test priority classification for config_changed events."""

    def test_config_changed_normal_is_standard(self) -> None:
        """Normal config changes should have standard priority."""
        payload = {"changes": {"detection": {"l2_enabled": False}}}
        result = classify_priority("config_changed", payload)
        assert result == "standard"

    def test_config_changed_empty_payload_is_standard(self) -> None:
        """Config change with empty payload should have standard priority."""
        result = classify_priority("config_changed", {})
        assert result == "standard"

    def test_config_changed_telemetry_disabled_nested_is_critical(self) -> None:
        """Disabling telemetry (nested structure) should have critical priority."""
        payload = {"changes": {"telemetry": {"enabled": False}}}
        result = classify_priority("config_changed", payload)
        assert result == "critical"

    def test_config_changed_telemetry_disabled_flat_is_critical(self) -> None:
        """Disabling telemetry (flat structure) should have critical priority."""
        payload = {"changes": {"telemetry.enabled": False}}
        result = classify_priority("config_changed", payload)
        assert result == "critical"

    def test_config_changed_telemetry_enabled_is_standard(self) -> None:
        """Enabling telemetry should have standard priority."""
        payload = {"changes": {"telemetry": {"enabled": True}}}
        result = classify_priority("config_changed", payload)
        assert result == "standard"

    def test_config_changed_setting_new_value_false_is_critical(self) -> None:
        """Using setting/new_value structure with telemetry disabled is critical."""
        payload = {"setting": "telemetry.enabled", "new_value": False}
        result = classify_priority("config_changed", payload)
        assert result == "critical"

    def test_config_changed_setting_new_value_true_is_standard(self) -> None:
        """Using setting/new_value structure with telemetry enabled is standard."""
        payload = {"setting": "telemetry.enabled", "new_value": True}
        result = classify_priority("config_changed", payload)
        assert result == "standard"

    def test_config_changed_other_setting_is_standard(self) -> None:
        """Other settings should have standard priority."""
        payload = {"setting": "detection.l2_enabled", "new_value": False}
        result = classify_priority("config_changed", payload)
        assert result == "standard"

    def test_config_changed_non_dict_telemetry_is_standard(self) -> None:
        """Non-dict telemetry value should be standard priority."""
        payload = {"changes": {"telemetry": "disabled"}}  # String, not dict
        result = classify_priority("config_changed", payload)
        assert result == "standard"


# =============================================================================
# Unknown Event Types Tests
# =============================================================================
class TestUnknownEventTypes:
    """Test priority classification for unknown event types."""

    @pytest.mark.parametrize(
        "event_type",
        [
            "unknown_type",
            "custom_event",
            "my_event",
            "",
            "12345",
        ],
    )
    def test_unknown_types_return_standard(self, event_type: str) -> None:
        """Unknown event types should default to standard priority."""
        result = classify_priority(event_type, {})
        assert result == "standard"

    def test_unknown_type_ignores_payload(self) -> None:
        """Unknown types should return standard regardless of payload."""
        payload = {"threat_detected": True, "highest_severity": "CRITICAL"}
        result = classify_priority("unknown_event", payload)
        assert result == "standard"


# =============================================================================
# Custom Config Tests
# =============================================================================
class TestCustomConfig:
    """Test priority classification with custom configuration."""

    def test_custom_critical_severities(self) -> None:
        """Should use custom critical severities."""
        config = PriorityConfig(critical_severities=frozenset({"CRITICAL"}))
        payload = {"threat_detected": True, "highest_severity": "HIGH"}

        # With default config, HIGH is critical
        assert classify_priority("scan", payload, None) == "critical"

        # With custom config, only CRITICAL is critical
        assert classify_priority("scan", payload, config) == "standard"

    def test_custom_always_critical_types(self) -> None:
        """Should use custom always-critical types."""
        config = PriorityConfig(
            always_critical_types=frozenset({"custom_critical"}),
            always_standard_types=frozenset({"installation"}),  # Override default
        )

        # Custom type is now critical
        assert classify_priority("custom_critical", {}, config) == "critical"

        # installation is now standard (moved from critical)
        assert classify_priority("installation", {}, config) == "standard"

    def test_custom_always_standard_types(self) -> None:
        """Should use custom always-standard types."""
        config = PriorityConfig(
            always_critical_types=frozenset({"error"}),
            always_standard_types=frozenset({"heartbeat", "custom_standard"}),
        )

        # Custom type is now standard
        assert classify_priority("custom_standard", {}, config) == "standard"


# =============================================================================
# Convenience Function Tests
# =============================================================================
class TestIsCriticalEventType:
    """Test is_critical_event_type convenience function."""

    @pytest.mark.parametrize(
        "event_type",
        [
            "installation",
            "activation",
            "session_end",
            "error",
            "key_upgrade",
        ],
    )
    def test_returns_true_for_critical_types(self, event_type: str) -> None:
        """Should return True for always-critical event types."""
        assert is_critical_event_type(event_type) is True

    @pytest.mark.parametrize(
        "event_type",
        [
            "session_start",
            "performance",
            "feature_usage",
            "heartbeat",
            "scan",  # Conditional, not always critical
            "config_changed",  # Conditional
            "unknown",
        ],
    )
    def test_returns_false_for_non_critical_types(
        self, event_type: str
    ) -> None:
        """Should return False for non-always-critical event types."""
        assert is_critical_event_type(event_type) is False

    def test_case_insensitive(self) -> None:
        """Should be case-insensitive."""
        assert is_critical_event_type("ERROR") is True
        assert is_critical_event_type("Error") is True
        assert is_critical_event_type(" error ") is True

    def test_with_custom_config(self) -> None:
        """Should use custom config when provided."""
        config = PriorityConfig(always_critical_types=frozenset({"custom"}))
        assert is_critical_event_type("custom", config) is True
        assert is_critical_event_type("error", config) is False


class TestIsStandardEventType:
    """Test is_standard_event_type convenience function."""

    @pytest.mark.parametrize(
        "event_type",
        [
            "session_start",
            "performance",
            "feature_usage",
            "heartbeat",
        ],
    )
    def test_returns_true_for_standard_types(self, event_type: str) -> None:
        """Should return True for always-standard event types."""
        assert is_standard_event_type(event_type) is True

    @pytest.mark.parametrize(
        "event_type",
        [
            "installation",
            "activation",
            "session_end",
            "error",
            "key_upgrade",
            "scan",  # Conditional
            "config_changed",  # Conditional
            "unknown",
        ],
    )
    def test_returns_false_for_non_standard_types(
        self, event_type: str
    ) -> None:
        """Should return False for non-always-standard event types."""
        assert is_standard_event_type(event_type) is False

    def test_case_insensitive(self) -> None:
        """Should be case-insensitive."""
        assert is_standard_event_type("HEARTBEAT") is True
        assert is_standard_event_type("Heartbeat") is True
        assert is_standard_event_type(" heartbeat ") is True

    def test_with_custom_config(self) -> None:
        """Should use custom config when provided."""
        config = PriorityConfig(always_standard_types=frozenset({"custom"}))
        assert is_standard_event_type("custom", config) is True
        assert is_standard_event_type("heartbeat", config) is False


# =============================================================================
# All 11 Event Types Comprehensive Test
# =============================================================================
class TestAllEventTypes:
    """Comprehensive test for all 11 event types."""

    @pytest.mark.parametrize(
        "event_type,expected_behavior",
        [
            ("installation", "always_critical"),
            ("activation", "always_critical"),
            ("session_start", "always_standard"),
            ("session_end", "always_critical"),
            ("scan", "conditional"),
            ("error", "always_critical"),
            ("performance", "always_standard"),
            ("feature_usage", "always_standard"),
            ("heartbeat", "always_standard"),
            ("key_upgrade", "always_critical"),
            ("config_changed", "conditional"),
        ],
    )
    def test_all_event_types_classified_correctly(
        self, event_type: str, expected_behavior: str
    ) -> None:
        """Each event type should be classified according to its behavior."""
        if expected_behavior == "always_critical":
            assert classify_priority(event_type, {}) == "critical"
            assert is_critical_event_type(event_type) is True
            assert is_standard_event_type(event_type) is False
        elif expected_behavior == "always_standard":
            assert classify_priority(event_type, {}) == "standard"
            assert is_critical_event_type(event_type) is False
            assert is_standard_event_type(event_type) is True
        elif expected_behavior == "conditional":
            # Conditional types with empty payload default to standard
            assert classify_priority(event_type, {}) == "standard"
            assert is_critical_event_type(event_type) is False
            assert is_standard_event_type(event_type) is False


# =============================================================================
# Pure Function Verification Tests
# =============================================================================
class TestPureFunctions:
    """Verify that all functions are pure (no I/O)."""

    def test_classify_priority_is_deterministic(self) -> None:
        """classify_priority should be deterministic."""
        payload = {"threat_detected": True, "highest_severity": "HIGH"}
        result1 = classify_priority("scan", payload)
        result2 = classify_priority("scan", payload)
        assert result1 == result2

    def test_classify_priority_does_not_modify_payload(self) -> None:
        """classify_priority should not modify the input payload."""
        payload = {"threat_detected": True, "highest_severity": "HIGH"}
        original_payload = payload.copy()
        classify_priority("scan", payload)
        assert payload == original_payload

    def test_is_critical_event_type_is_deterministic(self) -> None:
        """is_critical_event_type should be deterministic."""
        result1 = is_critical_event_type("error")
        result2 = is_critical_event_type("error")
        assert result1 == result2

    def test_is_standard_event_type_is_deterministic(self) -> None:
        """is_standard_event_type should be deterministic."""
        result1 = is_standard_event_type("heartbeat")
        result2 = is_standard_event_type("heartbeat")
        assert result1 == result2


# =============================================================================
# Edge Cases Tests
# =============================================================================
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_event_type(self) -> None:
        """Empty event type should return standard."""
        assert classify_priority("", {}) == "standard"

    def test_whitespace_only_event_type(self) -> None:
        """Whitespace-only event type should return standard."""
        assert classify_priority("   ", {}) == "standard"

    def test_none_in_payload_values(self) -> None:
        """Should handle None values in payload."""
        payload = {"threat_detected": None, "highest_severity": None}
        result = classify_priority("scan", payload)
        assert result == "standard"

    def test_non_string_severity(self) -> None:
        """Should handle non-string severity values."""
        payload = {"threat_detected": True, "highest_severity": 123}
        result = classify_priority("scan", payload)
        assert result == "standard"

    def test_nested_empty_changes(self) -> None:
        """Should handle empty nested changes."""
        payload = {"changes": {}}
        result = classify_priority("config_changed", payload)
        assert result == "standard"

    def test_deeply_nested_payload(self) -> None:
        """Should handle deeply nested payloads."""
        payload = {"changes": {"a": {"b": {"c": {"telemetry": {"enabled": False}}}}}}
        # Only checks first level of "changes"
        result = classify_priority("config_changed", payload)
        assert result == "standard"
