"""Test L2 model loading with ONNX/bundle/stub fallback chain."""

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from raxe.sdk.client import Raxe


class TestL2ModelLoading:
    """Test L2 model loading behavior and fallback chain."""

    @pytest.mark.requires_models
    def test_onnx_model_preferred(self):
        """Test ONNX model is loaded when available."""
        client = Raxe()

        # Check initialization stats
        stats = client.preload_stats
        assert stats.l2_duration_ms is not None

        # If ONNX is available, it should be loaded
        # This is implementation-specific, but we can check for indicators
        if hasattr(stats, "l2_model_type"):
            if stats.l2_model_type == "onnx":
                # ONNX should load faster than bundle
                assert stats.l2_duration_ms < 500

    def test_model_discovery_automatic(self):
        """Test automatic model discovery finds ONNX models."""
        # Check if ONNX models exist
        model_dir = Path("models") / "deberta_v3_base_prompt_injection_v2"
        onnx_int8 = model_dir / "onnx" / "int8" / "model.onnx"

        client = Raxe()

        if onnx_int8.exists():
            # Should have found and loaded ONNX
            stats = client.preload_stats
            # ONNX loading should be relatively fast
            assert stats.l2_duration_ms < 1000

    def test_bundle_fallback_when_no_onnx(self):
        """Test fallback to bundle when ONNX unavailable."""
        # Mock ONNX unavailable
        with patch("raxe.infrastructure.models.detector_factory._try_load_onnx") as mock_onnx:
            mock_onnx.return_value = None

            client = Raxe()
            stats = client.preload_stats

            # Should still initialize (using bundle or stub)
            assert client._initialized
            assert stats.l2_duration_ms is not None

    def test_stub_fallback_when_no_models(self):
        """Test fallback to stub when no models available."""
        # Mock both ONNX and bundle unavailable
        with (
            patch("raxe.infrastructure.models.detector_factory._try_load_onnx") as mock_onnx,
            patch("raxe.infrastructure.models.detector_factory._try_load_bundle") as mock_bundle,
        ):
            mock_onnx.return_value = None
            mock_bundle.return_value = None

            client = Raxe()

            # Should still initialize with stub
            assert client._initialized

            # Stub should be very fast
            stats = client.preload_stats
            if hasattr(stats, "l2_model_type") and stats.l2_model_type == "stub":
                assert stats.l2_duration_ms < 10

    def test_eager_loading_no_timeout(self):
        """Test eager L2 loading completes without timeout."""
        start = time.perf_counter()
        client = Raxe()
        init_time_ms = (time.perf_counter() - start) * 1000

        # Should complete initialization without timeout
        assert client._initialized
        assert init_time_ms < 5000  # Should not timeout (old timeout was 5s)

        # L2 should be loaded during init
        stats = client.preload_stats
        assert stats.l2_duration_ms is not None
        assert stats.l2_duration_ms > 0

    def test_no_lazy_loading(self):
        """Test L2 is not lazily loaded (eager loading)."""
        client = Raxe()

        # L2 should already be loaded
        stats = client.preload_stats
        assert stats.l2_duration_ms > 0

        # First scan should not trigger L2 loading
        start = time.perf_counter()
        client.scan("Test prompt")
        first_scan_ms = (time.perf_counter() - start) * 1000

        # First scan should be fast (L2 already loaded)
        assert first_scan_ms < 200  # Should not include model loading time

    def test_l2_disabled_no_loading(self):
        """Test L2 is not loaded when disabled."""
        start = time.perf_counter()
        client = Raxe(l2_enabled=False)
        init_time_ms = (time.perf_counter() - start) * 1000

        # Should be faster without L2
        assert init_time_ms < 300

        stats = client.preload_stats
        # L2 duration should be 0 or very small
        assert stats.l2_duration_ms == 0 or stats.l2_duration_ms < 10

    def test_model_loading_error_handling(self):
        """Test graceful handling of model loading errors."""
        with patch("raxe.infrastructure.models.detector_factory.create_l2_detector") as mock_create:
            # Simulate loading error
            mock_create.side_effect = Exception("Model corrupt")

            # Should still initialize (with stub fallback)
            client = Raxe()
            assert client._initialized

            # Should be able to scan (using L1 only or stub)
            result = client.scan("Test prompt")
            assert result is not None

    def test_model_version_detection(self):
        """Test detection of model version."""
        client = Raxe()

        # Check if model version is tracked
        if hasattr(client.preload_stats, "l2_model_version"):
            version = client.preload_stats.l2_model_version
            assert version is not None
            # Should be deberta v2 or similar
            assert "deberta" in version.lower() or "v2" in version

    def test_onnx_int8_optimization(self):
        """Test ONNX INT8 model is used for optimization."""
        model_dir = Path("models") / "deberta_v3_base_prompt_injection_v2"
        onnx_int8 = model_dir / "onnx" / "int8" / "model.onnx"

        if onnx_int8.exists():
            client = Raxe()

            # INT8 should be fast
            stats = client.preload_stats
            assert stats.l2_duration_ms < 1000

            # Inference should be fast too
            start = time.perf_counter()
            client.scan("Test prompt for INT8 model")
            inference_ms = (time.perf_counter() - start) * 1000

            assert inference_ms < 150  # INT8 should meet <150ms target

    def test_model_warmup_during_init(self):
        """Test model warmup happens during initialization."""
        client = Raxe()

        # Model should be warmed up
        stats = client.preload_stats
        assert stats.l2_duration_ms > 0

        # First real scan should be fast (model pre-warmed)
        scan_times = []
        for i in range(3):
            start = time.perf_counter()
            client.scan(f"Test prompt {i}")
            scan_times.append((time.perf_counter() - start) * 1000)

        # All scans should be consistently fast
        assert all(t < 200 for t in scan_times)
        # No significant warmup on first scan
        assert scan_times[0] < scan_times[1] * 2

    def test_model_memory_efficiency(self, memory_tracker):
        """Test model loading memory efficiency."""
        memory_tracker.reset_baseline()

        # Load with L2
        Raxe(l2_enabled=True)
        with_l2_memory = memory_tracker.get_delta_mb()

        memory_tracker.reset_baseline()

        # Load without L2
        Raxe(l2_enabled=False)
        without_l2_memory = memory_tracker.get_delta_mb()

        # L2 model should add reasonable memory (<500MB for INT8)
        memory_difference = with_l2_memory - without_l2_memory
        if memory_difference > 0:
            assert memory_difference < 500, f"L2 model uses {memory_difference:.1f}MB"

    @pytest.mark.slow
    def test_model_loading_stress(self):
        """Test rapid model loading under stress."""
        load_times = []

        for _i in range(3):
            start = time.perf_counter()
            client = Raxe()
            load_times.append((time.perf_counter() - start) * 1000)

            # Scan to ensure model works
            result = client.scan("Stress test prompt")
            assert result is not None

        # All should load successfully
        assert all(t < 5000 for t in load_times)

        # Loading times should be consistent
        avg_time = sum(load_times) / len(load_times)
        assert all(abs(t - avg_time) < avg_time * 0.5 for t in load_times)

    def test_backward_compatibility_lazy_l2(self):
        """Test backward compatibility with LazyL2Detector."""
        # If old LazyL2Detector exists, it should still work
        try:
            from raxe.infrastructure.models.lazy_l2_detector import LazyL2Detector

            detector = LazyL2Detector()
            # Should not timeout or error
            result = detector.detect("Test prompt")
            assert result is not None

        except ImportError:
            # LazyL2Detector might be removed - that's ok
            pytest.skip("LazyL2Detector not available")
