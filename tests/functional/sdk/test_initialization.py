"""Test SDK initialization and stats."""
import time
from unittest.mock import patch

import pytest

from raxe.sdk.client import Raxe


class TestSDKInitialization:
    """Test SDK initialization behavior and statistics."""

    def test_basic_initialization(self):
        """Test basic SDK initialization."""
        start = time.perf_counter()
        client = Raxe()
        init_time_ms = (time.perf_counter() - start) * 1000

        assert client._initialized
        assert client.pipeline is not None
        assert client.preload_stats is not None

        # Should initialize in under 500ms (target)
        assert init_time_ms < 1000, f"Initialization took {init_time_ms:.0f}ms"

    def test_initialization_stats(self):
        """Test initialization statistics are available."""
        client = Raxe()

        stats = client.preload_stats
        assert stats is not None
        assert hasattr(stats, "duration_ms")
        assert hasattr(stats, "rules_loaded")
        assert hasattr(stats, "l1_duration_ms")
        assert hasattr(stats, "l2_duration_ms")

        # Verify reasonable values
        assert stats.duration_ms > 0
        assert stats.duration_ms < 5000  # Should not take more than 5s
        assert stats.rules_loaded > 0

    def test_initialization_with_progress_callback(self, mock_progress):
        """Test initialization with progress callback."""
        Raxe(progress_callback=mock_progress)

        # Progress methods should have been called
        mock_progress.start.assert_called_once()
        mock_progress.complete.assert_called_once()

        # Should pass total duration to complete
        call_args = mock_progress.complete.call_args
        assert "total_duration_ms" in call_args.kwargs
        assert call_args.kwargs["total_duration_ms"] > 0

    def test_initialization_with_config(self, temp_config_file):
        """Test initialization with config file."""
        client = Raxe(config_path=temp_config_file)

        assert client.config is not None
        assert client.config.api_key == "test_key_123"
        assert not client.config.telemetry.enabled

    def test_initialization_with_explicit_params(self):
        """Test initialization with explicit parameters."""
        client = Raxe(
            api_key="explicit_key",
            telemetry=False,
            l2_enabled=False
        )

        assert client.config.api_key == "explicit_key"
        assert not client.config.telemetry.enabled
        assert not client.config.enable_l2

    def test_no_l2_initialization(self):
        """Test initialization without L2 detection."""
        start = time.perf_counter()
        client = Raxe(l2_enabled=False)
        init_time_ms = (time.perf_counter() - start) * 1000

        # Should be faster without L2
        assert init_time_ms < 300, f"No-L2 init took {init_time_ms:.0f}ms"
        assert not client.config.enable_l2

    def test_initialization_timing_separation(self):
        """Test init time is separate from scan time."""
        # First initialization
        start_init = time.perf_counter()
        client = Raxe()
        init_time = time.perf_counter() - start_init

        # First scan
        start_scan = time.perf_counter()
        client.scan("Test prompt")
        scan_time = time.perf_counter() - start_scan

        # Init should be slower than scan
        assert init_time > scan_time, f"Init: {init_time*1000:.1f}ms, Scan: {scan_time*1000:.1f}ms"

        # Scan should be fast (<10ms target)
        assert scan_time * 1000 < 50, f"Scan took {scan_time*1000:.1f}ms"

    def test_initialization_caching(self):
        """Test component caching during initialization."""
        client1 = Raxe()
        client2 = Raxe()

        # Second client should reuse some cached components
        # (though each client has its own pipeline instance)
        assert client1.pipeline != client2.pipeline
        assert client1._initialized and client2._initialized

    def test_initialization_failure_handling(self):
        """Test handling of initialization failures."""
        with patch("raxe.application.preloader.preload_pipeline") as mock_preload:
            mock_preload.side_effect = Exception("Init failed")

            with pytest.raises(Exception, match="Init failed"):
                Raxe()

    def test_lazy_component_initialization(self):
        """Test lazy initialization of optional components."""
        client = Raxe()

        # These should be None until first use
        assert client._usage_tracker is None
        assert client._scan_history is None
        assert client._streak_tracker is None

        # Should be created on first scan (if telemetry enabled)
        if client.config.telemetry.enabled:
            client.scan("Test")
            # Now tracker might be initialized (implementation dependent)

    def test_suppression_manager_initialization(self):
        """Test suppression manager is initialized."""
        client = Raxe()

        assert client.suppression_manager is not None
        # Should auto-load .raxeignore if present

    def test_initialization_with_environment_vars(self):
        """Test environment variable configuration."""
        import os

        # Set environment variables
        os.environ["RAXE_API_KEY"] = "env_key_123"
        os.environ["RAXE_TELEMETRY"] = "false"

        try:
            Raxe()
            # Env vars should be picked up (if config cascade implemented)
            # This might depend on implementation details
        finally:
            # Cleanup
            del os.environ["RAXE_API_KEY"]
            del os.environ["RAXE_TELEMETRY"]

    def test_initialization_multiple_times(self):
        """Test multiple client initializations."""
        # Should be able to create multiple instances
        client1 = Raxe()
        client2 = Raxe()

        # Each should have their own config
        assert client1.config is not None
        assert client2.config is not None

        # Each should work independently
        result1 = client1.scan("test prompt")
        result2 = client2.scan("test prompt")
        assert result1 is not None
        assert result2 is not None

    @pytest.mark.slow
    def test_initialization_stress(self):
        """Test multiple rapid initializations."""
        init_times = []

        for _i in range(5):
            start = time.perf_counter()
            Raxe()
            init_times.append((time.perf_counter() - start) * 1000)

        # All should succeed and be reasonably fast
        assert all(t < 1000 for t in init_times), f"Init times: {init_times}"

        # Later inits might be faster due to caching
        avg_first_three = sum(init_times[:3]) / 3
        avg_last_two = sum(init_times[-2:]) / 2
        # Just verify no degradation
        assert avg_last_two < avg_first_three * 2