"""JSON-RPC method handlers.

Application layer - handlers for JSON-RPC methods.

This module exports:
- BaseHandler: Abstract base class for handlers
- ScanHandler: Handler for 'scan' method
- ScanFastHandler: Handler for 'scan_fast' method
- ValidateToolHandler: Handler for 'scan_tool_call' method
- BatchScanHandler: Handler for 'scan_batch' method
- InfoHandler: Handler for 'version', 'health', 'stats' methods
- register_handlers: Function to register all handlers with dispatcher
- create_handler: Factory function to create handlers by name
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from raxe.application.jsonrpc.handlers.base import BaseHandler
from raxe.application.jsonrpc.handlers.batch import BatchScanHandler
from raxe.application.jsonrpc.handlers.info import InfoHandler
from raxe.application.jsonrpc.handlers.scan import ScanFastHandler, ScanHandler
from raxe.application.jsonrpc.handlers.validate_tool import ValidateToolHandler

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe


def register_handlers(raxe: Raxe) -> None:
    """Register all JSON-RPC handlers with the method registry.

    Args:
        raxe: Raxe client instance to use for handlers

    Example:
        >>> from raxe import Raxe
        >>> from raxe.application.jsonrpc.handlers import register_handlers
        >>> raxe = Raxe()
        >>> register_handlers(raxe)
        >>> # Now all methods are registered with the dispatcher
    """
    from raxe.application.jsonrpc.dispatcher import MethodRegistry

    registry = MethodRegistry.get_instance()

    # Create handler instances
    scan_handler = ScanHandler(raxe)
    scan_fast_handler = ScanFastHandler(raxe)
    validate_tool_handler = ValidateToolHandler(raxe)
    batch_scan_handler = BatchScanHandler(raxe)
    info_handler = InfoHandler(raxe)

    # Register scan handlers
    registry.register("scan", scan_handler.handle)
    registry.register("scan_fast", scan_fast_handler.handle)
    registry.register("scan_tool_call", validate_tool_handler.handle)
    registry.register("scan_batch", batch_scan_handler.handle)

    # Register info handlers
    registry.register("version", info_handler.handle_version)
    registry.register("health", info_handler.handle_health)
    registry.register("stats", info_handler.handle_stats)


def create_handler(handler_type: str, *, raxe: Raxe) -> BaseHandler:
    """Factory function to create a handler by type name.

    Args:
        handler_type: Type of handler to create
            - "scan": ScanHandler
            - "scan_fast": ScanFastHandler
            - "scan_tool_call" or "validate_tool": ValidateToolHandler
            - "scan_batch" or "batch": BatchScanHandler
            - "info": InfoHandler
        raxe: Raxe client instance

    Returns:
        Handler instance

    Raises:
        ValueError: If handler_type is unknown

    Example:
        >>> handler = create_handler("scan", raxe=raxe)
        >>> isinstance(handler, ScanHandler)
        True
    """
    # Map of handler types to their classes
    # Using type: ignore for mypy since all classes are concrete implementations
    handlers: dict[str, type[BaseHandler]] = {
        "scan": ScanHandler,
        "scan_fast": ScanFastHandler,
        "scan_tool_call": ValidateToolHandler,
        "validate_tool": ValidateToolHandler,
        "scan_batch": BatchScanHandler,
        "batch": BatchScanHandler,
        "info": InfoHandler,
    }

    if handler_type not in handlers:
        available = ", ".join(sorted(handlers.keys()))
        raise ValueError(f"unknown handler type: {handler_type}. Available types: {available}")

    handler_class = handlers[handler_type]
    return handler_class(raxe)  # type: ignore[call-arg]


__all__ = [
    "BaseHandler",
    "BatchScanHandler",
    "InfoHandler",
    "ScanFastHandler",
    "ScanHandler",
    "ValidateToolHandler",
    "create_handler",
    "register_handlers",
]
