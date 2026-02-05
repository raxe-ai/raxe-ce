"""Canonical severity level utilities.

This module provides the single source of truth for severity level
ordering and comparison across the RAXE codebase.

Severity levels from lowest to highest:
    NONE < LOW < MEDIUM < HIGH < CRITICAL
"""

from __future__ import annotations

# Canonical severity ordering (case-insensitive lookup via .upper())
# This is the single source of truth for severity comparison
SEVERITY_ORDER: dict[str, int] = {
    "NONE": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


def get_severity_value(severity: str | None) -> int:
    """Get numeric value for a severity level.

    Args:
        severity: Severity string (case-insensitive) or None

    Returns:
        Numeric severity value (0 for None/unknown)

    Example:
        >>> get_severity_value("HIGH")
        3
        >>> get_severity_value("medium")
        2
        >>> get_severity_value(None)
        0
    """
    if severity is None:
        return 0
    return SEVERITY_ORDER.get(severity.upper(), 0)


def compare_severity(sev1: str | None, sev2: str | None) -> int:
    """Compare two severity levels.

    Args:
        sev1: First severity level
        sev2: Second severity level

    Returns:
        -1 if sev1 < sev2
         0 if sev1 == sev2
         1 if sev1 > sev2

    Example:
        >>> compare_severity("HIGH", "MEDIUM")
        1
        >>> compare_severity("LOW", "CRITICAL")
        -1
    """
    val1 = get_severity_value(sev1)
    val2 = get_severity_value(sev2)
    if val1 < val2:
        return -1
    if val1 > val2:
        return 1
    return 0


def is_severity_at_least(severity: str | None, threshold: str) -> bool:
    """Check if a severity level meets or exceeds a threshold.

    Args:
        severity: Severity level to check
        threshold: Minimum severity threshold

    Returns:
        True if severity >= threshold

    Example:
        >>> is_severity_at_least("CRITICAL", "HIGH")
        True
        >>> is_severity_at_least("MEDIUM", "HIGH")
        False
    """
    return get_severity_value(severity) >= get_severity_value(threshold)


def get_highest_severity(severities: list[str | None]) -> str | None:
    """Get the highest severity from a list.

    Args:
        severities: List of severity strings

    Returns:
        The highest severity, or None if list is empty

    Example:
        >>> get_highest_severity(["LOW", "HIGH", "MEDIUM"])
        "HIGH"
    """
    if not severities:
        return None

    highest: str | None = None
    highest_value = -1

    for sev in severities:
        if sev is not None:
            val = get_severity_value(sev)
            if val > highest_value:
                highest_value = val
                highest = sev.upper() if sev else None

    return highest


__all__ = [
    "SEVERITY_ORDER",
    "compare_severity",
    "get_highest_severity",
    "get_severity_value",
    "is_severity_at_least",
]
