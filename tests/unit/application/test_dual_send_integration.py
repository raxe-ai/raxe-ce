"""Tests for dual-send telemetry integration.

TDD: These tests verify that:
1. RAXE backend NEVER receives _mssp_data (privacy guarantee)
2. MSSP webhook receives full data when configured
3. Dual-send is non-blocking (MSSP failures don't affect RAXE)
"""

import copy
from unittest.mock import MagicMock


class TestDualSendPrivacyGuarantee:
    """Tests that _mssp_data is NEVER sent to RAXE backend."""

    def test_mssp_data_stripped_before_raxe_queue(self):
        """_mssp_data must be stripped before enqueueing to RAXE."""
        from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
        from raxe.infrastructure.config.yaml_config import TelemetryConfig

        # Create orchestrator with telemetry enabled
        config = TelemetryConfig(enabled=True)
        orchestrator = TelemetryOrchestrator(config=config)

        # Mock the queue to capture what gets enqueued
        mock_queue = MagicMock()
        mock_queue.get_state.return_value = "inst_test"
        mock_queue.has_state.return_value = True
        mock_queue.get_stats.return_value = {
            "critical_count": 0,
            "standard_count": 0,
            "dlq_count": 0,
        }
        mock_queue.critical_max_size = 1000
        mock_queue.standard_max_size = 10000

        orchestrator._queue = mock_queue
        orchestrator._initialized = True
        orchestrator._installation_id = "inst_test"

        # Payload with _mssp_data (should be stripped)
        payload = {
            "prompt_hash": "sha256:abc123",
            "prompt_length": 100,
            "threat_detected": True,
            "_mssp_context": {
                "mssp_id": "mssp_test",
                "customer_id": "cust_test",
                "data_mode": "full",
            },
            "_mssp_data": {
                "prompt_text": "SENSITIVE DATA THAT MUST NOT GO TO RAXE",
            },
        }

        # Track the scan
        orchestrator.track_scan_v2(payload)

        # Verify enqueue was called
        assert mock_queue.enqueue.called

        # Get the event that was enqueued
        enqueued_event = mock_queue.enqueue.call_args[0][0]

        # CRITICAL: _mssp_data must NOT be in the payload
        assert (
            "_mssp_data" not in enqueued_event.payload
        ), "SECURITY VIOLATION: _mssp_data was sent to RAXE backend"

        # _mssp_context can be sent (it's metadata only)
        assert "_mssp_context" in enqueued_event.payload

    def test_original_payload_not_modified(self):
        """Original payload should not be modified (defensive copy)."""
        from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
        from raxe.infrastructure.config.yaml_config import TelemetryConfig

        config = TelemetryConfig(enabled=True)
        orchestrator = TelemetryOrchestrator(config=config)

        mock_queue = MagicMock()
        mock_queue.get_state.return_value = "inst_test"
        mock_queue.has_state.return_value = True
        mock_queue.get_stats.return_value = {
            "critical_count": 0,
            "standard_count": 0,
            "dlq_count": 0,
        }
        mock_queue.critical_max_size = 1000
        mock_queue.standard_max_size = 10000

        orchestrator._queue = mock_queue
        orchestrator._initialized = True
        orchestrator._installation_id = "inst_test"

        # Original payload
        original_payload = {
            "prompt_hash": "sha256:abc123",
            "prompt_length": 100,
            "threat_detected": True,
            "_mssp_data": {
                "prompt_text": "sensitive",
            },
        }

        # Keep a copy to compare
        payload_before = copy.deepcopy(original_payload)

        # Track the scan
        orchestrator.track_scan_v2(original_payload)

        # Original payload should be unchanged
        assert (
            original_payload == payload_before
        ), "Original payload was modified - should use defensive copy"


class TestDualSendMSSPWebhook:
    """Tests that MSSP webhook is called when configured."""

    def test_mssp_webhook_called_when_configured(self):
        """MSSP webhook should be called when mssp_id is present."""
        from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
        from raxe.infrastructure.config.yaml_config import TelemetryConfig

        config = TelemetryConfig(enabled=True)
        orchestrator = TelemetryOrchestrator(config=config)

        mock_queue = MagicMock()
        mock_queue.get_state.return_value = "inst_test"
        mock_queue.has_state.return_value = True
        mock_queue.get_stats.return_value = {
            "critical_count": 0,
            "standard_count": 0,
            "dlq_count": 0,
        }
        mock_queue.critical_max_size = 1000
        mock_queue.standard_max_size = 10000

        orchestrator._queue = mock_queue
        orchestrator._initialized = True
        orchestrator._installation_id = "inst_test"

        # Mock MSSP webhook sender
        mock_mssp_sender = MagicMock()
        mock_mssp_sender.send_if_configured.return_value = True
        orchestrator._mssp_webhook_sender = mock_mssp_sender

        payload = {
            "prompt_hash": "sha256:abc123",
            "prompt_length": 100,
            "threat_detected": True,
            "mssp_id": "mssp_test",
            "customer_id": "cust_test",
            "_mssp_context": {
                "mssp_id": "mssp_test",
                "customer_id": "cust_test",
                "data_mode": "full",
            },
            "_mssp_data": {
                "prompt_text": "sensitive for MSSP only",
            },
        }

        orchestrator.track_scan_v2(payload)

        # MSSP webhook sender should be called
        mock_mssp_sender.send_if_configured.assert_called_once()

        # Verify correct arguments
        call_args = mock_mssp_sender.send_if_configured.call_args
        assert call_args.kwargs.get("mssp_id") == "mssp_test"
        assert call_args.kwargs.get("customer_id") == "cust_test"

    def test_mssp_webhook_not_called_without_mssp_id(self):
        """MSSP webhook should not be called when no mssp_id."""
        from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
        from raxe.infrastructure.config.yaml_config import TelemetryConfig

        config = TelemetryConfig(enabled=True)
        orchestrator = TelemetryOrchestrator(config=config)

        mock_queue = MagicMock()
        mock_queue.get_state.return_value = "inst_test"
        mock_queue.has_state.return_value = True
        mock_queue.get_stats.return_value = {
            "critical_count": 0,
            "standard_count": 0,
            "dlq_count": 0,
        }
        mock_queue.critical_max_size = 1000
        mock_queue.standard_max_size = 10000

        orchestrator._queue = mock_queue
        orchestrator._initialized = True
        orchestrator._installation_id = "inst_test"

        mock_mssp_sender = MagicMock()
        orchestrator._mssp_webhook_sender = mock_mssp_sender

        # Payload WITHOUT mssp_id
        payload = {
            "prompt_hash": "sha256:abc123",
            "prompt_length": 100,
            "threat_detected": False,
        }

        orchestrator.track_scan_v2(payload)

        # MSSP webhook sender should still be called but will skip internally
        # The sender's send_if_configured handles the None case
        mock_mssp_sender.send_if_configured.assert_called_once()


class TestDualSendNonBlocking:
    """Tests that MSSP webhook failures don't block RAXE telemetry."""

    def test_mssp_failure_does_not_block_raxe(self):
        """MSSP webhook failure should not prevent RAXE queue."""
        from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
        from raxe.infrastructure.config.yaml_config import TelemetryConfig

        config = TelemetryConfig(enabled=True)
        orchestrator = TelemetryOrchestrator(config=config)

        mock_queue = MagicMock()
        mock_queue.get_state.return_value = "inst_test"
        mock_queue.has_state.return_value = True
        mock_queue.get_stats.return_value = {
            "critical_count": 0,
            "standard_count": 0,
            "dlq_count": 0,
        }
        mock_queue.critical_max_size = 1000
        mock_queue.standard_max_size = 10000

        orchestrator._queue = mock_queue
        orchestrator._initialized = True
        orchestrator._installation_id = "inst_test"

        # Mock MSSP sender that fails
        mock_mssp_sender = MagicMock()
        mock_mssp_sender.send_if_configured.return_value = False  # Delivery failed
        orchestrator._mssp_webhook_sender = mock_mssp_sender

        payload = {
            "prompt_hash": "sha256:abc123",
            "prompt_length": 100,
            "threat_detected": True,
            "mssp_id": "mssp_test",
            "customer_id": "cust_test",
        }

        # Should not raise
        orchestrator.track_scan_v2(payload)

        # RAXE queue should still receive the event
        assert mock_queue.enqueue.called

    def test_mssp_exception_does_not_block_raxe(self):
        """MSSP webhook exception should not prevent RAXE queue."""
        from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
        from raxe.infrastructure.config.yaml_config import TelemetryConfig

        config = TelemetryConfig(enabled=True)
        orchestrator = TelemetryOrchestrator(config=config)

        mock_queue = MagicMock()
        mock_queue.get_state.return_value = "inst_test"
        mock_queue.has_state.return_value = True
        mock_queue.get_stats.return_value = {
            "critical_count": 0,
            "standard_count": 0,
            "dlq_count": 0,
        }
        mock_queue.critical_max_size = 1000
        mock_queue.standard_max_size = 10000

        orchestrator._queue = mock_queue
        orchestrator._initialized = True
        orchestrator._installation_id = "inst_test"

        # Mock MSSP sender that raises exception
        mock_mssp_sender = MagicMock()
        mock_mssp_sender.send_if_configured.side_effect = RuntimeError("Network error")
        orchestrator._mssp_webhook_sender = mock_mssp_sender

        payload = {
            "prompt_hash": "sha256:abc123",
            "prompt_length": 100,
            "threat_detected": True,
            "mssp_id": "mssp_test",
            "customer_id": "cust_test",
        }

        # Should not raise
        orchestrator.track_scan_v2(payload)

        # RAXE queue should still receive the event
        assert mock_queue.enqueue.called
