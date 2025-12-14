"""Eager loading L2 ML detector.

This detector implements eager initialization strategy to avoid timeout issues:
- Loads model during __init__() (not lazy)
- Uses ONNX embeddings when available (10x faster: 500ms vs 5s)
- Provides detailed initialization statistics
- Falls back gracefully to bundle or stub

Key Differences from LazyL2Detector:
- LazyL2Detector: Loads on first analyze() call (can cause timeout)
- EagerL2Detector: Loads during initialization (predictable timing)

Performance:
- ONNX INT8: ~500ms initialization, ~10ms inference
- Bundle (sentence-transformers): ~5s initialization, ~50ms inference
- Stub: ~1ms initialization, ~1ms inference (no real detection)

Example:
    # Eager loading - model loads immediately
    detector = EagerL2Detector(use_production=True)
    print(f"Loaded in {detector.initialization_stats['load_time_ms']}ms")

    # Fast inference (model already loaded)
    result = detector.analyze(text, l1_results)
"""

from __future__ import annotations

import time
from typing import Any

from raxe.domain.engine.executor import ScanResult
from raxe.domain.ml.protocol import L2Detector, L2Result
from raxe.infrastructure.config.scan_config import ScanConfig
from raxe.infrastructure.models.discovery import (
    DiscoveredModel,
    ModelDiscoveryService,
    ModelType,
)
from raxe.utils.logging import get_logger

logger = get_logger(__name__)


class EagerL2Detector:
    """Eager loading L2 ML detector.

    Implements L2Detector protocol with eager initialization:
    - Model loads during __init__() (not lazy)
    - ONNX-first strategy for fast loading
    - Comprehensive initialization statistics
    - Graceful fallback to stub if needed

    Performance Characteristics:
    - ONNX INT8 initialization: ~500ms
    - Bundle initialization: ~5000ms
    - Stub initialization: ~1ms
    - ONNX INT8 inference: ~10ms
    - Bundle inference: ~50ms
    """

    # Class-level flag to show warning only once per process
    _stub_warning_shown = False

    def __init__(
        self,
        *,
        config: ScanConfig | None = None,
        use_production: bool = True,
        confidence_threshold: float = 0.5,
        models_dir: str | None = None,
        voting_preset: str | None = None,
    ):
        """Initialize eager L2 detector.

        Model loading happens during __init__() (not lazy).

        Args:
            config: Scan configuration (optional)
            use_production: Whether to use production L2 model
            confidence_threshold: Minimum confidence for L2 detections
            models_dir: Optional custom models directory
            voting_preset: Voting preset override (balanced, high_security, low_fp)

        Example:
            # Eager initialization
            start = time.time()
            detector = EagerL2Detector(use_production=True)
            print(f"Loaded in {(time.time() - start) * 1000}ms")

            # Check what was loaded
            stats = detector.initialization_stats
            print(f"Model type: {stats['model_type']}")
            print(f"Has ONNX: {stats['has_onnx']}")
        """
        self.config = config
        self.use_production = use_production
        self.confidence_threshold = confidence_threshold
        self.voting_preset = voting_preset
        self._detector: L2Detector | None = None
        self._init_stats: dict[str, Any] = {}

        logger.info(
            "eager_l2_detector_initializing",
            use_production=use_production,
            confidence_threshold=confidence_threshold,
        )

        # Eager initialization - load model NOW
        init_start = time.perf_counter()
        self._initialize_detector(models_dir)
        init_time_ms = (time.perf_counter() - init_start) * 1000

        # Store initialization statistics
        self._init_stats["load_time_ms"] = init_time_ms
        self._init_stats["timestamp"] = time.time()

        logger.info(
            "eager_l2_detector_initialized",
            load_time_ms=init_time_ms,
            model_type=self._init_stats.get("model_type", "unknown"),
            is_stub=self._init_stats.get("is_stub", False),
        )

    def _initialize_detector(self, models_dir: str | None = None) -> None:
        """Initialize the L2 detector eagerly.

        This is called during __init__() to load the model immediately.

        Args:
            models_dir: Optional custom models directory
        """
        if not self.use_production:
            # Use stub detector
            from raxe.domain.ml.stub_detector import StubL2Detector
            self._detector = StubL2Detector()
            self._init_stats.update({
                "model_type": "stub",
                "is_stub": True,
                "reason": "use_production_disabled",
            })
            logger.info("Using stub detector (use_production=False)")
            return

        # Check if config specifies a model_id
        from pathlib import Path

        import yaml

        configured_model_id = None
        try:
            # Load config YAML file directly to check for explicit model selection
            # (RaxeConfig dataclass doesn't include l2_model field yet)
            config_file = Path.home() / ".raxe" / "config.yaml"
            if config_file.exists():
                with open(config_file) as f:
                    config_data = yaml.safe_load(f) or {}

                l2_model_config = config_data.get("l2_model", {})
                if l2_model_config.get("selection") == "explicit":
                    configured_model_id = l2_model_config.get("model_id")
                    logger.info(
                        "explicit_model_id_configured",
                        model_id=configured_model_id,
                        source="config.yaml"
                    )
        except Exception as e:
            logger.debug(f"Failed to load config for model_id: {e}")

        # Use Model Registry if explicit model_id is configured
        if configured_model_id:
            from raxe.domain.ml.model_registry import get_registry

            registry = get_registry()

            # Check if the configured model exists
            if registry.has_model(configured_model_id):
                try:
                    logger.info(
                        "using_explicit_model_from_config",
                        model_id=configured_model_id
                    )

                    # Create detector from registry using explicit model_id
                    discovery_start = time.perf_counter()
                    self._detector = registry.create_detector(
                        model_id=configured_model_id,
                        voting_preset=self.voting_preset,
                    )
                    discovery_time_ms = (time.perf_counter() - discovery_start) * 1000

                    # Get model metadata
                    model_metadata = registry.get_model(configured_model_id)

                    # Store initialization statistics
                    self._init_stats.update({
                        "discovery_time_ms": discovery_time_ms,
                        "model_id": configured_model_id,
                        "model_type": model_metadata.runtime_type if model_metadata else "unknown",
                        "is_stub": False,
                        "estimated_load_ms": model_metadata.performance.p95_latency_ms if model_metadata else 0,
                        "selection_method": "explicit_config",
                    })

                    logger.info(
                        "explicit_model_loaded_successfully",
                        model_id=configured_model_id,
                        discovery_time_ms=discovery_time_ms,
                    )
                    return

                except Exception as e:
                    logger.warning(
                        "explicit_model_load_failed",
                        model_id=configured_model_id,
                        error=str(e),
                        fallback="auto_discovery"
                    )
                    # Continue to auto-discovery fallback
            else:
                logger.warning(
                    "configured_model_not_found",
                    model_id=configured_model_id,
                    available_models=[m.model_id for m in registry.list_models()],
                    fallback="auto_discovery"
                )
                # Continue to auto-discovery fallback

        # Fallback: Auto-discover best available model (original behavior)
        discovery_service = ModelDiscoveryService(
            models_dir=Path(models_dir) if models_dir else None
        )

        # Find best model (ONNX-first strategy)
        discovery_start = time.perf_counter()
        discovered = discovery_service.find_best_model(criteria="latency")
        discovery_time_ms = (time.perf_counter() - discovery_start) * 1000

        self._init_stats["discovery_time_ms"] = discovery_time_ms
        self._init_stats["model_id"] = discovered.model_id
        self._init_stats["model_type"] = discovered.model_type.value
        self._init_stats["is_stub"] = discovered.is_stub
        self._init_stats["estimated_load_ms"] = discovered.estimated_load_time_ms

        logger.info(
            "model_discovered",
            model_id=discovered.model_id,
            model_type=discovered.model_type.value,
            model_dir=str(discovered.model_dir) if discovered.model_dir else None,
            estimated_load_ms=discovered.estimated_load_time_ms,
            discovery_time_ms=discovery_time_ms,
        )

        # Load the discovered model
        if discovered.is_stub:
            self._load_stub_detector()
        else:
            self._load_production_detector(discovered)

    def _load_production_detector(self, discovered: DiscoveredModel) -> None:
        """Load production detector (ONNX-only, bundle, or ONNX variant).

        Args:
            discovered: Discovered model information
        """
        try:
            load_start = time.perf_counter()

            # Create hierarchical threat scorer if config is provided
            scorer = None
            if self.config and self.config.l2_scoring:
                from raxe.domain.ml.scoring_models import ScoringMode
                from raxe.domain.ml.threat_scorer import HierarchicalThreatScorer

                try:
                    # Map config mode string to ScoringMode enum
                    mode_map = {
                        "high_security": ScoringMode.HIGH_SECURITY,
                        "balanced": ScoringMode.BALANCED,
                        "low_fp": ScoringMode.LOW_FP,
                    }
                    mode = mode_map.get(self.config.l2_scoring.mode, ScoringMode.BALANCED)

                    scorer = HierarchicalThreatScorer(
                        mode=mode,
                        enable_consistency_check=self.config.l2_scoring.enable_consistency_check,
                        enable_margin_analysis=self.config.l2_scoring.enable_margin_analysis,
                    )
                    logger.info(
                        "hierarchical_scorer_created",
                        mode=self.config.l2_scoring.mode,
                        consistency_check=self.config.l2_scoring.enable_consistency_check,
                        margin_analysis=self.config.l2_scoring.enable_margin_analysis,
                    )
                except Exception as e:
                    logger.warning(f"Failed to create hierarchical scorer: {e}", exc_info=True)
                    scorer = None

            # Check model type to choose correct loader
            if discovered.model_type == ModelType.ONNX_ONLY and discovered.model_dir:
                # Load Gemma 5-head detector
                from raxe.domain.ml.gemma_detector import create_gemma_detector

                logger.info(f"Loading Gemma detector from: {discovered.model_dir}")
                self._detector = create_gemma_detector(
                    model_dir=str(discovered.model_dir),
                    confidence_threshold=self.confidence_threshold,
                    scorer=scorer,
                    voting_preset=self.voting_preset,
                )
            else:
                # No other model types supported - raise clear error
                raise ValueError(
                    f"Unsupported model type: {discovered.model_type}. "
                    f"Only ONNX_ONLY (Gemma folder-based) models are supported."
                )

            load_time_ms = (time.perf_counter() - load_start) * 1000

            # Get model info
            model_info = self._detector.model_info

            # Update statistics
            self._init_stats.update({
                "model_load_time_ms": load_time_ms,
                "model_version": model_info.get("version", "unknown"),
                "embedding_model": model_info.get("embedding_model", "unknown"),
                "families": model_info.get("families", []),
                "latency_p95_ms": model_info.get("latency_p95_ms", 0),
            })

            logger.info(
                "production_detector_loaded",
                model_type=discovered.model_type.value,
                model_id=discovered.model_id,
                model_version=model_info.get("version", "unknown"),
                load_time_ms=load_time_ms,
                embedding_model=model_info.get("embedding_model", "unknown"),
                confidence_threshold=self.confidence_threshold,
                families=model_info.get("families", []),
            )

        except Exception as e:
            # Fallback to stub on errors
            logger.error(
                "production_detector_load_failed",
                error=str(e),
                error_type=type(e).__name__,
                fallback="stub_detector",
                exc_info=True,
            )

            self._init_stats["load_error"] = str(e)
            self._init_stats["load_error_type"] = type(e).__name__
            self._load_stub_detector()

    def _load_stub_detector(self) -> None:
        """Load stub detector (fallback when no models available)."""
        from raxe.domain.ml.stub_detector import StubL2Detector

        self._detector = StubL2Detector()

        # Update statistics
        self._init_stats.update({
            "model_type": "stub",
            "is_stub": True,
        })

        # Show user-visible warning once per process
        if not EagerL2Detector._stub_warning_shown:
            from pathlib import Path
            Path(__file__).parent.parent / "domain" / "ml" / "models"

            EagerL2Detector._stub_warning_shown = True

        logger.warning(
            "stub_detector_loaded",
            reason="no_production_models_available",
            warning="L2 ML detection unavailable - using stub (no actual detection)",
        )

    def analyze(
        self,
        text: str,
        l1_result: ScanResult,
        context: dict[str, Any] | None = None
    ) -> L2Result:
        """Analyze text with L2 ML detector.

        Model is already loaded (eager initialization), so this is fast.

        Args:
            text: Text to analyze
            l1_result: L1 scan results
            context: Optional context metadata

        Returns:
            L2 detection results

        Example:
            detector = EagerL2Detector(use_production=True)

            # Fast inference (model already loaded)
            result = detector.analyze(text, l1_results)
            print(f"Processing time: {result.processing_time_ms}ms")
        """
        if self._detector is None:
            raise RuntimeError("Detector not initialized")

        # Delegate to underlying detector
        return self._detector.analyze(text, l1_result, context)

    @property
    def initialization_stats(self) -> dict[str, Any]:
        """Get initialization statistics.

        Returns:
            Dictionary with initialization metrics:
                - load_time_ms: Total initialization time
                - model_type: Type of model loaded (onnx_only, stub)
                - is_stub: Whether stub detector is used
                - model_id: Model identifier
                - discovery_time_ms: Time spent discovering model
                - model_load_time_ms: Time spent loading model
                - estimated_load_ms: Estimated load time
                - timestamp: When initialization completed

        Example:
            detector = EagerL2Detector(use_production=True)
            stats = detector.initialization_stats

            print(f"Model type: {stats['model_type']}")
            print(f"Load time: {stats['load_time_ms']}ms")
        """
        return self._init_stats.copy()

    @property
    def model_info(self) -> dict[str, Any]:
        """Get model information.

        Implements L2Detector protocol requirement.

        Returns:
            Dictionary with model metadata
        """
        if self._detector is None:
            return {
                "name": "Uninitialized EagerL2Detector",
                "version": "unknown",
                "type": "eager",
                "is_stub": True,
            }

        # Delegate to underlying detector
        info = self._detector.model_info.copy()

        # Add eager-specific metadata
        info.update({
            "detector_type": "eager",
            "initialization_time_ms": self._init_stats.get("load_time_ms", 0),
        })

        return info


def create_eager_l2_detector(
    *,
    config: ScanConfig | None = None,
    use_production: bool = True,
    confidence_threshold: float = 0.5,
    models_dir: str | None = None,
) -> EagerL2Detector:
    """Factory function to create eager L2 detector.

    Args:
        config: Scan configuration (optional)
        use_production: Whether to use production L2 model
        confidence_threshold: Minimum confidence for L2 detections
        models_dir: Optional custom models directory

    Returns:
        EagerL2Detector instance (already initialized)

    Example:
        from raxe.application.eager_l2 import create_eager_l2_detector

        # Create detector (loads immediately)
        detector = create_eager_l2_detector(use_production=True)

        # Check initialization stats
        stats = detector.initialization_stats
        print(f"Loaded in {stats['load_time_ms']}ms")
        print(f"Model type: {stats['model_type']}")

        # Use detector
        result = detector.analyze(text, l1_results)
    """
    return EagerL2Detector(
        config=config,
        use_production=use_production,
        confidence_threshold=confidence_threshold,
        models_dir=models_dir,
    )
