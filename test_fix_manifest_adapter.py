#!/usr/bin/env python3
"""Test a quick fix for manifest format compatibility.

This demonstrates how to adapt the ONNX manifest format to the expected bundle format.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import yaml


def adapt_onnx_manifest_to_bundle_format(manifest_data: dict) -> dict:
    """Adapt ONNX manifest format to bundle manifest format.

    Args:
        manifest_data: Original ONNX manifest data

    Returns:
        Adapted manifest in bundle format
    """
    adapted = manifest_data.copy()

    # 1. Move metadata.status to root level
    if "metadata" in manifest_data and "status" in manifest_data["metadata"]:
        adapted["status"] = manifest_data["metadata"]["status"]

    # 2. Create model section from file_info
    if "file_info" in manifest_data:
        file_info = manifest_data["file_info"]
        adapted["model"] = {
            "bundle_file": file_info.get("filename", ""),
            "runtime": "onnx_int8" if "int8" in file_info.get("filename", "") else "onnx",
        }

        # Add embedding model if in metadata
        if "metadata" in manifest_data:
            base_model = manifest_data["metadata"].get("base_model")
            if base_model:
                adapted["model"]["embedding_model"] = base_model

    # 3. Adapt tokenizer structure
    if "tokenizer" in manifest_data:
        tok = manifest_data["tokenizer"]
        adapted["tokenizer"] = {
            "name": tok.get("tokenizer_name", tok.get("hf_model_id", "")),
            "type": tok.get("tokenizer_class", "AutoTokenizer"),
            "config": {
                "max_length": tok.get("max_length", 512),
                "model_max_length": tok.get("model_max_length", 512),
                "do_lower_case": tok.get("do_lower_case", False),
                "padding_side": tok.get("padding_side", "right"),
                "truncation_side": tok.get("truncation_side", "right"),
            }
        }

    return adapted


def test_adaptation():
    """Test ONNX manifest adaptation."""

    manifest_path = Path("/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/models/model_quantized_int8_deploy/manifest.yaml")

    print("=" * 80)
    print("Testing Manifest Adaptation")
    print("=" * 80)
    print()

    # Load original
    with open(manifest_path, "r") as f:
        original = yaml.safe_load(f)

    print("Original manifest structure:")
    print(f"  - Has 'status': {'status' in original}")
    print(f"  - Has 'model': {'model' in original}")
    print(f"  - Has 'metadata.status': {'metadata' in original and 'status' in original.get('metadata', {})}")
    print(f"  - Has 'file_info': {'file_info' in original}")
    print()

    # Adapt
    adapted = adapt_onnx_manifest_to_bundle_format(original)

    print("Adapted manifest structure:")
    print(f"  - Has 'status': {'status' in adapted}")
    print(f"  - Has 'model': {'model' in adapted}")
    print(f"  - Has 'model.bundle_file': {'model' in adapted and 'bundle_file' in adapted.get('model', {})}")
    print(f"  - Has 'tokenizer.name': {'tokenizer' in adapted and 'name' in adapted.get('tokenizer', {})}")
    print(f"  - Has 'tokenizer.type': {'tokenizer' in adapted and 'type' in adapted.get('tokenizer', {})}")
    print(f"  - Has 'tokenizer.config': {'tokenizer' in adapted and 'config' in adapted.get('tokenizer', {})}")
    print()

    # Show key values
    print("Key values:")
    print(f"  status: {adapted.get('status')}")
    print(f"  model.bundle_file: {adapted.get('model', {}).get('bundle_file')}")
    print(f"  tokenizer.name: {adapted.get('tokenizer', {}).get('name')}")
    print(f"  tokenizer.type: {adapted.get('tokenizer', {}).get('type')}")
    print(f"  tokenizer.config.max_length: {adapted.get('tokenizer', {}).get('config', {}).get('max_length')}")
    print()

    # Validate with manifest schema
    from raxe.domain.ml.manifest_schema import validate_manifest

    is_valid, errors = validate_manifest(adapted)

    print("=" * 80)
    if is_valid:
        print("✓ Adapted manifest is VALID!")
    else:
        print(f"✗ Adapted manifest has {len(errors)} validation error(s):")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")

    print("=" * 80)

    return adapted, is_valid


if __name__ == "__main__":
    adapted, is_valid = test_adaptation()

    if is_valid:
        print("\nSUCCESS! Adaptation strategy works.")
        print("Next step: Implement this in model_registry.py")
    else:
        print("\nFAILED! Adaptation needs refinement.")
