#!/usr/bin/env python3
"""Test script to verify model registration and discovery."""

from raxe.domain.ml.model_registry import get_registry

def main():
    print("=" * 60)
    print("RAXE Model Registry Test")
    print("=" * 60)

    # Get registry
    registry = get_registry()

    print(f"\n✓ Discovered {registry.get_model_count()} total models")
    print(f"✓ Active models: {registry.get_active_model_count()}\n")

    # List all models
    print("-" * 60)
    print("All Models:")
    print("-" * 60)

    for model in registry.list_models():
        print(f"\nModel ID: {model.model_id}")
        print(f"  Name: {model.name}")
        print(f"  Status: {model.status.value}")
        print(f"  Runtime: {model.runtime_type}")
        print(f"  Bundle: {model.file_info.filename}")

        if model.file_info.onnx_embeddings:
            print(f"  ONNX Embeddings: {model.file_info.onnx_embeddings}")

        # Performance metrics
        perf = model.performance
        print(f"  Performance:")
        print(f"    Target latency: {perf.target_latency_ms}ms")
        if perf.p50_latency_ms:
            print(f"    P50: {perf.p50_latency_ms}ms")
        if perf.p95_latency_ms:
            print(f"    P95: {perf.p95_latency_ms}ms")
        if perf.throughput_per_sec:
            print(f"    Throughput: {perf.throughput_per_sec}/sec")

    # Test best model selection
    print("\n" + "=" * 60)
    print("Best Model Selection:")
    print("=" * 60)

    for criteria in ["latency", "accuracy", "balanced", "memory"]:
        best = registry.get_best_model(criteria)
        if best:
            print(f"\nBest for '{criteria}': {best.model_id}")
            print(f"  → {best.name}")

    # Test specific model lookup
    print("\n" + "=" * 60)
    print("Testing Your New Models:")
    print("=" * 60)

    for model_id in ["v1.0_fp16", "v1.0_int8_fast"]:
        model = registry.get_model(model_id)
        if model:
            print(f"\n✓ Model '{model_id}' registered successfully!")
            print(f"  ONNX file: {model.file_info.onnx_embeddings}")
            print(f"  Size: {model.file_info.size_mb}MB")
            print(f"  Target latency: {model.performance.target_latency_ms}ms")
        else:
            print(f"\n✗ Model '{model_id}' NOT FOUND")

    print("\n" + "=" * 60)
    print("Registry test complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
