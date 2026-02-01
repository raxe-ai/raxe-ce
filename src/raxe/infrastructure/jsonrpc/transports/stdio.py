"""Stdio transport for JSON-RPC.

Reads line-delimited JSON from stdin and writes to stdout.
Used for stdio-based JSON-RPC servers (like MCP servers).
"""

from __future__ import annotations

import json
import sys
from typing import IO, Any

from raxe.domain.jsonrpc.errors import JsonRpcErrorCode
from raxe.domain.jsonrpc.models import JsonRpcError, JsonRpcRequest, JsonRpcResponse
from raxe.infrastructure.jsonrpc.transports.base import Transport


class TransportError(Exception):
    """Error during transport operations.

    Attributes:
        message: Error description
        error_code: JSON-RPC error code
        details: Additional error details
    """

    def __init__(
        self,
        message: str,
        error_code: JsonRpcErrorCode,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize transport error.

        Args:
            message: Error description
            error_code: JSON-RPC error code
            details: Optional additional error details
        """
        super().__init__(message)
        self.error_code = error_code
        self.details = details

    def to_jsonrpc_error(self) -> JsonRpcError:
        """Convert to JSON-RPC error object.

        Returns:
            JsonRpcError representing this transport error
        """
        return JsonRpcError(
            code=self.error_code,
            message=str(self),
            data=self.details,
        )


class StdioTransport(Transport):
    """Transport using stdin/stdout for JSON-RPC communication.

    Reads line-delimited JSON from stdin and writes JSON responses
    to stdout. Each request/response is a single line of JSON.

    This transport is used for stdio-based servers like MCP.

    Example:
        >>> transport = StdioTransport()
        >>> with transport:
        ...     request = transport.read()
        ...     if request:
        ...         response = JsonRpcResponse(...)
        ...         transport.write(response)
    """

    def __init__(
        self,
        stdin: IO[str] | None = None,
        stdout: IO[str] | None = None,
    ) -> None:
        """Initialize stdio transport.

        Args:
            stdin: Input stream (defaults to sys.stdin)
            stdout: Output stream (defaults to sys.stdout)
        """
        self._stdin = stdin or sys.stdin
        self._stdout = stdout or sys.stdout
        self._closed = False

    @property
    def closed(self) -> bool:
        """Check if the transport is closed."""
        return self._closed

    def read(self) -> JsonRpcRequest | None:
        """Read the next JSON-RPC request from stdin.

        Reads one line from stdin, parses it as JSON, and validates
        it as a JSON-RPC request.

        Returns:
            JsonRpcRequest if valid, None on EOF or after close

        Raises:
            TransportError: If JSON is malformed or request is invalid
        """
        if self._closed:
            return None

        # Read lines until we get content or EOF
        while True:
            try:
                line = self._stdin.readline()
            except OSError:
                return None

            # EOF reached
            if not line:
                return None

            # Skip empty lines and whitespace-only lines
            stripped = line.strip()
            if not stripped:
                continue

            # Found content, process it
            break

        # Parse JSON
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as e:
            raise TransportError(
                message=f"Parse error: {e}",
                error_code=JsonRpcErrorCode.PARSE_ERROR,
                details={"line": 1, "column": e.colno if hasattr(e, "colno") else None},
            ) from e

        # Validate it's an object (not array or primitive)
        if not isinstance(data, dict):
            raise TransportError(
                message="Invalid Request: expected JSON object",
                error_code=JsonRpcErrorCode.INVALID_REQUEST,
            )

        # Parse and validate as JSON-RPC request
        try:
            return JsonRpcRequest.from_dict(data)
        except ValueError as e:
            raise TransportError(
                message=f"Invalid Request: {e}",
                error_code=JsonRpcErrorCode.INVALID_REQUEST,
                details={"validation_error": str(e)},
            ) from e

    def write(self, response: JsonRpcResponse) -> None:
        """Write a JSON-RPC response to stdout.

        Serializes the response to JSON and writes it as a single
        line to stdout.

        Args:
            response: The response to write
        """
        if self._closed:
            return

        json_str = json.dumps(response.to_dict(), ensure_ascii=False)
        self._stdout.write(json_str + "\n")
        self._stdout.flush()

    def close(self) -> None:
        """Close the transport.

        Marks the transport as closed. Does not close the underlying
        streams (stdin/stdout are typically shared resources).
        """
        self._closed = True


__all__ = ["StdioTransport", "TransportError"]
