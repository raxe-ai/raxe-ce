"""Unit tests for JSON-RPC transport layer.

Tests for:
- Transport abstract base class
- StdioTransport implementation (stdin/stdout JSON-RPC)

Uses io.StringIO to mock stdin/stdout for isolated testing.
"""

from __future__ import annotations

import io
import json
from typing import TYPE_CHECKING

import pytest

from raxe.domain.jsonrpc.errors import JsonRpcErrorCode
from raxe.domain.jsonrpc.models import JsonRpcRequest, JsonRpcResponse

if TYPE_CHECKING:
    pass


# ============================================================================
# Transport Base Tests
# ============================================================================


class TestTransportProtocol:
    """Tests for Transport abstract base class/protocol."""

    def test_transport_is_abstract(self):
        """Transport cannot be instantiated directly."""
        from raxe.infrastructure.jsonrpc.transports.base import Transport

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            Transport()  # type: ignore

    def test_transport_requires_read_method(self):
        """Transport requires read() method."""
        from raxe.infrastructure.jsonrpc.transports.base import Transport

        class IncompleteTransport(Transport):
            def write(self, response: JsonRpcResponse) -> None:
                pass

            def close(self) -> None:
                pass

        with pytest.raises(TypeError, match="abstract method"):
            IncompleteTransport()

    def test_transport_requires_write_method(self):
        """Transport requires write() method."""
        from raxe.infrastructure.jsonrpc.transports.base import Transport

        class IncompleteTransport(Transport):
            def read(self) -> JsonRpcRequest | None:
                return None

            def close(self) -> None:
                pass

        with pytest.raises(TypeError, match="abstract method"):
            IncompleteTransport()

    def test_transport_requires_close_method(self):
        """Transport requires close() method."""
        from raxe.infrastructure.jsonrpc.transports.base import Transport

        class IncompleteTransport(Transport):
            def read(self) -> JsonRpcRequest | None:
                return None

            def write(self, response: JsonRpcResponse) -> None:
                pass

        with pytest.raises(TypeError, match="abstract method"):
            IncompleteTransport()


# ============================================================================
# StdioTransport Tests
# ============================================================================


class TestStdioTransportRead:
    """Tests for StdioTransport.read() method."""

    def test_read_single_request(self):
        """Read a single valid JSON-RPC request from stdin."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        request_json = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "scan",
                "id": "1",
                "params": {"prompt": "test"},
            }
        )
        stdin = io.StringIO(request_json + "\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)
        result = transport.read()

        assert result is not None
        assert isinstance(result, JsonRpcRequest)
        assert result.method == "scan"
        assert result.id == "1"
        assert result.params == {"prompt": "test"}

    def test_read_multiple_requests(self):
        """Read multiple requests sequentially from stdin."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        requests = [
            {"jsonrpc": "2.0", "method": "scan", "id": "1"},
            {"jsonrpc": "2.0", "method": "info", "id": "2"},
            {"jsonrpc": "2.0", "method": "list_methods", "id": "3"},
        ]
        stdin_content = "\n".join(json.dumps(r) for r in requests) + "\n"
        stdin = io.StringIO(stdin_content)
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        # Read all three requests
        result1 = transport.read()
        result2 = transport.read()
        result3 = transport.read()

        assert result1 is not None and result1.method == "scan"
        assert result2 is not None and result2.method == "info"
        assert result3 is not None and result3.method == "list_methods"

    def test_read_request_with_integer_id(self):
        """Read request with integer id."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        request_json = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "scan",
                "id": 42,
            }
        )
        stdin = io.StringIO(request_json + "\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)
        result = transport.read()

        assert result is not None
        assert result.id == 42
        assert isinstance(result.id, int)

    def test_read_notification_without_id(self):
        """Read notification (request without id)."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        request_json = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "notify_event",
            }
        )
        stdin = io.StringIO(request_json + "\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)
        result = transport.read()

        assert result is not None
        assert result.is_notification is True
        assert result.id is None

    def test_read_request_with_list_params(self):
        """Read request with positional parameters (list)."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        request_json = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "subtract",
                "id": "1",
                "params": [42, 23],
            }
        )
        stdin = io.StringIO(request_json + "\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)
        result = transport.read()

        assert result is not None
        assert result.params == [42, 23]


class TestStdioTransportEOF:
    """Tests for EOF handling in StdioTransport."""

    def test_handles_eof_gracefully(self):
        """Return None when stdin reaches EOF."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        stdin = io.StringIO("")  # Empty input = immediate EOF
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)
        result = transport.read()

        assert result is None

    def test_handles_eof_after_request(self):
        """Return None when stdin reaches EOF after valid request."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        request_json = json.dumps({"jsonrpc": "2.0", "method": "scan", "id": "1"})
        stdin = io.StringIO(request_json + "\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        # First read returns request
        result1 = transport.read()
        assert result1 is not None

        # Second read returns None (EOF)
        result2 = transport.read()
        assert result2 is None


class TestStdioTransportEmptyLines:
    """Tests for empty line handling in StdioTransport."""

    def test_handles_empty_line(self):
        """Skip empty lines and continue reading."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        # Empty line followed by valid request
        content = "\n" + json.dumps({"jsonrpc": "2.0", "method": "scan", "id": "1"}) + "\n"
        stdin = io.StringIO(content)
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)
        result = transport.read()

        assert result is not None
        assert result.method == "scan"

    def test_handles_multiple_empty_lines(self):
        """Skip multiple empty lines."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        content = "\n\n\n" + json.dumps({"jsonrpc": "2.0", "method": "scan", "id": "1"}) + "\n"
        stdin = io.StringIO(content)
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)
        result = transport.read()

        assert result is not None
        assert result.method == "scan"

    def test_handles_whitespace_only_lines(self):
        """Skip lines with only whitespace."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        content = "   \n\t\n" + json.dumps({"jsonrpc": "2.0", "method": "scan", "id": "1"}) + "\n"
        stdin = io.StringIO(content)
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)
        result = transport.read()

        assert result is not None
        assert result.method == "scan"


class TestStdioTransportMalformedJSON:
    """Tests for malformed JSON handling in StdioTransport."""

    def test_handles_malformed_json(self):
        """Return parse error for malformed JSON."""
        from raxe.infrastructure.jsonrpc.transports.stdio import (
            StdioTransport,
            TransportError,
        )

        stdin = io.StringIO("not valid json\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        with pytest.raises(TransportError) as exc_info:
            transport.read()

        assert exc_info.value.error_code == JsonRpcErrorCode.PARSE_ERROR

    def test_handles_incomplete_json(self):
        """Return parse error for incomplete JSON."""
        from raxe.infrastructure.jsonrpc.transports.stdio import (
            StdioTransport,
            TransportError,
        )

        stdin = io.StringIO('{"jsonrpc": "2.0", "method"\n')  # Missing closing brace
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        with pytest.raises(TransportError) as exc_info:
            transport.read()

        assert exc_info.value.error_code == JsonRpcErrorCode.PARSE_ERROR

    def test_handles_json_array_instead_of_object(self):
        """Return invalid request for JSON array (batch not supported in transport)."""
        from raxe.infrastructure.jsonrpc.transports.stdio import (
            StdioTransport,
            TransportError,
        )

        stdin = io.StringIO('[{"jsonrpc": "2.0", "method": "scan", "id": "1"}]\n')
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        with pytest.raises(TransportError) as exc_info:
            transport.read()

        assert exc_info.value.error_code == JsonRpcErrorCode.INVALID_REQUEST

    def test_handles_json_primitive(self):
        """Return invalid request for JSON primitive."""
        from raxe.infrastructure.jsonrpc.transports.stdio import (
            StdioTransport,
            TransportError,
        )

        stdin = io.StringIO('"just a string"\n')
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        with pytest.raises(TransportError) as exc_info:
            transport.read()

        assert exc_info.value.error_code == JsonRpcErrorCode.INVALID_REQUEST


class TestStdioTransportInvalidRequest:
    """Tests for invalid JSON-RPC request handling."""

    def test_handles_missing_jsonrpc_field(self):
        """Return invalid request for missing jsonrpc field."""
        from raxe.infrastructure.jsonrpc.transports.stdio import (
            StdioTransport,
            TransportError,
        )

        request_json = json.dumps({"method": "scan", "id": "1"})
        stdin = io.StringIO(request_json + "\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        with pytest.raises(TransportError) as exc_info:
            transport.read()

        assert exc_info.value.error_code == JsonRpcErrorCode.INVALID_REQUEST

    def test_handles_wrong_jsonrpc_version(self):
        """Return invalid request for wrong jsonrpc version."""
        from raxe.infrastructure.jsonrpc.transports.stdio import (
            StdioTransport,
            TransportError,
        )

        request_json = json.dumps({"jsonrpc": "1.0", "method": "scan", "id": "1"})
        stdin = io.StringIO(request_json + "\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        with pytest.raises(TransportError) as exc_info:
            transport.read()

        assert exc_info.value.error_code == JsonRpcErrorCode.INVALID_REQUEST

    def test_handles_missing_method_field(self):
        """Return invalid request for missing method field."""
        from raxe.infrastructure.jsonrpc.transports.stdio import (
            StdioTransport,
            TransportError,
        )

        request_json = json.dumps({"jsonrpc": "2.0", "id": "1"})
        stdin = io.StringIO(request_json + "\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        with pytest.raises(TransportError) as exc_info:
            transport.read()

        assert exc_info.value.error_code == JsonRpcErrorCode.INVALID_REQUEST


class TestStdioTransportUnicode:
    """Tests for unicode handling in StdioTransport."""

    def test_handles_unicode_in_method(self):
        """Read request with unicode method name."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        request_json = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "scan_prompt",
                "id": "1",
            }
        )
        stdin = io.StringIO(request_json + "\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)
        result = transport.read()

        assert result is not None
        assert result.method == "scan_prompt"

    def test_handles_unicode_in_params(self):
        """Read request with unicode characters in params."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        request_json = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "scan",
                "id": "1",
                "params": {"prompt": "Hello!"},
            }
        )
        stdin = io.StringIO(request_json + "\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)
        result = transport.read()

        assert result is not None
        assert result.params["prompt"] == "Hello!"

    def test_handles_unicode_emoji(self):
        """Read request with emoji in params."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        request_json = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "scan",
                "id": "1",
                "params": {"prompt": "Hello world!"},
            }
        )
        stdin = io.StringIO(request_json + "\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)
        result = transport.read()

        assert result is not None
        assert result.params["prompt"] == "Hello world!"

    def test_handles_unicode_cjk_characters(self):
        """Read request with CJK characters in params."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        request_json = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "scan",
                "id": "1",
                "params": {"prompt": "Hello there!"},
            }
        )
        stdin = io.StringIO(request_json + "\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)
        result = transport.read()

        assert result is not None


class TestStdioTransportWrite:
    """Tests for StdioTransport.write() method."""

    def test_write_success_response(self):
        """Write success response to stdout."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        stdin = io.StringIO("")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result={"status": "ok"},
        )
        transport.write(response)

        output = stdout.getvalue()
        parsed = json.loads(output.strip())

        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == "1"
        assert parsed["result"] == {"status": "ok"}

    def test_write_error_response(self):
        """Write error response to stdout."""
        from raxe.domain.jsonrpc.models import JsonRpcError
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        stdin = io.StringIO("")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        error = JsonRpcError(code=-32600, message="Invalid Request")
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            error=error,
        )
        transport.write(response)

        output = stdout.getvalue()
        parsed = json.loads(output.strip())

        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == "1"
        assert parsed["error"]["code"] == -32600
        assert parsed["error"]["message"] == "Invalid Request"

    def test_write_response_with_null_result(self):
        """Write response with null result."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        stdin = io.StringIO("")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result=None,
        )
        transport.write(response)

        output = stdout.getvalue()
        parsed = json.loads(output.strip())

        assert parsed["result"] is None

    def test_write_response_with_complex_result(self):
        """Write response with complex nested result."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        stdin = io.StringIO("")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result={
                "threat_detected": True,
                "detections": [
                    {"rule_id": "pi-001", "severity": "HIGH"},
                    {"rule_id": "jb-002", "severity": "MEDIUM"},
                ],
                "scan_duration_ms": 5.2,
            },
        )
        transport.write(response)

        output = stdout.getvalue()
        parsed = json.loads(output.strip())

        assert parsed["result"]["threat_detected"] is True
        assert len(parsed["result"]["detections"]) == 2

    def test_write_multiple_responses(self):
        """Write multiple responses sequentially."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        stdin = io.StringIO("")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        # Write three responses
        for i in range(3):
            response = JsonRpcResponse(
                jsonrpc="2.0",
                id=str(i + 1),
                result={"index": i},
            )
            transport.write(response)

        # Parse all lines
        lines = stdout.getvalue().strip().split("\n")
        assert len(lines) == 3

        for i, line in enumerate(lines):
            parsed = json.loads(line)
            assert parsed["id"] == str(i + 1)
            assert parsed["result"]["index"] == i

    def test_write_response_ends_with_newline(self):
        """Written response ends with newline for line-delimited protocol."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        stdin = io.StringIO("")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result="ok",
        )
        transport.write(response)

        output = stdout.getvalue()
        assert output.endswith("\n")


class TestStdioTransportClose:
    """Tests for StdioTransport.close() method."""

    def test_close_sets_closed_flag(self):
        """Close sets internal closed flag."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        stdin = io.StringIO("")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)
        assert transport.closed is False

        transport.close()
        assert transport.closed is True

    def test_read_after_close_returns_none(self):
        """Read after close returns None."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        request_json = json.dumps({"jsonrpc": "2.0", "method": "scan", "id": "1"})
        stdin = io.StringIO(request_json + "\n")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)
        transport.close()

        result = transport.read()
        assert result is None

    def test_close_is_idempotent(self):
        """Close can be called multiple times safely."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        stdin = io.StringIO("")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        # Should not raise
        transport.close()
        transport.close()
        transport.close()

        assert transport.closed is True


class TestStdioTransportContextManager:
    """Tests for StdioTransport context manager support."""

    def test_context_manager_closes_on_exit(self):
        """Context manager closes transport on exit."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        stdin = io.StringIO("")
        stdout = io.StringIO()

        with StdioTransport(stdin=stdin, stdout=stdout) as transport:
            assert transport.closed is False

        assert transport.closed is True

    def test_context_manager_closes_on_exception(self):
        """Context manager closes transport on exception."""
        from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport

        stdin = io.StringIO("")
        stdout = io.StringIO()

        transport = StdioTransport(stdin=stdin, stdout=stdout)

        try:
            with transport:
                raise ValueError("Test error")
        except ValueError:
            pass

        assert transport.closed is True


class TestTransportError:
    """Tests for TransportError exception."""

    def test_transport_error_with_code(self):
        """TransportError stores error code."""
        from raxe.infrastructure.jsonrpc.transports.stdio import TransportError

        error = TransportError(
            message="Parse error",
            error_code=JsonRpcErrorCode.PARSE_ERROR,
        )

        assert error.error_code == JsonRpcErrorCode.PARSE_ERROR
        assert str(error) == "Parse error"

    def test_transport_error_with_details(self):
        """TransportError stores additional details."""
        from raxe.infrastructure.jsonrpc.transports.stdio import TransportError

        error = TransportError(
            message="Invalid JSON",
            error_code=JsonRpcErrorCode.PARSE_ERROR,
            details={"line": 1, "column": 5},
        )

        assert error.details == {"line": 1, "column": 5}

    def test_transport_error_to_jsonrpc_error(self):
        """TransportError can be converted to JsonRpcError."""
        from raxe.infrastructure.jsonrpc.transports.stdio import TransportError

        error = TransportError(
            message="Invalid request format",
            error_code=JsonRpcErrorCode.INVALID_REQUEST,
            details={"field": "method"},
        )

        jsonrpc_error = error.to_jsonrpc_error()

        assert jsonrpc_error.code == JsonRpcErrorCode.INVALID_REQUEST
        assert jsonrpc_error.message == "Invalid request format"
        assert jsonrpc_error.data == {"field": "method"}
