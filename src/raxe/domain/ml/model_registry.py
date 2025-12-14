"""Model registry for managing multiple L2 models.

Provides auto-discovery, selection, and comparison of L2 models.
Supports multiple model types (ONNX INT8, PyTorch, etc.) with
zero code changes to add new models.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from raxe.domain.ml.model_metadata import ModelMetadata, ModelStatus

if TYPE_CHECKING:
    from raxe.domain.ml.protocol import L2Detector

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
        """Auto-discover all models using three-tier priority discovery.

        Discovery Priority:
        1. Manifest-based models (manifest.yaml in subdirectories) - HIGHEST
        2. .raxe files in models/ root directory - MEDIUM
        3. metadata/*.json files - LOWEST (legacy)

        This ensures manifest-based models take precedence while maintaining
        backward compatibility with existing .raxe and JSON-based models.
        """
        if not self.models_dir.exists():
            logger.warning(f"Models directory not found: {self.models_dir}")
            return

        discovery_stats = {
            "manifest": 0,
            "raxe_root": 0,
            "metadata_json": 0,
            "errors": 0
        }

        # PRIORITY 1: Discover manifest-based models from subdirectories
        manifest_models = self._discover_manifest_models()
        for model_id, metadata in manifest_models.items():
            self._models[model_id] = metadata
            discovery_stats["manifest"] += 1

        # PRIORITY 2: Discover from .raxe files in root (if not already loaded)
        raxe_files = list(self.models_dir.glob("*.raxe"))
        if raxe_files:
            logger.info(f"Discovered {len(raxe_files)} .raxe files in {self.models_dir}")

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

                # Skip if already loaded from manifest
                if model_id in self._models:
                    logger.debug(f"Skipping {model_id} (already loaded from manifest)")
                    continue

                # Try to load metadata JSON
                metadata_dir = self.models_dir / "metadata"
                metadata_file = metadata_dir / f"{model_id}.json"

                if metadata_file.exists():
                    # Load from JSON
                    with open(metadata_file) as f:
                        data = json.load(f)
                    metadata = ModelMetadata.from_dict(data, file_path=raxe_file)
                    logger.info(f"Loaded model: {model_id} ({metadata.name})")
                else:
                    # Create minimal metadata from filename
                    metadata = self._create_default_metadata(model_id, raxe_file)
                    logger.info(f"No metadata file for {model_id}, using defaults")

                self._models[model_id] = metadata
                discovery_stats["raxe_root"] += 1

            except Exception as e:
                logger.error(f"Failed to load model {raxe_file.name}: {e}")
                discovery_stats["errors"] += 1
                continue

        # PRIORITY 3: Discover from metadata files (for variants that share bundle files)
        metadata_dir = self.models_dir / "metadata"
        if metadata_dir.exists():
            metadata_files = list(metadata_dir.glob("*.json"))
            for metadata_file in metadata_files:
                try:
                    model_id = metadata_file.stem

                    # Skip if already loaded from manifest or .raxe file
                    if model_id in self._models:
                        continue

                    # Load metadata
                    with open(metadata_file) as f:
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
                    discovery_stats["metadata_json"] += 1

                except Exception as e:
                    logger.error(f"Failed to load model from metadata {metadata_file.name}: {e}")
                    discovery_stats["errors"] += 1
                    continue

        # Log discovery summary
        total = discovery_stats["manifest"] + discovery_stats["raxe_root"] + discovery_stats["metadata_json"]
        if total > 0:
            logger.info(
                f"Model discovery complete: {total} models loaded "
                f"(manifest={discovery_stats['manifest']}, "
                f"raxe={discovery_stats['raxe_root']}, "
                f"json={discovery_stats['metadata_json']}, "
                f"errors={discovery_stats['errors']})"
            )
        else:
            logger.warning(f"No models discovered in {self.models_dir}")

    def _create_default_metadata(
        self,
        model_id: str,
        file_path: Path
    ) -> ModelMetadata:
        """Create default metadata for model without JSON file."""
        from raxe.domain.ml.model_metadata import (
            FileInfo,
            ModelRuntime,
            ModelStatus,
            PerformanceMetrics,
            Requirements,
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

    def _discover_manifest_models(self) -> dict[str, ModelMetadata]:
        """Discover models from manifest.yaml files in subdirectories.

        Returns:
            Dictionary mapping model_id to ModelMetadata
        """
        models = {}

        # Find all subdirectories with manifest.yaml
        for item in self.models_dir.iterdir():
            if not item.is_dir():
                continue

            manifest_file = item / "manifest.yaml"
            if not manifest_file.exists():
                continue

            try:
                # Load manifest
                model = self._load_manifest_model(item, manifest_file)
                if model:
                    models[model.model_id] = model
                    logger.info(f"Loaded manifest model: {model.model_id} from {item.name}")

            except Exception as e:
                logger.error(f"Failed to load manifest model from {item.name}: {e}")
                continue

        return models

    def _load_manifest_model(
        self,
        folder: Path,
        manifest_file: Path
    ) -> ModelMetadata | None:
        """Load model from manifest file.

        Args:
            folder: Model folder path
            manifest_file: Path to manifest.yaml

        Returns:
            ModelMetadata or None if loading failed
        """
        from raxe.domain.ml.manifest_loader import ManifestLoader

        # Load manifest
        loader = ManifestLoader(strict=False)  # Non-strict for graceful degradation
        manifest_data = loader.load_manifest(manifest_file)

        # Extract model_id from folder name or manifest
        model_id = manifest_data.get("model_id") or folder.name

        # ADAPTATION: Support both bundle and ONNX manifest formats
        manifest_data = self._adapt_manifest_format(manifest_data)

        # Validate tokenizer if present
        if manifest_data.get("tokenizer"):
            is_valid, errors = self._validate_tokenizer(manifest_data)
            if not is_valid:
                logger.warning(
                    f"Tokenizer validation warnings for {model_id}:\n" +
                    "\n".join(f"  - {err}" for err in errors)
                )

        # Convert manifest to metadata
        return self._manifest_to_metadata(manifest_data, folder)

    def _adapt_manifest_format(self, manifest: dict) -> dict:
        """Adapt ONNX manifest format to bundle format for compatibility.

        Supports three manifest formats:
        1. Bundle format: model.bundle_file points to .raxe file
        2. Legacy ONNX format: file_info.filename points to .onnx file
        3. ONNX-only format: onnx_files section with separate ONNX models

        Args:
            manifest: Original manifest data

        Returns:
            Adapted manifest in bundle-compatible format
        """
        # If already in bundle format, return as-is
        if "model" in manifest and "bundle_file" in manifest.get("model", {}):
            return manifest

        # NEW: Handle ONNX-only format (manifest v2.0)
        if manifest.get("model_type") == "onnx_only" or "onnx_files" in manifest:
            adapted = manifest.copy()
            adapted["is_onnx_only"] = True  # Flag for detector creation

            # Extract model runtime info
            runtime = "onnx"
            if manifest.get("metadata", {}).get("quantization") == "int8":
                runtime = "onnx_int8"
            elif manifest.get("metadata", {}).get("quantization") == "fp16":
                runtime = "onnx_fp16"

            # Create model section for compatibility
            adapted["model"] = {
                "runtime": runtime,
                "model_type": "onnx_only",
                # No bundle_file for ONNX-only models
            }

            # Keep onnx_files section
            if "onnx_files" in manifest:
                adapted["model"]["onnx_files"] = manifest["onnx_files"]

            return adapted

        # If in legacy ONNX format, adapt it
        if "file_info" in manifest:
            adapted = manifest.copy()

            # Move metadata.status to root level
            if "metadata" in manifest and "status" in manifest["metadata"]:
                adapted["status"] = manifest["metadata"]["status"]

            # Create model section from file_info
            file_info = manifest["file_info"]
            filename = file_info.get("filename", "")

            # Determine runtime from filename
            runtime = "onnx"
            if "int8" in filename.lower():
                runtime = "onnx_int8"
            elif "fp16" in filename.lower():
                runtime = "onnx_fp16"

            adapted["model"] = {
                "bundle_file": filename,
                "runtime": runtime,
                # Store original ONNX file reference
                "onnx_embeddings": filename,
            }

            # Add embedding model if in metadata
            if "metadata" in manifest:
                base_model = manifest["metadata"].get("base_model")
                if base_model:
                    adapted["model"]["embedding_model"] = base_model

            # Adapt tokenizer structure
            if "tokenizer" in manifest:
                tok = manifest["tokenizer"]
                tokenizer_class = tok.get("tokenizer_class", "AutoTokenizer")
                adapted["tokenizer"] = {
                    "name": tok.get("tokenizer_name", tok.get("hf_model_id", "")),
                    "type": tokenizer_class,
                    "config": {
                        "type": tokenizer_class,  # Add type to config as well
                        "max_length": tok.get("max_length", 512),
                        "model_max_length": tok.get("model_max_length", 512),
                        "do_lower_case": tok.get("do_lower_case", False),
                        "padding_side": tok.get("padding_side", "right"),
                        "truncation_side": tok.get("truncation_side", "right"),
                    }
                }

            return adapted

        # Unknown format, return as-is
        return manifest

    def _validate_tokenizer(self, manifest: dict) -> tuple[bool, list[str]]:
        """Validate tokenizer configuration in manifest.

        Args:
            manifest: Manifest data dictionary

        Returns:
            Tuple of (is_valid, error_messages)
        """
        from raxe.domain.ml.tokenizer_registry import get_tokenizer_registry

        errors = []

        tokenizer_data = manifest.get("tokenizer")
        if not tokenizer_data:
            return True, []  # No tokenizer, nothing to validate

        # Check required fields
        tokenizer_name = tokenizer_data.get("name")
        if not tokenizer_name:
            errors.append("Tokenizer name is required")

        # Check compatibility with embedding model
        model_data = manifest.get("model", {})
        embedding_model = model_data.get("embedding_model")

        if tokenizer_name and embedding_model:
            registry = get_tokenizer_registry()
            is_compat = registry.is_compatible(tokenizer_name, embedding_model)
            if not is_compat:
                errors.append(
                    f"Tokenizer '{tokenizer_name}' may not be compatible "
                    f"with embedding model '{embedding_model}'"
                )

            # Validate full tokenizer config
            tokenizer_config = tokenizer_data.get("config", {})
            _is_valid, validation_errors = registry.validate_tokenizer(
                tokenizer_name,
                tokenizer_config,
                embedding_model
            )
            errors.extend(validation_errors)

        return len(errors) == 0, errors

    def _manifest_to_metadata(
        self,
        manifest: dict,
        folder: Path
    ) -> ModelMetadata:
        """Convert manifest data to ModelMetadata.

        Args:
            manifest: Manifest data dictionary
            folder: Model folder path

        Returns:
            ModelMetadata instance
        """
        from raxe.domain.ml.model_metadata import (
            AccuracyMetrics,
            FileInfo,
            ModelRuntime,
            ModelStatus,
            PerformanceMetrics,
            Requirements,
        )

        # Extract basic fields
        model_id = manifest.get("model_id") or folder.name
        name = manifest.get("name", f"RAXE L2 {model_id}")
        version = manifest.get("version", "0.0.1")
        variant = manifest.get("variant", model_id)
        description = manifest.get("description", "")
        status = ModelStatus(manifest.get("status", "experimental"))

        # Extract model section
        model_data = manifest.get("model", {})
        is_onnx_only = manifest.get("is_onnx_only", False) or model_data.get("model_type") == "onnx_only"

        # Handle different model types
        if is_onnx_only:
            # ONNX-only: no bundle file, use folder size
            bundle_filename = ""
            bundle_path = None

            # Calculate total size of ONNX files
            size_mb = 0.0
            for onnx_file in folder.glob("*.onnx"):
                size_mb += onnx_file.stat().st_size / (1024 * 1024)
        else:
            # Bundle-based model
            bundle_filename = model_data.get("bundle_file", "")
            bundle_path = folder / bundle_filename if bundle_filename else None

            # Get bundle size if exists
            size_mb = 0.0
            if bundle_path and bundle_path.exists():
                size_mb = bundle_path.stat().st_size / (1024 * 1024)

        # Extract file info
        file_info = FileInfo(
            filename=bundle_filename if bundle_filename else folder.name,  # Use folder name for ONNX-only
            size_mb=size_mb,
            onnx_embeddings=model_data.get("onnx_embeddings"),
        )

        # Extract performance
        perf_data = manifest.get("performance", {})
        performance = PerformanceMetrics(
            target_latency_ms=perf_data.get("target_latency_ms", 50.0),
            p50_latency_ms=perf_data.get("p50_latency_ms"),
            p95_latency_ms=perf_data.get("p95_latency_ms"),
            p99_latency_ms=perf_data.get("p99_latency_ms"),
            memory_mb=perf_data.get("memory_mb"),
        )

        # Extract accuracy
        acc_data = manifest.get("accuracy", {})
        accuracy = None
        if acc_data:
            accuracy = AccuracyMetrics(
                binary_f1=acc_data.get("binary_f1"),
                family_f1=acc_data.get("family_f1"),
                subfamily_f1=acc_data.get("subfamily_f1"),
                false_positive_rate=acc_data.get("false_positive_rate"),
                false_negative_rate=acc_data.get("false_negative_rate"),
            )

        # Determine runtime from model data
        runtime_str = model_data.get("runtime", "onnx")
        try:
            runtime = ModelRuntime(runtime_str)
        except ValueError:
            runtime = ModelRuntime.ONNX  # Default fallback

        requirements = Requirements(runtime=runtime)

        # Extract tokenizer fields
        tokenizer_data = manifest.get("tokenizer")
        tokenizer_name = None
        tokenizer_config = None
        if tokenizer_data:
            tokenizer_name = tokenizer_data.get("name")
            tokenizer_config = tokenizer_data.get("config")

        embedding_model_name = model_data.get("embedding_model")

        # Extract tags
        tags = manifest.get("tags", [])

        # Determine file_path based on model type
        if is_onnx_only:
            # For ONNX-only models, file_path is the folder
            file_path_to_use = folder
        else:
            # For bundle models, file_path is the bundle file
            file_path_to_use = bundle_path

        return ModelMetadata(
            model_id=model_id,
            name=name,
            version=version,
            variant=variant,
            description=description,
            file_info=file_info,
            performance=performance,
            requirements=requirements,
            status=status,
            accuracy=accuracy,
            tags=tags,
            tokenizer_name=tokenizer_name,
            tokenizer_config=tokenizer_config,
            embedding_model_name=embedding_model_name,
            file_path=file_path_to_use,  # Folder for ONNX-only, file for bundles
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
        criteria: str | None = None,
        voting_preset: str | None = None,
    ) -> L2Detector:
        """Create detector from model.

        Args:
            model_id: Specific model to use, or None to auto-select
            criteria: Auto-selection criteria if model_id not specified
            voting_preset: Voting preset override (balanced, high_security, low_fp)

        Returns:
            L2Detector instance

        Raises:
            ValueError: If model not found
        """
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

        # Extract tokenizer config if present
        tokenizer_config = None
        if model.tokenizer_config:
            tokenizer_config = model.tokenizer_config.copy()
            # Add tokenizer name for ONNX embedder
            if model.tokenizer_name:
                tokenizer_config["tokenizer_name"] = model.tokenizer_name

        # Check if this is a folder-based model (ONNX-only)
        if model_file.is_dir():
            # This is a folder-based Gemma model
            from raxe.domain.ml.gemma_detector import create_gemma_detector
            from raxe.domain.ml.l2_config import get_l2_config

            l2_config = get_l2_config()
            logger.info(f"Creating Gemma detector from folder: {model_id} ({model_file.name})")
            return create_gemma_detector(
                model_dir=str(model_file),
                confidence_threshold=l2_config.thresholds.threat_threshold,
                voting_preset=voting_preset,
            )
        else:
            # File-based models not supported (only folder-based ONNX models)
            raise ValueError(
                f"Model {model_id} points to a file ({model_file.name}), not a folder. "
                f"Only folder-based Gemma ONNX models are supported."
            )

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
