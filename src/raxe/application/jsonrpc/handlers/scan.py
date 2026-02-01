"""Scan handlers for JSON-RPC.

Application layer - handles scan, scan_fast methods.

CRITICAL PRIVACY REQUIREMENTS:
- Never include raw prompt in response
- Never include matched_text in response
- Always use ScanResultSerializer for output
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from raxe.application.jsonrpc.handlers.base import BaseHandler
from raxe.application.jsonrpc.serializers import ScanResultSerializer

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe


class ScanHandler(BaseHandler):
    """Handler for 'scan' method - full L1+L2 scan.

    Scans a prompt for security threats using both rule-based (L1)
    and ML-based (L2) detection.

    Parameters:
        prompt (str, required): Text to scan for threats
        mode (str, optional): Performance mode - "fast", "balanced", "thorough"
        l2_enabled (bool, optional): Enable L2 ML detection (default: True)
        confidence_threshold (float, optional): Min confidence to report (default: 0.5)

    Returns:
        dict: Scan result with privacy-safe fields only:
            - has_threats: bool
            - severity: str | None
            - action: str
            - detections: list[dict]
            - scan_duration_ms: float
            - prompt_hash: str

    Example:
        >>> handler = ScanHandler(raxe)
        >>> result = handler.handle({"prompt": "Hello world"})
        >>> print(result["has_threats"])
        False
    """

    def __init__(self, raxe: Raxe) -> None:
        """Initialize handler.

        Args:
            raxe: Raxe client instance for scanning
        """
        self._raxe = raxe
        self._serializer = ScanResultSerializer()

    def handle(self, params: dict[str, Any] | None) -> dict[str, Any]:
        """Handle scan request.

        Args:
            params: Request parameters containing 'prompt' (required)

        Returns:
            Privacy-safe scan result dictionary

        Raises:
            ValueError: If 'prompt' parameter is missing
        """
        if not params or "prompt" not in params:
            raise ValueError("Missing required parameter: prompt")

        prompt = params["prompt"]

        # Extract optional parameters
        mode = params.get("mode", "balanced")
        l2_enabled = params.get("l2_enabled", True)
        confidence_threshold = params.get("confidence_threshold", 0.5)

        # Perform scan
        result = self._raxe.scan(
            prompt,
            mode=mode,
            l2_enabled=l2_enabled,
            confidence_threshold=confidence_threshold,
        )

        # Serialize to privacy-safe format
        return self._serializer.serialize(result)


class ScanFastHandler(BaseHandler):
    """Handler for 'scan_fast' method - L1 only (no ML).

    Fast scan using only rule-based detection (L1).
    Skips ML-based detection for lower latency.

    Parameters:
        prompt (str, required): Text to scan for threats

    Returns:
        dict: Scan result (same format as ScanHandler)

    Example:
        >>> handler = ScanFastHandler(raxe)
        >>> result = handler.handle({"prompt": "test prompt"})
    """

    def __init__(self, raxe: Raxe) -> None:
        """Initialize handler.

        Args:
            raxe: Raxe client instance for scanning
        """
        self._raxe = raxe
        self._serializer = ScanResultSerializer()

    def handle(self, params: dict[str, Any] | None) -> dict[str, Any]:
        """Handle scan_fast request.

        Args:
            params: Request parameters containing 'prompt' (required)

        Returns:
            Privacy-safe scan result dictionary

        Raises:
            ValueError: If 'prompt' parameter is missing
        """
        if not params or "prompt" not in params:
            raise ValueError("Missing required parameter: prompt")

        prompt = params["prompt"]

        # Perform fast scan (L1 only)
        result = self._raxe.scan(
            prompt,
            mode="fast",
            l2_enabled=False,
        )

        # Serialize to privacy-safe format
        return self._serializer.serialize(result)


__all__ = ["ScanFastHandler", "ScanHandler"]
