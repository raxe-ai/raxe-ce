"""Info handlers for JSON-RPC.

Application layer - handles version, health, stats methods.

Provides system information without exposing sensitive data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from raxe.application.jsonrpc.handlers.base import BaseHandler

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe


class InfoHandler(BaseHandler):
    """Handler for info methods: version, health, stats.

    Provides system information without exposing sensitive data
    like file paths, API keys, or internal configuration.

    Methods:
        - handle_version: Returns RAXE version
        - handle_health: Returns health status
        - handle_stats: Returns pipeline statistics
    """

    def __init__(self, raxe: Raxe) -> None:
        """Initialize handler.

        Args:
            raxe: Raxe client instance
        """
        self._raxe = raxe

    def handle(self, params: dict[str, Any] | None) -> dict[str, Any]:
        """Default handle method (not used directly).

        InfoHandler uses specific methods for each info type.
        """
        raise NotImplementedError("Use handle_version, handle_health, or handle_stats")

    def handle_version(self, params: dict[str, Any] | None) -> dict[str, Any]:
        """Return RAXE version information.

        Args:
            params: Request parameters (unused)

        Returns:
            dict: Version information
                - version: str
        """
        import raxe

        return {
            "version": raxe.__version__,
        }

    def handle_health(self, params: dict[str, Any] | None) -> dict[str, Any]:
        """Return health status.

        Args:
            params: Request parameters (unused)

        Returns:
            dict: Health status
                - status: str ("healthy", "ok", or "ready")
        """
        # Basic health check - if we got here, we're healthy
        return {
            "status": "healthy",
        }

    def handle_stats(self, params: dict[str, Any] | None) -> dict[str, Any]:
        """Return pipeline statistics.

        Args:
            params: Request parameters (unused)

        Returns:
            dict: Pipeline statistics
                - rules_loaded: int
                - packs_loaded: int
                - (other safe statistics)

        Note:
            Does not expose sensitive information like file paths
            or internal configuration.
        """
        # Get stats from Raxe client
        stats = getattr(self._raxe, "stats", {})

        # Filter to safe fields only
        safe_fields = {
            "rules_loaded",
            "packs_loaded",
            "patterns_compiled",
            "preload_time_ms",
        }

        # Build safe stats response
        safe_stats = {key: value for key, value in stats.items() if key in safe_fields}

        # Ensure required fields exist
        if "rules_loaded" not in safe_stats:
            safe_stats["rules_loaded"] = 0
        if "packs_loaded" not in safe_stats:
            safe_stats["packs_loaded"] = 0

        return safe_stats


__all__ = ["InfoHandler"]
