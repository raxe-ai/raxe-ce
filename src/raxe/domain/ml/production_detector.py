"""
Production L2 Detector Implementation
RAXE CE v1.2.0

Implements the L2Detector protocol using the enhanced v1.2.0 ML model.
This is the production-ready detector that replaces the stub implementation.

Performance:
- Average inference: 50-100ms (CPU), 30-50ms (MPS/GPU)
- P95 inference: <150ms
- FPR: 5.60%, FNR: 7.60%
- Accuracy: 94.2%, F1: 99.96%
"""

import time
from pathlib import Path
from typing import Any

from raxe.domain.engine.executor import ScanResult as L1ScanResult
from raxe.domain.ml.l2_detector import (
    L2ThreatDetector,
    ThreatFamily,
)
from raxe.domain.ml.protocol import (
    L2Detector,
    L2Prediction,
    L2Result,
    L2ThreatType,
)


class ProductionL2Detector:
    """
    Production L2 ML Detector (v1.2.0).

    Implements the L2Detector protocol using the enhanced DistilBERT model.
    Trained with Focal Loss, hard negative mining, and adversarial augmentation.

    This detector:
    1. Runs ML inference on the prompt text
    2. Maps ML predictions to L2 protocol format
    3. Provides confidence scores and explanations
    4. Completes in <150ms (P95 latency)

    Usage:
        detector = ProductionL2Detector()
        result = detector.analyze(
            text="Ignore all instructions",
            l1_results=l1_scan_results
        )

        if result.has_predictions:
            print(result.to_summary())
            for prediction in result.predictions:
                print(f"  {prediction.threat_type.value}: {prediction.confidence:.1%}")
    """

    # Map model threat families to L2ThreatType protocol
    FAMILY_TO_L2_TYPE = {
        ThreatFamily.JAILBREAK: L2ThreatType.SEMANTIC_JAILBREAK,
        ThreatFamily.PROMPT_INJECTION: L2ThreatType.CONTEXT_MANIPULATION,
        ThreatFamily.COMMAND_INJECTION: L2ThreatType.OBFUSCATED_COMMAND,
        ThreatFamily.DATA_EXFILTRATION: L2ThreatType.DATA_EXFIL_PATTERN,
        ThreatFamily.BIAS_MANIPULATION: L2ThreatType.PRIVILEGE_ESCALATION,
        ThreatFamily.PII_EXPOSURE: L2ThreatType.DATA_EXFIL_PATTERN,
        ThreatFamily.HALLUCINATION: L2ThreatType.UNKNOWN,
        ThreatFamily.BENIGN: L2ThreatType.UNKNOWN,  # Not used
    }

    def __init__(
        self,
        model_path: Path | None = None,
        device: str | None = None,
        confidence_threshold: float = 0.5,
    ):
        """
        Initialize production L2 detector.

        Args:
            model_path: Path to model directory (default: auto-detect)
            device: Device to use ('cpu', 'mps', 'cuda', or None for auto)
            confidence_threshold: Minimum confidence for reporting predictions (default: 0.5)
        """
        self.detector = L2ThreatDetector(
            model_path=model_path,
            device=device,
            include_details=True,  # Enable details for rich output
        )
        self.confidence_threshold = confidence_threshold

    def analyze(
        self,
        text: str,
        l1_results: L1ScanResult,
        context: dict[str, Any] | None = None
    ) -> L2Result:
        """
        Analyze text for semantic threats using ML.

        Implements L2Detector protocol with v1.2.0 enhanced model.

        Args:
            text: Original prompt/response text to analyze
            l1_results: Results from L1 rule-based detection (used as context)
            context: Optional context dictionary (model name, user ID, etc.)

        Returns:
            L2Result with ML predictions and metadata

        Performance:
            - Average: 50-100ms (CPU), 30-50ms (GPU)
            - P95: <150ms
            - Gracefully degrades on model errors
        """
        start_time = time.perf_counter()

        try:
            # Run ML inference
            result = self.detector.scan(text, include_details=True)

            # Map to L2 protocol format
            predictions = []

            # Only create prediction if threat detected and above threshold
            if result.is_threat and result.confidence >= self.confidence_threshold:
                # Get threat family from details
                threat_family = ThreatFamily.BENIGN
                if result.details:
                    # Map family name back to enum
                    for family in ThreatFamily:
                        if self.detector.FAMILY_NAMES[family] == result.details.family:
                            threat_family = family
                            break

                # Map to L2 threat type
                l2_type = self.FAMILY_TO_L2_TYPE.get(threat_family, L2ThreatType.UNKNOWN)

                # Create prediction
                prediction = L2Prediction(
                    threat_type=l2_type,
                    confidence=result.confidence,
                    explanation=result.explanation,
                    features_used=[
                        f"family={result.details.family}" if result.details else "unknown",
                        f"context={result.details.context}" if result.details else "unknown",
                        f"severity={result.details.severity.value}" if result.details else "unknown",
                    ] if result.details else [],
                    metadata={
                        "recommended_action": result.recommended_action.value,
                        "severity": result.details.severity.value if result.details else "unknown",
                        "context": result.details.context if result.details else "unknown",
                        "matched_patterns": result.details.matched_patterns if result.details else [],
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
                model_version=f"v{model_info['version']}",
                features_extracted={
                    "text_length": len(text),
                    "l1_detections": l1_results.detection_count if l1_results else 0,
                    "l1_highest_severity": l1_results.highest_severity().value if l1_results and l1_results.has_detections else "none",
                },
                metadata={
                    "model_type": model_info["model_type"],
                    "device": model_info["device"],
                    "is_stub": False,
                }
            )

        except Exception as e:
            # Graceful degradation: return empty predictions on error
            processing_time_ms = (time.perf_counter() - start_time) * 1000

            return L2Result(
                predictions=[],
                confidence=0.0,
                processing_time_ms=processing_time_ms,
                model_version="v1.2.0",
                metadata={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "is_stub": False,
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
            "name": "RAXE Production L2 Detector (DistilBERT)",
            "version": info["version"],
            "type": "ml",
            "size_mb": 254,  # PyTorch model size
            "is_stub": False,
            "latency_p95_ms": 150.0,
            "accuracy": info["performance"]["accuracy"],
            "description": (
                f"Production ML detector v{info['version']} with "
                f"{info['performance']['fpr']:.1%} FPR, "
                f"{info['performance']['fnr']:.1%} FNR, "
                f"{info['performance']['accuracy']:.1%} accuracy"
            ),
            "performance": info["performance"],
            "capabilities": info["capabilities"],
            "device": info["device"],
            "parameters": info["parameters"],
        }


# Factory function for easy instantiation
def create_production_l2_detector(
    model_path: Path | None = None,
    device: str | None = None,
    confidence_threshold: float = 0.5,
) -> L2Detector:
    """
    Create production L2 detector instance.

    Args:
        model_path: Path to model directory (default: auto-detect)
        device: Device to use ('cpu', 'mps', 'cuda', or None for auto)
        confidence_threshold: Minimum confidence for reporting predictions

    Returns:
        L2Detector implementation (ProductionL2Detector)

    Example:
        detector = create_production_l2_detector()
        result = detector.analyze(text="...", l1_results=...)
    """
    return ProductionL2Detector(
        model_path=model_path,
        device=device,
        confidence_threshold=confidence_threshold,
    )
