"""Individual head voting logic - Pure functions for per-head voting.

This module contains ONLY pure functions - no I/O operations.
Each function takes head output data and configuration, returns a vote.

Head Voters:
- vote_binary: Binary (is_threat) head voting
- vote_family: Family head voting
- vote_severity: Severity head voting
- vote_technique: Technique head voting
- vote_harm: Harm types head voting
"""

from raxe.domain.ml.voting.config import (
    BinaryHeadThresholds,
    FamilyHeadThresholds,
    HarmHeadThresholds,
    HeadWeights,
    SeverityHeadThresholds,
    TechniqueHeadThresholds,
)
from raxe.domain.ml.voting.models import HeadVoteDetail, Vote


def vote_binary(
    threat_probability: float,
    safe_probability: float,
    thresholds: BinaryHeadThresholds,
    weight: float,
) -> HeadVoteDetail:
    """Cast vote for the binary (is_threat) classifier head.

    Voting rules:
    - THREAT if threat_probability >= threat_threshold
    - SAFE if threat_probability < safe_threshold
    - ABSTAIN otherwise (gray zone)

    Args:
        threat_probability: Model output probability of threat (0.0 to 1.0)
        safe_probability: Model output probability of safe (0.0 to 1.0)
        thresholds: Threshold configuration for this head
        weight: Vote weight for this head

    Returns:
        HeadVoteDetail with the vote, confidence, and rationale

    Examples:
        >>> detail = vote_binary(0.80, 0.20, BinaryHeadThresholds(), 1.0)
        >>> detail.vote
        <Vote.THREAT: 'threat'>
        >>> detail.confidence
        0.8
    """
    if threat_probability >= thresholds.threat_threshold:
        vote = Vote.THREAT
        confidence = threat_probability
        threshold_used = thresholds.threat_threshold
        rationale = (
            f"threat_probability ({threat_probability:.2%}) >= "
            f"threat_threshold ({thresholds.threat_threshold:.2%})"
        )
    elif threat_probability < thresholds.safe_threshold:
        vote = Vote.SAFE
        confidence = safe_probability
        threshold_used = thresholds.safe_threshold
        rationale = (
            f"threat_probability ({threat_probability:.2%}) < "
            f"safe_threshold ({thresholds.safe_threshold:.2%})"
        )
    else:
        vote = Vote.ABSTAIN
        # Confidence for abstain is how close to the decision boundary
        confidence = 1.0 - abs(
            threat_probability - (thresholds.threat_threshold + thresholds.safe_threshold) / 2
        ) / ((thresholds.threat_threshold - thresholds.safe_threshold) / 2)
        confidence = max(0.0, min(1.0, confidence))
        threshold_used = (thresholds.threat_threshold + thresholds.safe_threshold) / 2
        rationale = (
            f"threat_probability ({threat_probability:.2%}) in gray zone "
            f"[{thresholds.safe_threshold:.2%}, {thresholds.threat_threshold:.2%})"
        )

    return HeadVoteDetail(
        head_name="binary",
        vote=vote,
        confidence=confidence,
        weight=weight,
        raw_probability=threat_probability,
        threshold_used=threshold_used,
        prediction="threat" if threat_probability >= 0.5 else "safe",
        rationale=rationale,
    )


def vote_family(
    family_prediction: str,
    family_confidence: float,
    thresholds: FamilyHeadThresholds,
    weight: float,
) -> HeadVoteDetail:
    """Cast vote for the family classifier head.

    Voting rules:
    - THREAT if family != benign AND confidence >= threat_confidence
    - SAFE if family == benign OR confidence < safe_confidence
    - ABSTAIN otherwise

    Args:
        family_prediction: Predicted threat family (e.g., "benign", "jailbreak")
        family_confidence: Model confidence in the prediction (0.0 to 1.0)
        thresholds: Threshold configuration for this head
        weight: Vote weight for this head

    Returns:
        HeadVoteDetail with the vote, confidence, and rationale

    Examples:
        >>> detail = vote_family("jailbreak", 0.75, FamilyHeadThresholds(), 1.2)
        >>> detail.vote
        <Vote.THREAT: 'threat'>
    """
    family_is_benign = family_prediction.lower() == "benign"

    if family_is_benign:
        vote = Vote.SAFE
        confidence = family_confidence
        threshold_used = 0.0  # No threshold for benign
        rationale = f"family={family_prediction} is benign"
    elif family_confidence >= thresholds.threat_confidence:
        vote = Vote.THREAT
        confidence = family_confidence
        threshold_used = thresholds.threat_confidence
        rationale = (
            f"family={family_prediction} with confidence ({family_confidence:.2%}) >= "
            f"threat_confidence ({thresholds.threat_confidence:.2%})"
        )
    elif family_confidence < thresholds.safe_confidence:
        vote = Vote.SAFE
        confidence = 1.0 - family_confidence  # Low confidence in threat = high confidence in safe
        threshold_used = thresholds.safe_confidence
        rationale = (
            f"family={family_prediction} with confidence ({family_confidence:.2%}) < "
            f"safe_confidence ({thresholds.safe_confidence:.2%})"
        )
    else:
        vote = Vote.ABSTAIN
        # Confidence for abstain reflects uncertainty
        confidence = 0.5
        threshold_used = (thresholds.threat_confidence + thresholds.safe_confidence) / 2
        rationale = (
            f"family={family_prediction} with confidence ({family_confidence:.2%}) in gray zone "
            f"[{thresholds.safe_confidence:.2%}, {thresholds.threat_confidence:.2%})"
        )

    return HeadVoteDetail(
        head_name="family",
        vote=vote,
        confidence=confidence,
        weight=weight,
        raw_probability=family_confidence,
        threshold_used=threshold_used,
        prediction=family_prediction,
        rationale=rationale,
    )


def vote_severity(
    severity_prediction: str,
    severity_confidence: float,
    thresholds: SeverityHeadThresholds,
    weight: float,
) -> HeadVoteDetail:
    """Cast vote for the severity classifier head.

    Voting rules:
    - THREAT if severity in threat_severities (low, medium, high, critical)
    - SAFE if severity in safe_severities (none)
    - No abstain - severity always has an opinion

    Note: Severity head has the highest weight (1.5) because it directly
    indicates threat severity and has strong signal quality.

    Args:
        severity_prediction: Predicted severity (e.g., "none", "high", "critical")
        severity_confidence: Model confidence in the prediction (0.0 to 1.0)
        thresholds: Threshold configuration for this head
        weight: Vote weight for this head

    Returns:
        HeadVoteDetail with the vote, confidence, and rationale

    Examples:
        >>> detail = vote_severity("high", 0.85, SeverityHeadThresholds(), 1.5)
        >>> detail.vote
        <Vote.THREAT: 'threat'>
    """
    severity_lower = severity_prediction.lower()

    if severity_lower in thresholds.safe_severities:
        vote = Vote.SAFE
        confidence = severity_confidence
        threshold_used = 0.0
        rationale = f"severity={severity_prediction} in safe_severities {thresholds.safe_severities}"
    elif severity_lower in thresholds.threat_severities:
        vote = Vote.THREAT
        confidence = severity_confidence
        threshold_used = 0.0
        rationale = f"severity={severity_prediction} in threat_severities {thresholds.threat_severities}"
    else:
        # Unknown severity - vote based on whether it's closer to threat or safe
        # This shouldn't happen with valid model outputs
        vote = Vote.ABSTAIN
        confidence = 0.5
        threshold_used = 0.5
        rationale = f"severity={severity_prediction} not in known categories"

    return HeadVoteDetail(
        head_name="severity",
        vote=vote,
        confidence=confidence,
        weight=weight,
        raw_probability=severity_confidence,
        threshold_used=threshold_used,
        prediction=severity_prediction,
        rationale=rationale,
    )


def vote_technique(
    technique_prediction: str | None,
    technique_confidence: float,
    thresholds: TechniqueHeadThresholds,
    weight: float,
) -> HeadVoteDetail:
    """Cast vote for the primary technique classifier head.

    Voting rules:
    - THREAT if technique not in safe_techniques AND confidence >= threat_confidence
    - SAFE if technique in safe_techniques OR confidence < safe_confidence
    - ABSTAIN otherwise

    Args:
        technique_prediction: Predicted attack technique (e.g., "none", "instruction_override")
        technique_confidence: Model confidence in the prediction (0.0 to 1.0)
        thresholds: Threshold configuration for this head
        weight: Vote weight for this head

    Returns:
        HeadVoteDetail with the vote, confidence, and rationale

    Examples:
        >>> detail = vote_technique("instruction_override", 0.70, TechniqueHeadThresholds(), 1.0)
        >>> detail.vote
        <Vote.THREAT: 'threat'>
    """
    # Handle None technique prediction
    if technique_prediction is None:
        technique_prediction = "none"

    technique_lower = technique_prediction.lower()
    is_safe_technique = technique_lower in [t.lower() for t in thresholds.safe_techniques]

    if is_safe_technique:
        vote = Vote.SAFE
        confidence = technique_confidence
        threshold_used = 0.0
        rationale = f"technique={technique_prediction} in safe_techniques"
    elif technique_confidence >= thresholds.threat_confidence:
        vote = Vote.THREAT
        confidence = technique_confidence
        threshold_used = thresholds.threat_confidence
        rationale = (
            f"technique={technique_prediction} with confidence ({technique_confidence:.2%}) >= "
            f"threat_confidence ({thresholds.threat_confidence:.2%})"
        )
    elif technique_confidence < thresholds.safe_confidence:
        vote = Vote.SAFE
        confidence = 1.0 - technique_confidence
        threshold_used = thresholds.safe_confidence
        rationale = (
            f"technique={technique_prediction} with confidence ({technique_confidence:.2%}) < "
            f"safe_confidence ({thresholds.safe_confidence:.2%})"
        )
    else:
        vote = Vote.ABSTAIN
        confidence = 0.5
        threshold_used = (thresholds.threat_confidence + thresholds.safe_confidence) / 2
        rationale = (
            f"technique={technique_prediction} with confidence ({technique_confidence:.2%}) in gray zone "
            f"[{thresholds.safe_confidence:.2%}, {thresholds.threat_confidence:.2%})"
        )

    return HeadVoteDetail(
        head_name="technique",
        vote=vote,
        confidence=confidence,
        weight=weight,
        raw_probability=technique_confidence,
        threshold_used=threshold_used,
        prediction=technique_prediction,
        rationale=rationale,
    )


def vote_harm(
    max_probability: float,
    active_labels: list[str],
    thresholds: HarmHeadThresholds,
    weight: float,
) -> HeadVoteDetail:
    """Cast vote for the harm types (multilabel) classifier head.

    Voting rules:
    - THREAT if max_probability >= threat_threshold
    - SAFE if max_probability < safe_threshold
    - ABSTAIN otherwise

    Note: Harm head has the lowest weight (0.8) because it can trigger
    false positives on benign content discussing sensitive topics.

    Args:
        max_probability: Maximum probability across all harm types (0.0 to 1.0)
        active_labels: List of active harm type labels
        thresholds: Threshold configuration for this head
        weight: Vote weight for this head

    Returns:
        HeadVoteDetail with the vote, confidence, and rationale

    Examples:
        >>> detail = vote_harm(0.95, ["violence_or_physical_harm"], HarmHeadThresholds(), 0.8)
        >>> detail.vote
        <Vote.THREAT: 'threat'>
    """
    # Build prediction string from active labels
    if active_labels:
        prediction = ",".join(active_labels[:3])  # Limit to top 3 for readability
        if len(active_labels) > 3:
            prediction += f",+{len(active_labels) - 3}"
    else:
        prediction = "none"

    if max_probability >= thresholds.threat_threshold:
        vote = Vote.THREAT
        confidence = max_probability
        threshold_used = thresholds.threat_threshold
        rationale = (
            f"max_probability ({max_probability:.2%}) >= "
            f"threat_threshold ({thresholds.threat_threshold:.2%})"
        )
    elif max_probability < thresholds.safe_threshold:
        vote = Vote.SAFE
        confidence = 1.0 - max_probability
        threshold_used = thresholds.safe_threshold
        rationale = (
            f"max_probability ({max_probability:.2%}) < "
            f"safe_threshold ({thresholds.safe_threshold:.2%})"
        )
    else:
        vote = Vote.ABSTAIN
        # Confidence for abstain reflects uncertainty
        confidence = 0.5
        threshold_used = (thresholds.threat_threshold + thresholds.safe_threshold) / 2
        rationale = (
            f"max_probability ({max_probability:.2%}) in gray zone "
            f"[{thresholds.safe_threshold:.2%}, {thresholds.threat_threshold:.2%})"
        )

    return HeadVoteDetail(
        head_name="harm",
        vote=vote,
        confidence=confidence,
        weight=weight,
        raw_probability=max_probability,
        threshold_used=threshold_used,
        prediction=prediction,
        rationale=rationale,
    )
