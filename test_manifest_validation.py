#!/usr/bin/env python3
"""Test manifest validation for the enhanced model registry."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from raxe.domain.ml.manifest_loader import ManifestLoader, validate_manifest_file

def test_manifest_validation():
    """Test manifest validation for both model variants."""

    models_dir = Path("/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/models")

    # Test INT8 manifest
    int8_manifest = models_dir / "model_quantized_int8_deploy" / "manifest.yaml"
    print("=" * 80)
    print("Testing INT8 Manifest")
    print("=" * 80)
    print(f"Path: {int8_manifest}")
    print()

    is_valid, errors = validate_manifest_file(int8_manifest)

    if is_valid:
        print("✓ INT8 manifest is VALID")
    else:
        print(f"✗ INT8 manifest has {len(errors)} validation error(s):")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")

    print()

    # Test FP16 manifest
    fp16_manifest = models_dir / "model_quantized_fp16_deploy" / "manifest.yaml"
    print("=" * 80)
    print("Testing FP16 Manifest")
    print("=" * 80)
    print(f"Path: {fp16_manifest}")
    print()

    is_valid, errors = validate_manifest_file(fp16_manifest)

    if is_valid:
        print("✓ FP16 manifest is VALID")
    else:
        print(f"✗ FP16 manifest has {len(errors)} validation error(s):")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")

    print()
    print("=" * 80)

    # Try loading with non-strict mode
    print("\nTrying non-strict loading of INT8 manifest...")
    loader = ManifestLoader(strict=False)
    try:
        data = loader.load_manifest(int8_manifest)
        print(f"✓ Loaded (non-strict): {data.get('name', 'unknown')}")
        print(f"  - Has 'model' section: {'model' in data}")
        print(f"  - Has 'file_info' section: {'file_info' in data}")
        if 'model' in data:
            print(f"  - model.bundle_file: {data['model'].get('bundle_file', 'MISSING')}")
        if 'file_info' in data:
            print(f"  - file_info.filename: {data['file_info'].get('filename', 'MISSING')}")
    except Exception as e:
        print(f"✗ Failed to load: {e}")

if __name__ == "__main__":
    test_manifest_validation()
