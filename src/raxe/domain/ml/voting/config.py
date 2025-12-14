"""Voting configuration - Thresholds and weights for ensemble voting.

This module contains ONLY pure configuration data - no I/O operations.
All classes are immutable value objects representing voting configuration.

Configuration Hierarchy:
- HeadThresholds: Per-head voting thresholds
- VotingWeights: Per-head vote weights
- DecisionThresholds: Ensemble decision thresholds
- VotingConfig: Complete voting configuration
- VotingPreset: Named preset configurations (balanced, high_security, low_fp)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class BinaryHeadThresholds:
    """Thresholds for the binary (is_threat) classifier head.

    Voting rules:
    - THREAT if threat_probability >= threat_threshold
    - SAFE if threat_probability < safe_threshold
    - ABSTAIN otherwise (gray zone)

    Attributes:
        threat_threshold: Minimum probability to vote THREAT (default: 0.65)
        safe_threshold: Maximum probability to vote SAFE (default: 0.40)
    """

    threat_threshold: float = 0.65
    safe_threshold: float = 0.40

    def __post_init__(self) -> None:
        """Validate thresholds."""
        if not 0.0 <= self.safe_threshold <= 1.0:
            raise ValueError(f"safe_threshold must be 0-1, got {self.safe_threshold}")
        if not 0.0 <= self.threat_threshold <= 1.0:
            raise ValueError(f"threat_threshold must be 0-1, got {self.threat_threshold}")
        if self.safe_threshold >= self.threat_threshold:
            raise ValueError(
                f"safe_threshold ({self.safe_threshold}) must be < threat_threshold ({self.threat_threshold})"
            )


@dataclass(frozen=True)
class FamilyHeadThresholds:
    """Thresholds for the family classifier head.

    Voting rules:
    - THREAT if family != benign AND confidence >= threat_confidence
    - SAFE if family == benign OR confidence < safe_confidence
    - ABSTAIN otherwise

    Attributes:
        threat_confidence: Minimum confidence to vote THREAT for non-benign (default: 0.55)
        safe_confidence: Maximum confidence to vote SAFE (default: 0.35)
    """

    threat_confidence: float = 0.55
    safe_confidence: float = 0.35

    def __post_init__(self) -> None:
        """Validate thresholds."""
        if not 0.0 <= self.safe_confidence <= 1.0:
            raise ValueError(f"safe_confidence must be 0-1, got {self.safe_confidence}")
        if not 0.0 <= self.threat_confidence <= 1.0:
            raise ValueError(f"threat_confidence must be 0-1, got {self.threat_confidence}")


@dataclass(frozen=True)
class SeverityHeadThresholds:
    """Thresholds for the severity classifier head.

    Voting rules:
    - THREAT if severity in (low, medium, high, critical)
    - SAFE if severity == none
    - No abstain - severity always has an opinion

    Note: Severity head has the highest weight (1.5) because it directly
    indicates threat severity and has strong signal quality.

    Attributes:
        threat_severities: Severities that indicate threat (default: low, medium, high, critical)
        safe_severities: Severities that indicate safe (default: none)
    """

    threat_severities: tuple[str, ...] = ("low", "medium", "high", "critical")
    safe_severities: tuple[str, ...] = ("none",)


@dataclass(frozen=True)
class TechniqueHeadThresholds:
    """Thresholds for the primary technique classifier head.

    Voting rules:
    - THREAT if technique != none AND confidence >= threat_confidence
    - SAFE if technique == none OR confidence < safe_confidence
    - ABSTAIN otherwise

    Attributes:
        threat_confidence: Minimum confidence to vote THREAT for attack technique (default: 0.50)
        safe_confidence: Maximum confidence to vote SAFE (default: 0.30)
        safe_techniques: Techniques that always indicate safe (default: none)
    """

    threat_confidence: float = 0.50
    safe_confidence: float = 0.30
    safe_techniques: tuple[str, ...] = ("none",)

    def __post_init__(self) -> None:
        """Validate thresholds."""
        if not 0.0 <= self.safe_confidence <= 1.0:
            raise ValueError(f"safe_confidence must be 0-1, got {self.safe_confidence}")
        if not 0.0 <= self.threat_confidence <= 1.0:
            raise ValueError(f"threat_confidence must be 0-1, got {self.threat_confidence}")


@dataclass(frozen=True)
class HarmHeadThresholds:
    """Thresholds for the harm types (multilabel) classifier head.

    Voting rules:
    - THREAT if max_probability >= threat_threshold
    - SAFE if max_probability < safe_threshold
    - ABSTAIN otherwise

    Note: Harm head has the lowest weight (0.8) because it can trigger
    false positives on benign content discussing sensitive topics.

    Attributes:
        threat_threshold: Max probability to vote THREAT (default: 0.92)
        safe_threshold: Max probability to vote SAFE (default: 0.50)
    """

    threat_threshold: float = 0.92
    safe_threshold: float = 0.50

    def __post_init__(self) -> None:
        """Validate thresholds."""
        if not 0.0 <= self.safe_threshold <= 1.0:
            raise ValueError(f"safe_threshold must be 0-1, got {self.safe_threshold}")
        if not 0.0 <= self.threat_threshold <= 1.0:
            raise ValueError(f"threat_threshold must be 0-1, got {self.threat_threshold}")


@dataclass(frozen=True)
class HeadWeights:
    """Vote weights for each classifier head.

    Weights determine how much each head's vote contributes to the
    weighted ratio calculation. Higher weight = more influence.

    Default weights (based on signal quality analysis):
    - binary: 1.0 (baseline, direct threat probability)
    - family: 1.2 (strong signal for threat categorization)
    - severity: 1.5 (HIGHEST - direct severity indicator)
    - technique: 1.0 (good signal for specific attacks)
    - harm: 0.8 (LOWEST - prone to FPs on sensitive topics)

    Attributes:
        binary: Weight for binary (is_threat) head
        family: Weight for family head
        severity: Weight for severity head
        technique: Weight for technique head
        harm: Weight for harm types head
    """

    binary: float = 1.0
    family: float = 1.2
    severity: float = 1.5
    technique: float = 1.0
    harm: float = 0.8

    def __post_init__(self) -> None:
        """Validate weights."""
        for name, weight in [
            ("binary", self.binary),
            ("family", self.family),
            ("severity", self.severity),
            ("technique", self.technique),
            ("harm", self.harm),
        ]:
            if weight < 0:
                raise ValueError(f"{name} weight must be non-negative, got {weight}")

    def get_weight(self, head_name: str) -> float:
        """Get weight for a specific head.

        Args:
            head_name: Name of the head (binary, family, severity, technique, harm)

        Returns:
            Weight for the specified head

        Raises:
            ValueError: If head_name is not recognized
        """
        weights = {
            "binary": self.binary,
            "family": self.family,
            "severity": self.severity,
            "technique": self.technique,
            "harm": self.harm,
        }
        if head_name not in weights:
            raise ValueError(f"Unknown head: {head_name}")
        return weights[head_name]

    @property
    def total_weight(self) -> float:
        """Total weight across all heads."""
        return self.binary + self.family + self.severity + self.technique + self.harm


@dataclass(frozen=True)
class DecisionThresholds:
    """Thresholds for ensemble decision rules.

    These thresholds control when each decision rule triggers:

    1. High-confidence override: Any head THREAT + confidence >= 85% + 1 other THREAT
    2. Severity veto: severity="none" -> need 3+ other THREAT votes to override
    3. Min votes: Need >= min_threat_votes to classify as THREAT
    4. Weighted ratio: threat_weight / safe_weight >= threat_ratio
    5. Review zone: weighted ratio in [review_ratio_min, threat_ratio)

    Attributes:
        high_confidence_threshold: Confidence for high-confidence override (default: 0.85)
        min_threat_votes: Minimum THREAT votes for THREAT decision (default: 2)
        severity_veto_override_votes: THREAT votes needed to override severity veto (default: 3)
        threat_ratio: Minimum weighted ratio for THREAT (default: 1.3)
        review_ratio_min: Minimum weighted ratio for REVIEW (default: 1.0)
    """

    high_confidence_threshold: float = 0.85
    min_threat_votes: int = 2
    severity_veto_override_votes: int = 3
    threat_ratio: float = 1.3
    review_ratio_min: float = 1.0

    def __post_init__(self) -> None:
        """Validate thresholds."""
        if not 0.0 <= self.high_confidence_threshold <= 1.0:
            raise ValueError(
                f"high_confidence_threshold must be 0-1, got {self.high_confidence_threshold}"
            )
        if self.min_threat_votes < 1:
            raise ValueError(
                f"min_threat_votes must be >= 1, got {self.min_threat_votes}"
            )
        if self.severity_veto_override_votes < 1:
            raise ValueError(
                f"severity_veto_override_votes must be >= 1, got {self.severity_veto_override_votes}"
            )
        if self.threat_ratio <= 0:
            raise ValueError(f"threat_ratio must be > 0, got {self.threat_ratio}")
        if self.review_ratio_min < 0:
            raise ValueError(f"review_ratio_min must be >= 0, got {self.review_ratio_min}")
        if self.review_ratio_min >= self.threat_ratio:
            raise ValueError(
                f"review_ratio_min ({self.review_ratio_min}) must be < threat_ratio ({self.threat_ratio})"
            )


@dataclass(frozen=True)
class VotingConfig:
    """Complete voting configuration.

    Combines all threshold and weight configurations into a single
    immutable configuration object.

    Attributes:
        name: Configuration name (e.g., "balanced", "high_security")
        binary: Binary head thresholds
        family: Family head thresholds
        severity: Severity head thresholds
        technique: Technique head thresholds
        harm: Harm head thresholds
        weights: Per-head vote weights
        decision: Ensemble decision thresholds
    """

    name: str = "balanced"
    binary: BinaryHeadThresholds = field(default_factory=BinaryHeadThresholds)
    family: FamilyHeadThresholds = field(default_factory=FamilyHeadThresholds)
    severity: SeverityHeadThresholds = field(default_factory=SeverityHeadThresholds)
    technique: TechniqueHeadThresholds = field(default_factory=TechniqueHeadThresholds)
    harm: HarmHeadThresholds = field(default_factory=HarmHeadThresholds)
    weights: HeadWeights = field(default_factory=HeadWeights)
    decision: DecisionThresholds = field(default_factory=DecisionThresholds)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "name": self.name,
            "binary": {
                "threat_threshold": self.binary.threat_threshold,
                "safe_threshold": self.binary.safe_threshold,
            },
            "family": {
                "threat_confidence": self.family.threat_confidence,
                "safe_confidence": self.family.safe_confidence,
            },
            "severity": {
                "threat_severities": list(self.severity.threat_severities),
                "safe_severities": list(self.severity.safe_severities),
            },
            "technique": {
                "threat_confidence": self.technique.threat_confidence,
                "safe_confidence": self.technique.safe_confidence,
                "safe_techniques": list(self.technique.safe_techniques),
            },
            "harm": {
                "threat_threshold": self.harm.threat_threshold,
                "safe_threshold": self.harm.safe_threshold,
            },
            "weights": {
                "binary": self.weights.binary,
                "family": self.weights.family,
                "severity": self.weights.severity,
                "technique": self.weights.technique,
                "harm": self.weights.harm,
            },
            "decision": {
                "high_confidence_threshold": self.decision.high_confidence_threshold,
                "min_threat_votes": self.decision.min_threat_votes,
                "severity_veto_override_votes": self.decision.severity_veto_override_votes,
                "threat_ratio": self.decision.threat_ratio,
                "review_ratio_min": self.decision.review_ratio_min,
            },
        }


class VotingPreset(str, Enum):
    """Named preset configurations for the voting engine.

    Presets provide pre-configured threshold combinations for common use cases:
    - BALANCED: Default, balances false positives and false negatives
    - HIGH_SECURITY: Lower thresholds, more aggressive blocking
    - LOW_FP: Higher thresholds, fewer false positives
    - HARM_FOCUSED: Sensitive to violence/harm content, lower harm thresholds
    """

    BALANCED = "balanced"
    HIGH_SECURITY = "high_security"
    LOW_FP = "low_fp"
    HARM_FOCUSED = "harm_focused"


def get_voting_config(preset: VotingPreset | str = VotingPreset.BALANCED) -> VotingConfig:
    """Get voting configuration for a preset.

    Args:
        preset: Voting preset name or enum

    Returns:
        VotingConfig for the specified preset

    Raises:
        ValueError: If preset is not recognized

    Examples:
        >>> config = get_voting_config(VotingPreset.BALANCED)
        >>> config.name
        'balanced'

        >>> config = get_voting_config("high_security")
        >>> config.decision.min_threat_votes
        1
    """
    # Normalize preset to string
    if isinstance(preset, VotingPreset):
        preset_name = preset.value
    else:
        preset_name = preset.lower()

    if preset_name == "balanced":
        return _get_balanced_config()
    elif preset_name == "high_security":
        return _get_high_security_config()
    elif preset_name == "low_fp":
        return _get_low_fp_config()
    elif preset_name == "harm_focused":
        return _get_harm_focused_config()
    else:
        raise ValueError(
            f"Unknown preset: {preset}. Valid presets: balanced, high_security, low_fp, harm_focused"
        )


def _get_balanced_config() -> VotingConfig:
    """Get the balanced (default) voting configuration.

    This configuration balances false positives and false negatives,
    suitable for most production use cases.
    """
    return VotingConfig(
        name="balanced",
        binary=BinaryHeadThresholds(
            threat_threshold=0.65,
            safe_threshold=0.40,
        ),
        family=FamilyHeadThresholds(
            threat_confidence=0.55,
            safe_confidence=0.35,
        ),
        severity=SeverityHeadThresholds(
            threat_severities=("low", "medium", "high", "critical"),
            safe_severities=("none",),
        ),
        technique=TechniqueHeadThresholds(
            threat_confidence=0.50,
            safe_confidence=0.30,
        ),
        harm=HarmHeadThresholds(
            threat_threshold=0.92,
            safe_threshold=0.50,
        ),
        weights=HeadWeights(
            binary=1.0,
            family=1.2,
            severity=1.5,
            technique=1.0,
            harm=0.8,
        ),
        decision=DecisionThresholds(
            high_confidence_threshold=0.85,
            min_threat_votes=2,
            severity_veto_override_votes=3,
            threat_ratio=1.3,
            review_ratio_min=1.0,
        ),
    )


def _get_high_security_config() -> VotingConfig:
    """Get the high security voting configuration.

    This configuration has lower thresholds and is more aggressive
    in blocking potential threats. Suitable for high-risk environments
    where false positives are acceptable to minimize false negatives.
    """
    return VotingConfig(
        name="high_security",
        binary=BinaryHeadThresholds(
            threat_threshold=0.50,  # Lower threshold
            safe_threshold=0.30,
        ),
        family=FamilyHeadThresholds(
            threat_confidence=0.40,  # Lower confidence required
            safe_confidence=0.25,
        ),
        severity=SeverityHeadThresholds(
            threat_severities=("low", "medium", "high", "critical"),
            safe_severities=("none",),
        ),
        technique=TechniqueHeadThresholds(
            threat_confidence=0.35,  # Lower confidence required
            safe_confidence=0.20,
        ),
        harm=HarmHeadThresholds(
            threat_threshold=0.80,  # Lower threshold
            safe_threshold=0.40,
        ),
        weights=HeadWeights(
            binary=1.0,
            family=1.3,  # Slightly higher family weight
            severity=1.6,  # Higher severity weight
            technique=1.1,
            harm=0.9,
        ),
        decision=DecisionThresholds(
            high_confidence_threshold=0.75,  # Lower override threshold
            min_threat_votes=1,  # Only 1 vote needed
            severity_veto_override_votes=2,
            threat_ratio=1.1,  # Lower ratio needed
            review_ratio_min=0.8,
        ),
    )


def _get_low_fp_config() -> VotingConfig:
    """Get the low false positive voting configuration.

    This configuration has higher thresholds and is more conservative
    in blocking. Suitable for environments where false positives
    are costly and must be minimized.
    """
    return VotingConfig(
        name="low_fp",
        binary=BinaryHeadThresholds(
            threat_threshold=0.80,  # Higher threshold
            safe_threshold=0.50,
        ),
        family=FamilyHeadThresholds(
            threat_confidence=0.70,  # Higher confidence required
            safe_confidence=0.45,
        ),
        severity=SeverityHeadThresholds(
            threat_severities=("medium", "high", "critical"),  # Exclude low severity
            safe_severities=("none", "low"),  # Low severity is considered safe
        ),
        technique=TechniqueHeadThresholds(
            threat_confidence=0.65,  # Higher confidence required
            safe_confidence=0.40,
        ),
        harm=HarmHeadThresholds(
            threat_threshold=0.95,  # Very high threshold
            safe_threshold=0.60,
        ),
        weights=HeadWeights(
            binary=1.2,  # Higher binary weight (most reliable)
            family=1.0,
            severity=1.4,
            technique=0.9,
            harm=0.6,  # Lower harm weight (most prone to FPs)
        ),
        decision=DecisionThresholds(
            high_confidence_threshold=0.90,  # Higher override threshold
            min_threat_votes=3,  # Require more votes
            severity_veto_override_votes=4,
            threat_ratio=1.5,  # Higher ratio needed
            review_ratio_min=1.2,
        ),
    )


def _get_harm_focused_config() -> VotingConfig:
    """Get the harm-focused voting configuration.

    This configuration is specifically tuned for detecting violence, weapons,
    self-harm, and other harmful content. It significantly lowers the harm
    head thresholds and increases the harm head weight to make it the
    dominant signal for harm-related threats.

    Key differences from balanced:
    - Harm head threshold: 0.50 (vs 0.92) - much more sensitive
    - Harm head weight: 3.0 (vs 0.8) - harm dominates other heads
    - Very low threat_ratio: 0.25 - harm vote alone can trigger threat
    - Binary/family/technique have higher safe thresholds - more abstains

    The key insight: to allow harm to override other heads, we need:
    1. Very high harm weight (3.0)
    2. Very low threat_ratio (0.25) so harm alone can win
    3. Higher safe thresholds on other heads so they abstain more

    Use cases:
    - Applications handling user-generated content with violence concerns
    - Platforms where self-harm/suicide content is a major risk
    - Environments processing weapons/explosive-related queries

    Note: This preset WILL have higher false positive rates on benign
    content discussing sensitive topics (news, education, etc.).
    Review carefully before production use.
    """
    return VotingConfig(
        name="harm_focused",
        binary=BinaryHeadThresholds(
            threat_threshold=0.50,
            safe_threshold=0.45,  # Higher - more abstains
        ),
        family=FamilyHeadThresholds(
            threat_confidence=0.45,
            safe_confidence=0.40,  # Higher - more abstains
        ),
        severity=SeverityHeadThresholds(
            threat_severities=("low", "medium", "high", "critical"),
            safe_severities=("none",),
        ),
        technique=TechniqueHeadThresholds(
            threat_confidence=0.45,
            safe_confidence=0.40,  # Higher - more abstains
        ),
        harm=HarmHeadThresholds(
            threat_threshold=0.50,  # Much lower! (was 0.92)
            safe_threshold=0.40,    # Still fairly sensitive
        ),
        weights=HeadWeights(
            binary=0.8,   # Lower weight
            family=0.8,   # Lower weight
            severity=1.0, # Normal weight
            technique=0.6,# Lower weight
            harm=3.0,     # DOMINANT weight - harm is 3x other heads
        ),
        decision=DecisionThresholds(
            high_confidence_threshold=0.60,  # Lower for harm override
            min_threat_votes=1,  # Single vote can trigger
            severity_veto_override_votes=1,  # Harm can override severity=none
            threat_ratio=0.25,  # Very low - harm alone can win
            review_ratio_min=0.15,  # Even lower for review zone
        ),
    )
