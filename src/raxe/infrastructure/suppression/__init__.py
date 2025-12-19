"""Infrastructure layer for suppression system - ALL I/O operations.

This module provides concrete implementations of the SuppressionRepository:

YAML format (.raxe/suppressions.yaml) - RECOMMENDED:
- YamlSuppressionRepository: Reads/writes .raxe/suppressions.yaml files
- YamlCompositeSuppressionRepository: Combines YAML + SQLite storage
- CompositeSuppressionRepository: Alias for YamlCompositeSuppressionRepository

Common:
- SQLiteSuppressionRepository: Logs audit entries to SQLite

Note: The legacy .raxeignore file format (FileSuppressionRepository) has been
removed in v1.0. Use .raxe/suppressions.yaml format instead. See UPDATE.md
for migration instructions.
"""
from raxe.infrastructure.suppression.composite_repository import (
    CompositeSuppressionRepository,
)
from raxe.infrastructure.suppression.sqlite_repository import (
    SQLiteSuppressionRepository,
)
from raxe.infrastructure.suppression.yaml_composite_repository import (
    YamlCompositeSuppressionRepository,
)
from raxe.infrastructure.suppression.yaml_repository import (
    YamlSuppressionRepository,
)

__all__ = [
    # Sorted alphabetically for lint compliance
    "CompositeSuppressionRepository",
    "SQLiteSuppressionRepository",
    "YamlCompositeSuppressionRepository",
    "YamlSuppressionRepository",
]
