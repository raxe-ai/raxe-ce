"""Shared fixtures and utilities for functional tests."""
import json
import os
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Get test data directory."""
    return Path(__file__).parent / "test_data"


@pytest.fixture(scope="session")
def safe_prompts(test_data_dir: Path) -> list[str]:
    """Load safe test prompts."""
    with open(test_data_dir / "safe_prompts.json") as f:
        return json.load(f)["prompts"]


@pytest.fixture(scope="session")
def threat_prompts(test_data_dir: Path) -> list[str]:
    """Load threat test prompts."""
    with open(test_data_dir / "threat_prompts.json") as f:
        return json.load(f)["prompts"]


@pytest.fixture(scope="session")
def edge_cases(test_data_dir: Path) -> dict[str, Any]:
    """Load edge case test data."""
    with open(test_data_dir / "edge_cases.json") as f:
        return json.load(f)


@pytest.fixture
def temp_config_file():
    """Create temporary config file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
api_key: test_key_123
telemetry:
  enabled: false
performance:
  mode: fast
l2:
  enabled: true
  timeout_ms: 5000
""")
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def mock_progress():
    """Mock progress callback for testing."""
    progress = Mock()
    progress.start = Mock()
    progress.update = Mock()
    progress.complete = Mock()
    return progress


@pytest.fixture
def performance_tracker():
    """Track performance metrics during tests."""
    class PerformanceTracker:
        def __init__(self):
            self.metrics = {}

        @contextmanager
        def track(self, name: str):
            """Track timing for a code block."""
            start = time.perf_counter()
            try:
                yield
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                if name not in self.metrics:
                    self.metrics[name] = []
                self.metrics[name].append(duration_ms)

        def get_stats(self, name: str) -> dict[str, float]:
            """Get statistics for a metric."""
            if name not in self.metrics:
                return {}

            values = sorted(self.metrics[name])
            n = len(values)
            if n == 0:
                return {}

            return {
                "min": values[0],
                "max": values[-1],
                "mean": sum(values) / n,
                "p50": values[n // 2],
                "p95": values[int(n * 0.95)] if n > 1 else values[0],
                "p99": values[int(n * 0.99)] if n > 1 else values[0],
                "count": n
            }

    return PerformanceTracker()


@pytest.fixture
def memory_tracker():
    """Track memory usage during tests."""
    import psutil

    class MemoryTracker:
        def __init__(self):
            self.process = psutil.Process()
            self.baseline = None

        def reset_baseline(self):
            """Set current memory as baseline."""
            import gc
            gc.collect()
            self.baseline = self.process.memory_info().rss / 1024 / 1024  # MB

        def get_current_mb(self) -> float:
            """Get current memory usage in MB."""
            return self.process.memory_info().rss / 1024 / 1024

        def get_delta_mb(self) -> float:
            """Get memory delta from baseline."""
            if self.baseline is None:
                self.reset_baseline()
            return self.get_current_mb() - self.baseline

    return MemoryTracker()


@pytest.fixture
def thread_pool():
    """Create thread pool for concurrent testing."""
    class ThreadPool:
        def __init__(self):
            self.results = []
            self.errors = []

        def run_concurrent(self, func, args_list, num_threads=10):
            """Run function concurrently with different args."""
            threads = []
            self.results = []
            self.errors = []

            def worker(args):
                try:
                    result = func(*args) if isinstance(args, tuple) else func(args)
                    self.results.append(result)
                except Exception as e:
                    self.errors.append(e)

            for args in args_list[:num_threads]:
                t = threading.Thread(target=worker, args=(args,))
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=10)

            return self.results, self.errors

    return ThreadPool()


@pytest.fixture
def assert_performance():
    """Performance assertion helper."""
    def _assert(actual_ms: float, target_ms: float, threshold_ms: float, metric_name: str):
        """Assert performance metric is within bounds."""
        assert actual_ms <= threshold_ms, (
            f"{metric_name} performance violation: "
            f"{actual_ms:.2f}ms > {threshold_ms}ms threshold (target: {target_ms}ms)"
        )

        if actual_ms > target_ms:
            pytest.skip(f"{metric_name} exceeds target: {actual_ms:.2f}ms > {target_ms}ms")

    return _assert


@pytest.fixture(autouse=True)
def cleanup_env():
    """Clean up environment variables between tests."""
    # Save current env
    original_env = os.environ.copy()

    yield

    # Restore original env
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def capture_telemetry(tmp_path):
    """Capture telemetry data for validation."""
    telemetry_file = tmp_path / "telemetry.json"

    # Override telemetry file location
    os.environ["RAXE_TELEMETRY_FILE"] = str(telemetry_file)

    yield telemetry_file

    # Cleanup
    if "RAXE_TELEMETRY_FILE" in os.environ:
        del os.environ["RAXE_TELEMETRY_FILE"]


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "performance: performance benchmark tests")
    config.addinivalue_line("markers", "integration: integration tests")
    config.addinivalue_line("markers", "requires_models: tests that need ML models")