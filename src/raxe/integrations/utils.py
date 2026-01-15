"""
Utility functions for safe optional imports.

This module provides patterns for handling optional dependencies
in a type-safe and user-friendly way.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, TypeVar

T = TypeVar("T")


@contextmanager
def optional_import(package_name: str, install_hint: str):
    """
    Context manager for optional imports with helpful error messages.

    Usage:
        with optional_import("langchain", "pip install raxe[langchain]"):
            from langchain.callbacks import BaseCallbackHandler

    Args:
        package_name: Name of the package being imported
        install_hint: Installation command to show on error

    Yields:
        None

    Raises:
        ImportError: With helpful message if import fails
    """
    try:
        yield
    except ImportError as e:
        raise ImportError(
            f"Could not import {package_name}. "
            f"This feature requires additional dependencies.\n"
            f"Install with: {install_hint}\n"
            f"Original error: {e}"
        ) from e


def safe_import(
    module_path: str,
    attribute: str | None = None,
    fallback: T | None = None,
) -> T | Any:
    """
    Safely import a module or attribute, returning fallback on failure.

    This is useful when you need a base class or type that may not
    be available, and want to provide a fallback.

    Args:
        module_path: Full module path (e.g., "langchain.callbacks")
        attribute: Optional attribute to get from module
        fallback: Value to return if import fails

    Returns:
        The imported module/attribute or fallback value

    Example:
        # Use object as fallback base class when langchain not installed
        BaseHandler = safe_import(
            "langchain.callbacks.base",
            "BaseCallbackHandler",
            fallback=object
        )

        class MyHandler(BaseHandler):
            ...
    """
    try:
        import importlib

        module = importlib.import_module(module_path)
        if attribute:
            return getattr(module, attribute)
        return module
    except (ImportError, AttributeError):
        return fallback


def get_version(package: str) -> str | None:
    """
    Get the installed version of a package.

    Args:
        package: Package name

    Returns:
        Version string or None if not installed
    """
    try:
        from importlib.metadata import version

        return version(package)
    except Exception:
        return None


def check_version_compatibility(
    package: str,
    min_version: str | None = None,
    max_version: str | None = None,
) -> tuple[bool, str | None]:
    """
    Check if installed package version is compatible.

    Args:
        package: Package name
        min_version: Minimum required version (inclusive)
        max_version: Maximum allowed version (exclusive)

    Returns:
        Tuple of (is_compatible, installed_version)
    """
    from packaging.version import Version

    installed = get_version(package)
    if installed is None:
        return False, None

    try:
        ver = Version(installed)
        if min_version and ver < Version(min_version):
            return False, installed
        if max_version and ver >= Version(max_version):
            return False, installed
        return True, installed
    except Exception:
        # If version parsing fails, assume compatible
        return True, installed
