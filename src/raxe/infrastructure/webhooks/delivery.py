"""
Webhook HTTP delivery infrastructure with retry and circuit breaker.

This module provides robust webhook delivery with:
- Exponential backoff with jitter for retries
- Circuit breaker pattern to prevent cascade failures
- Configurable retry policies for different error types
- HMAC-SHA256 signature authentication
- Statistics tracking for monitoring

Security:
- HTTPS required for production endpoints (HTTP only for localhost)
- All payloads signed with HMAC-SHA256
- Timeout protection against slow responses
"""

import json
import os
import random
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypedDict

from raxe import __version__
from raxe.infrastructure.webhooks.signing import WebhookSigner


class _ResponseDict(TypedDict):
    """Internal type for HTTP response."""

    status_code: int
    body: str


class WebhookDeliveryError(Exception):
    """Error raised when webhook delivery fails.

    This exception indicates delivery failure after all retries exhausted,
    or when circuit breaker is open.
    """

    pass


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class WebhookRetryPolicy:
    """Configuration for webhook retry behavior.

    Controls how the delivery service handles transient failures.

    Attributes:
        max_retries: Maximum number of retry attempts (0 = no retries)
        initial_delay_ms: Initial delay before first retry in milliseconds
        max_delay_ms: Maximum delay between retries in milliseconds
        backoff_multiplier: Factor to multiply delay after each retry
        jitter_factor: Random jitter factor (0.0 to 1.0) to prevent thundering herd
        retry_on_status: HTTP status codes that trigger retry (typically 5xx)

    Example:
        >>> policy = WebhookRetryPolicy(max_retries=3, initial_delay_ms=500)
        >>> policy.retry_on_status
        [429, 500, 502, 503, 504]
    """

    max_retries: int = 3
    initial_delay_ms: int = 500
    max_delay_ms: int = 5000
    backoff_multiplier: float = 2.0
    jitter_factor: float = 0.1
    retry_on_status: list[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])

    @classmethod
    def no_retry(cls) -> "WebhookRetryPolicy":
        """Create a policy with no retries.

        Useful for testing or when immediate failure is preferred.

        Returns:
            Policy with max_retries=0
        """
        return cls(max_retries=0)

    @classmethod
    def default(cls) -> "WebhookRetryPolicy":
        """Create the default retry policy.

        Returns:
            Policy with sensible defaults for production use
        """
        return cls()


@dataclass
class WebhookDeliveryResult:
    """Result of a webhook delivery attempt.

    Attributes:
        success: Whether delivery succeeded
        status_code: HTTP status code (None if no response received)
        error_message: Error description if failed
        error_type: Type of error (http_error, timeout, connection_error, etc.)
        attempts: Total number of delivery attempts (initial + retries)
        circuit_open: True if delivery was blocked by open circuit breaker
        response_body: Response body from server (if available)
    """

    success: bool
    status_code: int | None = None
    error_message: str | None = None
    error_type: str | None = None
    attempts: int = 1
    circuit_open: bool = False
    response_body: str | None = None


class CircuitBreaker:
    """Circuit breaker for webhook delivery.

    Prevents cascade failures by stopping requests when the endpoint
    is consistently failing.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Endpoint failing, requests blocked immediately
    - HALF_OPEN: Testing recovery, limited requests allowed
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout_seconds: int = 30,
        half_open_requests: int = 3,
        success_threshold: int = 2,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Consecutive failures to open circuit
            reset_timeout_seconds: Time before attempting recovery
            half_open_requests: Max requests in half-open state
            success_threshold: Successes needed to close circuit
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self.half_open_requests = half_open_requests
        self.success_threshold = success_threshold

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None
        self.half_open_attempt_count = 0
        self._lock = threading.Lock()

    def can_execute(self) -> bool:
        """Check if request should be allowed.

        Returns:
            True if circuit allows the request
        """
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_attempt_count = 0
                    self.success_count = 0
                    return True
                return False

            # HALF_OPEN state
            return self.half_open_attempt_count < self.half_open_requests

    def _should_attempt_reset(self) -> bool:
        """Check if enough time passed to attempt reset."""
        if not self.last_failure_time:
            return True

        elapsed = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
        return elapsed >= self.reset_timeout_seconds

    def record_success(self) -> None:
        """Record a successful request."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                self.half_open_attempt_count += 1

                if self.success_count >= self.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed request."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now(timezone.utc)

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.success_count = 0
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN

    def get_state(self) -> str:
        """Get current circuit state as string."""
        with self._lock:
            # Check if we should transition from OPEN to HALF_OPEN
            if self.state == CircuitState.OPEN and self._should_attempt_reset():
                return CircuitState.HALF_OPEN.value
            return self.state.value


class WebhookDeliveryService:
    """Service for delivering webhooks to MSSP endpoints.

    Provides reliable webhook delivery with:
    - HMAC-SHA256 signature authentication
    - Configurable retry with exponential backoff
    - Circuit breaker for cascade failure prevention
    - Delivery statistics tracking

    Security:
    - Requires HTTPS for non-localhost endpoints
    - All requests include signature and timestamp headers
    - Configurable timeout to prevent resource exhaustion

    Example:
        >>> service = WebhookDeliveryService(
        ...     endpoint="https://mssp.example.com/webhooks",
        ...     secret="whsec_your_secret_key",
        ... )
        >>> result = service.deliver({"event": "threat_detected", "data": {...}})
        >>> print(result.success)
        True
    """

    # HTTP headers
    USER_AGENT = f"RAXE-Webhook/{__version__}"
    CONTENT_TYPE = "application/json"

    def __init__(
        self,
        endpoint: str,
        secret: str,
        timeout_seconds: int = 10,
        retry_policy: WebhookRetryPolicy | None = None,
        circuit_breaker_config: dict[str, int] | None = None,
    ) -> None:
        """Initialize webhook delivery service.

        Args:
            endpoint: Webhook endpoint URL (must be HTTPS for production)
            secret: HMAC secret for signing requests
            timeout_seconds: Request timeout in seconds
            retry_policy: Retry configuration
            circuit_breaker_config: Circuit breaker settings dict

        Raises:
            ValueError: If endpoint URL is invalid or insecure
            ValueError: If secret is empty
        """
        # Validate secret
        if not secret:
            raise ValueError("Webhook secret is required and cannot be empty")

        # Validate endpoint URL
        try:
            parsed = urllib.parse.urlparse(endpoint)
        except Exception as e:
            raise ValueError(f"Invalid endpoint URL: {e}") from e

        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid endpoint URL format: {endpoint}")

        # Security: Require HTTPS for non-localhost
        if parsed.scheme == "http":
            is_localhost = parsed.netloc.startswith(("localhost", "127.0.0.1"))
            if not is_localhost:
                raise ValueError(
                    "HTTPS is required for webhook endpoints. "
                    "HTTP is only allowed for localhost during development."
                )
        elif parsed.scheme != "https":
            raise ValueError(
                f"Invalid URL scheme '{parsed.scheme}'. Use HTTPS for secure webhook delivery."
            )

        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or WebhookRetryPolicy.default()
        self.signer = WebhookSigner(secret)

        # Initialize circuit breaker
        cb_config = circuit_breaker_config or {}
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=cb_config.get("failure_threshold", 5),
            reset_timeout_seconds=cb_config.get("reset_timeout_seconds", 30),
            half_open_requests=cb_config.get("half_open_requests", 3),
            success_threshold=cb_config.get("success_threshold", 2),
        )

        # Statistics
        self._stats_lock = threading.Lock()
        self._total_deliveries = 0
        self._successful_deliveries = 0
        self._failed_deliveries = 0
        self._total_retries = 0

    def deliver(self, payload: dict[str, Any]) -> WebhookDeliveryResult:
        """Deliver webhook payload to endpoint.

        Serializes payload to JSON, signs it, and delivers with retry logic.

        Args:
            payload: Dict to serialize as JSON webhook body

        Returns:
            WebhookDeliveryResult with delivery outcome
        """
        # Check circuit breaker first
        if not self.circuit_breaker.can_execute():
            with self._stats_lock:
                self._total_deliveries += 1
                self._failed_deliveries += 1

            return WebhookDeliveryResult(
                success=False,
                attempts=0,
                circuit_open=True,
                error_message="Circuit breaker is open",
                error_type="circuit_open",
            )

        # Serialize payload
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        # Attempt delivery with retries
        return self._deliver_with_retry(body)

    def _deliver_with_retry(self, body: bytes) -> WebhookDeliveryResult:
        """Deliver with retry logic.

        Args:
            body: Serialized JSON payload bytes

        Returns:
            Delivery result
        """
        last_error: Exception | None = None
        last_status_code: int | None = None
        last_error_type: str | None = None
        delay_ms: float = float(self.retry_policy.initial_delay_ms)
        attempts = 0

        max_attempts = self.retry_policy.max_retries + 1  # Initial + retries

        for attempt in range(max_attempts):
            attempts += 1

            try:
                result = self._send_request(body)

                # Success
                self.circuit_breaker.record_success()
                with self._stats_lock:
                    self._total_deliveries += 1
                    self._successful_deliveries += 1
                    self._total_retries += attempt  # Retries used (not counting initial)

                return WebhookDeliveryResult(
                    success=True,
                    status_code=result.get("status_code", 200),
                    attempts=attempts,
                    response_body=result.get("body"),
                )

            except urllib.error.HTTPError as e:
                last_status_code = e.code
                last_error = e
                last_error_type = "http_error"

                # Check if this status code should be retried
                should_retry = e.code in self.retry_policy.retry_on_status
                if not should_retry or attempt >= max_attempts - 1:
                    # Non-retryable or max retries reached
                    self.circuit_breaker.record_failure()
                    break

                # Wait before retry with exponential backoff and jitter
                self._wait_with_backoff(delay_ms)
                delay_ms = min(
                    delay_ms * self.retry_policy.backoff_multiplier,
                    self.retry_policy.max_delay_ms,
                )

            except TimeoutError as e:
                last_error = e
                last_error_type = "timeout"

                if attempt >= max_attempts - 1:
                    self.circuit_breaker.record_failure()
                    break

                self._wait_with_backoff(delay_ms)
                delay_ms = min(
                    delay_ms * self.retry_policy.backoff_multiplier,
                    self.retry_policy.max_delay_ms,
                )

            except urllib.error.URLError as e:
                last_error = e
                last_error_type = "connection_error"

                if attempt >= max_attempts - 1:
                    self.circuit_breaker.record_failure()
                    break

                self._wait_with_backoff(delay_ms)
                delay_ms = min(
                    delay_ms * self.retry_policy.backoff_multiplier,
                    self.retry_policy.max_delay_ms,
                )

            except Exception as e:
                last_error = e
                last_error_type = "unknown_error"

                if attempt >= max_attempts - 1:
                    self.circuit_breaker.record_failure()
                    break

                self._wait_with_backoff(delay_ms)
                delay_ms = min(
                    delay_ms * self.retry_policy.backoff_multiplier,
                    self.retry_policy.max_delay_ms,
                )

        # All attempts failed
        with self._stats_lock:
            self._total_deliveries += 1
            self._failed_deliveries += 1
            self._total_retries += attempts - 1  # Exclude initial attempt

        return WebhookDeliveryResult(
            success=False,
            status_code=last_status_code,
            attempts=attempts,
            error_message=str(last_error) if last_error else "Unknown error",
            error_type=last_error_type,
        )

    def _wait_with_backoff(self, delay_ms: float) -> None:
        """Wait with jitter applied.

        Args:
            delay_ms: Base delay in milliseconds
        """
        # S311: Using non-crypto random is intentional for jitter timing
        jitter = random.uniform(  # noqa: S311
            -self.retry_policy.jitter_factor,
            self.retry_policy.jitter_factor,
        )
        actual_delay = delay_ms * (1 + jitter)
        time.sleep(actual_delay / 1000.0)

    def _send_request(self, body: bytes) -> _ResponseDict:
        """Send HTTP request with signed payload.

        Args:
            body: Serialized JSON payload

        Returns:
            Response dict with status_code and body

        Raises:
            urllib.error.HTTPError: For HTTP errors
            urllib.error.URLError: For connection errors
            socket.timeout: For timeout errors
        """
        # Get signature headers
        headers = self.signer.get_signature_headers(body)

        # Add standard headers
        headers["Content-Type"] = self.CONTENT_TYPE
        headers["User-Agent"] = self.USER_AGENT

        # Create request - S310: URL scheme validated in __init__
        request = urllib.request.Request(  # noqa: S310
            self.endpoint,
            data=body,
            headers=headers,
            method="POST",
        )

        # Send request - S310: URL scheme validated in __init__
        # Allow skipping SSL verification for testing with self-signed certs
        ssl_context = None
        if os.environ.get("RAXE_SKIP_SSL_VERIFY", "").lower() == "true":
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(  # noqa: S310
            request, timeout=self.timeout_seconds, context=ssl_context
        ) as response:
            response_body = response.read().decode("utf-8")
            return {
                "status_code": response.code,
                "body": response_body,
            }

    def get_circuit_state(self) -> str:
        """Get current circuit breaker state.

        Returns:
            State string: "closed", "open", or "half_open"
        """
        return self.circuit_breaker.get_state()

    def get_stats(self) -> dict[str, Any]:
        """Get delivery statistics.

        Returns:
            Dict with delivery metrics
        """
        with self._stats_lock:
            return {
                "total_deliveries": self._total_deliveries,
                "successful_deliveries": self._successful_deliveries,
                "failed_deliveries": self._failed_deliveries,
                "total_retries": self._total_retries,
                "circuit_state": self.get_circuit_state(),
            }
