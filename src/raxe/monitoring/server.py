"""
Optional Prometheus metrics HTTP server.

This module provides an HTTP server that exposes Prometheus metrics at /metrics.
The server is optional and can be started with `raxe metrics-server`.

Usage:
    # Start metrics server
    raxe metrics-server --port 9090

    # Metrics available at
    http://localhost:9090/metrics

The server runs in a background thread and does not block the main application.
"""

import threading
from wsgiref.simple_server import make_server

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest, make_wsgi_app


class MetricsServer:
    """
    Optional HTTP server to expose Prometheus metrics.

    This server runs in a background thread and exposes metrics at /metrics.
    It's intended for development and debugging - production deployments should
    use proper Prometheus exporters.

    Attributes:
        port: Port to listen on
        server: WSGIServer instance
        thread: Background thread running the server

    Example:
        server = MetricsServer(port=9090)
        server.start()
        # Metrics available at http://localhost:9090/metrics
        server.stop()
    """

    def __init__(self, port: int = 9090, host: str = ""):
        """
        Initialize metrics server.

        Args:
            port: Port to listen on (default: 9090)
            host: Host to bind to (default: "" = all interfaces)
        """
        self.port = port
        self.host = host
        self.server = None
        self.thread = None
        self._running = False

    def start(self):
        """
        Start metrics server in background thread.

        Raises:
            RuntimeError: If server is already running
        """
        if self._running:
            raise RuntimeError("Metrics server is already running")

        # Create WSGI app
        app = make_wsgi_app()

        # Create server
        self.server = make_server(self.host, self.port, app)

        # Start in background thread
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self._running = True
        self.thread.start()

    def _serve(self):
        """Background thread target - serves requests."""
        try:
            self.server.serve_forever()
        except Exception:
            # Server was shut down
            pass
        finally:
            self._running = False

    def stop(self):
        """
        Stop metrics server.

        Gracefully shuts down the server and joins the background thread.
        """
        if self.server and self._running:
            self.server.shutdown()
            self._running = False

            if self.thread:
                self.thread.join(timeout=5)

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running

    @property
    def url(self) -> str:
        """Get metrics URL."""
        return f"http://localhost:{self.port}/metrics"

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


def get_metrics_text() -> str:
    """
    Get current metrics as text in Prometheus format.

    This is useful for programmatic access to metrics without starting
    a full HTTP server.

    Returns:
        Metrics in Prometheus text format
    """
    return generate_latest().decode("utf-8")


def get_metrics_content_type() -> str:
    """Get Prometheus metrics content type."""
    return CONTENT_TYPE_LATEST
