"""
RAXE MCP (Model Context Protocol) Server.

This module provides an MCP server that exposes RAXE's threat detection
capabilities to AI assistants like Claude Desktop and IDE extensions.

Installation:
    pip install raxe[mcp]

Usage (CLI):
    raxe-mcp                    # Start server with stdio transport
    raxe-mcp --transport sse    # Start server with SSE transport
    raxe-mcp --port 8765        # Specify port for HTTP transport

Usage (Python):
    from raxe.mcp import create_server
    server = create_server()
    server.run()

Available Tools:
    - scan_prompt: Scan a prompt for security threats
    - get_scan_result: Get detailed result for a previous scan
    - list_rules: List available detection rules
    - get_rule_info: Get details about a specific rule

Available Resources:
    - raxe://rules/{family}: Detection rules by family
    - raxe://stats: Current scan statistics
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from raxe.integrations.availability import require_integration

if TYPE_CHECKING:
    from raxe.mcp.server import RaxeMCPServer

__all__ = ["create_server", "run_server", "RaxeMCPServer"]


def __getattr__(name: str):
    """Lazy import to avoid loading MCP dependencies until needed."""
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

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
