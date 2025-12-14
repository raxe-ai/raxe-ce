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


# Note: BlockAction and ScanPolicy have been removed.
# The advanced policy system in domain/policies/ replaces this functionality.


__all__ = [
    "Detection",
    "ScanRequest",
    "ScanResult",
    "ThreatType",
]
