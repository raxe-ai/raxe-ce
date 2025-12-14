"""Manifest loader for model packages.

Loads and validates YAML manifest files for folder-based model packages.
Provides clear error messages for invalid manifests with fix suggestions.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from raxe.domain.ml.manifest_schema import ManifestSchema, validate_manifest

logger = logging.getLogger(__name__)


class ManifestError(Exception):
    """Base exception for manifest loading errors."""
    pass


class ManifestLoadError(ManifestError):
    """Error loading manifest file."""
    pass


class ManifestValidationError(ManifestError):
    """Error validating manifest data."""
    pass


class ManifestLoader:
    """Loader for model manifest YAML files.

    Handles loading, parsing, and validation of manifest files.
    Provides clear error messages and fix suggestions for common issues.

    Example:
        loader = ManifestLoader()

        # Load and validate manifest
        manifest = loader.load_manifest(
            Path("models/model-v1/manifest.yaml")
        )

        print(f"Model: {manifest.name}")
        print(f"Version: {manifest.version}")
        if manifest.tokenizer:
            print(f"Tokenizer: {manifest.tokenizer.name}")
    """

    def __init__(self, strict: bool = True):
        """Initialize manifest loader.

        Args:
            strict: If True, raise exceptions on validation errors.
                   If False, log warnings and return partial data.
        """
        self.strict = strict

    def load_manifest(self, path: Path) -> dict[str, Any]:
        """Load and validate manifest from YAML file.

        Args:
            path: Path to manifest.yaml file

        Returns:
            Validated manifest data as dictionary

        Raises:
            ManifestLoadError: If file cannot be read or parsed
            ManifestValidationError: If manifest validation fails (strict mode)

        Example:
            >>> loader = ManifestLoader()
            >>> data = loader.load_manifest(Path("model/manifest.yaml"))
            >>> print(data["name"])
            "RAXE L2 v1.0"
        """
        # Check file exists
        if not path.exists():
            raise ManifestLoadError(
                f"Manifest file not found: {path}\n"
                f"Expected location: {path.absolute()}\n"
                f"Fix: Create a manifest.yaml file in the model directory"
            )

        # Load YAML
        try:
            data = self._load_yaml(path)
        except Exception as e:
            raise ManifestLoadError(
                f"Failed to parse YAML from {path}: {e}\n"
                f"Fix: Check YAML syntax using 'python -m yaml {path}' or a YAML validator"
            ) from e

        # Validate schema
        is_valid, errors = validate_manifest(data)

        if not is_valid:
            error_msg = self._format_validation_errors(path, errors)
            if self.strict:
                raise ManifestValidationError(error_msg)
            else:
                logger.warning(f"Manifest validation warnings for {path}:\n{error_msg}")

        return data

    def load_manifest_schema(self, path: Path) -> ManifestSchema:
        """Load manifest and return as schema object.

        Args:
            path: Path to manifest.yaml file

        Returns:
            ManifestSchema instance

        Raises:
            ManifestLoadError: If file cannot be read
            ManifestValidationError: If validation fails
        """
        data = self.load_manifest(path)

        try:
            return ManifestSchema.from_dict(data)
        except Exception as e:
            raise ManifestValidationError(
                f"Failed to create manifest schema from {path}: {e}\n"
                f"This is likely a bug in the manifest loader."
            ) from e

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """Load YAML file with error handling.

        Args:
            path: Path to YAML file

        Returns:
            Parsed YAML data as dictionary

        Raises:
            ImportError: If PyYAML not installed
            Exception: If YAML parsing fails
        """
        try:
            import yaml
        except ImportError as e:
            raise ImportError(
                "Manifest loader requires PyYAML. "
                "Install with: pip install pyyaml"
            ) from e

        with open(path, encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                # Provide helpful error message with line number
                raise Exception(
                    f"YAML parsing error: {e}\n"
                    f"File: {path}\n"
                    f"Check for:\n"
                    f"  - Indentation errors (use spaces, not tabs)\n"
                    f"  - Missing colons after keys\n"
                    f"  - Unquoted special characters\n"
                    f"  - Unclosed quotes or brackets"
                ) from e

        if data is None:
            raise Exception(f"Empty YAML file: {path}")

        if not isinstance(data, dict):
            raise Exception(
                f"Invalid YAML structure in {path}: "
                f"Expected dictionary at root level, got {type(data).__name__}"
            )

        return data

    def _format_validation_errors(
        self,
        path: Path,
        errors: list[str]
    ) -> str:
        """Format validation errors with fix suggestions.

        Args:
            path: Path to manifest file
            errors: List of validation error messages

        Returns:
            Formatted error message with suggestions
        """
        lines = [
            f"Manifest validation failed: {path}",
            f"Found {len(errors)} error(s):",
            ""
        ]

        for i, error in enumerate(errors, 1):
            lines.append(f"{i}. {error}")

            # Add fix suggestions for common errors
            if "version" in error.lower() and "format" in error.lower():
                lines.append("   Fix: Use semantic versioning format: '0.0.1'")

            elif "status" in error.lower():
                lines.append("   Fix: Use one of: 'active', 'experimental', 'deprecated'")

            elif "tokenizer" in error.lower() and "name" in error.lower():
                lines.append("   Fix: Add tokenizer.name field (e.g., 'sentence-transformers/all-mpnet-base-v2')")

            elif "tokenizer" in error.lower() and "type" in error.lower():
                lines.append("   Fix: Add tokenizer.type field (e.g., 'AutoTokenizer')")

            elif "tokenizer" in error.lower() and "config" in error.lower():
                lines.append("   Fix: Add tokenizer.config as a dictionary with settings")

            elif "bundle_file" in error.lower():
                lines.append("   Fix: Add model.bundle_file field with .raxe bundle filename")

            lines.append("")

        # Add example manifest section
        lines.extend([
            "Example valid manifest structure:",
            "```yaml",
            "name: 'RAXE L2 v0.0.1'",
            "version: '0.0.1'",
            "status: 'active'",
            "",
            "model:",
            "  bundle_file: 'raxe_model_l2_v1.0.raxe'",
            "  embedding_model: 'all-mpnet-base-v2'",
            "",
            "tokenizer:",
            "  name: 'sentence-transformers/all-mpnet-base-v2'",
            "  type: 'AutoTokenizer'",
            "  config:",
            "    max_length: 512",
            "```"
        ])

        return "\n".join(lines)

    def validate_only(self, path: Path) -> tuple[bool, list[str]]:
        """Validate manifest without loading.

        Useful for pre-deployment validation checks.

        Args:
            path: Path to manifest.yaml file

        Returns:
            Tuple of (is_valid, error_messages)

        Example:
            >>> loader = ManifestLoader()
            >>> is_valid, errors = loader.validate_only(Path("model/manifest.yaml"))
            >>> if not is_valid:
            ...     for error in errors:
            ...         print(f"Error: {error}")
        """
        try:
            data = self._load_yaml(path)
        except Exception as e:
            return False, [f"Failed to load YAML: {e}"]

        return validate_manifest(data)


def load_manifest(path: Path, strict: bool = True) -> dict[str, Any]:
    """Convenience function to load manifest.

    Args:
        path: Path to manifest.yaml file
        strict: If True, raise on validation errors

    Returns:
        Validated manifest data

    Raises:
        ManifestLoadError: If file cannot be read
        ManifestValidationError: If validation fails (strict mode)

    Example:
        >>> data = load_manifest(Path("model/manifest.yaml"))
        >>> print(data["version"])
        "0.0.1"
    """
    loader = ManifestLoader(strict=strict)
    return loader.load_manifest(path)


def validate_manifest_file(path: Path) -> tuple[bool, list[str]]:
    """Convenience function to validate manifest.

    Args:
        path: Path to manifest.yaml file

    Returns:
        Tuple of (is_valid, error_messages)

    Example:
        >>> is_valid, errors = validate_manifest_file(Path("model/manifest.yaml"))
        >>> if is_valid:
        ...     print("Manifest is valid!")
    """
    loader = ManifestLoader()
    return loader.validate_only(path)
