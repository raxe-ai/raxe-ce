"""
RAXE Framework Integrations.

This module provides integrations with various AI agent frameworks.
Each integration requires optional dependencies to be installed.

Available integrations:
    - mcp: Model Context Protocol server (pip install raxe[mcp])
    - langchain: LangChain callback handlers (pip install raxe[langchain])
    - crewai: CrewAI security tools (pip install raxe[crewai])
    - autogen: AutoGen agent security (pip install raxe[autogen])
    - llamaindex: LlamaIndex query security (pip install raxe[llamaindex])

Usage:
    from raxe.integrations.availability import get_available_integrations
    available = get_available_integrations()
"""

from __future__ import annotations

from raxe.integrations.availability import (
    ANTHROPIC_AVAILABLE,
    AUTOGEN_AVAILABLE,
    CREWAI_AVAILABLE,
    LANGCHAIN_AVAILABLE,
    LLAMAINDEX_AVAILABLE,
    MCP_AVAILABLE,
    OPENAI_AVAILABLE,
    get_available_integrations,
    is_available,
    require_integration,
)
from raxe.integrations.registry import (
    INTEGRATION_REGISTRY,
    IntegrationInfo,
    list_integrations,
)

__all__ = [
    "ANTHROPIC_AVAILABLE",
    "AUTOGEN_AVAILABLE",
    "CREWAI_AVAILABLE",
    # Registry
    "INTEGRATION_REGISTRY",
    "LANGCHAIN_AVAILABLE",
    "LLAMAINDEX_AVAILABLE",
    # Pre-computed flags
    "MCP_AVAILABLE",
    "OPENAI_AVAILABLE",
    "IntegrationInfo",
    "get_available_integrations",
    # Availability checks
    "is_available",
    "list_integrations",
    "require_integration",
]
