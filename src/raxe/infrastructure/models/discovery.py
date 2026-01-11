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
    metadata: dict[str, str | int | float] | None = None

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
            models_dir: Optional custom models directory.
                       If not specified, searches:
                       1. ~/.raxe/models/ (user directory - downloaded models)
                       2. Package models directory (bundled models, dev only)

        Environment Variables:
            RAXE_SKIP_BUNDLED_MODELS: If set, skip package models directory.
                Useful for testing fresh install UX in dev environments.
        """
        from raxe.infrastructure.ml.model_downloader import (
            get_models_directory,
            get_package_models_directory,
            should_use_bundled_models,
        )

        # Build search paths
        self._search_paths: list[Path] = []

        if models_dir is not None:
            # Use explicit models directory
            self._search_paths.append(models_dir)
        else:
            # Search user directory first (downloaded models)
            user_models_dir = get_models_directory()
            if user_models_dir.exists():
                self._search_paths.append(user_models_dir)

            # Then search package directory (bundled models, dev only)
            # Skip if RAXE_SKIP_BUNDLED_MODELS is set (for testing fresh install UX)
            if should_use_bundled_models():
                package_models_dir = get_package_models_directory()
                if package_models_dir.exists():
                    self._search_paths.append(package_models_dir)

        # For backwards compatibility, set models_dir to first path
        default_models_dir = Path.home() / ".raxe" / "models"
        self.models_dir = self._search_paths[0] if self._search_paths else default_models_dir
        logger.info(f"Model discovery service initialized (search_paths: {self._search_paths})")

    def find_best_model(
        self,
        criteria: Literal["latency", "accuracy", "balanced"] = "latency",
        auto_download: bool = True,
    ) -> DiscoveredModel:
        """Find best available model based on criteria.

        This implements folder-based ONNX discovery:
        1. Try to find ONNX-only folders
        2. If not found and auto_download=True, download the model
        3. Fall back to stub detector if download fails/disabled

        Args:
            criteria: Selection criteria (default: "latency")
            auto_download: Automatically download model if not found (default: True)

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

        # Step 1: Check for DEFAULT_MODEL (without fallback to older models)
        try:
            default_model = self._discover_onnx_folders(allow_fallback=False)
            if default_model:
                discovery_time_ms = (time.perf_counter() - start_time) * 1000
                logger.info(
                    "model_discovery_success",
                    model_type="onnx_only",
                    model_id=default_model.model_id,
                    model_dir=str(default_model.model_dir),
                    estimated_load_ms=default_model.estimated_load_time_ms,
                    discovery_time_ms=discovery_time_ms,
                )
                return default_model
        except Exception as e:
            logger.warning(f"ONNX folder discovery failed: {e}", exc_info=True)

        # Step 2: DEFAULT_MODEL not found - try auto-download
        if auto_download:
            logger.info("default_model_not_found_attempting_download")
            downloaded_model = self._auto_download_model()
            if downloaded_model:
                discovery_time_ms = (time.perf_counter() - start_time) * 1000
                logger.info(
                    "model_auto_download_success",
                    model_type="onnx_only",
                    model_id=downloaded_model.model_id,
                    model_dir=str(downloaded_model.model_dir),
                    discovery_time_ms=discovery_time_ms,
                )
                return downloaded_model

        # Step 3: Download failed - try any available model as fallback
        try:
            fallback_model = self._discover_onnx_folders(allow_fallback=True)
            if fallback_model:
                discovery_time_ms = (time.perf_counter() - start_time) * 1000
                logger.warning(
                    "model_discovery_fallback",
                    model_type="onnx_only",
                    model_id=fallback_model.model_id,
                    model_dir=str(fallback_model.model_dir),
                    discovery_time_ms=discovery_time_ms,
                    help="Using fallback model instead of DEFAULT_MODEL.",
                )
                return fallback_model
        except Exception as e:
            logger.warning(f"Fallback discovery failed: {e}", exc_info=True)

        # Step 4: No models at all - use stub
        discovery_time_ms = (time.perf_counter() - start_time) * 1000
        logger.warning(
            "model_discovery_fallback_to_stub",
            models_dir=str(self.models_dir),
            discovery_time_ms=discovery_time_ms,
            help="No L2 models found and auto-download failed.",
        )

        return DiscoveredModel(
            model_type=ModelType.STUB,
            model_dir=None,
            model_id="stub",
            estimated_load_time_ms=self.STUB_LOAD_TIME_MS,
        )

    def _auto_download_model(self) -> DiscoveredModel | None:
        """Automatically download the current ML model.

        Downloads on first use with proper progress feedback.
        Uses the unified download progress system for consistent UX
        across CLI, SDK, and CI/CD environments.

        Returns:
            DiscoveredModel if download successful, None otherwise
        """
        try:
            from raxe.infrastructure.ml.download_progress import (
                create_download_progress,
            )
            from raxe.infrastructure.ml.model_downloader import (
                CURRENT_MODEL,
                download_model,
                is_model_installed,
            )

            # Check if already installed (race condition check)
            if is_model_installed(CURRENT_MODEL.id):
                # Model appeared (maybe another process downloaded)
                user_models = Path.home() / ".raxe" / "models"
                model_dir = user_models / CURRENT_MODEL.folder_name
                return self._create_onnx_folder_model(model_dir)

            # Get model metadata for progress display (single source of truth)
            expected_size = CURRENT_MODEL.size_mb * 1024 * 1024  # Convert to bytes

            # Create progress indicator based on environment
            # - Interactive terminal: Rich progress bar with speed/ETA
            # - CI/CD: Timestamped log lines
            # - Quiet mode: Silent (errors only)
            progress = create_download_progress()

            # Start progress display
            progress.start(CURRENT_MODEL.name, expected_size)

            try:
                # Download with unified progress system
                model_path = download_model(
                    CURRENT_MODEL.id,
                    progress_callback=progress.get_callback(),
                )

                # Mark complete
                progress.complete()

                # Return discovered model
                return self._create_onnx_folder_model(model_path)

            except Exception as e:
                # Show error via progress indicator
                progress.error(str(e))
                raise

        except Exception as e:
            logger.warning(f"Auto-download failed: {e}", exc_info=True)
            # Non-fatal - will fall back to stub
            return None

    def _discover_onnx_folders(self, allow_fallback: bool = False) -> DiscoveredModel | None:
        """Discover ONNX-only model folders (new format).

        Discovery priority:
        1. Check for CURRENT_MODEL folder in ALL directories
        2. If not found and allow_fallback=True, check for any valid model

        This ensures CURRENT_MODEL is always downloaded if not present,
        rather than silently using older bundled models.

        Args:
            allow_fallback: If True, fall back to any valid model when
                          CURRENT_MODEL is not found. Used after download fails.

        Returns:
            DiscoveredModel if found, None otherwise (triggers auto-download)
        """
        from raxe.infrastructure.ml.model_downloader import CURRENT_MODEL

        # Priority 1: Check for CURRENT_MODEL folder in ALL directories
        for search_path in self._search_paths:
            if not search_path.exists():
                continue
            current_folder = search_path / CURRENT_MODEL.folder_name
            if current_folder.exists() and self._validate_onnx_folder(current_folder):
                logger.info(f"Discovered CURRENT_MODEL: {current_folder.name} in {search_path}")
                return self._create_onnx_folder_model(current_folder)

        # Priority 2: Fall back to any valid model ONLY if allowed
        # This is used after auto-download fails to use any available model
        if allow_fallback:
            for search_path in self._search_paths:
                model = self._search_directory_for_onnx(search_path)
                if model:
                    logger.warning(f"CURRENT_MODEL not found, falling back to: {model.model_id}")
                    return model

        logger.debug("CURRENT_MODEL not found, will trigger auto-download")
        return None

    def _search_directory_for_onnx(self, directory: Path) -> DiscoveredModel | None:
        """Search a single directory for ONNX model folders.

        Prioritizes CURRENT_MODEL folder to ensure users get the latest
        recommended model, even if older models exist.

        Args:
            directory: Directory to search

        Returns:
            DiscoveredModel if found, None otherwise
        """
        from raxe.infrastructure.ml.model_downloader import CURRENT_MODEL

        if not directory.exists():
            logger.debug(f"Models directory not found: {directory}")
            return None

        # Priority: Check for CURRENT_MODEL folder first
        # This ensures users get the latest recommended model
        current_folder = directory / CURRENT_MODEL.folder_name
        if current_folder.exists() and self._validate_onnx_folder(current_folder):
            logger.info(f"Discovered CURRENT_MODEL: {current_folder.name} in {directory}")
            return self._create_onnx_folder_model(current_folder)

        # Fallback: Check for any threat_classifier_*_deploy folders
        for folder in directory.glob("threat_classifier_*_deploy"):
            if self._validate_onnx_folder(folder):
                logger.info(f"Discovered ONNX folder: {folder.name} in {directory}")
                return self._create_onnx_folder_model(folder)

        # Pattern 2: Check subdirectories with manifest.yaml
        for manifest_path in directory.rglob("manifest.yaml"):
            folder = manifest_path.parent
            if self._validate_onnx_folder(folder):
                logger.info(f"Discovered ONNX folder with manifest: {folder.name} in {directory}")
                return self._create_onnx_folder_model(folder)

        # Pattern 3: Check any subdirectory with required files
        for folder in directory.iterdir():
            if folder.is_dir() and self._validate_onnx_folder(folder):
                logger.info(f"Discovered ONNX folder: {folder.name} in {directory}")
                return self._create_onnx_folder_model(folder)

        return None

    def _validate_onnx_folder(self, folder: Path) -> bool:
        """Validate folder contains required Gemma 5-head ONNX model files.

        Args:
            folder: Directory to validate

        Returns:
            True if folder contains required Gemma ONNX model files
        """
        # Required files for Gemma 5-head model
        gemma_required = [
            "model*.onnx",  # EmbeddingGemma model
            "classifier_is_threat*.onnx",  # Binary classifier
            "classifier_threat_family*.onnx",  # Family classifier
        ]
        return all(list(folder.glob(pattern)) for pattern in gemma_required)

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
