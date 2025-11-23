"""Test SDK thread safety for concurrent operations."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from raxe.sdk.client import Raxe


class TestSDKThreadSafety:
    """Test thread-safe operations in SDK."""

    @pytest.fixture
    def client(self):
        """Create a shared client instance."""
        return Raxe()

    def test_concurrent_scans_same_client(self, client, safe_prompts, thread_pool):
        """Test multiple threads scanning with same client."""
        prompts = safe_prompts[:10]

        def scan_prompt(prompt):
            result = client.scan(prompt)
            assert result is not None
            assert result.status in ["safe", "threat"]
            return result

        results, errors = thread_pool.run_concurrent(scan_prompt, prompts)

        # All scans should succeed
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        assert all(r.status == "safe" for r in results)

    def test_concurrent_initialization(self, thread_pool):
        """Test multiple threads initializing clients concurrently."""
        def create_client(idx):
            client = Raxe()
            assert client._initialized
            return client

        results, errors = thread_pool.run_concurrent(
            create_client,
            list(range(5)),
            num_threads=5
        )

        # All should initialize successfully
        assert len(errors) == 0
        assert len(results) == 5
        assert all(c._initialized for c in results)

    def test_thread_local_state_isolation(self, client, safe_prompts):
        """Test thread-local state doesn't leak between threads."""
        results = {}
        errors = []

        def worker(thread_id, prompt):
            try:
                # Each thread does multiple scans
                thread_results = []
                for i in range(3):
                    result = client.scan(f"{prompt} - thread {thread_id} scan {i}")
                    thread_results.append(result)
                    time.sleep(0.01)  # Small delay to increase concurrency

                results[thread_id] = thread_results
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Start threads
        threads = []
        for i in range(5):
            t = threading.Thread(
                target=worker,
                args=(i, safe_prompts[i % len(safe_prompts)])
            )
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join(timeout=5)

        # Verify results
        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 5

        # Each thread should have 3 results
        for _thread_id, thread_results in results.items():
            assert len(thread_results) == 3
            assert all(r.status == "safe" for r in thread_results)

    def test_concurrent_different_operations(self, safe_prompts, threat_prompts):
        """Test different SDK operations running concurrently."""
        client = Raxe()
        results = {"scans": [], "stats": [], "errors": []}

        def scan_safe():
            try:
                return client.scan(safe_prompts[0])
            except Exception as e:
                results["errors"].append(("scan_safe", str(e)))

        def scan_threat():
            try:
                return client.scan(threat_prompts[0])
            except Exception as e:
                results["errors"].append(("scan_threat", str(e)))

        def get_stats():
            try:
                return client.get_initialization_stats()
            except Exception as e:
                results["errors"].append(("get_stats", str(e)))

        # Run different operations concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []

            # Submit mixed operations
            for _ in range(3):
                futures.append(executor.submit(scan_safe))
                futures.append(executor.submit(scan_threat))
                futures.append(executor.submit(get_stats))

            # Collect results
            for future in as_completed(futures, timeout=5):
                try:
                    result = future.result()
                    if hasattr(result, "status"):
                        results["scans"].append(result)
                    else:
                        results["stats"].append(result)
                except Exception as e:
                    results["errors"].append(str(e))

        # Verify
        assert len(results["errors"]) == 0, f"Errors: {results['errors']}"
        assert len(results["scans"]) >= 6  # At least 6 scans
        # Check we got both safe and threat results
        statuses = [r.status for r in results["scans"]]
        assert "safe" in statuses
        assert "threat" in statuses

    def test_race_condition_detection(self, client, safe_prompts):
        """Test for race conditions in shared state."""
        # Try to detect race conditions by rapid concurrent access
        race_detected = False
        results = []

        def aggressive_scanner(prompt_idx):
            nonlocal race_detected
            try:
                # Rapid-fire scans
                for _ in range(20):
                    result = client.scan(safe_prompts[prompt_idx % len(safe_prompts)])
                    results.append(result)
            except Exception as e:
                if "race" in str(e).lower() or "concurrent" in str(e).lower():
                    race_detected = True
                raise

        # Launch aggressive concurrent scanning
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(aggressive_scanner, i) for i in range(20)]

            for future in as_completed(futures, timeout=10):
                try:
                    future.result()
                except Exception:
                    pass  # Collect all results/errors

        # Should not detect race conditions
        assert not race_detected
        # Should have completed many scans
        assert len(results) > 100

    def test_memory_safety_concurrent(self, client, safe_prompts, memory_tracker):
        """Test memory safety during concurrent operations."""
        memory_tracker.reset_baseline()
        baseline = memory_tracker.get_current_mb()

        def memory_intensive_scan(idx):
            # Create large prompt
            large_prompt = safe_prompts[0] * 100
            return client.scan(large_prompt)

        # Run memory-intensive concurrent operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(memory_intensive_scan, i) for i in range(50)]

            for future in as_completed(futures, timeout=30):
                future.result()

        # Check memory didn't explode
        final_memory = memory_tracker.get_current_mb()
        memory_increase = final_memory - baseline

        # Should not leak excessive memory
        assert memory_increase < 100, f"Memory increased by {memory_increase:.1f}MB"

    def test_initialization_singleton_pattern(self):
        """Test initialization doesn't create duplicate resources."""
        clients = []

        def create_client(idx):
            client = Raxe()
            clients.append(client)
            return client.preload_stats.duration_ms

        # Create clients concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_client, i) for i in range(5)]
            [f.result() for f in as_completed(futures, timeout=5)]

        # All should initialize successfully
        assert len(clients) == 5
        assert all(c._initialized for c in clients)

        # Each should have separate pipeline instance
        pipeline_ids = [id(c.pipeline) for c in clients]
        assert len(set(pipeline_ids)) == 5  # All unique

    def test_async_pipeline_thread_safety(self, client, safe_prompts):
        """Test async pipeline initialization is thread-safe."""
        initialization_errors = []

        def trigger_async_pipeline(idx):
            try:
                # This might trigger async pipeline creation
                result = client.scan(safe_prompts[idx % len(safe_prompts)])
                return result
            except Exception as e:
                initialization_errors.append(str(e))

        # Many threads try to trigger async pipeline
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(trigger_async_pipeline, i) for i in range(20)]

            for future in as_completed(futures, timeout=5):
                future.result()

        # Should not have initialization errors
        assert len(initialization_errors) == 0

    @pytest.mark.slow
    def test_sustained_concurrent_load(self, client, safe_prompts):
        """Test sustained concurrent load over time."""
        stop_flag = threading.Event()
        scan_counts = {}
        errors = []

        def sustained_scanner(thread_id):
            count = 0
            try:
                while not stop_flag.is_set():
                    client.scan(safe_prompts[thread_id % len(safe_prompts)])
                    count += 1
                    time.sleep(0.001)  # Small delay
            except Exception as e:
                errors.append((thread_id, str(e)))
            finally:
                scan_counts[thread_id] = count

        # Start sustained load
        threads = []
        for i in range(10):
            t = threading.Thread(target=sustained_scanner, args=(i,))
            threads.append(t)
            t.start()

        # Run for 2 seconds
        time.sleep(2)
        stop_flag.set()

        # Wait for threads
        for t in threads:
            t.join(timeout=1)

        # Verify
        assert len(errors) == 0, f"Errors during sustained load: {errors}"
        assert len(scan_counts) == 10
        # Each thread should have done many scans
        assert all(count > 10 for count in scan_counts.values())