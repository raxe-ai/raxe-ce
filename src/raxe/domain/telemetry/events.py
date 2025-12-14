"""
Telemetry event factory module with all 12 event types.

This module contains ONLY pure functions - no I/O operations.
All functions take data and return data without side effects.

Event Types:
- installation: Fired once on first import/install
- activation: Tracks first use of specific features
- session_start: Fired when Python interpreter session begins
- session_end: Fired when session ends
- scan: Core telemetry event for each threat detection scan
- error: Fired when an error occurs
- performance: Aggregated performance metrics
- feature_usage: Tracks usage of specific features
- heartbeat: Periodic health signal
- key_upgrade: Fired when API key is upgraded
- config_changed: Fired when configuration is changed
- team_invite: Tracks team invitations for viral growth metrics

Priority Assignment:
- Critical: installation, activation, session_end, error, key_upgrade, team_invite
- Standard: session_start, performance, feature_usage, heartbeat
- Conditional: scan (critical if threat HIGH+), config_changed (critical if disabling telemetry)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from .event_creator import hash_text


class EventType(str, Enum):
    """Enumeration of all telemetry event types."""

    INSTALLATION = "installation"
    ACTIVATION = "activation"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    SCAN = "scan"
    ERROR = "error"
    PERFORMANCE = "performance"
    FEATURE_USAGE = "feature_usage"
    HEARTBEAT = "heartbeat"
    KEY_UPGRADE = "key_upgrade"
    CONFIG_CHANGED = "config_changed"
    TEAM_INVITE = "team_invite"


@dataclass(frozen=True)
class TelemetryEvent:
    """Immutable telemetry event container.

    Attributes:
        event_id: Unique event identifier with evt_ prefix.
        event_type: Type of event from EventType enum.
        timestamp: ISO 8601 UTC timestamp of event creation.
        priority: Event priority level (critical or standard).
        payload: Event-specific data dictionary.
        org_id: Organization ID for multi-tenant tracking (optional).
        team_id: Team ID for team-level analytics (optional).
    """

    event_id: str
    event_type: str
    timestamp: str
    priority: Literal["critical", "standard"]
    payload: dict[str, Any]
    org_id: str | None = None
    team_id: str | None = None


# =============================================================================
# ID Generators
# =============================================================================


def generate_event_id() -> str:
    """Generate a unique event identifier.

    Returns:
        Event ID with evt_ prefix followed by 16 hex characters.

    Example:
        >>> generate_event_id()
        'evt_a1b2c3d4e5f67890'
    """
    return f"evt_{uuid4().hex[:16]}"


def generate_installation_id() -> str:
    """Generate a unique installation identifier.

    Returns:
        Installation ID with inst_ prefix followed by 16 hex characters.

    Example:
        >>> generate_installation_id()
        'inst_a1b2c3d4e5f67890'
    """
    return f"inst_{uuid4().hex[:16]}"


def generate_session_id() -> str:
    """Generate a unique session identifier.

    Returns:
        Session ID with sess_ prefix followed by 16 hex characters.

    Example:
        >>> generate_session_id()
        'sess_a1b2c3d4e5f67890'
    """
    return f"sess_{uuid4().hex[:16]}"


def generate_batch_id() -> str:
    """Generate a unique batch identifier.

    Returns:
        Batch ID with batch_ prefix followed by 16 hex characters.

    Example:
        >>> generate_batch_id()
        'batch_a1b2c3d4e5f67890'
    """
    return f"batch_{uuid4().hex[:16]}"


def _get_utc_timestamp() -> str:
    """Get current UTC timestamp in ISO 8601 format.

    Returns:
        ISO 8601 formatted UTC timestamp string.
    """
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Installation Event
# =============================================================================


def create_installation_event(
    installation_id: str,
    client_version: str,
    python_version: str,
    platform: Literal["darwin", "linux", "win32"],
    install_method: Literal["pip", "uv", "pipx", "poetry", "conda", "source", "docker", "unknown"],
    *,
    key_type: Literal["temp", "community", "pro", "enterprise"] = "temp",
    ml_available: bool | None = None,
    installed_extras: list[str] | None = None,
    platform_version: str | None = None,
    acquisition_source: Literal[
        "pip_install",
        "github_release",
        "docker",
        "homebrew",
        "website_download",
        "referral",
        "enterprise_deploy",
        "ci_integration",
        "unknown",
    ] = "unknown",
    org_id: str | None = None,
    team_id: str | None = None,
) -> TelemetryEvent:
    """Create an installation telemetry event.

    Fired once on first import/install of RAXE.

    Args:
        installation_id: Unique installation identifier (inst_ prefix).
        client_version: RAXE version installed.
        python_version: Python interpreter version.
        platform: Operating system platform.
        install_method: Package manager used for installation.
        key_type: API key tier at installation time.
            - temp: Temporary key (auto-generated, 14-day expiry)
            - community: Free registered user
            - pro: Paid individual user
            - enterprise: Team/organization plan
        ml_available: Whether ML dependencies are installed.
        installed_extras: List of installed optional extras.
        platform_version: OS version string.
        acquisition_source: How the user discovered/acquired RAXE.
            - pip_install: Installed via pip install raxe
            - github_release: Downloaded from GitHub releases
            - docker: Installed via Docker image
            - homebrew: Installed via brew install raxe
            - website_download: Downloaded from raxe.ai
            - referral: Referred by another user (via RAXE_REFERRAL_CODE)
            - enterprise_deploy: Enterprise deployment
            - ci_integration: Installed in CI/CD pipeline
            - unknown: Default/fallback
        org_id: Organization ID for multi-tenant tracking.
        team_id: Team ID for team-level analytics.

    Returns:
        TelemetryEvent with installation payload.

    Example:
        >>> event = create_installation_event(
        ...     installation_id="inst_abc123",
        ...     client_version="0.0.1",
        ...     python_version="3.11.5",
        ...     platform="darwin",
        ...     install_method="pip",
        ...     ml_available=True,
        ...     installed_extras=["ml", "openai"],
        ...     acquisition_source="pip_install",
        ...     org_id="org_123",
        ...     team_id="team_456",
        ... )
    """
    payload: dict[str, Any] = {
        "installation_id": installation_id,
        "client_version": client_version,
        "python_version": python_version,
        "platform": platform,
        "install_method": install_method,
        "key_type": key_type,
        "acquisition_source": acquisition_source,
    }

    if ml_available is not None:
        payload["ml_available"] = ml_available

    if installed_extras is not None:
        payload["installed_extras"] = installed_extras

    if platform_version is not None:
        payload["platform_version"] = platform_version

    return TelemetryEvent(
        event_id=generate_event_id(),
        event_type=EventType.INSTALLATION.value,
        timestamp=_get_utc_timestamp(),
        priority="critical",
        payload=payload,
        org_id=org_id,
        team_id=team_id,
    )


# =============================================================================
# Activation Event
# =============================================================================


def create_activation_event(
    feature: Literal[
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
    seconds_since_install: float,
    *,
    activation_context: dict[str, Any] | None = None,
    org_id: str | None = None,
    team_id: str | None = None,
) -> TelemetryEvent:
    """Create an activation telemetry event.

    Tracks first use of specific features (time-to-value metrics).

    Args:
        feature: Feature being activated for the first time.
            Canonical values aligned with backend:
            - first_scan: First prompt scan performed
            - first_threat: First threat detected
            - first_block: First threat blocked by policy
            - first_cli: First CLI command executed
            - first_sdk: First SDK API call
            - first_decorator: First use of @protect decorator
            - first_wrapper: First use of OpenAI/Anthropic wrapper
            - first_langchain: First LangChain integration use
            - first_l2_detection: First ML-based (L2) detection
            - first_custom_rule: First custom rule loaded
        seconds_since_install: Time elapsed since installation event.
        activation_context: Additional context about the activation.
        org_id: Organization ID for multi-tenant tracking.
        team_id: Team ID for team-level analytics.

    Returns:
        TelemetryEvent with activation payload.

    Example:
        >>> event = create_activation_event(
        ...     feature="first_scan",
        ...     seconds_since_install=120.5,
        ...     activation_context={"entry_point": "cli"},
        ...     org_id="org_123",
        ...     team_id="team_456",
        ... )
    """
    payload: dict[str, Any] = {
        "feature": feature,
        "seconds_since_install": seconds_since_install,
    }

    if activation_context is not None:
        payload["activation_context"] = activation_context

    return TelemetryEvent(
        event_id=generate_event_id(),
        event_type=EventType.ACTIVATION.value,
        timestamp=_get_utc_timestamp(),
        priority="critical",
        payload=payload,
        org_id=org_id,
        team_id=team_id,
    )


# =============================================================================
# Session Start Event
# =============================================================================


def create_session_start_event(
    session_id: str,
    session_number: int,
    *,
    entry_point: Literal["cli", "sdk", "wrapper", "integration", "repl"] | None = None,
    previous_session_gap_hours: float | None = None,
    environment: dict[str, bool] | None = None,
    org_id: str | None = None,
    team_id: str | None = None,
) -> TelemetryEvent:
    """Create a session start telemetry event.

    Fired when a new Python interpreter session begins (DAU/WAU/MAU tracking).

    Args:
        session_id: Unique session identifier (sess_ prefix).
        session_number: Sequential session count for this installation.
        entry_point: How RAXE was invoked.
        previous_session_gap_hours: Hours since last session ended.
        environment: Session environment details (is_ci, is_interactive, is_notebook).
        org_id: Organization ID for multi-tenant tracking.
        team_id: Team ID for team-level analytics.

    Returns:
        TelemetryEvent with session_start payload.

    Example:
        >>> event = create_session_start_event(
        ...     session_id="sess_abc123",
        ...     session_number=5,
        ...     entry_point="cli",
        ...     previous_session_gap_hours=24.5,
        ...     environment={"is_ci": False, "is_interactive": True},
        ...     org_id="org_123",
        ...     team_id="team_456",
        ... )
    """
    payload: dict[str, Any] = {
        "session_id": session_id,
        "session_number": session_number,
    }

    if entry_point is not None:
        payload["entry_point"] = entry_point

    if previous_session_gap_hours is not None:
        payload["previous_session_gap_hours"] = previous_session_gap_hours

    if environment is not None:
        payload["environment"] = environment

    return TelemetryEvent(
        event_id=generate_event_id(),
        event_type=EventType.SESSION_START.value,
        timestamp=_get_utc_timestamp(),
        priority="standard",
        payload=payload,
        org_id=org_id,
        team_id=team_id,
    )


# =============================================================================
# Session End Event
# =============================================================================


def create_session_end_event(
    session_id: str,
    duration_seconds: float,
    scans_in_session: int,
    threats_in_session: int,
    *,
    end_reason: Literal["normal", "error", "timeout", "interrupt", "unknown"] | None = None,
    peak_memory_mb: float | None = None,
    features_used: list[str] | None = None,
    org_id: str | None = None,
    team_id: str | None = None,
) -> TelemetryEvent:
    """Create a session end telemetry event.

    Fired when Python interpreter session ends (engagement metrics).

    Args:
        session_id: Session being ended (sess_ prefix).
        duration_seconds: Total session duration.
        scans_in_session: Number of scans performed.
        threats_in_session: Number of threats detected.
        end_reason: How session ended.
        peak_memory_mb: Peak memory usage during session.
        features_used: Features used during session.
        org_id: Organization ID for multi-tenant tracking.
        team_id: Team ID for team-level analytics.

    Returns:
        TelemetryEvent with session_end payload.

    Example:
        >>> event = create_session_end_event(
        ...     session_id="sess_abc123",
        ...     duration_seconds=3600.0,
        ...     scans_in_session=50,
        ...     threats_in_session=3,
        ...     end_reason="normal",
        ...     peak_memory_mb=150.5,
        ...     features_used=["cli", "explain"],
        ...     org_id="org_123",
        ...     team_id="team_456",
        ... )
    """
    payload: dict[str, Any] = {
        "session_id": session_id,
        "duration_seconds": duration_seconds,
        "scans_in_session": scans_in_session,
        "threats_in_session": threats_in_session,
    }

    if end_reason is not None:
        payload["end_reason"] = end_reason

    if peak_memory_mb is not None:
        payload["peak_memory_mb"] = peak_memory_mb

    if features_used is not None:
        payload["features_used"] = features_used

    return TelemetryEvent(
        event_id=generate_event_id(),
        event_type=EventType.SESSION_END.value,
        timestamp=_get_utc_timestamp(),
        priority="critical",
        payload=payload,
        org_id=org_id,
        team_id=team_id,
    )


# =============================================================================
# Scan Event
# =============================================================================


def create_scan_event(
    prompt_hash: str,
    threat_detected: bool,
    scan_duration_ms: float,
    *,
    event_id: str | None = None,
    detection_count: int | None = None,
    highest_severity: Literal["none", "low", "medium", "high", "critical"] | None = None,
    rule_ids: list[str] | None = None,
    families: list[str] | None = None,
    l1_duration_ms: float | None = None,
    l2_duration_ms: float | None = None,
    l1_hit: bool | None = None,
    l2_hit: bool | None = None,
    l2_enabled: bool | None = None,
    prompt_length: int | None = None,
    action_taken: Literal["allow", "block", "warn", "redact"] | None = None,
    entry_point: Literal["cli", "sdk", "wrapper", "integration"] | None = None,
    wrapper_type: Literal["openai", "anthropic", "langchain", "none"] | None = None,
    org_id: str | None = None,
    team_id: str | None = None,
) -> TelemetryEvent:
    """Create a scan telemetry event.

    Core telemetry event for each threat detection scan.

    Args:
        prompt_hash: SHA-256 hash of prompt for deduplication.
        threat_detected: Whether any threat was detected.
        scan_duration_ms: Total scan duration in milliseconds.
        event_id: Optional event ID. If not provided, one will be generated.
        detection_count: Number of detections found.
        highest_severity: Highest severity among detections.
        rule_ids: List of triggered rule IDs (up to 10).
        families: Threat families detected (PI, JB, PII, etc.).
        l1_duration_ms: L1 (rule-based) scan duration.
        l2_duration_ms: L2 (ML-based) scan duration.
        l1_hit: L1 detection triggered.
        l2_hit: L2 detection triggered.
        l2_enabled: Whether L2 was enabled for this scan.
        prompt_length: Character length of scanned prompt.
        action_taken: Action taken based on policy.
        entry_point: How the scan was triggered.
        wrapper_type: Wrapper used if applicable.
        org_id: Organization ID for multi-tenant tracking.
        team_id: Team ID for team-level analytics.

    Returns:
        TelemetryEvent with scan payload. Priority is critical if
        highest_severity is HIGH or CRITICAL, otherwise standard.

    Example:
        >>> event = create_scan_event(
        ...     prompt_hash="a" * 64,
        ...     threat_detected=True,
        ...     scan_duration_ms=4.5,
        ...     detection_count=2,
        ...     highest_severity="HIGH",
        ...     rule_ids=["pi-001", "pi-002"],
        ...     families=["PI"],
        ...     org_id="org_123",
        ...     team_id="team_456",
        ... )
    """
    payload: dict[str, Any] = {
        "prompt_hash": prompt_hash,
        "threat_detected": threat_detected,
        "scan_duration_ms": scan_duration_ms,
    }

    if detection_count is not None:
        payload["detection_count"] = detection_count

    if highest_severity is not None:
        payload["highest_severity"] = highest_severity

    if rule_ids is not None:
        # Limit to 10 rule IDs as per schema
        payload["rule_ids"] = rule_ids[:10]

    if families is not None:
        payload["families"] = families

    if l1_duration_ms is not None:
        payload["l1_duration_ms"] = l1_duration_ms

    if l2_duration_ms is not None:
        payload["l2_duration_ms"] = l2_duration_ms

    if l1_hit is not None:
        payload["l1_hit"] = l1_hit

    if l2_hit is not None:
        payload["l2_hit"] = l2_hit

    if l2_enabled is not None:
        payload["l2_enabled"] = l2_enabled

    if prompt_length is not None:
        payload["prompt_length"] = prompt_length

    if action_taken is not None:
        payload["action_taken"] = action_taken

    if entry_point is not None:
        payload["entry_point"] = entry_point

    if wrapper_type is not None:
        payload["wrapper_type"] = wrapper_type

    # Priority is critical if threat is HIGH or CRITICAL severity
    priority: Literal["critical", "standard"] = "standard"
    if highest_severity in ("high", "critical"):
        priority = "critical"

    return TelemetryEvent(
        event_id=event_id if event_id else generate_event_id(),
        event_type=EventType.SCAN.value,
        timestamp=_get_utc_timestamp(),
        priority=priority,
        payload=payload,
        org_id=org_id,
        team_id=team_id,
    )


# =============================================================================
# Scan Event v2.0 (Full L2 Telemetry)
# =============================================================================

# Schema version for v2 events
SCAN_SCHEMA_VERSION = "2.0.0"


def create_scan_event_v2(
    payload: dict[str, Any],
    *,
    event_id: str | None = None,
    org_id: str | None = None,
    team_id: str | None = None,
) -> TelemetryEvent:
    """Create a scan telemetry event using schema v2.0.

    This function accepts a pre-built payload from ScanTelemetryBuilder.
    The payload must conform to SCAN_TELEMETRY_SCHEMA.md.

    Args:
        payload: Pre-built payload dict from ScanTelemetryBuilder.build()
        event_id: Optional event ID. If not provided, one will be generated.
        org_id: Organization ID for multi-tenant tracking.
        team_id: Team ID for team-level analytics.

    Returns:
        TelemetryEvent with scan payload and schema_version.

    Example:
        >>> from raxe.domain.telemetry.scan_telemetry_builder import build_scan_telemetry
        >>> payload = build_scan_telemetry(prompt, l1_result, l2_result, duration_ms)
        >>> event = create_scan_event_v2(payload)
    """
    # Add schema version to payload
    payload_with_version = {"schema_version": SCAN_SCHEMA_VERSION, **payload}

    # Determine priority from L1/L2 severity
    priority: Literal["critical", "standard"] = "standard"

    # Check L1 severity
    l1_block = payload.get("l1", {})
    if l1_block.get("highest_severity") in ("high", "critical"):
        priority = "critical"

    # Check L2 classification
    l2_block = payload.get("l2", {})
    if l2_block.get("classification") in ("HIGH_THREAT", "THREAT"):
        priority = "critical"

    # Also critical if threat detected
    if payload.get("threat_detected"):
        priority = "critical"

    return TelemetryEvent(
        event_id=event_id if event_id else generate_event_id(),
        event_type=EventType.SCAN.value,
        timestamp=_get_utc_timestamp(),
        priority=priority,
        payload=payload_with_version,
        org_id=org_id,
        team_id=team_id,
    )


# =============================================================================
# Error Event
# =============================================================================


def create_error_event(
    error_type: Literal[
        "validation_error",
        "configuration_error",
        "rule_loading_error",
        "ml_model_error",
        "network_error",
        "permission_error",
        "timeout_error",
        "internal_error",
    ],
    error_code: str,
    component: Literal["cli", "sdk", "engine", "ml", "rules", "config", "telemetry", "wrapper"],
    *,
    error_message_hash: str | None = None,
    operation: str | None = None,
    is_recoverable: bool | None = None,
    stack_trace_hash: str | None = None,
    context: dict[str, str] | None = None,
    org_id: str | None = None,
    team_id: str | None = None,
) -> TelemetryEvent:
    """Create an error telemetry event.

    Fired when an error occurs (for debugging and quality improvement).

    Args:
        error_type: Category of error.
        error_code: Specific error code (e.g., RAXE_001).
        component: Component where error occurred.
        error_message_hash: SHA-256 hash of error message (for grouping without PII).
        operation: Operation being performed when error occurred.
        is_recoverable: Whether the error was recovered from.
        stack_trace_hash: SHA-256 hash of stack trace (for grouping).
        context: Non-sensitive error context (python_version, raxe_version, platform).
        org_id: Organization ID for multi-tenant tracking.
        team_id: Team ID for team-level analytics.

    Returns:
        TelemetryEvent with error payload.

    Example:
        >>> event = create_error_event(
        ...     error_type="validation_error",
        ...     error_code="RAXE_001",
        ...     component="engine",
        ...     error_message_hash=hash_text("Invalid prompt format"),
        ...     operation="scan",
        ...     is_recoverable=True,
        ...     org_id="org_123",
        ...     team_id="team_456",
        ... )
    """
    payload: dict[str, Any] = {
        "error_type": error_type,
        "error_code": error_code,
        "component": component,
    }

    if error_message_hash is not None:
        payload["error_message_hash"] = error_message_hash

    if operation is not None:
        payload["operation"] = operation

    if is_recoverable is not None:
        payload["is_recoverable"] = is_recoverable

    if stack_trace_hash is not None:
        payload["stack_trace_hash"] = stack_trace_hash

    if context is not None:
        payload["context"] = context

    return TelemetryEvent(
        event_id=generate_event_id(),
        event_type=EventType.ERROR.value,
        timestamp=_get_utc_timestamp(),
        priority="critical",
        payload=payload,
        org_id=org_id,
        team_id=team_id,
    )


# =============================================================================
# Performance Event
# =============================================================================


def create_performance_event(
    period_start: str,
    period_end: str,
    scan_count: int,
    *,
    latency_percentiles: dict[str, float] | None = None,
    l1_latency_percentiles: dict[str, float] | None = None,
    l2_latency_percentiles: dict[str, float] | None = None,
    memory_usage: dict[str, float] | None = None,
    threat_detection_rate: float | None = None,
    rules_loaded: int | None = None,
    l2_enabled: bool | None = None,
    org_id: str | None = None,
    team_id: str | None = None,
) -> TelemetryEvent:
    """Create a performance telemetry event.

    Aggregated performance metrics (sent periodically).

    Args:
        period_start: Start of measurement period (ISO 8601).
        period_end: End of measurement period (ISO 8601).
        scan_count: Number of scans in period.
        latency_percentiles: Scan latency distribution (p50_ms, p95_ms, p99_ms, max_ms).
        l1_latency_percentiles: L1 scan latency distribution.
        l2_latency_percentiles: L2 scan latency distribution.
        memory_usage: Memory usage statistics (current_mb, peak_mb).
        threat_detection_rate: Percentage of scans with threats detected (0.0-1.0).
        rules_loaded: Number of rules loaded.
        l2_enabled: Whether L2 ML detection is enabled.
        org_id: Organization ID for multi-tenant tracking.
        team_id: Team ID for team-level analytics.

    Returns:
        TelemetryEvent with performance payload.

    Example:
        >>> event = create_performance_event(
        ...     period_start="2025-01-22T10:00:00Z",
        ...     period_end="2025-01-22T11:00:00Z",
        ...     scan_count=1000,
        ...     latency_percentiles={"p50_ms": 2.5, "p95_ms": 8.0, "p99_ms": 12.0},
        ...     threat_detection_rate=0.05,
        ...     org_id="org_123",
        ...     team_id="team_456",
        ... )
    """
    payload: dict[str, Any] = {
        "period_start": period_start,
        "period_end": period_end,
        "scan_count": scan_count,
    }

    if latency_percentiles is not None:
        payload["latency_percentiles"] = latency_percentiles

    if l1_latency_percentiles is not None:
        payload["l1_latency_percentiles"] = l1_latency_percentiles

    if l2_latency_percentiles is not None:
        payload["l2_latency_percentiles"] = l2_latency_percentiles

    if memory_usage is not None:
        payload["memory_usage"] = memory_usage

    if threat_detection_rate is not None:
        payload["threat_detection_rate"] = threat_detection_rate

    if rules_loaded is not None:
        payload["rules_loaded"] = rules_loaded

    if l2_enabled is not None:
        payload["l2_enabled"] = l2_enabled

    return TelemetryEvent(
        event_id=generate_event_id(),
        event_type=EventType.PERFORMANCE.value,
        timestamp=_get_utc_timestamp(),
        priority="standard",
        payload=payload,
        org_id=org_id,
        team_id=team_id,
    )


# =============================================================================
# Feature Usage Event
# =============================================================================


def create_feature_usage_event(
    feature: Literal[
        "cli_scan",
        "cli_rules_list",
        "cli_rules_show",
        "cli_config",
        "cli_stats",
        "cli_repl",
        "cli_explain",
        "cli_validate_rule",
        "cli_doctor",
        "cli_telemetry_dlq",
        "sdk_scan",
        "sdk_batch_scan",
        "sdk_layer_control",
        "wrapper_openai",
        "wrapper_anthropic",
        "integration_langchain",
        "custom_rule_loaded",
        "policy_applied",
    ],
    action: Literal["invoked", "completed", "failed", "cancelled"],
    *,
    duration_ms: float | None = None,
    success: bool | None = None,
    metadata: dict[str, Any] | None = None,
    org_id: str | None = None,
    team_id: str | None = None,
) -> TelemetryEvent:
    """Create a feature usage telemetry event.

    Tracks usage of specific features for product analytics.

    Args:
        feature: Feature being used.
        action: Action taken with feature.
        duration_ms: Time spent using feature.
        success: Whether feature usage was successful.
        metadata: Feature-specific non-sensitive metadata.
        org_id: Organization ID for multi-tenant tracking.
        team_id: Team ID for team-level analytics.

    Returns:
        TelemetryEvent with feature_usage payload.

    Example:
        >>> event = create_feature_usage_event(
        ...     feature="cli_scan",
        ...     action="completed",
        ...     duration_ms=150.5,
        ...     success=True,
        ...     metadata={"output_format": "json"},
        ...     org_id="org_123",
        ...     team_id="team_456",
        ... )
    """
    payload: dict[str, Any] = {
        "feature": feature,
        "action": action,
    }

    if duration_ms is not None:
        payload["duration_ms"] = duration_ms

    if success is not None:
        payload["success"] = success

    if metadata is not None:
        payload["metadata"] = metadata

    return TelemetryEvent(
        event_id=generate_event_id(),
        event_type=EventType.FEATURE_USAGE.value,
        timestamp=_get_utc_timestamp(),
        priority="standard",
        payload=payload,
        org_id=org_id,
        team_id=team_id,
    )


# =============================================================================
# Heartbeat Event
# =============================================================================


def create_heartbeat_event(
    uptime_seconds: float,
    scans_since_last_heartbeat: int,
    *,
    threats_since_last_heartbeat: int | None = None,
    memory_mb: float | None = None,
    queue_depths: dict[str, int] | None = None,
    circuit_breaker_state: Literal["closed", "open", "half_open"] | None = None,
    last_successful_ship: str | None = None,
    org_id: str | None = None,
    team_id: str | None = None,
) -> TelemetryEvent:
    """Create a heartbeat telemetry event.

    Periodic health signal for long-running processes.

    Args:
        uptime_seconds: Time since process started.
        scans_since_last_heartbeat: Scans performed since last heartbeat.
        threats_since_last_heartbeat: Threats detected since last heartbeat.
        memory_mb: Current memory usage.
        queue_depths: Current telemetry queue sizes (critical, standard, dlq).
        circuit_breaker_state: Current circuit breaker state.
        last_successful_ship: Timestamp of last successful telemetry ship.
        org_id: Organization ID for multi-tenant tracking.
        team_id: Team ID for team-level analytics.

    Returns:
        TelemetryEvent with heartbeat payload.

    Example:
        >>> event = create_heartbeat_event(
        ...     uptime_seconds=3600.0,
        ...     scans_since_last_heartbeat=100,
        ...     threats_since_last_heartbeat=5,
        ...     memory_mb=120.5,
        ...     queue_depths={"critical": 0, "standard": 10, "dlq": 2},
        ...     circuit_breaker_state="closed",
        ...     org_id="org_123",
        ...     team_id="team_456",
        ... )
    """
    payload: dict[str, Any] = {
        "uptime_seconds": uptime_seconds,
        "scans_since_last_heartbeat": scans_since_last_heartbeat,
    }

    if threats_since_last_heartbeat is not None:
        payload["threats_since_last_heartbeat"] = threats_since_last_heartbeat

    if memory_mb is not None:
        payload["memory_mb"] = memory_mb

    if queue_depths is not None:
        payload["queue_depths"] = queue_depths

    if circuit_breaker_state is not None:
        payload["circuit_breaker_state"] = circuit_breaker_state

    if last_successful_ship is not None:
        payload["last_successful_ship"] = last_successful_ship

    return TelemetryEvent(
        event_id=generate_event_id(),
        event_type=EventType.HEARTBEAT.value,
        timestamp=_get_utc_timestamp(),
        priority="standard",
        payload=payload,
        org_id=org_id,
        team_id=team_id,
    )


# =============================================================================
# Key Upgrade Event
# =============================================================================


def create_key_upgrade_event(
    previous_key_type: Literal["temp", "community", "pro", "enterprise"],
    new_key_type: Literal["community", "pro", "enterprise"],
    *,
    previous_key_id: str | None = None,
    new_key_id: str | None = None,
    days_on_previous: int | None = None,
    scans_on_previous: int | None = None,
    threats_on_previous: int | None = None,
    conversion_trigger: Literal[
        "trial_expiry",
        "rate_limit_hit",
        "feature_needed",
        "manual_upgrade",
        "promo_code",
        "cli_connect",
    ]
    | None = None,
    org_id: str | None = None,
    team_id: str | None = None,
) -> TelemetryEvent:
    """Create a key upgrade telemetry event.

    Fired when API key is upgraded (conversion tracking). Includes key IDs
    to enable server-side linking of historical events from the old key
    to the new key.

    Args:
        previous_key_type: Previous key tier.
        new_key_type: New key tier.
        previous_key_id: BigQuery-compatible ID for previous key (e.g., "key_23cc2f9f21f9").
            Computed as "key_" + SHA256(api_key)[:12].
        new_key_id: BigQuery-compatible ID for new key (e.g., "key_7ce219b525f1").
            Computed as "key_" + SHA256(api_key)[:12].
        days_on_previous: Days spent on previous tier.
        scans_on_previous: Total scans on previous tier.
        threats_on_previous: Total threats detected on previous tier.
        conversion_trigger: What triggered the upgrade.
        org_id: Organization ID for multi-tenant tracking.
        team_id: Team ID for team-level analytics.

    Returns:
        TelemetryEvent with key_upgrade payload.

    Example:
        >>> event = create_key_upgrade_event(
        ...     previous_key_type="temp",
        ...     new_key_type="community",
        ...     previous_key_id="key_23cc2f9f21f9",
        ...     new_key_id="key_7ce219b525f1",
        ...     days_on_previous=7,
        ...     scans_on_previous=500,
        ...     threats_on_previous=25,
        ...     conversion_trigger="trial_expiry",
        ...     org_id="org_123",
        ...     team_id="team_456",
        ... )
    """
    payload: dict[str, Any] = {
        "previous_key_type": previous_key_type,
        "new_key_type": new_key_type,
    }

    # Add key IDs for server-side event linking
    if previous_key_id is not None:
        payload["previous_key_id"] = previous_key_id

    if new_key_id is not None:
        payload["new_key_id"] = new_key_id

    if days_on_previous is not None:
        payload["days_on_previous"] = days_on_previous

    if scans_on_previous is not None:
        payload["scans_on_previous"] = scans_on_previous

    if threats_on_previous is not None:
        payload["threats_on_previous"] = threats_on_previous

    if conversion_trigger is not None:
        payload["conversion_trigger"] = conversion_trigger

    return TelemetryEvent(
        event_id=generate_event_id(),
        event_type=EventType.KEY_UPGRADE.value,
        timestamp=_get_utc_timestamp(),
        priority="critical",
        payload=payload,
        org_id=org_id,
        team_id=team_id,
    )


# =============================================================================
# Config Changed Event
# =============================================================================


def create_config_changed_event(
    changed_via: Literal["cli", "sdk", "config_file", "env_var"],
    changes: list[dict[str, Any]],
    *,
    is_final_event: bool = False,
    org_id: str | None = None,
    team_id: str | None = None,
) -> TelemetryEvent:
    """Create a config changed telemetry event.

    Fired when configuration is changed (tracks opt-outs and preferences).

    Args:
        changed_via: How configuration was changed.
        changes: List of configuration changes. Each change should have:
            - key: Configuration key that changed (e.g., "telemetry.enabled")
            - new_value: New value
            - old_value: Previous value (optional)
        is_final_event: True if this is the last event before telemetry disable.
        org_id: Organization ID for multi-tenant tracking.
        team_id: Team ID for team-level analytics.

    Returns:
        TelemetryEvent with config_changed payload. Priority is critical
        if telemetry is being disabled (is_final_event=True), otherwise standard.

    Example:
        >>> event = create_config_changed_event(
        ...     changed_via="cli",
        ...     changes=[
        ...         {"key": "telemetry.enabled", "old_value": True, "new_value": False}
        ...     ],
        ...     is_final_event=True,
        ...     org_id="org_123",
        ...     team_id="team_456",
        ... )
    """
    payload: dict[str, Any] = {
        "changed_via": changed_via,
        "changes": changes,
    }

    if is_final_event:
        payload["is_final_event"] = is_final_event

    # Priority is critical if disabling telemetry (is_final_event=True)
    priority: Literal["critical", "standard"] = "critical" if is_final_event else "standard"

    return TelemetryEvent(
        event_id=generate_event_id(),
        event_type=EventType.CONFIG_CHANGED.value,
        timestamp=_get_utc_timestamp(),
        priority=priority,
        payload=payload,
        org_id=org_id,
        team_id=team_id,
    )


# =============================================================================
# Team Invite Event
# =============================================================================


def create_team_invite_event(
    inviter_installation_id: str,
    invitee_email_hash: str,
    org_id: str,
    team_id: str,
    role: Literal["admin", "member", "viewer"],
    *,
    invite_method: Literal["email", "link", "api"] = "email",
) -> TelemetryEvent:
    """Create a team invite telemetry event.

    Tracks team invitations for viral growth metrics.

    Args:
        inviter_installation_id: Installation ID of the user sending the invite.
        invitee_email_hash: SHA-256 hash of invitee's email (privacy-preserving).
        org_id: Organization identifier.
        team_id: Team identifier within the organization.
        role: Role being assigned to the invitee.
        invite_method: How the invitation was sent.

    Returns:
        TelemetryEvent with team_invite payload (critical priority).

    Example:
        >>> event = create_team_invite_event(
        ...     inviter_installation_id="inst_abc123def456789",
        ...     invitee_email_hash="a" * 64,
        ...     org_id="org_123",
        ...     team_id="team_456",
        ...     role="member",
        ...     invite_method="email",
        ... )
    """
    payload: dict[str, Any] = {
        "inviter_installation_id": inviter_installation_id,
        "invitee_email_hash": invitee_email_hash,
        "org_id": org_id,
        "team_id": team_id,
        "role": role,
        "invite_method": invite_method,
    }

    return TelemetryEvent(
        event_id=generate_event_id(),
        event_type=EventType.TEAM_INVITE.value,
        timestamp=_get_utc_timestamp(),
        priority="critical",
        payload=payload,
        org_id=org_id,
        team_id=team_id,
    )


# =============================================================================
# Utility Functions
# =============================================================================


def create_prompt_hash(prompt: str) -> str:
    """Create a SHA-256 hash of a prompt for telemetry.

    This is a convenience wrapper around hash_text for scan events.

    Args:
        prompt: The prompt text to hash.

    Returns:
        64-character hexadecimal SHA-256 hash string.

    Example:
        >>> create_prompt_hash("Hello, world!")
        '315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3'
    """
    return hash_text(prompt, algorithm="sha256")


def event_to_dict(event: TelemetryEvent) -> dict[str, Any]:
    """Convert a TelemetryEvent to a dictionary for serialization.

    Args:
        event: The telemetry event to convert.

    Returns:
        Dictionary representation of the event including org_id and team_id if present.

    Example:
        >>> event = create_heartbeat_event(uptime_seconds=100.0, scans_since_last_heartbeat=5)
        >>> d = event_to_dict(event)
        >>> d["event_type"]
        'heartbeat'
    """
    result: dict[str, Any] = {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp,
        "priority": event.priority,
        "payload": event.payload,
    }

    if event.org_id is not None:
        result["org_id"] = event.org_id

    if event.team_id is not None:
        result["team_id"] = event.team_id

    return result
