"""Infrastructure layer for suppression system - ALL I/O operations.

This module provides concrete implementations of the SuppressionRepository:
- FileSuppressionRepository: Reads/writes .raxeignore files
- SQLiteSuppressionRepository: Logs audit entries to SQLite
- CompositeSuppressionRepository: Combines file + SQLite storage
"""
from raxe.infrastructure.suppression.composite_repository import (
    CompositeSuppressionRepository,
)
from raxe.infrastructure.suppression.file_repository import FileSuppressionRepository
from raxe.infrastructure.suppression.sqlite_repository import (
    SQLiteSuppressionRepository,
)

__all__ = [
    "CompositeSuppressionRepository",
    "FileSuppressionRepository",
    "SQLiteSuppressionRepository",
]
