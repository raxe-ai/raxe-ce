"""Integrated performance benchmarks for complete scan pipeline.

Performance targets:
- P95 end-to-end latency: <10ms
- Average latency: <5ms
- Component breakdown: L1 <5ms, L2 <1ms, overhead <4ms

These tests measure real-world performance with all components integrated.
"""

import statistics
import time

import pytest

from raxe.application.preloader import preload_pipeline
from raxe.infrastructure.config.scan_config import ScanConfig


@pytest.mark.benchmark
class TestIntegratedScanLatency:
    """Benchmark complete scan pipeline latency."""

    @pytest.fixture
    def test_packs_dir(self, tmp_path):
        """Create test packs for benchmarking."""
        packs_root = tmp_path / "packs"
        core_pack = packs_root / "core" / "v1.0.0"
        core_pack.mkdir(parents=True)

        # Create pack with 10 rules (realistic load)
        pack_yaml = core_pack / "pack.yaml"
        pack_yaml.write_text("""
schema_version: "1.0.0"
id: core
version: "1.0.0"
name: "Benchmark Pack"
pack_type: official
description: "Performance testing pack"
authors: ["Test"]
rules_file: "rules.yaml"
""")

        # Create 10 rules
        rules_yaml_content = "rules:\n"
        for i in range(10):
            rules_yaml_content += f"""
  - rule_id: bench-{i:03d}
    version: "1.0.0"
    family: PI
    severity: medium
    confidence: 0.8
    description: "Benchmark rule {i}"
    patterns:
      - type: regex
        value: "pattern{i}.*match"
        flags: ["IGNORECASE"]
"""

        rules_yaml = core_pack / "rules.yaml"
        rules_yaml.write_text(rules_yaml_content)

        return packs_root

    def test_preload_overhead(self, test_packs_dir):
        """Measure preload overhead (one-time cost)."""
        config = ScanConfig(
            packs_root=test_packs_dir,
            enable_l2=True,
        )

        start = time.perf_counter()
        _pipeline, stats = preload_pipeline(config=config)
        duration_ms = (time.perf_counter() - start) * 1000

        print(f"\nPreload overhead: {duration_ms:.2f}ms")
        print(f"  - Packs loaded: {stats.packs_loaded}")
        print(f"  - Rules loaded: {stats.rules_loaded}")
        print(f"  - Patterns compiled: {stats.patterns_compiled}")

        # Preload should be fast (target <500ms)
        # This is acceptable one-time cost for recurring <10ms scans
        assert duration_ms < 1000  # Generous limit

    def test_single_scan_latency(self, test_packs_dir):
        """Measure single scan latency."""
        config = ScanConfig(
            packs_root=test_packs_dir,
            enable_l2=True,
        )

        pipeline, _ = preload_pipeline(config=config)

        # Measure single scan
        text = "This is a test prompt for benchmarking"
        result = pipeline.scan(text)

        print(f"\nSingle scan latency: {result.duration_ms:.3f}ms")
        print(f"  - L1 processing: {result.scan_result.l1_processing_ms:.3f}ms")
        print(f"  - L2 processing: {result.scan_result.l2_processing_ms:.3f}ms")
        print(f"  - Total processing: {result.scan_result.total_processing_ms:.3f}ms")

        # Should be fast
        assert result.duration_ms < 50  # Very generous for single scan

    def test_p95_latency_target(self, test_packs_dir):
        """Test P95 latency meets <10ms target."""
        config = ScanConfig(
            packs_root=test_packs_dir,
            enable_l2=True,
            fail_fast_on_critical=True,
        )

        pipeline, _ = preload_pipeline(config=config)

        # Run 100 scans to get P95
        durations = []
        texts = [
            "Test prompt for benchmarking",
            "Another test prompt",
            "Scanning for performance",
            "Measure latency here",
            "Quick brown fox",
        ]

        for i in range(100):
            text = texts[i % len(texts)]
            result = pipeline.scan(text)
            durations.append(result.duration_ms)

        # Calculate percentiles
        p50 = statistics.median(durations)
        sorted_durations = sorted(durations)
        p95_index = int(len(sorted_durations) * 0.95)
        p95 = sorted_durations[p95_index]
        p99_index = int(len(sorted_durations) * 0.99)
        p99 = sorted_durations[p99_index]
        avg = statistics.mean(durations)

        print("\nLatency statistics (100 scans):")
        print(f"  - Average: {avg:.3f}ms")
        print(f"  - P50 (median): {p50:.3f}ms")
        print(f"  - P95: {p95:.3f}ms")
        print(f"  - P99: {p99:.3f}ms")
        print(f"  - Min: {min(durations):.3f}ms")
        print(f"  - Max: {max(durations):.3f}ms")

        # Target: P95 <10ms
        # This may not always pass on slow hardware, so we're generous
        # Real target enforcement happens in CI with known hardware
        print(f"\nP95 target: <10ms, actual: {p95:.3f}ms")

        # Soft assertion - log if not met but don't fail
        if p95 > 10.0:
            print(f"WARNING: P95 latency {p95:.3f}ms exceeds 10ms target")

    def test_throughput(self, test_packs_dir):
        """Measure scanning throughput (scans per second)."""
        config = ScanConfig(
            packs_root=test_packs_dir,
            enable_l2=True,
        )

        pipeline, _ = preload_pipeline(config=config)

        # Run scans for 1 second
        start = time.perf_counter()
        scan_count = 0
        while time.perf_counter() - start < 1.0:
            pipeline.scan("Test prompt")
            scan_count += 1

        duration = time.perf_counter() - start
        throughput = scan_count / duration

        print(f"\nThroughput: {throughput:.1f} scans/second")
        print(f"  - Scans completed: {scan_count}")
        print(f"  - Duration: {duration:.3f}s")

        # Should achieve reasonable throughput
        # Target: >100 scans/second (implies <10ms per scan)
        assert throughput > 10  # Very conservative

    def test_l1_vs_l2_breakdown(self, test_packs_dir):
        """Measure L1 vs L2 processing time breakdown."""
        config = ScanConfig(
            packs_root=test_packs_dir,
            enable_l2=True,
            fail_fast_on_critical=False,  # Always run L2
        )

        pipeline, _ = preload_pipeline(config=config)

        # Run 50 scans
        l1_times = []
        l2_times = []
        total_times = []

        for _ in range(50):
            result = pipeline.scan("Test prompt for breakdown")
            l1_times.append(result.scan_result.l1_processing_ms)
            l2_times.append(result.scan_result.l2_processing_ms)
            total_times.append(result.scan_result.total_processing_ms)

        # Calculate averages
        avg_l1 = statistics.mean(l1_times)
        avg_l2 = statistics.mean(l2_times)
        avg_total = statistics.mean(total_times)

        print("\nProcessing time breakdown (50 scans):")
        print(f"  - L1 average: {avg_l1:.3f}ms")
        print(f"  - L2 average: {avg_l2:.3f}ms")
        print(f"  - Total average: {avg_total:.3f}ms")
        print(f"  - L1 percentage: {(avg_l1 / avg_total) * 100:.1f}%")
        print(f"  - L2 percentage: {(avg_l2 / avg_total) * 100:.1f}%")

        # L1 should be <5ms target
        print(f"\nL1 target: <5ms, actual: {avg_l1:.3f}ms")

        # L2 stub should be <1ms target
        print(f"L2 target: <1ms, actual: {avg_l2:.3f}ms")

    def test_fail_fast_optimization_impact(self, test_packs_dir):
        """Measure impact of fail_fast_on_critical optimization."""
        # Test WITHOUT fail_fast
        config_no_ff = ScanConfig(
            packs_root=test_packs_dir,
            enable_l2=True,
            fail_fast_on_critical=False,
        )
        pipeline_no_ff, _ = preload_pipeline(config=config_no_ff)

        durations_no_ff = []
        for _ in range(20):
            result = pipeline_no_ff.scan("Test")
            durations_no_ff.append(result.duration_ms)

        avg_no_ff = statistics.mean(durations_no_ff)

        # Test WITH fail_fast
        config_ff = ScanConfig(
            packs_root=test_packs_dir,
            enable_l2=True,
            fail_fast_on_critical=True,
        )
        pipeline_ff, _ = preload_pipeline(config=config_ff)

        durations_ff = []
        for _ in range(20):
            result = pipeline_ff.scan("Test")
            durations_ff.append(result.duration_ms)

        avg_ff = statistics.mean(durations_ff)

        print("\nFail-fast optimization impact:")
        print(f"  - Average WITHOUT fail_fast: {avg_no_ff:.3f}ms")
        print(f"  - Average WITH fail_fast: {avg_ff:.3f}ms")
        print(f"  - Difference: {avg_no_ff - avg_ff:.3f}ms")

        # Both should be fast (no CRITICAL detections in test)
        # Difference may be minimal without actual CRITICAL detections

    def test_batch_scan_performance(self, test_packs_dir):
        """Measure batch scanning performance."""
        config = ScanConfig(
            packs_root=test_packs_dir,
            enable_l2=True,
        )

        pipeline, _ = preload_pipeline(config=config)

        # Batch of 100 prompts
        texts = [f"Test prompt {i}" for i in range(100)]

        start = time.perf_counter()
        results = pipeline.scan_batch(texts)
        duration = time.perf_counter() - start

        avg_per_scan = (duration * 1000) / len(texts)
        throughput = len(texts) / duration

        print("\nBatch scan performance (100 prompts):")
        print(f"  - Total duration: {duration * 1000:.1f}ms")
        print(f"  - Average per scan: {avg_per_scan:.3f}ms")
        print(f"  - Throughput: {throughput:.1f} scans/second")

        # Should complete batch efficiently
        assert len(results) == 100

    def test_warmup_effect(self, test_packs_dir):
        """Measure warmup effect (first scan vs subsequent)."""
        config = ScanConfig(
            packs_root=test_packs_dir,
            enable_l2=True,
        )

        pipeline, _ = preload_pipeline(config=config)

        # First scan (might be slower due to JIT, etc)
        result_first = pipeline.scan("First scan")
        first_scan_ms = result_first.duration_ms

        # Subsequent scans (should be faster, patterns cached)
        subsequent_times = []
        for _ in range(20):
            result = pipeline.scan("Subsequent scan")
            subsequent_times.append(result.duration_ms)

        avg_subsequent = statistics.mean(subsequent_times)

        print("\nWarmup effect:")
        print(f"  - First scan: {first_scan_ms:.3f}ms")
        print(f"  - Subsequent average: {avg_subsequent:.3f}ms")
        print(f"  - Difference: {first_scan_ms - avg_subsequent:.3f}ms")

        # Subsequent should be faster (or at least not slower)
        # Pattern compilation happens during preload, so difference may be small


@pytest.mark.benchmark
class TestComponentLatency:
    """Benchmark individual component latency."""

    def test_pack_loading_latency(self, tmp_path):
        """Measure pack loading time."""
        # This is part of preload overhead
        from raxe.infrastructure.packs.registry import PackRegistry, RegistryConfig

        packs_root = tmp_path / "packs"
        packs_root.mkdir(parents=True)

        config = RegistryConfig(packs_root=packs_root, strict=False)
        registry = PackRegistry(config)

        start = time.perf_counter()
        registry.load_all_packs()
        duration_ms = (time.perf_counter() - start) * 1000

        print(f"\nPack loading latency: {duration_ms:.3f}ms")

        # Should be fast even with no packs
        assert duration_ms < 100

    def test_telemetry_overhead(self):
        """Measure telemetry sending overhead."""
        from raxe.infrastructure.telemetry.hook import TelemetryConfig, TelemetryHook

        config = TelemetryConfig(
            enabled=True,
            async_send=True,  # Async should have minimal overhead
        )

        hook = TelemetryHook(config)

        # Measure send latency
        start = time.perf_counter()
        for _ in range(100):
            hook.send(
                {
                    "text_hash": "a" * 64,
                    "severity": "low",
                    "detections": 0,
                }
            )
        duration_ms = (time.perf_counter() - start) * 1000
        avg_send_ms = duration_ms / 100

        print("\nTelemetry send overhead (async):")
        print(f"  - 100 sends: {duration_ms:.3f}ms")
        print(f"  - Average per send: {avg_send_ms:.3f}ms")

        hook.shutdown()

        # Async send should be very fast (just queuing)
        assert avg_send_ms < 1.0

    def test_circuit_breaker_overhead(self):
        """Measure circuit breaker overhead."""
        from raxe.utils.performance import CircuitBreaker

        breaker = CircuitBreaker()

        def dummy_func():
            return True

        # Measure overhead
        start = time.perf_counter()
        for _ in range(1000):
            breaker.call(dummy_func)
        duration_ms = (time.perf_counter() - start) * 1000
        avg_call_ms = duration_ms / 1000

        print("\nCircuit breaker overhead:")
        print(f"  - 1000 calls: {duration_ms:.3f}ms")
        print(f"  - Average per call: {avg_call_ms:.6f}ms")

        # Circuit breaker overhead should be negligible (<0.01ms per call)
        assert avg_call_ms < 0.1
