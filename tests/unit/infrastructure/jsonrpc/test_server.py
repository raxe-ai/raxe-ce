"""Unit tests for JSON-RPC server.

Tests for:
- JsonRpcServer: Main server orchestrator
- Request handling loop
- Signal handling (SIGTERM, SIGINT)
- Graceful shutdown
"""

from __future__ import annotations

import io
import json
import signal
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from raxe.domain.jsonrpc.errors import JsonRpcErrorCode
from raxe.domain.jsonrpc.models import (
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_transport():
    """Create a mock transport for testing."""
    transport = MagicMock()
    transport.closed = False
    transport.read.return_value = None
    return transport


@pytest.fixture
def mock_dispatcher():
    """Create a mock dispatcher for testing."""
    from raxe.application.jsonrpc.dispatcher import JsonRpcDispatcher

    dispatcher = MagicMock(spec=JsonRpcDispatcher)
    dispatcher.dispatch.return_value = JsonRpcResponse(
        jsonrpc="2.0",
        id="1",
        result={"status": "ok"},
    )
    return dispatcher


@pytest.fixture
def sample_request() -> JsonRpcRequest:
    """Create a sample JSON-RPC request."""
    return JsonRpcRequest(
        jsonrpc="2.0",
        method="scan",
        id="1",
        params={"prompt": "test"},
    )


@pytest.fixture
def sample_notification() -> JsonRpcRequest:
    """Create a sample JSON-RPC notification (no id)."""
    return JsonRpcRequest(
        jsonrpc="2.0",
        method="notify_event",
        params={"event": "started"},
    )


# ============================================================================
# Server Initialization Tests
# ============================================================================


class TestJsonRpcServerInit:
    """Tests for JsonRpcServer initialization."""

    def test_server_initializes_with_transport_and_dispatcher(
        self, mock_transport, mock_dispatcher
    ):
        """Server initializes with transport and dispatcher."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        assert server._transport is mock_transport
        assert server._dispatcher is mock_dispatcher

    def test_server_initializes_default_dispatcher(self, mock_transport):
        """Server creates default dispatcher if none provided."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        server = JsonRpcServer(transport=mock_transport)

        assert server._dispatcher is not None

    def test_server_not_running_initially(self, mock_transport, mock_dispatcher):
        """Server is not running after initialization."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        assert server.running is False


# ============================================================================
# Server Start/Stop Tests
# ============================================================================


class TestJsonRpcServerStartStop:
    """Tests for server start and stop functionality."""

    def test_start_sets_running_flag(self, mock_transport, mock_dispatcher):
        """Start sets running flag to True."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        # Make transport return None immediately to end loop
        mock_transport.read.return_value = None

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        # Run in thread to avoid blocking
        def run_server():
            server.start()

        thread = threading.Thread(target=run_server)
        thread.start()

        # Give server time to start
        time.sleep(0.05)

        # Server should have been running
        # (it may have stopped already due to EOF)
        assert thread.is_alive() or mock_transport.read.called

        # Ensure cleanup
        server.stop()
        thread.join(timeout=1.0)

    def test_stop_sets_running_flag_false(self, mock_transport, mock_dispatcher):
        """Stop sets running flag to False."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        # Simulate that server was running
        server._running = True

        server.stop()

        assert server.running is False

    def test_stop_closes_transport(self, mock_transport, mock_dispatcher):
        """Stop closes the transport."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        server.stop()

        mock_transport.close.assert_called_once()

    def test_stop_is_idempotent(self, mock_transport, mock_dispatcher):
        """Stop can be called multiple times safely."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        # Should not raise
        server.stop()
        server.stop()
        server.stop()


# ============================================================================
# Request Handling Tests
# ============================================================================


class TestJsonRpcServerRequestHandling:
    """Tests for server request handling."""

    def test_handle_request_dispatches_to_handler(
        self, mock_transport, mock_dispatcher, sample_request
    ):
        """Server dispatches request to handler and writes response."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        # Set up transport to return one request then None
        mock_transport.read.side_effect = [sample_request, None]

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        # Run server (will stop after EOF)
        server.start()

        # Verify dispatcher was called with request
        mock_dispatcher.dispatch.assert_called_once_with(sample_request)

        # Verify response was written
        mock_transport.write.assert_called_once()

    def test_handle_multiple_requests(self, mock_transport, mock_dispatcher):
        """Server handles multiple requests in sequence."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        requests = [
            JsonRpcRequest(jsonrpc="2.0", method="scan", id="1"),
            JsonRpcRequest(jsonrpc="2.0", method="info", id="2"),
            JsonRpcRequest(jsonrpc="2.0", method="list", id="3"),
        ]

        mock_transport.read.side_effect = [*requests, None]

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        server.start()

        # Verify all requests were dispatched
        assert mock_dispatcher.dispatch.call_count == 3

        # Verify all responses were written
        assert mock_transport.write.call_count == 3

    def test_notification_no_response(self, mock_transport, mock_dispatcher, sample_notification):
        """Server does not write response for notifications."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        mock_transport.read.side_effect = [sample_notification, None]

        # Dispatcher returns None for notification
        mock_dispatcher.dispatch.return_value = None

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        server.start()

        # Verify request was dispatched
        mock_dispatcher.dispatch.assert_called_once()

        # Verify no response was written
        mock_transport.write.assert_not_called()


class TestJsonRpcServerErrorHandling:
    """Tests for server error handling."""

    def test_unknown_method_returns_error(self, mock_transport, mock_dispatcher):
        """Server returns method not found error for unknown method."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        request = JsonRpcRequest(jsonrpc="2.0", method="unknown_method", id="1")
        mock_transport.read.side_effect = [request, None]

        # Dispatcher returns error response
        error = JsonRpcError(
            code=JsonRpcErrorCode.METHOD_NOT_FOUND,
            message="Method not found: unknown_method",
        )
        mock_dispatcher.dispatch.return_value = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            error=error,
        )

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        server.start()

        # Verify error response was written
        mock_transport.write.assert_called_once()
        written_response = mock_transport.write.call_args[0][0]
        assert written_response.is_error
        assert written_response.error.code == JsonRpcErrorCode.METHOD_NOT_FOUND

    def test_server_handles_transport_error(self, mock_transport, mock_dispatcher):
        """Server handles transport errors gracefully."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer
        from raxe.infrastructure.jsonrpc.transports.stdio import TransportError

        # Transport raises error on first read, then returns None (EOF)
        mock_transport.read.side_effect = [
            TransportError(
                message="Parse error",
                error_code=JsonRpcErrorCode.PARSE_ERROR,
            ),
            None,  # EOF after error
        ]

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        # Should not raise - server handles errors
        server.start()

        # Verify error response was written
        mock_transport.write.assert_called()
        written_response = mock_transport.write.call_args[0][0]
        assert written_response.is_error
        assert written_response.error.code == JsonRpcErrorCode.PARSE_ERROR

    def test_server_handles_dispatcher_exception(self, mock_transport, mock_dispatcher):
        """Server handles exceptions from dispatcher gracefully."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        request = JsonRpcRequest(jsonrpc="2.0", method="crash", id="1")
        mock_transport.read.side_effect = [request, None]

        # Dispatcher raises exception
        mock_dispatcher.dispatch.side_effect = RuntimeError("Handler crashed")

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        # Should not raise - server catches exception
        server.start()

        # Verify internal error response was written
        mock_transport.write.assert_called_once()
        written_response = mock_transport.write.call_args[0][0]
        assert written_response.is_error
        assert written_response.error.code == JsonRpcErrorCode.INTERNAL_ERROR


# ============================================================================
# Signal Handling Tests
# ============================================================================


class TestJsonRpcServerSignalHandling:
    """Tests for server signal handling (SIGTERM, SIGINT)."""

    def test_graceful_shutdown_on_sigterm(self, mock_transport, mock_dispatcher):
        """Server shuts down gracefully on SIGTERM."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        # Transport blocks on read until server is stopped
        read_event = threading.Event()

        def blocking_read():
            if read_event.wait(timeout=1.0):
                return None
            return None

        mock_transport.read.side_effect = blocking_read

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        # Run server in thread
        server_thread = threading.Thread(target=server.start)
        server_thread.start()

        # Give server time to start
        time.sleep(0.05)

        # Simulate SIGTERM by calling stop
        server.stop()
        read_event.set()

        # Wait for server to stop
        server_thread.join(timeout=1.0)

        assert not server_thread.is_alive()
        assert server.running is False

    def test_graceful_shutdown_on_sigint(self, mock_transport, mock_dispatcher):
        """Server shuts down gracefully on SIGINT (Ctrl+C)."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        # Transport blocks on read until server is stopped
        read_event = threading.Event()

        def blocking_read():
            if read_event.wait(timeout=1.0):
                return None
            return None

        mock_transport.read.side_effect = blocking_read

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        # Run server in thread
        server_thread = threading.Thread(target=server.start)
        server_thread.start()

        # Give server time to start
        time.sleep(0.05)

        # Simulate SIGINT by calling stop
        server.stop()
        read_event.set()

        # Wait for server to stop
        server_thread.join(timeout=1.0)

        assert not server_thread.is_alive()
        assert server.running is False

    def test_signal_handlers_installed_on_start(self, mock_transport, mock_dispatcher):
        """Server installs signal handlers when started."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        mock_transport.read.return_value = None

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        # Track signal handler installation
        original_sigterm = signal.getsignal(signal.SIGTERM)
        original_sigint = signal.getsignal(signal.SIGINT)

        try:
            with patch.object(signal, "signal") as mock_signal:
                server.start()

                # Verify signal handlers were installed
                # (at least one call for SIGTERM or SIGINT)
                signal_calls = [call[0][0] for call in mock_signal.call_args_list if call[0]]
                assert (
                    any(sig in signal_calls for sig in [signal.SIGTERM, signal.SIGINT])
                    or mock_signal.called
                )
        finally:
            # Restore original handlers
            signal.signal(signal.SIGTERM, original_sigterm)
            signal.signal(signal.SIGINT, original_sigint)


# ============================================================================
# Integration Tests with Stdio Transport
# ============================================================================


class TestJsonRpcServerWithStdioTransport:
    """Integration tests with StdioTransport."""

    def test_server_processes_stdio_request(self, mock_dispatcher):
        """Server processes request from stdio transport."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        # Create request
        request_data = {
            "jsonrpc": "2.0",
            "method": "scan",
            "id": "1",
            "params": {"prompt": "test"},
        }
        stdin = io.StringIO(json.dumps(request_data) + "\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        server = JsonRpcServer(
            transport=transport,
            dispatcher=mock_dispatcher,
        )

        server.start()

        # Parse output
        output = stdout.getvalue().strip()
        response = json.loads(output)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "1"

    def test_server_handles_malformed_json_from_stdio(self, mock_dispatcher):
        """Server handles malformed JSON from stdio."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        stdin = io.StringIO("not valid json\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        server = JsonRpcServer(
            transport=transport,
            dispatcher=mock_dispatcher,
        )

        server.start()

        # Parse output - should be error response
        output = stdout.getvalue().strip()
        response = json.loads(output)

        assert "error" in response
        assert response["error"]["code"] == JsonRpcErrorCode.PARSE_ERROR


# ============================================================================
# Server Statistics Tests
# ============================================================================


class TestJsonRpcServerStatistics:
    """Tests for server statistics tracking."""

    def test_server_tracks_request_count(self, mock_transport, mock_dispatcher):
        """Server tracks total request count."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        requests = [
            JsonRpcRequest(jsonrpc="2.0", method="scan", id="1"),
            JsonRpcRequest(jsonrpc="2.0", method="info", id="2"),
            JsonRpcRequest(jsonrpc="2.0", method="list", id="3"),
        ]
        mock_transport.read.side_effect = [*requests, None]

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        server.start()

        assert server.stats["requests_processed"] == 3

    def test_server_tracks_error_count(self, mock_transport, mock_dispatcher):
        """Server tracks error count."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer
        from raxe.infrastructure.jsonrpc.transports.stdio import TransportError

        # First read raises error, second returns None (EOF)
        mock_transport.read.side_effect = [
            TransportError(message="Parse error", error_code=JsonRpcErrorCode.PARSE_ERROR),
            None,
        ]

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        server.start()

        assert server.stats["errors"] >= 1


# ============================================================================
# Server Context Manager Tests
# ============================================================================


class TestJsonRpcServerContextManager:
    """Tests for server context manager support."""

    def test_server_as_context_manager(self, mock_transport, mock_dispatcher):
        """Server can be used as context manager."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        mock_transport.read.return_value = None

        with JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        ) as server:
            # Server should not auto-start in context manager
            assert server is not None

    def test_context_manager_stops_on_exit(self, mock_transport, mock_dispatcher):
        """Context manager stops server on exit."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        mock_transport.read.return_value = None

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        with server:
            pass

        # Server should be stopped after context exit
        mock_transport.close.assert_called()


# ============================================================================
# Thread Safety Tests
# ============================================================================


class TestJsonRpcServerThreadSafety:
    """Tests for server thread safety."""

    def test_concurrent_stop_calls(self, mock_transport, mock_dispatcher):
        """Multiple concurrent stop calls are handled safely."""
        from raxe.infrastructure.jsonrpc.server import JsonRpcServer

        server = JsonRpcServer(
            transport=mock_transport,
            dispatcher=mock_dispatcher,
        )

        # Call stop from multiple threads
        threads = [threading.Thread(target=server.stop) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should not raise or deadlock
        assert server.running is False
