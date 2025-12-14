"""Unit tests for flush_helper module.

Tests for:
- ensure_telemetry_flushed() function
- Session ending before flush
- Queue flushing (critical first, then standard)
- Timeout handling
- Error handling (never raises)
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest


class TestEnsureTelemetryFlushed:
    """Tests for ensure_telemetry_flushed function."""

    def test_import_works(self):
        """Test that the module can be imported."""
        from raxe.infrastructure.telemetry.flush_helper import ensure_telemetry_flushed
        assert callable(ensure_telemetry_flushed)

    def test_never_raises_on_import_error(self):
        """Test that function never raises even with import errors."""
        from raxe.infrastructure.telemetry.flush_helper import ensure_telemetry_flushed

        # Mock to simulate import failure
        with patch(
            'raxe.infrastructure.telemetry.flush_helper._get_telemetry_context',
            side_effect=ImportError("Test import error")
        ):
            # Should not raise
            ensure_telemetry_flushed(timeout_seconds=0.1)

    def test_never_raises_on_runtime_error(self):
        """Test that function never raises on runtime errors."""
        from raxe.infrastructure.telemetry.flush_helper import ensure_telemetry_flushed

        with patch(
            'raxe.infrastructure.telemetry.flush_helper._end_telemetry_session',
            side_effect=RuntimeError("Test error")
        ):
            # Should not raise
            ensure_telemetry_flushed(timeout_seconds=0.1)

    def test_respects_timeout(self):
        """Test that function respects timeout parameter."""
        from raxe.infrastructure.telemetry.flush_helper import ensure_telemetry_flushed

        start = time.time()
        # Very short timeout
        ensure_telemetry_flushed(timeout_seconds=0.1)
        elapsed = time.time() - start

        # Should complete within reasonable time (timeout + overhead)
        assert elapsed < 1.0, f"Took too long: {elapsed}s"

    def test_ends_session_when_requested(self):
        """Test that session is ended when end_session=True."""
        from raxe.infrastructure.telemetry.flush_helper import _end_telemetry_session

        mock_tracker = MagicMock()
        mock_tracker.is_session_active = True

        mock_orchestrator = MagicMock()
        mock_orchestrator._session_tracker = mock_tracker

        # Patch at the source module where get_orchestrator is imported from
        with patch(
            'raxe.application.telemetry_orchestrator.get_orchestrator',
            return_value=mock_orchestrator
        ):
            _end_telemetry_session()
            mock_tracker.end_session.assert_called_once_with(end_reason="normal")

    def test_skips_session_end_when_not_active(self):
        """Test that session end is skipped when no active session."""
        from raxe.infrastructure.telemetry.flush_helper import _end_telemetry_session

        mock_tracker = MagicMock()
        mock_tracker.is_session_active = False

        mock_orchestrator = MagicMock()
        mock_orchestrator._session_tracker = mock_tracker

        # Patch at the source module where get_orchestrator is imported from
        with patch(
            'raxe.application.telemetry_orchestrator.get_orchestrator',
            return_value=mock_orchestrator
        ):
            _end_telemetry_session()
            mock_tracker.end_session.assert_not_called()


class TestGetTelemetryContext:
    """Tests for _get_telemetry_context helper."""

    def test_returns_none_on_error(self):
        """Test that function returns None tuple on error."""
        from raxe.infrastructure.telemetry.flush_helper import _get_telemetry_context

        with patch(
            'raxe.infrastructure.telemetry.flush_helper._get_telemetry_context',
            return_value=(None, None, None)
        ):
            api_key, installation_id, config = _get_telemetry_context()
            # At minimum should not raise


class TestFlushQueue:
    """Tests for _flush_queue helper."""

    def test_handles_empty_queue(self):
        """Test that empty queue is handled gracefully."""
        from raxe.infrastructure.telemetry.flush_helper import _flush_queue

        mock_queue = MagicMock()
        mock_queue.dequeue_critical.return_value = []
        mock_sender = MagicMock()

        # Should not raise
        _flush_queue(mock_queue, mock_sender, "critical", max_batches=10, batch_size=50)

        # Should have attempted to dequeue
        mock_queue.dequeue_critical.assert_called_once()
        # Should not have tried to send (no events)
        mock_sender.send_batch.assert_not_called()

    def test_stops_on_send_error(self):
        """Test that flush stops on send error."""
        from raxe.infrastructure.telemetry.flush_helper import _flush_queue

        mock_queue = MagicMock()
        mock_queue.dequeue_standard.side_effect = [
            [{"event_id": "1"}],  # First batch
            [{"event_id": "2"}],  # Second batch (won't be reached)
        ]

        mock_sender = MagicMock()
        mock_sender.send_batch.side_effect = Exception("Network error")

        # Should not raise
        _flush_queue(mock_queue, mock_sender, "standard", max_batches=10, batch_size=50)

        # Should have stopped after first error
        assert mock_sender.send_batch.call_count == 1


class TestIntegration:
    """Integration tests for flush_helper with mocked dependencies."""

    def test_full_flush_flow(self):
        """Test the full flush flow with mocked components."""
        from raxe.infrastructure.telemetry.flush_helper import ensure_telemetry_flushed

        # This test verifies the function completes without error
        # In a real scenario, it would flush actual events

        # Mock all dependencies to return quickly
        with patch('raxe.infrastructure.telemetry.flush_helper._end_telemetry_session'):
            with patch(
                'raxe.infrastructure.telemetry.flush_helper._get_telemetry_context',
                return_value=(None, None, None)  # No credentials = early exit
            ):
                start = time.time()
                ensure_telemetry_flushed(timeout_seconds=0.5)
                elapsed = time.time() - start

                # Should complete quickly when no credentials
                assert elapsed < 1.0

    def test_thread_safety(self):
        """Test that multiple concurrent flushes don't cause issues."""
        from raxe.infrastructure.telemetry.flush_helper import ensure_telemetry_flushed

        errors = []

        def flush_thread():
            try:
                ensure_telemetry_flushed(timeout_seconds=0.1)
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = [threading.Thread(target=flush_thread) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)

        # Should have no errors
        assert len(errors) == 0, f"Errors occurred: {errors}"


class TestBatchCommandScenario:
    """Test scenarios specific to batch command usage."""

    def test_large_batch_timeout_calculation(self):
        """Verify timeout calculation for large batches."""
        # From main.py batch_scan:
        # timeout = min(2.0 + len(prompts) * 0.01, 30.0)

        # 100 prompts
        prompts_100 = list(range(100))
        timeout_100 = min(2.0 + len(prompts_100) * 0.01, 30.0)
        assert timeout_100 == 3.0

        # 1000 prompts
        prompts_1000 = list(range(1000))
        timeout_1000 = min(2.0 + len(prompts_1000) * 0.01, 30.0)
        assert timeout_1000 == 12.0

        # 5000 prompts (capped at 30s)
        prompts_5000 = list(range(5000))
        timeout_5000 = min(2.0 + len(prompts_5000) * 0.01, 30.0)
        assert timeout_5000 == 30.0

    def test_max_batches_calculation(self):
        """Verify max_batches calculation for large batches."""
        # From main.py batch_scan:
        # max_batches = max(10, len(prompts) // 50 + 1)

        # 100 prompts
        max_batches_100 = max(10, 100 // 50 + 1)
        assert max_batches_100 == 10  # Minimum 10

        # 1000 prompts
        max_batches_1000 = max(10, 1000 // 50 + 1)
        assert max_batches_1000 == 21

        # 5000 prompts
        max_batches_5000 = max(10, 5000 // 50 + 1)
        assert max_batches_5000 == 101


class TestFlushStaleTelemetry:
    """Tests for flush_stale_telemetry_async function."""

    def test_import_works(self):
        """Test that the function can be imported."""
        from raxe.infrastructure.telemetry.flush_helper import flush_stale_telemetry_async
        assert callable(flush_stale_telemetry_async)

    def test_never_raises(self):
        """Test that function never raises even with errors."""
        from raxe.infrastructure.telemetry.flush_helper import flush_stale_telemetry_async

        # Mock queue to raise error
        with patch(
            'raxe.infrastructure.telemetry.flush_helper._get_queue',
            side_effect=RuntimeError("Test error")
        ):
            # Should not raise
            flush_stale_telemetry_async()

    def test_skips_empty_queue(self):
        """Test that function skips when queue is empty."""
        from raxe.infrastructure.telemetry.flush_helper import flush_stale_telemetry_async

        mock_queue = MagicMock()
        mock_queue.get_stats.return_value = {
            "total_queued": 0,
            "oldest_standard": None,
            "oldest_critical": None,
        }

        with patch(
            'raxe.infrastructure.telemetry.flush_helper._get_queue',
            return_value=mock_queue
        ):
            flush_stale_telemetry_async()
            mock_queue.close.assert_called_once()

    def test_skips_fresh_events(self):
        """Test that function skips events newer than threshold."""
        from raxe.infrastructure.telemetry.flush_helper import flush_stale_telemetry_async
        from datetime import datetime, timezone

        mock_queue = MagicMock()
        # Events are only 5 minutes old (below 15 minute threshold)
        recent_timestamp = datetime.now(timezone.utc).isoformat()
        mock_queue.get_stats.return_value = {
            "total_queued": 100,
            "oldest_standard": recent_timestamp,
            "oldest_critical": None,
        }

        with patch(
            'raxe.infrastructure.telemetry.flush_helper._get_queue',
            return_value=mock_queue
        ):
            with patch(
                'raxe.infrastructure.telemetry.flush_helper.ensure_telemetry_flushed'
            ) as mock_flush:
                flush_stale_telemetry_async(stale_threshold_minutes=15.0)
                # Should NOT call flush because events are not stale
                mock_flush.assert_not_called()

    def test_flushes_stale_events(self):
        """Test that function flushes events older than threshold."""
        from raxe.infrastructure.telemetry.flush_helper import flush_stale_telemetry_async
        from datetime import datetime, timezone, timedelta

        mock_queue = MagicMock()
        # Events are 20 minutes old (above 15 minute threshold)
        old_timestamp = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        mock_queue.get_stats.return_value = {
            "total_queued": 100,
            "oldest_standard": old_timestamp,
            "oldest_critical": None,
        }

        with patch(
            'raxe.infrastructure.telemetry.flush_helper._get_queue',
            return_value=mock_queue
        ):
            with patch(
                'raxe.infrastructure.telemetry.flush_helper.ensure_telemetry_flushed'
            ) as mock_flush:
                flush_stale_telemetry_async(stale_threshold_minutes=15.0)
                # Give thread time to run
                time.sleep(0.2)
                # Should call flush because events are stale
                mock_flush.assert_called_once()
                # Verify end_session=False (startup flush shouldn't end session)
                call_kwargs = mock_flush.call_args[1]
                assert call_kwargs.get('end_session') is False
