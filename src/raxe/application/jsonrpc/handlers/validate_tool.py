"""Validate tool handler for JSON-RPC.

Application layer - handles scan_tool_call method.

Validates tool calls from AI agents for security threats.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from raxe.application.jsonrpc.handlers.base import BaseHandler
from raxe.application.jsonrpc.serializers import ScanResultSerializer

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe


class ValidateToolHandler(BaseHandler):
    """Handler for 'scan_tool_call' method.

    Scans tool calls from AI agents for security threats.
    Serializes tool_input to text and scans for malicious content.

    Parameters:
        tool_name (str, required): Name of the tool being called
        tool_input (dict, required): Tool input parameters to scan

    Returns:
        dict: Scan result with:
            - has_threats: bool (or is_safe as inverse)
            - severity: str | None
            - action: str
            - detections: list[dict]
            - scan_duration_ms: float
            - prompt_hash: str

    Example:
        >>> handler = ValidateToolHandler(raxe)
        >>> result = handler.handle({
        ...     "tool_name": "execute_command",
        ...     "tool_input": {"command": "rm -rf /"}
        ... })
    """

    def __init__(self, raxe: Raxe) -> None:
        """Initialize handler.

        Args:
            raxe: Raxe client instance for scanning
        """
        self._raxe = raxe
        self._serializer = ScanResultSerializer()

    def handle(self, params: dict[str, Any] | None) -> dict[str, Any]:
        """Handle scan_tool_call request.

        Args:
            params: Request parameters containing:
                - tool_name (str, required): Name of the tool
                - tool_input (dict, required): Tool input to scan

        Returns:
            Privacy-safe scan result dictionary

        Raises:
            ValueError: If required parameters are missing
        """
        if not params:
            raise ValueError("Missing required parameters: tool_name, tool_input")

        if "tool_name" not in params:
            raise ValueError("Missing required parameter: tool_name")

        if "tool_input" not in params:
            raise ValueError("Missing required parameter: tool_input")

        tool_name = params["tool_name"]
        tool_input = params["tool_input"]

        # Serialize tool call to text for scanning
        text_to_scan = self._serialize_tool_call(tool_name, tool_input)

        # Perform scan
        result = self._raxe.scan(text_to_scan)

        # Serialize to privacy-safe format
        serialized = self._serializer.serialize(result)

        # Add is_safe field (inverse of has_threats) for convenience
        serialized["is_safe"] = not serialized["has_threats"]

        return serialized

    def _serialize_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any] | Any,
    ) -> str:
        """Serialize tool call to text for scanning.

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters

        Returns:
            Text representation of tool call for scanning
        """
        # Handle different input types
        if isinstance(tool_input, dict):
            input_str = json.dumps(tool_input, indent=2, default=str)
        elif isinstance(tool_input, str):
            input_str = tool_input
        else:
            input_str = str(tool_input)

        # Format as tool call for scanning
        return f"Tool: {tool_name}\nInput:\n{input_str}"


__all__ = ["ValidateToolHandler"]
