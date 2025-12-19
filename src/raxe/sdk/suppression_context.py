"""Scoped suppression context manager for SDK.

Provides a context manager that temporarily applies suppressions
to all scans within its scope.

Example:
    with raxe.suppressed("pi-*", reason="Testing auth flow"):
        result = raxe.scan(text)
        # All scans within this block have pi-* suppressed

Clean Architecture:
    - SDK layer convenience that wraps domain suppression logic
    - Thread-safe using contextvars
"""
from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from raxe.domain.suppression import Suppression, SuppressionAction

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe

# Thread-local storage for scoped suppressions
# Note: We use a factory function to avoid mutable default issues
_scoped_suppressions: contextvars.ContextVar[list[Suppression]] = contextvars.ContextVar(
    "scoped_suppressions"
)


def _get_or_init_scoped_suppressions() -> list[Suppression]:
    """Get scoped suppressions, initializing with empty list if needed."""
    try:
        return _scoped_suppressions.get()
    except LookupError:
        # First access in this context - initialize with empty list
        empty_list: list[Suppression] = []
        _scoped_suppressions.set(empty_list)
        return empty_list


@dataclass(frozen=True)
class ScopedSuppressionConfig:
    """Configuration for scoped suppression.

    Attributes:
        pattern: Rule ID pattern to suppress
        action: Action to take (default: SUPPRESS)
        reason: Reason for suppression
    """

    pattern: str
    action: SuppressionAction = SuppressionAction.SUPPRESS
    reason: str = "Scoped suppression"


def get_scoped_suppressions() -> list[Suppression]:
    """Get current thread's scoped suppressions.

    Returns:
        List of suppressions active in the current context
    """
    return _get_or_init_scoped_suppressions()


def _create_scoped_suppression(
    pattern: str,
    *,
    action: SuppressionAction = SuppressionAction.SUPPRESS,
    reason: str = "Scoped suppression",
) -> Suppression:
    """Create a scoped suppression.

    Args:
        pattern: Rule ID pattern
        action: Action to take
        reason: Reason for suppression

    Returns:
        Suppression object
    """
    return Suppression(
        pattern=pattern,
        reason=reason,
        action=action,
        created_at=datetime.now(timezone.utc).isoformat(),
        created_by="scoped",
    )


@contextmanager
def suppression_scope(
    *patterns: str,
    action: SuppressionAction | str = SuppressionAction.SUPPRESS,
    reason: str = "Scoped suppression",
) -> Iterator[None]:
    """Context manager for scoped suppression.

    All scans within the context will have the specified patterns suppressed.
    This is thread-safe using contextvars.

    Args:
        *patterns: One or more rule ID patterns to suppress
        action: Action to take (SUPPRESS, FLAG, or LOG)
        reason: Reason for suppression

    Yields:
        None

    Example:
        with suppression_scope("pi-*", "jb-*", reason="Testing"):
            result = pipeline.scan(text)
            # pi-* and jb-* patterns are suppressed
    """
    # Convert string action to enum if needed
    if isinstance(action, str):
        action = SuppressionAction(action.upper())

    # Create suppressions for all patterns
    new_suppressions = [
        _create_scoped_suppression(pattern, action=action, reason=reason)
        for pattern in patterns
    ]

    # Get current suppressions and add new ones
    current = _get_or_init_scoped_suppressions()
    combined = list(current) + new_suppressions

    # Set new suppressions
    token = _scoped_suppressions.set(combined)

    try:
        yield
    finally:
        # Restore previous suppressions
        _scoped_suppressions.reset(token)


class SuppressedContext:
    """Context manager bound to a specific Raxe client.

    This is returned by Raxe.suppressed() and provides a more
    convenient API that's bound to the client instance.

    Example:
        raxe = Raxe()
        with raxe.suppressed("pi-*", reason="Testing"):
            result = raxe.scan(text)
    """

    def __init__(
        self,
        client: Raxe,
        *patterns: str,
        action: SuppressionAction | str = SuppressionAction.SUPPRESS,
        reason: str = "Scoped suppression",
    ) -> None:
        """Initialize suppressed context.

        Args:
            client: The Raxe client this context is bound to
            *patterns: Rule ID patterns to suppress
            action: Action to take
            reason: Reason for suppression
        """
        self._client = client
        self._patterns = patterns
        self._action = action
        self._reason = reason
        self._token: contextvars.Token[list[Suppression]] | None = None

    def __enter__(self) -> SuppressedContext:
        """Enter the suppression context."""
        # Convert string action to enum if needed
        action = self._action
        if isinstance(action, str):
            action = SuppressionAction(action.upper())

        # Create suppressions for all patterns
        new_suppressions = [
            _create_scoped_suppression(pattern, action=action, reason=self._reason)
            for pattern in self._patterns
        ]

        # Get current suppressions and add new ones
        current = _get_or_init_scoped_suppressions()
        combined = list(current) + new_suppressions

        # Set new suppressions
        self._token = _scoped_suppressions.set(combined)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit the suppression context."""
        if self._token is not None:
            _scoped_suppressions.reset(self._token)
            self._token = None


__all__ = [
    "ScopedSuppressionConfig",
    "SuppressedContext",
    "get_scoped_suppressions",
    "suppression_scope",
]
