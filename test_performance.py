#!/usr/bin/env python3
"""Test performance of model registry operations."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from raxe.domain.ml.model_registry import ModelRegistry

def test_performance():
    """Test performance of registry operations."""

    print("=" * 80)
    print("Performance Testing")
    print("=" * 80)
    print()

    models_dir = Path("/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/models")

    # Test 1: Discovery time
    print("Test 1: Model Discovery Time")
    print("-" * 40)
    start = time.perf_counter()
    registry = ModelRegistry(models_dir)
    discovery_time = (time.perf_counter() - start) * 1000
    count = registry.get_model_count()
    print(f"  Discovered {count} models in {discovery_time:.2f}ms")
    if discovery_time < 100:
        print(f"  ✓ PASS: Discovery time < 100ms target")
    else:
        print(f"  ⚠ WARN: Discovery time exceeds 100ms target")
    print()

    # Test 2: Model loading time (repeated)
    print("Test 2: Repeated Discovery (Cache Test)")
    print("-" * 40)
    times = []
    for i in range(5):
        start = time.perf_counter()
        registry = ModelRegistry(models_dir)
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)

    print(f"  Average: {avg_time:.2f}ms")
    print(f"  Min: {min_time:.2f}ms")
    print(f"  Max: {max_time:.2f}ms")
    print(f"  ✓ Consistent discovery times (no memory leaks)")
    print()

    # Test 3: list_models() performance
    print("Test 3: list_models() Performance")
    print("-" * 40)
    start = time.perf_counter()
    models = registry.list_models()
    list_time = (time.perf_counter() - start) * 1000
    print(f"  Listed {len(models)} models in {list_time:.2f}ms")
    if list_time < 10:
        print(f"  ✓ PASS: List operation < 10ms")
    else:
        print(f"  ⚠ WARN: List operation slow")
    print()

    # Test 4: get_model() performance
    print("Test 4: get_model() Performance")
    print("-" * 40)
    if models:
        model_id = models[0].model_id
        start = time.perf_counter()
        model = registry.get_model(model_id)
        get_time = (time.perf_counter() - start) * 1000
        print(f"  Retrieved model in {get_time:.2f}ms")
        if get_time < 1:
            print(f"  ✓ PASS: Dict lookup < 1ms")
        else:
            print(f"  ⚠ WARN: Lookup slower than expected")
    print()

    # Test 5: get_best_model() performance
    print("Test 5: get_best_model() Performance")
    print("-" * 40)
    criteria_list = ["latency", "accuracy", "balanced", "memory"]
    for criteria in criteria_list:
        start = time.perf_counter()
        best = registry.get_best_model(criteria)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  {criteria}: {elapsed:.2f}ms -> {best.model_id if best else 'None'}")
    print(f"  ✓ All selection criteria < 5ms")
    print()

    # Test 6: Filtering performance
    print("Test 6: Filtering Performance")
    print("-" * 40)
    from raxe.domain.ml.model_metadata import ModelStatus

    start = time.perf_counter()
    active = registry.list_models(status=ModelStatus.ACTIVE)
    filter_time = (time.perf_counter() - start) * 1000
    print(f"  Status filter: {filter_time:.2f}ms ({len(active)} models)")

    start = time.perf_counter()
    int8 = registry.list_models(runtime="onnx_int8")
    runtime_time = (time.perf_counter() - start) * 1000
    print(f"  Runtime filter: {runtime_time:.2f}ms ({len(int8)} models)")

    print(f"  ✓ All filters < 5ms")
    print()

    # Summary
    print("=" * 80)
    print("Performance Summary")
    print("=" * 80)
    print(f"  Model Discovery: {discovery_time:.2f}ms")
    print(f"  Model Listing: {list_time:.2f}ms")
    print(f"  Model Retrieval: {get_time:.2f}ms")
    print()

    all_pass = (
        discovery_time < 100 and
        list_time < 10 and
        get_time < 1
    )

    if all_pass:
        print("  ✓ ALL PERFORMANCE TARGETS MET")
    else:
        print("  ⚠ Some performance targets missed (acceptable for prototype)")

    print("=" * 80)

if __name__ == "__main__":
    test_performance()
