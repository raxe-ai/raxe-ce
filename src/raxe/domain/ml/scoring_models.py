"""Threat scoring data models.

Pure domain models for the hierarchical threat scoring system.
These models define the structure of scoring inputs, outputs, and configurations
without any I/O operations or side effects.

This follows Clean Architecture principles:
- Immutable data classes (frozen=True)
- No external dependencies (no numpy, no I/O)
- Type hints everywhere
- Clear validation rules
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ThreatLevel(Enum):
    """Threat classification levels.

    These levels represent increasing confidence that a detection is a true threat:

    - SAFE: Clearly not a threat (threat_score < 0.5)
    - FP_LIKELY: Likely false positive (all confidence signals weak)
    - REVIEW: Uncertain, needs manual review (inconsistent or low confidence)
    - LIKELY_THREAT: High confidence threat with obvious attack patterns
    - THREAT: Confident threat detection (strong signals)
    - HIGH_THREAT: Very confident threat (all signals very strong)
    """
    SAFE = "SAFE"
    FP_LIKELY = "FP_LIKELY"
    REVIEW = "REVIEW"
    LIKELY_THREAT = "LIKELY_THREAT"
    THREAT = "THREAT"
    HIGH_THREAT = "HIGH_THREAT"


class ActionType(Enum):
    """Recommended actions for each threat level.

    These actions guide how the system should respond to a detection:

    - ALLOW: Allow request to proceed (SAFE classification)
    - ALLOW_WITH_LOG: Allow but log for monitoring (FP_LIKELY classification)
    - MANUAL_REVIEW: Queue for human review (REVIEW classification)
    - BLOCK_WITH_REVIEW: Block request, flag for review (LIKELY_THREAT classification)
    - BLOCK: Block the request (THREAT classification)
    - BLOCK_ALERT: Block and send alert to security team (HIGH_THREAT classification)
    """
    ALLOW = "ALLOW"
    ALLOW_WITH_LOG = "ALLOW_WITH_LOG"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    BLOCK_WITH_REVIEW = "BLOCK_WITH_REVIEW"
    BLOCK = "BLOCK"
    BLOCK_ALERT = "BLOCK_ALERT"


class ScoringMode(Enum):
    """Scoring mode presets with different threshold profiles.

    Each mode represents a different risk tolerance:

    - HIGH_SECURITY: Minimize false negatives (block more, accept some FPs)
      Use for: Banking, healthcare, high-risk applications

    - BALANCED: Balance FPs and FNs (recommended default)
      Use for: General SaaS applications, most production use cases

    - LOW_FP: Minimize false positives (block less, accept some FNs)
      Use for: Educational platforms, creative tools, low-risk applications
    """
    HIGH_SECURITY = "high_security"
    BALANCED = "balanced"
    LOW_FP = "low_fp"


@dataclass(frozen=True)
class ThreatScore:
    """Raw ML model outputs for a single detection.

    Contains the 5-head hierarchical classification from Gemma model:
    1. Binary: Threat vs Safe
    2. Family: Broad attack category (9 classes)
    3. Subfamily/Technique: Specific attack type (22 techniques)
    4. Severity: ML-predicted severity (5 levels) - NEW
    5. Harm Types: Multilabel harm categories (10 types) - NEW

    Attributes:
        binary_threat_score: Probability that text is a threat (0.0-1.0)
        binary_safe_score: Probability that text is safe (0.0-1.0)
        family_confidence: Confidence in predicted family (0.0-1.0)
        subfamily_confidence: Confidence in predicted technique (0.0-1.0)
        binary_proba: Full binary probability distribution [safe, threat]
        family_proba: Full family probability distribution
        subfamily_proba: Full technique probability distribution
        family_name: Predicted family name
        subfamily_name: Predicted technique name
        severity_confidence: Confidence in severity prediction (NEW)
        severity_proba: Severity probability distribution (NEW)
        severity_name: Predicted severity name (NEW)
        harm_types_active_count: Number of active harm types (NEW)
        harm_types_max_confidence: Max confidence across harm types (NEW)
        harm_types_names: List of active harm type names (NEW)

    Example:
        >>> score = ThreatScore(
        ...     binary_threat_score=0.95,
        ...     binary_safe_score=0.05,
        ...     family_confidence=0.85,
        ...     subfamily_confidence=0.72,
        ...     binary_proba=[0.05, 0.95],
        ...     family_proba=[0.1, 0.05, 0.02, 0.85, 0.01, ...],
        ...     subfamily_proba=[0.72, 0.15, 0.08, ...],
        ...     severity_confidence=0.88,
        ...     severity_name="high",
        ...     harm_types_active_count=2,
        ... )
    """
    binary_threat_score: float
    binary_safe_score: float
    family_confidence: float
    subfamily_confidence: float
    binary_proba: list[float]
    family_proba: list[float]
    subfamily_proba: list[float]
    family_name: str | None = None
    subfamily_name: str | None = None
    # NEW: Severity head signals
    severity_confidence: float = 0.0
    severity_proba: list[float] = field(default_factory=list)
    severity_name: str | None = None
    # NEW: Harm types signals (aggregated from multilabel)
    harm_types_active_count: int = 0
    harm_types_max_confidence: float = 0.0
    harm_types_names: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate score values."""
        # Validate binary scores
        if not 0.0 <= self.binary_threat_score <= 1.0:
            raise ValueError(f"binary_threat_score must be 0-1, got {self.binary_threat_score}")
        if not 0.0 <= self.binary_safe_score <= 1.0:
            raise ValueError(f"binary_safe_score must be 0-1, got {self.binary_safe_score}")

        # Validate confidence scores
        if not 0.0 <= self.family_confidence <= 1.0:
            raise ValueError(f"family_confidence must be 0-1, got {self.family_confidence}")
        if not 0.0 <= self.subfamily_confidence <= 1.0:
            raise ValueError(f"subfamily_confidence must be 0-1, got {self.subfamily_confidence}")
        if not 0.0 <= self.severity_confidence <= 1.0:
            raise ValueError(f"severity_confidence must be 0-1, got {self.severity_confidence}")
        if not 0.0 <= self.harm_types_max_confidence <= 1.0:
            raise ValueError(f"harm_types_max_confidence must be 0-1, got {self.harm_types_max_confidence}")

        # Validate probability distributions
        if len(self.binary_proba) < 2:
            raise ValueError(f"binary_proba must have at least 2 elements, got {len(self.binary_proba)}")
        if not all(0.0 <= p <= 1.0 for p in self.binary_proba):
            raise ValueError("All binary_proba values must be 0-1")

        if len(self.family_proba) < 2:
            raise ValueError(f"family_proba must have at least 2 elements, got {len(self.family_proba)}")
        if not all(0.0 <= p <= 1.0 for p in self.family_proba):
            raise ValueError("All family_proba values must be 0-1")

        # Allow empty subfamily_proba for backward compatibility
        if len(self.subfamily_proba) > 0 and not all(0.0 <= p <= 1.0 for p in self.subfamily_proba):
            raise ValueError("All subfamily_proba values must be 0-1")


@dataclass(frozen=True)
class ScoringResult:
    """Result of hierarchical threat scoring.

    Contains the final classification, recommended action, and all intermediate
    metrics used to make the decision. This provides full transparency for
    debugging and monitoring.

    Attributes:
        classification: Final threat level classification
        action: Recommended action to take
        risk_score: Risk score 0-100 (for display/logging)
        hierarchical_score: Combined confidence score (0.0-1.0)
        threat_score: Binary threat probability (0.0-1.0)
        family_confidence: Family prediction confidence (0.0-1.0)
        subfamily_confidence: Subfamily prediction confidence (0.0-1.0)
        is_consistent: True if confidence levels are consistent across hierarchy
        variance: Variance in confidence levels (measure of consistency)
        weak_margins_count: Number of weak decision margins (0-3)
        reason: Human-readable explanation of the classification decision
        metadata: Additional metadata (margins, mode, family/subfamily names, etc.)

    Example:
        >>> result = ScoringResult(
        ...     classification=ThreatLevel.HIGH_THREAT,
        ...     action=ActionType.BLOCK_ALERT,
        ...     risk_score=79.4,
        ...     hierarchical_score=0.794,
        ...     threat_score=0.9835,
        ...     family_confidence=0.554,
        ...     subfamily_confidence=0.439,
        ...     is_consistent=True,
        ...     variance=0.021,
        ...     weak_margins_count=0,
        ...     reason="Very high confidence (threat: 0.984, family: 0.554)",
        ...     metadata={"mode": "balanced", "family_name": "PI"}
        ... )
    """
    classification: ThreatLevel
    action: ActionType
    risk_score: float
    hierarchical_score: float
    threat_score: float
    family_confidence: float
    subfamily_confidence: float
    is_consistent: bool
    variance: float
    weak_margins_count: int
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate scoring result."""
        # Validate score ranges
        if not 0.0 <= self.risk_score <= 100.0:
            raise ValueError(f"risk_score must be 0-100, got {self.risk_score}")
        if not 0.0 <= self.hierarchical_score <= 1.0:
            raise ValueError(f"hierarchical_score must be 0-1, got {self.hierarchical_score}")
        if not 0.0 <= self.threat_score <= 1.0:
            raise ValueError(f"threat_score must be 0-1, got {self.threat_score}")
        if not 0.0 <= self.family_confidence <= 1.0:
            raise ValueError(f"family_confidence must be 0-1, got {self.family_confidence}")
        if not 0.0 <= self.subfamily_confidence <= 1.0:
            raise ValueError(f"subfamily_confidence must be 0-1, got {self.subfamily_confidence}")

        # Validate counts
        if not 0 <= self.weak_margins_count <= 3:
            raise ValueError(f"weak_margins_count must be 0-3, got {self.weak_margins_count}")

        # Validate variance
        if self.variance < 0.0:
            raise ValueError(f"variance must be non-negative, got {self.variance}")

    def to_dict(self) -> dict[str, Any]:
        """Convert result to JSON-serializable dictionary.

        Returns:
            Dictionary with all result fields, formatted for logging/API responses
        """
        return {
            'classification': self.classification.value,
            'action': self.action.value,
            'risk_score': round(self.risk_score, 2),
            'scores': {
                'threat': round(self.threat_score, 4),
                'family': round(self.family_confidence, 4),
                'subfamily': round(self.subfamily_confidence, 4),
                'hierarchical': round(self.hierarchical_score, 4)
            },
            'signals': {
                'is_consistent': self.is_consistent,
                'variance': round(self.variance, 4),
                'weak_margins_count': self.weak_margins_count
            },
            'reason': self.reason,
            'metadata': self.metadata
        }

    def to_summary(self) -> str:
        """Generate human-readable summary string.

        Returns:
            Summary like "THREAT (BLOCK): 79.4/100 risk - Confident threat detection"
        """
        return (
            f"{self.classification.value} ({self.action.value}): "
            f"{self.risk_score:.1f}/100 risk - {self.reason}"
        )


@dataclass(frozen=True)
class ScoringThresholds:
    """Threshold configuration for threat scoring.

    These thresholds define the decision boundaries for each threat level.
    Different modes (HIGH_SECURITY, BALANCED, LOW_FP) use different thresholds
    to achieve different trade-offs between false positives and false negatives.

    Attributes:
        safe: Threshold below which text is classified as SAFE (default: 0.5)
        fp_likely: Threshold for FP_LIKELY classification
        review: Threshold for REVIEW classification
        likely_threat: Threshold for LIKELY_THREAT classification (optional, None to disable)
        threat: Threshold for THREAT classification
        high_threat: Threshold for HIGH_THREAT classification
        inconsistency_threshold: Variance above which confidence is inconsistent (default: 0.05)
        weak_family: Family confidence below which is considered weak
        weak_subfamily: Subfamily confidence below which is considered weak

    Thresholds are data-driven based on analysis of 67 false positives.

    Example (BALANCED mode with LIKELY_THREAT):
        >>> thresholds = ScoringThresholds(
        ...     safe=0.5,
        ...     fp_likely=0.55,
        ...     review=0.70,
        ...     likely_threat=0.78,
        ...     threat=0.85,
        ...     high_threat=0.95,
        ...     inconsistency_threshold=0.05,
        ...     weak_family=0.4,
        ...     weak_subfamily=0.3
        ... )
    """
    safe: float
    fp_likely: float
    review: float
    likely_threat: float | None
    threat: float
    high_threat: float
    inconsistency_threshold: float
    weak_family: float
    weak_subfamily: float

    def __post_init__(self) -> None:
        """Validate thresholds."""
        # Validate all thresholds are in valid range
        thresholds = [
            ('safe', self.safe),
            ('fp_likely', self.fp_likely),
            ('review', self.review),
            ('threat', self.threat),
            ('high_threat', self.high_threat),
            ('weak_family', self.weak_family),
            ('weak_subfamily', self.weak_subfamily)
        ]

        for name, value in thresholds:
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} threshold must be 0-1, got {value}")

        # Validate likely_threat if provided
        if self.likely_threat is not None:
            if not 0.0 <= self.likely_threat <= 1.0:
                raise ValueError(f"likely_threat threshold must be 0-1, got {self.likely_threat}")

        if not 0.0 <= self.inconsistency_threshold <= 1.0:
            raise ValueError(f"inconsistency_threshold must be 0-1, got {self.inconsistency_threshold}")

        # Validate threshold ordering
        # If likely_threat is enabled: safe < fp_likely < review < likely_threat < threat < high_threat
        # If likely_threat is disabled: safe < fp_likely < review < threat < high_threat
        if self.likely_threat is not None:
            if not (self.safe < self.fp_likely < self.review < self.likely_threat < self.threat < self.high_threat):
                raise ValueError(
                    "Thresholds must be ordered: safe < fp_likely < review < likely_threat < threat < high_threat. "
                    f"Got: {self.safe} < {self.fp_likely} < {self.review} < {self.likely_threat} < {self.threat} < {self.high_threat}"
                )
        else:
            if not (self.safe < self.fp_likely < self.review < self.threat < self.high_threat):
                raise ValueError(
                    "Thresholds must be ordered: safe < fp_likely < review < threat < high_threat. "
                    f"Got: {self.safe} < {self.fp_likely} < {self.review} < {self.threat} < {self.high_threat}"
                )

    @classmethod
    def for_mode(cls, mode: ScoringMode) -> "ScoringThresholds":
        """Create thresholds for a specific scoring mode.

        These thresholds are data-driven based on analysis of 67 false positives
        and validated against production data.

        Args:
            mode: Scoring mode (HIGH_SECURITY, BALANCED, or LOW_FP)

        Returns:
            ScoringThresholds configured for the specified mode

        Example:
            >>> thresholds = ScoringThresholds.for_mode(ScoringMode.BALANCED)
        """
        if mode == ScoringMode.HIGH_SECURITY:
            return cls(
                safe=0.5,
                fp_likely=0.55,
                review=0.60,
                likely_threat=0.65,  # Enabled: aggressive threshold for high security
                threat=0.70,
                high_threat=0.85,
                inconsistency_threshold=0.05,
                weak_family=0.5,
                weak_subfamily=0.4
            )
        elif mode == ScoringMode.BALANCED:
            return cls(
                safe=0.5,
                fp_likely=0.55,
                review=0.70,  # Adjusted from 0.68 to make room for likely_threat
                likely_threat=0.78,  # Enabled: balanced threshold (Option 2)
                threat=0.85,  # Adjusted from 0.78 to create proper spacing
                high_threat=0.95,
                inconsistency_threshold=0.05,
                weak_family=0.4,
                weak_subfamily=0.3
            )
        elif mode == ScoringMode.LOW_FP:
            return cls(
                safe=0.5,
                fp_likely=0.60,
                review=0.80,
                likely_threat=0.85,  # Enabled: conservative threshold for low FP
                threat=0.90,
                high_threat=0.97,
                inconsistency_threshold=0.05,
                weak_family=0.3,
                weak_subfamily=0.2
            )
        else:
            raise ValueError(f"Unknown scoring mode: {mode}")
