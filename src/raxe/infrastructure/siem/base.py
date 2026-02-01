"""Base SIEM adapter interface.

All SIEM adapters must implement this interface to ensure
consistent behavior across different SIEM platforms.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from raxe.domain.siem.config import SIEMConfig


@dataclass(frozen=True)
class SIEMDeliveryResult:
    """Result of SIEM event delivery.

    Attributes:
        success: Whether delivery succeeded
        status_code: HTTP status code (if applicable)
        error_message: Error description (if failed)
        event_id: SIEM-assigned event ID (if available)
        retry_after: Seconds to wait before retry (rate limiting)
        events_accepted: Number of events accepted (for batch)
        events_rejected: Number of events rejected (for batch)
    """

    success: bool
    status_code: int | None = None
    error_message: str | None = None
    event_id: str | None = None
    retry_after: int | None = None
    events_accepted: int = 0
    events_rejected: int = 0


class SIEMAdapter(ABC):
    """Abstract base class for SIEM integrations.

    All SIEM adapters must implement this interface to ensure
    consistent behavior across different SIEM platforms.

    The adapter lifecycle:
    1. Create with SIEMConfig
    2. Transform events to SIEM-specific format
    3. Send events (single or batch)
    4. Close to release resources

    Example implementation:
        >>> class MySIEMAdapter(SIEMAdapter):
        ...     def __init__(self, config: SIEMConfig):
        ...         super().__init__(config)
        ...         self._config = config
        ...
        ...     @property
        ...     def name(self) -> str:
        ...         return "mysiem"
        ...
        ...     # ... implement other methods
    """

    def __init__(self, config: SIEMConfig) -> None:
        """Initialize SIEM adapter with configuration.

        Args:
            config: SIEM configuration
        """
        # Base class just accepts config for type checking
        # Subclasses should store and use it
        del config  # Suppress unused parameter warning

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this SIEM adapter.

        Used for logging, configuration lookup, and statistics.
        Should be lowercase alphanumeric (e.g., 'splunk', 'sentinel').
        """
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for display.

        Used in UI, logs, and documentation.
        (e.g., 'Splunk HEC', 'Microsoft Sentinel')
        """
        ...

    @abstractmethod
    def transform_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Transform RAXE event to SIEM-specific format.

        Each SIEM has its own event schema requirements. This method
        converts the standard RAXE telemetry event format to the
        format expected by the SIEM's ingestion API.

        Args:
            event: RAXE telemetry event payload (from TelemetryEvent.to_dict())

        Returns:
            SIEM-specific event format ready for sending

        Note:
            Implementations should extract relevant fields and map them
            to SIEM-specific field names. Consider:
            - Timestamp format requirements
            - Field naming conventions (camelCase, snake_case, etc.)
            - Required vs optional fields
            - Nested vs flat structure
        """
        ...

    @abstractmethod
    def send_event(self, event: dict[str, Any]) -> SIEMDeliveryResult:
        """Send a single event to the SIEM.

        Args:
            event: Already-transformed SIEM event (from transform_event)

        Returns:
            Delivery result with status and details

        Note:
            For efficiency, prefer send_batch() when sending multiple events.
            This method may be implemented as send_batch([event]).
        """
        ...

    @abstractmethod
    def send_batch(self, events: list[dict[str, Any]]) -> SIEMDeliveryResult:
        """Send multiple events in a single request.

        Most SIEMs support batch ingestion for efficiency. This method
        should send all events in a single HTTP request when possible.

        Args:
            events: List of already-transformed SIEM events

        Returns:
            Aggregate delivery result with counts

        Note:
            If partial success is possible (some events accepted, others
            rejected), set events_accepted/events_rejected accordingly.
        """
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the SIEM endpoint is reachable and healthy.

        Used for:
        - Pre-flight checks before sending events
        - Monitoring dashboard status
        - Circuit breaker recovery testing

        Returns:
            True if healthy and accepting events, False otherwise

        Note:
            Should be a lightweight check (HEAD request, status endpoint)
            not a full event submission.
        """
        ...

    def close(self) -> None:
        """Clean up any resources (sessions, connections).

        Called when the adapter is no longer needed.
        Default implementation does nothing.

        Subclasses should override to close HTTP sessions,
        connection pools, or other resources.
        """
        return  # Default implementation - no resources to clean up

    def __enter__(self) -> SIEMAdapter:
        """Support context manager protocol."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Close resources on context exit."""
        self.close()


class BaseSIEMAdapter(SIEMAdapter):
    """Base implementation with common functionality.

    Provides:
    - HTTP session management
    - Common event field extraction helpers
    - Retry logic helpers
    - Statistics tracking

    Subclasses should:
    1. Call super().__init__(config) in their __init__
    2. Implement transform_event for their format
    3. Implement send_event and send_batch for their API
    4. Override health_check with their endpoint
    """

    def __init__(self, config: SIEMConfig) -> None:
        """Initialize base adapter.

        Args:
            config: SIEM configuration
        """
        self._config = config
        self._session: Any = None  # Lazy-initialized requests.Session
        self._stats: dict[str, Any] = {
            "events_sent": 0,
            "events_failed": 0,
            "batches_sent": 0,
            "last_error": None,
        }

    @property
    def config(self) -> SIEMConfig:
        """Get adapter configuration."""
        return self._config

    @property
    def stats(self) -> dict[str, Any]:
        """Get adapter statistics."""
        return self._stats.copy()

    def _get_session(self) -> Any:
        """Get or create HTTP session (lazy initialization)."""
        if self._session is None:
            import requests

            self._session = requests.Session()
            self._configure_session(self._session)
        return self._session

    def _configure_session(self, session: Any) -> None:
        """Configure HTTP session with adapter-specific settings.

        Override in subclasses to set headers, auth, etc.

        Args:
            session: requests.Session to configure
        """
        pass

    def close(self) -> None:
        """Close HTTP session."""
        if self._session is not None:
            self._session.close()
            self._session = None

    # Common field extraction helpers

    def _extract_timestamp_epoch(self, event: dict[str, Any]) -> float:
        """Extract timestamp as Unix epoch seconds.

        Args:
            event: RAXE event

        Returns:
            Unix timestamp in seconds (with millisecond precision)
        """
        import time
        from datetime import datetime

        timestamp = event.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return dt.timestamp()
        except (ValueError, AttributeError):
            return time.time()

    def _extract_severity(self, event: dict[str, Any]) -> str:
        """Extract highest severity from event.

        Args:
            event: RAXE event

        Returns:
            Severity string (none, LOW, MEDIUM, HIGH, CRITICAL)
        """
        payload = event.get("payload", {})
        l1 = payload.get("l1", {})
        l2 = payload.get("l2", {})

        l1_severity = l1.get("highest_severity", "none")
        l2_severity = l2.get("severity", "none")

        severity_order = ["none", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
        l1_idx = severity_order.index(l1_severity) if l1_severity in severity_order else 0
        l2_idx = severity_order.index(l2_severity) if l2_severity in severity_order else 0

        return severity_order[max(l1_idx, l2_idx)]

    def _extract_rule_ids(self, event: dict[str, Any]) -> list[str]:
        """Extract all triggered rule IDs.

        Args:
            event: RAXE event

        Returns:
            List of rule IDs that triggered
        """
        detections = event.get("payload", {}).get("l1", {}).get("detections", [])
        return [d.get("rule_id") for d in detections if d.get("rule_id")]

    def _extract_families(self, event: dict[str, Any]) -> list[str]:
        """Extract all triggered rule families.

        Args:
            event: RAXE event

        Returns:
            List of rule families (PI, JB, MH, etc.)
        """
        families = event.get("payload", {}).get("l1", {}).get("families", [])
        return list(families) if families else []

    def _extract_mssp_context(self, event: dict[str, Any]) -> dict[str, Any]:
        """Extract MSSP context from event.

        Args:
            event: RAXE event

        Returns:
            MSSP context dict with mssp_id, customer_id, agent_id
        """
        payload = event.get("payload", {})
        return {
            "mssp_id": payload.get("mssp_id"),
            "customer_id": payload.get("customer_id"),
            "agent_id": payload.get("agent_id"),
        }

    def _update_stats(self, result: SIEMDeliveryResult, batch_size: int = 1) -> None:
        """Update internal statistics after delivery attempt.

        Args:
            result: Delivery result
            batch_size: Number of events in batch
        """
        events_sent = int(self._stats.get("events_sent", 0) or 0)
        events_failed = int(self._stats.get("events_failed", 0) or 0)
        batches_sent = int(self._stats.get("batches_sent", 0) or 0)

        if result.success:
            self._stats["events_sent"] = events_sent + (result.events_accepted or batch_size)
            self._stats["events_failed"] = events_failed + result.events_rejected
        else:
            self._stats["events_failed"] = events_failed + batch_size
            self._stats["last_error"] = result.error_message

        if batch_size > 1:
            self._stats["batches_sent"] = batches_sent + 1
