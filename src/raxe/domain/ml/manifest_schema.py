"""Manifest schema definition for model packages.

Defines the YAML manifest structure for folder-based model packages.
Manifests provide rich metadata about models including tokenizer requirements,
performance metrics, and deployment information.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ModelStatus(Enum):
    """Model deployment status."""
    ACTIVE = "active"
    EXPERIMENTAL = "experimental"
    DEPRECATED = "deprecated"


@dataclass
class TokenizerConfig:
    """Tokenizer configuration from manifest.

    Specifies the tokenizer to use with the model and its settings.
    Used to ensure tokenizer compatibility with embedding models.
    """
    name: str
    type: str
    config: dict[str, Any]

    def validate(self) -> tuple[bool, list[str]]:
        """Validate tokenizer configuration.

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        if not self.name:
            errors.append("Tokenizer name is required")

        if not self.type:
            errors.append("Tokenizer type is required")

        if not isinstance(self.config, dict):
            errors.append("Tokenizer config must be a dictionary")

        return len(errors) == 0, errors


@dataclass
class ManifestSchema:
    """Schema for model manifest YAML files.

    Defines the complete structure of a model manifest including
    all required and optional fields.

    Example manifest structure:
        name: "RAXE L2 v0.0.1 ONNX INT8"
        version: "0.0.1"
        status: "active"

        model:
          bundle_file: "raxe_model_l2_v1.0.raxe"
          embedding_model: "all-mpnet-base-v2"

        tokenizer:
          name: "sentence-transformers/all-mpnet-base-v2"
          type: "AutoTokenizer"
          config:
            max_length: 512

        performance:
          target_latency_ms: 3.0
          memory_mb: 130
    """
    # Required fields
    name: str
    version: str
    status: str

    # Model configuration
    model: dict[str, Any]

    # Optional fields
    tokenizer: TokenizerConfig | None = None
    performance: dict[str, Any] | None = None
    accuracy: dict[str, Any] | None = None
    deployment: dict[str, Any] | None = None

    @property
    def model_status(self) -> ModelStatus:
        """Get status as enum."""
        return ModelStatus(self.status)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ManifestSchema:
        """Create schema from dictionary.

        Args:
            data: Raw manifest data from YAML

        Returns:
            ManifestSchema instance

        Raises:
            ValueError: If required fields missing
        """
        # Extract required fields
        name = data.get("name")
        version = data.get("version")
        status = data.get("status", "experimental")
        model = data.get("model", {})

        # Parse tokenizer if present
        tokenizer = None
        if data.get("tokenizer"):
            tok_data = data["tokenizer"]
            tokenizer = TokenizerConfig(
                name=tok_data.get("name", ""),
                type=tok_data.get("type", ""),
                config=tok_data.get("config", {})
            )

        return cls(
            name=name,
            version=version,
            status=status,
            model=model,
            tokenizer=tokenizer,
            performance=data.get("performance"),
            accuracy=data.get("accuracy"),
            deployment=data.get("deployment")
        )


def validate_manifest(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate manifest data against schema.

    Performs comprehensive validation including:
    - Required fields present
    - Version format valid
    - Status enum valid
    - Tokenizer config valid (if present)
    - Performance metrics valid (if present)

    Args:
        data: Raw manifest data from YAML

    Returns:
        Tuple of (is_valid, error_messages)

    Example:
        >>> is_valid, errors = validate_manifest(manifest_data)
        >>> if not is_valid:
        ...     for error in errors:
        ...         print(f"Validation error: {error}")
    """
    errors = []

    # Required fields
    if "name" not in data or not data["name"]:
        errors.append("Field 'name' is required")

    if "version" not in data or not data["version"]:
        errors.append("Field 'version' is required")
    else:
        # Validate version format (semantic versioning)
        version = data["version"]
        if not validate_version_format(version):
            errors.append(
                f"Invalid version format: {version}. "
                "Expected semantic versioning (e.g., '0.0.1', '0.1.0')"
            )

    if "status" not in data or not data["status"]:
        errors.append("Field 'status' is required")
    else:
        # Validate status enum
        status = data["status"]
        valid_statuses = [s.value for s in ModelStatus]
        if status not in valid_statuses:
            errors.append(
                f"Invalid status: {status}. "
                f"Must be one of: {', '.join(valid_statuses)}"
            )

    if "model" not in data or not data["model"]:
        errors.append("Field 'model' is required")
    else:
        # Validate model section
        model = data["model"]
        if not isinstance(model, dict):
            errors.append("Field 'model' must be a dictionary")
        else:
            if "bundle_file" not in model:
                errors.append("Field 'model.bundle_file' is required")

    # Optional tokenizer validation
    if data.get("tokenizer"):
        tok_data = data["tokenizer"]
        if not isinstance(tok_data, dict):
            errors.append("Field 'tokenizer' must be a dictionary")
        else:
            # Validate tokenizer fields
            if "name" not in tok_data or not tok_data["name"]:
                errors.append("Field 'tokenizer.name' is required when tokenizer is specified")

            if "type" not in tok_data or not tok_data["type"]:
                errors.append("Field 'tokenizer.type' is required when tokenizer is specified")

            if "config" not in tok_data or not isinstance(tok_data.get("config"), dict):
                errors.append("Field 'tokenizer.config' must be a dictionary when tokenizer is specified")

    # Optional performance validation
    if data.get("performance"):
        perf = data["performance"]
        if not isinstance(perf, dict):
            errors.append("Field 'performance' must be a dictionary")
        else:
            # Validate numeric fields
            numeric_fields = ["target_latency_ms", "p50_latency_ms", "p95_latency_ms",
                            "p99_latency_ms", "memory_mb"]
            for field in numeric_fields:
                if field in perf:
                    value = perf[field]
                    if not isinstance(value, (int, float)) or value < 0:
                        errors.append(
                            f"Field 'performance.{field}' must be a non-negative number"
                        )

    # Optional accuracy validation
    if data.get("accuracy"):
        acc = data["accuracy"]
        if not isinstance(acc, dict):
            errors.append("Field 'accuracy' must be a dictionary")
        else:
            # Validate metric fields (0-1 range)
            metric_fields = ["binary_f1", "family_f1", "subfamily_f1",
                           "false_positive_rate", "false_negative_rate"]
            for field in metric_fields:
                if field in acc:
                    value = acc[field]
                    if not isinstance(value, (int, float)) or not (0 <= value <= 1):
                        errors.append(
                            f"Field 'accuracy.{field}' must be a number between 0 and 1"
                        )

    return len(errors) == 0, errors


def validate_version_format(version: str) -> bool:
    """Validate semantic version format.

    Accepts formats like:
    - "0.0.1"
    - "0.1.0"
    - "0.0.1-beta"
    - "0.1.0-rc.1"

    Args:
        version: Version string to validate

    Returns:
        True if valid semantic version format
    """
    # Semantic versioning pattern: MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
    pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.-]+))?(?:\+([a-zA-Z0-9.-]+))?$"
    return bool(re.match(pattern, version))


def validate_tokenizer(tokenizer_data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate tokenizer configuration.

    Checks that tokenizer has all required fields and valid values.

    Args:
        tokenizer_data: Tokenizer section from manifest

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    if not isinstance(tokenizer_data, dict):
        errors.append("Tokenizer must be a dictionary")
        return False, errors

    # Required fields
    required = ["name", "type", "config"]
    for field in required:
        if field not in tokenizer_data or not tokenizer_data[field]:
            errors.append(f"Tokenizer field '{field}' is required")

    # Validate config is a dict
    if "config" in tokenizer_data:
        config = tokenizer_data["config"]
        if not isinstance(config, dict):
            errors.append("Tokenizer config must be a dictionary")

    return len(errors) == 0, errors


def get_required_fields() -> list[str]:
    """Get list of required manifest fields.

    Returns:
        List of required field names
    """
    return [
        "name",
        "version",
        "status",
        "model",
        "model.bundle_file"
    ]


def get_optional_fields() -> list[str]:
    """Get list of optional manifest fields.

    Returns:
        List of optional field names
    """
    return [
        "tokenizer",
        "tokenizer.name",
        "tokenizer.type",
        "tokenizer.config",
        "performance",
        "performance.target_latency_ms",
        "performance.p50_latency_ms",
        "performance.p95_latency_ms",
        "performance.p99_latency_ms",
        "performance.memory_mb",
        "accuracy",
        "accuracy.binary_f1",
        "accuracy.family_f1",
        "accuracy.subfamily_f1",
        "deployment",
        "deployment.status",
        "deployment.environments"
    ]
