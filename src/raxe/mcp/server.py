"""
RAXE MCP Server Implementation.

This module implements the Model Context Protocol server for RAXE,
exposing threat detection capabilities to AI assistants.

The server is sync-first and uses the MCP SDK's synchronous APIs.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

# Security limits
MAX_TEXT_LENGTH = 100_000  # 100KB max input
MAX_CONTEXT_LENGTH = 1_000  # 1KB max context
RATE_LIMIT_RPM = 60  # 60 requests per minute per client

# These imports will fail if MCP is not installed
# The CLI entry point checks for this before importing this module
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    Resource,
    TextContent,
    Tool,
)
from pydantic import AnyUrl

from raxe.sdk.client import Raxe


class RateLimiter:
    """Simple in-memory rate limiter for MCP requests."""

    def __init__(self, requests_per_minute: int = RATE_LIMIT_RPM) -> None:
        self.requests_per_minute = requests_per_minute
        self._request_times: dict[str, list[float]] = defaultdict(list)

    def allow(self, client_id: str = "default") -> bool:
        """Check if request is allowed under rate limit.

        Args:
            client_id: Client identifier for per-client limiting

        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()
        window_start = now - 60  # 1 minute window

        # Clean old requests
        self._request_times[client_id] = [
            t for t in self._request_times[client_id] if t > window_start
        ]

        # Check limit
        if len(self._request_times[client_id]) >= self.requests_per_minute:
            return False

        # Record this request
        self._request_times[client_id].append(now)
        return True


class RaxeMCPServer:
    """
    MCP Server for RAXE threat detection.

    Exposes RAXE scanning capabilities as MCP tools that can be
    called by AI assistants like Claude Desktop.
    """

    def __init__(self, verbose: bool = False) -> None:
        """
        Initialize the MCP server.

        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        self.raxe = Raxe()
        self.server = Server("raxe-security")
        self.rate_limiter = RateLimiter()

        # Register handlers
        self._register_tools()
        self._register_resources()
        self._register_prompts()

    def _register_tools(self) -> None:
        """Register MCP tools for threat detection."""

        @self.server.list_tools()
        async def list_tools() -> ListToolsResult:
            return ListToolsResult(
                tools=[
                    Tool(
                        name="scan_prompt",
                        description=(
                            "Scan a prompt or text for security threats including "
                            "prompt injection, jailbreak attempts, and data exfiltration. "
                            "Returns threat detections with severity levels."
                        ),
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "description": "The text/prompt to scan for threats",
                                },
                                "context": {
                                    "type": "string",
                                    "description": "Optional context about where this text came from",
                                },
                            },
                            "required": ["text"],
                        },
                    ),
                    Tool(
                        name="list_threat_families",
                        description="List all available threat detection families (e.g., PI for Prompt Injection)",
                        inputSchema={
                            "type": "object",
                            "properties": {},
                        },
                    ),
                    Tool(
                        name="get_rule_info",
                        description="Get detailed information about a specific detection rule",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "rule_id": {
                                    "type": "string",
                                    "description": "The rule ID (e.g., 'pi-001', 'de-003')",
                                },
                            },
                            "required": ["rule_id"],
                        },
                    ),
                ]
            )

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
            if name == "scan_prompt":
                return await self._handle_scan(arguments)
            elif name == "list_threat_families":
                return await self._handle_list_families()
            elif name == "get_rule_info":
                return await self._handle_rule_info(arguments)
            else:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Unknown tool: {name}")]
                )

    async def _handle_scan(self, arguments: dict[str, Any]) -> CallToolResult:
        """Handle scan_prompt tool call."""
        text = arguments.get("text", "")
        context = arguments.get("context", "")

        # Rate limiting
        if not self.rate_limiter.allow():
            return CallToolResult(
                content=[
                    TextContent(
                        type="text", text="Error: Rate limit exceeded. Please try again later."
                    )
                ]
            )

        # Input validation
        if not text:
            return CallToolResult(
                content=[TextContent(type="text", text="Error: 'text' is required")]
            )

        if len(text) > MAX_TEXT_LENGTH:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Error: Input too large. Maximum {MAX_TEXT_LENGTH:,} characters allowed.",
                    )
                ]
            )

        if context and len(context) > MAX_CONTEXT_LENGTH:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Error: Context too large. Maximum {MAX_CONTEXT_LENGTH:,} characters allowed.",
                    )
                ]
            )

        try:
            result = self.raxe.scan(text)

            if result.is_safe:
                response = "SAFE: No threats detected in the provided text."
            else:
                threats = []
                for detection in result.detections:
                    threats.append(
                        f"- [{detection.severity}] {detection.rule_id}: {detection.description}"
                    )
                threat_list = "\n".join(threats)
                response = f"THREATS DETECTED ({len(result.detections)}):\n{threat_list}"

            if context:
                response = f"Context: {context}\n\n{response}"

            return CallToolResult(content=[TextContent(type="text", text=response)])
        except Exception as e:
            return CallToolResult(content=[TextContent(type="text", text=f"Scan error: {e}")])

    async def _handle_list_families(self) -> CallToolResult:
        """Handle list_threat_families tool call."""
        families = {
            "PI": "Prompt Injection - Attempts to override or manipulate AI instructions",
            "JB": "Jailbreak - Attempts to bypass AI safety constraints",
            "DE": "Data Exfiltration - Attempts to extract sensitive information",
            "RP": "Role Play - Manipulation through persona adoption",
            "CS": "Context Switching - Attempts to change conversation context",
            "SE": "Social Engineering - Psychological manipulation techniques",
            "TA": "Token Abuse - Exploitation of tokenization behaviors",
            "CI": "Code Injection - Attempts to inject malicious code",
        }

        lines = ["Available Threat Families:\n"]
        for code, desc in families.items():
            lines.append(f"- {code}: {desc}")

        return CallToolResult(content=[TextContent(type="text", text="\n".join(lines))])

    async def _handle_rule_info(self, arguments: dict[str, Any]) -> CallToolResult:
        """Handle get_rule_info tool call."""
        rule_id = arguments.get("rule_id", "")

        if not rule_id:
            return CallToolResult(
                content=[TextContent(type="text", text="Error: 'rule_id' is required")]
            )

        # Get rule info from RAXE
        try:
            from raxe.infrastructure.rules.loader import RuleLoader

            loader = RuleLoader()
            rules = loader.load_rules()

            for rule in rules:
                if rule.rule_id.lower() == rule_id.lower():
                    info = [
                        f"Rule: {rule.rule_id}",
                        f"Family: {rule.family}",
                        f"Severity: {rule.severity}",
                        f"Description: {rule.description}",
                    ]
                    return CallToolResult(content=[TextContent(type="text", text="\n".join(info))])

            return CallToolResult(
                content=[TextContent(type="text", text=f"Rule not found: {rule_id}")]
            )
        except Exception as e:
            return CallToolResult(content=[TextContent(type="text", text=f"Error: {e}")])

    def _register_resources(self) -> None:
        """Register MCP resources for RAXE data."""

        @self.server.list_resources()
        async def list_resources() -> ListResourcesResult:
            return ListResourcesResult(
                resources=[
                    Resource(
                        uri=AnyUrl("raxe://version"),
                        name="RAXE Version",
                        description="Current RAXE version information",
                        mimeType="text/plain",
                    ),
                    Resource(
                        uri=AnyUrl("raxe://rules/summary"),
                        name="Rules Summary",
                        description="Summary of available detection rules",
                        mimeType="text/plain",
                    ),
                ]
            )

    def _register_prompts(self) -> None:
        """Register MCP prompts for common security tasks."""

        @self.server.list_prompts()
        async def list_prompts() -> ListPromptsResult:
            return ListPromptsResult(
                prompts=[
                    Prompt(
                        name="security_review",
                        description="Review text for security concerns before processing",
                        arguments=[
                            PromptArgument(
                                name="text",
                                description="The text to review",
                                required=True,
                            ),
                        ],
                    ),
                ]
            )

        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
            if name == "security_review":
                text = (arguments or {}).get("text", "")
                return GetPromptResult(
                    description="Security review prompt",
                    messages=[
                        PromptMessage(
                            role="user",
                            content=TextContent(
                                type="text",
                                text=f"Please use the scan_prompt tool to check this text for security threats before processing:\n\n{text}",
                            ),
                        ),
                    ],
                )
            return GetPromptResult(description="Unknown prompt", messages=[])

    async def run_async(self) -> None:
        """Run the server with stdio transport (async)."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


def create_server(verbose: bool = False) -> RaxeMCPServer:
    """
    Create a new RAXE MCP server instance.

    Args:
        verbose: Enable verbose logging

    Returns:
        Configured RaxeMCPServer instance
    """
    return RaxeMCPServer(verbose=verbose)


def run_server(
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8765,
    verbose: bool = False,
) -> int:
    """
    Run the RAXE MCP server.

    Args:
        transport: Transport protocol ("stdio" or "sse")
        host: Host to bind for SSE transport
        port: Port to bind for SSE transport
        verbose: Enable verbose logging

    Returns:
        Exit code (0 for success)
    """
    import asyncio

    server = create_server(verbose=verbose)

    if transport == "stdio":
        if verbose:
            pass
        asyncio.run(server.run_async())
    elif transport == "sse":
        # SSE transport requires additional setup
        if verbose:
            pass
        # For SSE, we would use starlette/uvicorn
        # This is a placeholder - full SSE implementation would go here
        return 1
    else:
        return 1

    return 0
