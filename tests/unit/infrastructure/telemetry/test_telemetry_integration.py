"""
Comprehensive tests for the telemetry system.

Tests cover:
- SQLite event queue with priority handling
- Batch sender with circuit breaker
- Hash-only event creation (privacy)
- Telemetry configuration
- End-to-end integration
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raxe.application.telemetry_manager import TelemetryManager
from raxe.domain.telemetry import create_scan_event_legacy as create_scan_event
from raxe.domain.telemetry import hash_text, validate_event_privacy
from raxe.infrastructure.telemetry.config import TelemetryConfig
from raxe.infrastructure.telemetry.queue import EventPriority, EventQueue
from raxe.infrastructure.telemetry.sender import (
    BatchSender,
    CircuitBreaker,
    CircuitState,
    RetryPolicy,
)


class TestEventQueue:
    """Test SQLite event queue functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        # Cleanup
        try:
            db_path.unlink()
        except:
            pass

    def test_queue_initialization(self, temp_db):
        """Test queue initializes with proper schema."""
        EventQueue(db_path=temp_db)

        # Check tables exist
        with sqlite3.connect(str(temp_db)) as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table'
                ORDER BY name
            """)
            tables = [row[0] for row in cursor]

        assert "events" in tables
        assert "dead_letter_queue" in tables
        assert "batches" in tables
        assert "queue_stats" in tables

    def test_enqueue_dequeue(self, temp_db):
        """Test basic enqueue and dequeue operations."""
        queue = EventQueue(db_path=temp_db)

        # Enqueue events with different priorities
        queue.enqueue("scan_performed", {"test": "data1"}, EventPriority.CRITICAL)
        queue.enqueue("scan_performed", {"test": "data2"}, EventPriority.LOW)
        queue.enqueue("scan_performed", {"test": "data3"}, EventPriority.HIGH)

        # Dequeue batch - should get in priority order
        _batch_id, events = queue.dequeue_batch(batch_size=10)

        assert len(events) == 3
        # Check priority order: CRITICAL, HIGH, LOW
        assert events[0].priority == EventPriority.CRITICAL
        assert events[1].priority == EventPriority.HIGH
        assert events[2].priority == EventPriority.LOW

    def test_queue_overflow_handling(self, temp_db):
        """Test queue handles overflow by dropping low priority events."""
        queue = EventQueue(db_path=temp_db, max_queue_size=3)

        # Fill queue
        queue.enqueue("event", {"n": 1}, EventPriority.LOW)
        queue.enqueue("event", {"n": 2}, EventPriority.MEDIUM)
        queue.enqueue("event", {"n": 3}, EventPriority.HIGH)

        stats = queue.get_stats()
        assert stats["queue_depth"] == 3

        # Add one more - should drop lowest priority
        queue.enqueue("event", {"n": 4}, EventPriority.CRITICAL)

        stats = queue.get_stats()
        assert stats["queue_depth"] == 3
        assert stats["total_dropped"] == 1

        # Check that low priority was dropped
        _batch_id, events = queue.dequeue_batch()
        priorities = [e.priority for e in events]
        assert EventPriority.LOW not in priorities
        assert EventPriority.CRITICAL in priorities

    def test_batch_success_and_failure(self, temp_db):
        """Test marking batches as sent or failed."""
        queue = EventQueue(db_path=temp_db)

        # Add events
        for i in range(5):
            queue.enqueue("event", {"n": i}, EventPriority.MEDIUM)

        # Dequeue batch
        batch_id, events = queue.dequeue_batch(batch_size=3)
        assert len(events) == 3

        # Mark as sent
        queue.mark_batch_sent(batch_id)

        stats = queue.get_stats()
        assert stats["total_sent"] == 3
        assert stats["queue_depth"] == 2

        # Dequeue another batch
        batch_id2, events2 = queue.dequeue_batch()
        assert len(events2) == 2

        # Mark as failed
        queue.mark_batch_failed(batch_id2, "Network error", retry_delay_seconds=1)

        # Events should be back in queue with retry_after set
        stats = queue.get_stats()
        assert stats["queue_depth"] == 2


class TestCircuitBreaker:
    """Test circuit breaker pattern."""

    def test_circuit_breaker_states(self):
        """Test circuit breaker state transitions."""
        config = CircuitBreakerConfig(
            failure_threshold=2, reset_timeout_seconds=1, success_threshold=1
        )
        breaker = CircuitBreaker(config)

        # Initially closed
        assert breaker.get_state() == CircuitState.CLOSED

        # Successful call
        result = breaker.call(lambda: "success")
        assert result == "success"
        assert breaker.get_state() == CircuitState.CLOSED

        # Two failures opens circuit
        with pytest.raises(Exception):
            breaker.call(lambda: 1 / 0)
        assert breaker.get_state() == CircuitState.CLOSED

        with pytest.raises(Exception):
            breaker.call(lambda: 1 / 0)
        assert breaker.get_state() == CircuitState.OPEN

        # Circuit is open, calls rejected
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            breaker.call(lambda: "test")

        # Wait for reset timeout
        import time

        time.sleep(1.1)

        # Circuit transitions to half-open
        result = breaker.call(lambda: "recovery")
        assert result == "recovery"
        assert breaker.get_state() == CircuitState.CLOSED


class TestBatchSender:
    """Test batch sender with mocked HTTP."""

    @patch("urllib.request.urlopen")
    def test_successful_send(self, mock_urlopen):
        """Test successful batch sending."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_response.code = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        sender = BatchSender(endpoint="https://test.com/events", api_key="test_key")

        events = [{"event": "test1"}, {"event": "test2"}]
        result = sender.send_batch(events)

        assert result["status"] == "ok"
        mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_retry_on_failure(self, mock_urlopen):
        """Test retry logic on failures."""
        # Mock failures then success
        mock_urlopen.side_effect = [
            urllib.error.HTTPError(None, 500, "Server Error", {}, None),
            urllib.error.HTTPError(None, 503, "Service Unavailable", {}, None),
            MagicMock(
                read=MagicMock(return_value=b'{"status": "ok"}'),
                code=200,
                __enter__=lambda s: s,
                __exit__=lambda s, *args: None,
            ),
        ]

        retry_policy = RetryPolicy(max_retries=2, initial_delay_ms=10, backoff_multiplier=1.5)

        sender = BatchSender(endpoint="https://test.com/events", retry_policy=retry_policy)

        events = [{"event": "test"}]
        result = sender.send_batch(events)

        assert result["status"] == "ok"
        assert mock_urlopen.call_count == 3


class TestEventCreation:
    """Test privacy-preserving event creation."""

    def test_hash_text(self):
        """Test text hashing is deterministic and irreversible."""
        text = "This is sensitive information"
        hash1 = hash_text(text)
        hash2 = hash_text(text)

        # Deterministic
        assert hash1 == hash2
        # SHA256 produces 71 char prefixed string (sha256: + 64 hex)
        assert len(hash1) == 71
        assert hash1.startswith("sha256:")
        # Cannot recover original text
        assert text not in hash1

    def test_create_scan_event_privacy(self):
        """Test event creation preserves privacy."""
        scan_result = {
            "prompt": "Tell me about user@example.com",
            "l1_result": {
                "detections": [{"rule_id": "pii_001", "severity": "HIGH", "confidence": 0.95}]
            },
            "l2_result": {"predictions": [{"threat_type": "pii_leak", "confidence": 0.88}]},
            "policy_result": {"action": "BLOCK", "matched_policies": ["no_pii"]},
        }

        event = create_scan_event(
            scan_result=scan_result,
            customer_id="cust-12345678",
            context={"session_id": "sess_123", "user_id": "user_456"},
        )

        # Check no PII in event
        event_str = json.dumps(event)
        assert "user@example.com" not in event_str
        assert "Tell me about" not in event_str
        assert "sess_123" not in event_str
        assert "user_456" not in event_str

        # Check hashes are present (71 chars = sha256: prefix + 64 hex)
        assert len(event["scan_result"]["text_hash"]) == 71
        assert event["scan_result"]["text_hash"].startswith("sha256:")
        assert event["scan_result"]["threat_detected"] is True
        assert event["scan_result"]["highest_severity"] == "high"

        # Validate privacy compliance
        violations = validate_event_privacy(event)
        assert violations == []

    def test_event_priority_calculation(self):
        """Test event priority is calculated correctly."""
        # Critical severity
        event1 = {"scan_result": {"highest_severity": "critical"}}
        assert calculate_event_priority(event1) == "critical"

        # Policy block
        event2 = {"scan_result": {"policy_decision": {"action": "BLOCK"}}}
        assert calculate_event_priority(event2) == "critical"

        # High severity
        event3 = {"scan_result": {"highest_severity": "high"}}
        assert calculate_event_priority(event3) == "high"

        # Clean scan
        event4 = {"scan_result": {"threat_detected": False}}
        assert calculate_event_priority(event4) == "low"


class TestTelemetryConfig:
    """Test telemetry configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TelemetryConfig()

        assert config.enabled is True
        assert config.privacy_mode == "strict"
        assert config.include_full_prompts is False
        assert config.batch_size == 100
        assert config.hash_algorithm == "sha256"

    def test_environment_overrides(self):
        """Test environment variable overrides."""
        with patch.dict(
            os.environ,
            {
                "RAXE_TELEMETRY_ENABLED": "false",
                "RAXE_TELEMETRY_PRIVACY_MODE": "detailed",
                "RAXE_TELEMETRY_BATCH_SIZE": "50",
                "RAXE_TELEMETRY_SAMPLE_RATE": "0.5",
            },
        ):
            config = TelemetryConfig.from_environment()

            assert config.enabled is False
            assert config.privacy_mode == "detailed"
            assert config.batch_size == 50
            assert config.sample_rate == 0.5

    def test_privacy_validation(self):
        """Test privacy settings are enforced."""
        config = TelemetryConfig(
            privacy_mode="strict",
            include_full_prompts=True,  # Should be overridden
        )
        config._validate_privacy()

        assert config.include_full_prompts is False

    def test_sampling(self):
        """Test sampling logic."""
        # Always sample
        config1 = TelemetryConfig(sample_rate=1.0)
        assert all(config1.should_sample() for _ in range(100))

        # Never sample
        config2 = TelemetryConfig(sample_rate=0.0)
        assert not any(config2.should_sample() for _ in range(100))

        # 50% sampling (approximate)
        config3 = TelemetryConfig(sample_rate=0.5)
        samples = sum(1 for _ in range(1000) if config3.should_sample())
        assert 400 < samples < 600  # Allow some variance


class TestTelemetryManager:
    """Test telemetry manager orchestration."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        try:
            db_path.unlink()
        except:
            pass

    def test_manager_initialization(self, temp_db):
        """Test manager initializes correctly."""
        config = TelemetryConfig(
            enabled=True,
            flush_interval_ms=0,  # Disable auto-flush for testing
        )

        manager = TelemetryManager(config=config, db_path=temp_db, api_key="test_key")

        assert manager.config.enabled is True
        assert manager.queue is not None
        assert manager.sender is not None

        stats = manager.get_stats()
        assert stats["enabled"] is True
        assert "queue_stats" in stats

        manager.shutdown()

    def test_manager_disabled(self):
        """Test manager when telemetry is disabled."""
        config = TelemetryConfig(enabled=False)
        manager = TelemetryManager(config=config)

        assert manager.queue is None
        assert manager.sender is None

        # Should not crash when disabled
        result = manager.track_scan(scan_result={"test": "data"}, customer_id="cust-12345678")
        assert result is None

        stats = manager.get_stats()
        assert stats == {"enabled": False}

    def test_track_scan_end_to_end(self, temp_db):
        """Test end-to-end scan tracking."""
        config = TelemetryConfig(enabled=True, flush_interval_ms=0)

        manager = TelemetryManager(config=config, db_path=temp_db)

        scan_result = {
            "prompt": "Test prompt with email@example.com",
            "l1_result": {
                "detections": [{"rule_id": "test_001", "severity": "CRITICAL", "confidence": 1.0}]
            },
            "performance": {"total_ms": 10.5, "l1_ms": 5.2, "l2_ms": 3.1, "policy_ms": 2.2},
        }

        event_id = manager.track_scan(
            scan_result=scan_result,
            customer_id="cust-12345678",
            context={"session_id": "sess_abc", "app_name": "test_app"},
        )

        assert event_id is not None

        # Check event was queued
        stats = manager.get_stats()
        assert stats["queue_stats"]["queue_depth"] == 1
        assert stats["queue_stats"]["priority_breakdown"]["critical"] == 1

        manager.shutdown()


# Import statements for missing items
import urllib.error

from raxe.domain.telemetry.event_creator import calculate_event_priority
from raxe.infrastructure.telemetry.sender import CircuitBreakerConfig

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
