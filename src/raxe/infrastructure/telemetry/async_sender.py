"""Asynchronous telemetry sender using httpx.

This module provides async batch sending for telemetry events with:
- Async HTTP requests using httpx
- Circuit breaker pattern
- Exponential backoff with jitter
- Gzip compression
- Connection pooling
"""
import asyncio
import gzip
import json
import random
from datetime import datetime, timezone
from typing import Any

import httpx

from raxe.infrastructure.telemetry.sender import CircuitBreaker, RetryPolicy
from raxe.utils.logging import get_logger

logger = get_logger(__name__)


class AsyncBatchSender:
    """Asynchronous batch sender for telemetry events.

    Features:
    - Async HTTP using httpx for better performance
    - Connection pooling (reuses connections)
    - Circuit breaker pattern
    - Exponential backoff with jitter
    - Gzip compression
    - Configurable retry policy
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        compression: str = "gzip",
        timeout_seconds: int = 30,
        max_connections: int = 10,
        max_keepalive_connections: int = 5,
    ):
        """Initialize async batch sender.

        Args:
            endpoint: Telemetry endpoint URL
            api_key: API key for authentication
            circuit_breaker: Circuit breaker instance
            retry_policy: Retry policy configuration
            compression: Compression type ("none", "gzip")
            timeout_seconds: Request timeout
            max_connections: Maximum number of connections
            max_keepalive_connections: Maximum keepalive connections
        """
        self.endpoint = endpoint
        self.api_key = api_key
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.retry_policy = retry_policy or RetryPolicy()
        self.compression = compression
        self.timeout_seconds = timeout_seconds

        # HTTP client configuration
        self._client: httpx.AsyncClient | None = None
        self._max_connections = max_connections
        self._max_keepalive_connections = max_keepalive_connections

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized.

        Returns:
            Initialized httpx.AsyncClient
        """
        if self._client is None:
            # Configure connection limits for efficient pooling
            limits = httpx.Limits(
                max_connections=self._max_connections,
                max_keepalive_connections=self._max_keepalive_connections,
            )

            # Configure timeout
            timeout = httpx.Timeout(self.timeout_seconds)

            # Create client with connection pooling
            self._client = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
                http2=False,  # HTTP/2 disabled (requires h2 package)
            )

        return self._client

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def send_batch(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """Send a batch of events to telemetry endpoint.

        Args:
            events: List of event dictionaries

        Returns:
            Response from server

        Raises:
            Exception: If sending fails after all retries
        """
        if not events:
            return {"status": "ok", "message": "No events to send"}

        # Prepare payload
        payload = {
            "events": events,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "batch_size": len(events),
        }

        # Execute through circuit breaker (sync wrapper for async)
        return await self._send_with_circuit_breaker(payload)

    async def _send_with_circuit_breaker(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send with circuit breaker protection.

        Args:
            payload: Data to send

        Returns:
            Server response

        Raises:
            Exception: If circuit is open or sending fails
        """
        # Check circuit state before attempting
        circuit_state = self.circuit_breaker.get_state()
        if circuit_state.value == "open":
            # Circuit is open, attempt reset if timeout expired
            if self.circuit_breaker._should_attempt_reset():
                logger.info("circuit_breaker_attempting_reset")
            else:
                raise Exception(
                    f"Circuit breaker is OPEN (will retry after "
                    f"{self.circuit_breaker.config.reset_timeout_seconds}s)"
                )

        # Attempt send with retry
        try:
            result = await self._send_with_retry(payload)
            self.circuit_breaker._on_success()
            return result
        except Exception:
            self.circuit_breaker._on_failure()
            raise

    async def _send_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send payload with retry logic.

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
                return await self._send_request(payload)

            except httpx.HTTPStatusError as e:
                # Check if status code is retryable
                if e.response.status_code not in self.retry_policy.retry_on_status:
                    # Non-retryable error
                    logger.error(
                        "http_error_non_retryable",
                        status_code=e.response.status_code,
                        error=str(e),
                    )
                    raise

                last_error = e
                if attempt < self.retry_policy.max_retries:
                    # Calculate delay with exponential backoff and jitter
                    jitter = random.uniform(
                        -self.retry_policy.jitter_factor, self.retry_policy.jitter_factor
                    )
                    actual_delay = delay_ms * (1 + jitter)
                    actual_delay = min(actual_delay, self.retry_policy.max_delay_ms)

                    logger.warning(
                        "http_error_retrying",
                        status_code=e.response.status_code,
                        attempt=attempt + 1,
                        max_retries=self.retry_policy.max_retries,
                        delay_ms=int(actual_delay),
                    )

                    await asyncio.sleep(actual_delay / 1000.0)
                    delay_ms *= self.retry_policy.backoff_multiplier

            except Exception as e:
                last_error = e
                if attempt < self.retry_policy.max_retries:
                    # Network or other error, retry with backoff
                    actual_delay = delay_ms * (1 + random.uniform(
                        -self.retry_policy.jitter_factor, self.retry_policy.jitter_factor
                    ))
                    actual_delay = min(actual_delay, self.retry_policy.max_delay_ms)

                    logger.warning(
                        "request_error_retrying",
                        error=str(e),
                        attempt=attempt + 1,
                        max_retries=self.retry_policy.max_retries,
                        delay_ms=int(actual_delay),
                    )

                    await asyncio.sleep(actual_delay / 1000.0)
                    delay_ms *= self.retry_policy.backoff_multiplier

        # All retries exhausted
        raise Exception(
            f"Failed to send batch after {self.retry_policy.max_retries} retries: {last_error}"
        )

    async def _send_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send HTTP request with payload.

        Args:
            payload: Data to send

        Returns:
            Server response

        Raises:
            Exception: If request fails
        """
        # Ensure client is initialized
        client = await self._ensure_client()

        # Serialize payload
        json_data = json.dumps(payload).encode("utf-8")

        # Compress if enabled
        if self.compression == "gzip":
            json_data = gzip.compress(json_data)
            content_encoding = "gzip"
        else:
            content_encoding = None

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "RAXE-CE/1.0",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        if content_encoding:
            headers["Content-Encoding"] = content_encoding

        # Send request
        try:
            response = await client.post(
                self.endpoint, content=json_data, headers=headers
            )

            # Raise for HTTP errors
            response.raise_for_status()

            # Parse response
            if response.content:
                return response.json()
            return {"status": "ok", "code": response.status_code}

        except httpx.HTTPStatusError as e:
            # Read error response if available
            error_body = None
            try:
                error_body = e.response.text
            except Exception:
                pass

            logger.error(
                "http_error",
                status_code=e.response.status_code,
                error_body=error_body or str(e),
            )
            raise

        except httpx.RequestError as e:
            logger.error("request_error", error=str(e))
            raise

        except Exception as e:
            logger.error("unexpected_error", error=str(e))
            raise

    def get_circuit_state(self) -> str:
        """Get current circuit breaker state.

        Returns:
            Circuit state as string
        """
        return self.circuit_breaker.get_state().value

    async def send_analytics_event(
        self,
        event_type: str,
        installation_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send analytics event to telemetry endpoint.

        Args:
            event_type: Type of analytics event
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
            "metadata": metadata or {},
        }

        return await self.send_batch([event])


def run_async_send(sender: AsyncBatchSender, events: list[dict[str, Any]]) -> dict[str, Any]:
    """Run async send operation in sync context.

    Helper function to run async sender from synchronous code.
    Uses asyncio.run() which properly manages event loop lifecycle.

    Args:
        sender: AsyncBatchSender instance
        events: Events to send

    Returns:
        Server response
    """
    async def _send_with_cleanup():
        """Send with proper context manager and cleanup."""
        async with sender:
            return await sender.send_batch(events)

    # Use asyncio.run() which properly handles cleanup and shutdown
    # This prevents "Future exception was never retrieved" errors
    return asyncio.run(_send_with_cleanup())
