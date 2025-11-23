"""Model Discovery Service for L2 ML Detection.

This service discovers folder-based ONNX models:
1. Search for ONNX model folders (fast loading: ~200ms)
2. Fall back to stub detector if no models found

Design Goals:
- Fast loading with folder-based ONNX models
- Graceful fallback on missing/corrupted models
- Comprehensive error reporting
- Production-ready telemetry
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal

from raxe.utils.logging import get_logger

logger = get_logger(__name__)


class ModelType(Enum):
    """Type of model discovered."""
    ONNX_ONLY = "onnx_only"  # Pure ONNX models in folder (embeddings + classifiers)
    STUB = "stub"  # Fallback stub detector (no real detection)


@dataclass
class DiscoveredModel:
    """Information about a discovered model.

    Attributes:
        model_type: Type of model (ONNX_ONLY or stub)
        model_dir: Path to folder containing ONNX models
        model_id: Model identifier from metadata
        estimated_load_time_ms: Estimated time to load model
        metadata: Additional metadata from registry
    """
    model_type: ModelType
    model_dir: Path | None  # Folder containing ONNX models
    model_id: str
    estimated_load_time_ms: float
    metadata: dict | None = None

    @property
    def is_stub(self) -> bool:
        """True if this is a stub (no real detection)."""
        return self.model_type == ModelType.STUB


class ModelDiscoveryService:
    """Service for discovering and selecting L2 models.

    This service discovers folder-based ONNX models:
    1. Look for ONNX model folders (fast: ~200ms load time)
    2. Fall back to stub detector if no models available

    Example:
        service = ModelDiscoveryService()

        # Find best model
        model = service.find_best_model()

        if not model.is_stub:
            print(f"Using ONNX model: {model.model_dir}")
            print(f"Estimated load: {model.estimated_load_time_ms}ms")
        else:
            print("Using stub detector")
    """

    # Performance estimates (from benchmarking)
    ONNX_LOAD_TIME_MS = 200  # ONNX folder load time
    STUB_LOAD_TIME_MS = 1  # stub detector (instant)

    def __init__(self, models_dir: Path | None = None):
        """Initialize discovery service.

        Args:
            models_dir: Optional custom models directory
                       (default: src/raxe/domain/ml/models)
        """
        if models_dir is None:
            # Default to package models directory
            # src/raxe/infrastructure/models/discovery.py -> src/raxe/domain/ml/models
            current_file = Path(__file__)
            models_dir = current_file.parent.parent.parent / "domain" / "ml" / "models"

        self.models_dir = models_dir
        logger.info(f"Model discovery service initialized (models_dir: {models_dir})")

    def find_best_model(
        self,
        criteria: Literal["latency", "accuracy", "balanced"] = "latency"
    ) -> DiscoveredModel:
        """Find best available model based on criteria.

        This implements folder-based ONNX discovery:
        1. Try to find ONNX-only folders
        2. Fall back to stub detector

        Args:
            criteria: Selection criteria (default: "latency")

        Returns:
            DiscoveredModel with best available option

        Example:
            service = ModelDiscoveryService()
            model = service.find_best_model(criteria="latency")

            if model.model_type == ModelType.ONNX_ONLY:
                print("Found ONNX model folder!")
            else:
                print("No models found - using stub")
        """
        start_time = time.perf_counter()

        # Try to find ONNX-only folders
        try:
            onnx_only_model = self._discover_onnx_folders()
            if onnx_only_model:
                discovery_time_ms = (time.perf_counter() - start_time) * 1000
                logger.info(
                    "model_discovery_success",
                    model_type="onnx_only",
                    model_id=onnx_only_model.model_id,
                    model_dir=str(onnx_only_model.model_dir),
                    estimated_load_ms=onnx_only_model.estimated_load_time_ms,
                    discovery_time_ms=discovery_time_ms,
                )
                return onnx_only_model
        except Exception as e:
            logger.warning(f"ONNX folder discovery failed: {e}", exc_info=True)

        # Fall back to stub detector (no real detection)
        discovery_time_ms = (time.perf_counter() - start_time) * 1000
        logger.warning(
            "model_discovery_fallback_to_stub",
            models_dir=str(self.models_dir),
            discovery_time_ms=discovery_time_ms,
            help="No L2 models found. Place ONNX model folder in models directory.",
        )

        return DiscoveredModel(
            model_type=ModelType.STUB,
            model_dir=None,
            model_id="stub",
            estimated_load_time_ms=self.STUB_LOAD_TIME_MS,
        )

    def _discover_onnx_folders(self) -> DiscoveredModel | None:
        """Discover ONNX-only model folders (new format).

        Looks for folders containing:
        - embeddings_*.onnx
        - classifier_binary_*.onnx
        - classifier_family_*.onnx
        - classifier_subfamily_*.onnx
        - label_encoders.json

        Priority patterns:
        1. threat_classifier_*_deploy/ folders
        2. Folders with manifest.yaml
        3. Any folder with required ONNX files

        Returns:
            DiscoveredModel if ONNX folder found, None otherwise
        """
        if not self.models_dir.exists():
            logger.debug(f"Models directory not found: {self.models_dir}")
            return None

        # Pattern 1: Check for threat_classifier_*_deploy folders
        for folder in self.models_dir.glob("threat_classifier_*_deploy"):
            if self._validate_onnx_folder(folder):
                logger.info(f"Discovered ONNX folder: {folder.name}")
                return self._create_onnx_folder_model(folder)

        # Pattern 2: Check subdirectories with manifest.yaml
        for manifest_path in self.models_dir.rglob("manifest.yaml"):
            folder = manifest_path.parent
            if self._validate_onnx_folder(folder):
                logger.info(f"Discovered ONNX folder with manifest: {folder.name}")
                return self._create_onnx_folder_model(folder)

        # Pattern 3: Check any subdirectory with required files
        for folder in self.models_dir.iterdir():
            if folder.is_dir() and self._validate_onnx_folder(folder):
                logger.info(f"Discovered ONNX folder: {folder.name}")
                return self._create_onnx_folder_model(folder)

        logger.debug("No ONNX-only folders discovered")
        return None

    def _validate_onnx_folder(self, folder: Path) -> bool:
        """Validate folder contains required ONNX files.

        Args:
            folder: Directory to validate

        Returns:
            True if folder contains required ONNX model files
        """
        # Required files for a valid ONNX-only model
        required_patterns = [
            "embeddings*.onnx",  # Embeddings model
            "classifier_binary*.onnx",  # Binary classifier
            "label_encoders.json",  # Label mappings
        ]

        for pattern in required_patterns:
            if not list(folder.glob(pattern)):
                return False

        return True

    def _create_onnx_folder_model(self, folder: Path) -> DiscoveredModel:
        """Create DiscoveredModel from ONNX folder.

        Args:
            folder: Directory containing ONNX models

        Returns:
            DiscoveredModel configured for ONNX-only loading
        """
        import json

        # Try to load metadata if available
        metadata = {}
        metadata_path = folder / "model_metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path) as f:
                    metadata = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load metadata from {metadata_path}: {e}")

        # Extract model ID from folder name or metadata
        if "model_id" in metadata:
            model_id = metadata["model_id"]
        else:
            # Use folder name as model ID
            model_id = folder.name

        return DiscoveredModel(
            model_type=ModelType.ONNX_ONLY,
            model_dir=folder,
            model_id=model_id,
            estimated_load_time_ms=200,  # ONNX-only loads very fast
            metadata=metadata,
        )

    def list_available_models(self) -> list[DiscoveredModel]:
        """List all available models (for debugging/reporting).

        Returns:
            List of all discovered models

        Example:
            service = ModelDiscoveryService()
            models = service.list_available_models()

            for model in models:
                print(f"{model.model_id}: {model.model_type.value}")
                if model.model_dir:
                    print(f"  ONNX folder: {model.model_dir}")
        """
        models = []

        # Try ONNX folders
        try:
            onnx_model = self._discover_onnx_folders()
            if onnx_model:
                models.append(onnx_model)
        except Exception as e:
            logger.debug(f"ONNX folder discovery failed: {e}")

        return models

    def verify_model(self, model: DiscoveredModel) -> tuple[bool, list[str]]:
        """Verify model files are accessible and valid.

        Args:
            model: Model to verify

        Returns:
            Tuple of (is_valid, error_messages)

        Example:
            model = service.find_best_model()
            is_valid, errors = service.verify_model(model)

            if is_valid:
                print("Model is valid and ready to use")
            else:
                print(f"Model has errors: {errors}")
        """
        errors = []

        if model.is_stub:
            # Stub is always valid
            return True, []

        # Check ONNX folder
        if not model.model_dir:
            errors.append("No model directory specified")
            return False, errors

        if not model.model_dir.exists():
            errors.append(f"Model directory not found: {model.model_dir}")
            return False, errors

        # Validate folder has required ONNX files
        if not self._validate_onnx_folder(model.model_dir):
            errors.append(f"Model directory missing required ONNX files: {model.model_dir}")

        return len(errors) == 0, errors


def create_discovery_service(models_dir: Path | None = None) -> ModelDiscoveryService:
    """Factory function to create discovery service.

    Args:
        models_dir: Optional custom models directory

    Returns:
        ModelDiscoveryService instance

    Example:
        from raxe.infrastructure.models.discovery import create_discovery_service

        service = create_discovery_service()
        model = service.find_best_model()
    """
    return ModelDiscoveryService(models_dir=models_dir)
