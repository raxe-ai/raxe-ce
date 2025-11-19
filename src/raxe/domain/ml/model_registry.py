"""Model registry for managing multiple L2 models.

Provides auto-discovery, selection, and comparison of L2 models.
Supports multiple model types (ONNX INT8, PyTorch, etc.) with
zero code changes to add new models.
"""
import json
import logging
from pathlib import Path
from typing import Literal

from raxe.domain.ml.model_metadata import ModelMetadata, ModelStatus

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Registry for L2 models with auto-discovery.

    Automatically discovers all .raxe model files in the models directory
    and loads their metadata from JSON files.

    Example:
        registry = ModelRegistry()

        # List all models
        models = registry.list_models()

        # Get specific model
        model = registry.get_model("v1.0_onnx_int8")

        # Get best model for criteria
        fastest = registry.get_best_model("latency")

        # Create detector
        detector = registry.create_detector("v1.0_onnx_int8")
    """

    def __init__(self, models_dir: Path | None = None):
        """Initialize registry.

        Args:
            models_dir: Optional custom models directory
                       (default: src/raxe/domain/ml/models)
        """
        if models_dir is None:
            # Default to package models directory
            models_dir = Path(__file__).parent / "models"

        self.models_dir = models_dir
        self._models: dict[str, ModelMetadata] = {}
        self._discover_models()

    def _discover_models(self) -> None:
        """Auto-discover all .raxe model files and load metadata."""
        if not self.models_dir.exists():
            logger.warning(f"Models directory not found: {self.models_dir}")
            return

        metadata_dir = self.models_dir / "metadata"

        # Strategy 1: Discover from .raxe files
        raxe_files = list(self.models_dir.glob("*.raxe"))
        if raxe_files:
            logger.info(f"Discovered {len(raxe_files)} model files in {self.models_dir}")

        for raxe_file in raxe_files:
            try:
                # Extract model_id from filename
                # Format: raxe_model_l2_{version}_{variant}.raxe
                # Example: raxe_model_l2_v1.0_onnx_int8.raxe -> v1.0_onnx_int8
                filename = raxe_file.stem  # Without .raxe extension
                if filename.startswith("raxe_model_l2_"):
                    model_id = filename.replace("raxe_model_l2_", "")
                else:
                    # Fallback: use full filename as ID
                    model_id = filename

                # Try to load metadata JSON
                metadata_file = metadata_dir / f"{model_id}.json"

                if metadata_file.exists():
                    # Load from JSON
                    with open(metadata_file, "r") as f:
                        data = json.load(f)
                    metadata = ModelMetadata.from_dict(data, file_path=raxe_file)
                    logger.info(f"Loaded model: {model_id} ({metadata.name})")
                else:
                    # Create minimal metadata from filename
                    metadata = self._create_default_metadata(model_id, raxe_file)
                    logger.info(f"No metadata file for {model_id}, using defaults")

                self._models[model_id] = metadata

            except Exception as e:
                logger.error(f"Failed to load model {raxe_file.name}: {e}")
                continue

        # Strategy 2: Discover from metadata files (for variants that share bundle files)
        if metadata_dir.exists():
            metadata_files = list(metadata_dir.glob("*.json"))
            for metadata_file in metadata_files:
                try:
                    model_id = metadata_file.stem

                    # Skip if already loaded from .raxe file
                    if model_id in self._models:
                        continue

                    # Load metadata
                    with open(metadata_file, "r") as f:
                        data = json.load(f)

                    # Resolve bundle file path
                    bundle_filename = data["file_info"]["filename"]
                    bundle_path = self.models_dir / bundle_filename

                    if not bundle_path.exists():
                        logger.warning(f"Bundle file not found for {model_id}: {bundle_path}")
                        continue

                    # Load model with correct bundle path
                    metadata = ModelMetadata.from_dict(data, file_path=bundle_path)
                    logger.info(f"Loaded model from metadata: {model_id} ({metadata.name})")
                    self._models[model_id] = metadata

                except Exception as e:
                    logger.error(f"Failed to load model from metadata {metadata_file.name}: {e}")
                    continue

        if not self._models:
            logger.warning(f"No models discovered in {self.models_dir}")

    def _create_default_metadata(
        self,
        model_id: str,
        file_path: Path
    ) -> ModelMetadata:
        """Create default metadata for model without JSON file."""
        from raxe.domain.ml.model_metadata import (
            FileInfo,
            PerformanceMetrics,
            Requirements,
            ModelRuntime,
            ModelStatus,
        )

        # Guess runtime from model_id
        if "onnx_int8" in model_id:
            runtime = ModelRuntime.ONNX_INT8
        elif "onnx" in model_id:
            runtime = ModelRuntime.ONNX
        elif "pytorch" in model_id:
            runtime = ModelRuntime.PYTORCH
        else:
            runtime = ModelRuntime.CUSTOM

        # Get file size
        size_mb = file_path.stat().st_size / (1024 * 1024) if file_path.exists() else 0

        return ModelMetadata(
            model_id=model_id,
            name=f"RAXE L2 {model_id}",
            version="unknown",
            variant=model_id,
            description=f"L2 model {model_id} (auto-discovered, no metadata file)",
            file_info=FileInfo(
                filename=file_path.name,
                size_mb=size_mb,
            ),
            performance=PerformanceMetrics(
                target_latency_ms=50.0,  # Conservative default
            ),
            requirements=Requirements(runtime=runtime),
            status=ModelStatus.EXPERIMENTAL,  # Mark as experimental without metadata
            file_path=file_path,
        )

    def list_models(
        self,
        status: ModelStatus | None = None,
        runtime: str | None = None
    ) -> list[ModelMetadata]:
        """List all discovered models.

        Args:
            status: Optional filter by status (active, experimental, deprecated)
            runtime: Optional filter by runtime type

        Returns:
            List of model metadata, sorted by model_id
        """
        models = list(self._models.values())

        # Filter by status
        if status:
            models = [m for m in models if m.status == status]

        # Filter by runtime
        if runtime:
            models = [m for m in models if m.runtime_type == runtime]

        # Sort by model_id
        models.sort(key=lambda m: m.model_id)

        return models

    def get_model(self, model_id: str) -> ModelMetadata | None:
        """Get specific model by ID.

        Args:
            model_id: Model identifier (e.g., "v1.0_onnx_int8")

        Returns:
            Model metadata or None if not found
        """
        return self._models.get(model_id)

    def has_model(self, model_id: str) -> bool:
        """Check if model exists.

        Args:
            model_id: Model identifier

        Returns:
            True if model exists
        """
        return model_id in self._models

    def get_best_model(
        self,
        criteria: Literal["latency", "accuracy", "balanced", "memory"] = "balanced"
    ) -> ModelMetadata | None:
        """Get best model based on criteria.

        Args:
            criteria: Selection criteria:
                - "latency": Fastest model
                - "accuracy": Most accurate model
                - "balanced": Best balance of speed and accuracy
                - "memory": Smallest memory footprint

        Returns:
            Best model or None if no models available
        """
        # Only consider active models
        active_models = self.list_models(status=ModelStatus.ACTIVE)

        if not active_models:
            # Fall back to any model
            active_models = self.list_models()

        if not active_models:
            return None

        # Score each model and pick best
        best_model = None
        best_score = -1

        for model in active_models:
            score = model.score_for_criteria(criteria)
            if score > best_score:
                best_score = score
                best_model = model

        return best_model

    def create_detector(
        self,
        model_id: str | None = None,
        criteria: str | None = None
    ) -> "L2Detector":
        """Create detector from model.

        Args:
            model_id: Specific model to use, or None to auto-select
            criteria: Auto-selection criteria if model_id not specified

        Returns:
            L2Detector instance

        Raises:
            ValueError: If model not found
        """
        from raxe.domain.ml.bundle_detector import create_bundle_detector

        # Auto-select if no model_id specified
        if model_id is None:
            criteria = criteria or "balanced"
            model = self.get_best_model(criteria)  # type: ignore
            if not model:
                raise ValueError("No models available")
            model_id = model.model_id
            logger.info(f"Auto-selected model '{model_id}' (criteria: {criteria})")

        # Get model metadata
        model = self.get_model(model_id)
        if not model:
            raise ValueError(f"Model not found: {model_id}")

        # Get model file path
        if model.file_path:
            model_file = model.file_path
        else:
            # Fallback: look in models directory
            model_file = self.models_dir / model.file_info.filename

        if not model_file.exists():
            raise ValueError(f"Model file not found: {model_file}")

        # Get ONNX embeddings path if specified
        onnx_path = None
        if model.file_info.onnx_embeddings:
            onnx_path = self.models_dir / model.file_info.onnx_embeddings
            if not onnx_path.exists():
                logger.warning(f"ONNX embeddings not found: {onnx_path}, falling back to sentence-transformers")
                onnx_path = None

        # Create detector using bundle detector factory
        logger.info(f"Creating detector from model: {model_id} ({model_file.name})")
        if onnx_path:
            logger.info(f"Using ONNX embeddings: {onnx_path.name}")
        return create_bundle_detector(model_path=str(model_file), onnx_path=onnx_path)

    def compare_models(
        self,
        model_ids: list[str] | None = None
    ) -> dict[str, ModelMetadata]:
        """Compare multiple models.

        Args:
            model_ids: List of model IDs to compare, or None for all active models

        Returns:
            Dictionary mapping model_id to metadata
        """
        if model_ids:
            # Compare specific models
            models = {}
            for model_id in model_ids:
                model = self.get_model(model_id)
                if model:
                    models[model_id] = model
                else:
                    logger.warning(f"Model not found: {model_id}")
        else:
            # Compare all active models
            active_models = self.list_models(status=ModelStatus.ACTIVE)
            models = {m.model_id: m for m in active_models}

        return models

    def get_model_count(self) -> int:
        """Get total number of discovered models."""
        return len(self._models)

    def get_active_model_count(self) -> int:
        """Get number of active (production-ready) models."""
        return len(self.list_models(status=ModelStatus.ACTIVE))


# Global registry instance (lazy initialized)
_registry: ModelRegistry | None = None


def get_registry() -> ModelRegistry:
    """Get global model registry instance.

    Returns:
        Singleton ModelRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
