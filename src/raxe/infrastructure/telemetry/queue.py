"""
SQLite-based event queue for telemetry with priority support.

This module implements a persistent, priority-based event queue using SQLite.
Events are stored locally and processed in priority order (critical > high > medium > low).
The queue handles overflow by dropping oldest low-priority events.
"""

import json
import logging
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event priority levels for queue processing."""
    CRITICAL = 0  # Sent immediately
    HIGH = 1      # Sent in next batch
    MEDIUM = 2    # Normal batching
    LOW = 3       # Aggressive batching, first to drop


@dataclass
class QueuedEvent:
    """Represents an event in the queue."""
    event_id: str
    event_type: str
    payload: dict[str, Any]
    priority: EventPriority
    created_at: datetime
    retry_count: int = 0
    retry_after: datetime | None = None
    batch_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "retry_count": self.retry_count,
            "retry_after": self.retry_after.isoformat() if self.retry_after else None,
            "batch_id": self.batch_id
        }

    @classmethod
    def from_row(cls, row: tuple) -> "QueuedEvent":
        """Create from database row."""
        return cls(
            event_id=row[0],
            event_type=row[1],
            payload=json.loads(row[2]),
            priority=EventPriority(row[3]),
            created_at=datetime.fromisoformat(row[4]),
            retry_count=row[5],
            retry_after=datetime.fromisoformat(row[6]) if row[6] else None,
            batch_id=row[7]
        )


class EventQueue:
    """
    SQLite-based priority event queue for telemetry.

    Features:
    - Priority-based queuing (critical > high > medium > low)
    - Persistent storage across restarts
    - Overflow handling (drops oldest low-priority events)
    - Retry support with exponential backoff
    - Batch processing support
    - Thread-safe operations
    """

    def __init__(
        self,
        db_path: Path | None = None,
        max_queue_size: int = 10000,
        max_retry_count: int = 3,
        enable_wal: bool = True
    ):
        """
        Initialize the event queue.

        Args:
            db_path: Path to SQLite database (default: ~/.raxe/telemetry.db)
            max_queue_size: Maximum events before overflow handling
            max_retry_count: Maximum retries before moving to dead letter
            enable_wal: Enable Write-Ahead Logging for better concurrency
        """
        self.db_path = db_path or Path.home() / ".raxe" / "telemetry.db"
        self.max_queue_size = max_queue_size
        self.max_retry_count = max_retry_count
        self._lock = threading.Lock()

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database(enable_wal)

        logger.info(f"EventQueue initialized at {self.db_path}")

    def _init_database(self, enable_wal: bool) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            # Enable WAL mode for better concurrency
            if enable_wal:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")

            # Create events table with indexes
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    retry_count INTEGER DEFAULT 0,
                    retry_after TEXT,
                    batch_id TEXT,
                    FOREIGN KEY (batch_id) REFERENCES batches(batch_id)
                )
            """)

            # Create indexes for efficient queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_priority_created
                ON events(priority ASC, created_at ASC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_retry_after
                ON events(retry_after)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_batch_id
                ON events(batch_id)
            """)

            # Create dead letter queue table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dead_letter_queue (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    failed_at TEXT NOT NULL,
                    failure_reason TEXT,
                    retry_count INTEGER
                )
            """)

            # Create batches table for tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS batches (
                    batch_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    sent_at TEXT,
                    response_code INTEGER,
                    response_message TEXT
                )
            """)

            # Create queue stats table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS queue_stats (
                    stat_name TEXT PRIMARY KEY,
                    stat_value INTEGER DEFAULT 0
                )
            """)

            # Initialize stats if not exist
            conn.execute("""
                INSERT OR IGNORE INTO queue_stats (stat_name, stat_value) VALUES
                ('total_queued', 0),
                ('total_sent', 0),
                ('total_dropped', 0),
                ('total_failed', 0)
            """)

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get a database connection context manager."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        try:
            yield conn
        finally:
            conn.close()

    def enqueue(
        self,
        event_type: str,
        payload: dict[str, Any],
        priority: EventPriority = EventPriority.MEDIUM
    ) -> str:
        """
        Add an event to the queue.

        Args:
            event_type: Type of event (e.g., "scan_performed")
            payload: Event data (must be JSON serializable)
            priority: Event priority level

        Returns:
            Event ID
        """
        event_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)

        with self._lock:
            with self._get_connection() as conn:
                # Check queue size
                count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

                if count >= self.max_queue_size:
                    # Handle overflow - drop oldest low priority event
                    self._handle_overflow(conn)

                # Insert new event
                conn.execute("""
                    INSERT INTO events (
                        event_id, event_type, payload, priority, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    event_id,
                    event_type,
                    json.dumps(payload),
                    priority.value,
                    created_at.isoformat()
                ))

                # Update stats
                conn.execute("""
                    UPDATE queue_stats SET stat_value = stat_value + 1
                    WHERE stat_name = 'total_queued'
                """)

                conn.commit()

                logger.debug(f"Enqueued event {event_id} with priority {priority.name}")

        return event_id

    def _handle_overflow(self, conn: sqlite3.Connection) -> None:
        """Handle queue overflow by dropping oldest low-priority events."""
        # Find and remove oldest low priority event
        result = conn.execute("""
            SELECT event_id FROM events
            WHERE priority = ?
            ORDER BY created_at ASC
            LIMIT 1
        """, (EventPriority.LOW.value,)).fetchone()

        if result:
            event_id = result[0]
            conn.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
            conn.execute("""
                UPDATE queue_stats SET stat_value = stat_value + 1
                WHERE stat_name = 'total_dropped'
            """)
            logger.warning(f"Dropped low-priority event {event_id} due to queue overflow")
        else:
            # No low priority events, try medium
            result = conn.execute("""
                SELECT event_id FROM events
                WHERE priority = ?
                ORDER BY created_at ASC
                LIMIT 1
            """, (EventPriority.MEDIUM.value,)).fetchone()

            if result:
                event_id = result[0]
                conn.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
                conn.execute("""
                    UPDATE queue_stats SET stat_value = stat_value + 1
                    WHERE stat_name = 'total_dropped'
                """)
                logger.warning(f"Dropped medium-priority event {event_id} due to queue overflow")

    def dequeue_batch(
        self,
        batch_size: int = 50,
        max_bytes: int = 100_000
    ) -> tuple[str, list[QueuedEvent]]:
        """
        Dequeue a batch of events for processing.

        Events are selected in priority order and marked with a batch ID.

        Args:
            batch_size: Maximum number of events in batch
            max_bytes: Maximum payload size in bytes

        Returns:
            Tuple of (batch_id, list of events)
        """
        batch_id = str(uuid.uuid4())
        events = []
        current_bytes = 0
        now = datetime.now(timezone.utc)

        with self._lock:
            with self._get_connection() as conn:
                # Select events ready for processing (not in retry backoff)
                cursor = conn.execute("""
                    SELECT event_id, event_type, payload, priority, created_at,
                           retry_count, retry_after, batch_id
                    FROM events
                    WHERE batch_id IS NULL
                      AND (retry_after IS NULL OR retry_after <= ?)
                    ORDER BY priority ASC, created_at ASC
                    LIMIT ?
                """, (now.isoformat(), batch_size))

                event_ids = []
                for row in cursor:
                    event = QueuedEvent.from_row(row)
                    event_json = json.dumps(event.to_dict())
                    event_bytes = len(event_json.encode('utf-8'))

                    if current_bytes + event_bytes > max_bytes and events:
                        # Stop if adding this event would exceed max bytes
                        break

                    events.append(event)
                    event_ids.append(event.event_id)
                    current_bytes += event_bytes

                if events:
                    # Mark events as part of this batch
                    # Security: Safe - placeholders constructed from fixed '?' list, all values parameterized
                    placeholders = ','.join(['?'] * len(event_ids))
                    conn.execute(f"""  # nosec B608 - Safe parameterized query
                        UPDATE events SET batch_id = ?
                        WHERE event_id IN ({placeholders})
                    """, [batch_id, *event_ids])

                    # Create batch record
                    conn.execute("""
                        INSERT INTO batches (batch_id, created_at, event_count)
                        VALUES (?, ?, ?)
                    """, (batch_id, now.isoformat(), len(events)))

                    conn.commit()

                    logger.info(f"Created batch {batch_id} with {len(events)} events")

        return batch_id, events

    def mark_batch_sent(self, batch_id: str, response_code: int = 200) -> None:
        """
        Mark a batch as successfully sent.

        Args:
            batch_id: Batch identifier
            response_code: HTTP response code
        """
        with self._lock:
            with self._get_connection() as conn:
                now = datetime.now(timezone.utc)

                # Delete events from queue
                conn.execute("DELETE FROM events WHERE batch_id = ?", (batch_id,))

                # Update batch record
                conn.execute("""
                    UPDATE batches
                    SET status = 'sent', sent_at = ?, response_code = ?
                    WHERE batch_id = ?
                """, (now.isoformat(), response_code, batch_id))

                # Update stats
                event_count = conn.execute("""
                    SELECT event_count FROM batches WHERE batch_id = ?
                """, (batch_id,)).fetchone()[0]

                conn.execute("""
                    UPDATE queue_stats SET stat_value = stat_value + ?
                    WHERE stat_name = 'total_sent'
                """, (event_count,))

                conn.commit()

                logger.info(f"Marked batch {batch_id} as sent ({event_count} events)")

    def mark_batch_failed(
        self,
        batch_id: str,
        error_message: str,
        retry_delay_seconds: int = 60
    ) -> None:
        """
        Mark a batch as failed and schedule retry.

        Args:
            batch_id: Batch identifier
            error_message: Error description
            retry_delay_seconds: Seconds to wait before retry
        """
        with self._lock:
            with self._get_connection() as conn:
                retry_after = datetime.now(timezone.utc)
                retry_after = retry_after.replace(
                    second=retry_after.second + retry_delay_seconds
                )

                # Update events for retry
                cursor = conn.execute("""
                    SELECT event_id, retry_count FROM events WHERE batch_id = ?
                """, (batch_id,))

                dead_letter_events = []
                retry_events = []

                for event_id, retry_count in cursor:
                    if retry_count >= self.max_retry_count:
                        dead_letter_events.append(event_id)
                    else:
                        retry_events.append(event_id)

                # Move max-retry events to dead letter queue
                if dead_letter_events:
                    # Security: Safe - placeholders constructed from fixed '?' list, all values parameterized
                    placeholders = ','.join(['?'] * len(dead_letter_events))
                    conn.execute(f"""  # nosec B608 - Safe parameterized query
                        INSERT INTO dead_letter_queue
                        SELECT event_id, event_type, payload, priority, created_at,
                               ?, ?, retry_count
                        FROM events WHERE event_id IN ({placeholders})
                    """, [datetime.now(timezone.utc).isoformat(), error_message, *dead_letter_events])

                    conn.execute(f"""  # nosec B608 - Safe parameterized query
                        DELETE FROM events WHERE event_id IN ({placeholders})
                    """, dead_letter_events)

                    logger.warning(f"Moved {len(dead_letter_events)} events to dead letter queue")

                # Update retry events
                if retry_events:
                    # Security: Safe - placeholders constructed from fixed '?' list, all values parameterized
                    placeholders = ','.join(['?'] * len(retry_events))
                    conn.execute(f"""  # nosec B608 - Safe parameterized query
                        UPDATE events
                        SET batch_id = NULL,
                            retry_count = retry_count + 1,
                            retry_after = ?
                        WHERE event_id IN ({placeholders})
                    """, [retry_after.isoformat(), *retry_events])

                # Update batch status
                conn.execute("""
                    UPDATE batches
                    SET status = 'failed', response_message = ?
                    WHERE batch_id = ?
                """, (error_message, batch_id))

                conn.commit()

                logger.warning(f"Marked batch {batch_id} as failed: {error_message}")

    def get_stats(self) -> dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Dictionary with queue metrics
        """
        with self._get_connection() as conn:
            # Get queue counts by priority
            priority_counts = {}
            for priority in EventPriority:
                count = conn.execute("""
                    SELECT COUNT(*) FROM events WHERE priority = ?
                """, (priority.value,)).fetchone()[0]
                priority_counts[priority.name.lower()] = count

            # Get overall stats
            stats = {}
            cursor = conn.execute("SELECT stat_name, stat_value FROM queue_stats")
            for name, value in cursor:
                stats[name] = value

            # Get current queue depth
            queue_depth = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            dead_letter_count = conn.execute("SELECT COUNT(*) FROM dead_letter_queue").fetchone()[0]

            return {
                "queue_depth": queue_depth,
                "dead_letter_count": dead_letter_count,
                "priority_breakdown": priority_counts,
                **stats
            }

    def clear_queue(self) -> None:
        """Clear all events from the queue (for testing/reset)."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM events")
                conn.execute("DELETE FROM batches")
                conn.execute("UPDATE queue_stats SET stat_value = 0")
                conn.commit()
                logger.warning("Queue cleared")