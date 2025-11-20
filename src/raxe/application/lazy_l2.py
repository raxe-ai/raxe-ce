"""Lazy loading wrapper for L2 ML detector.

⚠️ DEPRECATED: This module is deprecated in favor of EagerL2Detector.

DEPRECATION TIMELINE:
- v0.0.2 (current): Deprecated with warnings, still functional
- v0.1.0 (Q1 2026): Will emit FutureWarning
- v1.0.0 (Q2 2026): Will be removed entirely

LazyL2Detector can cause timeout issues on first scan due to lazy initialization.
Use EagerL2Detector for predictable initialization timing and no timeouts.

WHY DEPRECATED:
1. Can cause L2 timeout on first scan (model loads during scan, exceeds 150ms limit)
2. Unpredictable first-scan latency (5s model load inside scan timer)
3. Harder to debug initialization failures (errors occur during scan, not init)
4. Misleading performance metrics (initialization conflated with scan time)

MIGRATION GUIDE:
    # Old (deprecated)
    from raxe.application.lazy_l2 import LazyL2Detector
    detector = LazyL2Detector(config=config, use_production=True)

    # New (recommended)
    from raxe.application.eager_l2 import EagerL2Detector
    detector = EagerL2Detector(use_production=True, confidence_threshold=0.5)

PERFORMANCE COMPARISON:
    LazyL2Detector:
    - Init: <1ms (wrapper only)
    - First scan: 5,150ms (includes 5s model loading) ❌ TIMEOUT
    - Subsequent scans: 50ms

    EagerL2Detector:
    - Init: 2,300ms (loads ONNX model) ✓ ONE-TIME
    - First scan: 7ms (model ready) ✓ NO TIMEOUT
    - Subsequent scans: 7ms ✓ CONSISTENT

For more information, see: docs/ONNX_MODEL_LOADING.md
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

    # Class-level flag to show warning only once per process
    _stub_warning_shown = False

    def __init__(
        self,
        *,
        config: ScanConfig,
        use_production: bool,
        confidence_threshold: float
    ):
        """Initialize lazy L2 detector.

        DEPRECATED: Use EagerL2Detector instead to avoid first-scan timeout issues.

        Args:
            config: Scan configuration
            use_production: Whether to use production L2 model
            confidence_threshold: Minimum confidence for L2 detections
        """
        import warnings
        warnings.warn(
            "LazyL2Detector is deprecated and will be removed in a future version. "
            "Use EagerL2Detector instead to avoid first-scan timeout issues. "
            "See migration guide in module docstring.",
            DeprecationWarning,
            stacklevel=2
        )

        self.config = config
        self.use_production = use_production
        self.confidence_threshold = confidence_threshold
        self._detector: L2Detector | None = None
        self._initialized = False

        logger.warning(
            "LazyL2Detector is deprecated - use EagerL2Detector instead",
            use_production=use_production,
            threshold=confidence_threshold,
            reason="lazy_loading_causes_first_scan_timeout"
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
                from pathlib import Path
                models_dir = Path(__file__).parent.parent / "domain" / "ml" / "models"

                logger.warning(
                    "l2_bundle_failed",
                    error=str(e),
                    fallback="stub_detector",
                    models_dir=str(models_dir),
                    help="L2 ML detection unavailable. Falling back to stub detector (no actual threat detection). "
                         f"To enable L2: Place a .raxe model file in {models_dir}. "
                         "See L2_SCANNING_ISSUE_AND_FIX.md for details.",
                )

                # Show user-visible warning once per process
                if not LazyL2Detector._stub_warning_shown:
                    import sys
                    print(
                        f"\n⚠️  Warning: L2 ML model not found. Using stub detector (no threat detection).\n"
                        f"   Expected location: {models_dir}/raxe_model_l2.raxe\n"
                        f"   See L2_SCANNING_ISSUE_AND_FIX.md or 'raxe models list' for details.\n",
                        file=sys.stderr
                    )
                    LazyL2Detector._stub_warning_shown = True

                from raxe.domain.ml.stub_detector import StubL2Detector
                self._detector = StubL2Detector()

                model_info = self._detector.model_info
                logger.info(
                    "l2_detector_loaded",
                    detector_type="stub",
                    model_version=model_info.get("version", "unknown"),
                    is_stub=True,
                    warning="L2 ML detection unavailable - using stub (no actual detection)",
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

    @property
    def model_info(self) -> dict[str, Any]:
        """Get model information.

        Implements L2Detector protocol requirement.

        Returns:
            Dictionary with model metadata
        """
        if not self._initialized or self._detector is None:
            return {
                "name": "Uninitialized LazyL2Detector (DEPRECATED)",
                "version": "unknown",
                "type": "lazy",
                "is_stub": True,
                "deprecated": True,
            }

        # Delegate to underlying detector
        info = self._detector.model_info.copy()

        # Add lazy-specific metadata
        info.update({
            "detector_type": "lazy",
            "deprecated": True,
        })

        return info
