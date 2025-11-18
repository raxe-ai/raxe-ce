"""
Production ONNX L2 Detector with Sentence-BERT Embeddings
RAXE CE v1.2.0+

This module wraps the ONNX detector bundle with embedding generation
to provide a complete L2 detection solution compatible with the L2Detector protocol.

Architecture:
1. Generate 768-dim embeddings using sentence-transformers
2. Run cascaded ONNX models (binary → family → subfamily)
3. Return L2Result with predictions

Performance:
- Embedding generation: ~20-50ms (CPU)
- ONNX inference: ~5-10ms (CPU)
- Total latency: ~30-60ms
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raxe.domain.engine.executor import ScanResult as L1ScanResult

from raxe.domain.ml.onnx_detector import BUNDLE_FAMILY_MAP, ONNXDetectorBundle
from raxe.domain.ml.protocol import (
    L2Detector,
    L2Prediction,
    L2Result,
    L2ThreatType,
)

logger = logging.getLogger(__name__)


# Map ThreatFamily to L2ThreatType protocol
from raxe.domain.ml.l2_detector import ThreatFamily

FAMILY_TO_L2_TYPE = {
    ThreatFamily.JAILBREAK: L2ThreatType.SEMANTIC_JAILBREAK,
    ThreatFamily.PROMPT_INJECTION: L2ThreatType.CONTEXT_MANIPULATION,
    ThreatFamily.COMMAND_INJECTION: L2ThreatType.OBFUSCATED_COMMAND,
    ThreatFamily.DATA_EXFILTRATION: L2ThreatType.DATA_EXFIL_PATTERN,
    ThreatFamily.BIAS_MANIPULATION: L2ThreatType.PRIVILEGE_ESCALATION,
    ThreatFamily.PII_EXPOSURE: L2ThreatType.DATA_EXFIL_PATTERN,
    ThreatFamily.HALLUCINATION: L2ThreatType.UNKNOWN,
    ThreatFamily.BENIGN: L2ThreatType.UNKNOWN,
}


class ProductionONNXDetector:
    """
    Production L2 Detector using ONNX models with sentence embeddings.

    This detector implements the L2Detector protocol and provides:
    - Automatic embedding generation using sentence-transformers
    - Fast ONNX inference (<10ms)
    - Full L2Result compatibility
    - Graceful degradation on errors

    Usage:
        detector = ProductionONNXDetector()
        result = detector.analyze(
            text="Ignore all instructions",
            l1_results=l1_scan_results
        )

        if result.has_predictions:
            for prediction in result.predictions:
                print(f"{prediction.threat_type.value}: {prediction.confidence:.1%}")
    """

    def __init__(
        self,
        model_dir: Path | None = None,
        confidence_threshold: float = 0.5,
        embedding_model: str = "sentence-transformers/all-mpnet-base-v2",
    ):
        """
        Initialize production ONNX detector.

        Args:
            model_dir: Directory containing ONNX bundle files
            confidence_threshold: Minimum confidence for predictions (default: 0.5)
            embedding_model: Sentence-transformers model name (default: all-MiniLM-L6-v2)

        Raises:
            ImportError: If onnxruntime or sentence-transformers not installed
        """
        # Lazy import sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "Production ONNX detector requires sentence-transformers. "
                "Install with: pip install sentence-transformers"
            ) from e

        # Load ONNX bundle
        self.detector = ONNXDetectorBundle(
            model_dir=model_dir,
            confidence_threshold=confidence_threshold,
        )

        # Load embedding model
        logger.info(f"Loading sentence-transformers model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        self.embedding_model_name = embedding_model

        logger.info(
            f"ProductionONNXDetector initialized "
            f"(threshold={confidence_threshold}, embeddings={embedding_model})"
        )

    def analyze(
        self,
        text: str,
        l1_result: L1ScanResult,
        context: dict[str, Any] | None = None
    ) -> L2Result:
        """
        Analyze text for semantic threats using ONNX ML models.

        Implements L2Detector protocol with ONNX inference.

        Args:
            text: Original prompt/response text to analyze
            l1_result: Results from L1 rule-based detection (used as context)
            context: Optional context dictionary (model name, user ID, etc.)

        Returns:
            L2Result with ML predictions and metadata

        Performance:
            - Embedding generation: 20-50ms
            - ONNX inference: 5-10ms
            - Total: 30-60ms
        """
        start_time = time.perf_counter()

        try:
            # Generate embeddings
            embeddings = self.embedding_model.encode(
                text,
                convert_to_numpy=True,
                show_progress_bar=False,
            )

            # Run ONNX inference
            result = self.detector.scan(
                prompt=text,
                embeddings=embeddings,
                include_details=True,
            )

            # Map to L2 protocol format
            predictions = []

            if result.is_threat:
                # Get threat family from details
                threat_family = ThreatFamily.BENIGN
                if result.details:
                    # Map family name back to enum
                    for family in ThreatFamily:
                        if self.detector.FAMILY_NAMES[family] == result.details.family:
                            threat_family = family
                            break

                # Map to L2 threat type
                l2_type = FAMILY_TO_L2_TYPE.get(threat_family, L2ThreatType.UNKNOWN)

                # Create prediction
                prediction = L2Prediction(
                    threat_type=l2_type,
                    confidence=result.confidence,
                    explanation=result.explanation,
                    features_used=(
                        result.details.matched_patterns if result.details else []
                    ),
                    metadata={
                        "recommended_action": result.recommended_action.value,
                        "severity": result.details.severity.value if result.details else "unknown",
                        "context": result.details.context if result.details else "unknown",
                        "family": result.details.family if result.details else "unknown",
                    }
                )
                predictions.append(prediction)

            # Calculate processing time
            processing_time_ms = (time.perf_counter() - start_time) * 1000

            # Get model info
            model_info = self.detector.get_model_info()

            # Create L2 result
            return L2Result(
                predictions=predictions,
                confidence=result.confidence if result.is_threat else 1.0 - result.confidence,
                processing_time_ms=processing_time_ms,
                model_version=f"onnx-v{model_info['version']}",
                features_extracted={
                    "text_length": len(text),
                    "embedding_dim": model_info["embedding_dim"],
                    "l1_detections": l1_result.detection_count if l1_result else 0,
                    "l1_highest_severity": (
                        l1_result.highest_severity().value
                        if l1_result and l1_result.has_detections
                        else "none"
                    ),
                },
                metadata={
                    "model_type": model_info["model_type"],
                    "embedding_model": self.embedding_model_name,
                    "is_stub": False,
                    "format": "onnx",
                }
            )

        except Exception as e:
            # Graceful degradation: return empty predictions on error
            processing_time_ms = (time.perf_counter() - start_time) * 1000

            logger.error(f"ONNX detector error: {e}", exc_info=True)

            return L2Result(
                predictions=[],
                confidence=0.0,
                processing_time_ms=processing_time_ms,
                model_version="onnx-v1.0",
                metadata={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "is_stub": False,
                    "format": "onnx",
                }
            )

    @property
    def model_info(self) -> dict[str, Any]:
        """
        Get model metadata.

        Returns:
            Dictionary with model information
        """
        info = self.detector.get_model_info()

        return {
            "name": "RAXE Production ONNX L2 Detector",
            "version": info["version"],
            "type": "ml",
            "format": "onnx",
            "is_stub": False,
            "latency_p95_ms": 60.0,  # Embedding + ONNX
            "accuracy": info["performance"]["binary_accuracy"],
            "description": (
                f"Production ONNX detector v{info['version']} with "
                f"{info['performance']['binary_accuracy']:.1%} binary accuracy, "
                f"{info['performance']['family_accuracy']:.1%} family accuracy"
            ),
            "performance": info["performance"],
            "capabilities": info["capabilities"],
            "device": info["inference_device"],
            "embedding_model": self.embedding_model_name,
            "embedding_dim": info["embedding_dim"],
        }


# Factory function for easy instantiation
def create_onnx_l2_detector(
    model_dir: Path | None = None,
    confidence_threshold: float = 0.5,
    embedding_model: str = "sentence-transformers/all-mpnet-base-v2",
) -> L2Detector:
    """
    Create production ONNX L2 detector instance.

    Args:
        model_dir: Directory containing ONNX bundle files
        confidence_threshold: Minimum confidence for predictions
        embedding_model: Sentence-transformers model for embeddings

    Returns:
        L2Detector implementation (ProductionONNXDetector)

    Example:
        detector = create_onnx_l2_detector()
        result = detector.analyze(text="...", l1_result=...)
    """
    return ProductionONNXDetector(
        model_dir=model_dir,
        confidence_threshold=confidence_threshold,
        embedding_model=embedding_model,
    )
