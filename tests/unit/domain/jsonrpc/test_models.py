"""Unit tests for JSON-RPC domain models.

Tests pure domain logic - no I/O operations, no mocks needed.
These tests should be fast and comprehensive.

Following JSON-RPC 2.0 Specification: https://www.jsonrpc.org/specification
"""

import json

import pytest

from raxe.domain.jsonrpc.models import (
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
)


class TestJsonRpcRequest:
    """Test JsonRpcRequest value object."""

    # ==================== Valid Request Creation ====================

    def test_create_request_with_minimal_fields(self):
        """Request can be created with minimal required fields."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="test_method",
            id="1",
        )

        assert request.jsonrpc == "2.0"
        assert request.method == "test_method"
        assert request.id == "1"
        assert request.params is None

    def test_create_request_with_dict_params(self):
        """Request can be created with dictionary params (by-name)."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="test_method",
            id="1",
            params={"key": "value", "count": 42},
        )

        assert request.params == {"key": "value", "count": 42}

    def test_create_request_with_list_params(self):
        """Request can be created with list params (by-position)."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="test_method",
            id="1",
            params=["arg1", "arg2", 123],
        )

        assert request.params == ["arg1", "arg2", 123]

    def test_create_request_with_integer_id(self):
        """Request can be created with integer id."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="test_method",
            id=42,
        )

        assert request.id == 42
        assert isinstance(request.id, int)

    def test_create_request_with_string_id(self):
        """Request can be created with string id."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="test_method",
            id="uuid-1234-5678",
        )

        assert request.id == "uuid-1234-5678"
        assert isinstance(request.id, str)

    def test_create_notification_without_id(self):
        """Notification (request without id) can be created."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="notify_event",
            id=None,
            params={"event": "started"},
        )

        assert request.id is None
        assert request.is_notification is True

    def test_create_notification_id_omitted(self):
        """Notification can be created by omitting id parameter."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="notify_event",
        )

        assert request.id is None
        assert request.is_notification is True

    # ==================== Request Immutability ====================

    def test_request_is_immutable(self):
        """Request is frozen and cannot be modified."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="test_method",
            id="1",
        )

        with pytest.raises(AttributeError):
            request.method = "new_method"  # type: ignore

    def test_request_is_immutable_jsonrpc(self):
        """Request jsonrpc field cannot be modified."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="test_method",
            id="1",
        )

        with pytest.raises(AttributeError):
            request.jsonrpc = "1.0"  # type: ignore

    def test_request_is_immutable_id(self):
        """Request id field cannot be modified."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="test_method",
            id="1",
        )

        with pytest.raises(AttributeError):
            request.id = "2"  # type: ignore

    # ==================== Request Validation ====================

    def test_request_validates_jsonrpc_version(self):
        """Request raises ValueError for invalid jsonrpc version."""
        with pytest.raises(ValueError, match="jsonrpc must be '2.0'"):
            JsonRpcRequest(
                jsonrpc="1.0",
                method="test_method",
                id="1",
            )

    def test_request_validates_jsonrpc_version_empty(self):
        """Request raises ValueError for empty jsonrpc."""
        with pytest.raises(ValueError, match="jsonrpc must be '2.0'"):
            JsonRpcRequest(
                jsonrpc="",
                method="test_method",
                id="1",
            )

    def test_request_validates_method_not_empty(self):
        """Request raises ValueError for empty method."""
        with pytest.raises(ValueError, match="method cannot be empty"):
            JsonRpcRequest(
                jsonrpc="2.0",
                method="",
                id="1",
            )

    def test_request_validates_method_not_reserved(self):
        """Request raises ValueError for reserved method names (rpc. prefix)."""
        with pytest.raises(ValueError, match="method names beginning with 'rpc.' are reserved"):
            JsonRpcRequest(
                jsonrpc="2.0",
                method="rpc.discover",
                id="1",
            )

    def test_request_validates_method_rpc_prefix_case_sensitive(self):
        """Reserved method check is case-sensitive (rpc. only, not RPC.)."""
        # Should NOT raise - RPC. is different from rpc.
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="RPC.discover",
            id="1",
        )
        assert request.method == "RPC.discover"

    def test_request_validates_params_type(self):
        """Request raises ValueError for invalid params type."""
        with pytest.raises(ValueError, match="params must be a dict or list"):
            JsonRpcRequest(
                jsonrpc="2.0",
                method="test_method",
                id="1",
                params="invalid",  # type: ignore
            )

    def test_request_validates_params_type_integer(self):
        """Request raises ValueError for integer params."""
        with pytest.raises(ValueError, match="params must be a dict or list"):
            JsonRpcRequest(
                jsonrpc="2.0",
                method="test_method",
                id="1",
                params=42,  # type: ignore
            )

    def test_request_validates_id_type(self):
        """Request raises ValueError for invalid id type (float)."""
        with pytest.raises(ValueError, match="id must be a string, integer, or None"):
            JsonRpcRequest(
                jsonrpc="2.0",
                method="test_method",
                id=3.14,  # type: ignore
            )

    def test_request_validates_id_type_list(self):
        """Request raises ValueError for list id type."""
        with pytest.raises(ValueError, match="id must be a string, integer, or None"):
            JsonRpcRequest(
                jsonrpc="2.0",
                method="test_method",
                id=["not", "valid"],  # type: ignore
            )

    # ==================== Request Properties ====================

    def test_is_notification_true_when_id_none(self):
        """is_notification returns True when id is None."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="notify",
            id=None,
        )

        assert request.is_notification is True

    def test_is_notification_false_when_id_present(self):
        """is_notification returns False when id is present."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="method",
            id="1",
        )

        assert request.is_notification is False

    def test_is_notification_false_with_zero_id(self):
        """is_notification returns False when id is 0 (valid id)."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="method",
            id=0,
        )

        assert request.is_notification is False

    def test_is_notification_false_with_empty_string_id(self):
        """is_notification returns False when id is empty string (valid id)."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="method",
            id="",
        )

        assert request.is_notification is False

    # ==================== Request Serialization ====================

    def test_to_dict_basic(self):
        """Request serializes to dictionary correctly."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="test_method",
            id="1",
        )

        data = request.to_dict()

        assert data["jsonrpc"] == "2.0"
        assert data["method"] == "test_method"
        assert data["id"] == "1"
        assert "params" not in data  # None params should be omitted

    def test_to_dict_with_params(self):
        """Request with params serializes correctly."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="test_method",
            id=42,
            params={"key": "value"},
        )

        data = request.to_dict()

        assert data["params"] == {"key": "value"}

    def test_to_dict_notification_no_id(self):
        """Notification serializes without id field."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="notify",
            id=None,
        )

        data = request.to_dict()

        assert "id" not in data

    def test_from_dict_basic(self):
        """Request deserializes from dictionary."""
        data = {
            "jsonrpc": "2.0",
            "method": "test_method",
            "id": "1",
        }

        request = JsonRpcRequest.from_dict(data)

        assert request.jsonrpc == "2.0"
        assert request.method == "test_method"
        assert request.id == "1"
        assert request.params is None

    def test_from_dict_with_params(self):
        """Request deserializes with params."""
        data = {
            "jsonrpc": "2.0",
            "method": "test_method",
            "id": 1,
            "params": {"foo": "bar"},
        }

        request = JsonRpcRequest.from_dict(data)

        assert request.id == 1
        assert request.params == {"foo": "bar"}

    def test_from_dict_notification(self):
        """Notification deserializes correctly."""
        data = {
            "jsonrpc": "2.0",
            "method": "notify_event",
        }

        request = JsonRpcRequest.from_dict(data)

        assert request.id is None
        assert request.is_notification is True

    def test_from_dict_missing_jsonrpc(self):
        """Deserialization fails for missing jsonrpc."""
        data = {
            "method": "test_method",
            "id": "1",
        }

        with pytest.raises(ValueError, match="jsonrpc must be '2.0'"):
            JsonRpcRequest.from_dict(data)

    def test_from_dict_missing_method(self):
        """Deserialization fails for missing method."""
        data = {
            "jsonrpc": "2.0",
            "id": "1",
        }

        with pytest.raises(ValueError, match="method cannot be empty"):
            JsonRpcRequest.from_dict(data)

    def test_round_trip_serialization(self):
        """Request survives round-trip serialization."""
        original = JsonRpcRequest(
            jsonrpc="2.0",
            method="complex_method",
            id="uuid-123",
            params={"nested": {"key": "value"}, "list": [1, 2, 3]},
        )

        data = original.to_dict()
        restored = JsonRpcRequest.from_dict(data)

        assert restored.jsonrpc == original.jsonrpc
        assert restored.method == original.method
        assert restored.id == original.id
        assert restored.params == original.params

    def test_json_serialization(self):
        """Request can be serialized to JSON string."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="test",
            id=1,
            params={"key": "value"},
        )

        json_str = json.dumps(request.to_dict())
        parsed = json.loads(json_str)

        assert parsed == request.to_dict()


class TestJsonRpcError:
    """Test JsonRpcError value object."""

    # ==================== Valid Error Creation ====================

    def test_create_error_with_minimal_fields(self):
        """Error can be created with minimal required fields."""
        error = JsonRpcError(
            code=-32600,
            message="Invalid Request",
        )

        assert error.code == -32600
        assert error.message == "Invalid Request"
        assert error.data is None

    def test_create_error_with_data(self):
        """Error can be created with additional data."""
        error = JsonRpcError(
            code=-32602,
            message="Invalid params",
            data={"expected": "string", "got": "integer"},
        )

        assert error.data == {"expected": "string", "got": "integer"}

    def test_create_error_with_string_data(self):
        """Error can be created with string data."""
        error = JsonRpcError(
            code=-32603,
            message="Internal error",
            data="Stack trace here",
        )

        assert error.data == "Stack trace here"

    def test_create_error_with_list_data(self):
        """Error can be created with list data."""
        error = JsonRpcError(
            code=-32602,
            message="Invalid params",
            data=["param1 missing", "param2 invalid type"],
        )

        assert error.data == ["param1 missing", "param2 invalid type"]

    # ==================== Error Immutability ====================

    def test_error_is_immutable(self):
        """Error is frozen and cannot be modified."""
        error = JsonRpcError(
            code=-32600,
            message="Invalid Request",
        )

        with pytest.raises(AttributeError):
            error.code = -32601  # type: ignore

    def test_error_is_immutable_message(self):
        """Error message field cannot be modified."""
        error = JsonRpcError(
            code=-32600,
            message="Invalid Request",
        )

        with pytest.raises(AttributeError):
            error.message = "New message"  # type: ignore

    # ==================== Error Validation ====================

    def test_error_validates_code_is_integer(self):
        """Error raises TypeError for non-integer code."""
        with pytest.raises(TypeError, match="code must be an integer"):
            JsonRpcError(
                code="invalid",  # type: ignore
                message="Error",
            )

    def test_error_validates_message_not_empty(self):
        """Error raises ValueError for empty message."""
        with pytest.raises(ValueError, match="message cannot be empty"):
            JsonRpcError(
                code=-32600,
                message="",
            )

    def test_error_validates_message_is_string(self):
        """Error raises TypeError for non-string message."""
        with pytest.raises(TypeError, match="message must be a string"):
            JsonRpcError(
                code=-32600,
                message=123,  # type: ignore
            )

    # ==================== Error Serialization ====================

    def test_to_dict_basic(self):
        """Error serializes to dictionary correctly."""
        error = JsonRpcError(
            code=-32600,
            message="Invalid Request",
        )

        data = error.to_dict()

        assert data["code"] == -32600
        assert data["message"] == "Invalid Request"
        assert "data" not in data  # None data should be omitted

    def test_to_dict_with_data(self):
        """Error with data serializes correctly."""
        error = JsonRpcError(
            code=-32602,
            message="Invalid params",
            data={"field": "name"},
        )

        data = error.to_dict()

        assert data["data"] == {"field": "name"}

    def test_from_dict_basic(self):
        """Error deserializes from dictionary."""
        data = {
            "code": -32600,
            "message": "Invalid Request",
        }

        error = JsonRpcError.from_dict(data)

        assert error.code == -32600
        assert error.message == "Invalid Request"
        assert error.data is None

    def test_from_dict_with_data(self):
        """Error deserializes with data."""
        data = {
            "code": -32602,
            "message": "Invalid params",
            "data": {"details": "missing field"},
        }

        error = JsonRpcError.from_dict(data)

        assert error.data == {"details": "missing field"}

    def test_round_trip_serialization(self):
        """Error survives round-trip serialization."""
        original = JsonRpcError(
            code=-32000,
            message="Server error",
            data={"trace": "line 42"},
        )

        data = original.to_dict()
        restored = JsonRpcError.from_dict(data)

        assert restored.code == original.code
        assert restored.message == original.message
        assert restored.data == original.data


class TestJsonRpcResponse:
    """Test JsonRpcResponse value object."""

    # ==================== Valid Response Creation ====================

    def test_create_success_response(self):
        """Success response can be created."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result={"status": "ok"},
        )

        assert response.jsonrpc == "2.0"
        assert response.id == "1"
        assert response.result == {"status": "ok"}
        assert response.error is None

    def test_create_success_response_with_null_result(self):
        """Success response can have None as result."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result=None,
        )

        assert response.result is None
        assert response.error is None
        assert response.is_success is True

    def test_create_success_response_with_primitive_result(self):
        """Success response can have primitive result."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result=42,
        )

        assert response.result == 42

    def test_create_success_response_with_list_result(self):
        """Success response can have list result."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result=[1, 2, 3],
        )

        assert response.result == [1, 2, 3]

    def test_create_error_response(self):
        """Error response can be created."""
        error = JsonRpcError(code=-32600, message="Invalid Request")
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            error=error,
        )

        assert response.result is None
        assert response.error is not None
        assert response.error.code == -32600

    def test_create_response_with_integer_id(self):
        """Response can be created with integer id."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id=42,
            result="ok",
        )

        assert response.id == 42

    def test_create_response_with_null_id_for_parse_error(self):
        """Response to parse error has null id."""
        error = JsonRpcError(code=-32700, message="Parse error")
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id=None,
            error=error,
        )

        assert response.id is None
        assert response.error is not None

    # ==================== Response Immutability ====================

    def test_response_is_immutable(self):
        """Response is frozen and cannot be modified."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result="ok",
        )

        with pytest.raises(AttributeError):
            response.result = "new"  # type: ignore

    def test_response_is_immutable_id(self):
        """Response id field cannot be modified."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result="ok",
        )

        with pytest.raises(AttributeError):
            response.id = "2"  # type: ignore

    # ==================== Response Validation ====================

    def test_response_validates_jsonrpc_version(self):
        """Response raises ValueError for invalid jsonrpc version."""
        with pytest.raises(ValueError, match="jsonrpc must be '2.0'"):
            JsonRpcResponse(
                jsonrpc="1.0",
                id="1",
                result="ok",
            )

    def test_response_validates_mutual_exclusion(self):
        """Response raises ValueError when both result and error are present."""
        error = JsonRpcError(code=-32600, message="Invalid Request")

        with pytest.raises(ValueError, match="result and error are mutually exclusive"):
            JsonRpcResponse(
                jsonrpc="2.0",
                id="1",
                result="ok",
                error=error,
            )

    def test_response_validates_at_least_one_present(self):
        """Response requires either result or error (unless result=None explicitly)."""
        # This should be valid - result=None is explicit success
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result=None,
        )
        assert response.is_success is True

    def test_response_validates_id_type(self):
        """Response raises ValueError for invalid id type."""
        with pytest.raises(ValueError, match="id must be a string, integer, or None"):
            JsonRpcResponse(
                jsonrpc="2.0",
                id=3.14,  # type: ignore
                result="ok",
            )

    def test_response_validates_error_type(self):
        """Response raises TypeError for invalid error type."""
        with pytest.raises(TypeError, match="error must be a JsonRpcError"):
            JsonRpcResponse(
                jsonrpc="2.0",
                id="1",
                error={"code": -32600, "message": "Invalid"},  # type: ignore
            )

    # ==================== Response Properties ====================

    def test_is_success_true_for_result(self):
        """is_success returns True for successful response."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result={"data": "value"},
        )

        assert response.is_success is True
        assert response.is_error is False

    def test_is_error_true_for_error(self):
        """is_error returns True for error response."""
        error = JsonRpcError(code=-32600, message="Invalid Request")
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            error=error,
        )

        assert response.is_error is True
        assert response.is_success is False

    def test_is_success_true_for_null_result(self):
        """is_success is True when result is explicitly None."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result=None,
        )

        assert response.is_success is True
        assert response.is_error is False

    # ==================== Response Serialization ====================

    def test_to_dict_success(self):
        """Success response serializes correctly."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result={"status": "ok"},
        )

        data = response.to_dict()

        assert data["jsonrpc"] == "2.0"
        assert data["id"] == "1"
        assert data["result"] == {"status": "ok"}
        assert "error" not in data

    def test_to_dict_success_null_result(self):
        """Success response with null result serializes correctly."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result=None,
        )

        data = response.to_dict()

        assert data["result"] is None
        assert "error" not in data

    def test_to_dict_error(self):
        """Error response serializes correctly."""
        error = JsonRpcError(code=-32600, message="Invalid Request", data="details")
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            error=error,
        )

        data = response.to_dict()

        assert "result" not in data
        assert data["error"]["code"] == -32600
        assert data["error"]["message"] == "Invalid Request"
        assert data["error"]["data"] == "details"

    def test_to_dict_null_id(self):
        """Response with null id serializes correctly."""
        error = JsonRpcError(code=-32700, message="Parse error")
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id=None,
            error=error,
        )

        data = response.to_dict()

        assert data["id"] is None

    def test_from_dict_success(self):
        """Success response deserializes correctly."""
        data = {
            "jsonrpc": "2.0",
            "id": "1",
            "result": {"status": "ok"},
        }

        response = JsonRpcResponse.from_dict(data)

        assert response.jsonrpc == "2.0"
        assert response.id == "1"
        assert response.result == {"status": "ok"}
        assert response.error is None

    def test_from_dict_error(self):
        """Error response deserializes correctly."""
        data = {
            "jsonrpc": "2.0",
            "id": "1",
            "error": {
                "code": -32600,
                "message": "Invalid Request",
                "data": "extra info",
            },
        }

        response = JsonRpcResponse.from_dict(data)

        assert response.result is None
        assert response.error is not None
        assert response.error.code == -32600
        assert response.error.data == "extra info"

    def test_from_dict_missing_jsonrpc(self):
        """Deserialization fails for missing jsonrpc."""
        data = {
            "id": "1",
            "result": "ok",
        }

        with pytest.raises(ValueError, match="jsonrpc must be '2.0'"):
            JsonRpcResponse.from_dict(data)

    def test_round_trip_serialization_success(self):
        """Success response survives round-trip."""
        original = JsonRpcResponse(
            jsonrpc="2.0",
            id=42,
            result={"nested": {"key": "value"}},
        )

        data = original.to_dict()
        restored = JsonRpcResponse.from_dict(data)

        assert restored.jsonrpc == original.jsonrpc
        assert restored.id == original.id
        assert restored.result == original.result

    def test_round_trip_serialization_error(self):
        """Error response survives round-trip."""
        error = JsonRpcError(code=-32602, message="Invalid params", data=["err1"])
        original = JsonRpcResponse(
            jsonrpc="2.0",
            id="req-123",
            error=error,
        )

        data = original.to_dict()
        restored = JsonRpcResponse.from_dict(data)

        assert restored.error is not None
        assert restored.error.code == original.error.code
        assert restored.error.message == original.error.message
        assert restored.error.data == original.error.data

    def test_json_serialization(self):
        """Response can be serialized to JSON string."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result={"key": "value"},
        )

        json_str = json.dumps(response.to_dict())
        parsed = json.loads(json_str)

        assert parsed == response.to_dict()


class TestJsonRpcEdgeCases:
    """Test edge cases and special scenarios."""

    def test_request_with_empty_params_dict(self):
        """Request with empty params dict is valid."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="method",
            id="1",
            params={},
        )

        assert request.params == {}

    def test_request_with_empty_params_list(self):
        """Request with empty params list is valid."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="method",
            id="1",
            params=[],
        )

        assert request.params == []

    def test_response_with_false_result(self):
        """Response with False as result is valid success."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result=False,
        )

        assert response.result is False
        assert response.is_success is True

    def test_response_with_zero_result(self):
        """Response with 0 as result is valid success."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result=0,
        )

        assert response.result == 0
        assert response.is_success is True

    def test_response_with_empty_string_result(self):
        """Response with empty string as result is valid success."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result="",
        )

        assert response.result == ""
        assert response.is_success is True

    def test_request_method_with_dots(self):
        """Request method can contain dots (except rpc. prefix)."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="namespace.sub.method",
            id="1",
        )

        assert request.method == "namespace.sub.method"

    def test_request_method_unicode(self):
        """Request method can contain unicode characters."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="method_name",
            id="1",
        )

        assert request.method == "method_name"

    def test_large_params(self):
        """Request can handle large params."""
        large_params = {"data": "x" * 10000, "items": list(range(1000))}

        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="bulk_operation",
            id="1",
            params=large_params,
        )

        assert len(request.params["data"]) == 10000
        assert len(request.params["items"]) == 1000

    def test_negative_id(self):
        """Request can have negative integer id."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="method",
            id=-1,
        )

        assert request.id == -1

    def test_very_large_id(self):
        """Request can have very large integer id."""
        large_id = 2**63 - 1

        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="method",
            id=large_id,
        )

        assert request.id == large_id


class TestJsonRpcEquality:
    """Test equality comparison for models."""

    def test_request_equality(self):
        """Two identical requests are equal."""
        request1 = JsonRpcRequest(
            jsonrpc="2.0",
            method="test",
            id="1",
            params={"key": "value"},
        )
        request2 = JsonRpcRequest(
            jsonrpc="2.0",
            method="test",
            id="1",
            params={"key": "value"},
        )

        assert request1 == request2

    def test_request_inequality(self):
        """Different requests are not equal."""
        request1 = JsonRpcRequest(
            jsonrpc="2.0",
            method="test1",
            id="1",
        )
        request2 = JsonRpcRequest(
            jsonrpc="2.0",
            method="test2",
            id="1",
        )

        assert request1 != request2

    def test_error_equality(self):
        """Two identical errors are equal."""
        error1 = JsonRpcError(code=-32600, message="Invalid", data="x")
        error2 = JsonRpcError(code=-32600, message="Invalid", data="x")

        assert error1 == error2

    def test_response_equality(self):
        """Two identical responses are equal."""
        response1 = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result={"key": "value"},
        )
        response2 = JsonRpcResponse(
            jsonrpc="2.0",
            id="1",
            result={"key": "value"},
        )

        assert response1 == response2
