"""JSON-RPC method dispatcher.

Application layer - routes JSON-RPC requests to handlers.

This module provides:
- MethodRegistry: Singleton registry for method handlers
- JsonRpcDispatcher: Routes requests to correct handler
- register_method: Decorator for registering handlers

Thread-safe implementation for concurrent request handling.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from difflib import get_close_matches
from typing import Any

from raxe.domain.jsonrpc.errors import (
    create_internal_error,
    create_method_not_found_error,
)
from raxe.domain.jsonrpc.models import JsonRpcRequest, JsonRpcResponse

logger = logging.getLogger(__name__)

# Type alias for handler functions
HandlerFunc = Callable[[dict[str, Any] | None], Any]


class MethodRegistry:
    """Singleton registry for JSON-RPC method handlers.

    Thread-safe registry that maps method names to handler functions.

    Example:
        >>> registry = MethodRegistry.get_instance()
        >>> registry.register("scan", scan_handler)
        >>> handler = registry.get_handler("scan")
        >>> result = handler({"prompt": "test"})
    """

    _instance: MethodRegistry | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        """Initialize registry (use get_instance() instead)."""
        self._handlers: dict[str, HandlerFunc] = {}
        self._handler_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> MethodRegistry:
        """Get singleton instance of MethodRegistry.

        Thread-safe singleton pattern.

        Returns:
            The singleton MethodRegistry instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing only).

        Warning:
            This is intended for testing purposes only.
            Do not use in production code.
        """
        with cls._lock:
            cls._instance = None

    def register(self, method: str, handler: HandlerFunc) -> None:
        """Register a handler for a method.

        If a handler already exists for the method, it will be replaced.

        Args:
            method: Method name (e.g., "scan", "scan_fast")
            handler: Callable that handles the method

        Example:
            >>> registry.register("scan", lambda p: {"result": "ok"})
        """
        with self._handler_lock:
            self._handlers[method] = handler
            logger.debug(f"Registered handler for method: {method}")

    def unregister(self, method: str) -> None:
        """Unregister a method handler.

        Args:
            method: Method name to unregister

        Note:
            Does nothing if method is not registered.
        """
        with self._handler_lock:
            if method in self._handlers:
                del self._handlers[method]
                logger.debug(f"Unregistered handler for method: {method}")

    def get_handler(self, method: str) -> HandlerFunc | None:
        """Get handler for a method.

        Args:
            method: Method name

        Returns:
            Handler function or None if not found
        """
        with self._handler_lock:
            return self._handlers.get(method)

    def has_method(self, method: str) -> bool:
        """Check if a method is registered.

        Args:
            method: Method name

        Returns:
            True if method is registered
        """
        with self._handler_lock:
            return method in self._handlers

    def list_methods(self) -> list[str]:
        """List all registered methods.

        Returns:
            List of registered method names
        """
        with self._handler_lock:
            return list(self._handlers.keys())

    def get_similar_methods(self, method: str, n: int = 3) -> list[str]:
        """Get similar method names (for error suggestions).

        Args:
            method: Method name to find similar matches for
            n: Maximum number of suggestions

        Returns:
            List of similar method names
        """
        with self._handler_lock:
            methods = list(self._handlers.keys())
            return get_close_matches(method, methods, n=n, cutoff=0.4)


def register_method(method: str) -> Callable[[HandlerFunc], HandlerFunc]:
    """Decorator to register a function as a method handler.

    Args:
        method: Method name to register

    Returns:
        Decorator function

    Example:
        >>> @register_method("my_method")
        ... def my_handler(params):
        ...     return {"result": "ok"}
    """

    def decorator(func: HandlerFunc) -> HandlerFunc:
        registry = MethodRegistry.get_instance()
        registry.register(method, func)
        return func

    return decorator


class JsonRpcDispatcher:
    """Dispatch JSON-RPC requests to registered handlers.

    Thread-safe dispatcher that routes requests based on method name.

    Example:
        >>> dispatcher = JsonRpcDispatcher()
        >>> request = JsonRpcRequest(jsonrpc="2.0", method="scan", id="1")
        >>> response = dispatcher.dispatch(request)
    """

    def __init__(self, registry: MethodRegistry | None = None) -> None:
        """Initialize dispatcher.

        Args:
            registry: Optional MethodRegistry to use (defaults to singleton)
        """
        self._registry = registry or MethodRegistry.get_instance()

    def dispatch(self, request: JsonRpcRequest) -> JsonRpcResponse | None:
        """Dispatch a single request to its handler.

        Args:
            request: JSON-RPC request to dispatch

        Returns:
            JSON-RPC response, or None for notifications
        """
        # Get handler for method
        handler = self._registry.get_handler(request.method)

        if handler is None:
            return self._method_not_found_response(request)

        try:
            # Call handler with params
            params = request.params if isinstance(request.params, dict) else {}
            result = handler(params)

            # For notifications (no id), we may return None
            if request.is_notification:
                return JsonRpcResponse(
                    jsonrpc="2.0",
                    id=None,
                    result=result,
                )

            return JsonRpcResponse(
                jsonrpc="2.0",
                id=request.id,
                result=result,
            )

        except Exception as e:
            logger.exception(f"Handler error for method {request.method}")
            return self._internal_error_response(request, e)

    def dispatch_batch(
        self,
        requests: list[JsonRpcRequest],
    ) -> list[JsonRpcResponse]:
        """Dispatch a batch of requests.

        Args:
            requests: List of JSON-RPC requests

        Returns:
            List of responses (in same order as requests)
        """
        responses = []
        for request in requests:
            response = self.dispatch(request)
            if response is not None:
                responses.append(response)
        return responses

    def _method_not_found_response(
        self,
        request: JsonRpcRequest,
    ) -> JsonRpcResponse:
        """Create METHOD_NOT_FOUND error response.

        Includes suggestions for similar methods if available.

        Args:
            request: The request with unknown method

        Returns:
            Error response with METHOD_NOT_FOUND code
        """
        # Get suggestions for similar methods
        suggestions = self._registry.get_similar_methods(request.method)

        error_data = None
        if suggestions:
            error_data = {"suggestions": suggestions}

        error = create_method_not_found_error(
            message=f"Method not found: {request.method}",
            data=error_data,
        )

        return JsonRpcResponse(
            jsonrpc="2.0",
            id=request.id,
            error=error,
        )

    def _internal_error_response(
        self,
        request: JsonRpcRequest,
        exception: Exception,
    ) -> JsonRpcResponse:
        """Create INTERNAL_ERROR response.

        CRITICAL: Does NOT expose internal error details to client.
        Error details are logged server-side only.

        Args:
            request: The request that caused the error
            exception: The exception that occurred

        Returns:
            Error response with INTERNAL_ERROR code
        """
        # Log full error details server-side
        logger.error(
            f"Internal error processing {request.method}: {exception!s}",
            exc_info=True,
        )

        # Create generic error (no internal details exposed)
        error = create_internal_error(
            message="Internal error occurred while processing request",
        )

        return JsonRpcResponse(
            jsonrpc="2.0",
            id=request.id,
            error=error,
        )


__all__ = [
    "HandlerFunc",
    "JsonRpcDispatcher",
    "MethodRegistry",
    "register_method",
]
