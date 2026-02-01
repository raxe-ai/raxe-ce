"""Abstract base class for JSON-RPC transports.

Transports handle the low-level communication channel for JSON-RPC messages.
All transports must implement read(), write(), and close() methods.

This module follows the SIEM adapter pattern for consistency.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from raxe.domain.jsonrpc.models import JsonRpcRequest, JsonRpcResponse


class Transport(ABC):
    """Abstract base class for JSON-RPC transports.

    Transports handle reading requests and writing responses
    over a communication channel (stdio, socket, HTTP, etc.).

    All transports must implement:
    - read(): Read next JSON-RPC request
    - write(): Write JSON-RPC response
    - close(): Clean up resources

    Example implementation:
        >>> class MyTransport(Transport):
        ...     def read(self) -> JsonRpcRequest | None:
        ...         # Read from channel
        ...         return request
        ...
        ...     def write(self, response: JsonRpcResponse) -> None:
        ...         # Write to channel
        ...         pass
        ...
        ...     def close(self) -> None:
        ...         # Clean up resources
        ...         pass
    """

    @abstractmethod
    def read(self) -> JsonRpcRequest | None:
        """Read the next JSON-RPC request from the transport.

        Returns:
            JsonRpcRequest if a valid request is available,
            None if the transport is closed or EOF reached.

        Raises:
            TransportError: If the data cannot be parsed or is invalid.
        """
        ...

    @abstractmethod
    def write(self, response: JsonRpcResponse) -> None:
        """Write a JSON-RPC response to the transport.

        Args:
            response: The response to write

        Raises:
            TransportError: If writing fails
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """Close the transport and release resources.

        This method should be idempotent - calling it multiple
        times should not raise errors.
        """
        ...

    @property
    def closed(self) -> bool:
        """Check if the transport is closed.

        Returns:
            True if the transport has been closed
        """
        return False  # Subclasses should override

    def __enter__(self) -> Transport:
        """Support context manager protocol."""
        return self

    def __exit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: object) -> None:
        """Close transport on context exit."""
        self.close()


__all__ = ["Transport"]
