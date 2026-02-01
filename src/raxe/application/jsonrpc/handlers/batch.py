"""Batch scan handler for JSON-RPC.

Application layer - handles scan_batch method.

Scans multiple prompts in a single request.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from raxe.application.jsonrpc.handlers.base import BaseHandler
from raxe.application.jsonrpc.serializers import ScanResultSerializer

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe

logger = logging.getLogger(__name__)


class BatchScanHandler(BaseHandler):
    """Handler for 'scan_batch' method.

    Scans multiple prompts in a single request.
    Returns a list of results corresponding to each prompt.

    Parameters:
        prompts (list[str], required): List of prompts to scan

    Returns:
        dict: Batch result with:
            - results: list[dict] - One scan result per prompt
            - Each result may contain 'error' if scan failed

    Example:
        >>> handler = BatchScanHandler(raxe)
        >>> result = handler.handle({
        ...     "prompts": ["prompt 1", "prompt 2", "prompt 3"]
        ... })
        >>> len(result["results"])
        3
    """

    def __init__(self, raxe: Raxe) -> None:
        """Initialize handler.

        Args:
            raxe: Raxe client instance for scanning
        """
        self._raxe = raxe
        self._serializer = ScanResultSerializer()

    def handle(self, params: dict[str, Any] | None) -> dict[str, Any]:
        """Handle scan_batch request.

        Args:
            params: Request parameters containing:
                - prompts (list[str], required): List of prompts to scan

        Returns:
            Dictionary with 'results' list

        Raises:
            ValueError: If 'prompts' parameter is missing or invalid
        """
        if not params or "prompts" not in params:
            raise ValueError("Missing required parameter: prompts")

        prompts = params["prompts"]

        if not isinstance(prompts, list):
            raise ValueError("Parameter 'prompts' must be a list")

        # Handle empty list
        if not prompts:
            return {"results": []}

        # Scan each prompt
        results = []
        for i, prompt in enumerate(prompts):
            result = self._scan_single_prompt(prompt, index=i)
            results.append(result)

        return {"results": results}

    def _scan_single_prompt(
        self,
        prompt: str,
        index: int,
    ) -> dict[str, Any]:
        """Scan a single prompt and return result or error.

        Args:
            prompt: Prompt to scan
            index: Index in batch (for error reporting)

        Returns:
            Scan result dict or error dict
        """
        try:
            # Perform scan
            result = self._raxe.scan(prompt)

            # Serialize to privacy-safe format
            return self._serializer.serialize(result)

        except Exception as e:
            # Log error server-side
            logger.error(f"Error scanning prompt at index {index}: {e}")

            # Return error result (without exposing internal details)
            return {
                "has_error": True,
                "error": "Scan failed for this prompt",
                "has_threats": False,
                "severity": None,
                "action": "allow",
                "detections": [],
                "scan_duration_ms": 0.0,
                "prompt_hash": "",
            }


__all__ = ["BatchScanHandler"]
