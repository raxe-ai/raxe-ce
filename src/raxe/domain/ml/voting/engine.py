"""Voting Engine - Ensemble decision logic for 5-head classifier.

This module contains the VotingEngine class which implements the weighted
voting and decision rules for the ensemble. Pure domain logic - no I/O.

Decision Rules (in priority order):
1. High-confidence override: Any head THREAT + conf >= 85% + 1 other THREAT -> THREAT
2. Severity veto: severity="none" -> need 3+ other THREAT votes to override -> else SAFE
3. Min votes: Need >= 2 THREAT votes
4. Weighted ratio: threat_weight / safe_weight >= 1.3
5. Tie-breaker: Ties favor SAFE (reduce FPs)
"""

from dataclasses import dataclass
from typing import Any

from raxe.domain.ml.voting.config import (
    VotingConfig,
    VotingPreset,
    get_voting_config,
)
from raxe.domain.ml.voting.head_voters import (
    vote_binary,
    vote_family,
    vote_harm,
    vote_severity,
    vote_technique,
)
from raxe.domain.ml.voting.models import (
    Decision,
    HeadVoteDetail,
    Vote,
    VotingResult,
)


@dataclass
class HeadOutputs:
    """Container for all 5-head classifier outputs.

    This is an intermediate data structure for passing head outputs
    to the voting engine.

    Attributes:
        binary_threat_prob: Binary head threat probability
        binary_safe_prob: Binary head safe probability
        family_prediction: Family head prediction label
        family_confidence: Family head confidence
        severity_prediction: Severity head prediction label
        severity_confidence: Severity head confidence
        technique_prediction: Technique head prediction label (optional)
        technique_confidence: Technique head confidence
        harm_max_probability: Harm head max probability
        harm_active_labels: Harm head active label list
    """

    binary_threat_prob: float
    binary_safe_prob: float
    family_prediction: str
    family_confidence: float
    severity_prediction: str
    severity_confidence: float
    technique_prediction: str | None
    technique_confidence: float
    harm_max_probability: float
    harm_active_labels: list[str]


class VotingEngine:
    """Ensemble voting engine for 5-head classifier.

    Implements weighted voting with configurable thresholds and
    decision rules for combining 5 classifier head outputs into
    a final SAFE/REVIEW/THREAT decision.

    The engine supports three presets:
    - balanced: Default, balances false positives and false negatives
    - high_security: More aggressive blocking, fewer false negatives
    - low_fp: More conservative, fewer false positives

    Decision Rules (in priority order):
    1. High-confidence override: Any head THREAT + conf >= 85% + 1 other THREAT
    2. Severity veto: severity="none" + no override -> SAFE
    3. Min votes: Need >= min_threat_votes
    4. Weighted ratio: threat_weight / safe_weight >= threat_ratio
    5. Review zone: ratio in [review_ratio_min, threat_ratio) -> REVIEW
    6. Tie-breaker: Ties favor SAFE

    Example:
        >>> engine = VotingEngine(preset="balanced")
        >>> result = engine.vote(head_outputs)
        >>> result.decision
        <Decision.THREAT: 'threat'>
    """

    def __init__(
        self,
        preset: VotingPreset | str = VotingPreset.BALANCED,
        config: VotingConfig | None = None,
    ):
        """Initialize the voting engine.

        Args:
            preset: Voting preset name or enum (default: balanced)
            config: Custom VotingConfig (overrides preset if provided)
        """
        if config is not None:
            self._config = config
        else:
            self._config = get_voting_config(preset)

    @property
    def config(self) -> VotingConfig:
        """Get the current voting configuration."""
        return self._config

    @property
    def preset_name(self) -> str:
        """Get the name of the current preset."""
        return self._config.name

    def vote(self, outputs: HeadOutputs) -> VotingResult:
        """Run the voting engine on head outputs.

        Collects votes from all 5 heads, applies weights, and runs
        decision rules to produce a final SAFE/REVIEW/THREAT decision.

        Args:
            outputs: Container with all head outputs

        Returns:
            VotingResult with full transparency into the voting process

        Example:
            >>> outputs = HeadOutputs(
            ...     binary_threat_prob=0.75,
            ...     binary_safe_prob=0.25,
            ...     family_prediction="jailbreak",
            ...     family_confidence=0.80,
            ...     severity_prediction="high",
            ...     severity_confidence=0.85,
            ...     technique_prediction="instruction_override",
            ...     technique_confidence=0.70,
            ...     harm_max_probability=0.60,
            ...     harm_active_labels=[],
            ... )
            >>> result = engine.vote(outputs)
            >>> result.decision
            <Decision.THREAT: 'threat'>
        """
        cfg = self._config

        # Step 1: Collect votes from all heads
        votes: dict[str, HeadVoteDetail] = {}

        # Binary head
        votes["binary"] = vote_binary(
            threat_probability=outputs.binary_threat_prob,
            safe_probability=outputs.binary_safe_prob,
            thresholds=cfg.binary,
            weight=cfg.weights.binary,
        )

        # Family head
        votes["family"] = vote_family(
            family_prediction=outputs.family_prediction,
            family_confidence=outputs.family_confidence,
            thresholds=cfg.family,
            weight=cfg.weights.family,
        )

        # Severity head
        votes["severity"] = vote_severity(
            severity_prediction=outputs.severity_prediction,
            severity_confidence=outputs.severity_confidence,
            thresholds=cfg.severity,
            weight=cfg.weights.severity,
        )

        # Technique head
        votes["technique"] = vote_technique(
            technique_prediction=outputs.technique_prediction,
            technique_confidence=outputs.technique_confidence,
            thresholds=cfg.technique,
            weight=cfg.weights.technique,
        )

        # Harm head
        votes["harm"] = vote_harm(
            max_probability=outputs.harm_max_probability,
            active_labels=outputs.harm_active_labels,
            thresholds=cfg.harm,
            weight=cfg.weights.harm,
        )

        # Step 2: Calculate vote counts and weighted scores
        threat_count = sum(1 for v in votes.values() if v.vote == Vote.THREAT)
        safe_count = sum(1 for v in votes.values() if v.vote == Vote.SAFE)
        abstain_count = sum(1 for v in votes.values() if v.vote == Vote.ABSTAIN)

        weighted_threat = sum(v.weight for v in votes.values() if v.vote == Vote.THREAT)
        weighted_safe = sum(v.weight for v in votes.values() if v.vote == Vote.SAFE)

        # Calculate weighted ratio (avoid division by zero)
        if weighted_safe > 0:
            weighted_ratio = weighted_threat / weighted_safe
        elif weighted_threat > 0:
            weighted_ratio = float("inf")
        else:
            weighted_ratio = 0.0

        # Step 3: Apply decision rules in priority order
        decision, rule_triggered, confidence = self._apply_decision_rules(
            votes=votes,
            threat_count=threat_count,
            safe_count=safe_count,
            weighted_threat=weighted_threat,
            weighted_safe=weighted_safe,
            weighted_ratio=weighted_ratio,
        )

        # Step 4: Build aggregated scores for transparency
        aggregated_scores = {
            "safe": weighted_safe,
            "threat": weighted_threat,
            "ratio": weighted_ratio if weighted_ratio != float("inf") else 999.0,
        }

        return VotingResult(
            decision=decision,
            confidence=confidence,
            preset_used=self._config.name,
            per_head_votes=votes,
            aggregated_scores=aggregated_scores,
            decision_rule_triggered=rule_triggered,
            threat_vote_count=threat_count,
            safe_vote_count=safe_count,
            abstain_vote_count=abstain_count,
            weighted_threat_score=weighted_threat,
            weighted_safe_score=weighted_safe,
        )

    def _apply_decision_rules(
        self,
        votes: dict[str, HeadVoteDetail],
        threat_count: int,
        safe_count: int,
        weighted_threat: float,
        weighted_safe: float,
        weighted_ratio: float,
    ) -> tuple[Decision, str, float]:
        """Apply decision rules in priority order.

        Args:
            votes: Per-head vote details
            threat_count: Number of THREAT votes
            safe_count: Number of SAFE votes
            weighted_threat: Total weighted THREAT score
            weighted_safe: Total weighted SAFE score
            weighted_ratio: weighted_threat / weighted_safe

        Returns:
            Tuple of (decision, rule_triggered, confidence)
        """
        cfg = self._config.decision

        # Rule 1: High-confidence override
        # Any head THREAT + confidence >= 85% + at least 1 other THREAT -> THREAT
        for head_name, vote_detail in votes.items():
            if (
                vote_detail.vote == Vote.THREAT
                and vote_detail.confidence >= cfg.high_confidence_threshold
            ):
                # Count other THREAT votes
                other_threat_count = sum(
                    1 for name, v in votes.items()
                    if name != head_name and v.vote == Vote.THREAT
                )
                if other_threat_count >= 1:
                    return (
                        Decision.THREAT,
                        f"high_confidence_override:{head_name}",
                        vote_detail.confidence,
                    )

        # Rule 2: Severity veto
        # If severity="none", need 3+ other THREAT votes to override
        severity_vote = votes.get("severity")
        if severity_vote and severity_vote.vote == Vote.SAFE:
            # Severity says SAFE (severity=none)
            # Count non-severity THREAT votes
            non_severity_threat_count = sum(
                1 for name, v in votes.items()
                if name != "severity" and v.vote == Vote.THREAT
            )
            if non_severity_threat_count < cfg.severity_veto_override_votes:
                # Not enough THREAT votes to override severity veto
                return (
                    Decision.SAFE,
                    "severity_veto",
                    severity_vote.confidence,
                )

        # Rule 3: Minimum votes check
        # Need >= min_threat_votes to consider as THREAT
        if threat_count < cfg.min_threat_votes:
            # Not enough THREAT votes
            # But check if we're in review zone
            if (
                threat_count >= 1
                and weighted_ratio >= cfg.review_ratio_min
            ):
                # Some threat signals but below threshold -> REVIEW
                avg_threat_confidence = (
                    sum(v.confidence for v in votes.values() if v.vote == Vote.THREAT)
                    / threat_count
                    if threat_count > 0
                    else 0.0
                )
                return (
                    Decision.REVIEW,
                    "insufficient_votes_review",
                    avg_threat_confidence,
                )

            # No significant threat signals -> SAFE
            avg_safe_confidence = (
                sum(v.confidence for v in votes.values() if v.vote == Vote.SAFE)
                / safe_count
                if safe_count > 0
                else 0.5
            )
            return (
                Decision.SAFE,
                "insufficient_threat_votes",
                avg_safe_confidence,
            )

        # Rule 4: Weighted ratio check
        # threat_weight / safe_weight >= threat_ratio -> THREAT
        if weighted_ratio >= cfg.threat_ratio:
            avg_threat_confidence = (
                sum(v.confidence for v in votes.values() if v.vote == Vote.THREAT)
                / threat_count
            )
            return (
                Decision.THREAT,
                "weighted_ratio_threshold",
                avg_threat_confidence,
            )

        # Rule 5: Review zone
        # Weighted ratio in [review_ratio_min, threat_ratio) -> REVIEW
        if weighted_ratio >= cfg.review_ratio_min:
            # In the review zone - uncertain
            avg_confidence = sum(v.confidence for v in votes.values()) / len(votes)
            return (
                Decision.REVIEW,
                "weighted_ratio_review_zone",
                avg_confidence,
            )

        # Rule 6: Tie-breaker
        # Ties favor SAFE to reduce false positives
        if threat_count == safe_count:
            avg_safe_confidence = (
                sum(v.confidence for v in votes.values() if v.vote == Vote.SAFE)
                / safe_count
                if safe_count > 0
                else 0.5
            )
            return (
                Decision.SAFE,
                "tie_breaker_favors_safe",
                avg_safe_confidence,
            )

        # Default: Check majority
        if threat_count > safe_count:
            avg_threat_confidence = (
                sum(v.confidence for v in votes.values() if v.vote == Vote.THREAT)
                / threat_count
            )
            # But ratio didn't meet threshold, so REVIEW
            return (
                Decision.REVIEW,
                "threat_majority_below_ratio",
                avg_threat_confidence,
            )
        else:
            avg_safe_confidence = (
                sum(v.confidence for v in votes.values() if v.vote == Vote.SAFE)
                / safe_count
                if safe_count > 0
                else 0.5
            )
            return (
                Decision.SAFE,
                "safe_majority",
                avg_safe_confidence,
            )

    def vote_from_classification(
        self,
        classification_result: Any,
    ) -> VotingResult:
        """Vote from a GemmaClassificationResult.

        Convenience method that extracts head outputs from a
        GemmaClassificationResult and runs the voting engine.

        Args:
            classification_result: GemmaClassificationResult from Gemma detector

        Returns:
            VotingResult with full transparency
        """
        # Extract harm data
        harm_max_prob = 0.0
        harm_active_labels: list[str] = []
        if classification_result.harm_types is not None:
            harm_max_prob = classification_result.harm_types.max_probability
            harm_active_labels = [
                h.value for h in classification_result.harm_types.active_labels
            ]

        # Build HeadOutputs from classification result
        outputs = HeadOutputs(
            binary_threat_prob=classification_result.threat_probability,
            binary_safe_prob=classification_result.safe_probability,
            family_prediction=classification_result.threat_family.value,
            family_confidence=classification_result.family_confidence,
            severity_prediction=classification_result.severity.value,
            severity_confidence=classification_result.severity_confidence,
            technique_prediction=(
                classification_result.primary_technique.value
                if classification_result.primary_technique
                else None
            ),
            technique_confidence=classification_result.technique_confidence,
            harm_max_probability=harm_max_prob,
            harm_active_labels=harm_active_labels,
        )

        return self.vote(outputs)


def create_voting_engine(
    preset: VotingPreset | str = VotingPreset.BALANCED,
    config: VotingConfig | None = None,
) -> VotingEngine:
    """Factory function to create a VotingEngine.

    Args:
        preset: Voting preset name or enum (default: balanced)
        config: Custom VotingConfig (overrides preset if provided)

    Returns:
        Configured VotingEngine instance

    Examples:
        >>> engine = create_voting_engine("balanced")
        >>> engine = create_voting_engine(VotingPreset.HIGH_SECURITY)
    """
    return VotingEngine(preset=preset, config=config)
