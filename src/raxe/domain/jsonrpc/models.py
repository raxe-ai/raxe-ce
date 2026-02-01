"""JSON-RPC 2.0 domain models.

Immutable value objects for JSON-RPC requests, errors, and responses.
Pure domain layer - no I/O operations.

Following JSON-RPC 2.0 Specification: https://www.jsonrpc.org/specification
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JsonRpcRequest:
    """JSON-RPC 2.0 Request object.

    A Request object represents a remote procedure call.

    Attributes:
        jsonrpc: Must be exactly "2.0"
        method: Name of the method to be invoked
        id: Identifier for the request (None for notifications)
        params: Optional structured parameter values (dict or list)

    Example:
        >>> request = JsonRpcRequest(
        ...     jsonrpc="2.0",
        ...     method="scan",
        ...     id="1",
        ...     params={"prompt": "test"},
        ... )
    """

    jsonrpc: str
    method: str
    id: str | int | None = None
    params: dict[str, Any] | list[Any] | None = None

    def __post_init__(self) -> None:
        """Validate request after construction.

        Raises:
            ValueError: If validation fails
        """
        # Validate jsonrpc version
        if self.jsonrpc != "2.0":
            raise ValueError("jsonrpc must be '2.0'")

        # Validate method
        if not self.method:
            raise ValueError("method cannot be empty")
        if self.method.startswith("rpc."):
            raise ValueError("method names beginning with 'rpc.' are reserved")

        # Validate params type
        if self.params is not None and not isinstance(self.params, dict | list):
            raise ValueError("params must be a dict or list")

        # Validate id type
        if self.id is not None and not isinstance(self.id, str | int):
            raise ValueError("id must be a string, integer, or None")

    @property
    def is_notification(self) -> bool:
        """True if this request is a notification (no id).

        Notifications do not expect a response.
        """
        return self.id is None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON encoding.

        Omits None values for clean JSON output per spec.

        Returns:
            Dictionary representation of the request
        """
        result: dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
        }

        # Only include id if not a notification
        if self.id is not None:
            result["id"] = self.id

        # Only include params if present
        if self.params is not None:
            result["params"] = self.params

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JsonRpcRequest:
        """Deserialize from dictionary.

        Args:
            data: Dictionary representation of a request

        Returns:
            JsonRpcRequest instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        return cls(
            jsonrpc=data.get("jsonrpc", ""),
            method=data.get("method", ""),
            id=data.get("id"),
            params=data.get("params"),
        )


@dataclass(frozen=True)
class JsonRpcError:
    """JSON-RPC 2.0 Error object.

    Represents an error that occurred during a request.

    Attributes:
        code: Integer error code
        message: Short error description
        data: Optional additional error data

    Error Code Ranges:
        -32700: Parse error
        -32600: Invalid Request
        -32601: Method not found
        -32602: Invalid params
        -32603: Internal error
        -32000 to -32099: Server error (reserved for implementation)
    """

    code: int
    message: str
    data: Any = None

    def __post_init__(self) -> None:
        """Validate error after construction.

        Raises:
            TypeError: If code or message have invalid types
            ValueError: If message is empty
        """
        if not isinstance(self.code, int):
            raise TypeError("code must be an integer")
        if not isinstance(self.message, str):
            raise TypeError("message must be a string")
        if not self.message:
            raise ValueError("message cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON encoding.

        Returns:
            Dictionary representation of the error
        """
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }

        if self.data is not None:
            result["data"] = self.data

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JsonRpcError:
        """Deserialize from dictionary.

        Args:
            data: Dictionary representation of an error

        Returns:
            JsonRpcError instance
        """
        return cls(
            code=data["code"],
            message=data["message"],
            data=data.get("data"),
        )


# Sentinel value to distinguish "not provided" from "explicitly None"
_NOT_PROVIDED = object()


@dataclass(frozen=True)
class JsonRpcResponse:
    """JSON-RPC 2.0 Response object.

    A Response object represents the result of a request.
    Must have either result OR error, never both.

    Attributes:
        jsonrpc: Must be exactly "2.0"
        id: Request identifier this response corresponds to
        result: Result of successful request (any type, including None)
        error: Error object if request failed

    Example:
        >>> # Success response
        >>> response = JsonRpcResponse(
        ...     jsonrpc="2.0",
        ...     id="1",
        ...     result={"status": "ok"},
        ... )
        >>> response.is_success
        True
    """

    jsonrpc: str
    id: str | int | None
    result: Any = _NOT_PROVIDED
    error: JsonRpcError | None = None

    def __post_init__(self) -> None:
        """Validate response after construction.

        Raises:
            ValueError: If validation fails
            TypeError: If error is not a JsonRpcError
        """
        # Validate jsonrpc version
        if self.jsonrpc != "2.0":
            raise ValueError("jsonrpc must be '2.0'")

        # Validate id type
        if self.id is not None and not isinstance(self.id, str | int):
            raise ValueError("id must be a string, integer, or None")

        # Validate mutual exclusion
        has_result = self.result is not _NOT_PROVIDED
        has_error = self.error is not None

        if has_result and has_error:
            raise ValueError("result and error are mutually exclusive")

        # Validate error type
        if has_error and not isinstance(self.error, JsonRpcError):
            raise TypeError("error must be a JsonRpcError")

        # Normalize result field:
        # - For error responses: result should be None
        # - For success responses without explicit result: result should be None
        if not has_result:
            # Use object.__setattr__ to bypass frozen
            object.__setattr__(self, "result", None)

    @property
    def is_success(self) -> bool:
        """True if this is a successful response (has result, no error)."""
        return self.error is None

    @property
    def is_error(self) -> bool:
        """True if this is an error response."""
        return self.error is not None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON encoding.

        Returns:
            Dictionary representation of the response
        """
        result_dict: dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
        }

        if self.is_error:
            result_dict["error"] = self.error.to_dict()  # type: ignore[union-attr]
        else:
            result_dict["result"] = self.result

        return result_dict

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JsonRpcResponse:
        """Deserialize from dictionary.

        Args:
            data: Dictionary representation of a response

        Returns:
            JsonRpcResponse instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        error_data = data.get("error")
        error = JsonRpcError.from_dict(error_data) if error_data else None

        # Check if result key exists (even if None)
        if "result" in data:
            return cls(
                jsonrpc=data.get("jsonrpc", ""),
                id=data.get("id"),
                result=data["result"],
                error=error,
            )
        else:
            return cls(
                jsonrpc=data.get("jsonrpc", ""),
                id=data.get("id"),
                error=error,
            )


__all__ = [
    "JsonRpcError",
    "JsonRpcRequest",
    "JsonRpcResponse",
]
