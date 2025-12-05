"""Policy evaluation engine.

Pure domain logic for evaluating policies against detections.
All functions are stateless and side-effect free (NO I/O).

Performance target: <1ms policy evaluation per detection.
"""
from raxe.domain.engine.executor import Detection
from raxe.domain.policies.models import (
    Policy,
    PolicyAction,
    PolicyCondition,
    PolicyDecision,
)
from raxe.domain.rules.models import Severity


def _matches_condition(detection: Detection, condition: PolicyCondition) -> bool:
    """Check if detection matches a single policy condition.

    All specified fields in condition are AND-ed together.
    If a field is None, it's ignored (matches all).

    Args:
        detection: Detection to evaluate
        condition: Condition to check against

    Returns:
        True if detection matches all specified condition criteria
    """
    # Check rule ID match
    if condition.rule_ids is not None:
        if detection.rule_id not in condition.rule_ids:
            return False

    # Check severity threshold
    if condition.severity_threshold is not None:
        # Severity order (lower number = more severe)
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }

        detection_severity_level = severity_order[detection.severity]
        threshold_level = severity_order[condition.severity_threshold]

        # Detection must be >= threshold severity (i.e., <= in numeric order)
        if detection_severity_level > threshold_level:
            return False

    # Check confidence range
    if condition.min_confidence is not None:
        if detection.confidence < condition.min_confidence:
            return False

    if condition.max_confidence is not None:
        if detection.confidence > condition.max_confidence:
            return False

    # Note: threat_types and custom_filter not implemented in this phase
    # They would require additional metadata on Detection
    # For now, if specified, we ignore them (conservative approach)

    return True


def _matches_policy(detection: Detection, policy: Policy) -> bool:
    """Check if detection matches any condition in policy.

    Policy conditions use OR logic - any matching condition triggers policy.

    Args:
        detection: Detection to evaluate
        policy: Policy to check

    Returns:
        True if detection matches any policy condition
    """
    if not policy.enabled:
        return False

    # OR logic: any condition matching triggers policy
    return any(
        _matches_condition(detection, condition)
        for condition in policy.conditions
    )


def evaluate_policies(
    detection: Detection,
    policies: list[Policy],
) -> PolicyDecision:
    """Evaluate all policies against a detection.

    Applies policy matching logic and returns final decision:
    1. Find all policies that match detection
    2. Sort by priority (highest first)
    3. Take action from highest priority policy
    4. Aggregate webhooks from all matched policies
    5. Apply severity override if specified

    Args:
        detection: Detection to evaluate policies against
        policies: List of policies to evaluate (may be empty)

    Returns:
        PolicyDecision with final action and metadata

    Note:
        If no policies match, returns default decision (LOG action, no override).
        Pure function - no I/O, no side effects.
    """
    # Find matching policies
    matched_policies = [
        policy for policy in policies
        if _matches_policy(detection, policy)
    ]

    # If no policies match, return default decision
    if not matched_policies:
        return PolicyDecision(
            action=PolicyAction.LOG,
            original_severity=detection.severity,
            final_severity=detection.severity,
            matched_policies=[],
            metadata={},
        )

    # Sort by priority (highest first, then by policy_id for determinism)
    matched_policies.sort(
        key=lambda p: (-p.priority, p.policy_id)
    )

    # Highest priority policy determines action
    primary_policy = matched_policies[0]
    action = primary_policy.action

    # Apply severity override from highest priority policy
    final_severity = (
        primary_policy.override_severity
        if primary_policy.override_severity is not None
        else detection.severity
    )

    # Aggregate metadata from all matched policies
    combined_metadata: dict[str, str] = {}
    for policy in matched_policies:
        combined_metadata.update(policy.metadata)

    return PolicyDecision(
        action=action,
        original_severity=detection.severity,
        final_severity=final_severity,
        matched_policies=[p.policy_id for p in matched_policies],
        metadata=combined_metadata,
    )


def evaluate_policies_batch(
    detections: list[Detection],
    policies: list[Policy],
) -> dict[str, PolicyDecision]:
    """Evaluate policies for multiple detections.

    Convenience function for batch evaluation.

    Args:
        detections: List of detections to evaluate
        policies: List of policies to apply

    Returns:
        Dict mapping detection rule_id to PolicyDecision

    Note:
        For detections with same rule_id, uses versioned_rule_id as key.
    """
    results: dict[str, PolicyDecision] = {}

    for detection in detections:
        # Use versioned rule ID as key for uniqueness
        key = detection.versioned_rule_id
        decision = evaluate_policies(detection, policies)
        results[key] = decision

    return results


def filter_policies_by_customer(
    policies: list[Policy],
    customer_id: str,
) -> list[Policy]:
    """Filter policies to only those belonging to customer.

    Security helper to ensure policy isolation.

    Args:
        policies: All policies
        customer_id: Customer ID to filter by

    Returns:
        List of policies belonging to customer

    Note:
        Pure function for use in application layer.
    """
    return [
        policy for policy in policies
        if policy.customer_id == customer_id
    ]
