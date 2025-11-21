#!/usr/bin/env python3
"""Test tokenizer validation in the enhanced model registry."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from raxe.domain.ml.model_registry import get_registry
from raxe.domain.ml.tokenizer_registry import get_tokenizer_registry

def test_tokenizer_validation():
    """Test tokenizer validation for discovered models."""

    print("=" * 80)
    print("Testing Tokenizer Validation")
    print("=" * 80)
    print()

    # Get registries
    model_registry = get_registry()
    tokenizer_registry = get_tokenizer_registry()

    # Get models
    models = model_registry.list_models()

    for model in models:
        print(f"Model: {model.model_id}")
        print(f"  Tokenizer Name: {model.tokenizer_name}")
        print(f"  Embedding Model: {model.embedding_model_name}")
        print()

        # Check compatibility
        if model.tokenizer_name and model.embedding_model_name:
            is_compat = tokenizer_registry.is_compatible(
                model.tokenizer_name,
                model.embedding_model_name
            )

            if is_compat:
                print(f"  ✓ Tokenizer compatible with embedding model")
            else:
                print(f"  ⚠ Tokenizer may not be compatible with embedding model")

            # Validate tokenizer config
            if model.tokenizer_config:
                is_valid, errors = tokenizer_registry.validate_tokenizer(
                    model.tokenizer_name,
                    model.tokenizer_config,
                    model.embedding_model_name
                )

                if is_valid:
                    print(f"  ✓ Tokenizer config is valid")
                else:
                    print(f"  ✗ Tokenizer config has {len(errors)} validation error(s):")
                    for err in errors:
                        print(f"      - {err}")

                # Show config details
                print(f"  Tokenizer Config:")
                for key, value in model.tokenizer_config.items():
                    print(f"    - {key}: {value}")
        else:
            print("  ⚠ Missing tokenizer or embedding model info")

        print()
        print("-" * 80)
        print()

    print("=" * 80)
    print("Tokenizer Validation Complete")
    print("=" * 80)

if __name__ == "__main__":
    test_tokenizer_validation()
