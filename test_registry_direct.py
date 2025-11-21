#!/usr/bin/env python3
"""Test model registry directly to see what happens with current manifests."""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)-8s %(name)s: %(message)s'
)

from raxe.domain.ml.model_registry import ModelRegistry

def test_registry_discovery():
    """Test model registry discovery with current manifests."""

    models_dir = Path("/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/models")

    print("=" * 80)
    print("Testing Model Registry Discovery")
    print("=" * 80)
    print(f"Models directory: {models_dir}")
    print()

    # Create registry
    try:
        registry = ModelRegistry(models_dir)
        print(f"\n✓ Registry created successfully")
        print(f"  Total models discovered: {registry.get_model_count()}")
        print(f"  Active models: {registry.get_active_model_count()}")
        print()

        # List all models
        models = registry.list_models()
        print(f"Models found: {len(models)}")
        for model in models:
            print(f"\n  Model ID: {model.model_id}")
            print(f"    Name: {model.name}")
            print(f"    Version: {model.version}")
            print(f"    Status: {model.status.value}")
            print(f"    Runtime: {model.runtime_type}")
            print(f"    Tokenizer: {model.tokenizer_name or 'N/A'}")
            print(f"    Embedding Model: {model.embedding_model_name or 'N/A'}")
            print(f"    File: {model.file_path}")

        print()
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Registry creation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_registry_discovery()
