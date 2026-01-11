"""Binary-First Voting Engine - Binary head as sole intent detector.

This module implements the BinaryFirstEngine which inverts the traditional
consensus-based voting approach. The binary head is the sole arbiter of
threat intent; other heads can only SUPPRESS (not veto) the threat signal
when there is strong, converging benign evidence.

Design Principles:
1. Binary head is the sole intent detector (trained for threat/benign)
2. Other heads provide classification metadata, not threat detection
3. Suppression requires multi-head quorum, not single-head veto
4. No false negative from "severity=none" alone

Decision Zones:
- HIGH_THREAT_ZONE (binary >= 0.85): THREAT unless suppressed by quorum
- MID_ZONE (binary 0.50-0.85): Use auxiliary heads for tiebreak
- LOW_THREAT_ZONE (binary < 0.50): SAFE (binary confident benign)

This engine was designed to address the 47% FN rate caused by severity_veto
in the original VotingEngine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raxe.domain.ml.voting.engine import HeadOutputs

from raxe.domain.ml.voting.models import (
    Decision,
    HeadVoteDetail,
    Vote,
    VotingResult,
)


@dataclass(frozen=True)
class BinaryFirstConfig:
    """Configuration for binary-first voting engine.

    Attributes:
        name: Configuration name for telemetry
        high_threat_threshold: Binary prob above which we're in HIGH_THREAT_ZONE
        mid_zone_low: Binary prob above which we're in MID_ZONE
        suppression_quorum: Minimum benign-voting heads to suppress in HIGH_THREAT_ZONE
        severity_none_confidence: Min confidence for severity=none to count as benign vote
        family_benign_confidence: Min confidence for family=benign to count as benign vote
        technique_none_confidence: Min confidence for technique=none to count as benign vote
        mid_zone_threat_ratio: Weighted ratio threshold for THREAT in MID_ZONE
        mid_zone_review_ratio: Weighted ratio threshold for REVIEW in MID_ZONE
    """

    name: str = "binary_first"
    high_threat_threshold: float = 0.85
    mid_zone_low: float = 0.50
    suppression_quorum: int = 3  # Requires 3 heads for suppression (validated: TPR 90.4%, FPR 7.4%)
    severity_none_confidence: float = 0.70
    family_benign_confidence: float = 0.60
    technique_none_confidence: float = 0.50
    mid_zone_threat_ratio: float = 1.5
    mid_zone_review_ratio: float = 0.8


# Preset configurations for different use cases
BINARY_FIRST_PRESETS: dict[str, BinaryFirstConfig] = {
    # Default: Balanced (TPR 90.4%, FPR 7.4%) - requires 3-head quorum for suppression
    "balanced": BinaryFirstConfig(name="balanced"),
    # High recall (TPR 90.8%, FPR 7.6%) - lower threshold + 3-head quorum
    "high_recall": BinaryFirstConfig(
        name="high_recall",
        high_threat_threshold=0.80,
        suppression_quorum=3,
    ),
    # Maximum recall (TPR 91.2%, FPR 8.0%) - aggressive thresholds for highest TPR
    "max_recall": BinaryFirstConfig(
        name="max_recall",
        high_threat_threshold=0.75,
        mid_zone_low=0.40,
        suppression_quorum=3,
    ),
    # Low FP (TPR 89.0%, FPR 6.0%) - original quorum=2 for lowest FPR
    "low_fp": BinaryFirstConfig(
        name="low_fp",
        suppression_quorum=2,
    ),
}

# Default configuration
DEFAULT_BINARY_FIRST_CONFIG = BINARY_FIRST_PRESETS["balanced"]


@dataclass
class SuppressionDetail:
    """Details about suppression evaluation for telemetry.

    Attributes:
        evaluated: Whether suppression was evaluated
        suppressed: Whether the threat was suppressed
        benign_votes: Number of heads voting benign
        quorum_required: Minimum votes needed for suppression
        head_contributions: Per-head suppression details
    """

    evaluated: bool = False
    suppressed: bool = False
    benign_votes: int = 0
    quorum_required: int = 3
    head_contributions: dict[str, tuple[str, float, bool]] = field(default_factory=dict)


class BinaryFirstEngine:
    """Binary-first voting engine with suppression-only auxiliary heads.

    This engine treats the binary head as the sole intent detector.
    Other heads (severity, family, technique) can only suppress a threat
    signal when there is strong, converging benign evidence from multiple
    heads meeting confidence thresholds.

    Key differences from VotingEngine:
    - No severity_veto: Single head cannot veto binary's threat signal
    - Suppression requires quorum: 2+ heads must agree on benign
    - Zone-based decisions: Different logic for high/mid/low binary prob

    Example:
        >>> engine = BinaryFirstEngine()
        >>> result = engine.vote(head_outputs)
        >>> result.decision
        <Decision.THREAT: 'threat'>
    """

    def __init__(self, config: BinaryFirstConfig | None = None):
        """Initialize the binary-first voting engine.

        Args:
            config: Custom configuration (default: DEFAULT_BINARY_FIRST_CONFIG)
        """
        self._config = config or DEFAULT_BINARY_FIRST_CONFIG
        self._last_suppression: SuppressionDetail | None = None

    @property
    def config(self) -> BinaryFirstConfig:
        """Get the current configuration."""
        return self._config

    @property
    def preset_name(self) -> str:
        """Get the configuration name."""
        return self._config.name

    @property
    def last_suppression(self) -> SuppressionDetail | None:
        """Get details of the last suppression evaluation (for telemetry)."""
        return self._last_suppression

    def vote(self, outputs: HeadOutputs) -> VotingResult:
        """Run the binary-first voting engine on head outputs.

        Routes to zone-specific handlers based on binary threat probability.

        Args:
            outputs: Container with all head outputs

        Returns:
            VotingResult with full transparency into the voting process
        """
        binary_prob = outputs.binary_threat_prob

        # Route to appropriate zone handler
        if binary_prob >= self._config.high_threat_threshold:
            return self._high_threat_zone(outputs)
        elif binary_prob >= self._config.mid_zone_low:
            return self._mid_zone(outputs)
        else:
            return self._low_threat_zone(outputs)

    def _high_threat_zone(self, outputs: HeadOutputs) -> VotingResult:
        """Handle HIGH_THREAT_ZONE (binary >= 0.85).

        In this zone, binary head is confident it's a threat.
        Decision is THREAT unless suppressed by multi-head quorum.

        Suppression requires:
        - severity=none with confidence >= threshold
        - family=benign with confidence >= threshold
        - technique=none with confidence >= threshold
        - At least suppression_quorum of these conditions met
        """
        votes = self._collect_votes(outputs)
        suppressed, suppression_reason = self._check_suppression(outputs)

        # Store suppression detail for telemetry
        self._last_suppression = self._build_suppression_detail(outputs, suppressed)

        if suppressed:
            # Multi-head quorum says benign - suppress the threat
            confidence = self._calculate_safe_confidence(votes)
            return self._build_result(
                decision=Decision.SAFE,
                confidence=confidence,
                rule_triggered=f"suppression:{suppression_reason}",
                votes=votes,
            )
        else:
            # No suppression - trust binary's threat signal
            confidence = outputs.binary_threat_prob
            return self._build_result(
                decision=Decision.THREAT,
                confidence=confidence,
                rule_triggered="binary_high_threat",
                votes=votes,
            )

    def _mid_zone(self, outputs: HeadOutputs) -> VotingResult:
        """Handle MID_ZONE (binary 0.50-0.85).

        In this zone, binary is uncertain but leaning threat.
        Use weighted ratio of auxiliary heads for tiebreak.
        """
        votes = self._collect_votes(outputs)
        self._last_suppression = None  # No suppression in mid zone

        # Calculate weighted scores and ratio
        weighted_threat, weighted_safe = self._calculate_weighted_scores(votes)
        ratio = self._calculate_ratio(weighted_threat, weighted_safe)

        # Apply ratio thresholds
        if ratio >= self._config.mid_zone_threat_ratio:
            confidence = min(0.85, outputs.binary_threat_prob + 0.1)
            return self._build_result(
                decision=Decision.THREAT,
                confidence=confidence,
                rule_triggered="mid_zone_threat_ratio",
                votes=votes,
            )
        elif ratio >= self._config.mid_zone_review_ratio:
            confidence = outputs.binary_threat_prob
            return self._build_result(
                decision=Decision.REVIEW,
                confidence=confidence,
                rule_triggered="mid_zone_review",
                votes=votes,
            )
        else:
            confidence = 1.0 - outputs.binary_threat_prob
            return self._build_result(
                decision=Decision.SAFE,
                confidence=confidence,
                rule_triggered="mid_zone_safe",
                votes=votes,
            )

    def _low_threat_zone(self, outputs: HeadOutputs) -> VotingResult:
        """Handle LOW_THREAT_ZONE (binary < 0.50).

        In this zone, binary is confident it's benign.
        Trust binary - return SAFE regardless of other heads.
        """
        votes = self._collect_votes(outputs)
        self._last_suppression = None  # No suppression in low zone

        confidence = 1.0 - outputs.binary_threat_prob
        return self._build_result(
            decision=Decision.SAFE,
            confidence=confidence,
            rule_triggered="binary_low_threat",
            votes=votes,
        )

    def _check_suppression(self, outputs: HeadOutputs) -> tuple[bool, str]:
        """Check if multi-head quorum supports suppression.

        For suppression in HIGH_THREAT_ZONE, we need multiple heads
        to converge on benign with sufficient confidence.

        Returns:
            Tuple of (suppressed, reason_string)
        """
        contributions = self._evaluate_head_contributions(outputs)
        benign_votes = sum(1 for _, _, counts in contributions.values() if counts)
        reasons = [
            f"{head}={pred}@{conf:.2f}"
            for head, (pred, conf, counts) in contributions.items()
            if counts
        ]

        suppressed = benign_votes >= self._config.suppression_quorum
        reason_str = f"{benign_votes}/{self._config.suppression_quorum}:{','.join(reasons)}"

        return suppressed, reason_str

    def _evaluate_head_contributions(
        self, outputs: HeadOutputs
    ) -> dict[str, tuple[str, float, bool]]:
        """Evaluate each head's contribution to suppression.

        Returns:
            Dict mapping head name to (prediction, confidence, counts_as_benign)
        """
        cfg = self._config
        tech_pred = outputs.technique_prediction or "none"

        return {
            "severity": (
                outputs.severity_prediction,
                outputs.severity_confidence,
                outputs.severity_prediction == "none"
                and outputs.severity_confidence >= cfg.severity_none_confidence,
            ),
            "family": (
                outputs.family_prediction,
                outputs.family_confidence,
                outputs.family_prediction == "benign"
                and outputs.family_confidence >= cfg.family_benign_confidence,
            ),
            "technique": (
                tech_pred,
                outputs.technique_confidence,
                tech_pred == "none"
                and outputs.technique_confidence >= cfg.technique_none_confidence,
            ),
        }

    def _build_suppression_detail(
        self, outputs: HeadOutputs, suppressed: bool
    ) -> SuppressionDetail:
        """Build suppression detail for telemetry."""
        contributions = self._evaluate_head_contributions(outputs)
        benign_votes = sum(1 for _, _, counts in contributions.values() if counts)

        return SuppressionDetail(
            evaluated=True,
            suppressed=suppressed,
            benign_votes=benign_votes,
            quorum_required=self._config.suppression_quorum,
            head_contributions=contributions,
        )

    def _collect_votes(self, outputs: HeadOutputs) -> dict[str, HeadVoteDetail]:
        """Collect votes from all heads for transparency.

        Note: In BinaryFirstEngine, votes are informational only.
        The actual decision is based on binary prob + suppression logic.
        """
        cfg = self._config
        tech_pred = outputs.technique_prediction or "none"
        harm_labels = ",".join(outputs.harm_active_labels) or "none"

        # Determine binary vote based on zone
        binary_vote = self._determine_binary_vote(outputs.binary_threat_prob)

        return {
            "binary": HeadVoteDetail(
                head_name="binary",
                vote=binary_vote,
                confidence=outputs.binary_threat_prob,
                weight=1.0,
                raw_probability=outputs.binary_threat_prob,
                threshold_used=cfg.high_threat_threshold,
                prediction="threat" if binary_vote == Vote.THREAT else "safe",
                rationale=f"binary_prob={outputs.binary_threat_prob:.3f}",
            ),
            "family": HeadVoteDetail(
                head_name="family",
                vote=Vote.THREAT if outputs.family_prediction != "benign" else Vote.SAFE,
                confidence=outputs.family_confidence,
                weight=0.8,
                raw_probability=outputs.family_confidence,
                threshold_used=cfg.family_benign_confidence,
                prediction=outputs.family_prediction,
                rationale=f"family={outputs.family_prediction}",
            ),
            "severity": HeadVoteDetail(
                head_name="severity",
                vote=(
                    Vote.THREAT if outputs.severity_prediction not in ("none", "low") else Vote.SAFE
                ),
                confidence=outputs.severity_confidence,
                weight=0.8,
                raw_probability=outputs.severity_confidence,
                threshold_used=cfg.severity_none_confidence,
                prediction=outputs.severity_prediction,
                rationale=f"severity={outputs.severity_prediction}",
            ),
            "technique": HeadVoteDetail(
                head_name="technique",
                vote=Vote.THREAT if tech_pred != "none" else Vote.SAFE,
                confidence=outputs.technique_confidence,
                weight=0.6,
                raw_probability=outputs.technique_confidence,
                threshold_used=cfg.technique_none_confidence,
                prediction=tech_pred,
                rationale=f"technique={tech_pred}",
            ),
            "harm": HeadVoteDetail(
                head_name="harm",
                vote=Vote.THREAT if outputs.harm_max_probability >= 0.5 else Vote.SAFE,
                confidence=outputs.harm_max_probability,
                weight=0.4,
                raw_probability=outputs.harm_max_probability,
                threshold_used=0.5,
                prediction=harm_labels,
                rationale=f"harm_max={outputs.harm_max_probability:.3f}",
            ),
        }

    def _determine_binary_vote(self, threat_prob: float) -> Vote:
        """Determine binary head vote based on threat probability zone."""
        if threat_prob >= self._config.high_threat_threshold:
            return Vote.THREAT
        if threat_prob >= self._config.mid_zone_low:
            return Vote.ABSTAIN
        return Vote.SAFE

    def _calculate_weighted_scores(self, votes: dict[str, HeadVoteDetail]) -> tuple[float, float]:
        """Calculate weighted threat and safe scores."""
        weighted_threat = sum(v.weight for v in votes.values() if v.vote == Vote.THREAT)
        weighted_safe = sum(v.weight for v in votes.values() if v.vote == Vote.SAFE)
        return weighted_threat, weighted_safe

    @staticmethod
    def _calculate_ratio(threat_score: float, safe_score: float) -> float:
        """Calculate threat/safe ratio, handling division by zero."""
        if safe_score > 0:
            return threat_score / safe_score
        return float("inf") if threat_score > 0 else 0.0

    def _calculate_safe_confidence(self, votes: dict[str, HeadVoteDetail]) -> float:
        """Calculate average confidence for SAFE-voting heads."""
        safe_votes = [v for v in votes.values() if v.vote == Vote.SAFE]
        return sum(v.confidence for v in safe_votes) / len(safe_votes) if safe_votes else 0.5

    def _count_votes(self, votes: dict[str, HeadVoteDetail]) -> tuple[int, int, int]:
        """Count votes by type. Returns (threat_count, safe_count, abstain_count)."""
        threat = sum(1 for v in votes.values() if v.vote == Vote.THREAT)
        safe = sum(1 for v in votes.values() if v.vote == Vote.SAFE)
        abstain = sum(1 for v in votes.values() if v.vote == Vote.ABSTAIN)
        return threat, safe, abstain

    def _build_result(
        self,
        decision: Decision,
        confidence: float,
        rule_triggered: str,
        votes: dict[str, HeadVoteDetail],
    ) -> VotingResult:
        """Build VotingResult from collected data."""
        threat_count, safe_count, abstain_count = self._count_votes(votes)
        weighted_threat, weighted_safe = self._calculate_weighted_scores(votes)
        ratio = min(self._calculate_ratio(weighted_threat, weighted_safe), 999.0)

        return VotingResult(
            decision=decision,
            confidence=min(1.0, max(0.0, confidence)),
            preset_used=self._config.name,
            per_head_votes=votes,
            aggregated_scores={"safe": weighted_safe, "threat": weighted_threat, "ratio": ratio},
            decision_rule_triggered=rule_triggered,
            threat_vote_count=threat_count,
            safe_vote_count=safe_count,
            abstain_vote_count=abstain_count,
            weighted_threat_score=weighted_threat,
            weighted_safe_score=weighted_safe,
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
        # Import here to avoid circular import
        from raxe.domain.ml.voting.engine import HeadOutputs

        # Extract harm data
        harm_max_prob = 0.0
        harm_active_labels: list[str] = []
        if classification_result.harm_types is not None:
            harm_max_prob = classification_result.harm_types.max_probability
            harm_active_labels = [h.value for h in classification_result.harm_types.active_labels]

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


def create_binary_first_engine(
    preset: str | None = None,
    config: BinaryFirstConfig | None = None,
) -> BinaryFirstEngine:
    """Factory function to create a BinaryFirstEngine.

    Args:
        preset: Preset name ("balanced", "high_recall", "max_recall", "low_fp").
                Ignored if config is provided.
        config: Custom configuration. Takes precedence over preset.

    Returns:
        Configured BinaryFirstEngine instance

    Available presets:
        - "balanced" (default): TPR 90.4%, FPR 7.4% - requires 3-head suppression quorum
        - "high_recall": TPR 90.8%, FPR 7.6% - lower threshold for more threat detection
        - "max_recall": TPR 91.2%, FPR 8.0% - aggressive thresholds for maximum TPR
        - "low_fp": TPR 89.0%, FPR 6.0% - strictest thresholds for minimal false positives

    Example:
        >>> engine = create_binary_first_engine()  # Uses balanced preset
        >>> engine = create_binary_first_engine(preset="high_recall")
        >>> engine = create_binary_first_engine(config=BinaryFirstConfig(suppression_quorum=2))
    """
    if config is not None:
        return BinaryFirstEngine(config=config)

    if preset is not None:
        if preset not in BINARY_FIRST_PRESETS:
            raise ValueError(
                f"Unknown preset '{preset}'. Available: {list(BINARY_FIRST_PRESETS.keys())}"
            )
        return BinaryFirstEngine(config=BINARY_FIRST_PRESETS[preset])

    return BinaryFirstEngine()
