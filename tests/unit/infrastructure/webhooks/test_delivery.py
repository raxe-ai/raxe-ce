"""
Tests for webhook HTTP delivery infrastructure.

These tests verify:
- Successful webhook delivery with proper headers
- Retry logic for 5xx server errors
- No retry for 4xx client errors
- Circuit breaker pattern integration
- Signature and timestamp headers are included
- Timeout handling
- Exponential backoff behavior
"""

import urllib.error
from unittest.mock import MagicMock, patch

import pytest

# Import paths for the module under test (will fail until implemented)
try:
    from raxe.infrastructure.webhooks.delivery import (
        WebhookDeliveryError,
        WebhookDeliveryResult,
        WebhookDeliveryService,
        WebhookRetryPolicy,
    )

    WEBHOOK_MODULE_AVAILABLE = True
except ImportError:
    WEBHOOK_MODULE_AVAILABLE = False
    WebhookDeliveryError = None
    WebhookDeliveryResult = None
    WebhookDeliveryService = None
    WebhookRetryPolicy = None

# Skip all tests if module not implemented yet
pytestmark = pytest.mark.skipif(
    not WEBHOOK_MODULE_AVAILABLE,
    reason="Webhook delivery module not implemented yet",
)


class TestWebhookDeliverySuccess:
    """Tests for successful webhook delivery."""

    def test_successful_delivery(
        self,
        webhook_config,
        sample_webhook_payload: dict,
        mock_urlopen_success,
    ):
        """Test successful webhook delivery returns success result."""
        service = WebhookDeliveryService(
            endpoint=webhook_config.endpoint,
            secret=webhook_config.secret,
            timeout_seconds=webhook_config.timeout_seconds,
        )

        result = service.deliver(sample_webhook_payload)

        assert result.success is True
        assert result.status_code == 200
        assert result.attempts == 1
        mock_urlopen_success.assert_called_once()

    def test_signature_header_included(
        self,
        webhook_config,
        sample_webhook_payload: dict,
        mock_urlopen_success,
    ):
        """Test that X-RAXE-Signature header is included in request."""
        service = WebhookDeliveryService(
            endpoint=webhook_config.endpoint,
            secret=webhook_config.secret,
        )

        service.deliver(sample_webhook_payload)

        # Get the Request object passed to urlopen
        call_args = mock_urlopen_success.call_args
        request = call_args[0][0]

        # Verify signature header exists and has correct format
        signature_header = request.get_header("X-raxe-signature")
        assert signature_header is not None, "X-RAXE-Signature header must be present"
        assert signature_header.startswith("sha256="), "Signature must start with sha256="

    def test_timestamp_header_included(
        self,
        webhook_config,
        sample_webhook_payload: dict,
        mock_urlopen_success,
    ):
        """Test that X-RAXE-Timestamp header is included in request."""
        service = WebhookDeliveryService(
            endpoint=webhook_config.endpoint,
            secret=webhook_config.secret,
        )

        service.deliver(sample_webhook_payload)

        # Get the Request object passed to urlopen
        call_args = mock_urlopen_success.call_args
        request = call_args[0][0]

        # Verify timestamp header exists and is numeric
        timestamp_header = request.get_header("X-raxe-timestamp")
        assert timestamp_header is not None, "X-RAXE-Timestamp header must be present"
        assert timestamp_header.isdigit(), "Timestamp must be numeric"

    def test_content_type_json(
        self,
        webhook_config,
        sample_webhook_payload: dict,
        mock_urlopen_success,
    ):
        """Test that Content-Type is set to application/json."""
        service = WebhookDeliveryService(
            endpoint=webhook_config.endpoint,
            secret=webhook_config.secret,
        )

        service.deliver(sample_webhook_payload)

        call_args = mock_urlopen_success.call_args
        request = call_args[0][0]

        content_type = request.get_header("Content-type")
        assert content_type == "application/json"

    def test_user_agent_header(
        self,
        webhook_config,
        sample_webhook_payload: dict,
        mock_urlopen_success,
    ):
        """Test that User-Agent header identifies RAXE."""
        service = WebhookDeliveryService(
            endpoint=webhook_config.endpoint,
            secret=webhook_config.secret,
        )

        service.deliver(sample_webhook_payload)

        call_args = mock_urlopen_success.call_args
        request = call_args[0][0]

        user_agent = request.get_header("User-agent")
        assert user_agent is not None
        assert "RAXE" in user_agent


class TestWebhookDeliveryRetry:
    """Tests for webhook delivery retry logic."""

    def test_retry_on_500_error(
        self,
        webhook_config,
        sample_webhook_payload: dict,
    ):
        """Test that 500 errors trigger retries."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            # Fail twice with 500, then succeed
            mock_success = MagicMock()
            mock_success.read.return_value = b'{"status": "ok"}'
            mock_success.code = 200
            mock_success.__enter__ = lambda s: s
            mock_success.__exit__ = lambda s, *args: None

            mock_urlopen.side_effect = [
                urllib.error.HTTPError(None, 500, "Internal Server Error", {}, None),
                urllib.error.HTTPError(None, 500, "Internal Server Error", {}, None),
                mock_success,
            ]

            retry_policy = WebhookRetryPolicy(
                max_retries=3,
                initial_delay_ms=10,  # Short for testing
                max_delay_ms=100,
            )

            service = WebhookDeliveryService(
                endpoint=webhook_config.endpoint,
                secret=webhook_config.secret,
                retry_policy=retry_policy,
            )

            result = service.deliver(sample_webhook_payload)

            assert result.success is True
            assert result.attempts == 3
            assert mock_urlopen.call_count == 3

    def test_retry_on_502_503_504_errors(
        self,
        webhook_config,
        sample_webhook_payload: dict,
    ):
        """Test that 502, 503, 504 errors trigger retries."""
        for error_code in [502, 503, 504]:
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_success = MagicMock()
                mock_success.read.return_value = b'{"status": "ok"}'
                mock_success.code = 200
                mock_success.__enter__ = lambda s: s
                mock_success.__exit__ = lambda s, *args: None

                mock_urlopen.side_effect = [
                    urllib.error.HTTPError(None, error_code, f"Error {error_code}", {}, None),
                    mock_success,
                ]

                retry_policy = WebhookRetryPolicy(
                    max_retries=2,
                    initial_delay_ms=10,
                )

                service = WebhookDeliveryService(
                    endpoint=webhook_config.endpoint,
                    secret=webhook_config.secret,
                    retry_policy=retry_policy,
                )

                result = service.deliver(sample_webhook_payload)

                assert result.success is True, f"Should succeed after retry for {error_code}"
                assert mock_urlopen.call_count == 2

    def test_no_retry_on_400_error(
        self,
        webhook_config,
        sample_webhook_payload: dict,
        mock_urlopen_bad_request,
    ):
        """Test that 400 errors do NOT trigger retries (client error)."""
        retry_policy = WebhookRetryPolicy(
            max_retries=3,
            initial_delay_ms=10,
        )

        service = WebhookDeliveryService(
            endpoint=webhook_config.endpoint,
            secret=webhook_config.secret,
            retry_policy=retry_policy,
        )

        result = service.deliver(sample_webhook_payload)

        assert result.success is False
        assert result.status_code == 400
        assert result.attempts == 1  # No retries
        mock_urlopen_bad_request.assert_called_once()

    def test_no_retry_on_401_403_404_errors(
        self,
        webhook_config,
        sample_webhook_payload: dict,
    ):
        """Test that 401, 403, 404 errors do NOT trigger retries."""
        for error_code in [401, 403, 404]:
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_urlopen.side_effect = urllib.error.HTTPError(
                    None, error_code, f"Error {error_code}", {}, None
                )

                retry_policy = WebhookRetryPolicy(
                    max_retries=3,
                    initial_delay_ms=10,
                )

                service = WebhookDeliveryService(
                    endpoint=webhook_config.endpoint,
                    secret=webhook_config.secret,
                    retry_policy=retry_policy,
                )

                result = service.deliver(sample_webhook_payload)

                assert result.success is False
                assert result.attempts == 1, f"Should not retry for {error_code}"

    def test_max_retries_exhausted(
        self,
        webhook_config,
        sample_webhook_payload: dict,
    ):
        """Test that delivery fails after max retries exhausted."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                None, 500, "Internal Server Error", {}, None
            )

            retry_policy = WebhookRetryPolicy(
                max_retries=3,
                initial_delay_ms=10,
                max_delay_ms=50,
            )

            service = WebhookDeliveryService(
                endpoint=webhook_config.endpoint,
                secret=webhook_config.secret,
                retry_policy=retry_policy,
            )

            result = service.deliver(sample_webhook_payload)

            assert result.success is False
            assert result.status_code == 500
            assert result.attempts == 4  # Initial + 3 retries
            assert mock_urlopen.call_count == 4


class TestWebhookDeliveryCircuitBreaker:
    """Tests for circuit breaker integration."""

    def test_circuit_breaker_opens_on_failures(
        self,
        webhook_config,
        sample_webhook_payload: dict,
        circuit_breaker_test_config,
    ):
        """Test that circuit breaker opens after consecutive failures."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                None, 500, "Internal Server Error", {}, None
            )

            # Use no-retry policy to quickly trigger circuit breaker
            retry_policy = WebhookRetryPolicy(max_retries=0)

            service = WebhookDeliveryService(
                endpoint=webhook_config.endpoint,
                secret=webhook_config.secret,
                retry_policy=retry_policy,
                circuit_breaker_config=circuit_breaker_test_config,
            )

            # Make enough requests to open the circuit
            failure_threshold = circuit_breaker_test_config["failure_threshold"]
            for _ in range(failure_threshold):
                service.deliver(sample_webhook_payload)

            # Circuit should now be open
            assert service.get_circuit_state() == "open"

            # Next delivery should fail immediately without making HTTP request
            mock_urlopen.reset_mock()
            result = service.deliver(sample_webhook_payload)

            assert result.success is False
            assert result.circuit_open is True
            mock_urlopen.assert_not_called()

    def test_circuit_breaker_recovers(
        self,
        webhook_config,
        sample_webhook_payload: dict,
        circuit_breaker_test_config,
    ):
        """Test that circuit breaker recovers after timeout."""
        import time

        with patch("urllib.request.urlopen") as mock_urlopen:
            # First, cause failures to open the circuit
            mock_urlopen.side_effect = urllib.error.HTTPError(
                None, 500, "Internal Server Error", {}, None
            )

            retry_policy = WebhookRetryPolicy(max_retries=0)
            service = WebhookDeliveryService(
                endpoint=webhook_config.endpoint,
                secret=webhook_config.secret,
                retry_policy=retry_policy,
                circuit_breaker_config=circuit_breaker_test_config,
            )

            # Open the circuit
            failure_threshold = circuit_breaker_test_config["failure_threshold"]
            for _ in range(failure_threshold):
                service.deliver(sample_webhook_payload)

            assert service.get_circuit_state() == "open"

            # Wait for reset timeout
            time.sleep(circuit_breaker_test_config["reset_timeout_seconds"] + 0.1)

            # Now make the endpoint succeed
            mock_success = MagicMock()
            mock_success.read.return_value = b'{"status": "ok"}'
            mock_success.code = 200
            mock_success.__enter__ = lambda s: s
            mock_success.__exit__ = lambda s, *args: None
            mock_urlopen.side_effect = None
            mock_urlopen.return_value = mock_success

            # Circuit should transition to half-open and allow request
            result = service.deliver(sample_webhook_payload)

            assert result.success is True


class TestWebhookDeliveryTimeout:
    """Tests for timeout handling."""

    def test_timeout_handling(
        self,
        webhook_config,
        sample_webhook_payload: dict,
        mock_urlopen_timeout,
    ):
        """Test that timeout errors are handled gracefully."""
        retry_policy = WebhookRetryPolicy(max_retries=0)  # No retries for this test

        service = WebhookDeliveryService(
            endpoint=webhook_config.endpoint,
            secret=webhook_config.secret,
            timeout_seconds=1,
            retry_policy=retry_policy,
        )

        result = service.deliver(sample_webhook_payload)

        assert result.success is False
        assert result.error_type == "timeout"

    def test_timeout_triggers_retry(
        self,
        webhook_config,
        sample_webhook_payload: dict,
    ):
        """Test that timeout errors trigger retry."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_success = MagicMock()
            mock_success.read.return_value = b'{"status": "ok"}'
            mock_success.code = 200
            mock_success.__enter__ = lambda s: s
            mock_success.__exit__ = lambda s, *args: None

            mock_urlopen.side_effect = [
                TimeoutError("Connection timed out"),
                mock_success,
            ]

            retry_policy = WebhookRetryPolicy(
                max_retries=2,
                initial_delay_ms=10,
            )

            service = WebhookDeliveryService(
                endpoint=webhook_config.endpoint,
                secret=webhook_config.secret,
                retry_policy=retry_policy,
            )

            result = service.deliver(sample_webhook_payload)

            assert result.success is True
            assert result.attempts == 2

    def test_connection_error_triggers_retry(
        self,
        webhook_config,
        sample_webhook_payload: dict,
    ):
        """Test that connection errors trigger retry."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_success = MagicMock()
            mock_success.read.return_value = b'{"status": "ok"}'
            mock_success.code = 200
            mock_success.__enter__ = lambda s: s
            mock_success.__exit__ = lambda s, *args: None

            mock_urlopen.side_effect = [
                urllib.error.URLError("Connection refused"),
                mock_success,
            ]

            retry_policy = WebhookRetryPolicy(
                max_retries=2,
                initial_delay_ms=10,
            )

            service = WebhookDeliveryService(
                endpoint=webhook_config.endpoint,
                secret=webhook_config.secret,
                retry_policy=retry_policy,
            )

            result = service.deliver(sample_webhook_payload)

            assert result.success is True
            assert result.attempts == 2


class TestWebhookRetryPolicy:
    """Tests for WebhookRetryPolicy configuration."""

    def test_default_retry_policy(self):
        """Test default retry policy values."""
        policy = WebhookRetryPolicy()

        assert policy.max_retries >= 0
        assert policy.initial_delay_ms > 0
        assert policy.max_delay_ms >= policy.initial_delay_ms
        assert policy.backoff_multiplier >= 1.0

    def test_no_retry_policy(self):
        """Test creating a no-retry policy."""
        policy = WebhookRetryPolicy.no_retry()

        assert policy.max_retries == 0

    def test_retry_on_status_codes(self):
        """Test that retry_on_status specifies which codes trigger retry."""
        policy = WebhookRetryPolicy()

        # 5xx errors should retry by default
        assert 500 in policy.retry_on_status
        assert 502 in policy.retry_on_status
        assert 503 in policy.retry_on_status
        assert 504 in policy.retry_on_status

        # 4xx errors should NOT retry by default
        assert 400 not in policy.retry_on_status
        assert 401 not in policy.retry_on_status
        assert 403 not in policy.retry_on_status
        assert 404 not in policy.retry_on_status


class TestWebhookDeliveryResult:
    """Tests for WebhookDeliveryResult dataclass."""

    def test_result_success_attributes(self):
        """Test success result has expected attributes."""
        result = WebhookDeliveryResult(
            success=True,
            status_code=200,
            attempts=1,
            response_body='{"status": "ok"}',
        )

        assert result.success is True
        assert result.status_code == 200
        assert result.attempts == 1
        assert result.response_body == '{"status": "ok"}'

    def test_result_failure_attributes(self):
        """Test failure result has expected attributes."""
        result = WebhookDeliveryResult(
            success=False,
            status_code=500,
            attempts=4,
            error_message="Internal Server Error",
            error_type="http_error",
        )

        assert result.success is False
        assert result.status_code == 500
        assert result.attempts == 4
        assert result.error_message == "Internal Server Error"
        assert result.error_type == "http_error"

    def test_result_circuit_open_flag(self):
        """Test circuit open flag in result."""
        result = WebhookDeliveryResult(
            success=False,
            attempts=0,
            circuit_open=True,
            error_message="Circuit breaker is open",
        )

        assert result.circuit_open is True
        assert result.attempts == 0


class TestWebhookDeliveryService:
    """Tests for WebhookDeliveryService configuration."""

    def test_service_requires_https_in_production(self):
        """Test that service requires HTTPS for non-localhost endpoints."""
        with pytest.raises(ValueError, match="[Hh][Tt][Tt][Pp][Ss]|[Ss]ecure"):
            WebhookDeliveryService(
                endpoint="http://mssp.example.com/webhooks",  # HTTP, not HTTPS
                secret="test_secret",
            )

    def test_service_allows_http_localhost(self):
        """Test that service allows HTTP for localhost (development)."""
        # Should not raise
        service = WebhookDeliveryService(
            endpoint="http://localhost:8080/webhooks",
            secret="test_secret",
        )
        assert service is not None

    def test_service_validates_endpoint_url(self):
        """Test that service validates endpoint URL format."""
        with pytest.raises(ValueError, match="[Uu][Rr][Ll]|[Ee]ndpoint"):
            WebhookDeliveryService(
                endpoint="not-a-valid-url",
                secret="test_secret",
            )

    def test_service_requires_secret(self):
        """Test that service requires a non-empty secret."""
        with pytest.raises(ValueError, match="[Ss]ecret"):
            WebhookDeliveryService(
                endpoint="https://mssp.example.com/webhooks",
                secret="",  # Empty secret
            )

    def test_service_stats(
        self,
        webhook_config,
        sample_webhook_payload: dict,
        mock_urlopen_success,
    ):
        """Test that service tracks delivery statistics."""
        service = WebhookDeliveryService(
            endpoint=webhook_config.endpoint,
            secret=webhook_config.secret,
        )

        # Make a few deliveries
        for _ in range(3):
            service.deliver(sample_webhook_payload)

        stats = service.get_stats()

        assert stats["total_deliveries"] == 3
        assert stats["successful_deliveries"] == 3
        assert stats["failed_deliveries"] == 0
