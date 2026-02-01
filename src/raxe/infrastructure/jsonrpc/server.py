"""JSON-RPC server orchestrator.

Handles the request/response loop, signal handling, and graceful shutdown.
"""

from __future__ import annotations

import logging
import signal
import threading
from collections.abc import Callable
from types import FrameType
from typing import TYPE_CHECKING, Any

from raxe.domain.jsonrpc.errors import create_internal_error
from raxe.domain.jsonrpc.models import JsonRpcResponse
from raxe.infrastructure.jsonrpc.transports.stdio import TransportError

if TYPE_CHECKING:
    from raxe.application.jsonrpc.dispatcher import JsonRpcDispatcher
    from raxe.infrastructure.jsonrpc.transports.base import Transport

# Signal handler type for proper typing
SignalHandler = Callable[[int, FrameType | None], Any] | int | None

logger = logging.getLogger(__name__)


class JsonRpcServer:
    """JSON-RPC server orchestrator.

    Handles the main request/response loop, dispatching requests
    to handlers, and graceful shutdown on signals.

    Example:
        >>> transport = StdioTransport()
        >>> server = JsonRpcServer(transport=transport)
        >>> server.start()  # Blocks until stopped

    Example with context manager:
        >>> with JsonRpcServer(transport=transport) as server:
        ...     server.start()
    """

    def __init__(
        self,
        transport: Transport,
        dispatcher: JsonRpcDispatcher | None = None,
    ) -> None:
        """Initialize JSON-RPC server.

        Args:
            transport: Transport for reading requests and writing responses
            dispatcher: Optional dispatcher (creates default if not provided)
        """
        self._transport = transport

        if dispatcher is None:
            from raxe.application.jsonrpc.dispatcher import JsonRpcDispatcher

            dispatcher = JsonRpcDispatcher()

        self._dispatcher = dispatcher
        self._running = False
        self._lock = threading.Lock()
        self._stats: dict[str, Any] = {
            "requests_processed": 0,
            "errors": 0,
        }
        self._original_sigterm: SignalHandler = signal.SIG_DFL
        self._original_sigint: SignalHandler = signal.SIG_DFL

    @property
    def running(self) -> bool:
        """Check if the server is running."""
        return self._running

    @property
    def stats(self) -> dict[str, Any]:
        """Get server statistics."""
        return self._stats.copy()

    def start(self) -> None:
        """Start the server and process requests.

        Blocks until the server is stopped via stop(), signal,
        or EOF on the transport.

        Signal handlers for SIGTERM and SIGINT are installed
        to enable graceful shutdown.
        """
        self._running = True
        self._install_signal_handlers()

        try:
            self._run_loop()
        finally:
            self._restore_signal_handlers()
            self._running = False

    def stop(self) -> None:
        """Stop the server gracefully.

        This method is thread-safe and can be called from
        signal handlers or other threads.
        """
        with self._lock:
            self._running = False
            self._transport.close()

    def _run_loop(self) -> None:
        """Main request processing loop."""
        while self._running:
            try:
                request = self._transport.read()

                # EOF or closed
                if request is None:
                    break

                # Dispatch request
                try:
                    response = self._dispatcher.dispatch(request)
                except Exception as e:
                    logger.exception(f"Dispatcher error: {e}")
                    response = JsonRpcResponse(
                        jsonrpc="2.0",
                        id=request.id,
                        error=create_internal_error(
                            message="Internal error occurred while processing request",
                        ),
                    )
                    self._stats["errors"] += 1

                # Write response (skip for notifications if response is None)
                if response is not None:
                    self._transport.write(response)

                self._stats["requests_processed"] += 1

            except TransportError as e:
                # Handle transport errors (parse errors, invalid requests)
                logger.warning(f"Transport error: {e}")
                self._stats["errors"] += 1

                # Write error response
                error_response = JsonRpcResponse(
                    jsonrpc="2.0",
                    id=None,  # Unknown request id
                    error=e.to_jsonrpc_error(),
                )
                self._transport.write(error_response)

                # For parse errors, try to continue
                # For fatal errors, we might break
                if self._transport.closed:
                    break

            except Exception as e:
                # Unexpected error - log and continue
                logger.exception(f"Unexpected error in server loop: {e}")
                self._stats["errors"] += 1

                # Try to send generic error
                try:
                    error_response = JsonRpcResponse(
                        jsonrpc="2.0",
                        id=None,
                        error=create_internal_error(),
                    )
                    self._transport.write(error_response)
                except Exception as write_error:
                    logger.debug(f"Failed to write error response: {write_error}")

    def _install_signal_handlers(self) -> None:
        """Install signal handlers for graceful shutdown."""
        try:
            self._original_sigterm = signal.signal(signal.SIGTERM, self._signal_handler)
            self._original_sigint = signal.signal(signal.SIGINT, self._signal_handler)
        except (ValueError, OSError):
            # Can't set signal handlers (e.g., not main thread)
            pass

    def _restore_signal_handlers(self) -> None:
        """Restore original signal handlers."""
        try:
            signal.signal(signal.SIGTERM, self._original_sigterm)
            signal.signal(signal.SIGINT, self._original_sigint)
        except (ValueError, OSError):
            pass

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()

    def __enter__(self) -> JsonRpcServer:
        """Support context manager protocol."""
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: Exception | None,
        exc_tb: object,
    ) -> None:
        """Stop server on context exit."""
        self.stop()


__all__ = ["JsonRpcServer"]
