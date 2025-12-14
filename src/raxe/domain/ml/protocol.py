"""L2 ML detection protocol.

Defines the interface contract between L1 (rules) and L2 (ML models).

This is a PURE DOMAIN INTERFACE - no I/O operations.
Implementations may do I/O (loading models, etc.) but the protocol itself
defines pure transformation: text + L1 results → L2 predictions.

Performance requirement: <5ms for production implementations.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from raxe.domain.engine.executor import ScanResult as L1ScanResult


class L2ThreatType(Enum):
    """ML-detected threat types from Gemma 5-head classifier.

    Maps to the 9 threat families from the Gemma model.
    L2 complements L1 by catching threats that require understanding context,
    encoding, or subtle manipulation.
    """
    # Matches Gemma threat_family classes
    BENIGN = "benign"
    DATA_EXFILTRATION = "data_exfiltration"
    ENCODING_OR_OBFUSCATION = "encoding_or_obfuscation_attack"
    JAILBREAK = "jailbreak"
    OTHER_SECURITY = "other_security"
    PROMPT_INJECTION = "prompt_injection"
    RAG_OR_CONTEXT_ATTACK = "rag_or_context_attack"
    TOOL_OR_COMMAND_ABUSE = "tool_or_command_abuse"
    TOXIC_CONTENT = "toxic_or_policy_violating_content"

    @classmethod
    def from_family(cls, family_value: str) -> "L2ThreatType":
        """Map Gemma ThreatFamily value to L2ThreatType."""
        mapping = {
            "benign": cls.BENIGN,
            "data_exfiltration": cls.DATA_EXFILTRATION,
            "encoding_or_obfuscation_attack": cls.ENCODING_OR_OBFUSCATION,
            "jailbreak": cls.JAILBREAK,
            "other_security": cls.OTHER_SECURITY,
            "prompt_injection": cls.PROMPT_INJECTION,
            "rag_or_context_attack": cls.RAG_OR_CONTEXT_ATTACK,
            "tool_or_command_abuse": cls.TOOL_OR_COMMAND_ABUSE,
            "toxic_or_policy_violating_content": cls.TOXIC_CONTENT,
        }
        return mapping.get(family_value, cls.OTHER_SECURITY)


@dataclass(frozen=True)
class L2Prediction:
    """A single ML prediction.

    Represents one threat detected by the ML model with confidence score.

    Attributes:
        threat_type: Type of threat detected
        confidence: Confidence score (0.0-1.0) - higher means more certain
        explanation: Human-readable explanation of why this was flagged
        features_used: List of feature names that triggered this prediction
        metadata: Additional prediction metadata (model-specific)
        scoring_result: Optional hierarchical scoring result (if scorer is enabled)
    """
    threat_type: L2ThreatType
    confidence: float
    explanation: str | None = None
    features_used: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    scoring_result: Any | None = None  # ScoringResult from scoring.py

    def __post_init__(self) -> None:
        """Validate prediction."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0-1, got {self.confidence}")


@dataclass(frozen=True)
class L2Result:
    """Result from L2 ML detector.

    Contains all predictions from the ML model plus metadata about the
    inference process.

    Attributes:
        predictions: List of threat predictions (may be empty)
        confidence: Overall confidence in the analysis (0.0-1.0)
        processing_time_ms: L2 inference time in milliseconds
        model_version: Identifier of the model that produced this result
        features_extracted: Dictionary of features extracted for analysis
        metadata: Additional result metadata (model-specific)
        hierarchical_score: Optional hierarchical threat score (0-1)
        classification: Optional threat classification (SAFE, FP_LIKELY, etc.)
        recommended_action: Optional recommended action (ALLOW, BLOCK, etc.)
        decision_rationale: Optional explanation of classification decision
        signal_quality: Optional dict with consistency, margins, variance metrics
        voting: Optional voting result from ensemble voting engine
    """
    predictions: list[L2Prediction]
    confidence: float
    processing_time_ms: float
    model_version: str
    features_extracted: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    hierarchical_score: float | None = None
    classification: str | None = None
    recommended_action: str | None = None
    decision_rationale: str | None = None
    signal_quality: dict[str, Any] | None = None
    voting: dict[str, Any] | None = None  # VotingResult.to_dict() output

    def __post_init__(self) -> None:
        """Validate result."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0-1, got {self.confidence}")
        if self.processing_time_ms < 0:
            raise ValueError(
                f"processing_time_ms must be non-negative, got {self.processing_time_ms}"
            )

    @property
    def has_predictions(self) -> bool:
        """True if any threats were predicted."""
        return len(self.predictions) > 0

    @property
    def is_threat(self) -> bool:
        """True if L2 detected a threat (has predictions with actionable classification).

        This property is used by telemetry to determine l2_hit status.
        Uses voting result if available, otherwise falls back to classification.
        """
        if not self.predictions:
            return False
        # Use voting result if available (new ensemble voting engine)
        if self.voting:
            voting_decision = self.voting.get("decision")
            return voting_decision == "threat"
        # Check if classification indicates a threat (not FP_LIKELY or SAFE)
        if self.classification and self.classification in ("HIGH_THREAT", "THREAT", "LIKELY_THREAT", "REVIEW"):
            return True
        # Fallback: check if any prediction has high confidence
        return self.confidence >= 0.35

    @property
    def prediction_count(self) -> int:
        """Number of threats predicted."""
        return len(self.predictions)

    @property
    def highest_confidence(self) -> float:
        """Highest confidence across all predictions.

        Returns:
            Maximum confidence score, or 0.0 if no predictions
        """
        if not self.predictions:
            return 0.0
        return max(p.confidence for p in self.predictions)

    def get_predictions_by_type(self, threat_type: L2ThreatType) -> list[L2Prediction]:
        """Get all predictions of a specific threat type.

        Args:
            threat_type: The threat type to filter by

        Returns:
            List of predictions matching the threat type
        """
        return [p for p in self.predictions if p.threat_type == threat_type]

    def to_summary(self) -> str:
        """Generate human-readable summary.

        Returns:
            Summary string like "2 ML predictions (0.85 confidence) in 3.2ms"
        """
        if not self.has_predictions:
            return f"No ML predictions ({self.processing_time_ms:.2f}ms)"

        return (
            f"{self.prediction_count} ML prediction{'s' if self.prediction_count > 1 else ''} "
            f"(max confidence: {self.highest_confidence:.2f}) "
            f"in {self.processing_time_ms:.2f}ms"
        )


class L2Detector(Protocol):
    """Protocol for L2 ML-based threat detectors.

    This defines the interface contract that all L2 implementations must follow,
    whether it's a stub, ONNX model, or cloud API.

    Design principles:
    1. L2 AUGMENTS L1, never replaces it
    2. L2 receives L1 results as features (can learn from rule detections)
    3. L2 must complete in <5ms for production use
    4. L2 returns probabilistic predictions, not binary decisions
    5. L2 implementations can be swapped (stub → ONNX → cloud)

    Example implementations:
    - StubL2Detector: Simple heuristics for MVP
    - ONNXDetector: Optimized ML model for production
    - CloudDetector: Remote API for complex analysis
    """

    def analyze(
        self,
        text: str,
        l1_results: L1ScanResult,
        context: dict[str, Any] | None = None
    ) -> L2Result:
        """Analyze text for semantic threats using ML.

        This is the core method of the L2 protocol. It receives:
        1. Raw text to analyze
        2. L1 rule-based detection results (as features)
        3. Optional context (model name, user ID, session, etc.)

        And returns:
        1. List of ML predictions
        2. Confidence scores
        3. Processing metadata

        Args:
            text: Original prompt/response text to analyze
            l1_results: Results from L1 rule-based detection
            context: Optional context dictionary with keys like:
                - 'model': LLM model name (e.g., 'gpt-4')
                - 'user_id': User identifier (hashed)
                - 'session_id': Session identifier
                - 'conversation_history': Prior messages
                - etc.

        Returns:
            L2Result with ML predictions and metadata

        Performance:
            - MUST complete in <5ms (P95 latency)
            - Should be <3ms average
            - Failures should degrade gracefully (return empty predictions)

        Notes:
            - L2 can use L1 results as features
            - L2 should NOT block on L1 failures (defensive programming)
            - L2 predictions are probabilistic, not definitive
            - Higher confidence doesn't mean "block" - let application layer decide
        """
        ...

    @property
    def model_info(self) -> dict[str, Any]:
        """Information about the model.

        Returns:
            Dictionary with model metadata. Recommended keys:
                - 'name': Model name
                - 'version': Model version
                - 'type': 'heuristic' | 'ml' | 'cloud'
                - 'size_mb': Model size in megabytes
                - 'is_stub': True if this is a placeholder implementation
                - 'latency_p95_ms': Expected P95 latency
                - 'accuracy': Expected accuracy (if known)
                - 'description': Human-readable description

        Example:
            {
                'name': 'RAXE Stub L2 Detector',
                'version': 'stub-1.0.0',
                'type': 'heuristic',
                'is_stub': True,
                'latency_p95_ms': 1.0,
                'description': 'Simple pattern-based stub for MVP'
            }
        """
        ...


# Type alias for convenience
L2DetectorType = L2Detector
