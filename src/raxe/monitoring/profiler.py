"""
Performance profiling tools for RAXE CE.

This module provides tools for profiling RAXE performance to identify
bottlenecks and optimize scan throughput. It includes:

- Function-level profiling with cProfile
- Memory profiling (if memory_profiler is available)
- Custom performance reports
- Integration with CLI commands

Usage:
    # Profile a scan
    profiler = PerformanceProfiler()
    report = profiler.profile_scan(prompt, iterations=100)
    print(report)

    # Save profile for visualization
    profiler.profile_to_file(prompt, "profile.prof")
    # Then: snakeviz profile.prof
"""

import cProfile
import pstats
import time
from collections.abc import Callable
from dataclasses import dataclass
from io import StringIO
from typing import Any


@dataclass
class ProfileResult:
    """Results from a profiling run."""

    total_time: float
    """Total time in seconds"""

    iterations: int
    """Number of iterations"""

    avg_time: float
    """Average time per iteration"""

    stats_report: str
    """Formatted profiling statistics"""

    def __str__(self) -> str:
        """Format profile result as string."""
        return f"""
Performance Profile Results
===========================
Total Time:      {self.total_time:.4f}s
Iterations:      {self.iterations}
Avg per Scan:    {self.avg_time * 1000:.2f}ms
Scans per Second: {1 / self.avg_time:.1f}

Top Functions by Cumulative Time:
{self.stats_report}
"""


class PerformanceProfiler:
    """
    Performance profiler for RAXE scans.

    This profiler helps identify performance bottlenecks by measuring
    function execution times and call counts.

    Example:
        profiler = PerformanceProfiler()

        # Quick profile
        result = profiler.profile_scan(prompt)
        print(result)

        # Save for analysis
        profiler.profile_to_file(prompt, "scan.prof")
    """

    def profile_function(
        self,
        func: Callable,
        *args,
        iterations: int = 100,
        **kwargs,
    ) -> ProfileResult:
        """
        Profile a function with cProfile.

        Args:
            func: Function to profile
            *args: Positional arguments for function
            iterations: Number of times to run function
            **kwargs: Keyword arguments for function

        Returns:
            ProfileResult with timing and statistics
        """
        profiler = cProfile.Profile()

        # Warm up (one iteration without profiling)
        func(*args, **kwargs)

        # Profile
        start_time = time.perf_counter()
        profiler.enable()

        for _ in range(iterations):
            func(*args, **kwargs)

        profiler.disable()
        total_time = time.perf_counter() - start_time

        # Generate stats
        stream = StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.strip_dirs()
        stats.sort_stats(pstats.SortKey.CUMULATIVE)
        stats.print_stats(20)  # Top 20 functions

        return ProfileResult(
            total_time=total_time,
            iterations=iterations,
            avg_time=total_time / iterations,
            stats_report=stream.getvalue(),
        )

    def profile_scan(self, prompt: str, iterations: int = 100) -> ProfileResult:
        """
        Profile a single scan operation.

        Args:
            prompt: Prompt to scan
            iterations: Number of iterations to run

        Returns:
            ProfileResult with timing and statistics

        Example:
            result = profiler.profile_scan("test prompt", iterations=100)
            print(f"Average scan time: {result.avg_time * 1000:.2f}ms")
        """
        # Import here to avoid circular dependency
        from raxe.application.scan_pipeline import scan_prompt

        return self.profile_function(scan_prompt, prompt, iterations=iterations)

    def profile_to_file(
        self,
        prompt: str,
        output_path: str,
        iterations: int = 100,
    ) -> None:
        """
        Profile scan and save to file for visualization.

        The output file can be visualized with tools like:
        - snakeviz: pip install snakeviz && snakeviz profile.prof
        - gprof2dot: gprof2dot -f pstats profile.prof | dot -Tpng -o profile.png

        Args:
            prompt: Prompt to scan
            output_path: Path to save profile data
            iterations: Number of iterations

        Example:
            profiler.profile_to_file("test", "scan.prof")
            # Then: snakeviz scan.prof
        """
        from raxe.application.scan_pipeline import scan_prompt

        profiler = cProfile.Profile()

        # Warm up
        scan_prompt(prompt)

        # Profile
        profiler.enable()
        for _ in range(iterations):
            scan_prompt(prompt)
        profiler.disable()

        # Save
        profiler.dump_stats(output_path)

    def compare_implementations(
        self,
        func1: Callable,
        func2: Callable,
        *args,
        iterations: int = 100,
        **kwargs,
    ) -> str:
        """
        Compare two implementations.

        Args:
            func1: First implementation
            func2: Second implementation
            *args: Arguments to pass to both functions
            iterations: Number of iterations
            **kwargs: Keyword arguments to pass to both functions

        Returns:
            Comparison report as string
        """
        result1 = self.profile_function(func1, *args, iterations=iterations, **kwargs)
        result2 = self.profile_function(func2, *args, iterations=iterations, **kwargs)

        speedup = result1.avg_time / result2.avg_time
        faster = "func2" if speedup > 1 else "func1"
        ratio = max(speedup, 1 / speedup)

        return f"""
Implementation Comparison
========================
Function 1: {result1.avg_time * 1000:.2f}ms avg
Function 2: {result2.avg_time * 1000:.2f}ms avg

Result: {faster} is {ratio:.2f}x faster
"""

    def benchmark_throughput(
        self,
        prompts: list[str],
        warmup: int = 10,
        iterations: int = 100,
    ) -> dict[str, Any]:
        """
        Benchmark scan throughput with multiple prompts.

        Args:
            prompts: List of prompts to scan
            warmup: Number of warmup iterations
            iterations: Number of benchmark iterations

        Returns:
            Dictionary with throughput metrics
        """
        from raxe.application.scan_pipeline import scan_prompt

        # Warm up
        for prompt in prompts[:warmup]:
            scan_prompt(prompt)

        # Benchmark
        start_time = time.perf_counter()

        for _ in range(iterations):
            for prompt in prompts:
                scan_prompt(prompt)

        total_time = time.perf_counter() - start_time

        total_scans = iterations * len(prompts)
        scans_per_second = total_scans / total_time
        avg_time_ms = (total_time / total_scans) * 1000

        return {
            "total_scans": total_scans,
            "total_time": total_time,
            "scans_per_second": scans_per_second,
            "avg_time_ms": avg_time_ms,
            "prompts_tested": len(prompts),
            "iterations": iterations,
        }


class MemoryProfiler:
    """
    Memory profiling for RAXE scans.

    Requires memory_profiler package:
        pip install memory_profiler

    This profiler helps identify memory leaks and excessive allocations.
    """

    def __init__(self):
        """Initialize memory profiler."""
        try:
            import memory_profiler

            self.available = True
            self._profiler = memory_profiler
        except ImportError:
            self.available = False
            self._profiler = None

    def profile_memory(self, func: Callable, *args, **kwargs) -> str | None:
        """
        Profile memory usage of a function.

        Args:
            func: Function to profile
            *args: Arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Memory profile report or None if memory_profiler not available
        """
        if not self.available:
            return None

        from memory_profiler import memory_usage

        # Measure memory
        mem_usage = memory_usage((func, args, kwargs), interval=0.001)

        if mem_usage:
            peak_mem = max(mem_usage)
            avg_mem = sum(mem_usage) / len(mem_usage)
            mem_increase = mem_usage[-1] - mem_usage[0]

            return f"""
Memory Profile
==============
Peak Memory: {peak_mem:.2f} MiB
Avg Memory:  {avg_mem:.2f} MiB
Memory Δ:    {mem_increase:+.2f} MiB
"""
        return None


def format_time(seconds: float) -> str:
    """
    Format time duration in human-readable format.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted string (e.g., "1.23ms", "45.6s")
    """
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.0f}µs"
    elif seconds < 1:
        return f"{seconds * 1000:.2f}ms"
    else:
        return f"{seconds:.2f}s"


def create_performance_report(
    scan_times: list[float],
    prompt_lengths: list[int],
) -> str:
    """
    Create a comprehensive performance report.

    Args:
        scan_times: List of scan durations in seconds
        prompt_lengths: List of prompt lengths in characters

    Returns:
        Formatted performance report
    """
    if not scan_times:
        return "No performance data available"

    import statistics

    # Calculate statistics
    avg_time = statistics.mean(scan_times)
    median_time = statistics.median(scan_times)
    p95_time = sorted(scan_times)[int(len(scan_times) * 0.95)]
    p99_time = sorted(scan_times)[int(len(scan_times) * 0.99)]
    min_time = min(scan_times)
    max_time = max(scan_times)

    avg_length = statistics.mean(prompt_lengths) if prompt_lengths else 0

    return f"""
Performance Report
==================
Scans:       {len(scan_times)}
Avg Length:  {avg_length:.0f} chars

Latency:
  Mean:      {format_time(avg_time)}
  Median:    {format_time(median_time)}
  P95:       {format_time(p95_time)}
  P99:       {format_time(p99_time)}
  Min:       {format_time(min_time)}
  Max:       {format_time(max_time)}

Throughput:  {len(scan_times) / sum(scan_times):.1f} scans/sec
"""
