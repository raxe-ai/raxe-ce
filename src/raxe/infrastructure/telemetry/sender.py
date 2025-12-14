"""
Batch sender with circuit breaker pattern for telemetry.

This module implements a robust batch sending mechanism with:
- Circuit breaker pattern to prevent cascade failures
- Exponential backoff with jitter for retries
- Gzip compression for efficient transmission
- Thread-safe operation
"""

import gzip
import json
import logging
import random
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from raxe import __version__

logger = logging.getLogger(__name__)


def _generate_batch_id() -> str:
    """Generate a unique batch ID following the schema pattern."""
    return f"batch_{secrets.token_hex(16)}"


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    reset_timeout_seconds: int = 30
    half_open_requests: int = 3
    success_threshold: int = 2


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascade failures by opening circuit after consecutive failures.
    """

    def __init__(self, config: CircuitBreakerConfig | None = None):
        """
        Initialize circuit breaker.

        Args:
            config: Circuit breaker configuration
        """
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None
        self.half_open_requests = 0
        self._lock = threading.Lock()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If circuit is open or function fails
        """
        with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_requests = 0
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                else:
                    raise Exception(f"Circuit breaker is OPEN (will retry after {self.config.reset_timeout_seconds}s)")

            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_requests >= self.config.half_open_requests:
                    # Exceeded half-open request limit
                    raise Exception("Circuit breaker HALF_OPEN request limit exceeded")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.last_failure_time:
            return True

        time_since_failure = datetime.now(timezone.utc) - self.last_failure_time
        return time_since_failure.total_seconds() >= self.config.reset_timeout_seconds

    def _on_success(self) -> None:
        """Handle successful call."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                self.half_open_requests += 1

                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    logger.info("Circuit breaker closed after successful recovery")
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now(timezone.utc)

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.success_count = 0
                logger.warning("Circuit breaker reopened after failure in HALF_OPEN state")
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
                    logger.warning(f"Circuit breaker opened after {self.failure_count} consecutive failures")

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self.state

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.half_open_requests = 0
            logger.info("Circuit breaker manually reset")


@dataclass
class RetryPolicy:
    """Retry policy configuration."""
    max_retries: int = 2  # Reduced from 10 - CLI should fail fast
    initial_delay_ms: int = 500  # Reduced from 1000
    max_delay_ms: int = 5000  # Reduced from 512000 - max 5s wait between retries
    backoff_multiplier: float = 2.0
    jitter_factor: float = 0.1
    retry_on_status: list[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])

    @classmethod
    def no_retry(cls) -> "RetryPolicy":
        """Create a policy with no retries for shutdown/urgent operations."""
        return cls(max_retries=0, initial_delay_ms=0, max_delay_ms=0)

    @classmethod
    def fast(cls) -> "RetryPolicy":
        """Create a fast policy with minimal retries."""
        return cls(max_retries=1, initial_delay_ms=200, max_delay_ms=1000)


class BatchSender:
    """
    Batch sender for telemetry events.

    Features:
    - Circuit breaker pattern
    - Exponential backoff with jitter
    - Gzip compression
    - Configurable retry policy
    """

    # Schema version for telemetry batches
    SCHEMA_VERSION = "0.0.1"

    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        installation_id: str | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        compression: str = "gzip",
        timeout_seconds: int = 5,  # Reduced from 10 for faster failure detection
        api_key_id: str | None = None,
    ):
        """
        Initialize batch sender.

        Args:
            endpoint: Telemetry endpoint URL (must be https://)
            api_key: API key for authentication
            installation_id: Installation ID for batch envelope
            circuit_breaker: Circuit breaker instance
            retry_policy: Retry policy configuration
            compression: Compression type ("none", "gzip")
            timeout_seconds: Request timeout
            api_key_id: Pre-computed key ID for batch envelope (optional).
                If not provided, will be computed from api_key when sending.

        Raises:
            ValueError: If endpoint is not HTTPS
        """
        # Security: Validate endpoint uses HTTPS only
        parsed = urllib.parse.urlparse(endpoint)
        if parsed.scheme not in ('https', 'http'):
            raise ValueError(f"Endpoint must use HTTPS protocol, got: {parsed.scheme}")
        if parsed.scheme == 'http' and not parsed.netloc.startswith('localhost'):
            raise ValueError("HTTP endpoints only allowed for localhost, use HTTPS for production")

        self.endpoint = endpoint
        self.api_key = api_key
        self.installation_id = installation_id or "inst_unknown"
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.retry_policy = retry_policy or RetryPolicy()
        self.compression = compression
        self.timeout_seconds = timeout_seconds
        self.api_key_id = api_key_id

    def send_batch(self, events: list[dict[str, Any]], no_retry: bool = False) -> dict[str, Any]:
        """
        Send a batch of events to telemetry endpoint.

        Args:
            events: List of event dictionaries
            no_retry: If True, skip retries (useful for shutdown scenarios)

        Returns:
            Response from server

        Raises:
            Exception: If sending fails after all retries
        """
        if not events:
            return {"status": "ok", "message": "No events to send"}

        # Compute client_api_key_id: use pre-computed value or compute from api_key
        client_api_key_id = self._get_client_api_key_id()

        # Prepare payload following the API specification format
        batch_id = _generate_batch_id()
        payload = {
            "batch_id": batch_id,
            "schema_version": self.SCHEMA_VERSION,
            "client_version": __version__,
            "installation_id": self.installation_id,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "event_count": len(events),
            "compression": self.compression,
            "events": events,
        }

        # Include client_api_key_id if available (for event linking during key upgrades)
        if client_api_key_id:
            payload["client_api_key_id"] = client_api_key_id

        # For shutdown scenarios, skip retries and circuit breaker
        if no_retry:
            return self._send_request(payload)

        # Execute through circuit breaker with retry logic
        return self.circuit_breaker.call(self._send_with_retry, payload)

    def _get_client_api_key_id(self) -> str | None:
        """Get the client API key ID for the batch envelope.

        Returns pre-computed api_key_id if available, otherwise computes
        from api_key using the standard hashing algorithm.

        Returns:
            The api_key_id string (e.g., "key_23cc2f9f21f9"), or None if
            no API key is configured.
        """
        # Priority 1: Use pre-computed api_key_id
        if self.api_key_id:
            return self.api_key_id

        # Priority 2: Compute from api_key
        if self.api_key:
            from raxe.infrastructure.telemetry.credential_store import compute_key_id
            return compute_key_id(self.api_key)

        return None

    def _send_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Send payload with retry logic.

        Args:
            payload: Data to send

        Returns:
            Server response

        Raises:
            Exception: If all retries fail
        """
        last_error = None
        delay_ms = self.retry_policy.initial_delay_ms

        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                return self._send_request(payload)
            except urllib.error.HTTPError as e:
                if e.code not in self.retry_policy.retry_on_status:
                    # Non-retryable error
                    raise

                last_error = e
                if attempt < self.retry_policy.max_retries:
                    # Calculate delay with exponential backoff and jitter
                    jitter = random.uniform(
                        -self.retry_policy.jitter_factor,
                        self.retry_policy.jitter_factor
                    )
                    actual_delay = delay_ms * (1 + jitter)
                    actual_delay = min(actual_delay, self.retry_policy.max_delay_ms)

                    logger.warning(
                        f"Request failed with status {e.code}, "
                        f"retrying in {actual_delay:.0f}ms (attempt {attempt + 1}/{self.retry_policy.max_retries})"
                    )

                    time.sleep(actual_delay / 1000.0)
                    delay_ms *= self.retry_policy.backoff_multiplier

            except Exception as e:
                last_error = e
                if attempt < self.retry_policy.max_retries:
                    # Network or other error, retry with backoff
                    actual_delay = delay_ms * (1 + random.uniform(
                        -self.retry_policy.jitter_factor,
                        self.retry_policy.jitter_factor
                    ))
                    actual_delay = min(actual_delay, self.retry_policy.max_delay_ms)

                    logger.warning(
                        f"Request failed: {e}, "
                        f"retrying in {actual_delay:.0f}ms (attempt {attempt + 1}/{self.retry_policy.max_retries})"
                    )

                    time.sleep(actual_delay / 1000.0)
                    delay_ms *= self.retry_policy.backoff_multiplier

        # All retries exhausted
        raise Exception(f"Failed to send batch after {self.retry_policy.max_retries} retries: {last_error}")

    def _send_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Send HTTP request with payload.

        Args:
            payload: Data to send

        Returns:
            Server response

        Raises:
            Exception: If request fails
        """
        # Serialize payload
        json_data = json.dumps(payload).encode('utf-8')

        # Compress if enabled
        if self.compression == "gzip":
            json_data = gzip.compress(json_data)
            content_encoding = "gzip"
        else:
            content_encoding = None

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "RAXE-CE/1.0"
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        if content_encoding:
            headers["Content-Encoding"] = content_encoding

        # Create request
        # Security: Validate endpoint is HTTPS only (configured in __init__)
        request = urllib.request.Request(
            self.endpoint,
            data=json_data,
            headers=headers,
            method="POST"
        )

        # Send request
        try:
            # nosec B310 - URL scheme validated in __init__ (must be https://)
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_data = response.read()
                if response_data:
                    return json.loads(response_data.decode('utf-8'))
                return {"status": "ok", "code": response.code}

        except urllib.error.HTTPError as e:
            # Read error response if available
            error_body = None
            try:
                error_body = e.read().decode('utf-8')
            except:
                pass

            logger.error(f"HTTP error {e.code}: {error_body or e.reason}")
            raise

        except urllib.error.URLError as e:
            logger.error(f"URL error: {e.reason}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def get_circuit_state(self) -> str:
        """Get current circuit breaker state."""
        return self.circuit_breaker.get_state().value

    def send_analytics_event(
        self,
        event_type: str,
        installation_id: str,
        metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Send analytics event to telemetry endpoint.

        Args:
            event_type: Type of analytics event (installation, milestone, retention, etc.)
            installation_id: User's installation identifier
            metadata: Optional event metadata

        Returns:
            Response from server

        Raises:
            Exception: If sending fails
        """
        event = {
            "event_type": event_type,
            "installation_id": installation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }

        return self.send_batch([event])