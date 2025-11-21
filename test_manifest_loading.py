#!/usr/bin/env python3
"""Debug manifest loading process step by step."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from raxe.domain.ml.manifest_loader import ManifestLoader
import yaml

def test_manifest_structure():
    """Test the actual structure of the manifest files."""

    manifest_path = Path("/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/models/model_quantized_int8_deploy/manifest.yaml")

    print("=" * 80)
    print("Examining Manifest Structure")
    print("=" * 80)
    print(f"Path: {manifest_path}\n")

    # Load raw YAML
    with open(manifest_path, "r") as f:
        data = yaml.safe_load(f)

    # Show top-level keys
    print("Top-level keys in manifest:")
    for key in sorted(data.keys()):
        print(f"  - {key}")

    print()

    # Check specific sections
    print("Section analysis:")
    print()

    # Status
    if "status" in data:
        print(f"  ✓ 'status' field exists: {data['status']}")
    elif "metadata" in data and "status" in data["metadata"]:
        print(f"  ⚠ 'status' is in metadata section: {data['metadata']['status']}")
        print(f"    (Expected at root level)")
    else:
        print("  ✗ 'status' field missing")

    print()

    # Model section
    if "model" in data:
        print(f"  ✓ 'model' section exists")
        if "bundle_file" in data["model"]:
            print(f"    ✓ model.bundle_file: {data['model']['bundle_file']}")
        else:
            print("    ✗ model.bundle_file missing")
            if "embedding_model" in data["model"]:
                print(f"    Has model.embedding_model: {data['model']['embedding_model']}")
    else:
        print("  ✗ 'model' section missing")
        if "file_info" in data:
            print(f"    Found 'file_info' section instead:")
            print(f"      - filename: {data['file_info'].get('filename', 'N/A')}")

    print()

    # Tokenizer
    if "tokenizer" in data:
        tok = data["tokenizer"]
        print(f"  ✓ 'tokenizer' section exists")

        if isinstance(tok, dict):
            print(f"    - Keys: {list(tok.keys())}")

            # Check required fields
            if "name" in tok:
                print(f"    ✓ tokenizer.name: {tok.get('name')}")
            else:
                print("    ✗ tokenizer.name missing")
                if "tokenizer_name" in tok:
                    print(f"      Found 'tokenizer_name': {tok['tokenizer_name']}")

            if "type" in tok:
                print(f"    ✓ tokenizer.type: {tok.get('type')}")
            else:
                print("    ✗ tokenizer.type missing")
                if "tokenizer_class" in tok:
                    print(f"      Found 'tokenizer_class': {tok['tokenizer_class']}")

            if "config" in tok:
                if isinstance(tok["config"], dict):
                    print(f"    ✓ tokenizer.config exists (dict with {len(tok['config'])} keys)")
                else:
                    print(f"    ✗ tokenizer.config is not a dict: {type(tok['config'])}")
            else:
                print("    ✗ tokenizer.config missing")
        else:
            print(f"    ✗ tokenizer is not a dict: {type(tok)}")

    else:
        print("  ✗ 'tokenizer' section missing")

    print()
    print("=" * 80)
    print("\nConclusion:")
    print("The manifest uses a different structure than expected by ManifestSchema.")
    print("It appears to be an ONNX model manifest, not a .raxe bundle manifest.")
    print()
    print("Expected structure (for .raxe bundles):")
    print("  - status: 'active'")
    print("  - model:")
    print("      bundle_file: 'model.raxe'")
    print("  - tokenizer:")
    print("      name: '...'")
    print("      type: '...'")
    print("      config: {}")
    print()
    print("Actual structure (ONNX model):")
    print("  - metadata:")
    print("      status: 'active'")
    print("  - file_info:")
    print("      filename: 'model.onnx'")
    print("  - tokenizer:")
    print("      tokenizer_name: '...'")
    print("      tokenizer_class: '...'")
    print("      (various tokenizer settings)")

if __name__ == "__main__":
    test_manifest_structure()
