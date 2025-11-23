"""Domain models for policy-based threat response.

Pure domain layer - immutable value objects for policy evaluation.
Policies allow customers to override default threat responses.
"""
from dataclasses import dataclass, field
from enum import Enum

from raxe.domain.rules.models import Severity


class PolicyAction(Enum):
    """Action to take when policy conditions match.

    Overrides default detection behavior.
    """
    ALLOW = "ALLOW"      # Allow through despite detection
    BLOCK = "BLOCK"      # Block despite low severity
    FLAG = "FLAG"        # Flag for review but allow
    LOG = "LOG"          # Log only, no enforcement


@dataclass(frozen=True)
class PolicyCondition:
    """Conditions that must be met for policy to apply.

    All specified conditions are AND-ed together.
    If a field is None, that condition is ignored.

    Attributes:
        rule_ids: Specific rule IDs this policy applies to (None = all rules)
        severity_threshold: Minimum severity level (None = all severities)
        threat_types: Specific threat types (None = all types)
        min_confidence: Minimum confidence score (0.0-1.0, None = all)
        max_confidence: Maximum confidence score (0.0-1.0, None = all)
        custom_filter: JSONPath expression for advanced filtering (None = no filter)
    """
    rule_ids: list[str] | None = None
    severity_threshold: Severity | None = None
    threat_types: list[str] | None = None
    min_confidence: float | None = None
    max_confidence: float | None = None
    custom_filter: str | None = None

    def __post_init__(self) -> None:
        """Validate condition constraints."""
        if self.min_confidence is not None:
            if not (0.0 <= self.min_confidence <= 1.0):
                raise ValueError(
                    f"min_confidence must be 0-1, got {self.min_confidence}"
                )

        if self.max_confidence is not None:
            if not (0.0 <= self.max_confidence <= 1.0):
                raise ValueError(
                    f"max_confidence must be 0-1, got {self.max_confidence}"
                )

        if (
            self.min_confidence is not None
            and self.max_confidence is not None
            and self.min_confidence > self.max_confidence
        ):
            raise ValueError(
                f"min_confidence ({self.min_confidence}) cannot be greater than "
                f"max_confidence ({self.max_confidence})"
            )

        if self.rule_ids is not None and not self.rule_ids:
            raise ValueError("rule_ids cannot be empty list (use None for all rules)")

        if self.threat_types is not None and not self.threat_types:
            raise ValueError("threat_types cannot be empty list (use None for all types)")


@dataclass(frozen=True)
class Policy:
    """Policy for overriding threat detection behavior.

    Policies allow customers to customize how threats are handled:
    - Allow known false positives
    - Block specific patterns more aggressively
    - Route detections to webhooks
    - Override severity levels

    Attributes:
        policy_id: Unique identifier for this policy
        customer_id: Customer who owns this policy
        name: Human-readable policy name
        description: What this policy does and why
        conditions: List of conditions (OR logic - any match applies policy)
        action: Action to take when conditions match
        override_severity: Optional severity override (None = keep original)
        priority: Priority for conflict resolution (higher = higher priority)
        enabled: Whether policy is active
        metadata: Additional metadata for tracking/auditing
    """
    policy_id: str
    customer_id: str
    name: str
    description: str
    conditions: list[PolicyCondition]
    action: PolicyAction
    override_severity: Severity | None = None
    priority: int = 0
    enabled: bool = True
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate policy configuration."""
        if not self.policy_id:
            raise ValueError("policy_id cannot be empty")

        if not self.customer_id:
            raise ValueError("customer_id cannot be empty")

        if not self.name:
            raise ValueError("name cannot be empty")

        if not self.conditions:
            raise ValueError("Policy must have at least one condition")

        if self.priority < 0:
            raise ValueError(f"priority must be non-negative, got {self.priority}")

        # Security: Cap priority at 1000 to prevent resource exhaustion
        if self.priority > 1000:
            raise ValueError(f"priority cannot exceed 1000, got {self.priority}")


@dataclass(frozen=True)
class PolicyDecision:
    """Result of policy evaluation against a detection.

    Represents the final decision after evaluating all applicable policies.

    Attributes:
        action: Action to take (from highest priority matching policy)
        original_severity: Original severity from detection
        final_severity: Severity after policy override (may be same as original)
        matched_policies: List of policy IDs that matched (ordered by priority)
        should_block: True if action is BLOCK
        should_allow: True if action is ALLOW
        should_flag: True if action is FLAG
        metadata: Combined metadata from matched policies
    """
    action: PolicyAction
    original_severity: Severity
    final_severity: Severity
    matched_policies: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def should_block(self) -> bool:
        """True if action is BLOCK."""
        return self.action == PolicyAction.BLOCK

    @property
    def should_allow(self) -> bool:
        """True if action is ALLOW."""
        return self.action == PolicyAction.ALLOW

    @property
    def should_flag(self) -> bool:
        """True if action is FLAG."""
        return self.action == PolicyAction.FLAG

    @property
    def severity_changed(self) -> bool:
        """True if severity was overridden by policy."""
        return self.original_severity != self.final_severity

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of decision
        """
        return {
            "action": self.action.value,
            "original_severity": self.original_severity.value,
            "final_severity": self.final_severity.value,
            "severity_changed": self.severity_changed,
            "should_block": self.should_block,
            "should_allow": self.should_allow,
            "should_flag": self.should_flag,
            "matched_policies": self.matched_policies,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class PolicySet:
    """Collection of policies with security limits.

    Ensures policy count doesn't exceed reasonable limits
    to prevent resource exhaustion attacks.

    Attributes:
        policies: List of policies in the set
        max_policies: Maximum number of policies allowed (default: 100)
    """
    policies: list[Policy]
    max_policies: int = 100

    def __post_init__(self) -> None:
        """Validate policy set."""
        if len(self.policies) > self.max_policies:
            raise ValueError(
                f"Policy count ({len(self.policies)}) exceeds maximum "
                f"allowed ({self.max_policies}). This limit prevents resource "
                f"exhaustion attacks."
            )

    @property
    def policy_count(self) -> int:
        """Number of policies in the set."""
        return len(self.policies)

    @property
    def enabled_policies(self) -> list[Policy]:
        """Return only enabled policies."""
        return [p for p in self.policies if p.enabled]
