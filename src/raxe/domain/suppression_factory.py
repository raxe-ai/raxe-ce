"""Factory for creating SuppressionManager with default infrastructure.

This module provides backward-compatible factory functions that:
- Create the default infrastructure implementations
- Inject them into the domain SuppressionManager
- Maintain the same API as the old SuppressionManager

This makes migration easy - just change:
    from raxe.domain.suppression import SuppressionManager
to:
    from raxe.domain.suppression_factory import create_suppression_manager as SuppressionManager
"""
from pathlib import Path

from raxe.domain.suppression import SuppressionManager as _SuppressionManager
from raxe.infrastructure.suppression.composite_repository import (
    CompositeSuppressionRepository,
)


def create_suppression_manager(
    config_path: Path | None = None,
    db_path: Path | None = None,
    auto_load: bool = True,
) -> _SuppressionManager:
    """Create SuppressionManager with default infrastructure (backward compatible).

    This factory function maintains the same API as the old SuppressionManager
    constructor, but uses Clean Architecture under the hood.

    Args:
        config_path: Path to .raxeignore file (default: ./.raxeignore)
        db_path: Path to SQLite database (default: ~/.raxe/suppressions.db)
        auto_load: Automatically load suppressions from file on init

    Returns:
        SuppressionManager configured with CompositeSuppressionRepository
    """
    repository = CompositeSuppressionRepository(
        config_path=config_path,
        db_path=db_path,
    )

    return _SuppressionManager(
        repository=repository,
        auto_load=auto_load,
    )


# Backward compatibility alias
# This allows: from raxe.domain.suppression_factory import SuppressionManager
SuppressionManager = create_suppression_manager


__all__ = [
    "SuppressionManager",
    "create_suppression_manager",
]
