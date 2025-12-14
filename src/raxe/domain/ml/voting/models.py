"""Voting domain models - Pure data structures for ensemble voting.

This module contains ONLY pure domain models - no I/O operations.
All classes are immutable value objects representing voting states and results.

Model Hierarchy:
- Vote: Three-way vote enum (SAFE, ABSTAIN, THREAT)
- HeadVoteDetail: Detailed vote from a single classifier head
- VotingResult: Complete voting engine output with full transparency
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Vote(str, Enum):
    """Three-way vote classification.

    Each classifier head casts one of these votes:
    - SAFE: Head is confident the input is benign
    - ABSTAIN: Head is uncertain (in the "gray zone")
    - THREAT: Head is confident the input is a threat
    """

    SAFE = "safe"
    ABSTAIN = "abstain"
    THREAT = "threat"


class Decision(str, Enum):
    """Final three-way classification decision.

    The ensemble produces one of these decisions:
    - SAFE: Consensus that input is benign, allow with confidence
    - REVIEW: Uncertain, recommend human review
    - THREAT: Consensus that input is malicious, recommend block
    """

    SAFE = "safe"
    REVIEW = "review"
    THREAT = "threat"


@dataclass(frozen=True)
class HeadVoteDetail:
    """Detailed vote from a single classifier head.

    Provides full transparency into each head's voting decision,
    including the raw probabilities and thresholds used.

    Attributes:
        head_name: Name of the classifier head (binary, family, severity, technique, harm)
        vote: The vote cast by this head
        confidence: Confidence in the vote (0.0 to 1.0)
        weight: Weight applied to this head's vote
        raw_probability: Raw model output probability
        threshold_used: Threshold that triggered this vote
        prediction: The head's prediction label (e.g., "jailbreak", "high")
        rationale: Human-readable explanation for the vote
    """

    head_name: str
    vote: Vote
    confidence: float
    weight: float
    raw_probability: float
    threshold_used: float
    prediction: str
    rationale: str

    def __post_init__(self) -> None:
        """Validate head vote detail."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0-1, got {self.confidence}")
        if not 0.0 <= self.raw_probability <= 1.0:
            raise ValueError(f"raw_probability must be 0-1, got {self.raw_probability}")
        if self.weight < 0:
            raise ValueError(f"weight must be non-negative, got {self.weight}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "head_name": self.head_name,
            "vote": self.vote.value,
            "confidence": self.confidence,
            "weight": self.weight,
            "raw_probability": self.raw_probability,
            "threshold_used": self.threshold_used,
            "prediction": self.prediction,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class VotingResult:
    """Complete result from the ensemble voting engine.

    Provides full transparency into the voting process, including
    per-head votes, aggregated scores, and the decision rationale.

    Attributes:
        decision: Final classification (SAFE, REVIEW, THREAT)
        confidence: Overall confidence in the decision (0.0 to 1.0)
        preset_used: Name of the voting preset that was applied
        per_head_votes: Detailed vote breakdown for each head
        aggregated_scores: Weighted vote totals {"safe": X, "review": Y, "threat": Z}
        decision_rule_triggered: Which decision rule made the final call
        threat_vote_count: Number of heads that voted THREAT
        safe_vote_count: Number of heads that voted SAFE
        abstain_vote_count: Number of heads that abstained
        weighted_threat_score: Total weighted THREAT votes
        weighted_safe_score: Total weighted SAFE votes
    """

    decision: Decision
    confidence: float
    preset_used: str
    per_head_votes: dict[str, HeadVoteDetail]
    aggregated_scores: dict[str, float]
    decision_rule_triggered: str
    threat_vote_count: int
    safe_vote_count: int
    abstain_vote_count: int
    weighted_threat_score: float = 0.0
    weighted_safe_score: float = 0.0

    def __post_init__(self) -> None:
        """Validate voting result."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0-1, got {self.confidence}")
        if self.threat_vote_count < 0:
            raise ValueError(f"threat_vote_count must be non-negative")
        if self.safe_vote_count < 0:
            raise ValueError(f"safe_vote_count must be non-negative")
        if self.abstain_vote_count < 0:
            raise ValueError(f"abstain_vote_count must be non-negative")

    @property
    def is_threat(self) -> bool:
        """True if the decision is THREAT."""
        return self.decision == Decision.THREAT

    @property
    def is_safe(self) -> bool:
        """True if the decision is SAFE."""
        return self.decision == Decision.SAFE

    @property
    def is_review(self) -> bool:
        """True if the decision is REVIEW (uncertain)."""
        return self.decision == Decision.REVIEW

    @property
    def total_votes(self) -> int:
        """Total number of votes cast (excluding abstentions for ratio calc)."""
        return self.threat_vote_count + self.safe_vote_count

    @property
    def threat_ratio(self) -> float:
        """Ratio of THREAT votes to total votes (excluding abstentions)."""
        if self.total_votes == 0:
            return 0.0
        return self.threat_vote_count / self.total_votes

    @property
    def weighted_ratio(self) -> float:
        """Ratio of weighted THREAT votes to weighted SAFE votes."""
        if self.weighted_safe_score == 0:
            return float("inf") if self.weighted_threat_score > 0 else 0.0
        return self.weighted_threat_score / self.weighted_safe_score

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        # Handle infinity for JSON serialization (JSON doesn't support Infinity)
        ratio = self.weighted_ratio
        if ratio == float("inf"):
            ratio = 999.0  # Sentinel value for "infinitely more threat than safe"

        return {
            "decision": self.decision.value,
            "confidence": self.confidence,
            "preset_used": self.preset_used,
            "per_head_votes": {
                name: vote.to_dict() for name, vote in self.per_head_votes.items()
            },
            "aggregated_scores": self.aggregated_scores,
            "decision_rule_triggered": self.decision_rule_triggered,
            "threat_vote_count": self.threat_vote_count,
            "safe_vote_count": self.safe_vote_count,
            "abstain_vote_count": self.abstain_vote_count,
            "weighted_threat_score": self.weighted_threat_score,
            "weighted_safe_score": self.weighted_safe_score,
            "weighted_ratio": ratio,
        }


@dataclass(frozen=True)
class HeadOutput:
    """Raw output from a classifier head before voting.

    This is an intermediate data structure used to pass head outputs
    to the voting engine without coupling to GemmaClassificationResult.

    Attributes:
        head_name: Name of the head (binary, family, severity, technique, harm)
        prediction: Predicted class label
        confidence: Confidence in the prediction
        probabilities: Full probability distribution (optional)
        is_threat_indicator: Whether this prediction indicates a threat
    """

    head_name: str
    prediction: str
    confidence: float
    probabilities: tuple[float, ...] | None = None
    is_threat_indicator: bool = False

    def __post_init__(self) -> None:
        """Validate head output."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0-1, got {self.confidence}")
