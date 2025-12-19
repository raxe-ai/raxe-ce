"""Factory for creating SuppressionManager with default infrastructure.

This module provides factory functions that:
- Create the default infrastructure implementations
- Inject them into the domain SuppressionManager
- Check for legacy .raxeignore files and warn about migration

Repository configuration:
- YAML (.raxe/suppressions.yaml) - recommended, full-featured
- SQLite - audit logging

Note: The legacy .raxeignore file format was deprecated in v1.0 and has been
removed in v1.0. Use .raxe/suppressions.yaml instead. See UPDATE.md for
migration instructions.
"""
import logging
import warnings
from pathlib import Path

from raxe.domain.suppression import SuppressionManager as _SuppressionManager
from raxe.infrastructure.suppression.composite_repository import (
    CompositeSuppressionRepository,
)
from raxe.infrastructure.suppression.yaml_repository import (
    DEFAULT_SUPPRESSIONS_PATH,
)

logger = logging.getLogger(__name__)


def _check_legacy_raxeignore(yaml_path: Path | None = None) -> None:
    """Check for legacy .raxeignore file and warn user about migration.

    If .raxeignore exists but .raxe/suppressions.yaml does not, logs a
    deprecation warning directing the user to migrate.

    Args:
        yaml_path: Path to the YAML config file to check against.
                  Defaults to ./.raxe/suppressions.yaml
    """
    # Determine paths to check
    if yaml_path is None:
        yaml_path = Path.cwd() / DEFAULT_SUPPRESSIONS_PATH

    # Check for legacy .raxeignore in same parent directory as YAML config
    legacy_path = yaml_path.parent.parent / ".raxeignore"

    # If working with default path, also check cwd
    if yaml_path == Path.cwd() / DEFAULT_SUPPRESSIONS_PATH:
        legacy_path = Path.cwd() / ".raxeignore"

    if legacy_path.exists() and not yaml_path.exists():
        warning_message = (
            f"DEPRECATION WARNING: Found legacy .raxeignore file at {legacy_path}. "
            f"The .raxeignore format has been removed in v1.0. "
            f"Please migrate to .raxe/suppressions.yaml format. "
            f"See UPDATE.md for migration instructions."
        )
        logger.warning(
            "legacy_raxeignore_detected",
            extra={
                "legacy_path": str(legacy_path),
                "yaml_path": str(yaml_path),
                "migration_hint": "Please migrate to .raxe/suppressions.yaml format",
            },
        )
        warnings.warn(warning_message, DeprecationWarning, stacklevel=3)


def create_suppression_manager(
    config_path: Path | None = None,
    db_path: Path | None = None,
    auto_load: bool = True,
) -> _SuppressionManager:
    """Create SuppressionManager with YAML-based configuration.

    This factory creates a SuppressionManager using the recommended
    .raxe/suppressions.yaml format with full features including:
    - Action overrides (SUPPRESS, FLAG, LOG)
    - Expiration dates
    - Better validation and error messages
    - SQLite audit logging

    Note:
        The legacy .raxeignore format has been removed. If a .raxeignore
        file is detected without a corresponding suppressions.yaml, a
        deprecation warning will be logged.

    Args:
        config_path: Path to suppressions.yaml file.
                    Default: ./.raxe/suppressions.yaml
        db_path: Path to SQLite database for audit logging.
                Default: ~/.raxe/suppressions.db
        auto_load: Automatically load suppressions from file on init

    Returns:
        SuppressionManager configured with CompositeSuppressionRepository
    """
    # Check for legacy .raxeignore and warn if found
    _check_legacy_raxeignore(yaml_path=config_path)

    repository = CompositeSuppressionRepository(
        config_path=config_path,
        db_path=db_path,
    )

    return _SuppressionManager(
        repository=repository,
        auto_load=auto_load,
    )


def create_suppression_manager_with_yaml(
    yaml_path: Path | None = None,
    db_path: Path | None = None,
    auto_load: bool = True,
) -> _SuppressionManager:
    """Create SuppressionManager with YAML-based suppression configuration.

    This factory uses the .raxe/suppressions.yaml format which supports:
    - Action overrides (SUPPRESS, FLAG, LOG)
    - Expiration dates
    - Better validation and error messages

    Note:
        This is the same as create_suppression_manager() and is provided
        for API compatibility. Both functions use YAML configuration.

    Args:
        yaml_path: Path to suppressions.yaml file
                  (default: ./.raxe/suppressions.yaml)
        db_path: Path to SQLite database for audit logging
                (default: ~/.raxe/suppressions.db)
        auto_load: Automatically load suppressions from file on init

    Returns:
        SuppressionManager configured with YamlCompositeRepository

    Example:
        ```python
        from raxe.domain.suppression_factory import create_suppression_manager_with_yaml

        manager = create_suppression_manager_with_yaml()
        is_suppressed, reason = manager.is_suppressed("pi-001")
        ```
    """
    from raxe.infrastructure.suppression.yaml_composite_repository import (
        YamlCompositeSuppressionRepository,
    )

    # Check for legacy .raxeignore and warn if found
    _check_legacy_raxeignore(yaml_path=yaml_path)

    repository = YamlCompositeSuppressionRepository(
        yaml_path=yaml_path,
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
    "create_suppression_manager_with_yaml",
]
