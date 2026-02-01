"""JSON-RPC 2.0 domain layer.

Provides immutable value objects for JSON-RPC 2.0 protocol:
- JsonRpcRequest: Request object (method call or notification)
- JsonRpcError: Error object with code, message, and optional data
- JsonRpcResponse: Response object (success result or error)

Plus error code definitions and factory functions for creating errors.

This is a pure domain layer with no I/O operations.

Reference: https://www.jsonrpc.org/specification
"""

from raxe.domain.jsonrpc.errors import (
    JsonRpcErrorCode,
    create_internal_error,
    create_invalid_params_error,
    create_invalid_request_error,
    create_method_not_found_error,
    create_parse_error,
    create_server_error,
    create_threat_detected_error,
)
from raxe.domain.jsonrpc.models import (
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
)

__all__ = [
    "JsonRpcError",
    "JsonRpcErrorCode",
    "JsonRpcRequest",
    "JsonRpcResponse",
    "create_internal_error",
    "create_invalid_params_error",
    "create_invalid_request_error",
    "create_method_not_found_error",
    "create_parse_error",
    "create_server_error",
    "create_threat_detected_error",
]
