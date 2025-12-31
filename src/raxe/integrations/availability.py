"""
Feature availability detection for optional dependencies.

This module provides a centralized way to check if optional
dependencies are installed without importing them.

Usage:
    from raxe.integrations.availability import MCP_AVAILABLE, require_integration

    if MCP_AVAILABLE:
        from raxe.mcp import server
    else:
        print("MCP not installed: pip install raxe[mcp]")

    # Or raise helpful error:
    require_integration("mcp")  # Raises ImportError with install hint
"""
from __future__ import annotations

import importlib.util
from functools import lru_cache
from typing import Literal

# Type alias for integration names
IntegrationName = Literal[
    "mcp", "langchain", "crewai", "autogen", "llamaindex", "openai", "anthropic",
    "litellm", "dspy"
]


@lru_cache(maxsize=16)
def is_available(package: str) -> bool:
    """
    Check if a package is available for import.

    Uses importlib.util.find_spec for fast detection without
    actually importing the package.

    Args:
        package: The package name to check

    Returns:
        True if the package is installed and importable
    """
    try:
        return importlib.util.find_spec(package) is not None
    except (ModuleNotFoundError, ValueError):
        return False


# Pre-computed availability checks for common integrations
# These are evaluated once at import time for fast access
MCP_AVAILABLE: bool = is_available("mcp")
LANGCHAIN_AVAILABLE: bool = is_available("langchain")
CREWAI_AVAILABLE: bool = is_available("crewai")
AUTOGEN_AVAILABLE: bool = is_available("pyautogen")
LLAMAINDEX_AVAILABLE: bool = is_available("llama_index")
OPENAI_AVAILABLE: bool = is_available("openai")
ANTHROPIC_AVAILABLE: bool = is_available("anthropic")
LITELLM_AVAILABLE: bool = is_available("litellm")
DSPY_AVAILABLE: bool = is_available("dspy")


def get_available_integrations() -> list[IntegrationName]:
    """
    Get list of all available integrations.

    Returns:
        List of integration names that are installed
    """
    available: list[IntegrationName] = []

    if MCP_AVAILABLE:
        available.append("mcp")
    if LANGCHAIN_AVAILABLE:
        available.append("langchain")
    if CREWAI_AVAILABLE:
        available.append("crewai")
    if AUTOGEN_AVAILABLE:
        available.append("autogen")
    if LLAMAINDEX_AVAILABLE:
        available.append("llamaindex")
    if OPENAI_AVAILABLE:
        available.append("openai")
    if ANTHROPIC_AVAILABLE:
        available.append("anthropic")
    if LITELLM_AVAILABLE:
        available.append("litellm")
    if DSPY_AVAILABLE:
        available.append("dspy")

    return available


def require_integration(name: IntegrationName) -> None:
    """
    Raise ImportError with helpful message if integration is not available.

    Args:
        name: The integration name

    Raises:
        ImportError: If the integration is not installed
    """
    packages: dict[IntegrationName, tuple[str, str]] = {
        "mcp": ("mcp", "raxe[mcp]"),
        "langchain": ("langchain", "raxe[langchain]"),
        "crewai": ("crewai", "raxe[crewai]"),
        "autogen": ("pyautogen", "raxe[autogen]"),
        "llamaindex": ("llama_index", "raxe[llamaindex]"),
        "openai": ("openai", "raxe[openai-agents]"),
        "anthropic": ("anthropic", "raxe[anthropic]"),
        "litellm": ("litellm", "raxe[litellm]"),
        "dspy": ("dspy", "raxe[dspy]"),
    }

    package_name, install_extra = packages[name]

    if not is_available(package_name):
        raise ImportError(
            f"{name.title()} integration requires additional dependencies.\n"
            f"Install with: pip install {install_extra}"
        )


def check_all_integrations() -> dict[IntegrationName, bool]:
    """
    Check availability of all integrations.

    Returns:
        Dictionary mapping integration names to their availability status
    """
    return {
        "mcp": MCP_AVAILABLE,
        "langchain": LANGCHAIN_AVAILABLE,
        "crewai": CREWAI_AVAILABLE,
        "autogen": AUTOGEN_AVAILABLE,
        "llamaindex": LLAMAINDEX_AVAILABLE,
        "openai": OPENAI_AVAILABLE,
        "anthropic": ANTHROPIC_AVAILABLE,
        "litellm": LITELLM_AVAILABLE,
        "dspy": DSPY_AVAILABLE,
    }
