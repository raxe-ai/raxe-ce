"""RAXE MCP (Model Context Protocol) Integration.

This module provides two MCP integration modes:

1. **MCP Server** - RAXE exposes threat detection as MCP tools
   that AI assistants can call directly.

2. **MCP Security Gateway** - RAXE acts as a transparent proxy
   between MCP clients and servers, scanning ALL traffic for threats.

Installation:
    pip install raxe[mcp]

Usage (MCP Server - CLI):
    raxe mcp serve                    # Start server with stdio transport
    raxe mcp serve --transport sse    # Start server with SSE transport

Usage (MCP Security Gateway - CLI):
    raxe mcp gateway -u "npx @modelcontextprotocol/server-filesystem /tmp"
    raxe mcp gateway --config mcp-security.yaml

Usage (Python - Server):
    from raxe.mcp import create_server
    server = create_server()
    await server.run_async()

Usage (Python - Gateway):
    from raxe.mcp import create_gateway, GatewayConfig
    config = GatewayConfig.load("mcp-security.yaml")
    gateway = create_gateway(config)
    await gateway.run()

Available Tools (MCP Server):
    - scan_prompt: Scan a prompt for security threats
    - list_threat_families: List available threat detection families
    - get_rule_info: Get details about a specific rule

Security Gateway Features:
    - Intercept and scan tool calls (arguments)
    - Intercept and scan tool responses
    - Intercept and scan resources
    - Intercept and scan prompt templates
    - Configurable block/log/warn policies
    - Per-upstream policy overrides
    - Rate limiting
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from raxe.integrations.availability import require_integration

if TYPE_CHECKING:
    from raxe.mcp.config import GatewayConfig, PolicyConfig, UpstreamConfig
    from raxe.mcp.gateway import RaxeMCPGateway
    from raxe.mcp.server import RaxeMCPServer

__all__ = [
    "GatewayConfig",
    "PolicyConfig",
    "RaxeMCPGateway",
    "RaxeMCPServer",
    "UpstreamConfig",
    "create_gateway",
    "create_server",
    "run_server",
]


def __getattr__(name: str) -> Any:
    """Lazy import to avoid loading MCP dependencies until needed."""
    # Server exports
    if name == "create_server":
        require_integration("mcp")
        from raxe.mcp.server import create_server

        return create_server

    if name == "run_server":
        require_integration("mcp")
        from raxe.mcp.server import run_server

        return run_server

    if name == "RaxeMCPServer":
        require_integration("mcp")
        from raxe.mcp.server import RaxeMCPServer

        return RaxeMCPServer

    # Gateway exports
    if name == "create_gateway":
        require_integration("mcp")
        from raxe.mcp.gateway import create_gateway

        return create_gateway

    if name == "RaxeMCPGateway":
        require_integration("mcp")
        from raxe.mcp.gateway import RaxeMCPGateway

        return RaxeMCPGateway

    # Config exports (no MCP dependency required)
    if name == "GatewayConfig":
        from raxe.mcp.config import GatewayConfig

        return GatewayConfig

    if name == "PolicyConfig":
        from raxe.mcp.config import PolicyConfig

        return PolicyConfig

    if name == "UpstreamConfig":
        from raxe.mcp.config import UpstreamConfig

        return UpstreamConfig

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
