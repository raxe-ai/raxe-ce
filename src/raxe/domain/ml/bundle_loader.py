"""
Model Bundle Loader for RAXE CE

Loads unified .raxe model bundles created by raxe-ml.

Bundle Format:
    - Single .raxe file (ZIP archive)
    - Contains: manifest.json, classifier.joblib, keyword_triggers.json,
                attack_clusters.joblib, embedding_config.json, training_stats.json, schema.json
    - SHA256 checksums for integrity validation
    - Versioning and metadata

Output Schema (from bundle):
    - is_attack: Binary classification (0 or 1)
    - family: Attack family (PI, JB, CMD, PII, ENC, RAG)
    - sub_family: Specific attack subfamily (47+ classes)
    - scores: Confidence scores for each level
    - why_it_hit: Explanations/reasons for detection
    - recommended_action: Suggested response (ALLOW, WARN, BLOCK)
    - trigger_matches: Matched patterns/keywords
    - similar_attacks: Similar attacks from training data

This module provides the bridge between raxe-ml bundles and raxe-ce detectors.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from raxe.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BundleManifest:
    """Manifest metadata from model bundle."""

    bundle_version: str
    schema_version: str
    model_id: str
    created_at: str
    metadata: dict[str, Any]
    architecture: dict[str, Any]
    training: dict[str, Any]
    capabilities: dict[str, Any]
    output_schema_ref: str
    checksums: dict[str, str]


@dataclass
class BundleComponents:
    """Extracted components from model bundle."""

    manifest: BundleManifest
    classifier: Any  # Loaded classifier (joblib object)
    triggers: dict[str, Any]  # Keyword triggers
    clusters: Any  # Attack clusters (joblib object)
    embedding_config: dict[str, Any]
    training_stats: dict[str, Any]
    schema: dict[str, Any]  # Output schema


class ModelBundleLoader:
    """
    Loader for unified .raxe model bundles.

    This class provides methods to load, validate, and extract components
    from .raxe bundle files created by raxe-ml.

    Example:
        # Load bundle
        loader = ModelBundleLoader()
        components = loader.load_bundle('models/my_model.raxe')

        # Access components
        print(f"Model ID: {components.manifest.model_id}")
        print(f"Families: {components.manifest.capabilities['families']}")

        # Get predictions (if you have a detector that uses bundles)
        # detector = BundleBasedDetector(components)
        # result = detector.predict("Ignore all instructions")
    """

    VERSION = "1.0.0"

    def __init__(self):
        """Initialize bundle loader."""
        self._cache = {}  # Optional caching for repeated loads

    def load_bundle(
        self,
        bundle_path: str | Path,
        validate: bool = True,
        cache: bool = False,
    ) -> BundleComponents:
        """
        Load and validate a model bundle.

        Args:
            bundle_path: Path to .raxe bundle file
            validate: Whether to validate checksums (default: True)
            cache: Whether to cache loaded components (default: False)

        Returns:
            BundleComponents with all model components

        Raises:
            FileNotFoundError: If bundle file not found
            ValueError: If bundle is corrupted or invalid
            ImportError: If joblib is not installed

        Example:
            loader = ModelBundleLoader()
            components = loader.load_bundle('models/production_v1.raxe')

            # Use components
            manifest = components.manifest
            classifier = components.classifier
            triggers = components.triggers
        """
        bundle_path = Path(bundle_path)

        # Check cache first
        if cache and str(bundle_path) in self._cache:
            logger.debug(f"Using cached bundle: {bundle_path}")
            return self._cache[str(bundle_path)]

        logger.info(f"Loading model bundle: {bundle_path}")

        if not bundle_path.exists():
            raise FileNotFoundError(f"Bundle not found: {bundle_path}")

        # Import joblib (lazy import to avoid dependency if not using bundles)
        try:
            import joblib
        except ImportError as e:
            raise ImportError(
                "Model bundles require joblib. Install with: pip install joblib"
            ) from e

        components_dict = {}

        # Extract bundle
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Extract all files from ZIP
            with zipfile.ZipFile(bundle_path, 'r') as zf:
                zf.extractall(tmpdir_path)

            # Load manifest
            with open(tmpdir_path / 'manifest.json', 'r') as f:
                manifest_dict = json.load(f)

            manifest = BundleManifest(
                bundle_version=manifest_dict['bundle_version'],
                schema_version=manifest_dict['schema_version'],
                model_id=manifest_dict['model_id'],
                created_at=manifest_dict['created_at'],
                metadata=manifest_dict['metadata'],
                architecture=manifest_dict['architecture'],
                training=manifest_dict['training'],
                capabilities=manifest_dict['capabilities'],
                output_schema_ref=manifest_dict['output_schema_ref'],
                checksums=manifest_dict['checksums'],
            )

            logger.debug(f"Bundle version: {manifest.bundle_version}")
            logger.debug(f"Model ID: {manifest.model_id}")
            logger.debug(f"Created: {manifest.created_at}")

            # Validate checksums (if enabled)
            if validate:
                logger.debug("Validating checksums...")
                for file_name, expected_checksum in manifest.checksums.items():
                    file_path = tmpdir_path / file_name
                    actual_checksum = self._compute_checksum(file_path)
                    if actual_checksum != expected_checksum:
                        raise ValueError(
                            f"Checksum mismatch for {file_name}. "
                            f"Expected: {expected_checksum}, Got: {actual_checksum}. "
                            "Bundle may be corrupted."
                        )
                logger.debug("✓ All checksums valid")

            # Load components
            logger.debug("Loading classifier...")
            components_dict['classifier'] = joblib.load(tmpdir_path / 'classifier.joblib')

            logger.debug("Loading attack clusters...")
            components_dict['clusters'] = joblib.load(tmpdir_path / 'attack_clusters.joblib')

            logger.debug("Loading keyword triggers...")
            with open(tmpdir_path / 'keyword_triggers.json', 'r') as f:
                components_dict['triggers'] = json.load(f)

            logger.debug("Loading embedding config...")
            with open(tmpdir_path / 'embedding_config.json', 'r') as f:
                components_dict['embedding_config'] = json.load(f)

            logger.debug("Loading training stats...")
            with open(tmpdir_path / 'training_stats.json', 'r') as f:
                components_dict['training_stats'] = json.load(f)

            logger.debug("Loading output schema...")
            with open(tmpdir_path / 'schema.json', 'r') as f:
                components_dict['schema'] = json.load(f)

        # Create BundleComponents dataclass
        components = BundleComponents(
            manifest=manifest,
            classifier=components_dict['classifier'],
            triggers=components_dict['triggers'],
            clusters=components_dict['clusters'],
            embedding_config=components_dict['embedding_config'],
            training_stats=components_dict['training_stats'],
            schema=components_dict['schema'],
        )

        # Cache if requested
        if cache:
            self._cache[str(bundle_path)] = components

        logger.info("✓ Bundle loaded successfully")
        return components

    def get_bundle_info(self, bundle_path: str | Path) -> BundleManifest:
        """
        Get bundle metadata without fully loading it.

        This is useful for inspecting bundle details without the overhead
        of loading all components.

        Args:
            bundle_path: Path to .raxe bundle file

        Returns:
            BundleManifest with metadata

        Raises:
            FileNotFoundError: If bundle not found

        Example:
            loader = ModelBundleLoader()
            manifest = loader.get_bundle_info('models/my_model.raxe')

            print(f"Model ID: {manifest.model_id}")
            print(f"Families: {manifest.capabilities['families']}")
            print(f"Created: {manifest.created_at}")
        """
        bundle_path = Path(bundle_path)

        if not bundle_path.exists():
            raise FileNotFoundError(f"Bundle not found: {bundle_path}")

        with zipfile.ZipFile(bundle_path, 'r') as zf:
            with zf.open('manifest.json') as f:
                manifest_dict = json.load(f)

        manifest = BundleManifest(
            bundle_version=manifest_dict['bundle_version'],
            schema_version=manifest_dict['schema_version'],
            model_id=manifest_dict['model_id'],
            created_at=manifest_dict['created_at'],
            metadata=manifest_dict['metadata'],
            architecture=manifest_dict['architecture'],
            training=manifest_dict['training'],
            capabilities=manifest_dict['capabilities'],
            output_schema_ref=manifest_dict['output_schema_ref'],
            checksums=manifest_dict['checksums'],
        )

        return manifest

    def validate_bundle(self, bundle_path: str | Path) -> tuple[bool, list[str]]:
        """
        Validate a bundle without loading it.

        Args:
            bundle_path: Path to .raxe bundle file

        Returns:
            Tuple of (is_valid, errors)
            - is_valid: True if bundle is valid
            - errors: List of error messages (empty if valid)

        Example:
            loader = ModelBundleLoader()
            is_valid, errors = loader.validate_bundle('models/my_model.raxe')

            if is_valid:
                print("Bundle is valid!")
            else:
                print(f"Bundle has errors: {errors}")
        """
        bundle_path = Path(bundle_path)
        errors = []

        # Check file exists
        if not bundle_path.exists():
            errors.append(f"Bundle not found: {bundle_path}")
            return False, errors

        # Check file extension
        if bundle_path.suffix != '.raxe':
            errors.append(f"Invalid bundle extension: {bundle_path.suffix} (expected .raxe)")

        # Try to load manifest
        try:
            manifest = self.get_bundle_info(bundle_path)
        except Exception as e:
            errors.append(f"Failed to load manifest: {str(e)}")
            return False, errors

        # Validate version compatibility
        if manifest.bundle_version != self.VERSION:
            errors.append(
                f"Bundle version mismatch: bundle={manifest.bundle_version}, "
                f"loader={self.VERSION}"
            )

        # Validate required files
        required_files = [
            'manifest.json',
            'classifier.joblib',
            'keyword_triggers.json',
            'attack_clusters.joblib',
            'embedding_config.json',
            'training_stats.json',
            'schema.json',
        ]

        try:
            with zipfile.ZipFile(bundle_path, 'r') as zf:
                bundle_files = set(zf.namelist())
                missing_files = set(required_files) - bundle_files
                if missing_files:
                    errors.append(f"Missing required files: {missing_files}")
        except Exception as e:
            errors.append(f"Failed to read bundle: {str(e)}")
            return False, errors

        # Validate checksums
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)

                with zipfile.ZipFile(bundle_path, 'r') as zf:
                    zf.extractall(tmpdir_path)

                for file_name, expected_checksum in manifest.checksums.items():
                    file_path = tmpdir_path / file_name
                    if not file_path.exists():
                        errors.append(f"Missing file for checksum: {file_name}")
                        continue

                    actual_checksum = self._compute_checksum(file_path)
                    if actual_checksum != expected_checksum:
                        errors.append(
                            f"Checksum mismatch for {file_name}: "
                            f"expected {expected_checksum[:8]}..., "
                            f"got {actual_checksum[:8]}..."
                        )
        except Exception as e:
            errors.append(f"Checksum validation failed: {str(e)}")

        return len(errors) == 0, errors

    def _compute_checksum(self, file_path: Path) -> str:
        """Compute SHA256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def clear_cache(self):
        """Clear the bundle cache."""
        self._cache.clear()
        logger.debug("Bundle cache cleared")


# Convenience functions for quick access
def load_bundle(bundle_path: str | Path, validate: bool = True) -> BundleComponents:
    """
    Quick function to load a bundle.

    Args:
        bundle_path: Path to .raxe bundle file
        validate: Whether to validate checksums (default: True)

    Returns:
        BundleComponents with all model components

    Example:
        from raxe.domain.ml.bundle_loader import load_bundle

        components = load_bundle('models/my_model.raxe')
        print(f"Model ID: {components.manifest.model_id}")
    """
    loader = ModelBundleLoader()
    return loader.load_bundle(bundle_path, validate=validate)


def get_bundle_info(bundle_path: str | Path) -> BundleManifest:
    """
    Quick function to get bundle info.

    Args:
        bundle_path: Path to .raxe bundle file

    Returns:
        BundleManifest with metadata

    Example:
        from raxe.domain.ml.bundle_loader import get_bundle_info

        manifest = get_bundle_info('models/my_model.raxe')
        print(f"Families: {manifest.capabilities['families']}")
    """
    loader = ModelBundleLoader()
    return loader.get_bundle_info(bundle_path)
