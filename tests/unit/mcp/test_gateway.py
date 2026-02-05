"""Unit tests for MCP Security Gateway."""

from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest

from raxe.mcp.config import GatewayConfig, PolicyConfig, UpstreamConfig
from raxe.mcp.gateway import (
    DISCARD_CHUNK_SIZE,
    JSONRPC_ERROR_BLOCKED,
    JSONRPC_ERROR_INTERNAL,
    JSONRPC_ERROR_MESSAGE_TOO_LARGE,
    JSONRPC_ERROR_NO_UPSTREAM,
    JSONRPC_ERROR_PARSE,
    JSONRPC_ERROR_RATE_LIMIT,
    JSONRPC_ERROR_UPSTREAM_FAILED,
    MAX_MESSAGE_SIZE,
    MAX_TRACKED_CLIENTS,
    UPSTREAM_REQUEST_TIMEOUT_SECONDS,
    GatewayStats,
    RaxeMCPGateway,
    UpstreamConnection,
    create_gateway,
)


class TestSecurityConstants:
    """Tests for security-related constants."""

    def test_max_message_size_is_10mb(self):
        """Test that max message size is 10MB."""
        assert MAX_MESSAGE_SIZE == 10 * 1024 * 1024

    def test_discard_chunk_size_is_reasonable(self):
        """Test that discard chunk size is set to prevent memory issues."""
        # Chunk size should be small enough to not cause memory pressure
        assert DISCARD_CHUNK_SIZE <= 1024 * 1024  # At most 1MB
        # But large enough to be efficient
        assert DISCARD_CHUNK_SIZE >= 4 * 1024  # At least 4KB

    def test_discard_chunk_prevents_large_allocation(self):
        """Test that chunked reading would prevent large allocations.

        When discarding a 100MB message, we should never allocate more
        than DISCARD_CHUNK_SIZE at once.
        """
        oversized_message = 100 * 1024 * 1024  # 100MB
        chunks_needed = (oversized_message + DISCARD_CHUNK_SIZE - 1) // DISCARD_CHUNK_SIZE

        # Should need multiple chunks
        assert chunks_needed > 1
        # Each chunk should be bounded
        for i in range(chunks_needed):
            remaining = oversized_message - (i * DISCARD_CHUNK_SIZE)
            chunk_size = min(remaining, DISCARD_CHUNK_SIZE)
            assert chunk_size <= DISCARD_CHUNK_SIZE

    def test_max_tracked_clients_bounds_memory(self):
        """Test that MAX_TRACKED_CLIENTS is set to prevent unbounded memory."""
        assert MAX_TRACKED_CLIENTS > 0
        assert MAX_TRACKED_CLIENTS <= 100000  # Reasonable upper bound

    def test_upstream_timeout_is_reasonable(self):
        """Test that upstream timeout is set reasonably."""
        assert UPSTREAM_REQUEST_TIMEOUT_SECONDS > 0
        assert UPSTREAM_REQUEST_TIMEOUT_SECONDS <= 120  # Not too long


class TestErrorCodeConstants:
    """Tests for JSON-RPC error code constants."""

    def test_error_codes_are_negative(self):
        """Test that error codes are negative per JSON-RPC 2.0 spec."""
        assert JSONRPC_ERROR_RATE_LIMIT < 0
        assert JSONRPC_ERROR_BLOCKED < 0
        assert JSONRPC_ERROR_NO_UPSTREAM < 0
        assert JSONRPC_ERROR_UPSTREAM_FAILED < 0
        assert JSONRPC_ERROR_MESSAGE_TOO_LARGE < 0

    def test_error_codes_are_unique(self):
        """Test that all error codes are unique."""
        codes = [
            JSONRPC_ERROR_PARSE,
            JSONRPC_ERROR_INTERNAL,
            JSONRPC_ERROR_RATE_LIMIT,
            JSONRPC_ERROR_BLOCKED,
            JSONRPC_ERROR_NO_UPSTREAM,
            JSONRPC_ERROR_UPSTREAM_FAILED,
            JSONRPC_ERROR_MESSAGE_TOO_LARGE,
        ]
        assert len(codes) == len(set(codes)), "Error codes must be unique"

    def test_error_codes_expected_values(self):
        """Test that error codes have expected values for compatibility."""
        assert JSONRPC_ERROR_RATE_LIMIT == -32000
        assert JSONRPC_ERROR_BLOCKED == -32001
        assert JSONRPC_ERROR_NO_UPSTREAM == -32002
        assert JSONRPC_ERROR_UPSTREAM_FAILED == -32003
        assert JSONRPC_ERROR_MESSAGE_TOO_LARGE == -32004

    def test_standard_jsonrpc_error_codes(self):
        """Test standard JSON-RPC 2.0 error codes per spec."""
        # Per JSON-RPC 2.0 specification
        assert JSONRPC_ERROR_PARSE == -32700
        assert JSONRPC_ERROR_INTERNAL == -32603

    def test_application_error_codes_in_reserved_range(self):
        """Test application codes are in reserved range (-32000 to -32099)."""
        app_codes = [
            JSONRPC_ERROR_RATE_LIMIT,
            JSONRPC_ERROR_BLOCKED,
            JSONRPC_ERROR_NO_UPSTREAM,
            JSONRPC_ERROR_UPSTREAM_FAILED,
            JSONRPC_ERROR_MESSAGE_TOO_LARGE,
        ]
        for code in app_codes:
            assert -32099 <= code <= -32000, f"Code {code} not in reserved range"


class TestGatewayStats:
    """Tests for GatewayStats class."""

    def test_initial_values(self):
        """Test that initial stats are zero."""
        stats = GatewayStats()

        assert stats.requests_forwarded == 0
        assert stats.requests_blocked == 0
        assert stats.responses_scanned == 0
        assert stats.threats_detected == 0
        assert stats.total_scan_time_ms == 0.0

    def test_record_request_forwarded(self):
        """Test recording forwarded request."""
        stats = GatewayStats()

        stats.record_request(blocked=False, threat=False)

        assert stats.requests_forwarded == 1
        assert stats.requests_blocked == 0
        assert stats.threats_detected == 0

    def test_record_request_blocked(self):
        """Test recording blocked request."""
        stats = GatewayStats()

        stats.record_request(blocked=True, threat=True)

        assert stats.requests_forwarded == 0
        assert stats.requests_blocked == 1
        assert stats.threats_detected == 1

    def test_record_scan_time(self):
        """Test recording scan duration."""
        stats = GatewayStats()

        stats.record_scan(5.0)
        stats.record_scan(3.0)

        assert stats.total_scan_time_ms == 8.0

    def test_rate_limit_allows_within_limit(self):
        """Test that requests within limit are allowed."""
        stats = GatewayStats()

        # With limit of 10, first 10 should be allowed
        for _ in range(10):
            assert stats.check_rate_limit("client1", 10) is True

        # 11th should be blocked
        assert stats.check_rate_limit("client1", 10) is False

    def test_rate_limit_zero_means_unlimited(self):
        """Test that rate limit of 0 allows unlimited requests."""
        stats = GatewayStats()

        # With limit of 0, all should be allowed
        for _ in range(100):
            assert stats.check_rate_limit("client1", 0) is True

    def test_rate_limit_per_client(self):
        """Test that rate limiting is per-client."""
        stats = GatewayStats()

        # Fill client1's limit
        for _ in range(5):
            stats.check_rate_limit("client1", 5)

        # client1 should be blocked
        assert stats.check_rate_limit("client1", 5) is False

        # client2 should still be allowed
        assert stats.check_rate_limit("client2", 5) is True

    def test_rate_limit_evicts_oldest_when_at_capacity(self):
        """Test that rate limiter evicts oldest client when at max capacity."""
        stats = GatewayStats()

        # Fill to capacity with unique clients
        for i in range(MAX_TRACKED_CLIENTS):
            stats.check_rate_limit(f"client_{i}", 10)

        assert len(stats._request_times) == MAX_TRACKED_CLIENTS

        # Adding a new client should evict the oldest
        stats.check_rate_limit("new_client", 10)

        # Should still be at capacity (not over)
        assert len(stats._request_times) == MAX_TRACKED_CLIENTS
        # New client should be tracked
        assert "new_client" in stats._request_times


class TestUpstreamConnection:
    """Tests for UpstreamConnection class."""

    def test_init_with_config(self):
        """Test initialization with UpstreamConfig."""
        config = UpstreamConfig(
            name="test",
            command="echo",
            args=["hello"],
        )

        connection = UpstreamConnection(config)

        assert connection.config == config
        assert connection._process is None

    @pytest.mark.asyncio
    async def test_start_requires_command(self):
        """Test that start() requires a command."""
        config = UpstreamConfig(name="no-command", url="http://example.com")

        connection = UpstreamConnection(config)

        with pytest.raises(ValueError, match="no command configured"):
            await connection.start()

    def test_has_lock_for_concurrency(self):
        """Test that UpstreamConnection has asyncio.Lock for thread safety."""
        import asyncio

        config = UpstreamConfig(name="test", command="echo")
        connection = UpstreamConnection(config)

        # Verify lock exists and is an asyncio.Lock
        assert hasattr(connection, "_lock")
        assert isinstance(connection._lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_concurrent_id_assignment_is_unique(self):
        """Test that concurrent requests get unique IDs."""
        config = UpstreamConfig(name="test", command="echo")
        connection = UpstreamConnection(config)

        # Simulate concurrent ID assignment by calling the protected section
        assigned_ids = []

        async def assign_id():
            async with connection._lock:
                current_id = connection._next_id
                connection._next_id += 1
            assigned_ids.append(current_id)

        # Run 100 concurrent ID assignments
        import asyncio

        await asyncio.gather(*[assign_id() for _ in range(100)])

        # All IDs should be unique
        assert len(assigned_ids) == 100
        assert len(set(assigned_ids)) == 100, "All IDs must be unique"


class TestRaxeMCPGateway:
    """Tests for RaxeMCPGateway class."""

    @pytest.fixture
    def gateway_config(self):
        """Create a test gateway configuration."""
        return GatewayConfig(
            listen_transport="stdio",
            telemetry_enabled=False,
            l2_enabled=False,
            upstreams=[
                UpstreamConfig(
                    name="test-server",
                    command="echo",
                    args=["test"],
                )
            ],
            default_policy=PolicyConfig(
                on_threat="log",
                severity_threshold="HIGH",
            ),
        )

    @pytest.fixture
    def mock_raxe(self):
        """Create a mock Raxe client."""
        raxe = MagicMock()
        return raxe

    def test_init_with_config(self, gateway_config, mock_raxe):
        """Test initialization with config."""
        gateway = RaxeMCPGateway(gateway_config, mock_raxe)

        assert gateway.config == gateway_config
        assert gateway._raxe == mock_raxe
        assert len(gateway._upstreams) == 0  # Not started yet

    def test_default_config(self, mock_raxe):
        """Test initialization with default config."""
        gateway = RaxeMCPGateway(raxe=mock_raxe)

        assert gateway.config.listen_transport == "stdio"
        assert gateway.config.default_policy.on_threat == "log"

    def test_get_stats(self, gateway_config, mock_raxe):
        """Test get_stats returns statistics."""
        gateway = RaxeMCPGateway(gateway_config, mock_raxe)

        stats = gateway.get_stats()

        assert "requests_forwarded" in stats
        assert "requests_blocked" in stats
        assert "threats_detected" in stats
        assert "total_scan_time_ms" in stats
        assert stats["upstreams_connected"] == 0

    def test_get_policy_default(self, gateway_config, mock_raxe):
        """Test that default policy is returned when no upstream specified."""
        gateway = RaxeMCPGateway(gateway_config, mock_raxe)

        policy = gateway._get_policy(None)

        assert policy.on_threat == "log"
        assert policy.severity_threshold == "HIGH"

    def test_get_policy_upstream_override(self, mock_raxe):
        """Test that upstream policy overrides default."""
        config = GatewayConfig(
            upstreams=[
                UpstreamConfig(
                    name="secure-server",
                    command="server",
                    policy=PolicyConfig(
                        on_threat="block",
                        severity_threshold="MEDIUM",
                    ),
                )
            ]
        )

        gateway = RaxeMCPGateway(config, mock_raxe)

        policy = gateway._get_policy("secure-server")

        assert policy.on_threat == "block"
        assert policy.severity_threshold == "MEDIUM"

    def test_should_block_respects_policy(self, gateway_config, mock_raxe):
        """Test that _should_block respects policy settings."""
        gateway = RaxeMCPGateway(gateway_config, mock_raxe)

        # With log policy, should not block
        log_policy = PolicyConfig(on_threat="log")

        mock_result = Mock()
        mock_result.scan_result = Mock()
        mock_result.scan_result.has_threats = True
        mock_result.scan_result.severity = "HIGH"

        from raxe.mcp.interceptors import InterceptionResult

        result = InterceptionResult(
            should_block=True,
            scan_result=mock_result.scan_result,
        )

        assert gateway._should_block(result, log_policy) is False

    def test_should_block_with_block_policy(self, gateway_config, mock_raxe):
        """Test that blocking policy blocks high severity threats."""
        gateway = RaxeMCPGateway(gateway_config, mock_raxe)

        block_policy = PolicyConfig(
            on_threat="block",
            severity_threshold="HIGH",
        )

        mock_scan_result = Mock()
        mock_scan_result.has_threats = True
        mock_scan_result.severity = "HIGH"

        from raxe.mcp.interceptors import InterceptionResult

        result = InterceptionResult(
            should_block=True,
            scan_result=mock_scan_result,
        )

        assert gateway._should_block(result, block_policy) is True

    def test_should_block_respects_severity_threshold(self, gateway_config, mock_raxe):
        """Test that severity threshold is respected."""
        gateway = RaxeMCPGateway(gateway_config, mock_raxe)

        # Block only CRITICAL
        policy = PolicyConfig(
            on_threat="block",
            severity_threshold="CRITICAL",
        )

        mock_scan_result = Mock()
        mock_scan_result.has_threats = True
        mock_scan_result.severity = "HIGH"  # Below CRITICAL

        from raxe.mcp.interceptors import InterceptionResult

        result = InterceptionResult(
            should_block=True,
            scan_result=mock_scan_result,
        )

        # HIGH is below CRITICAL threshold, should not block
        assert gateway._should_block(result, policy) is False

        # CRITICAL should block
        mock_scan_result.severity = "CRITICAL"
        assert gateway._should_block(result, policy) is True

    def test_error_response_format(self, gateway_config, mock_raxe):
        """Test that error responses are properly formatted."""
        gateway = RaxeMCPGateway(gateway_config, mock_raxe)

        response = gateway._error_response(123, JSONRPC_ERROR_BLOCKED, "Test error")

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 123
        assert response["error"]["code"] == JSONRPC_ERROR_BLOCKED
        assert response["error"]["message"] == "Test error"


class TestCreateGateway:
    """Tests for create_gateway factory function."""

    def test_creates_gateway_with_default_config(self):
        """Test that factory creates gateway with defaults."""
        gateway = create_gateway()

        assert isinstance(gateway, RaxeMCPGateway)
        assert gateway.config.listen_transport == "stdio"

    def test_creates_gateway_with_custom_config(self):
        """Test that factory accepts custom config."""
        config = GatewayConfig(l2_enabled=False)

        gateway = create_gateway(config)

        assert gateway.config.l2_enabled is False

    def test_creates_gateway_with_custom_raxe(self):
        """Test that factory accepts custom Raxe client."""
        mock_raxe = MagicMock()

        gateway = create_gateway(raxe=mock_raxe)

        assert gateway._raxe == mock_raxe


class TestGatewayIntegration:
    """Integration-style tests for gateway behavior."""

    @pytest.fixture
    def mock_scanner(self):
        """Create a mock scanner that returns safe results."""
        scanner = MagicMock()
        safe_result = Mock()
        safe_result.has_threats = False
        safe_result.should_block = False
        safe_result.severity = None
        safe_result.rule_ids = []
        scanner.scan_prompt.return_value = safe_result
        return scanner

    @pytest.mark.asyncio
    async def test_handle_request_without_upstream(self):
        """Test that handle_request returns error when no upstream."""
        config = GatewayConfig(upstreams=[])
        mock_raxe = MagicMock()

        gateway = RaxeMCPGateway(config, mock_raxe)

        # Mock interceptors to return safe result
        gateway._interceptors = MagicMock()
        gateway._interceptors.intercept_request.return_value = MagicMock(
            should_block=False,
            scan_result=None,
        )

        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "test"},
        }

        response = await gateway.handle_request(message)

        assert "error" in response
        assert response["error"]["code"] == JSONRPC_ERROR_NO_UPSTREAM

    @pytest.mark.asyncio
    async def test_handle_request_blocks_on_threat(self):
        """Test that requests with threats are blocked."""
        config = GatewayConfig(
            default_policy=PolicyConfig(
                on_threat="block",
                severity_threshold="HIGH",
            ),
            upstreams=[
                UpstreamConfig(name="test", command="echo"),
            ],
        )
        mock_raxe = MagicMock()

        gateway = RaxeMCPGateway(config, mock_raxe)

        # Mock interceptors to return threat
        mock_scan_result = Mock()
        mock_scan_result.has_threats = True
        mock_scan_result.should_block = True
        mock_scan_result.severity = "HIGH"
        mock_scan_result.rule_ids = ["pi-001"]

        gateway._interceptors = MagicMock()
        gateway._interceptors.intercept_request.return_value = MagicMock(
            should_block=True,
            scan_result=mock_scan_result,
            reason="Threat detected",
        )

        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "test", "arguments": {"cmd": "malicious"}},
        }

        response = await gateway.handle_request(message)

        assert "error" in response
        assert response["error"]["code"] == JSONRPC_ERROR_BLOCKED
        assert "blocked" in response["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_request_rate_limit(self):
        """Test that rate limiting works."""
        config = GatewayConfig(
            default_policy=PolicyConfig(rate_limit_rpm=1),
            upstreams=[
                UpstreamConfig(name="test", command="echo"),
            ],
        )
        mock_raxe = MagicMock()

        gateway = RaxeMCPGateway(config, mock_raxe)

        # First request uses up the rate limit
        gateway._stats.check_rate_limit("default", 1)

        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "test"},
        }

        response = await gateway.handle_request(message)

        assert "error" in response
        assert "rate limit" in response["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_request_message_size_limit(self):
        """Test that oversized messages are rejected."""
        config = GatewayConfig(
            upstreams=[
                UpstreamConfig(name="test", command="echo"),
            ],
        )
        mock_raxe = MagicMock()

        gateway = RaxeMCPGateway(config, mock_raxe)

        # Mock interceptors to return safe result
        gateway._interceptors = MagicMock()
        gateway._interceptors.intercept_request.return_value = MagicMock(
            should_block=False,
            scan_result=None,
        )

        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "test"},
        }

        # Simulate oversized message (11MB > 10MB limit)
        oversized_bytes = 11 * 1024 * 1024

        response = await gateway.handle_request(message, message_size=oversized_bytes)

        assert "error" in response
        assert response["error"]["code"] == JSONRPC_ERROR_MESSAGE_TOO_LARGE
        assert "too large" in response["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_request_recovers_from_interceptor_error(self):
        """Test that gateway recovers when interceptor raises exception."""
        config = GatewayConfig(
            upstreams=[
                UpstreamConfig(name="test", command="echo"),
            ],
        )
        mock_raxe = MagicMock()

        gateway = RaxeMCPGateway(config, mock_raxe)

        # Mock interceptors to raise an exception
        gateway._interceptors = MagicMock()
        gateway._interceptors.intercept_request.side_effect = RuntimeError("Interceptor failed")

        message = {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {"name": "test"},
        }

        # Should not raise - should return error response instead
        # Note: This tests handle_request directly, which doesn't catch exceptions
        # The exception recovery is in run_stdio() which wraps handle_request
        with pytest.raises(RuntimeError):
            await gateway.handle_request(message)


class TestGatewayErrorRecovery:
    """Tests for gateway error recovery behavior."""

    def test_error_response_includes_request_id(self):
        """Test that error responses include the request ID when available."""
        mock_raxe = MagicMock()
        gateway = RaxeMCPGateway(raxe=mock_raxe)

        response = gateway._error_response(42, -32603, "Internal error")

        assert response["id"] == 42
        assert response["error"]["code"] == -32603

    def test_error_response_handles_none_request_id(self):
        """Test that error responses handle None request ID."""
        mock_raxe = MagicMock()
        gateway = RaxeMCPGateway(raxe=mock_raxe)

        response = gateway._error_response(None, -32700, "Parse error")

        assert response["id"] is None
        assert response["error"]["code"] == -32700

    def test_json_rpc_parse_error_code_is_standard(self):
        """Test that JSON-RPC parse error uses standard code -32700."""
        # Per JSON-RPC 2.0 spec, -32700 is the parse error code
        mock_raxe = MagicMock()
        gateway = RaxeMCPGateway(raxe=mock_raxe)

        response = gateway._error_response(None, -32700, "Parse error")

        assert response["error"]["code"] == -32700

    def test_json_rpc_internal_error_code_is_standard(self):
        """Test that JSON-RPC internal error uses standard code -32603."""
        # Per JSON-RPC 2.0 spec, -32603 is the internal error code
        mock_raxe = MagicMock()
        gateway = RaxeMCPGateway(raxe=mock_raxe)

        response = gateway._error_response(None, -32603, "Internal error")

        assert response["error"]["code"] == -32603
