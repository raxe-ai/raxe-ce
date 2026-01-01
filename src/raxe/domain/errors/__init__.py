"""Error catalog and help system for RAXE error codes."""

from raxe.domain.errors.error_catalog import (
    ERROR_CATALOG,
    ErrorInfo,
    get_error_info,
    list_by_category,
    list_error_codes,
)

__all__ = [
    "ERROR_CATALOG",
    "ErrorInfo",
    "get_error_info",
    "list_by_category",
    "list_error_codes",
]
