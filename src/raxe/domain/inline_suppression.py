"""Inline suppression types for SDK scan() method.

This module provides PURE domain types for inline suppressions passed
directly to scan() calls. These are separate from file-based suppressions
(.raxe/suppressions.yaml) and take precedence over them.

Example:
    # Simple list of patterns
    result = raxe.scan(text, suppress=["pi-001", "jb-*"])

    # With action override
    result = raxe.scan(text, suppress=[
        "pi-001",  # Default SUPPRESS action
        {"pattern": "jb-*", "action": "FLAG", "reason": "Under review"}
    ])

Clean Architecture:
    - This is PURE domain logic
    - No I/O, no file access, no logging
    - Converts inline specs to Suppression objects
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, TypeAlias

from raxe.domain.suppression import (
    Suppression,
    SuppressionAction,
    SuppressionValidationError,
)

# Type alias for inline suppression specification
# Can be either a string pattern or a dict with pattern, action, reason
InlineSuppressionSpec: TypeAlias = str | dict[str, Any]


@dataclass(frozen=True)
class InlineSuppressionConfig:
    """Configuration for an inline suppression.

    Represents a suppression passed directly to scan() rather than
    loaded from a configuration file.

    Attributes:
        pattern: Rule ID pattern (supports wildcards: pi-*, jb-*)
        action: Action to take when matched (default: SUPPRESS)
        reason: Optional reason for suppression
    """

    pattern: str
    action: SuppressionAction = SuppressionAction.SUPPRESS
    reason: str = "Inline suppression"


def parse_inline_suppression(spec: InlineSuppressionSpec) -> Suppression:
    """Parse an inline suppression specification into a Suppression object.

    Accepts either:
    - String pattern: "pi-001" or "jb-*"
    - Dict with full config: {"pattern": "jb-*", "action": "FLAG", "reason": "..."}

    Args:
        spec: Inline suppression specification

    Returns:
        Suppression object ready for use

    Raises:
        SuppressionValidationError: If specification is invalid
    """
    if isinstance(spec, str):
        # Simple string pattern - default to SUPPRESS action
        return Suppression(
            pattern=spec,
            reason="Inline suppression",
            action=SuppressionAction.SUPPRESS,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="inline",
        )

    if isinstance(spec, dict):
        # Dict with full config
        pattern = spec.get("pattern")
        if not pattern:
            raise SuppressionValidationError(
                "Inline suppression dict must have 'pattern' key"
            )

        # Parse action
        action_str = spec.get("action", "SUPPRESS")
        if isinstance(action_str, SuppressionAction):
            action = action_str
        else:
            try:
                action = SuppressionAction(str(action_str).upper())
            except ValueError:
                valid_actions = [a.value for a in SuppressionAction]
                raise SuppressionValidationError(
                    f"Invalid action '{action_str}'. "
                    f"Valid actions: {', '.join(valid_actions)}"
                ) from None

        # Get reason (optional, has default)
        reason = spec.get("reason", "Inline suppression")
        if not reason:
            reason = "Inline suppression"

        return Suppression(
            pattern=str(pattern),
            reason=str(reason),
            action=action,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="inline",
        )

    raise SuppressionValidationError(
        f"Invalid inline suppression type: {type(spec).__name__}. "
        "Expected str or dict."
    )


def parse_inline_suppressions(
    specs: list[InlineSuppressionSpec] | None,
) -> list[Suppression]:
    """Parse a list of inline suppression specifications.

    Args:
        specs: List of inline suppression specs, or None

    Returns:
        List of Suppression objects

    Raises:
        SuppressionValidationError: If any specification is invalid
    """
    if not specs:
        return []

    return [parse_inline_suppression(spec) for spec in specs]


def merge_suppressions(
    config_suppressions: list[Suppression],
    inline_suppressions: list[Suppression],
) -> list[Suppression]:
    """Merge config file suppressions with inline suppressions.

    Inline suppressions take precedence over config file suppressions
    for the same pattern.

    Args:
        config_suppressions: Suppressions from config files
        inline_suppressions: Suppressions passed to scan()

    Returns:
        Merged list with inline taking precedence
    """
    # Build dict with config suppressions first
    merged: dict[str, Suppression] = {}
    for supp in config_suppressions:
        merged[supp.pattern] = supp

    # Override with inline suppressions (they take precedence)
    for supp in inline_suppressions:
        merged[supp.pattern] = supp

    return list(merged.values())


__all__ = [
    "InlineSuppressionConfig",
    "InlineSuppressionSpec",
    "merge_suppressions",
    "parse_inline_suppression",
    "parse_inline_suppressions",
]
