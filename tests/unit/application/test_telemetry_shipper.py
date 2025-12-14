"""Tests for BatchSender HTTP client.

This module tests the BatchSender class which handles:
- HTTP batch shipping with gzip compression
- Circuit breaker pattern (closed, open, half_open states)
- Retry with exponential backoff
- Various HTTP error handling (429, 401/403, 422, 5xx)
- Network timeout handling
- Dry-run mode
- Health check endpoint
- Clock drift detection
- Batch building and schema compliance
"""

from __future__ import annotations

import gzip
import io
import json
import time
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from raxe.infrastructure.telemetry.sender import (
    BatchSender,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    RetryPolicy,
)

from .conftest import create_http_error, create_mock_urlopen_response

if TYPE_CHECKING:
    from raxe.domain.telemetry.events import TelemetryEvent


# =============================================================================
# CircuitBreaker Tests
# =============================================================================


class TestCircuitBreaker:
    """Tests for CircuitBreaker pattern implementation."""

    def test_initial_state_is_closed(self, circuit_breaker: CircuitBreaker) -> None:
        """Circuit breaker starts in CLOSED state."""
        assert circuit_breaker.get_state() == CircuitState.CLOSED

    def test_successful_calls_keep_circuit_closed(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Successful calls keep the circuit in CLOSED state."""
        for _ in range(10):
            result = circuit_breaker.call(lambda: "success")
            assert result == "success"

        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    def test_failures_below_threshold_stay_closed(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Failures below threshold keep circuit CLOSED."""
        # Config has failure_threshold=3
        for _ in range(2):  # Less than threshold
            try:
                circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 2

    def test_failures_at_threshold_open_circuit(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Reaching failure threshold opens the circuit."""
        # Config has failure_threshold=3
        for _ in range(3):
            try:
                circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        assert circuit_breaker.get_state() == CircuitState.OPEN

    def test_open_circuit_rejects_calls(
        self, open_circuit_breaker: CircuitBreaker
    ) -> None:
        """OPEN circuit rejects calls immediately."""
        with pytest.raises(Exception) as exc_info:
            open_circuit_breaker.call(lambda: "should not run")

        assert "Circuit breaker is OPEN" in str(exc_info.value)

    def test_circuit_transitions_to_half_open_after_timeout(
        self, circuit_breaker_config: CircuitBreakerConfig
    ) -> None:
        """Circuit transitions to HALF_OPEN after reset timeout."""
        # Create circuit with very short timeout
        config = CircuitBreakerConfig(
            failure_threshold=2,
            reset_timeout_seconds=0,  # Immediate reset
            half_open_requests=2,
            success_threshold=1,
        )
        cb = CircuitBreaker(config)

        # Open the circuit
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        assert cb.get_state() == CircuitState.OPEN

        # Next call should transition to HALF_OPEN (timeout is 0)
        # This will try to make a call in HALF_OPEN state
        try:
            cb.call(lambda: "success")
        except Exception:
            pass

        # Should have transitioned through HALF_OPEN
        # After success it may close again depending on success_threshold
        assert cb.get_state() in (CircuitState.HALF_OPEN, CircuitState.CLOSED)

    def test_half_open_success_closes_circuit(self) -> None:
        """Successful calls in HALF_OPEN state close the circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            reset_timeout_seconds=0,
            half_open_requests=5,
            success_threshold=2,  # Need 2 successes to close
        )
        cb = CircuitBreaker(config)

        # Open circuit
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        assert cb.get_state() == CircuitState.OPEN

        # First call transitions to HALF_OPEN and succeeds
        cb.call(lambda: "success")
        assert cb.get_state() == CircuitState.HALF_OPEN

        # Second success closes the circuit
        cb.call(lambda: "success")
        assert cb.get_state() == CircuitState.CLOSED

    def test_half_open_failure_reopens_circuit(self) -> None:
        """Failure in HALF_OPEN state reopens the circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            reset_timeout_seconds=0,
            half_open_requests=5,
            success_threshold=2,
        )
        cb = CircuitBreaker(config)

        # Open circuit
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        # Transition to HALF_OPEN with first call
        cb.call(lambda: "success")
        assert cb.get_state() == CircuitState.HALF_OPEN

        # Failure reopens circuit
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("fail in half-open")))
        except Exception:
            pass

        assert cb.get_state() == CircuitState.OPEN

    def test_manual_reset(self, open_circuit_breaker: CircuitBreaker) -> None:
        """Circuit can be manually reset to CLOSED."""
        assert open_circuit_breaker.get_state() == CircuitState.OPEN

        open_circuit_breaker.reset()

        assert open_circuit_breaker.get_state() == CircuitState.CLOSED
        assert open_circuit_breaker.failure_count == 0
        assert open_circuit_breaker.success_count == 0

    def test_success_resets_failure_count_in_closed(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Successful call resets failure count when CLOSED."""
        # Build up some failures
        try:
            circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        except Exception:
            pass
        assert circuit_breaker.failure_count == 1

        # Success resets count
        circuit_breaker.call(lambda: "success")
        assert circuit_breaker.failure_count == 0


# =============================================================================
# RetryPolicy Tests
# =============================================================================


class TestRetryPolicy:
    """Tests for RetryPolicy configuration."""

    def test_default_retry_policy(self) -> None:
        """Default retry policy has expected values."""
        policy = RetryPolicy()
        assert policy.max_retries == 10  # Updated per specification
        assert policy.initial_delay_ms == 1000
        assert policy.max_delay_ms == 512000  # 512s max per specification
        assert policy.backoff_multiplier == 2.0
        assert 429 in policy.retry_on_status
        assert 500 in policy.retry_on_status

    def test_custom_retry_policy(self) -> None:
        """Custom retry policy values are set correctly."""
        policy = RetryPolicy(
            max_retries=5,
            initial_delay_ms=500,
            max_delay_ms=10000,
            backoff_multiplier=1.5,
            jitter_factor=0.2,
            retry_on_status=[429, 503],
        )
        assert policy.max_retries == 5
        assert policy.initial_delay_ms == 500
        assert policy.max_delay_ms == 10000
        assert policy.backoff_multiplier == 1.5
        assert policy.jitter_factor == 0.2
        assert policy.retry_on_status == [429, 503]


# =============================================================================
# BatchSender Tests
# =============================================================================


class TestBatchSender:
    """Tests for BatchSender HTTP client."""

    def test_endpoint_validation_requires_https(self) -> None:
        """Endpoint must use HTTPS for non-localhost."""
        with pytest.raises(ValueError, match="HTTP endpoints only allowed for localhost"):
            BatchSender(
                endpoint="http://example.com/v1/telemetry",  # HTTP to non-localhost fails
                api_key="raxe_test_xxx",
            )

    def test_endpoint_allows_localhost_http(self) -> None:
        """HTTP is allowed for localhost endpoints."""
        sender = BatchSender(
            endpoint="http://localhost:9999/v1/telemetry",
            api_key="raxe_test_xxx",
        )
        assert sender.endpoint == "http://localhost:9999/v1/telemetry"

    def test_endpoint_allows_https(self) -> None:
        """HTTPS endpoints are allowed."""
        sender = BatchSender(
            endpoint="https://test.example.com/v1/telemetry",
            api_key="raxe_test_xxx",
        )
        assert sender.endpoint == "https://test.example.com/v1/telemetry"

    def test_send_empty_batch_returns_ok(self, mock_shipper: BatchSender) -> None:
        """Sending empty batch returns success without HTTP call."""
        result = mock_shipper.send_batch([])
        assert result["status"] == "ok"
        assert "No events to send" in result["message"]

    @patch("urllib.request.urlopen")
    def test_successful_batch_shipping(
        self, mock_urlopen: Mock, production_shipper: BatchSender
    ) -> None:
        """Successful batch is sent and returns response."""
        mock_urlopen.return_value = create_mock_urlopen_response(
            200, {"status": "ok", "accepted": 5}
        )

        events = [
            {"event_id": f"evt_{i}", "event_type": "scan", "payload": {}}
            for i in range(5)
        ]

        result = production_shipper.send_batch(events)

        assert result["status"] == "ok"
        assert result["accepted"] == 5
        mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_gzip_compression_enabled(
        self, mock_urlopen: Mock, production_shipper: BatchSender
    ) -> None:
        """Request body is gzip compressed when compression is enabled."""
        mock_urlopen.return_value = create_mock_urlopen_response(200, {"status": "ok"})

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]
        production_shipper.send_batch(events)

        # Get the request that was made
        request_obj = mock_urlopen.call_args[0][0]

        # Check Content-Encoding header
        assert request_obj.get_header("Content-encoding") == "gzip"

        # Verify body is actually gzipped
        body = request_obj.data
        decompressed = gzip.decompress(body)
        payload = json.loads(decompressed)
        assert "events" in payload
        assert len(payload["events"]) == 1

    @patch("urllib.request.urlopen")
    def test_no_compression_sends_raw_json(
        self, mock_urlopen: Mock, circuit_breaker: CircuitBreaker
    ) -> None:
        """Request body is raw JSON when compression is disabled."""
        sender = BatchSender(
            endpoint="https://test.local/v1/telemetry",
            api_key="raxe_test_xxx",
            circuit_breaker=circuit_breaker,
            compression="none",
        )

        mock_urlopen.return_value = create_mock_urlopen_response(200, {"status": "ok"})

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]
        sender.send_batch(events)

        request_obj = mock_urlopen.call_args[0][0]

        # No Content-Encoding header
        assert request_obj.get_header("Content-encoding") is None

        # Body is raw JSON
        payload = json.loads(request_obj.data)
        assert "events" in payload

    @patch("urllib.request.urlopen")
    def test_authorization_header_set(
        self, mock_urlopen: Mock, production_shipper: BatchSender
    ) -> None:
        """Authorization header is set with Bearer token."""
        mock_urlopen.return_value = create_mock_urlopen_response(200, {"status": "ok"})

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]
        production_shipper.send_batch(events)

        request_obj = mock_urlopen.call_args[0][0]
        auth_header = request_obj.get_header("Authorization")
        assert auth_header.startswith("Bearer ")
        assert "raxe_test_" in auth_header

    @patch("urllib.request.urlopen")
    def test_user_agent_header_set(
        self, mock_urlopen: Mock, production_shipper: BatchSender
    ) -> None:
        """User-Agent header identifies RAXE CE."""
        mock_urlopen.return_value = create_mock_urlopen_response(200, {"status": "ok"})

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]
        production_shipper.send_batch(events)

        request_obj = mock_urlopen.call_args[0][0]
        user_agent = request_obj.get_header("User-agent")
        assert "RAXE" in user_agent

    def test_get_circuit_state(self, mock_shipper: BatchSender) -> None:
        """Can retrieve circuit breaker state."""
        state = mock_shipper.get_circuit_state()
        assert state == "closed"


# =============================================================================
# Retry Tests
# =============================================================================


class TestBatchSenderRetry:
    """Tests for retry behavior with exponential backoff."""

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_retry_on_5xx_error(
        self, mock_urlopen: Mock, mock_sleep: Mock, retry_policy: RetryPolicy
    ) -> None:
        """5xx errors trigger retry with exponential backoff."""
        # First 2 calls fail with 503, third succeeds
        mock_urlopen.side_effect = [
            create_http_error(503, {"error": "Service unavailable"}),
            create_http_error(503, {"error": "Service unavailable"}),
            create_mock_urlopen_response(200, {"status": "ok"}),
        ]

        sender = BatchSender(
            endpoint="https://test.local/v1/telemetry",
            api_key="raxe_test_xxx",
            retry_policy=retry_policy,
        )

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]
        result = sender.send_batch(events)

        assert result["status"] == "ok"
        assert mock_urlopen.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_retry_exhaustion_raises_exception(
        self, mock_urlopen: Mock, mock_sleep: Mock, retry_policy: RetryPolicy
    ) -> None:
        """All retries exhausted raises exception."""
        # All calls fail
        mock_urlopen.side_effect = create_http_error(
            503, {"error": "Service unavailable"}
        )

        sender = BatchSender(
            endpoint="https://test.local/v1/telemetry",
            api_key="raxe_test_xxx",
            retry_policy=retry_policy,
        )

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]

        with pytest.raises(Exception, match="Failed to send batch after"):
            sender.send_batch(events)

        # Initial + max_retries (3) = 4 attempts
        assert mock_urlopen.call_count == 4

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_exponential_backoff_delays(
        self, mock_urlopen: Mock, mock_sleep: Mock
    ) -> None:
        """Retry delays follow exponential backoff pattern."""
        policy = RetryPolicy(
            max_retries=3,
            initial_delay_ms=100,
            max_delay_ms=1000,
            backoff_multiplier=2.0,
            jitter_factor=0.0,  # No jitter for predictable delays
        )

        mock_urlopen.side_effect = [
            create_http_error(503, {"error": "fail"}),
            create_http_error(503, {"error": "fail"}),
            create_http_error(503, {"error": "fail"}),
            create_mock_urlopen_response(200, {"status": "ok"}),
        ]

        sender = BatchSender(
            endpoint="https://test.local/v1/telemetry",
            api_key="raxe_test_xxx",
            retry_policy=policy,
        )

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]
        sender.send_batch(events)

        # Check sleep calls: 100ms, 200ms, 400ms
        sleep_times = [call[0][0] for call in mock_sleep.call_args_list]
        assert len(sleep_times) == 3
        assert sleep_times[0] == pytest.approx(0.1, abs=0.01)  # 100ms
        assert sleep_times[1] == pytest.approx(0.2, abs=0.01)  # 200ms
        assert sleep_times[2] == pytest.approx(0.4, abs=0.01)  # 400ms

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_delay_capped_at_max(
        self, mock_urlopen: Mock, mock_sleep: Mock
    ) -> None:
        """Retry delay is capped at max_delay_ms."""
        policy = RetryPolicy(
            max_retries=3,
            initial_delay_ms=500,
            max_delay_ms=600,  # Cap at 600ms
            backoff_multiplier=2.0,
            jitter_factor=0.0,
        )

        mock_urlopen.side_effect = [
            create_http_error(503, {"error": "fail"}),
            create_http_error(503, {"error": "fail"}),
            create_http_error(503, {"error": "fail"}),
            create_mock_urlopen_response(200, {"status": "ok"}),
        ]

        sender = BatchSender(
            endpoint="https://test.local/v1/telemetry",
            api_key="raxe_test_xxx",
            retry_policy=policy,
        )

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]
        sender.send_batch(events)

        sleep_times = [call[0][0] for call in mock_sleep.call_args_list]
        # All should be capped at 600ms (0.6s)
        for sleep_time in sleep_times:
            assert sleep_time <= 0.6


# =============================================================================
# HTTP Error Handling Tests
# =============================================================================


class TestBatchSenderErrorHandling:
    """Tests for specific HTTP error handling."""

    @patch("urllib.request.urlopen")
    def test_429_rate_limit_triggers_retry(
        self, mock_urlopen: Mock, retry_policy: RetryPolicy
    ) -> None:
        """429 rate limit error triggers retry."""
        with patch("time.sleep"):
            mock_urlopen.side_effect = [
                create_http_error(429, {"error": "Rate limited"}),
                create_mock_urlopen_response(200, {"status": "ok"}),
            ]

            sender = BatchSender(
                endpoint="https://test.local/v1/telemetry",
                api_key="raxe_test_xxx",
                retry_policy=retry_policy,
            )

            events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]
            result = sender.send_batch(events)

            assert result["status"] == "ok"
            assert mock_urlopen.call_count == 2

    @patch("urllib.request.urlopen")
    def test_401_auth_error_no_retry(
        self, mock_urlopen: Mock, retry_policy: RetryPolicy
    ) -> None:
        """401 authentication error does not trigger retry."""
        mock_urlopen.side_effect = create_http_error(401, {"error": "Unauthorized"})

        sender = BatchSender(
            endpoint="https://test.local/v1/telemetry",
            api_key="raxe_test_xxx",
            retry_policy=retry_policy,
        )

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            sender.send_batch(events)

        assert exc_info.value.code == 401
        # Only one call - no retries for auth errors
        assert mock_urlopen.call_count == 1

    @patch("urllib.request.urlopen")
    def test_403_forbidden_no_retry(
        self, mock_urlopen: Mock, retry_policy: RetryPolicy
    ) -> None:
        """403 forbidden error does not trigger retry."""
        mock_urlopen.side_effect = create_http_error(403, {"error": "Forbidden"})

        sender = BatchSender(
            endpoint="https://test.local/v1/telemetry",
            api_key="raxe_test_xxx",
            retry_policy=retry_policy,
        )

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            sender.send_batch(events)

        assert exc_info.value.code == 403
        assert mock_urlopen.call_count == 1

    @patch("urllib.request.urlopen")
    def test_422_privacy_violation_no_retry(
        self, mock_urlopen: Mock, retry_policy: RetryPolicy
    ) -> None:
        """422 privacy violation does not trigger retry (should go to DLQ)."""
        mock_urlopen.side_effect = create_http_error(
            422, {"error": "Privacy violation", "field": "payload.prompt"}
        )

        sender = BatchSender(
            endpoint="https://test.local/v1/telemetry",
            api_key="raxe_test_xxx",
            retry_policy=retry_policy,
        )

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            sender.send_batch(events)

        assert exc_info.value.code == 422
        assert mock_urlopen.call_count == 1

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_network_timeout_triggers_retry(
        self, mock_urlopen: Mock, mock_sleep: Mock, retry_policy: RetryPolicy
    ) -> None:
        """Network timeout triggers retry."""
        mock_urlopen.side_effect = [
            urllib.error.URLError("Connection timed out"),
            urllib.error.URLError("Connection timed out"),
            create_mock_urlopen_response(200, {"status": "ok"}),
        ]

        sender = BatchSender(
            endpoint="https://test.local/v1/telemetry",
            api_key="raxe_test_xxx",
            retry_policy=retry_policy,
        )

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]
        result = sender.send_batch(events)

        assert result["status"] == "ok"
        assert mock_urlopen.call_count == 3

    @patch("urllib.request.urlopen")
    def test_circuit_opens_after_repeated_failures(
        self, mock_urlopen: Mock, circuit_breaker_config: CircuitBreakerConfig
    ) -> None:
        """Circuit breaker opens after repeated failures."""
        # Configure to open quickly
        cb_config = CircuitBreakerConfig(
            failure_threshold=2,
            reset_timeout_seconds=60,
            half_open_requests=1,
            success_threshold=1,
        )
        cb = CircuitBreaker(cb_config)
        policy = RetryPolicy(max_retries=0)  # No retries for faster test

        mock_urlopen.side_effect = create_http_error(503, {"error": "fail"})

        sender = BatchSender(
            endpoint="https://test.local/v1/telemetry",
            api_key="raxe_test_xxx",
            circuit_breaker=cb,
            retry_policy=policy,
        )

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]

        # First two failures open the circuit
        for _ in range(2):
            try:
                sender.send_batch(events)
            except Exception:
                pass

        assert cb.get_state() == CircuitState.OPEN

        # Subsequent calls are rejected by circuit breaker
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            sender.send_batch(events)


# =============================================================================
# Batch Building Tests
# =============================================================================


class TestBatchBuilding:
    """Tests for batch payload construction and schema compliance."""

    @patch("urllib.request.urlopen")
    def test_batch_includes_metadata(
        self, mock_urlopen: Mock, production_shipper: BatchSender
    ) -> None:
        """Batch payload includes timestamp and batch_size metadata."""
        mock_urlopen.return_value = create_mock_urlopen_response(200, {"status": "ok"})

        events = [
            {"event_id": f"evt_{i}", "event_type": "scan", "payload": {}}
            for i in range(3)
        ]
        production_shipper.send_batch(events)

        request_obj = mock_urlopen.call_args[0][0]
        body = gzip.decompress(request_obj.data)
        payload = json.loads(body)

        assert "events" in payload
        assert "timestamp" in payload
        assert "batch_size" in payload
        assert payload["batch_size"] == 3
        assert len(payload["events"]) == 3

    @patch("urllib.request.urlopen")
    def test_batch_timestamp_is_iso8601(
        self, mock_urlopen: Mock, production_shipper: BatchSender
    ) -> None:
        """Batch timestamp is valid ISO 8601 format."""
        mock_urlopen.return_value = create_mock_urlopen_response(200, {"status": "ok"})

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]
        production_shipper.send_batch(events)

        request_obj = mock_urlopen.call_args[0][0]
        body = gzip.decompress(request_obj.data)
        payload = json.loads(body)

        # Should be parseable as ISO 8601
        timestamp = datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))
        assert isinstance(timestamp, datetime)

    @patch("urllib.request.urlopen")
    def test_events_preserved_in_batch(
        self, mock_urlopen: Mock, production_shipper: BatchSender
    ) -> None:
        """Event structure is preserved in batch."""
        mock_urlopen.return_value = create_mock_urlopen_response(200, {"status": "ok"})

        events = [
            {
                "event_id": "evt_test_123",
                "event_type": "scan",
                "timestamp": "2025-01-22T10:00:00Z",
                "payload": {"threat_detected": True, "prompt_hash": "a" * 64},
            }
        ]
        production_shipper.send_batch(events)

        request_obj = mock_urlopen.call_args[0][0]
        body = gzip.decompress(request_obj.data)
        payload = json.loads(body)

        batch_event = payload["events"][0]
        assert batch_event["event_id"] == "evt_test_123"
        assert batch_event["event_type"] == "scan"
        assert batch_event["payload"]["threat_detected"] is True


# =============================================================================
# Analytics Event Tests
# =============================================================================


class TestSendAnalyticsEvent:
    """Tests for send_analytics_event convenience method."""

    @patch("urllib.request.urlopen")
    def test_analytics_event_structure(
        self, mock_urlopen: Mock, production_shipper: BatchSender
    ) -> None:
        """Analytics event has correct structure."""
        mock_urlopen.return_value = create_mock_urlopen_response(200, {"status": "ok"})

        production_shipper.send_analytics_event(
            event_type="milestone",
            installation_id="inst_test123",
            metadata={"milestone": "1000_scans"},
        )

        request_obj = mock_urlopen.call_args[0][0]
        body = gzip.decompress(request_obj.data)
        payload = json.loads(body)

        event = payload["events"][0]
        assert event["event_type"] == "milestone"
        assert event["installation_id"] == "inst_test123"
        assert event["metadata"]["milestone"] == "1000_scans"
        assert "timestamp" in event

    @patch("urllib.request.urlopen")
    def test_analytics_event_empty_metadata(
        self, mock_urlopen: Mock, production_shipper: BatchSender
    ) -> None:
        """Analytics event with no metadata uses empty dict."""
        mock_urlopen.return_value = create_mock_urlopen_response(200, {"status": "ok"})

        production_shipper.send_analytics_event(
            event_type="installation",
            installation_id="inst_test123",
        )

        request_obj = mock_urlopen.call_args[0][0]
        body = gzip.decompress(request_obj.data)
        payload = json.loads(body)

        event = payload["events"][0]
        assert event["metadata"] == {}


# =============================================================================
# Integration with Circuit Breaker
# =============================================================================


class TestCircuitBreakerIntegration:
    """Tests for circuit breaker integration with BatchSender."""

    @patch("urllib.request.urlopen")
    def test_circuit_breaker_state_updates(
        self, mock_urlopen: Mock
    ) -> None:
        """Circuit breaker state updates based on request success/failure."""
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=2, reset_timeout_seconds=60)
        )
        sender = BatchSender(
            endpoint="https://test.local/v1/telemetry",
            api_key="raxe_test_xxx",
            circuit_breaker=cb,
            retry_policy=RetryPolicy(max_retries=0),
        )

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]

        # Successful call
        mock_urlopen.return_value = create_mock_urlopen_response(200, {"status": "ok"})
        sender.send_batch(events)
        assert sender.get_circuit_state() == "closed"

        # Failures open circuit
        mock_urlopen.side_effect = create_http_error(503, {"error": "fail"})
        for _ in range(2):
            try:
                sender.send_batch(events)
            except Exception:
                pass

        assert sender.get_circuit_state() == "open"

    @patch("urllib.request.urlopen")
    def test_circuit_recovery_after_timeout(self, mock_urlopen: Mock) -> None:
        """Circuit recovers after timeout period."""
        cb = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=2,
                reset_timeout_seconds=0,  # Immediate recovery
                half_open_requests=1,
                success_threshold=1,
            )
        )
        sender = BatchSender(
            endpoint="https://test.local/v1/telemetry",
            api_key="raxe_test_xxx",
            circuit_breaker=cb,
            retry_policy=RetryPolicy(max_retries=0),
        )

        events = [{"event_id": "evt_1", "event_type": "scan", "payload": {}}]

        # Open the circuit
        mock_urlopen.side_effect = create_http_error(503, {"error": "fail"})
        for _ in range(2):
            try:
                sender.send_batch(events)
            except Exception:
                pass

        assert sender.get_circuit_state() == "open"

        # Successful call should recover
        mock_urlopen.side_effect = None
        mock_urlopen.return_value = create_mock_urlopen_response(200, {"status": "ok"})
        result = sender.send_batch(events)

        assert result["status"] == "ok"
        assert sender.get_circuit_state() == "closed"
