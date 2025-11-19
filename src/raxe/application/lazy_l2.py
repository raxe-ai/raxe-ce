"""Lazy loading wrapper for L2 ML detector.

This module provides a lazy loading wrapper for the L2 detector to improve
first scan startup time. The L2 model is only loaded when first needed,
reducing initialization time from ~4s to <2s.

Key Benefits:
- Faster time-to-first-scan for users
- L2 only loaded if actually used (respects l2_enabled flag)
- Transparent to the rest of the system (implements L2Detector protocol)
"""

from typing import Any

from raxe.domain.engine.executor import ScanResult
from raxe.domain.ml.protocol import L2Detector, L2Result
from raxe.infrastructure.config.scan_config import ScanConfig
from raxe.utils.logging import get_logger

logger = get_logger(__name__)


class LazyL2Detector:
    """Lazy loading wrapper for L2 ML detector.

    Implements the L2Detector protocol but defers actual L2 initialization
    until the first call to analyze(). This significantly reduces startup time.
    """

    def __init__(
        self,
        *,
        config: ScanConfig,
        use_production: bool,
        confidence_threshold: float
    ):
        """Initialize lazy L2 detector.

        Args:
            config: Scan configuration
            use_production: Whether to use production L2 model
            confidence_threshold: Minimum confidence for L2 detections
        """
        self.config = config
        self.use_production = use_production
        self.confidence_threshold = confidence_threshold
        self._detector: L2Detector | None = None
        self._initialized = False

        logger.info(
            "LazyL2Detector created "
            f"(use_production={use_production}, threshold={confidence_threshold})"
        )

    def _find_bundled_model(self) -> str | None:
        """Auto-discover bundled L2 model file.

        Searches for .raxe bundle files in the models directory.
        Prioritizes raxe_model_l2.raxe if it exists.

        Returns:
            Path to the bundled model file, or None if not found
        """
        from pathlib import Path

        # Get the models directory relative to this file
        # src/raxe/application/lazy_l2.py -> src/raxe/domain/ml/models/
        current_file = Path(__file__)
        models_dir = current_file.parent.parent / "domain" / "ml" / "models"

        # First, try the primary L2 model
        primary_model = models_dir / "raxe_model_l2.raxe"
        if primary_model.exists():
            logger.info(f"Found primary L2 model: {primary_model}")
            return str(primary_model)

        # Fallback: find any .raxe file
        raxe_files = list(models_dir.glob("*.raxe"))
        if raxe_files:
            # Sort by modification time, use most recent
            raxe_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            logger.info(f"Found bundled model: {raxe_files[0]}")
            return str(raxe_files[0])

        logger.warning(f"No bundled L2 models found in {models_dir}")
        return None

    def _ensure_initialized(self) -> L2Detector:
        """Ensure L2 detector is initialized, loading it if needed.

        Returns:
            The initialized L2 detector
        """
        if self._initialized and self._detector is not None:
            return self._detector

        logger.info(
            "l2_detector_loading",
            use_production=self.use_production,
            confidence_threshold=self.confidence_threshold,
        )

        if self.use_production:
            # Try bundle-based detector first (unified model format)
            try:
                from raxe.domain.ml.bundle_detector import create_bundle_detector
                from pathlib import Path

                # Auto-discover bundled model
                model_path = self._find_bundled_model()

                if model_path:
                    logger.info(f"Loading bundled L2 model from: {model_path}")
                    self._detector = create_bundle_detector(
                        bundle_path=model_path,
                        confidence_threshold=self.confidence_threshold
                    )

                    # Get model info for logging
                    model_info = self._detector.model_info
                    logger.info(
                        "l2_detector_loaded",
                        detector_type="bundle",
                        model_version=model_info.get("version", "unknown"),
                        model_id=model_info.get("model_id", "unknown"),
                        embedding_model=model_info.get("embedding_model", "unknown"),
                        confidence_threshold=self.confidence_threshold,
                        latency_p95_ms=model_info.get("latency_p95_ms", 0),
                        families=model_info.get("families", []),
                    )
                else:
                    raise FileNotFoundError("No bundled L2 model found")

            except Exception as e:
                # Fallback to stub detector if bundle loading fails
                logger.warning(
                    "l2_bundle_failed",
                    error=str(e),
                    fallback="stub_detector",
                )
                from raxe.domain.ml.stub_detector import StubL2Detector
                self._detector = StubL2Detector()

                model_info = self._detector.model_info
                logger.info(
                    "l2_detector_loaded",
                    detector_type="stub",
                    model_version=model_info.get("version", "unknown"),
                    is_stub=True,
                )
        else:
            from raxe.domain.ml.stub_detector import StubL2Detector
            self._detector = StubL2Detector()

            model_info = self._detector.model_info
            logger.info(
                "l2_detector_loaded",
                detector_type="stub",
                model_version=model_info.get("version", "unknown"),
                is_stub=True,
                reason="use_production_l2_disabled",
            )

        self._initialized = True
        return self._detector

    def analyze(
        self,
        text: str,
        l1_result: ScanResult,
        context: dict[str, Any] | None = None
    ) -> L2Result:
        """Analyze text with L2 ML detector (lazy loads on first call).

        Args:
            text: Text to analyze
            l1_result: L1 scan results
            context: Optional context metadata

        Returns:
            L2 detection results
        """
        # Lazy load detector on first use
        detector = self._ensure_initialized()

        # Delegate to actual detector
        return detector.analyze(text, l1_result, context)
