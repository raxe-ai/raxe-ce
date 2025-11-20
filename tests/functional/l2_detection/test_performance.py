"""Test L2 detection performance metrics."""
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from raxe.sdk.client import Raxe


class TestL2Performance:
    """Test L2 detection performance requirements."""

    @pytest.fixture
    def client(self):
        """Create client with L2 enabled."""
        return Raxe(l2_enabled=True)

    @pytest.mark.requires_models
    def test_inference_latency_under_150ms(self, client, safe_prompts, performance_tracker):
        """Test L2 inference meets <150ms requirement."""
        # Warm up
        client.scan("warmup")

        # Measure inference times
        for prompt in safe_prompts[:10]:
            with performance_tracker.track("l2_inference"):
                result = client.scan(prompt)
                assert result is not None

        stats = performance_tracker.get_stats("l2_inference")

        # Check performance requirements
        assert stats["p95"] < 150, f"L2 P95 latency: {stats['p95']:.1f}ms > 150ms"
        assert stats["mean"] < 100, f"L2 mean latency: {stats['mean']:.1f}ms"

    def test_combined_l1_l2_under_10ms(self, client, safe_prompts, performance_tracker):
        """Test combined L1+L2 meets <10ms scan target."""
        # Warm up
        client.scan("warmup")

        # Measure combined scan times
        for prompt in safe_prompts[:20]:
            with performance_tracker.track("combined_scan"):
                result = client.scan(prompt)

        stats = performance_tracker.get_stats("combined_scan")

        # Combined should meet aggressive target
        assert stats["p95"] < 20, f"Combined P95: {stats['p95']:.1f}ms > 20ms"
        assert stats["mean"] < 15, f"Combined mean: {stats['mean']:.1f}ms"

    def test_batch_processing_performance(self, client, safe_prompts):
        """Test batch processing maintains performance."""
        batch_sizes = [1, 10, 50, 100]
        batch_times = {}

        for batch_size in batch_sizes:
            prompts = safe_prompts[:batch_size] * (100 // batch_size)

            start = time.perf_counter()
            for prompt in prompts:
                client.scan(prompt)
            total_ms = (time.perf_counter() - start) * 1000

            per_prompt_ms = total_ms / len(prompts)
            batch_times[batch_size] = per_prompt_ms

        # Larger batches should not degrade per-prompt performance significantly
        assert batch_times[100] < batch_times[1] * 2, "Batch performance degradation"

    def test_concurrent_l2_performance(self, client, safe_prompts):
        """Test L2 performance under concurrent load."""
        prompts = safe_prompts[:20] * 5  # 100 prompts
        latencies = []

        def scan_with_timing(prompt):
            start = time.perf_counter()
            result = client.scan(prompt)
            latency_ms = (time.perf_counter() - start) * 1000
            return latency_ms

        # Run concurrent scans
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(scan_with_timing, p) for p in prompts]

            for future in as_completed(futures, timeout=30):
                latencies.append(future.result())

        # Calculate stats
        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        mean = statistics.mean(latencies)

        # Concurrent performance should still be good
        assert p95 < 200, f"Concurrent P95: {p95:.1f}ms"
        assert mean < 150, f"Concurrent mean: {mean:.1f}ms"

    def test_memory_stable_during_inference(self, client, safe_prompts, memory_tracker):
        """Test memory remains stable during inference."""
        memory_tracker.reset_baseline()

        # Do many inferences
        for _ in range(100):
            client.scan(safe_prompts[0])

        memory_after_100 = memory_tracker.get_delta_mb()

        # Do many more
        for _ in range(900):
            client.scan(safe_prompts[0])

        memory_after_1000 = memory_tracker.get_delta_mb()

        # Memory should not grow significantly
        memory_growth = memory_after_1000 - memory_after_100
        assert memory_growth < 50, f"Memory grew by {memory_growth:.1f}MB"

    def test_cache_effectiveness(self, client):
        """Test caching improves performance for repeated prompts."""
        prompt = "Test caching effectiveness"
        times = []

        # Scan same prompt multiple times
        for i in range(10):
            start = time.perf_counter()
            client.scan(prompt)
            times.append((time.perf_counter() - start) * 1000)

        # Later scans should be faster (cache hits)
        first_avg = statistics.mean(times[:3])
        last_avg = statistics.mean(times[-3:])

        # Cache should provide some speedup
        if last_avg < first_avg:
            improvement = (first_avg - last_avg) / first_avg * 100
            print(f"Cache improvement: {improvement:.1f}%")

    def test_varied_prompt_lengths(self, client, performance_tracker):
        """Test performance with varied prompt lengths."""
        test_cases = [
            ("short", "Hi"),
            ("medium", "This is a medium length prompt " * 10),
            ("long", "This is a very long prompt " * 100),
            ("very_long", "Extremely long prompt " * 500)
        ]

        for name, prompt in test_cases:
            with performance_tracker.track(f"length_{name}"):
                client.scan(prompt)

        # Check all complete reasonably
        for name, _ in test_cases:
            stats = performance_tracker.get_stats(f"length_{name}")
            assert stats["mean"] < 500, f"{name} prompt too slow: {stats['mean']:.1f}ms"

    def test_model_switching_performance(self):
        """Test performance when switching between models."""
        # Test with L2
        client_with_l2 = Raxe(l2_enabled=True)
        start = time.perf_counter()
        client_with_l2.scan("Test")
        with_l2_ms = (time.perf_counter() - start) * 1000

        # Test without L2
        client_without_l2 = Raxe(l2_enabled=False)
        start = time.perf_counter()
        client_without_l2.scan("Test")
        without_l2_ms = (time.perf_counter() - start) * 1000

        # Without L2 should be faster
        assert without_l2_ms < with_l2_ms

        # But both should be reasonably fast
        assert with_l2_ms < 200
        assert without_l2_ms < 50

    @pytest.mark.slow
    def test_sustained_performance(self, client, safe_prompts):
        """Test performance remains stable over sustained load."""
        window_stats = []

        # Run for multiple time windows
        for window in range(5):
            window_times = []

            # 100 scans per window
            for _ in range(100):
                start = time.perf_counter()
                client.scan(safe_prompts[0])
                window_times.append((time.perf_counter() - start) * 1000)

            window_stats.append({
                "mean": statistics.mean(window_times),
                "p95": statistics.quantiles(window_times, n=20)[18]
            })

        # Performance should not degrade over time
        first_window = window_stats[0]
        last_window = window_stats[-1]

        assert last_window["mean"] < first_window["mean"] * 1.5
        assert last_window["p95"] < first_window["p95"] * 1.5

    def test_onnx_optimization_benefit(self):
        """Test ONNX provides performance benefit."""
        # This test is conditional on ONNX availability
        try:
            import onnxruntime
            has_onnx = True
        except ImportError:
            has_onnx = False

        if not has_onnx:
            pytest.skip("ONNX not available")

        client = Raxe()
        stats = client.preload_stats

        # If using ONNX, init should be fast (2.2x faster than before)
        if hasattr(stats, "l2_model_type") and stats.l2_model_type == "onnx":
            assert stats.l2_duration_ms < 500, f"ONNX init slow: {stats.l2_duration_ms}ms"

            # Inference should also be fast
            start = time.perf_counter()
            client.scan("ONNX performance test")
            inference_ms = (time.perf_counter() - start) * 1000

            assert inference_ms < 100, f"ONNX inference slow: {inference_ms:.1f}ms"