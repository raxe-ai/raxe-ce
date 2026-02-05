"""MCP Security Gateway.

The MCP Security Gateway acts as a transparent proxy between MCP clients
(like Claude Desktop) and MCP servers (like filesystem, git, etc.).
It intercepts all traffic and scans for security threats.

Architecture:
    MCP Client (Claude Desktop)
           |
           v
    [RAXE MCP Security Gateway]
    |   - Intercept tool calls
    |   - Scan tool arguments
    |   - Scan tool responses
    |   - Scan resources
    |   - Scan prompts
    |   - Block/log per policy
           |
           v
    MCP Server(s) (filesystem, git, etc.)

Usage:
    # CLI
    raxe mcp gateway --upstream "npx @modelcontextprotocol/server-filesystem /tmp"

    # Python
    from raxe.mcp.gateway import RaxeMCPGateway, GatewayConfig
    gateway = RaxeMCPGateway(config)
    await gateway.run()
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from raxe.domain.severity import is_severity_at_least
from raxe.mcp.config import GatewayConfig, PolicyConfig, UpstreamConfig
from raxe.mcp.interceptors import InterceptionResult, InterceptorChain
from raxe.sdk.agent_scanner import AgentScanner, AgentScannerConfig, create_agent_scanner
from raxe.sdk.client import Raxe
from raxe.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


# Security limits
MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB max message size
RATE_LIMIT_WINDOW = 60  # 1 minute window
MAX_TRACKED_CLIENTS = 10000  # Bound rate limiter memory usage
UPSTREAM_REQUEST_TIMEOUT_SECONDS = 30.0

# JSON-RPC 2.0 Standard Error Codes (per spec)
JSONRPC_ERROR_PARSE = -32700  # Invalid JSON received
JSONRPC_ERROR_INVALID_REQUEST = -32600  # Not a valid request object
JSONRPC_ERROR_METHOD_NOT_FOUND = -32601  # Method not found
JSONRPC_ERROR_INVALID_PARAMS = -32602  # Invalid method parameters
JSONRPC_ERROR_INTERNAL = -32603  # Internal error

# JSON-RPC 2.0 Application Error Codes (-32000 to -32099 reserved for implementation)
# - RATE_LIMIT (-32000): Client exceeded requests/minute limit
# - BLOCKED (-32001): Request blocked due to security threat detection
# - NO_UPSTREAM (-32002): No upstream server configured or available
# - UPSTREAM_FAILED (-32003): Upstream server error or timeout
# - MESSAGE_TOO_LARGE (-32004): Message exceeds MAX_MESSAGE_SIZE
JSONRPC_ERROR_RATE_LIMIT = -32000
JSONRPC_ERROR_BLOCKED = -32001
JSONRPC_ERROR_NO_UPSTREAM = -32002
JSONRPC_ERROR_UPSTREAM_FAILED = -32003
JSONRPC_ERROR_MESSAGE_TOO_LARGE = -32004

# Chunk size for discarding oversized messages (prevents memory DoS)
DISCARD_CHUNK_SIZE = 64 * 1024  # 64KB chunks


@dataclass
class GatewayStats:
    """Statistics for gateway operation.

    Attributes:
        requests_forwarded: Total requests forwarded to upstream
        requests_blocked: Total requests blocked due to threats
        responses_scanned: Total responses scanned
        threats_detected: Total threats detected
        total_scan_time_ms: Total time spent scanning
    """

    requests_forwarded: int = 0
    requests_blocked: int = 0
    responses_scanned: int = 0
    threats_detected: int = 0
    total_scan_time_ms: float = 0.0
    _request_times: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def record_request(self, blocked: bool = False, threat: bool = False) -> None:
        """Record a request."""
        if blocked:
            self.requests_blocked += 1
        else:
            self.requests_forwarded += 1
        if threat:
            self.threats_detected += 1

    def record_scan(self, duration_ms: float) -> None:
        """Record scan duration."""
        self.total_scan_time_ms += duration_ms

    def check_rate_limit(self, client_id: str, limit_rpm: int) -> bool:
        """Check if request is within rate limit.

        Args:
            client_id: Client identifier
            limit_rpm: Requests per minute limit (0 = unlimited)

        Returns:
            True if request is allowed
        """
        if limit_rpm <= 0:
            return True

        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW

        # Bound memory usage by evicting oldest client when at capacity
        if len(self._request_times) >= MAX_TRACKED_CLIENTS and client_id not in self._request_times:
            # Evict client with oldest last request
            oldest_client = min(
                self._request_times.keys(),
                key=lambda k: max(self._request_times[k], default=0),
            )
            del self._request_times[oldest_client]

        # Clean old requests for this client
        self._request_times[client_id] = [
            t for t in self._request_times[client_id] if t > window_start
        ]

        # Check limit
        if len(self._request_times[client_id]) >= limit_rpm:
            return False

        # Record request
        self._request_times[client_id].append(now)
        return True


class UpstreamConnection:
    """Connection to an upstream MCP server.

    Manages the subprocess and communication with a single MCP server.
    """

    def __init__(self, config: UpstreamConfig) -> None:
        """Initialize upstream connection.

        Args:
            config: Configuration for this upstream
        """
        self.config = config
        self._process: subprocess.Popen[bytes] | None = None
        self._read_task: asyncio.Task[None] | None = None
        self._pending_requests: dict[int | str, asyncio.Future[dict[str, Any]]] = {}
        self._next_id = 1
        self._lock = asyncio.Lock()  # Protects _next_id and _pending_requests

    async def start(self) -> None:
        """Start the upstream MCP server process."""
        if self.config.command is None:
            raise ValueError(f"Upstream {self.config.name} has no command configured")

        cmd = [self.config.command, *self.config.args]
        import os

        env = {**dict(os.environ), **self.config.env}

        logger.info(
            "starting_upstream",
            name=self.config.name,
            command=self.config.command,
        )

        self._process = subprocess.Popen(  # noqa: S603 - cmd built from config, not user input
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    async def stop(self) -> None:
        """Stop the upstream MCP server process."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

    async def send_request(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send a request to the upstream and wait for response.

        Args:
            message: JSON-RPC request message

        Returns:
            JSON-RPC response message

        Thread-safety:
            Uses asyncio.Lock to protect concurrent access to _next_id
            and _pending_requests dict.
        """
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Upstream not started")

        # Use lock to protect ID assignment and pending requests dict
        async with self._lock:
            # Assign ID if not present
            if "id" not in message:
                message["id"] = self._next_id
                self._next_id += 1

            request_id = message["id"]

            # Create future for response
            future: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
            self._pending_requests[request_id] = future

        # Send message (outside lock - I/O can be concurrent)
        data = json.dumps(message).encode("utf-8")
        content_length = len(data)
        header = f"Content-Length: {content_length}\r\n\r\n".encode()

        self._process.stdin.write(header + data)
        self._process.stdin.flush()

        # Wait for response (with timeout)
        try:
            return await asyncio.wait_for(future, timeout=UPSTREAM_REQUEST_TIMEOUT_SECONDS)
        finally:
            # Clean up pending request regardless of success/failure/timeout
            async with self._lock:
                self._pending_requests.pop(request_id, None)

    async def read_response(self) -> dict[str, Any] | None:
        """Read a response from the upstream.

        Returns:
            JSON-RPC response message or None if EOF
        """
        if self._process is None or self._process.stdout is None:
            return None

        # Read Content-Length header
        header_line = b""
        while not header_line.endswith(b"\r\n"):
            byte = self._process.stdout.read(1)
            if not byte:
                return None
            header_line += byte

        # Skip empty line
        self._process.stdout.read(2)

        # Parse content length
        if not header_line.startswith(b"Content-Length:"):
            return None

        content_length = int(header_line.split(b":")[1].strip())

        # Read content
        content = self._process.stdout.read(content_length)
        if not content:
            return None

        return json.loads(content.decode("utf-8"))  # type: ignore[no-any-return]


class RaxeMCPGateway:
    """MCP Security Gateway.

    A transparent proxy that sits between MCP clients and servers,
    scanning all traffic for security threats.
    """

    def __init__(
        self,
        config: GatewayConfig | None = None,
        raxe: Raxe | None = None,
    ) -> None:
        """Initialize the gateway.

        Args:
            config: Gateway configuration
            raxe: Optional Raxe client (created if not provided)
        """
        self.config = config or GatewayConfig()
        self._raxe = raxe
        self._upstreams: dict[str, UpstreamConnection] = {}
        self._scanner: AgentScanner | None = None
        self._interceptors: InterceptorChain | None = None
        self._stats = GatewayStats()

        logger.info(
            "gateway_initialized",
            config=self.config.to_dict(),
        )

    @property
    def raxe(self) -> Raxe:
        """Get or create Raxe client."""
        if self._raxe is None:
            self._raxe = Raxe(
                telemetry=self.config.telemetry_enabled,
                l2_enabled=self.config.l2_enabled,
            )
        return self._raxe

    @property
    def scanner(self) -> AgentScanner:
        """Get or create AgentScanner."""
        if self._scanner is None:
            # Always use log mode for the scanner - gateway makes blocking decisions
            # based on its own policy. Using "block" would cause the scanner to
            # throw SecurityException which triggers fail-open behavior.
            scanner_config = AgentScannerConfig(
                scan_prompts=True,
                scan_responses=True,
                on_threat="log",  # Gateway decides blocking, not scanner
            )
            self._scanner = create_agent_scanner(
                self.raxe,
                scanner_config,
                integration_type="mcp_gateway",
            )
        return self._scanner

    @property
    def interceptors(self) -> InterceptorChain:
        """Get or create interceptor chain."""
        if self._interceptors is None:
            self._interceptors = InterceptorChain(self.scanner)
        return self._interceptors

    async def start_upstreams(self) -> None:
        """Start all configured upstream connections."""
        for upstream_config in self.config.upstreams:
            connection = UpstreamConnection(upstream_config)
            await connection.start()
            self._upstreams[upstream_config.name] = connection

    async def stop_upstreams(self) -> None:
        """Stop all upstream connections."""
        for connection in self._upstreams.values():
            await connection.stop()
        self._upstreams.clear()

    def _get_policy(self, upstream_name: str | None = None) -> PolicyConfig:
        """Get policy for an upstream.

        Args:
            upstream_name: Name of upstream (None for default)

        Returns:
            PolicyConfig to use
        """
        if upstream_name:
            for upstream in self.config.upstreams:
                if upstream.name == upstream_name and upstream.policy:
                    return upstream.policy
        return self.config.default_policy

    def _should_block(
        self,
        result: InterceptionResult,
        policy: PolicyConfig,
    ) -> bool:
        """Determine if message should be blocked based on policy.

        Args:
            result: Interception result with scan data
            policy: Policy to apply

        Returns:
            True if message should be blocked
        """
        if not result.scan_result or not result.scan_result.has_threats:
            return False

        if policy.on_threat != "block":
            return False

        # Check severity threshold using canonical severity comparison
        return is_severity_at_least(
            result.scan_result.severity,
            policy.severity_threshold,
        )

    async def handle_request(
        self,
        message: dict[str, Any],
        upstream_name: str | None = None,
        message_size: int | None = None,
    ) -> dict[str, Any]:
        """Handle an incoming MCP request.

        Intercepts the request, scans it, and forwards to upstream if allowed.

        Args:
            message: JSON-RPC request message
            upstream_name: Target upstream (uses first if not specified)
            message_size: Optional size of raw message in bytes

        Returns:
            JSON-RPC response message
        """
        method = message.get("method", "")
        request_id = message.get("id")

        # Enforce message size limit
        if message_size is not None and message_size > MAX_MESSAGE_SIZE:
            logger.warning(
                "message_too_large",
                size=message_size,
                limit=MAX_MESSAGE_SIZE,
                method=method,
            )
            msg = f"Message too large: {message_size} bytes exceeds limit"
            return self._error_response(request_id, JSONRPC_ERROR_MESSAGE_TOO_LARGE, msg)

        # Get policy and upstream
        policy = self._get_policy(upstream_name)

        # Check rate limit
        if not self._stats.check_rate_limit("default", policy.rate_limit_rpm):
            logger.warning("rate_limit_exceeded", method=method)
            return self._error_response(request_id, JSONRPC_ERROR_RATE_LIMIT, "Rate limit exceeded")

        # Intercept and scan request
        start_time = time.perf_counter()
        result = self.interceptors.intercept_request(message)
        scan_duration = (time.perf_counter() - start_time) * 1000
        self._stats.record_scan(scan_duration)

        # Log scan result
        if result.scan_result and result.scan_result.has_threats:
            logger.warning(
                "threat_detected_in_request",
                method=method,
                severity=result.scan_result.severity,
                rules=result.scan_result.rule_ids[:3],
                blocked=self._should_block(result, policy),
            )

        # Check if should block
        if self._should_block(result, policy):
            self._stats.record_request(blocked=True, threat=True)
            return self._error_response(
                request_id,
                JSONRPC_ERROR_BLOCKED,
                f"Request blocked: {result.reason or 'Security threat detected'}",
            )

        # Forward to upstream
        upstream = self._get_upstream(upstream_name)
        if upstream is None:
            self._stats.record_request(blocked=True)
            return self._error_response(
                request_id, JSONRPC_ERROR_NO_UPSTREAM, "No upstream available"
            )

        try:
            response = await upstream.send_request(message)
        except Exception as e:
            # Log full error internally, return sanitized message to client
            logger.error("upstream_error", error=str(e), exc_info=True)
            self._stats.record_request(blocked=True)
            return self._error_response(
                request_id, JSONRPC_ERROR_UPSTREAM_FAILED, "Upstream server error"
            )

        # Intercept and scan response
        start_time = time.perf_counter()
        response_result = self.interceptors.intercept_response(message, response)
        scan_duration = (time.perf_counter() - start_time) * 1000
        self._stats.record_scan(scan_duration)
        self._stats.responses_scanned += 1

        # Log response scan result
        if response_result.scan_result and response_result.scan_result.has_threats:
            logger.warning(
                "threat_detected_in_response",
                method=method,
                severity=response_result.scan_result.severity,
                rules=response_result.scan_result.rule_ids[:3],
                blocked=self._should_block(response_result, policy),
            )
            self._stats.threats_detected += 1

        # Check if response should be blocked
        if self._should_block(response_result, policy):
            self._stats.record_request(blocked=True, threat=True)
            return self._error_response(
                request_id,
                JSONRPC_ERROR_BLOCKED,
                f"Response blocked: {response_result.reason or 'Security threat detected'}",
            )

        self._stats.record_request(
            blocked=False,
            threat=result.scan_result is not None and result.scan_result.has_threats,
        )

        return response

    def _get_upstream(self, name: str | None = None) -> UpstreamConnection | None:
        """Get an upstream connection.

        Args:
            name: Upstream name (uses first if not specified)

        Returns:
            UpstreamConnection or None
        """
        if name and name in self._upstreams:
            return self._upstreams[name]
        if self._upstreams:
            return next(iter(self._upstreams.values()))
        return None

    def _error_response(
        self,
        request_id: int | str | None,
        code: int,
        message: str,
    ) -> dict[str, Any]:
        """Create a JSON-RPC error response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    async def run_stdio(self) -> None:
        """Run gateway with stdio transport.

        Reads JSON-RPC messages from stdin, processes them,
        and writes responses to stdout.
        """
        logger.info("gateway_starting", transport="stdio")

        await self.start_upstreams()

        try:
            # Read from stdin
            reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(reader)
            await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

            writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
                asyncio.streams.FlowControlMixin, sys.stdout
            )
            loop = asyncio.get_event_loop()
            writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, loop)

            while True:
                # Read Content-Length header
                header_line = await reader.readline()
                if not header_line:
                    break

                # Skip empty lines
                while header_line == b"\r\n" or header_line == b"\n":
                    header_line = await reader.readline()

                if not header_line.startswith(b"Content-Length:"):
                    continue

                content_length = int(header_line.split(b":")[1].strip())

                # Enforce message size limit at read time
                if content_length > MAX_MESSAGE_SIZE:
                    logger.warning(
                        "message_too_large",
                        size=content_length,
                        limit=MAX_MESSAGE_SIZE,
                    )
                    # Skip the oversized message by reading in chunks to prevent memory DoS
                    await reader.readline()  # Skip header separator
                    # Read and discard in chunks to avoid allocating full message size
                    remaining = content_length
                    while remaining > 0:
                        chunk_size = min(remaining, DISCARD_CHUNK_SIZE)
                        await reader.read(chunk_size)
                        remaining -= chunk_size
                    # Write error response
                    msg = f"Message too large: {content_length} bytes exceeds limit"
                    error_response = self._error_response(
                        None, JSONRPC_ERROR_MESSAGE_TOO_LARGE, msg
                    )
                    response_data = json.dumps(error_response).encode("utf-8")
                    header = f"Content-Length: {len(response_data)}\r\n\r\n".encode()
                    writer.write(header + response_data)
                    await writer.drain()
                    continue

                # Skip header separator
                await reader.readline()

                # Read content
                content = await reader.read(content_length)
                if not content:
                    break

                # Handle message with error recovery to prevent single message failures
                # from crashing the entire gateway
                try:
                    # Parse message
                    message = json.loads(content.decode("utf-8"))
                    request_id = message.get("id")

                    # Handle message
                    response = await self.handle_request(message, message_size=content_length)
                except json.JSONDecodeError as e:
                    # Log full error internally, return sanitized message to client
                    logger.error("json_parse_error", error=str(e))
                    response = self._error_response(
                        None, JSONRPC_ERROR_PARSE, "Invalid JSON in request"
                    )
                except Exception as e:
                    # Recover from any handler error - log full details, sanitize response
                    logger.error("request_handler_error", error=str(e), exc_info=True)
                    # Try to get request_id if message was parsed
                    try:
                        request_id = message.get("id") if "message" in dir() else None
                    except Exception:
                        request_id = None
                    # Don't leak exception details to client
                    response = self._error_response(
                        request_id, JSONRPC_ERROR_INTERNAL, "Internal server error"
                    )

                # Write response
                response_data = json.dumps(response).encode("utf-8")
                header = f"Content-Length: {len(response_data)}\r\n\r\n".encode()
                writer.write(header + response_data)
                await writer.drain()

        except asyncio.CancelledError:
            logger.info("gateway_cancelled")
        except Exception as e:
            logger.error("gateway_error", error=str(e))
            raise
        finally:
            await self.stop_upstreams()

    async def run(self) -> None:
        """Run the gateway with configured transport."""
        if self.config.listen_transport == "stdio":
            await self.run_stdio()
        else:
            # HTTP transport would go here
            raise NotImplementedError("HTTP transport not yet implemented")

    def get_stats(self) -> dict[str, Any]:
        """Get gateway statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            "requests_forwarded": self._stats.requests_forwarded,
            "requests_blocked": self._stats.requests_blocked,
            "responses_scanned": self._stats.responses_scanned,
            "threats_detected": self._stats.threats_detected,
            "total_scan_time_ms": round(self._stats.total_scan_time_ms, 2),
            "upstreams_connected": len(self._upstreams),
        }


def create_gateway(
    config: GatewayConfig | None = None,
    raxe: Raxe | None = None,
) -> RaxeMCPGateway:
    """Factory function to create MCP Security Gateway.

    Args:
        config: Optional configuration override
        raxe: Optional Raxe client

    Returns:
        Configured RaxeMCPGateway instance
    """
    return RaxeMCPGateway(config, raxe)
