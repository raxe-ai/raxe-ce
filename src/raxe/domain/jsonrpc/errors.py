"""JSON-RPC 2.0 error codes and factory functions.

Provides standard error codes per JSON-RPC 2.0 specification
and factory functions for creating error objects.

Error Code Ranges:
    -32700: Parse error - Invalid JSON was received
    -32600: Invalid Request - JSON is not a valid Request object
    -32601: Method not found - Method does not exist
    -32602: Invalid params - Invalid method parameters
    -32603: Internal error - Internal JSON-RPC error
    -32000 to -32099: Server error - Reserved for implementation-defined errors

Reference: https://www.jsonrpc.org/specification
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from raxe.domain.jsonrpc.models import JsonRpcError


class JsonRpcErrorCode(IntEnum):
    """JSON-RPC 2.0 standard error codes.

    Includes standard codes from the spec plus RAXE-specific server errors.

    Attributes:
        PARSE_ERROR: Invalid JSON was received
        INVALID_REQUEST: JSON is not a valid Request object
        METHOD_NOT_FOUND: Method does not exist
        INVALID_PARAMS: Invalid method parameters
        INTERNAL_ERROR: Internal JSON-RPC error
        SERVER_ERROR: Generic server error (implementation-defined)
        THREAT_DETECTED: RAXE-specific - security threat detected

    Example:
        >>> JsonRpcErrorCode.PARSE_ERROR.value
        -32700
        >>> JsonRpcErrorCode.PARSE_ERROR.message
        'Parse error'
    """

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR = -32000
    THREAT_DETECTED = -32001

    @property
    def message(self) -> str:
        """Get the default message for this error code."""
        messages = {
            self.PARSE_ERROR: "Parse error",
            self.INVALID_REQUEST: "Invalid Request",
            self.METHOD_NOT_FOUND: "Method not found",
            self.INVALID_PARAMS: "Invalid params",
            self.INTERNAL_ERROR: "Internal error",
            self.SERVER_ERROR: "Server error",
            self.THREAT_DETECTED: "Threat detected",
        }
        return messages.get(self, "Unknown error")

    @property
    def description(self) -> str:
        """Get a detailed description for this error code."""
        descriptions = {
            self.PARSE_ERROR: "Invalid JSON was received by the server",
            self.INVALID_REQUEST: "The JSON sent is not a valid JSON-RPC Request object",
            self.METHOD_NOT_FOUND: "The requested method does not exist or is not available",
            self.INVALID_PARAMS: "Invalid method parameter(s) were provided",
            self.INTERNAL_ERROR: "An internal JSON-RPC error occurred",
            self.SERVER_ERROR: "A server error occurred during processing",
            self.THREAT_DETECTED: "A security threat was detected in the request",
        }
        return descriptions.get(self, "Unknown error occurred")


def create_parse_error(
    *,
    message: str | None = None,
    data: Any = None,
) -> JsonRpcError:
    """Create a Parse error (-32700).

    Invalid JSON was received by the server.

    Args:
        message: Custom message (defaults to "Parse error")
        data: Additional error data (e.g., parse error details)

    Returns:
        JsonRpcError with code -32700
    """
    return JsonRpcError(
        code=JsonRpcErrorCode.PARSE_ERROR.value,
        message=message or JsonRpcErrorCode.PARSE_ERROR.message,
        data=data,
    )


def create_invalid_request_error(
    *,
    message: str | None = None,
    data: Any = None,
) -> JsonRpcError:
    """Create an Invalid Request error (-32600).

    The JSON sent is not a valid Request object.

    Args:
        message: Custom message (defaults to "Invalid Request")
        data: Additional error data (e.g., validation errors)

    Returns:
        JsonRpcError with code -32600
    """
    return JsonRpcError(
        code=JsonRpcErrorCode.INVALID_REQUEST.value,
        message=message or JsonRpcErrorCode.INVALID_REQUEST.message,
        data=data,
    )


def create_method_not_found_error(
    *,
    message: str | None = None,
    data: Any = None,
) -> JsonRpcError:
    """Create a Method not found error (-32601).

    The method does not exist or is not available.

    Args:
        message: Custom message (defaults to "Method not found")
        data: Additional error data (e.g., method name, suggestions)

    Returns:
        JsonRpcError with code -32601
    """
    return JsonRpcError(
        code=JsonRpcErrorCode.METHOD_NOT_FOUND.value,
        message=message or JsonRpcErrorCode.METHOD_NOT_FOUND.message,
        data=data,
    )


def create_invalid_params_error(
    *,
    message: str | None = None,
    data: Any = None,
) -> JsonRpcError:
    """Create an Invalid params error (-32602).

    Invalid method parameter(s).

    Args:
        message: Custom message (defaults to "Invalid params")
        data: Additional error data (e.g., validation errors)

    Returns:
        JsonRpcError with code -32602
    """
    return JsonRpcError(
        code=JsonRpcErrorCode.INVALID_PARAMS.value,
        message=message or JsonRpcErrorCode.INVALID_PARAMS.message,
        data=data,
    )


def create_internal_error(
    *,
    message: str | None = None,
    data: Any = None,
) -> JsonRpcError:
    """Create an Internal error (-32603).

    Internal JSON-RPC error.

    Note: Be careful not to expose sensitive information (stack traces)
    in the data field for production use.

    Args:
        message: Custom message (defaults to "Internal error")
        data: Additional error data (e.g., error tracking ID)

    Returns:
        JsonRpcError with code -32603
    """
    return JsonRpcError(
        code=JsonRpcErrorCode.INTERNAL_ERROR.value,
        message=message or JsonRpcErrorCode.INTERNAL_ERROR.message,
        data=data,
    )


def create_server_error(
    *,
    code: int | None = None,
    message: str | None = None,
    data: Any = None,
) -> JsonRpcError:
    """Create a Server error (reserved range -32000 to -32099).

    Server errors are reserved for implementation-defined server errors.

    Args:
        code: Error code in range -32000 to -32099 (defaults to -32000)
        message: Custom message (defaults to "Server error")
        data: Additional error data

    Returns:
        JsonRpcError with code in server error range

    Raises:
        ValueError: If code is outside the reserved range
    """
    error_code = code if code is not None else JsonRpcErrorCode.SERVER_ERROR.value

    # Validate code is in reserved range
    if not (-32099 <= error_code <= -32000):
        raise ValueError(f"code must be in range -32099 to -32000, got {error_code}")

    return JsonRpcError(
        code=error_code,
        message=message or JsonRpcErrorCode.SERVER_ERROR.message,
        data=data,
    )


def create_threat_detected_error(
    *,
    message: str | None = None,
    data: Any = None,
) -> JsonRpcError:
    """Create a Threat detected error (-32001).

    RAXE-specific error indicating a security threat was detected.

    Args:
        message: Custom message (defaults to "Threat detected")
        data: Threat information (rule_id, severity, family)
              Note: Should NOT include matched_text or prompt (privacy)

    Returns:
        JsonRpcError with code -32001
    """
    return JsonRpcError(
        code=JsonRpcErrorCode.THREAT_DETECTED.value,
        message=message or JsonRpcErrorCode.THREAT_DETECTED.message,
        data=data,
    )


__all__ = [
    "JsonRpcErrorCode",
    "create_internal_error",
    "create_invalid_params_error",
    "create_invalid_request_error",
    "create_method_not_found_error",
    "create_parse_error",
    "create_server_error",
    "create_threat_detected_error",
]
