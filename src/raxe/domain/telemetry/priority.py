"""
Pure functions for classifying telemetry event priority.

This module contains ONLY pure functions - no I/O operations.
All functions take data and return data without side effects.

Priority classification determines which queue an event goes to:
- Critical queue (5s flush): High-priority events that need rapid delivery
- Standard queue (5m flush): Normal events that can be batched

See specification section 9.1 for queue tier definitions.
"""

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class PriorityConfig:
    """Configuration for priority classification.

    Immutable configuration object containing the rules for classifying
    event priority. Uses frozensets for immutability and O(1) lookups.

    Attributes:
        critical_severities: Severity levels that trigger critical priority
            for scan events with threat detection.
        always_critical_types: Event types that are always critical regardless
            of payload content.
        always_standard_types: Event types that are always standard regardless
            of payload content.
    """

    critical_severities: frozenset[str] = frozenset({"CRITICAL", "HIGH", "MEDIUM"})
    always_critical_types: frozenset[str] = frozenset({
        "installation",
        "activation",
        "session_end",
        "error",
        "key_upgrade",
    })
    always_standard_types: frozenset[str] = frozenset({
        "session_start",
        "performance",
        "feature_usage",
        "heartbeat",
    })


# Default configuration instance for convenience
DEFAULT_PRIORITY_CONFIG = PriorityConfig()


def classify_priority(
    event_type: str,
    payload: dict[str, Any],
    config: PriorityConfig | None = None,
) -> Literal["critical", "standard"]:
    """
    Classify event priority based on type and payload.

    This is a PURE function - no I/O, deterministic output.
    Classification rules are defined in specification section 9.1.

    Priority Rules:
        1. Always Critical: installation, activation, session_end, error, key_upgrade
        2. Always Standard: session_start, performance, feature_usage, heartbeat
        3. Conditional (scan events):
           - Critical IF threat_detected AND severity in [CRITICAL, HIGH, MEDIUM]
           - Standard IF no threat OR severity in [LOW, INFO, NONE]
        4. Conditional (config_changed):
           - Critical IF changing telemetry.enabled to false
           - Standard for most other config changes
        5. Default: standard (for unknown event types)

    Args:
        event_type: The type of telemetry event (e.g., "scan", "error", "heartbeat").
        payload: The event payload containing event-specific data.
        config: Optional configuration for priority classification.
            Uses DEFAULT_PRIORITY_CONFIG if not provided.

    Returns:
        Priority level as literal "critical" or "standard".

    Examples:
        >>> classify_priority("error", {"message": "API failure"})
        'critical'

        >>> classify_priority("heartbeat", {"timestamp": "2025-01-22T10:00:00Z"})
        'standard'

        >>> classify_priority("scan", {"threat_detected": True, "highest_severity": "HIGH"})
        'critical'

        >>> classify_priority("scan", {"threat_detected": False})
        'standard'
    """
    if config is None:
        config = DEFAULT_PRIORITY_CONFIG

    # Normalize event type to lowercase for consistent matching
    normalized_type = event_type.lower().strip()

    # Rule 1: Always critical event types
    if normalized_type in config.always_critical_types:
        return "critical"

    # Rule 2: Always standard event types
    if normalized_type in config.always_standard_types:
        return "standard"

    # Rule 3: Scan events - conditional based on threat detection
    if normalized_type == "scan":
        return _classify_scan_priority(payload, config)

    # Rule 4: Config changes - conditional based on what changed
    if normalized_type == "config_changed":
        return _classify_config_change_priority(payload)

    # Default: standard priority for unknown event types
    return "standard"


def _classify_scan_priority(
    payload: dict[str, Any],
    config: PriorityConfig,
) -> Literal["critical", "standard"]:
    """
    Classify priority for scan events based on detection results.

    A scan event is critical if:
    1. A threat was detected (threat_detected=True), AND
    2. The highest severity is CRITICAL, HIGH, or MEDIUM

    Args:
        payload: Scan event payload containing detection results.
        config: Priority configuration with critical severity levels.

    Returns:
        "critical" if scan detected significant threat, "standard" otherwise.
    """
    # Check if threat was detected
    threat_detected = payload.get("threat_detected", False)
    if not threat_detected:
        return "standard"

    # Check severity level
    highest_severity = payload.get("highest_severity")
    if highest_severity is None:
        # No severity info but threat detected - be conservative, treat as standard
        return "standard"

    # Normalize severity to uppercase for comparison
    severity_upper = str(highest_severity).upper().strip()

    if severity_upper in config.critical_severities:
        return "critical"

    return "standard"


def _classify_config_change_priority(
    payload: dict[str, Any],
) -> Literal["critical", "standard"]:
    """
    Classify priority for config_changed events.

    Config changes are critical when:
    - Disabling telemetry (telemetry.enabled -> false)

    This ensures we capture the "last message" before telemetry is disabled.

    Args:
        payload: Config change payload containing change details.

    Returns:
        "critical" if disabling telemetry, "standard" otherwise.
    """
    # Check for telemetry being disabled
    changes = payload.get("changes", {})

    # Handle nested structure: {"telemetry": {"enabled": false}}
    telemetry_changes = changes.get("telemetry", {})
    if isinstance(telemetry_changes, dict):
        if telemetry_changes.get("enabled") is False:
            return "critical"

    # Handle flat structure: {"telemetry.enabled": false}
    if changes.get("telemetry.enabled") is False:
        return "critical"

    # Handle old_value/new_value structure
    if payload.get("setting") == "telemetry.enabled":
        if payload.get("new_value") is False:
            return "critical"

    return "standard"


def is_critical_event_type(
    event_type: str,
    config: PriorityConfig | None = None,
) -> bool:
    """
    Check if an event type is always classified as critical.

    This is a convenience function for checking static priority
    without needing to examine the payload.

    Args:
        event_type: The event type to check.
        config: Optional priority configuration.

    Returns:
        True if the event type is always critical, False otherwise.

    Examples:
        >>> is_critical_event_type("error")
        True

        >>> is_critical_event_type("heartbeat")
        False

        >>> is_critical_event_type("scan")  # Depends on payload
        False
    """
    if config is None:
        config = DEFAULT_PRIORITY_CONFIG

    return event_type.lower().strip() in config.always_critical_types


def is_standard_event_type(
    event_type: str,
    config: PriorityConfig | None = None,
) -> bool:
    """
    Check if an event type is always classified as standard.

    This is a convenience function for checking static priority
    without needing to examine the payload.

    Args:
        event_type: The event type to check.
        config: Optional priority configuration.

    Returns:
        True if the event type is always standard, False otherwise.

    Examples:
        >>> is_standard_event_type("heartbeat")
        True

        >>> is_standard_event_type("error")
        False

        >>> is_standard_event_type("scan")  # Depends on payload
        False
    """
    if config is None:
        config = DEFAULT_PRIORITY_CONFIG

    return event_type.lower().strip() in config.always_standard_types
