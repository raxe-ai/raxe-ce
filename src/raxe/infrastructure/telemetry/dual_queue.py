"""
SQLite-based dual-priority queue for telemetry events.

This module implements a persistent, dual-priority event queue using SQLite.
Events are routed to critical or standard priority queues based on their type.
The queue provides state persistence, dead letter queue support, and graceful
degradation when the database is unavailable.

Key Features:
- Dual priority queues (critical, standard)
- SQLite with WAL mode for concurrency
- State persistence across restarts
- Dead letter queue for failed events
- Thread-safe operations
- Graceful degradation on database errors
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

from raxe.domain.telemetry.events import TelemetryEvent, event_to_dict

logger = logging.getLogger(__name__)


class StateKey(str, Enum):
    """Enumeration of state keys for persistent telemetry state tracking.

    These keys are used to track installation state, activation milestones,
    and session information across restarts.

    Activation keys are aligned with backend canonical values.
    """

    INSTALLATION_FIRED = "installation_fired"
    INSTALLATION_ID = "installation_id"
    INSTALL_TIMESTAMP = "install_timestamp"
    SESSION_COUNT = "session_count"
    # Activation milestones (aligned with backend canonical values)
    ACTIVATED_FIRST_SCAN = "activated_first_scan"
    ACTIVATED_FIRST_THREAT = "activated_first_threat"
    ACTIVATED_FIRST_BLOCK = "activated_first_block"
    ACTIVATED_FIRST_CLI = "activated_first_cli"
    ACTIVATED_FIRST_SDK = "activated_first_sdk"
    ACTIVATED_FIRST_DECORATOR = "activated_first_decorator"
    ACTIVATED_FIRST_WRAPPER = "activated_first_wrapper"
    ACTIVATED_FIRST_LANGCHAIN = "activated_first_langchain"
    ACTIVATED_FIRST_L2_DETECTION = "activated_first_l2_detection"
    ACTIVATED_FIRST_CUSTOM_RULE = "activated_first_custom_rule"
    # API key ID tracking for consistency across auth and telemetry flows
    CURRENT_API_KEY_ID = "current_api_key_id"


class DualQueue:
    """
    SQLite-based dual-priority queue for telemetry events.

    Provides separate queues for critical and standard priority events with
    persistent state storage, dead letter queue support, and graceful error handling.

    Features:
    - Dual priority queues (critical sent first, standard batched)
    - WAL mode for concurrent access
    - State persistence across restarts
    - Dead letter queue for failed events after max retries
    - Thread-safe operations with connection pooling
    - Graceful degradation on database errors

    Example:
        >>> queue = DualQueue()
        >>> event = create_scan_event(...)
        >>> event_id = queue.enqueue(event)
        >>> batch = queue.dequeue_critical(batch_size=50)
        >>> queue.mark_batch_sent([e["event_id"] for e in batch])
    """

    # Schema version for migrations
    _SCHEMA_VERSION = 1

    def __init__(
        self,
        db_path: Path | None = None,
        critical_max_size: int = 10_000,
        standard_max_size: int = 50_000,
        *,
        max_retry_count: int = 3,
        enable_wal: bool = True,
    ) -> None:
        """
        Initialize the dual-priority queue.

        Args:
            db_path: Path to SQLite database (default: ~/.raxe/telemetry.db).
            critical_max_size: Maximum events in critical queue before overflow.
            standard_max_size: Maximum events in standard queue before overflow.
            max_retry_count: Maximum retries before moving to dead letter queue.
            enable_wal: Enable Write-Ahead Logging for better concurrency.
        """
        self.db_path = db_path or Path.home() / ".raxe" / "telemetry.db"
        self.critical_max_size = critical_max_size
        self.standard_max_size = standard_max_size
        self.max_retry_count = max_retry_count
        self._enable_wal = enable_wal
        self._lock = threading.Lock()
        self._closed = False

        # Ensure directory exists
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create telemetry directory: {e}")
            # Continue - we'll handle database errors gracefully

        # Initialize database
        self._init_database()

        logger.debug(f"DualQueue initialized at {self.db_path}")

    def _init_database(self) -> None:
        """Initialize database schema with all required tables and indexes."""
        try:
            with self._get_connection() as conn:
                # Enable WAL mode for better concurrency
                if self._enable_wal:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA synchronous=NORMAL")

                # Set busy timeout for concurrent access
                conn.execute("PRAGMA busy_timeout=5000")

                # Create events table with priority routing
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS telemetry_events (
                        event_id TEXT PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        priority TEXT NOT NULL CHECK (priority IN ('critical', 'standard')),
                        payload TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        retry_count INTEGER DEFAULT 0,
                        retry_after TEXT,
                        batch_id TEXT
                    )
                """)

                # Create state flags table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS telemetry_state (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)

                # Create dead letter queue
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS telemetry_dlq (
                        event_id TEXT PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        priority TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        failed_at TEXT NOT NULL,
                        failure_reason TEXT,
                        retry_count INTEGER,
                        server_error_code TEXT,
                        server_error_message TEXT
                    )
                """)

                # Create stats table for tracking sent events
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS telemetry_stats (
                        stat_key TEXT PRIMARY KEY,
                        stat_value INTEGER DEFAULT 0,
                        updated_at TEXT NOT NULL
                    )
                """)

                # Initialize stats if not present
                now = datetime.now(timezone.utc).isoformat()
                conn.execute("""
                    INSERT OR IGNORE INTO telemetry_stats (stat_key, stat_value, updated_at)
                    VALUES ('events_sent_total', 0, ?), ('batches_sent_total', 0, ?), ('scans_sent_total', 0, ?)
                """, (now, now, now))

                # Create indexes for efficient queries
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_events_priority
                    ON telemetry_events(priority, created_at)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_events_retry
                    ON telemetry_events(retry_after)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_dlq_failed
                    ON telemetry_dlq(failed_at)
                """)

                conn.commit()

        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            # Continue - graceful degradation

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection context manager.

        Returns:
            SQLite connection with proper cleanup.

        Raises:
            sqlite3.Error: If connection cannot be established.
        """
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        try:
            yield conn
        finally:
            conn.close()

    def enqueue(self, event: TelemetryEvent) -> str:
        """
        Add an event to the appropriate priority queue.

        Events are routed to critical or standard queue based on their priority
        attribute. Queue overflow is handled by dropping oldest events from the
        same priority.

        Args:
            event: TelemetryEvent to enqueue.

        Returns:
            Event ID of the enqueued event.

        Example:
            >>> event = create_scan_event(...)
            >>> event_id = queue.enqueue(event)
        """
        if self._closed:
            logger.warning("Attempted to enqueue to closed queue")
            return event.event_id

        event_dict = event_to_dict(event)
        priority = event.priority

        try:
            with self._lock:
                with self._get_connection() as conn:
                    # Check queue size for this priority
                    count = conn.execute(
                        "SELECT COUNT(*) FROM telemetry_events WHERE priority = ?",
                        (priority,),
                    ).fetchone()[0]

                    max_size = (
                        self.critical_max_size if priority == "critical" else self.standard_max_size
                    )

                    if count >= max_size:
                        # Handle overflow - drop oldest event from same priority
                        self._handle_overflow(conn, priority)

                    # Insert new event
                    conn.execute(
                        """
                        INSERT INTO telemetry_events (
                            event_id, event_type, priority, payload, created_at
                        ) VALUES (?, ?, ?, ?, ?)
                    """,
                        (
                            event.event_id,
                            event.event_type,
                            priority,
                            json.dumps(event_dict["payload"]),
                            event.timestamp,
                        ),
                    )

                    conn.commit()

                    logger.debug(f"Enqueued {priority} event {event.event_id} ({event.event_type})")

        except sqlite3.Error as e:
            logger.error(f"Failed to enqueue event: {e}")
            # Graceful degradation - event is lost but application continues

        return event.event_id

    def _handle_overflow(self, conn: sqlite3.Connection, priority: str) -> None:
        """Handle queue overflow by dropping oldest event from same priority.

        Args:
            conn: Active database connection.
            priority: Priority queue experiencing overflow.
        """
        result = conn.execute(
            """
            SELECT event_id FROM telemetry_events
            WHERE priority = ?
            ORDER BY created_at ASC
            LIMIT 1
        """,
            (priority,),
        ).fetchone()

        if result:
            event_id = result[0]
            conn.execute("DELETE FROM telemetry_events WHERE event_id = ?", (event_id,))
            logger.warning(f"Dropped oldest {priority} event {event_id} due to queue overflow")

    def dequeue_critical(self, batch_size: int = 100) -> list[dict[str, Any]]:
        """
        Dequeue a batch of critical priority events.

        Events are returned in FIFO order, skipping events with retry_after
        in the future.

        Args:
            batch_size: Maximum number of events to dequeue.

        Returns:
            List of event dictionaries ready for sending.

        Example:
            >>> events = queue.dequeue_critical(batch_size=50)
            >>> for event in events:
            ...     print(event["event_id"])
        """
        return self._dequeue_by_priority("critical", batch_size)

    def dequeue_standard(self, batch_size: int = 100) -> list[dict[str, Any]]:
        """
        Dequeue a batch of standard priority events.

        Events are returned in FIFO order, skipping events with retry_after
        in the future.

        Args:
            batch_size: Maximum number of events to dequeue.

        Returns:
            List of event dictionaries ready for sending.

        Example:
            >>> events = queue.dequeue_standard(batch_size=100)
        """
        return self._dequeue_by_priority("standard", batch_size)

    def _dequeue_by_priority(self, priority: str, batch_size: int) -> list[dict[str, Any]]:
        """Dequeue events of a specific priority.

        Args:
            priority: Priority level to dequeue ("critical" or "standard").
            batch_size: Maximum number of events to return.

        Returns:
            List of event dictionaries.
        """
        if self._closed:
            logger.warning("Attempted to dequeue from closed queue")
            return []

        events: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()

        try:
            with self._lock:
                with self._get_connection() as conn:
                    # Select events ready for processing (not in retry backoff)
                    cursor = conn.execute(
                        """
                        SELECT event_id, event_type, priority, payload, created_at,
                               retry_count, retry_after, batch_id
                        FROM telemetry_events
                        WHERE priority = ?
                          AND batch_id IS NULL
                          AND (retry_after IS NULL OR retry_after <= ?)
                        ORDER BY created_at ASC
                        LIMIT ?
                    """,
                        (priority, now, batch_size),
                    )

                    for row in cursor:
                        event_dict = {
                            "event_id": row[0],
                            "event_type": row[1],
                            "priority": row[2],
                            "payload": json.loads(row[3]),
                            "timestamp": row[4],
                            "retry_count": row[5],
                        }
                        events.append(event_dict)

                    logger.debug(f"Dequeued {len(events)} {priority} events")

        except sqlite3.Error as e:
            logger.error(f"Failed to dequeue events: {e}")

        return events

    def mark_batch_sent(self, event_ids: list[str]) -> None:
        """
        Mark events as successfully sent and remove from queue.

        Also updates lifetime stats (events_sent_total, batches_sent_total).

        Args:
            event_ids: List of event IDs to mark as sent.

        Example:
            >>> queue.mark_batch_sent(["evt_abc123", "evt_def456"])
        """
        if not event_ids:
            return

        if self._closed:
            logger.warning("Attempted to mark batch on closed queue")
            return

        try:
            with self._lock:
                with self._get_connection() as conn:
                    # Security: Safe - placeholders constructed from fixed '?' list
                    placeholders = ",".join(["?"] * len(event_ids))

                    # Count scan events BEFORE deleting (for scans_sent_total stat)
                    count_sql = f"SELECT COUNT(*) FROM telemetry_events WHERE event_id IN ({placeholders}) AND event_type = 'scan'"  # noqa: S608
                    scan_count = conn.execute(count_sql, event_ids).fetchone()[0]

                    # Delete events
                    sql = f"DELETE FROM telemetry_events WHERE event_id IN ({placeholders})"  # noqa: S608
                    conn.execute(sql, event_ids)

                    # Update lifetime stats
                    now = datetime.now(timezone.utc).isoformat()
                    conn.execute("""
                        UPDATE telemetry_stats
                        SET stat_value = stat_value + ?, updated_at = ?
                        WHERE stat_key = 'events_sent_total'
                    """, (len(event_ids), now))
                    conn.execute("""
                        UPDATE telemetry_stats
                        SET stat_value = stat_value + ?, updated_at = ?
                        WHERE stat_key = 'scans_sent_total'
                    """, (scan_count, now))
                    conn.execute("""
                        UPDATE telemetry_stats
                        SET stat_value = stat_value + 1, updated_at = ?
                        WHERE stat_key = 'batches_sent_total'
                    """, (now,))

                    conn.commit()

                    logger.debug(f"Marked {len(event_ids)} events ({scan_count} scans) as sent")

        except sqlite3.Error as e:
            logger.error(f"Failed to mark batch sent: {e}")

    def mark_batch_failed(self, event_ids: list[str], error: str, retry_delay_seconds: int) -> None:
        """
        Mark events as failed and schedule for retry.

        Events exceeding max_retry_count are moved to dead letter queue.

        Args:
            event_ids: List of event IDs that failed.
            error: Error message describing failure.
            retry_delay_seconds: Seconds to wait before retry.

        Example:
            >>> queue.mark_batch_failed(
            ...     ["evt_abc123"],
            ...     "Connection timeout",
            ...     retry_delay_seconds=60,
            ... )
        """
        if not event_ids:
            return

        if self._closed:
            logger.warning("Attempted to mark batch failed on closed queue")
            return

        try:
            with self._lock:
                with self._get_connection() as conn:
                    retry_after = datetime.now(timezone.utc) + timedelta(
                        seconds=retry_delay_seconds
                    )
                    retry_after_str = retry_after.isoformat()
                    now_str = datetime.now(timezone.utc).isoformat()

                    # Get current retry counts for all events
                    # Security: Safe - placeholders constructed from fixed '?' list
                    placeholders = ",".join(["?"] * len(event_ids))
                    sql = f"""
                        SELECT event_id, event_type, priority, payload, created_at, retry_count
                        FROM telemetry_events
                        WHERE event_id IN ({placeholders})
                    """  # noqa: S608
                    cursor = conn.execute(sql, event_ids)

                    dlq_events = []
                    retry_events = []

                    for row in cursor:
                        event_id = row[0]
                        retry_count = row[5]

                        if retry_count >= self.max_retry_count:
                            dlq_events.append(
                                {
                                    "event_id": event_id,
                                    "event_type": row[1],
                                    "priority": row[2],
                                    "payload": row[3],
                                    "created_at": row[4],
                                    "retry_count": retry_count,
                                }
                            )
                        else:
                            retry_events.append(event_id)

                    # Move max-retry events to dead letter queue
                    for dlq_event in dlq_events:
                        conn.execute(
                            """
                            INSERT INTO telemetry_dlq (
                                event_id, event_type, priority, payload, created_at,
                                failed_at, failure_reason, retry_count
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                dlq_event["event_id"],
                                dlq_event["event_type"],
                                dlq_event["priority"],
                                dlq_event["payload"],
                                dlq_event["created_at"],
                                now_str,
                                error,
                                dlq_event["retry_count"],
                            ),
                        )

                    if dlq_events:
                        dlq_ids = [e["event_id"] for e in dlq_events]
                        placeholders = ",".join(["?"] * len(dlq_ids))
                        sql = f"DELETE FROM telemetry_events WHERE event_id IN ({placeholders})"  # noqa: S608
                        conn.execute(sql, dlq_ids)
                        logger.warning(f"Moved {len(dlq_events)} events to dead letter queue")

                    # Update retry events
                    if retry_events:
                        placeholders = ",".join(["?"] * len(retry_events))
                        sql = f"""
                            UPDATE telemetry_events
                            SET batch_id = NULL,
                                retry_count = retry_count + 1,
                                retry_after = ?
                            WHERE event_id IN ({placeholders})
                        """  # noqa: S608
                        conn.execute(sql, [retry_after_str, *retry_events])

                    conn.commit()

                    logger.debug(
                        f"Marked {len(event_ids)} events as failed, "
                        f"{len(retry_events)} will retry, {len(dlq_events)} moved to DLQ"
                    )

        except sqlite3.Error as e:
            logger.error(f"Failed to mark batch failed: {e}")

    def get_state(self, key: str | StateKey) -> str | None:
        """
        Get a state value by key.

        Args:
            key: State key (StateKey enum or string).

        Returns:
            State value if exists, None otherwise.

        Example:
            >>> if queue.get_state(StateKey.INSTALLATION_FIRED):
            ...     print("Installation already fired")
        """
        if self._closed:
            return None

        key_str = key.value if isinstance(key, StateKey) else key

        try:
            with self._get_connection() as conn:
                result = conn.execute(
                    "SELECT value FROM telemetry_state WHERE key = ?", (key_str,)
                ).fetchone()
                return result[0] if result else None

        except sqlite3.Error as e:
            logger.error(f"Failed to get state: {e}")
            return None

    def set_state(self, key: str | StateKey, value: str) -> None:
        """
        Set a state value.

        Args:
            key: State key (StateKey enum or string).
            value: Value to store.

        Example:
            >>> queue.set_state(StateKey.INSTALLATION_FIRED, "true")
        """
        if self._closed:
            logger.warning("Attempted to set state on closed queue")
            return

        key_str = key.value if isinstance(key, StateKey) else key
        now = datetime.now(timezone.utc).isoformat()

        try:
            with self._lock:
                with self._get_connection() as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO telemetry_state (key, value, updated_at)
                        VALUES (?, ?, ?)
                    """,
                        (key_str, value, now),
                    )
                    conn.commit()

        except sqlite3.Error as e:
            logger.error(f"Failed to set state: {e}")

    def has_state(self, key: str | StateKey) -> bool:
        """
        Check if a state key exists.

        Args:
            key: State key to check.

        Returns:
            True if key exists, False otherwise.

        Example:
            >>> if not queue.has_state(StateKey.ACTIVATED_FIRST_SCAN):
            ...     # Fire first scan activation event
            ...     pass
        """
        return self.get_state(key) is not None

    def increment_state(self, key: str | StateKey, default: int = 0) -> int:
        """
        Atomically increment a numeric state value.

        Args:
            key: State key to increment.
            default: Default value if key doesn't exist.

        Returns:
            New value after increment.

        Example:
            >>> session_num = queue.increment_state(StateKey.SESSION_COUNT)
            >>> print(f"Session #{session_num}")
        """
        if self._closed:
            logger.warning("Attempted to increment state on closed queue")
            return default

        key_str = key.value if isinstance(key, StateKey) else key
        now = datetime.now(timezone.utc).isoformat()

        try:
            with self._lock:
                with self._get_connection() as conn:
                    # Get current value
                    result = conn.execute(
                        "SELECT value FROM telemetry_state WHERE key = ?", (key_str,)
                    ).fetchone()

                    current = int(result[0]) if result else default
                    new_value = current + 1

                    conn.execute(
                        """
                        INSERT OR REPLACE INTO telemetry_state (key, value, updated_at)
                        VALUES (?, ?, ?)
                    """,
                        (key_str, str(new_value), now),
                    )
                    conn.commit()

                    return new_value

        except (sqlite3.Error, ValueError) as e:
            logger.error(f"Failed to increment state: {e}")
            return default

    def move_to_dlq(
        self,
        event_id: str,
        reason: str,
        server_code: str | None = None,
        server_message: str | None = None,
    ) -> None:
        """
        Manually move an event to the dead letter queue.

        Args:
            event_id: Event ID to move.
            reason: Reason for moving to DLQ.
            server_code: HTTP error code from server.
            server_message: Error message from server.

        Example:
            >>> queue.move_to_dlq(
            ...     "evt_abc123",
            ...     "Permanent failure",
            ...     server_code="400",
            ...     server_message="Invalid payload",
            ... )
        """
        if self._closed:
            logger.warning("Attempted to move to DLQ on closed queue")
            return

        now_str = datetime.now(timezone.utc).isoformat()

        try:
            with self._lock:
                with self._get_connection() as conn:
                    # Get event from queue
                    result = conn.execute(
                        """
                        SELECT event_id, event_type, priority, payload, created_at, retry_count
                        FROM telemetry_events
                        WHERE event_id = ?
                    """,
                        (event_id,),
                    ).fetchone()

                    if not result:
                        logger.warning(f"Event {event_id} not found for DLQ move")
                        return

                    # Insert into DLQ
                    conn.execute(
                        """
                        INSERT INTO telemetry_dlq (
                            event_id, event_type, priority, payload, created_at,
                            failed_at, failure_reason, retry_count,
                            server_error_code, server_error_message
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            result[0],  # event_id
                            result[1],  # event_type
                            result[2],  # priority
                            result[3],  # payload
                            result[4],  # created_at
                            now_str,
                            reason,
                            result[5],  # retry_count
                            server_code,
                            server_message,
                        ),
                    )

                    # Remove from main queue
                    conn.execute("DELETE FROM telemetry_events WHERE event_id = ?", (event_id,))

                    conn.commit()

                    logger.info(f"Moved event {event_id} to DLQ: {reason}")

        except sqlite3.Error as e:
            logger.error(f"Failed to move event to DLQ: {e}")

    def get_dlq_events(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Get events from the dead letter queue.

        Args:
            limit: Maximum number of events to return.

        Returns:
            List of DLQ event dictionaries.

        Example:
            >>> dlq_events = queue.get_dlq_events(limit=50)
            >>> for event in dlq_events:
            ...     print(f"{event['event_id']}: {event['failure_reason']}")
        """
        if self._closed:
            return []

        events: list[dict[str, Any]] = []

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT event_id, event_type, priority, payload, created_at,
                           failed_at, failure_reason, retry_count,
                           server_error_code, server_error_message
                    FROM telemetry_dlq
                    ORDER BY failed_at DESC
                    LIMIT ?
                """,
                    (limit,),
                )

                for row in cursor:
                    events.append(
                        {
                            "event_id": row[0],
                            "event_type": row[1],
                            "priority": row[2],
                            "payload": json.loads(row[3]),
                            "created_at": row[4],
                            "failed_at": row[5],
                            "failure_reason": row[6],
                            "retry_count": row[7],
                            "server_error_code": row[8],
                            "server_error_message": row[9],
                        }
                    )

        except sqlite3.Error as e:
            logger.error(f"Failed to get DLQ events: {e}")

        return events

    def retry_dlq_events(self, event_ids: list[str] | None = None) -> int:
        """
        Move events from DLQ back to main queue for retry.

        Args:
            event_ids: Specific event IDs to retry, or None for all.

        Returns:
            Number of events moved back to queue.

        Example:
            >>> # Retry specific events
            >>> count = queue.retry_dlq_events(["evt_abc123"])
            >>> # Retry all DLQ events
            >>> count = queue.retry_dlq_events()
        """
        if self._closed:
            logger.warning("Attempted to retry DLQ on closed queue")
            return 0

        moved_count = 0

        try:
            with self._lock:
                with self._get_connection() as conn:
                    if event_ids:
                        # Retry specific events
                        # Security: Safe - placeholders constructed from fixed '?' list
                        placeholders = ",".join(["?"] * len(event_ids))
                        sql = f"""
                            SELECT event_id, event_type, priority, payload, created_at
                            FROM telemetry_dlq
                            WHERE event_id IN ({placeholders})
                        """  # noqa: S608
                        cursor = conn.execute(sql, event_ids)
                    else:
                        # Retry all events
                        cursor = conn.execute(
                            """
                            SELECT event_id, event_type, priority, payload, created_at
                            FROM telemetry_dlq
                        """
                        )

                    events_to_move = list(cursor)

                    for row in events_to_move:
                        # Insert back into main queue with reset retry count
                        conn.execute(
                            """
                            INSERT INTO telemetry_events (
                                event_id, event_type, priority, payload, created_at, retry_count
                            ) VALUES (?, ?, ?, ?, ?, 0)
                        """,
                            (row[0], row[1], row[2], row[3], row[4]),
                        )

                        # Remove from DLQ
                        conn.execute("DELETE FROM telemetry_dlq WHERE event_id = ?", (row[0],))

                        moved_count += 1

                    conn.commit()

                    if moved_count:
                        logger.info(f"Moved {moved_count} events from DLQ back to queue")

        except sqlite3.Error as e:
            logger.error(f"Failed to retry DLQ events: {e}")

        return moved_count

    def clear_dlq(self, older_than_days: int | None = None) -> int:
        """
        Clear events from the dead letter queue.

        Args:
            older_than_days: Only clear events older than this many days,
                or None to clear all.

        Returns:
            Number of events cleared.

        Example:
            >>> # Clear events older than 30 days
            >>> cleared = queue.clear_dlq(older_than_days=30)
            >>> # Clear all DLQ events
            >>> cleared = queue.clear_dlq()
        """
        if self._closed:
            logger.warning("Attempted to clear DLQ on closed queue")
            return 0

        cleared_count = 0

        try:
            with self._lock:
                with self._get_connection() as conn:
                    if older_than_days is not None:
                        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
                        cutoff_str = cutoff.isoformat()

                        result = conn.execute(
                            "SELECT COUNT(*) FROM telemetry_dlq WHERE failed_at < ?",
                            (cutoff_str,),
                        ).fetchone()
                        cleared_count = result[0] if result else 0

                        conn.execute(
                            "DELETE FROM telemetry_dlq WHERE failed_at < ?",
                            (cutoff_str,),
                        )
                    else:
                        result = conn.execute("SELECT COUNT(*) FROM telemetry_dlq").fetchone()
                        cleared_count = result[0] if result else 0

                        conn.execute("DELETE FROM telemetry_dlq")

                    conn.commit()

                    if cleared_count:
                        logger.info(f"Cleared {cleared_count} events from DLQ")

        except sqlite3.Error as e:
            logger.error(f"Failed to clear DLQ: {e}")

        return cleared_count

    def get_stats(self) -> dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Dictionary with queue metrics including:
            - critical_count: Events in critical queue
            - standard_count: Events in standard queue
            - dlq_count: Events in dead letter queue
            - total_queued: Total events across all queues
            - oldest_critical: Timestamp of oldest critical event
            - oldest_standard: Timestamp of oldest standard event
            - retry_pending: Events waiting for retry

        Example:
            >>> stats = queue.get_stats()
            >>> print(f"Critical: {stats['critical_count']}")
            >>> print(f"DLQ: {stats['dlq_count']}")
        """
        if self._closed:
            return {
                "critical_count": 0,
                "standard_count": 0,
                "dlq_count": 0,
                "total_queued": 0,
                "oldest_critical": None,
                "oldest_standard": None,
                "retry_pending": 0,
            }

        stats: dict[str, Any] = {}

        try:
            with self._get_connection() as conn:
                # Count by priority
                critical_count = conn.execute(
                    "SELECT COUNT(*) FROM telemetry_events WHERE priority = 'critical'"
                ).fetchone()[0]

                standard_count = conn.execute(
                    "SELECT COUNT(*) FROM telemetry_events WHERE priority = 'standard'"
                ).fetchone()[0]

                dlq_count = conn.execute("SELECT COUNT(*) FROM telemetry_dlq").fetchone()[0]

                # Get oldest events
                oldest_critical = conn.execute(
                    """
                    SELECT MIN(created_at) FROM telemetry_events WHERE priority = 'critical'
                """
                ).fetchone()[0]

                oldest_standard = conn.execute(
                    """
                    SELECT MIN(created_at) FROM telemetry_events WHERE priority = 'standard'
                """
                ).fetchone()[0]

                # Events in retry backoff
                now = datetime.now(timezone.utc).isoformat()
                retry_pending = conn.execute(
                    """
                    SELECT COUNT(*) FROM telemetry_events
                    WHERE retry_after IS NOT NULL AND retry_after > ?
                """,
                    (now,),
                ).fetchone()[0]

                # Get lifetime stats (events_sent_total, batches_sent_total, scans_sent_total)
                events_sent_total = 0
                batches_sent_total = 0
                scans_sent_total = 0
                try:
                    result = conn.execute(
                        "SELECT stat_key, stat_value FROM telemetry_stats"
                    ).fetchall()
                    for row in result:
                        if row[0] == "events_sent_total":
                            events_sent_total = row[1]
                        elif row[0] == "batches_sent_total":
                            batches_sent_total = row[1]
                        elif row[0] == "scans_sent_total":
                            scans_sent_total = row[1]
                except sqlite3.Error:
                    pass  # Stats table might not exist in older DBs

                stats = {
                    "critical_count": critical_count,
                    "standard_count": standard_count,
                    "dlq_count": dlq_count,
                    "total_queued": critical_count + standard_count,
                    "oldest_critical": oldest_critical,
                    "oldest_standard": oldest_standard,
                    "retry_pending": retry_pending,
                    "scans_sent_total": scans_sent_total,
                    "events_sent_total": events_sent_total,
                    "batches_sent_total": batches_sent_total,
                }

        except sqlite3.Error as e:
            logger.error(f"Failed to get stats: {e}")
            stats = {
                "critical_count": 0,
                "standard_count": 0,
                "dlq_count": 0,
                "total_queued": 0,
                "oldest_critical": None,
                "oldest_standard": None,
                "retry_pending": 0,
                "scans_sent_total": 0,
                "events_sent_total": 0,
                "batches_sent_total": 0,
                "error": str(e),
            }

        return stats

    def close(self) -> None:
        """
        Close the queue and release resources.

        After closing, all operations will be no-ops and return empty/default values.

        Example:
            >>> queue = DualQueue()
            >>> # ... use queue ...
            >>> queue.close()
        """
        self._closed = True
        logger.debug("DualQueue closed")

    def __enter__(self) -> DualQueue:
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Context manager exit."""
        self.close()
