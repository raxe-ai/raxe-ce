"""
Domain layer telemetry - pure functions for event creation and management.

This module provides pure functions for:
- Creating privacy-preserving telemetry events (12 event types)
- Classifying event priority (critical vs standard queue)
- Calculating backpressure for queue management

No I/O operations are performed here - all functions are pure.
"""

from .backpressure import (
    BackpressureDecision,
    BackpressureThresholds,
    QueueMetrics,
    calculate_backpressure,
    calculate_effective_sample_rate,
    should_sample_event,
)
from .event_creator import (
    calculate_event_priority,
    hash_text,
    validate_event_privacy,
)
from .event_creator import (
    create_scan_event as create_scan_event_legacy,
)
from .events import (
    SCAN_SCHEMA_VERSION,
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
    create_scan_event_v2,
    create_session_end_event,
    create_session_start_event,
    create_team_invite_event,
    event_to_dict,
    generate_batch_id,
    generate_event_id,
    generate_installation_id,
    generate_session_id,
)
from .scan_telemetry_builder import (
    SCHEMA_VERSION,
    ScanTelemetryBuilder,
    build_scan_telemetry,
    get_scan_telemetry_builder,
)
from .priority import (
    DEFAULT_PRIORITY_CONFIG,
    PriorityConfig,
    classify_priority,
    is_critical_event_type,
    is_standard_event_type,
)

__all__ = [
    # Event models
    "TelemetryEvent",
    "EventType",
    # ID generators
    "generate_event_id",
    "generate_installation_id",
    "generate_session_id",
    "generate_batch_id",
    # Event factory functions
    "create_installation_event",
    "create_activation_event",
    "create_session_start_event",
    "create_session_end_event",
    "create_scan_event",
    "create_scan_event_v2",
    "create_error_event",
    "create_performance_event",
    "create_feature_usage_event",
    "create_heartbeat_event",
    "create_key_upgrade_event",
    "create_config_changed_event",
    "create_team_invite_event",
    # Scan telemetry builder (v2 schema)
    "SCAN_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "ScanTelemetryBuilder",
    "build_scan_telemetry",
    "get_scan_telemetry_builder",
    # Utilities
    "create_prompt_hash",
    "event_to_dict",
    # Priority classification
    "PriorityConfig",
    "DEFAULT_PRIORITY_CONFIG",
    "classify_priority",
    "is_critical_event_type",
    "is_standard_event_type",
    # Backpressure
    "QueueMetrics",
    "BackpressureDecision",
    "BackpressureThresholds",
    "calculate_backpressure",
    "calculate_effective_sample_rate",
    "should_sample_event",
    # Legacy (from event_creator.py) - keep for backwards compatibility
    "hash_text",
    "create_scan_event_legacy",
    "validate_event_privacy",
    "calculate_event_priority",
]