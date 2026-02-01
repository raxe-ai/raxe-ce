"""Base handler protocol for JSON-RPC methods.

Application layer - defines the interface for all JSON-RPC handlers.

All handlers must implement the BaseHandler protocol to ensure
consistent behavior and type safety.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseHandler(ABC):
    """Abstract base class for JSON-RPC method handlers.

    All handlers must inherit from this class and implement
    the handle() method.

    Example:
        >>> class MyHandler(BaseHandler):
        ...     def handle(self, params: dict | None) -> Any:
        ...         return {"result": "ok"}
    """

    @abstractmethod
    def handle(self, params: dict[str, Any] | None) -> Any:
        """Handle a JSON-RPC method call.

        Args:
            params: Method parameters (may be None or empty dict)

        Returns:
            Result to include in JSON-RPC response

        Raises:
            ValueError: If required parameters are missing or invalid
            RuntimeError: If an error occurs during processing
        """
        raise NotImplementedError("Subclasses must implement handle()")


__all__ = ["BaseHandler"]
