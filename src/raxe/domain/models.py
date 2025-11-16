"""Core domain models for RAXE CE.

All models are immutable value objects (frozen=True).
Pure domain layer - no I/O operations.
"""
from dataclasses import dataclass
from enum import Enum

# Re-export Detection and ScanResult from executor for convenience
from raxe.domain.engine.executor import Detection, ScanResult


class ThreatType(Enum):
    """Categories of threats.

    Maps to rule families but provides more semantic categorization.
    """
    PROMPT_INJECTION = "PROMPT_INJECTION"
    JAILBREAK = "JAILBREAK"
    PII_LEAK = "PII_LEAK"
    DATA_EXFILTRATION = "DATA_EXFIL"
    SECURITY = "SECURITY"
    QUALITY = "QUALITY"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True)
class ScanRequest:
    """Request to scan text for threats.

    Immutable value object for scan input.

    Attributes:
        text: The text to scan for threats
        context: Optional context metadata (user_id, session_id, etc.)
        rule_filters: Optional list of rule IDs to apply (None = all rules)
        max_text_length: Maximum allowed text length (default 1MB)
    """
    text: str
    context: dict[str, str] | None = None
    rule_filters: list[str] | None = None
    max_text_length: int = 1_000_000  # 1MB default limit

    def __post_init__(self) -> None:
        """Validate request after construction.

        Raises:
            ValueError: If validation fails
        """
        if not self.text:
            raise ValueError("Text cannot be empty")

        if len(self.text) > self.max_text_length:
            raise ValueError(
                f"Text exceeds maximum length of {self.max_text_length} "
                f"(got {len(self.text)} chars)"
            )

        if self.rule_filters is not None and not self.rule_filters:
            raise ValueError("rule_filters cannot be empty list (use None for all rules)")

    @property
    def text_length(self) -> int:
        """Length of text to scan."""
        return len(self.text)

    @property
    def has_filters(self) -> bool:
        """True if rule filters are specified."""
        return self.rule_filters is not None


@dataclass(frozen=True)
class BlockAction(Enum):
    """Actions to take when threat is detected.

    Used for policy enforcement in application layer.
    """
    ALLOW = "ALLOW"           # Log but allow through
    WARN = "WARN"             # Log warning but allow
    BLOCK = "BLOCK"           # Block the request
    CHALLENGE = "CHALLENGE"   # Require additional verification


@dataclass(frozen=True)
class ScanPolicy:
    """Policy for how to handle scan results.

    Defines what to do when threats are detected.
    Used by application layer for enforcement.

    Attributes:
        block_on_critical: Block requests with CRITICAL threats
        block_on_high: Block requests with HIGH threats
        allow_on_low_confidence: Allow if confidence < threshold
        confidence_threshold: Minimum confidence to enforce (0.0-1.0)
        default_action: Action when no policy matches
    """
    block_on_critical: bool = True
    block_on_high: bool = False
    allow_on_low_confidence: bool = True
    confidence_threshold: float = 0.7
    default_action: BlockAction = BlockAction.WARN

    def __post_init__(self) -> None:
        """Validate policy."""
        if not (0.0 <= self.confidence_threshold <= 1.0):
            raise ValueError(
                f"confidence_threshold must be 0-1, got {self.confidence_threshold}"
            )

    def should_block(self, result: ScanResult) -> bool:
        """Determine if scan result should be blocked.

        Args:
            result: Scan result to evaluate

        Returns:
            True if request should be blocked based on policy
        """
        if not result.has_detections:
            return False

        from raxe.domain.rules.models import Severity

        for detection in result.detections:
            # Check confidence threshold first
            if self.allow_on_low_confidence and detection.confidence < self.confidence_threshold:
                continue

            # Check severity-based blocking
            if detection.severity == Severity.CRITICAL and self.block_on_critical:
                return True

            if detection.severity == Severity.HIGH and self.block_on_high:
                return True

        return False

    def get_action(self, result: ScanResult) -> BlockAction:
        """Get action to take for scan result.

        Args:
            result: Scan result to evaluate

        Returns:
            BlockAction to take
        """
        if self.should_block(result):
            return BlockAction.BLOCK

        if result.has_detections:
            return BlockAction.WARN

        return BlockAction.ALLOW


__all__ = [
    "BlockAction",
    "Detection",
    "ScanPolicy",
    "ScanRequest",
    "ScanResult",
    "ThreatType",
]
