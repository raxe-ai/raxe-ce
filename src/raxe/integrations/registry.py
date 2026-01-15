"""
Integration registry for runtime discovery and configuration.

This module provides metadata about available integrations
and utilities for listing/discovering them.
"""

from __future__ import annotations

from dataclasses import dataclass

from raxe.integrations.availability import (
    IntegrationName,
    get_available_integrations,
)


@dataclass(frozen=True)
class IntegrationInfo:
    """Metadata about an integration."""

    name: IntegrationName
    display_name: str
    install_command: str
    description: str
    documentation_url: str | None = None


INTEGRATION_REGISTRY: dict[IntegrationName, IntegrationInfo] = {
    "mcp": IntegrationInfo(
        name="mcp",
        display_name="MCP Server",
        install_command="pip install raxe[mcp]",
        description="Model Context Protocol server for AI assistants",
        documentation_url="https://docs.raxe.ai/integrations/mcp",
    ),
    "langchain": IntegrationInfo(
        name="langchain",
        display_name="LangChain",
        install_command="pip install raxe[langchain]",
        description="Callback handlers and guardrails for LangChain",
        documentation_url="https://docs.raxe.ai/integrations/langchain",
    ),
    "crewai": IntegrationInfo(
        name="crewai",
        display_name="CrewAI",
        install_command="pip install raxe[crewai]",
        description="Security tools for CrewAI agents",
        documentation_url="https://docs.raxe.ai/integrations/crewai",
    ),
    "autogen": IntegrationInfo(
        name="autogen",
        display_name="AutoGen",
        install_command="pip install raxe[autogen]",
        description="Agent security for Microsoft AutoGen",
        documentation_url="https://docs.raxe.ai/integrations/autogen",
    ),
    "llamaindex": IntegrationInfo(
        name="llamaindex",
        display_name="LlamaIndex",
        install_command="pip install raxe[llamaindex]",
        description="Query engine security for LlamaIndex",
        documentation_url="https://docs.raxe.ai/integrations/llamaindex",
    ),
    "openai": IntegrationInfo(
        name="openai",
        display_name="OpenAI Agents",
        install_command="pip install raxe[openai-agents]",
        description="Function call security for OpenAI Swarm-style agents",
        documentation_url="https://docs.raxe.ai/integrations/openai",
    ),
    "anthropic": IntegrationInfo(
        name="anthropic",
        display_name="Anthropic Claude",
        install_command="pip install raxe[anthropic]",
        description="Tool use security for Claude",
        documentation_url="https://docs.raxe.ai/integrations/anthropic",
    ),
    "litellm": IntegrationInfo(
        name="litellm",
        display_name="LiteLLM",
        install_command="pip install raxe[litellm]",
        description="Security scanning for LiteLLM's unified LLM API",
        documentation_url="https://docs.raxe.ai/integrations/litellm",
    ),
    "dspy": IntegrationInfo(
        name="dspy",
        display_name="DSPy",
        install_command="pip install raxe[dspy]",
        description="Security callbacks and guards for DSPy modules",
        documentation_url="https://docs.raxe.ai/integrations/dspy",
    ),
}


def list_integrations(installed_only: bool = False) -> list[IntegrationInfo]:
    """
    List all available integrations.

    Args:
        installed_only: If True, only return installed integrations

    Returns:
        List of IntegrationInfo objects
    """
    if installed_only:
        available = get_available_integrations()
        return [info for name, info in INTEGRATION_REGISTRY.items() if name in available]

    return list(INTEGRATION_REGISTRY.values())


def get_integration_info(name: IntegrationName) -> IntegrationInfo | None:
    """
    Get info for a specific integration.

    Args:
        name: The integration name

    Returns:
        IntegrationInfo or None if not found
    """
    return INTEGRATION_REGISTRY.get(name)
