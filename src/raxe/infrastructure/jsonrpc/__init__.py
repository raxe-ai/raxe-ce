"""JSON-RPC infrastructure layer.

Provides transport implementations and server orchestration
for JSON-RPC 2.0 communication.

Components:
- Transport: Abstract base for communication channels
- StdioTransport: Line-delimited JSON over stdin/stdout
- JsonRpcServer: Main server orchestrator
"""

from raxe.infrastructure.jsonrpc.server import JsonRpcServer
from raxe.infrastructure.jsonrpc.transports.base import Transport
from raxe.infrastructure.jsonrpc.transports.stdio import (
    StdioTransport,
    TransportError,
)

__all__ = [
    "JsonRpcServer",
    "StdioTransport",
    "Transport",
    "TransportError",
]
