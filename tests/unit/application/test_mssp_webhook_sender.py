"""Tests for MSSP Webhook Sender.

TDD: These tests define expected behavior for dual-send telemetry.
Implementation should make these tests pass.

The MSSPWebhookSender is responsible for:
1. Sending telemetry to MSSP webhooks when configured
2. Respecting data_mode (full vs privacy_safe)
3. Never blocking RAXE telemetry on MSSP webhook failures
4. Caching webhook services per MSSP for efficiency
"""

from unittest.mock import MagicMock, patch

import pytest


class TestMSSPWebhookSenderInit:
    """Tests for MSSPWebhookSender initialization."""

    def test_sender_initializes_without_mssp_config(self):
        """Sender should initialize even without MSSP configuration."""
        from raxe.application.mssp_webhook_sender import MSSPWebhookSender

        sender = MSSPWebhookSender()
        assert sender is not None

    def test_sender_lazy_loads_webhook_services(self):
        """Webhook services should be created lazily on first use."""
        from raxe.application.mssp_webhook_sender import MSSPWebhookSender

        sender = MSSPWebhookSender()
        # No webhook services should be created until send_if_configured is called
        assert len(sender._webhook_cache) == 0


class TestMSSPWebhookSenderSendLogic:
    """Tests for send_if_configured logic."""

    @pytest.fixture
    def mock_mssp_service(self, tmp_path, monkeypatch):
        """Create mock MSSP service with test data."""
        from raxe.domain.mssp.models import (
            MSSP,
            DataMode,
            MSSPCustomer,
            MSSPTier,
            WebhookConfig,
        )

        # Create test MSSP with webhook
        test_mssp = MSSP(
            mssp_id="mssp_test",
            name="Test MSSP",
            tier=MSSPTier.STARTER,
            max_customers=10,
            api_key_hash="hash123",
            webhook_config=WebhookConfig(
                url="https://test.mssp.com/webhook",
                secret="test_secret",
            ),
        )

        # Create test customer with full data mode
        test_customer_full = MSSPCustomer(
            customer_id="cust_full",
            mssp_id="mssp_test",
            name="Full Mode Customer",
            data_mode=DataMode.FULL,
            data_fields=["prompt", "matched_text"],
            retention_days=30,
            heartbeat_threshold_seconds=300,
        )

        # Create test customer with privacy_safe mode
        test_customer_safe = MSSPCustomer(
            customer_id="cust_safe",
            mssp_id="mssp_test",
            name="Privacy Safe Customer",
            data_mode=DataMode.PRIVACY_SAFE,
            data_fields=[],
            retention_days=30,
            heartbeat_threshold_seconds=300,
        )

        # Mock service
        mock_service = MagicMock()
        mock_service.get_mssp.return_value = test_mssp
        mock_service.get_customer.side_effect = lambda mssp_id, cust_id: (
            test_customer_full if cust_id == "cust_full" else test_customer_safe
        )

        return mock_service

    def test_send_skipped_when_no_mssp_id(self):
        """Send should be skipped gracefully when no mssp_id provided."""
        from raxe.application.mssp_webhook_sender import MSSPWebhookSender

        sender = MSSPWebhookSender()
        result = sender.send_if_configured(
            event_payload={"test": "data"},
            mssp_id=None,
            customer_id=None,
        )

        # Should return True (not an error, just not configured)
        assert result is True

    def test_send_skipped_when_no_customer_id(self):
        """Send should be skipped when no customer_id provided."""
        from raxe.application.mssp_webhook_sender import MSSPWebhookSender

        sender = MSSPWebhookSender()
        result = sender.send_if_configured(
            event_payload={"test": "data"},
            mssp_id="mssp_test",
            customer_id=None,
        )

        assert result is True

    def test_send_skipped_when_mssp_not_found(self, monkeypatch):
        """Send should handle MSSP not found gracefully."""
        from raxe.application.mssp_webhook_sender import MSSPWebhookSender
        from raxe.infrastructure.mssp.yaml_repository import MSSPNotFoundError

        # Mock service to raise not found
        mock_service = MagicMock()
        mock_service.get_mssp.side_effect = MSSPNotFoundError("mssp_unknown")

        sender = MSSPWebhookSender()
        sender._mssp_service = mock_service

        result = sender.send_if_configured(
            event_payload={"test": "data"},
            mssp_id="mssp_unknown",
            customer_id="cust_test",
        )

        # Should return True (graceful failure, don't block RAXE telemetry)
        assert result is True

    def test_send_skipped_when_no_webhook_configured(self, monkeypatch):
        """Send should be skipped when MSSP has no webhook configured."""
        from raxe.application.mssp_webhook_sender import MSSPWebhookSender
        from raxe.domain.mssp.models import (
            MSSP,
            DataMode,
            MSSPCustomer,
            MSSPTier,
        )

        # MSSP without webhook
        mssp_no_webhook = MSSP(
            mssp_id="mssp_no_webhook",
            name="No Webhook MSSP",
            tier=MSSPTier.STARTER,
            max_customers=10,
            api_key_hash="hash",
            webhook_config=None,  # No webhook!
        )

        customer = MSSPCustomer(
            customer_id="cust_test",
            mssp_id="mssp_no_webhook",
            name="Test",
            data_mode=DataMode.FULL,
            data_fields=[],
            retention_days=30,
            heartbeat_threshold_seconds=300,
            webhook_config=None,  # No customer override either
        )

        mock_service = MagicMock()
        mock_service.get_mssp.return_value = mssp_no_webhook
        mock_service.get_customer.return_value = customer

        sender = MSSPWebhookSender()
        sender._mssp_service = mock_service

        result = sender.send_if_configured(
            event_payload={"test": "data"},
            mssp_id="mssp_no_webhook",
            customer_id="cust_test",
        )

        assert result is True  # Not an error, just not configured


class TestMSSPWebhookSenderDataMode:
    """Tests for data mode handling (full vs privacy_safe)."""

    @pytest.fixture
    def sender_with_mock_service(self, tmp_path, monkeypatch):
        """Create sender with mocked MSSP service."""
        from raxe.application.mssp_webhook_sender import MSSPWebhookSender
        from raxe.domain.mssp.models import (
            MSSP,
            DataMode,
            MSSPCustomer,
            MSSPTier,
            WebhookConfig,
        )

        mssp = MSSP(
            mssp_id="mssp_test",
            name="Test MSSP",
            tier=MSSPTier.STARTER,
            max_customers=10,
            api_key_hash="hash",
            webhook_config=WebhookConfig(
                url="https://test.com/webhook",
                secret="secret",
            ),
        )

        def get_customer(mssp_id, customer_id):
            if customer_id == "cust_full":
                return MSSPCustomer(
                    customer_id="cust_full",
                    mssp_id="mssp_test",
                    name="Full",
                    data_mode=DataMode.FULL,
                    data_fields=["prompt", "matched_text"],
                    retention_days=30,
                    heartbeat_threshold_seconds=300,
                )
            else:
                return MSSPCustomer(
                    customer_id="cust_safe",
                    mssp_id="mssp_test",
                    name="Safe",
                    data_mode=DataMode.PRIVACY_SAFE,
                    data_fields=[],
                    retention_days=30,
                    heartbeat_threshold_seconds=300,
                )

        mock_service = MagicMock()
        mock_service.get_mssp.return_value = mssp
        mock_service.get_customer.side_effect = get_customer

        sender = MSSPWebhookSender()
        sender._mssp_service = mock_service

        return sender

    def test_full_mode_includes_mssp_data(self, sender_with_mock_service, monkeypatch):
        """Full mode should include _mssp_data in webhook payload."""
        sender = sender_with_mock_service

        # Mock webhook delivery
        mock_delivery = MagicMock()
        mock_delivery.deliver.return_value = MagicMock(success=True, attempts=1)
        sender._get_or_create_webhook_service = MagicMock(return_value=mock_delivery)

        payload = {
            "event_type": "scan",
            "payload": {
                "threat_detected": True,
                "_mssp_context": {
                    "mssp_id": "mssp_test",
                    "customer_id": "cust_full",
                    "data_mode": "full",
                },
                "_mssp_data": {
                    "prompt_text": "test prompt",
                    "matched_text": "ignore all",
                },
            },
        }

        result = sender.send_if_configured(
            event_payload=payload,
            mssp_id="mssp_test",
            customer_id="cust_full",
        )

        assert result is True
        # Verify _mssp_data was included in delivery
        delivered_payload = mock_delivery.deliver.call_args[0][0]
        assert "_mssp_data" in delivered_payload.get("payload", {})

    def test_privacy_safe_mode_strips_mssp_data(self, sender_with_mock_service, monkeypatch):
        """Privacy safe mode should strip _mssp_data from webhook payload."""
        sender = sender_with_mock_service

        mock_delivery = MagicMock()
        mock_delivery.deliver.return_value = MagicMock(success=True, attempts=1)
        sender._get_or_create_webhook_service = MagicMock(return_value=mock_delivery)

        payload = {
            "event_type": "scan",
            "payload": {
                "threat_detected": True,
                "_mssp_context": {
                    "mssp_id": "mssp_test",
                    "customer_id": "cust_safe",
                    "data_mode": "privacy_safe",
                },
                "_mssp_data": {
                    "prompt_text": "should be stripped",
                },
            },
        }

        result = sender.send_if_configured(
            event_payload=payload,
            mssp_id="mssp_test",
            customer_id="cust_safe",
        )

        assert result is True
        # Verify _mssp_data was stripped
        delivered_payload = mock_delivery.deliver.call_args[0][0]
        assert "_mssp_data" not in delivered_payload.get("payload", {})


class TestMSSPWebhookSenderCaching:
    """Tests for webhook service caching."""

    def test_webhook_service_cached_per_mssp(self, monkeypatch):
        """Webhook services should be cached and reused per MSSP."""
        from raxe.application.mssp_webhook_sender import MSSPWebhookSender
        from raxe.domain.mssp.models import (
            MSSP,
            DataMode,
            MSSPCustomer,
            MSSPTier,
            WebhookConfig,
        )

        mssp = MSSP(
            mssp_id="mssp_test",
            name="Test",
            tier=MSSPTier.STARTER,
            max_customers=10,
            api_key_hash="hash",
            webhook_config=WebhookConfig(url="https://test.com/webhook", secret="s"),
        )

        customer = MSSPCustomer(
            customer_id="cust_test",
            mssp_id="mssp_test",
            name="Test",
            data_mode=DataMode.FULL,
            data_fields=[],
            retention_days=30,
            heartbeat_threshold_seconds=300,
        )

        mock_service = MagicMock()
        mock_service.get_mssp.return_value = mssp
        mock_service.get_customer.return_value = customer

        sender = MSSPWebhookSender()
        sender._mssp_service = mock_service

        # Mock WebhookDeliveryService creation
        mock_webhook = MagicMock()
        mock_webhook.deliver.return_value = MagicMock(success=True, attempts=1)

        with patch(
            "raxe.application.mssp_webhook_sender.WebhookDeliveryService",
            return_value=mock_webhook,
        ) as mock_class:
            # First call - creates new service
            sender.send_if_configured(
                event_payload={"payload": {}},
                mssp_id="mssp_test",
                customer_id="cust_test",
            )

            # Second call - should reuse cached service
            sender.send_if_configured(
                event_payload={"payload": {}},
                mssp_id="mssp_test",
                customer_id="cust_test",
            )

            # WebhookDeliveryService should only be created once
            assert mock_class.call_count == 1


class TestMSSPWebhookSenderNonBlocking:
    """Tests to verify MSSP webhook failures don't block RAXE telemetry."""

    def test_webhook_failure_returns_false_not_exception(self, monkeypatch):
        """Webhook delivery failure should return False, not raise exception."""
        from raxe.application.mssp_webhook_sender import MSSPWebhookSender
        from raxe.domain.mssp.models import (
            MSSP,
            DataMode,
            MSSPCustomer,
            MSSPTier,
            WebhookConfig,
        )

        mssp = MSSP(
            mssp_id="mssp_test",
            name="Test",
            tier=MSSPTier.STARTER,
            max_customers=10,
            api_key_hash="hash",
            webhook_config=WebhookConfig(url="https://test.com/webhook", secret="s"),
        )

        customer = MSSPCustomer(
            customer_id="cust_test",
            mssp_id="mssp_test",
            name="Test",
            data_mode=DataMode.FULL,
            data_fields=[],
            retention_days=30,
            heartbeat_threshold_seconds=300,
        )

        mock_service = MagicMock()
        mock_service.get_mssp.return_value = mssp
        mock_service.get_customer.return_value = customer

        sender = MSSPWebhookSender()
        sender._mssp_service = mock_service

        # Mock failed delivery
        mock_webhook = MagicMock()
        mock_webhook.deliver.return_value = MagicMock(
            success=False, attempts=3, error_message="Connection timeout"
        )

        with patch(
            "raxe.application.mssp_webhook_sender.WebhookDeliveryService",
            return_value=mock_webhook,
        ):
            # Should not raise, just return False
            result = sender.send_if_configured(
                event_payload={"payload": {}},
                mssp_id="mssp_test",
                customer_id="cust_test",
            )

            assert result is False  # Indicates failure but no exception

    def test_unexpected_exception_returns_false(self, monkeypatch):
        """Unexpected exceptions should be caught and return False."""
        from raxe.application.mssp_webhook_sender import MSSPWebhookSender

        mock_service = MagicMock()
        mock_service.get_mssp.side_effect = RuntimeError("Unexpected error")

        sender = MSSPWebhookSender()
        sender._mssp_service = mock_service

        # Should not raise
        result = sender.send_if_configured(
            event_payload={"payload": {}},
            mssp_id="mssp_test",
            customer_id="cust_test",
        )

        assert result is False
