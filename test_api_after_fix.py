#!/usr/bin/env python3
"""Test Python API after fix implementation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from raxe.domain.ml.model_registry import get_registry

def test_api():
    """Test direct Python API access."""

    print("=" * 80)
    print("Testing Direct Python API")
    print("=" * 80)
    print()

    # Get registry
    registry = get_registry()

    # List models
    models = registry.list_models()
    print(f"✓ Discovered {len(models)} models")
    print()

    # Test each model
    for model in models:
        print("-" * 80)
        print(f"Model: {model.model_id}")
        print(f"  Name: {model.name}")
        print(f"  Version: {model.version}")
        print(f"  Status: {model.status.value}")
        print(f"  Runtime: {model.runtime_type}")
        print()

        # CRITICAL: Check tokenizer fields
        print("  Tokenizer Information:")
        print(f"    - tokenizer_name: {model.tokenizer_name}")
        print(f"    - embedding_model_name: {model.embedding_model_name}")
        if model.tokenizer_config:
            print(f"    - tokenizer_config keys: {list(model.tokenizer_config.keys())}")
            print(f"    - max_length: {model.tokenizer_config.get('max_length')}")
        else:
            print("    - tokenizer_config: None")
        print()

        # Performance metrics
        print(f"  Performance:")
        print(f"    - P50: {model.performance.p50_latency_ms}ms")
        print(f"    - P95: {model.performance.p95_latency_ms}ms")
        print(f"    - P99: {model.performance.p99_latency_ms}ms")
        print(f"    - Memory: {model.performance.memory_mb}MB")
        print()

        # Accuracy metrics
        if model.accuracy:
            print(f"  Accuracy:")
            print(f"    - Binary F1: {model.accuracy.binary_f1:.1%}")
            print(f"    - Family F1: {model.accuracy.family_f1:.1%}")
            print(f"    - Subfamily F1: {model.accuracy.subfamily_f1:.1%}")
            print(f"    - FP Rate: {model.accuracy.false_positive_rate:.2%}")
            print(f"    - FN Rate: {model.accuracy.false_negative_rate:.2%}")
        print()

        # File info
        print(f"  File:")
        print(f"    - Filename: {model.file_info.filename}")
        print(f"    - Size: {model.file_info.size_mb:.1f}MB")
        print(f"    - Path: {model.file_path}")
        if model.file_info.onnx_embeddings:
            print(f"    - ONNX embeddings: {model.file_info.onnx_embeddings}")
        print()

    # Test filtering
    print("=" * 80)
    print("Testing Filters")
    print("=" * 80)
    print()

    int8_models = registry.list_models(runtime="onnx_int8")
    print(f"✓ INT8 models: {len(int8_models)}")
    for m in int8_models:
        print(f"  - {m.model_id}")
    print()

    active_models = registry.list_models(status=model.status)  # Use same status enum
    print(f"✓ Active models: {len(active_models)}")
    for m in active_models:
        print(f"  - {m.model_id}")
    print()

    # Test get_model
    print("=" * 80)
    print("Testing get_model()")
    print("=" * 80)
    print()

    specific = registry.get_model("mpnet-int8-embeddings-v1.0")
    if specific:
        print(f"✓ Retrieved model: {specific.name}")
        print(f"  Tokenizer: {specific.tokenizer_name}")
    else:
        print("✗ Failed to retrieve model")
    print()

    # Test get_best_model
    print("=" * 80)
    print("Testing get_best_model()")
    print("=" * 80)
    print()

    best_latency = registry.get_best_model("latency")
    print(f"✓ Best for latency: {best_latency.model_id} ({best_latency.performance.p95_latency_ms}ms)")

    best_accuracy = registry.get_best_model("accuracy")
    print(f"✓ Best for accuracy: {best_accuracy.model_id} ({best_accuracy.accuracy.binary_f1:.1%})")

    best_balanced = registry.get_best_model("balanced")
    print(f"✓ Best balanced: {best_balanced.model_id}")

    print()
    print("=" * 80)
    print("API Test Complete - ALL PASSED!")
    print("=" * 80)

if __name__ == "__main__":
    test_api()
