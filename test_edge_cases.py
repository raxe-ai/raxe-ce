#!/usr/bin/env python3
"""Test edge cases and error handling for model registry."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from raxe.domain.ml.model_registry import ModelRegistry

def test_edge_cases():
    """Test edge cases and error handling."""

    print("=" * 80)
    print("Testing Edge Cases and Error Handling")
    print("=" * 80)
    print()

    # Test 1: Empty directory
    print("Test 1: Empty models directory")
    print("-" * 40)
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = ModelRegistry(Path(tmpdir))
        count = registry.get_model_count()
        if count == 0:
            print(f"✓ Empty directory handled: {count} models (expected: 0)")
        else:
            print(f"✗ Failed: Found {count} models in empty directory")
    print()

    # Test 2: Non-existent directory
    print("Test 2: Non-existent directory")
    print("-" * 40)
    registry = ModelRegistry(Path("/nonexistent/path/to/models"))
    count = registry.get_model_count()
    if count == 0:
        print(f"✓ Non-existent directory handled: {count} models")
    else:
        print(f"✗ Failed: Found {count} models in non-existent directory")
    print()

    # Test 3: Invalid manifest.yaml
    print("Test 3: Invalid manifest.yaml (corrupted YAML)")
    print("-" * 40)
    with tempfile.TemporaryDirectory() as tmpdir:
        models_dir = Path(tmpdir) / "models"
        model_dir = models_dir / "test_model"
        model_dir.mkdir(parents=True)

        # Create invalid YAML
        manifest_file = model_dir / "manifest.yaml"
        manifest_file.write_text("invalid: yaml: [unclosed bracket")

        registry = ModelRegistry(models_dir)
        count = registry.get_model_count()
        if count == 0:
            print(f"✓ Invalid YAML handled gracefully: {count} models")
        else:
            print(f"✗ Failed: Found {count} models with invalid YAML")
    print()

    # Test 4: Manifest with missing required fields
    print("Test 4: Manifest with missing required fields")
    print("-" * 40)
    with tempfile.TemporaryDirectory() as tmpdir:
        models_dir = Path(tmpdir) / "models"
        model_dir = models_dir / "test_model"
        model_dir.mkdir(parents=True)

        # Create manifest missing required fields
        manifest_file = model_dir / "manifest.yaml"
        manifest_file.write_text("""
name: "Test Model"
# Missing version, status, model section
""")

        registry = ModelRegistry(models_dir)
        count = registry.get_model_count()
        if count == 0:
            print(f"✓ Missing required fields handled: {count} models")
        else:
            print(f"⚠ Loaded despite missing fields: {count} models (may be acceptable)")
    print()

    # Test 5: Get non-existent model
    print("Test 5: Get non-existent model")
    print("-" * 40)
    registry = ModelRegistry()  # Use default models dir
    model = registry.get_model("non-existent-model-id")
    if model is None:
        print("✓ Non-existent model returns None")
    else:
        print(f"✗ Failed: Returned model for non-existent ID: {model.model_id}")
    print()

    # Test 6: Filter with no matches
    print("Test 6: Filter with no matches")
    print("-" * 40)
    from raxe.domain.ml.model_metadata import ModelStatus
    registry = ModelRegistry()
    models = registry.list_models(status=ModelStatus.DEPRECATED)
    if len(models) == 0:
        print(f"✓ Filter with no matches returns empty list")
    else:
        print(f"⚠ Found {len(models)} deprecated models")
    print()

    # Test 7: Runtime filter
    print("Test 7: Runtime filter with invalid runtime")
    print("-" * 40)
    models = registry.list_models(runtime="invalid_runtime")
    if len(models) == 0:
        print(f"✓ Invalid runtime filter returns empty list")
    else:
        print(f"✗ Failed: Found {len(models)} models with invalid runtime")
    print()

    # Test 8: get_best_model with no models
    print("Test 8: get_best_model with empty registry")
    print("-" * 40)
    with tempfile.TemporaryDirectory() as tmpdir:
        empty_registry = ModelRegistry(Path(tmpdir))
        best = empty_registry.get_best_model("latency")
        if best is None:
            print("✓ get_best_model returns None for empty registry")
        else:
            print(f"✗ Failed: Returned model from empty registry: {best.model_id}")
    print()

    # Test 9: Model with no accuracy metrics
    print("Test 9: Scoring model with missing accuracy metrics")
    print("-" * 40)
    registry = ModelRegistry()
    models = registry.list_models()
    if models:
        # Try to get best by accuracy
        best = registry.get_best_model("accuracy")
        if best:
            print(f"✓ get_best_model handles missing metrics: {best.model_id}")
        else:
            print("⚠ get_best_model returned None (may be expected)")
    print()

    # Test 10: Compatibility test - both formats
    print("Test 10: Both bundle and ONNX manifest formats")
    print("-" * 40)
    with tempfile.TemporaryDirectory() as tmpdir:
        models_dir = Path(tmpdir) / "models"

        # Create bundle format manifest
        bundle_dir = models_dir / "bundle_model"
        bundle_dir.mkdir(parents=True)
        bundle_manifest = bundle_dir / "manifest.yaml"
        bundle_manifest.write_text("""
name: "Bundle Model"
version: "1.0.0"
status: "active"
model:
  bundle_file: "model.raxe"
  embedding_model: "all-mpnet-base-v2"
tokenizer:
  name: "sentence-transformers/all-mpnet-base-v2"
  type: "AutoTokenizer"
  config:
    max_length: 512
""")

        # Create ONNX format manifest
        onnx_dir = models_dir / "onnx_model"
        onnx_dir.mkdir(parents=True)
        onnx_manifest = onnx_dir / "manifest.yaml"
        onnx_manifest.write_text("""
name: "ONNX Model"
version: "1.0.0"
metadata:
  status: "active"
file_info:
  filename: "model.onnx"
  size_mb: 100.0
tokenizer:
  tokenizer_name: "sentence-transformers/all-mpnet-base-v2"
  tokenizer_class: "MPNetTokenizer"
  max_length: 512
""")

        registry = ModelRegistry(models_dir)
        count = registry.get_model_count()
        if count == 2:
            print(f"✓ Both manifest formats loaded: {count} models")
            for m in registry.list_models():
                print(f"  - {m.model_id}: {m.name}")
        else:
            print(f"✗ Failed: Expected 2 models, got {count}")
    print()

    print("=" * 80)
    print("Edge Case Testing Complete")
    print("=" * 80)

if __name__ == "__main__":
    test_edge_cases()
