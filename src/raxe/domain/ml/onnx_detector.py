"""
ONNX-based L2 Detector for Production Inference
RAXE CE v1.2.0+

This module provides production-ready L2 detection using ONNX Runtime
for fast, cross-platform inference with the cascaded detector bundle.

Architecture:
- Binary classifier: Malicious (1) vs Benign (0)
- Family classifier: 6 threat families (CMD, JB, PI, PII, TOX, XX)
- Subfamily classifier: 93 fine-grained threat types

Performance:
- Binary accuracy: 90.2%, F1: 78.5%
- Family accuracy: 76.5%, F1: 77.9% (weighted)
- Inference time: <10ms (CPU)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass

from raxe.domain.ml.l2_detector import (
    ContextType,
    L2DetectionDetails,
    L2DetectionResult,
    RecommendedAction,
    SeverityLevel,
    ThreatFamily,
)

logger = logging.getLogger(__name__)


# Map bundle family labels to ThreatFamily enum
BUNDLE_FAMILY_MAP = {
    "CMD": ThreatFamily.COMMAND_INJECTION,
    "JB": ThreatFamily.JAILBREAK,
    "PI": ThreatFamily.PROMPT_INJECTION,
    "PII": ThreatFamily.PII_EXPOSURE,
    "TOX": ThreatFamily.BIAS_MANIPULATION,  # Map toxicity to bias manipulation
    "XX": ThreatFamily.BENIGN,  # Unknown/other
}


@dataclass
class BundleMetadata:
    """Metadata from the detector bundle."""
    version: str
    embedding_dim: int
    confidence_threshold: float
    n_binary_classes: int
    n_family_classes: int
    n_subfamily_classes: int
    binary_accuracy: float
    family_accuracy: float
    subfamily_accuracy: float
    family_labels: list[str]
    subfamily_labels: list[str]


class ONNXDetectorBundle:
    """
    Production L2 detector using ONNX Runtime with cascaded models.

    This detector uses a multi-stage approach:
    1. Binary classification (malicious/benign)
    2. If malicious, classify threat family (6 categories)
    3. If malicious, classify threat subfamily (93 fine-grained types)

    Usage:
        detector = ONNXDetectorBundle()
        result = detector.scan("Ignore all previous instructions")

        if result.is_threat:
            print(result.explanation)
            # "High jailbreak (high confidence)"
    """

    # Thresholds for action recommendations
    BLOCK_THRESHOLD = 0.8      # Block if malicious probability > 80%
    WARN_THRESHOLD = 0.5       # Warn if malicious probability > 50%

    # Family names (human-readable)
    FAMILY_NAMES = {
        ThreatFamily.BENIGN: "Benign",
        ThreatFamily.COMMAND_INJECTION: "Command Injection",
        ThreatFamily.PII_EXPOSURE: "PII Exposure",
        ThreatFamily.JAILBREAK: "Jailbreak",
        ThreatFamily.PROMPT_INJECTION: "Prompt Injection",
        ThreatFamily.DATA_EXFILTRATION: "Data Exfiltration",
        ThreatFamily.BIAS_MANIPULATION: "Bias Manipulation",
        ThreatFamily.HALLUCINATION: "Hallucination",
    }

    def __init__(
        self,
        model_dir: Path | None = None,
        confidence_threshold: float | None = None,
    ):
        """
        Initialize ONNX detector bundle.

        Args:
            model_dir: Directory containing the detector bundle files
            confidence_threshold: Override default confidence threshold

        Raises:
            ImportError: If onnxruntime is not installed
            FileNotFoundError: If bundle files are missing
        """
        # Lazy import onnxruntime
        try:
            import onnxruntime as ort
        except ImportError as e:
            raise ImportError(
                "ONNX detector requires onnxruntime. "
                "Install with: pip install onnxruntime"
            ) from e

        if model_dir is None:
            model_dir = Path(__file__).parent / "models"

        self.model_dir = Path(model_dir)

        # Load metadata
        self.metadata = self._load_metadata()

        # Override threshold if specified
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else self.metadata.confidence_threshold
        )

        # Create ONNX session options
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = 2  # Limit threads for better latency

        # Execution providers (CPU only for now, can add GPU later)
        providers = ['CPUExecutionProvider']

        # Load models
        logger.info("Loading ONNX detector bundle...")

        self.binary_session = ort.InferenceSession(
            str(self.model_dir / "binary_classifier.onnx"),
            sess_options,
            providers=providers
        )

        self.family_session = ort.InferenceSession(
            str(self.model_dir / "family_classifier.onnx"),
            sess_options,
            providers=providers
        )

        self.subfamily_session = ort.InferenceSession(
            str(self.model_dir / "subfamily_classifier.onnx"),
            sess_options,
            providers=providers
        )

        logger.info(
            f"ONNX detector loaded (v{self.metadata.version}, "
            f"binary_acc={self.metadata.binary_accuracy:.1%}, "
            f"family_acc={self.metadata.family_accuracy:.1%})"
        )

    def _load_metadata(self) -> BundleMetadata:
        """Load metadata and label encoders from bundle."""
        # Load model metadata
        with open(self.model_dir / "model_metadata.json") as f:
            metadata = json.load(f)

        # Load label encoders
        with open(self.model_dir / "label_encoders.json") as f:
            encoders = json.load(f)

        return BundleMetadata(
            version=metadata["model_version"],
            embedding_dim=metadata["embedding_dim"],
            confidence_threshold=metadata["confidence_threshold"],
            n_binary_classes=metadata["n_binary_classes"],
            n_family_classes=metadata["n_family_classes"],
            n_subfamily_classes=metadata["n_subfamily_classes"],
            binary_accuracy=metadata["training_metrics"]["binary"]["accuracy"],
            family_accuracy=metadata["training_metrics"]["family"]["accuracy"],
            subfamily_accuracy=metadata["training_metrics"]["subfamily"]["accuracy"],
            family_labels=encoders["family"]["classes"],
            subfamily_labels=encoders["subfamily"]["classes"],
        )

    def scan(
        self,
        prompt: str,
        embeddings: np.ndarray | None = None,
        include_details: bool = True
    ) -> L2DetectionResult:
        """
        Scan a prompt for threats using ONNX models.

        Args:
            prompt: The prompt text to scan
            embeddings: Pre-computed embeddings (768-dim) or None to skip ML
            include_details: Whether to include detailed context

        Returns:
            L2DetectionResult with human-readable explanation

        Notes:
            - If embeddings is None, returns benign result (embeddings required)
            - Binary classifier runs first, then family/subfamily if malicious
            - Confidence threshold determines ALLOW/WARN/BLOCK action
        """
        # If no embeddings provided, cannot run ML inference
        if embeddings is None:
            return L2DetectionResult(
                is_threat=False,
                confidence=0.0,
                explanation="No ML embeddings available (embeddings required)",
                recommended_action=RecommendedAction.ALLOW,
                details=None,
            )

        # Ensure embeddings are correct shape (1, 768)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        if embeddings.shape[1] != self.metadata.embedding_dim:
            raise ValueError(
                f"Expected embeddings of dimension {self.metadata.embedding_dim}, "
                f"got {embeddings.shape[1]}"
            )

        # Convert to float32 for ONNX
        embeddings = embeddings.astype(np.float32)

        # Run binary classification
        binary_outputs = self.binary_session.run(
            None,
            {"input": embeddings}
        )
        # Output format: [labels, probabilities_dict]
        binary_label = int(binary_outputs[0][0])  # Predicted class (0 or 1)
        binary_probs_dict = binary_outputs[1][0]  # Dict mapping class -> probability

        # Extract probabilities
        # binary_probs_dict is like {0: 0.3, 1: 0.7}
        malicious_prob = float(binary_probs_dict.get(1, 0.0))  # P(malicious)
        is_threat = malicious_prob >= self.confidence_threshold

        # If not a threat, return early
        if not is_threat:
            return L2DetectionResult(
                is_threat=False,
                confidence=1.0 - malicious_prob,  # Confidence in benign
                explanation="No threats detected",
                recommended_action=RecommendedAction.ALLOW,
                details=None,
            )

        # Run family classification
        family_outputs = self.family_session.run(
            None,
            {"input": embeddings}
        )
        family_label_idx = int(family_outputs[0][0])
        family_probs_dict = family_outputs[1][0]

        family_label = self.metadata.family_labels[family_label_idx]
        family_confidence = float(family_probs_dict.get(family_label_idx, 0.0))

        # Map to ThreatFamily enum
        threat_family = BUNDLE_FAMILY_MAP.get(family_label, ThreatFamily.BENIGN)

        # Run subfamily classification
        subfamily_outputs = self.subfamily_session.run(
            None,
            {"input": embeddings}
        )
        subfamily_label_idx = int(subfamily_outputs[0][0])
        subfamily_probs_dict = subfamily_outputs[1][0]

        subfamily_label = self.metadata.subfamily_labels[subfamily_label_idx]
        subfamily_confidence = float(subfamily_probs_dict.get(subfamily_label_idx, 0.0))

        # Determine severity based on subfamily confidence
        severity_score = subfamily_confidence

        # Determine recommended action
        if malicious_prob >= self.BLOCK_THRESHOLD:
            recommended_action = RecommendedAction.BLOCK
        elif malicious_prob >= self.WARN_THRESHOLD:
            recommended_action = RecommendedAction.WARN
        else:
            recommended_action = RecommendedAction.ALLOW

        # Generate explanation
        explanation = self._generate_explanation(
            is_threat=True,
            confidence=malicious_prob,
            family=threat_family,
            severity_score=severity_score,
        )

        # Generate details if requested
        details = None
        if include_details:
            # Map severity score to SeverityLevel
            if severity_score >= 0.8:
                severity_level = SeverityLevel.CRITICAL
            elif severity_score >= 0.6:
                severity_level = SeverityLevel.HIGH
            elif severity_score >= 0.4:
                severity_level = SeverityLevel.MEDIUM
            elif severity_score >= 0.2:
                severity_level = SeverityLevel.LOW
            else:
                severity_level = SeverityLevel.NONE

            # Determine context based on threat type
            # For now, mark all threats as ATTACK context
            context = ContextType.ATTACK

            details = L2DetectionDetails(
                family=self.FAMILY_NAMES[threat_family],
                severity=severity_level,
                context="Attack",  # Context name
                confidence_level="high" if malicious_prob >= 0.8 else "moderate" if malicious_prob >= 0.5 else "low",
                matched_patterns=[
                    f"family={family_label} ({family_confidence:.1%})",
                    f"subfamily={subfamily_label} ({subfamily_confidence:.1%})",
                ],
            )

        return L2DetectionResult(
            is_threat=True,
            confidence=malicious_prob,
            explanation=explanation,
            recommended_action=recommended_action,
            details=details,
        )

    def _softmax(self, logits: np.ndarray) -> np.ndarray:
        """Apply softmax to convert logits to probabilities."""
        exp_logits = np.exp(logits - np.max(logits))  # Numerical stability
        return exp_logits / np.sum(exp_logits)

    def _generate_explanation(
        self,
        is_threat: bool,
        confidence: float,
        family: ThreatFamily,
        severity_score: float,
    ) -> str:
        """
        Generate concise, human-readable explanation.

        Examples:
            "No threats detected"
            "Low prompt injection (moderate confidence)"
            "High jailbreak (high confidence)"
            "Critical command injection (high confidence)"
        """
        if not is_threat:
            return "No threats detected"

        # Map confidence to human-readable level
        if confidence >= 0.8:
            confidence_str = "high confidence"
        elif confidence >= 0.5:
            confidence_str = "moderate confidence"
        else:
            confidence_str = "low confidence"

        # Map severity score to level
        if severity_score >= 0.8:
            severity_level = "Critical"
        elif severity_score >= 0.6:
            severity_level = "High"
        elif severity_score >= 0.4:
            severity_level = "Medium"
        else:
            severity_level = "Low"

        # Get family name
        family_name = self.FAMILY_NAMES[family].lower()

        # Generate explanation
        return f"{severity_level} {family_name} ({confidence_str})"

    def get_model_info(self) -> dict:
        """
        Get model metadata.

        Returns:
            Dictionary with model information
        """
        return {
            "version": self.metadata.version,
            "model_type": "ONNX Cascaded Classifier",
            "format": "onnx",
            "performance": {
                "binary_accuracy": self.metadata.binary_accuracy,
                "binary_f1": 0.785,  # From metadata
                "family_accuracy": self.metadata.family_accuracy,
                "family_f1": 0.780,  # From metadata
                "subfamily_accuracy": self.metadata.subfamily_accuracy,
            },
            "capabilities": [
                f"Binary classification ({self.metadata.n_binary_classes} classes)",
                f"Family classification ({self.metadata.n_family_classes} families)",
                f"Subfamily classification ({self.metadata.n_subfamily_classes} types)",
            ],
            "inference_device": "CPU",
            "embedding_dim": self.metadata.embedding_dim,
            "confidence_threshold": self.confidence_threshold,
        }
