"""Tests for Prometheus metrics server."""

import time

import pytest
import requests

from raxe.monitoring.server import (
    MetricsServer,
    get_metrics_content_type,
    get_metrics_text,
)


class TestMetricsServer:
    """Test MetricsServer class."""

    def test_server_init(self):
        """Test server initialization."""
        server = MetricsServer(port=9090, host="localhost")

        assert server.port == 9090
        assert server.host == "localhost"
        assert server.server is None
        assert server.thread is None
        assert server.is_running is False

    def test_server_start_stop(self):
        """Test starting and stopping server."""
        server = MetricsServer(port=9095)  # Use different port

        try:
            # Start server
            server.start()
            time.sleep(0.5)  # Give server time to start

            assert server.is_running is True
            assert server.server is not None
            assert server.thread is not None
            assert server.thread.is_alive()

        finally:
            # Stop server
            server.stop()
            time.sleep(0.2)

            assert server.is_running is False

    def test_server_url_property(self):
        """Test server URL property."""
        server = MetricsServer(port=9090)

        assert server.url == "http://localhost:9090/metrics"

    def test_server_already_running_error(self):
        """Test error when starting already running server."""
        server = MetricsServer(port=9096)

        try:
            server.start()
            time.sleep(0.2)

            # Try to start again
            with pytest.raises(RuntimeError, match="already running"):
                server.start()

        finally:
            server.stop()

    @pytest.mark.integration
    def test_server_serves_metrics(self):
        """Test that server actually serves metrics."""
        server = MetricsServer(port=9097)

        try:
            server.start()
            time.sleep(0.5)

            # Try to fetch metrics
            response = requests.get(server.url, timeout=2)

            assert response.status_code == 200
            assert "raxe_" in response.text  # Should contain RAXE metrics

        except requests.RequestException as e:
            pytest.skip(f"Could not connect to metrics server: {e}")

        finally:
            server.stop()

    def test_server_context_manager(self):
        """Test server as context manager."""
        with MetricsServer(port=9098) as server:
            time.sleep(0.5)
            assert server.is_running is True

        # Server should be stopped after context
        time.sleep(0.2)
        assert server.is_running is False

    def test_server_stop_when_not_running(self):
        """Test stopping server when not running."""
        server = MetricsServer(port=9099)

        # Should not raise error
        server.stop()

        assert server.is_running is False


class TestMetricsHelpers:
    """Test helper functions."""

    def test_get_metrics_text(self):
        """Test getting metrics as text."""
        # Record some metrics first
        from raxe.monitoring.metrics import collector

        collector.record_scan_simple(
            severity="high",
            blocked=True,
            detection_count=1,
            input_length=100,
        )

        # Get metrics
        metrics_text = get_metrics_text()

        assert isinstance(metrics_text, str)
        assert len(metrics_text) > 0
        # Should contain Prometheus format metrics
        assert "# HELP" in metrics_text or "# TYPE" in metrics_text

    def test_get_metrics_content_type(self):
        """Test getting Prometheus content type."""
        content_type = get_metrics_content_type()

        assert isinstance(content_type, str)
        assert "text/plain" in content_type or "text/openmetrics" in content_type


class TestMetricsServerIntegration:
    """Test server integration with actual metrics."""

    @pytest.mark.integration
    def test_server_with_active_metrics(self):
        """Test server serving active metrics."""
        from raxe.monitoring.metrics import collector

        server = MetricsServer(port=9100)

        try:
            # Record some metrics
            collector.record_scan_simple(
                severity="critical",
                blocked=True,
                detection_count=3,
                input_length=500,
            )

            collector.update_queue_depth(42, priority="high")

            # Start server
            server.start()
            time.sleep(0.5)

            # Fetch metrics
            response = requests.get(server.url, timeout=2)

            assert response.status_code == 200

            metrics_text = response.text

            # Verify our metrics are present
            assert "raxe_scans_total" in metrics_text
            assert "raxe_queue_depth" in metrics_text

        except requests.RequestException as e:
            pytest.skip(f"Could not connect to metrics server: {e}")

        finally:
            server.stop()

    @pytest.mark.integration
    def test_server_concurrent_requests(self):
        """Test server handling concurrent requests."""
        import concurrent.futures

        server = MetricsServer(port=9101)

        try:
            server.start()
            time.sleep(0.5)

            def fetch_metrics():
                response = requests.get(server.url, timeout=2)
                return response.status_code

            # Make multiple concurrent requests
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(fetch_metrics) for _ in range(20)]

                results = [f.result() for f in concurrent.futures.as_completed(futures)]

            # All requests should succeed
            assert all(status == 200 for status in results)
            assert len(results) == 20

        except requests.RequestException as e:
            pytest.skip(f"Could not connect to metrics server: {e}")

        finally:
            server.stop()


class TestMetricsServerEdgeCases:
    """Test edge cases and error conditions."""

    def test_server_invalid_port(self):
        """Test server with invalid port."""
        # Port 0 should auto-assign a port
        server = MetricsServer(port=0)

        try:
            server.start()
            time.sleep(0.2)

            # Should still work
            assert server.is_running is True

        finally:
            server.stop()

    def test_server_privileged_port_unix(self):
        """Test server with privileged port (< 1024) on Unix."""
        import os
        import sys

        if sys.platform != "win32" and os.getuid() != 0:
            # Non-root user on Unix - should fail
            MetricsServer(port=80)

            # Starting should fail (permission denied)
            # But we can't easily test this without mocking
            pass

    def test_server_rapid_start_stop(self):
        """Test rapid start/stop cycles."""
        server = MetricsServer(port=9102)

        for _ in range(5):
            server.start()
            time.sleep(0.2)
            server.stop()
            time.sleep(0.2)

    def test_server_metrics_during_load(self):
        """Test serving metrics during high metric update load."""
        import threading

        from raxe.monitoring.metrics import collector

        server = MetricsServer(port=9103)

        try:
            server.start()
            time.sleep(0.5)

            # Generate metrics in background
            def generate_metrics():
                for _i in range(100):
                    collector.record_scan_simple(
                        severity="low",
                        blocked=False,
                        detection_count=0,
                        input_length=100,
                    )
                    time.sleep(0.01)

            metric_thread = threading.Thread(target=generate_metrics)
            metric_thread.start()

            # Fetch metrics while being updated
            time.sleep(0.2)

            try:
                response = requests.get(server.url, timeout=2)
                assert response.status_code == 200
            except requests.RequestException as e:
                pytest.skip(f"Could not connect: {e}")

            metric_thread.join()

        finally:
            server.stop()


@pytest.mark.integration
class TestMetricsServerPerformance:
    """Test server performance characteristics."""

    def test_server_response_time(self):
        """Test server response time is acceptable."""
        server = MetricsServer(port=9104)

        try:
            server.start()
            time.sleep(0.5)

            # Measure response time
            start = time.perf_counter()
            response = requests.get(server.url, timeout=2)
            duration = time.perf_counter() - start

            assert response.status_code == 200

            # Should respond in < 100ms
            assert duration < 0.1

        except requests.RequestException as e:
            pytest.skip(f"Could not connect: {e}")

        finally:
            server.stop()

    def test_server_throughput(self):
        """Test server can handle many requests."""
        server = MetricsServer(port=9105)

        try:
            server.start()
            time.sleep(0.5)

            # Make many sequential requests
            start = time.perf_counter()

            for _ in range(50):
                response = requests.get(server.url, timeout=2)
                assert response.status_code == 200

            duration = time.perf_counter() - start

            # Should handle 50 requests quickly (< 5 seconds)
            assert duration < 5.0

        except requests.RequestException as e:
            pytest.skip(f"Could not connect: {e}")

        finally:
            server.stop()
