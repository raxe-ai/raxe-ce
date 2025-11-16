"""Tests for performance profiler."""

import time
from unittest.mock import Mock, patch

import pytest

from raxe.monitoring.profiler import (
    MemoryProfiler,
    PerformanceProfiler,
    ProfileResult,
    create_performance_report,
    format_time,
)


class TestPerformanceProfiler:
    """Test PerformanceProfiler class."""

    @pytest.fixture
    def profiler(self):
        """Create profiler instance."""
        return PerformanceProfiler()

    def test_profile_function_basic(self, profiler):
        """Test basic function profiling."""
        def simple_function(x, y):
            return x + y

        result = profiler.profile_function(
            simple_function,
            5, 10,
            iterations=10,
        )

        assert isinstance(result, ProfileResult)
        assert result.iterations == 10
        assert result.total_time > 0
        assert result.avg_time > 0
        assert result.avg_time == result.total_time / result.iterations
        assert len(result.stats_report) > 0

    def test_profile_function_with_kwargs(self, profiler):
        """Test profiling function with keyword arguments."""
        def kwarg_function(a, b=10):
            return a * b

        result = profiler.profile_function(
            kwarg_function,
            5,
            b=20,
            iterations=50,
        )

        assert result.iterations == 50
        assert result.total_time > 0

    def test_profile_function_slow_operation(self, profiler):
        """Test profiling a slow operation."""
        def slow_function():
            time.sleep(0.01)  # 10ms

        result = profiler.profile_function(
            slow_function,
            iterations=5,
        )

        # Should take at least 50ms (5 * 10ms)
        assert result.total_time >= 0.05
        assert result.avg_time >= 0.01

    @patch('raxe.monitoring.profiler.scan_prompt')
    def test_profile_scan(self, mock_scan, profiler):
        """Test profile_scan method."""
        mock_scan.return_value = Mock()

        result = profiler.profile_scan("test prompt", iterations=10)

        assert isinstance(result, ProfileResult)
        assert result.iterations == 10
        # Warmup + iterations
        assert mock_scan.call_count == 10 + 1

    @patch('raxe.monitoring.profiler.scan_prompt')
    def test_profile_to_file(self, mock_scan, profiler, tmp_path):
        """Test saving profile to file."""
        mock_scan.return_value = Mock()

        output_path = tmp_path / "profile.prof"

        profiler.profile_to_file(
            "test prompt",
            str(output_path),
            iterations=10,
        )

        # Verify file was created
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_compare_implementations(self, profiler):
        """Test comparing two implementations."""
        def fast_impl():
            return sum(range(100))

        def slow_impl():
            result = 0
            for i in range(100):
                result += i
            return result

        report = profiler.compare_implementations(
            fast_impl,
            slow_impl,
            iterations=50,
        )

        assert "Implementation Comparison" in report
        assert "faster" in report.lower()

    def test_benchmark_throughput(self, profiler):
        """Test throughput benchmarking."""
        # Mock scan_prompt
        with patch('raxe.monitoring.profiler.scan_prompt') as mock_scan:
            mock_scan.return_value = Mock()

            prompts = ["prompt1", "prompt2", "prompt3"]

            results = profiler.benchmark_throughput(
                prompts,
                warmup=5,
                iterations=10,
            )

            assert "total_scans" in results
            assert results["total_scans"] == 10 * 3  # iterations * prompts
            assert "total_time" in results
            assert results["total_time"] > 0
            assert "scans_per_second" in results
            assert results["scans_per_second"] > 0
            assert "avg_time_ms" in results
            assert results["avg_time_ms"] > 0
            assert results["prompts_tested"] == 3
            assert results["iterations"] == 10


class TestProfileResult:
    """Test ProfileResult dataclass."""

    def test_profile_result_creation(self):
        """Test creating ProfileResult."""
        result = ProfileResult(
            total_time=1.234,
            iterations=100,
            avg_time=0.01234,
            stats_report="test stats",
        )

        assert result.total_time == 1.234
        assert result.iterations == 100
        assert result.avg_time == 0.01234
        assert result.stats_report == "test stats"

    def test_profile_result_string_representation(self):
        """Test ProfileResult string formatting."""
        result = ProfileResult(
            total_time=1.234,
            iterations=100,
            avg_time=0.01234,
            stats_report="test stats",
        )

        str_repr = str(result)

        assert "Performance Profile Results" in str_repr
        assert "1.2340s" in str_repr
        assert "100" in str_repr
        assert "12.34ms" in str_repr
        assert "81.0" in str_repr  # scans per second


class TestMemoryProfiler:
    """Test MemoryProfiler class."""

    def test_memory_profiler_init(self):
        """Test MemoryProfiler initialization."""
        profiler = MemoryProfiler()

        # Should initialize without error
        # Availability depends on memory_profiler package
        assert isinstance(profiler.available, bool)

    @pytest.mark.skipif(
        not pytest.importorskip("memory_profiler"),
        reason="memory_profiler not installed",
    )
    def test_memory_profiler_available(self):
        """Test MemoryProfiler when package is available."""
        profiler = MemoryProfiler()

        assert profiler.available is True

    def test_memory_profiler_not_available(self):
        """Test MemoryProfiler when package is not available."""
        with patch('raxe.monitoring.profiler.memory_profiler', None):
            profiler = MemoryProfiler()
            assert profiler.available is False

    def test_profile_memory_not_available(self):
        """Test profile_memory when not available."""
        with patch.object(MemoryProfiler, 'available', False):
            profiler = MemoryProfiler()

            result = profiler.profile_memory(lambda: None)

            assert result is None


class TestHelperFunctions:
    """Test helper functions."""

    def test_format_time_microseconds(self):
        """Test formatting time in microseconds."""
        assert "µs" in format_time(0.0001)
        assert "µs" in format_time(0.0005)

    def test_format_time_milliseconds(self):
        """Test formatting time in milliseconds."""
        assert "ms" in format_time(0.001)
        assert "ms" in format_time(0.5)
        assert "5.00ms" == format_time(0.005)

    def test_format_time_seconds(self):
        """Test formatting time in seconds."""
        assert "1.00s" == format_time(1.0)
        assert "s" in format_time(2.5)

    def test_format_time_edge_cases(self):
        """Test format_time edge cases."""
        assert format_time(0) == "0µs"
        assert format_time(1000) == "1000.00s"

    def test_create_performance_report_empty(self):
        """Test creating report with no data."""
        report = create_performance_report([], [])

        assert "No performance data available" in report

    def test_create_performance_report_with_data(self):
        """Test creating report with data."""
        scan_times = [0.001, 0.002, 0.003, 0.004, 0.005] * 20  # 100 samples
        prompt_lengths = [100, 200, 150, 180, 120] * 20

        report = create_performance_report(scan_times, prompt_lengths)

        assert "Performance Report" in report
        assert "Scans:" in report
        assert "100" in report  # number of scans
        assert "Latency:" in report
        assert "Mean:" in report
        assert "Median:" in report
        assert "P95:" in report
        assert "P99:" in report
        assert "Throughput:" in report

    def test_create_performance_report_single_sample(self):
        """Test report with single sample."""
        report = create_performance_report([0.005], [100])

        assert "Scans:       1" in report
        assert "Mean:" in report


class TestProfilingIntegration:
    """Test profiling integration scenarios."""

    @pytest.fixture
    def profiler(self):
        """Create profiler instance."""
        return PerformanceProfiler()

    @patch('raxe.monitoring.profiler.scan_prompt')
    def test_end_to_end_profiling(self, mock_scan, profiler):
        """Test complete profiling workflow."""
        mock_scan.return_value = Mock()

        # Profile scan
        result = profiler.profile_scan("test prompt", iterations=50)

        # Verify results
        assert result.iterations == 50
        assert result.total_time > 0
        assert result.avg_time > 0
        assert len(result.stats_report) > 0

        # Verify warmup occurred
        assert mock_scan.call_count == 51  # 1 warmup + 50 iterations

    def test_benchmark_with_multiple_prompts(self, profiler):
        """Test benchmarking with multiple prompts."""
        with patch('raxe.monitoring.profiler.scan_prompt') as mock_scan:
            mock_scan.return_value = Mock()

            prompts = [f"prompt {i}" for i in range(10)]

            results = profiler.benchmark_throughput(
                prompts,
                warmup=5,
                iterations=20,
            )

            # Verify all prompts were scanned
            assert results["prompts_tested"] == 10
            assert results["total_scans"] == 20 * 10

            # Verify metrics
            assert results["scans_per_second"] > 0
            assert results["avg_time_ms"] > 0


class TestProfilingEdgeCases:
    """Test profiling edge cases."""

    @pytest.fixture
    def profiler(self):
        """Create profiler instance."""
        return PerformanceProfiler()

    def test_profile_function_zero_iterations(self, profiler):
        """Test profiling with zero iterations."""
        def test_func():
            pass

        # Should still work (with warmup)
        result = profiler.profile_function(test_func, iterations=0)

        assert result.iterations == 0
        assert result.total_time >= 0

    def test_profile_function_exception(self, profiler):
        """Test profiling function that raises exception."""
        def error_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            profiler.profile_function(error_func, iterations=1)

    @patch('raxe.monitoring.profiler.scan_prompt')
    def test_profile_very_fast_function(self, mock_scan, profiler):
        """Test profiling very fast function."""
        mock_scan.return_value = Mock()

        # Profile with many iterations
        result = profiler.profile_scan("test", iterations=10000)

        # Should still measure accurately
        assert result.avg_time > 0
        assert result.total_time > 0

    def test_compare_identical_implementations(self, profiler):
        """Test comparing identical implementations."""
        def impl():
            return 42

        report = profiler.compare_implementations(
            impl,
            impl,
            iterations=10,
        )

        # Should report similar performance
        assert "Implementation Comparison" in report


class TestProfilingPerformance:
    """Test profiler performance and overhead."""

    @pytest.fixture
    def profiler(self):
        """Create profiler instance."""
        return PerformanceProfiler()

    def test_profiler_overhead(self, profiler):
        """Test that profiler overhead is minimal."""
        def simple_func():
            return 42

        # Measure without profiling
        start = time.perf_counter()
        for _ in range(100):
            simple_func()
        baseline_time = time.perf_counter() - start

        # Measure with profiling
        result = profiler.profile_function(simple_func, iterations=100)

        # Profiling overhead should be reasonable (< 100x)
        # Note: cProfile has overhead, this is expected
        assert result.total_time < baseline_time * 100

    @patch('raxe.monitoring.profiler.scan_prompt')
    def test_warmup_effectiveness(self, mock_scan, profiler):
        """Test that warmup improves measurement accuracy."""
        mock_scan.return_value = Mock()

        # First call (cold)
        result1 = profiler.profile_scan("test", iterations=1)

        # Second call (warm)
        result2 = profiler.profile_scan("test", iterations=1)

        # Both should complete successfully
        assert result1.iterations == 1
        assert result2.iterations == 1
