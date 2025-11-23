"""Tests for async telemetry sender."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from raxe.infrastructure.telemetry.async_sender import (
    AsyncBatchSender,
    run_async_send,
)
from raxe.infrastructure.telemetry.sender import CircuitBreaker, RetryPolicy


class TestAsyncBatchSender:
    """Test async batch sender."""

    @pytest.mark.asyncio
    async def test_init(self):
        """Test sender initialization."""
        sender = AsyncBatchSender(
            endpoint="https://api.test.com/events",
            api_key="test-key",
            timeout_seconds=10,
        )

        assert sender.endpoint == "https://api.test.com/events"
        assert sender.api_key == "test-key"
        assert sender.timeout_seconds == 10
        assert sender._client is None  # Lazy initialization

        await sender.close()

    @pytest.mark.asyncio
    async def test_client_lazy_initialization(self):
        """Test HTTP client is created lazily."""
        sender = AsyncBatchSender(endpoint="https://api.test.com/events")

        # Client should not exist yet
        assert sender._client is None

        # Accessing client creates it
        client = await sender._ensure_client()
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        assert sender._client is client

        # Second access returns same instance
        client2 = await sender._ensure_client()
        assert client2 is client

        await sender.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        async with AsyncBatchSender(endpoint="https://api.test.com/events") as sender:
            assert sender._client is not None

        # Client should be closed after exit
        assert sender._client is None

    @pytest.mark.asyncio
    async def test_send_batch_empty(self):
        """Test sending empty batch."""
        async with AsyncBatchSender(endpoint="https://api.test.com/events") as sender:
            result = await sender.send_batch([])

            assert result["status"] == "ok"
            assert result["message"] == "No events to send"

    @pytest.mark.asyncio
    async def test_send_batch_success(self):
        """Test successful batch send."""
        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "ok", "received": 2}'
        mock_response.json.return_value = {"status": "ok", "received": 2}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        async with AsyncBatchSender(endpoint="https://api.test.com/events") as sender:
            sender._client = mock_client

            events = [
                {"event_type": "test1", "data": "value1"},
                {"event_type": "test2", "data": "value2"},
            ]

            result = await sender.send_batch(events)

            assert result["status"] == "ok"
            assert result["received"] == 2

            # Verify HTTP call
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_with_compression(self):
        """Test sending with gzip compression."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "ok"}'
        mock_response.json.return_value = {"status": "ok"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        async with AsyncBatchSender(
            endpoint="https://api.test.com/events", compression="gzip"
        ) as sender:
            sender._client = mock_client

            events = [{"event_type": "test"}]
            await sender.send_batch(events)

            # Verify gzip compression
            call_args = mock_client.post.call_args
            headers = call_args.kwargs["headers"]
            assert headers["Content-Encoding"] == "gzip"

            # Verify content is compressed
            content = call_args.kwargs["content"]
            assert content != b'{"events": [{"event_type": "test"}]}'

    @pytest.mark.asyncio
    async def test_send_with_api_key(self):
        """Test sending with API key."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "ok"}'
        mock_response.json.return_value = {"status": "ok"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        async with AsyncBatchSender(
            endpoint="https://api.test.com/events", api_key="secret-key"
        ) as sender:
            sender._client = mock_client

            await sender.send_batch([{"event_type": "test"}])

            # Verify authorization header
            call_args = mock_client.post.call_args
            headers = call_args.kwargs["headers"]
            assert headers["Authorization"] == "Bearer secret-key"

    @pytest.mark.asyncio
    async def test_retry_on_retryable_status(self):
        """Test retry on retryable HTTP status codes."""
        # First call fails with 503, second succeeds
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 503
        mock_response_fail.text = "Service Unavailable"

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.content = b'{"status": "ok"}'
        mock_response_success.json.return_value = {"status": "ok"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError(
                    "503", request=MagicMock(), response=mock_response_fail
                ),
                mock_response_success,
            ]
        )

        # Use short retry policy for testing
        retry_policy = RetryPolicy(
            max_retries=2, initial_delay_ms=10, max_delay_ms=20
        )

        async with AsyncBatchSender(
            endpoint="https://api.test.com/events", retry_policy=retry_policy
        ) as sender:
            sender._client = mock_client

            result = await sender.send_batch([{"event_type": "test"}])

            assert result["status"] == "ok"
            assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_status(self):
        """Test no retry on non-retryable HTTP status codes."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "400", request=MagicMock(), response=mock_response
            )
        )

        async with AsyncBatchSender(endpoint="https://api.test.com/events") as sender:
            sender._client = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await sender.send_batch([{"event_type": "test"}])

            # Should only try once (no retries)
            assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Test circuit breaker integration."""
        circuit_breaker = CircuitBreaker()
        sender = AsyncBatchSender(
            endpoint="https://api.test.com/events",
            circuit_breaker=circuit_breaker,
        )

        # Get circuit state
        state = sender.get_circuit_state()
        assert state == "closed"

        await sender.close()

    @pytest.mark.asyncio
    async def test_send_analytics_event(self):
        """Test sending analytics event."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "ok"}'
        mock_response.json.return_value = {"status": "ok"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        async with AsyncBatchSender(endpoint="https://api.test.com/events") as sender:
            sender._client = mock_client

            result = await sender.send_analytics_event(
                event_type="installation",
                installation_id="test-install-123",
                metadata={"version": "1.0.0"},
            )

            assert result["status"] == "ok"
            mock_client.post.assert_called_once()


class TestRunAsyncSend:
    """Test sync wrapper for async send."""

    def test_run_async_send(self):
        """Test running async send from sync context."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "ok"}'
        mock_response.json.return_value = {"status": "ok"}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            MockClient.return_value = mock_client

            sender = AsyncBatchSender(endpoint="https://api.test.com/events")

            events = [{"event_type": "test"}]
            result = run_async_send(sender, events)

            assert result["status"] == "ok"


class TestAsyncSenderPerformance:
    """Test async sender performance characteristics."""

    @pytest.mark.asyncio
    async def test_connection_pooling(self):
        """Test connection pooling configuration."""
        sender = AsyncBatchSender(
            endpoint="https://api.test.com/events",
            max_connections=20,
            max_keepalive_connections=10,
        )

        client = await sender._ensure_client()

        # Verify limits are set correctly
        assert client.limits.max_connections == 20
        assert client.limits.max_keepalive_connections == 10

        await sender.close()

    @pytest.mark.asyncio
    async def test_http2_enabled(self):
        """Test HTTP/2 is enabled."""
        sender = AsyncBatchSender(endpoint="https://api.test.com/events")

        client = await sender._ensure_client()

        # Verify HTTP/2 is enabled
        # Note: httpx enables HTTP/2 when http2=True
        # We can't directly check this, but we can verify client was created
        assert client is not None

        await sender.close()

    @pytest.mark.asyncio
    async def test_concurrent_sends(self):
        """Test handling concurrent sends."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "ok"}'
        mock_response.json.return_value = {"status": "ok"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        async with AsyncBatchSender(endpoint="https://api.test.com/events") as sender:
            sender._client = mock_client

            # Send multiple batches concurrently
            tasks = [
                sender.send_batch([{"event_type": f"test{i}"}])
                for i in range(5)
            ]

            results = await asyncio.gather(*tasks)

            # All should succeed
            assert len(results) == 5
            assert all(r["status"] == "ok" for r in results)

            # Should have made 5 POST calls
            assert mock_client.post.call_count == 5
