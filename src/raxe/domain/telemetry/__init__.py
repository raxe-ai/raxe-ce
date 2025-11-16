"""
Domain layer telemetry - pure functions for event creation.

This module provides pure functions for creating privacy-preserving
telemetry events. No I/O operations are performed here.
"""

from .event_creator import (
    calculate_event_priority,
    create_scan_event,
    hash_text,
    validate_event_privacy,
)

__all__ = ["calculate_event_priority", "create_scan_event", "hash_text", "validate_event_privacy"]