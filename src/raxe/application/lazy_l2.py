"""Lazy loading wrapper for L2 ML detector.

This module provides a lazy loading wrapper for the L2 detector to improve
first scan startup time. The L2 model is only loaded when first needed,
reducing initialization time from ~4s to <2s.

Key Benefits:
- Faster time-to-first-scan for users
- L2 only loaded if actually used (respects l2_enabled flag)
- Transparent to the rest of the system (implements L2Detector protocol)
"""

import logging
from typing import Any

from raxe.domain.engine.executor import ScanResult
from raxe.domain.ml.protocol import L2Detector, L2Result
from raxe.infrastructure.config.scan_config import ScanConfig

logger = logging.getLogger(__name__)


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

    def _ensure_initialized(self) -> L2Detector:
        """Ensure L2 detector is initialized, loading it if needed.

        Returns:
            The initialized L2 detector
        """
        if self._initialized and self._detector is not None:
            return self._detector

        logger.info("Loading L2 detector on first use...")

        if self.use_production:
            try:
                from raxe.domain.ml.factory import create_production_l2_detector

                self._detector = create_production_l2_detector(
                    confidence_threshold=self.confidence_threshold
                )
                logger.info(
                    f"Production L2 detector loaded "
                    f"(threshold={self.confidence_threshold})"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to load production L2 detector: {e}. "
                    f"Falling back to stub detector."
                )
                from raxe.domain.ml.stub_detector import StubL2Detector
                self._detector = StubL2Detector()
        else:
            from raxe.domain.ml.stub_detector import StubL2Detector
            self._detector = StubL2Detector()
            logger.info("Using stub L2 detector (use_production_l2=false)")

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
