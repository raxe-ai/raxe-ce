"""JSON-RPC application layer.

Provides JSON-RPC method handling for the RAXE scan API.

This package includes:
- Serializers: Privacy-safe serialization of scan results
- Dispatcher: Routes JSON-RPC requests to handlers
- Handlers: Method implementations (scan, scan_fast, etc.)

Example:
    >>> from raxe import Raxe
    >>> from raxe.application.jsonrpc import (
    ...     JsonRpcDispatcher,
    ...     register_handlers,
    ... )
    >>> from raxe.domain.jsonrpc.models import JsonRpcRequest
    >>>
    >>> # Initialize
    >>> raxe = Raxe()
    >>> register_handlers(raxe)
    >>> dispatcher = JsonRpcDispatcher()
    >>>
    >>> # Handle request
    >>> request = JsonRpcRequest(
    ...     jsonrpc="2.0",
    ...     method="scan",
    ...     id="1",
    ...     params={"prompt": "test"},
    ... )
    >>> response = dispatcher.dispatch(request)
    >>> print(response.result)
"""

from raxe.application.jsonrpc.dispatcher import (
    JsonRpcDispatcher,
    MethodRegistry,
    register_method,
)
from raxe.application.jsonrpc.handlers import (
    BaseHandler,
    BatchScanHandler,
    InfoHandler,
    ScanFastHandler,
    ScanHandler,
    ValidateToolHandler,
    create_handler,
    register_handlers,
)
from raxe.application.jsonrpc.serializers import ScanResultSerializer

__all__ = [
    "BaseHandler",
    "BatchScanHandler",
    "InfoHandler",
    "JsonRpcDispatcher",
    "MethodRegistry",
    "ScanFastHandler",
    "ScanHandler",
    "ScanResultSerializer",
    "ValidateToolHandler",
    "create_handler",
    "register_handlers",
    "register_method",
]
