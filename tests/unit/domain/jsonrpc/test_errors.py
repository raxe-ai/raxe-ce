"""Unit tests for JSON-RPC error codes and factory functions.

Tests pure domain logic - no I/O operations, no mocks needed.
Following JSON-RPC 2.0 Specification: https://www.jsonrpc.org/specification

Error Code Ranges:
- -32700: Parse error
- -32600: Invalid Request
- -32601: Method not found
- -32602: Invalid params
- -32603: Internal error
- -32000 to -32099: Server error (reserved for implementation-defined errors)
"""

import pytest

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
from raxe.domain.jsonrpc.models import JsonRpcError


class TestJsonRpcErrorCode:
    """Test JsonRpcErrorCode enum."""

    # ==================== Standard Error Codes ====================

    def test_parse_error_code(self):
        """Parse error has correct code."""
        assert JsonRpcErrorCode.PARSE_ERROR.value == -32700

    def test_invalid_request_code(self):
        """Invalid Request has correct code."""
        assert JsonRpcErrorCode.INVALID_REQUEST.value == -32600

    def test_method_not_found_code(self):
        """Method not found has correct code."""
        assert JsonRpcErrorCode.METHOD_NOT_FOUND.value == -32601

    def test_invalid_params_code(self):
        """Invalid params has correct code."""
        assert JsonRpcErrorCode.INVALID_PARAMS.value == -32602

    def test_internal_error_code(self):
        """Internal error has correct code."""
        assert JsonRpcErrorCode.INTERNAL_ERROR.value == -32603

    # ==================== Server Error Codes (-32000 to -32099) ====================

    def test_server_error_code(self):
        """Server error has correct code in reserved range."""
        assert JsonRpcErrorCode.SERVER_ERROR.value == -32000

    def test_threat_detected_code(self):
        """Threat detected has correct code in reserved range."""
        assert JsonRpcErrorCode.THREAT_DETECTED.value == -32001

    # ==================== Enum Properties ====================

    def test_all_codes_are_negative(self):
        """All error codes are negative integers."""
        for code in JsonRpcErrorCode:
            assert code.value < 0, f"{code.name} has non-negative value"

    def test_all_codes_are_unique(self):
        """All error codes are unique."""
        values = [code.value for code in JsonRpcErrorCode]
        assert len(values) == len(set(values)), "Duplicate error codes found"

    def test_standard_codes_in_correct_range(self):
        """Standard codes are in the -32600 to -32700 range."""
        standard_codes = [
            JsonRpcErrorCode.PARSE_ERROR,
            JsonRpcErrorCode.INVALID_REQUEST,
            JsonRpcErrorCode.METHOD_NOT_FOUND,
            JsonRpcErrorCode.INVALID_PARAMS,
            JsonRpcErrorCode.INTERNAL_ERROR,
        ]
        for code in standard_codes:
            assert -32700 <= code.value <= -32600, f"{code.name} not in standard range"

    def test_server_codes_in_correct_range(self):
        """Server error codes are in the -32000 to -32099 range."""
        server_codes = [
            JsonRpcErrorCode.SERVER_ERROR,
            JsonRpcErrorCode.THREAT_DETECTED,
        ]
        for code in server_codes:
            assert -32099 <= code.value <= -32000, f"{code.name} not in server range"

    def test_code_enum_is_int_subclass(self):
        """Error codes can be used as integers."""
        assert JsonRpcErrorCode.PARSE_ERROR == -32700
        assert JsonRpcErrorCode.INTERNAL_ERROR + 1 == -32602

    def test_code_from_value(self):
        """Error code can be retrieved by value."""
        code = JsonRpcErrorCode(-32700)
        assert code == JsonRpcErrorCode.PARSE_ERROR

    def test_code_from_invalid_value_raises(self):
        """Invalid value raises ValueError."""
        with pytest.raises(ValueError):
            JsonRpcErrorCode(-99999)


class TestErrorCodeMessages:
    """Test default messages for error codes."""

    def test_parse_error_has_message(self):
        """Parse error has descriptive message."""
        assert JsonRpcErrorCode.PARSE_ERROR.message == "Parse error"

    def test_invalid_request_has_message(self):
        """Invalid Request has descriptive message."""
        assert JsonRpcErrorCode.INVALID_REQUEST.message == "Invalid Request"

    def test_method_not_found_has_message(self):
        """Method not found has descriptive message."""
        assert JsonRpcErrorCode.METHOD_NOT_FOUND.message == "Method not found"

    def test_invalid_params_has_message(self):
        """Invalid params has descriptive message."""
        assert JsonRpcErrorCode.INVALID_PARAMS.message == "Invalid params"

    def test_internal_error_has_message(self):
        """Internal error has descriptive message."""
        assert JsonRpcErrorCode.INTERNAL_ERROR.message == "Internal error"

    def test_server_error_has_message(self):
        """Server error has descriptive message."""
        assert JsonRpcErrorCode.SERVER_ERROR.message == "Server error"

    def test_threat_detected_has_message(self):
        """Threat detected has descriptive message."""
        assert JsonRpcErrorCode.THREAT_DETECTED.message == "Threat detected"


class TestCreateParseError:
    """Test create_parse_error factory function."""

    def test_creates_parse_error_basic(self):
        """Creates parse error with default message."""
        error = create_parse_error()

        assert isinstance(error, JsonRpcError)
        assert error.code == -32700
        assert error.message == "Parse error"
        assert error.data is None

    def test_creates_parse_error_with_data(self):
        """Creates parse error with additional data."""
        error = create_parse_error(data="Invalid JSON at position 42")

        assert error.code == -32700
        assert error.data == "Invalid JSON at position 42"

    def test_creates_parse_error_with_dict_data(self):
        """Creates parse error with dict data."""
        error = create_parse_error(data={"position": 42, "char": "}"})

        assert error.data == {"position": 42, "char": "}"}

    def test_creates_parse_error_with_custom_message(self):
        """Creates parse error with custom message."""
        error = create_parse_error(message="Malformed JSON input")

        assert error.message == "Malformed JSON input"


class TestCreateInvalidRequestError:
    """Test create_invalid_request_error factory function."""

    def test_creates_invalid_request_basic(self):
        """Creates invalid request error with default message."""
        error = create_invalid_request_error()

        assert isinstance(error, JsonRpcError)
        assert error.code == -32600
        assert error.message == "Invalid Request"
        assert error.data is None

    def test_creates_invalid_request_with_data(self):
        """Creates invalid request error with data."""
        error = create_invalid_request_error(data="Missing 'method' field")

        assert error.data == "Missing 'method' field"

    def test_creates_invalid_request_with_custom_message(self):
        """Creates invalid request error with custom message."""
        error = create_invalid_request_error(message="Request is not a JSON object")

        assert error.message == "Request is not a JSON object"

    def test_creates_invalid_request_with_validation_errors(self):
        """Creates invalid request error with list of validation errors."""
        validation_errors = [
            "jsonrpc must be '2.0'",
            "method is required",
        ]
        error = create_invalid_request_error(data=validation_errors)

        assert error.data == validation_errors


class TestCreateMethodNotFoundError:
    """Test create_method_not_found_error factory function."""

    def test_creates_method_not_found_basic(self):
        """Creates method not found error with default message."""
        error = create_method_not_found_error()

        assert isinstance(error, JsonRpcError)
        assert error.code == -32601
        assert error.message == "Method not found"
        assert error.data is None

    def test_creates_method_not_found_with_method_name(self):
        """Creates method not found error with method name in data."""
        error = create_method_not_found_error(data="unknown_method")

        assert error.data == "unknown_method"

    def test_creates_method_not_found_with_suggestions(self):
        """Creates method not found error with suggestions."""
        error = create_method_not_found_error(
            data={
                "requested": "scna",
                "suggestions": ["scan", "status"],
            }
        )

        assert error.data["requested"] == "scna"
        assert "scan" in error.data["suggestions"]

    def test_creates_method_not_found_custom_message(self):
        """Creates method not found error with custom message."""
        error = create_method_not_found_error(message="The method 'foo' does not exist")

        assert error.message == "The method 'foo' does not exist"


class TestCreateInvalidParamsError:
    """Test create_invalid_params_error factory function."""

    def test_creates_invalid_params_basic(self):
        """Creates invalid params error with default message."""
        error = create_invalid_params_error()

        assert isinstance(error, JsonRpcError)
        assert error.code == -32602
        assert error.message == "Invalid params"
        assert error.data is None

    def test_creates_invalid_params_with_data(self):
        """Creates invalid params error with data."""
        error = create_invalid_params_error(data="'prompt' is required")

        assert error.data == "'prompt' is required"

    def test_creates_invalid_params_with_schema_errors(self):
        """Creates invalid params error with schema validation errors."""
        schema_errors = {
            "prompt": "required field missing",
            "timeout": "must be positive integer",
        }
        error = create_invalid_params_error(data=schema_errors)

        assert error.data["prompt"] == "required field missing"
        assert error.data["timeout"] == "must be positive integer"

    def test_creates_invalid_params_custom_message(self):
        """Creates invalid params error with custom message."""
        error = create_invalid_params_error(message="Parameter validation failed")

        assert error.message == "Parameter validation failed"


class TestCreateInternalError:
    """Test create_internal_error factory function."""

    def test_creates_internal_error_basic(self):
        """Creates internal error with default message."""
        error = create_internal_error()

        assert isinstance(error, JsonRpcError)
        assert error.code == -32603
        assert error.message == "Internal error"
        assert error.data is None

    def test_creates_internal_error_with_data(self):
        """Creates internal error with data (e.g., error ID for tracking)."""
        error = create_internal_error(data={"error_id": "err_abc123"})

        assert error.data == {"error_id": "err_abc123"}

    def test_creates_internal_error_custom_message(self):
        """Creates internal error with custom message."""
        error = create_internal_error(message="Database connection failed")

        assert error.message == "Database connection failed"

    def test_creates_internal_error_without_sensitive_data(self):
        """Internal error should not expose sensitive stack traces by default."""
        # This is a design guideline test - implementation should be careful
        error = create_internal_error()

        # Data should be None by default, not containing stack traces
        assert error.data is None


class TestCreateServerError:
    """Test create_server_error factory function."""

    def test_creates_server_error_basic(self):
        """Creates server error with default message."""
        error = create_server_error()

        assert isinstance(error, JsonRpcError)
        assert error.code == -32000
        assert error.message == "Server error"
        assert error.data is None

    def test_creates_server_error_with_data(self):
        """Creates server error with data."""
        error = create_server_error(data="Service temporarily unavailable")

        assert error.data == "Service temporarily unavailable"

    def test_creates_server_error_custom_code(self):
        """Creates server error with custom code in reserved range."""
        error = create_server_error(code=-32050)

        assert error.code == -32050

    def test_creates_server_error_rejects_invalid_code(self):
        """Server error rejects code outside reserved range."""
        with pytest.raises(ValueError, match="code must be in range"):
            create_server_error(code=-33000)

    def test_creates_server_error_rejects_standard_codes(self):
        """Server error rejects standard error codes."""
        with pytest.raises(ValueError, match="code must be in range"):
            create_server_error(code=-32600)


class TestCreateThreatDetectedError:
    """Test create_threat_detected_error factory function."""

    def test_creates_threat_detected_basic(self):
        """Creates threat detected error with default message."""
        error = create_threat_detected_error()

        assert isinstance(error, JsonRpcError)
        assert error.code == -32001
        assert error.message == "Threat detected"
        assert error.data is None

    def test_creates_threat_detected_with_threat_info(self):
        """Creates threat detected error with threat information."""
        threat_info = {
            "rule_id": "pi-001",
            "severity": "HIGH",
            "family": "PI",
        }
        error = create_threat_detected_error(data=threat_info)

        assert error.data["rule_id"] == "pi-001"
        assert error.data["severity"] == "HIGH"
        assert error.data["family"] == "PI"

    def test_creates_threat_detected_custom_message(self):
        """Creates threat detected error with custom message."""
        error = create_threat_detected_error(message="Prompt injection attack detected")

        assert error.message == "Prompt injection attack detected"

    def test_creates_threat_detected_with_multiple_threats(self):
        """Creates threat detected error with multiple threats."""
        threats = {
            "threats": [
                {"rule_id": "pi-001", "severity": "HIGH"},
                {"rule_id": "jb-002", "severity": "MEDIUM"},
            ],
            "highest_severity": "HIGH",
            "action": "blocked",
        }
        error = create_threat_detected_error(data=threats)

        assert len(error.data["threats"]) == 2
        assert error.data["highest_severity"] == "HIGH"

    def test_creates_threat_detected_privacy_safe(self):
        """Threat detected error should NOT contain matched text (privacy)."""
        # This is a design guideline test
        error = create_threat_detected_error(
            data={
                "rule_id": "pi-001",
                # Note: should NOT include "matched_text" or "prompt"
            }
        )

        assert "matched_text" not in (error.data or {})
        assert "prompt" not in (error.data or {})


class TestErrorFactoryImmutability:
    """Test that factory functions return immutable errors."""

    def test_parse_error_immutable(self):
        """Parse error is immutable."""
        error = create_parse_error()

        with pytest.raises(AttributeError):
            error.code = -32000  # type: ignore

    def test_invalid_request_error_immutable(self):
        """Invalid request error is immutable."""
        error = create_invalid_request_error()

        with pytest.raises(AttributeError):
            error.message = "New message"  # type: ignore

    def test_threat_detected_error_immutable(self):
        """Threat detected error is immutable."""
        error = create_threat_detected_error()

        with pytest.raises(AttributeError):
            error.data = {"new": "data"}  # type: ignore


class TestErrorSerialization:
    """Test that factory-created errors serialize correctly."""

    def test_parse_error_to_dict(self):
        """Parse error serializes correctly."""
        error = create_parse_error(data="invalid")

        data = error.to_dict()

        assert data["code"] == -32700
        assert data["message"] == "Parse error"
        assert data["data"] == "invalid"

    def test_invalid_request_to_dict(self):
        """Invalid request error serializes correctly."""
        error = create_invalid_request_error()

        data = error.to_dict()

        assert data["code"] == -32600
        assert "data" not in data

    def test_threat_detected_to_dict(self):
        """Threat detected error serializes correctly."""
        error = create_threat_detected_error(data={"rule_id": "pi-001", "severity": "HIGH"})

        data = error.to_dict()

        assert data["code"] == -32001
        assert data["data"]["rule_id"] == "pi-001"


class TestErrorCodeDescriptions:
    """Test that error codes have useful descriptions."""

    def test_parse_error_description(self):
        """Parse error has informative description."""
        assert hasattr(JsonRpcErrorCode.PARSE_ERROR, "description")
        assert "JSON" in JsonRpcErrorCode.PARSE_ERROR.description

    def test_invalid_request_description(self):
        """Invalid request has informative description."""
        assert "JSON-RPC" in JsonRpcErrorCode.INVALID_REQUEST.description

    def test_method_not_found_description(self):
        """Method not found has informative description."""
        assert "method" in JsonRpcErrorCode.METHOD_NOT_FOUND.description.lower()

    def test_invalid_params_description(self):
        """Invalid params has informative description."""
        assert "param" in JsonRpcErrorCode.INVALID_PARAMS.description.lower()

    def test_internal_error_description(self):
        """Internal error has informative description."""
        assert "internal" in JsonRpcErrorCode.INTERNAL_ERROR.description.lower()

    def test_threat_detected_description(self):
        """Threat detected has informative description."""
        desc = JsonRpcErrorCode.THREAT_DETECTED.description.lower()
        assert "threat" in desc or "security" in desc


class TestErrorCodeComparison:
    """Test error code comparison operations."""

    def test_compare_with_integer(self):
        """Error code can be compared with integer."""
        assert JsonRpcErrorCode.PARSE_ERROR == -32700
        assert JsonRpcErrorCode.INVALID_REQUEST != -32700

    def test_compare_enum_members(self):
        """Error codes can be compared with each other."""
        assert JsonRpcErrorCode.PARSE_ERROR != JsonRpcErrorCode.INVALID_REQUEST
        assert JsonRpcErrorCode.PARSE_ERROR == JsonRpcErrorCode.PARSE_ERROR

    def test_ordering(self):
        """Error codes can be ordered."""
        assert JsonRpcErrorCode.PARSE_ERROR < JsonRpcErrorCode.INVALID_REQUEST
        assert JsonRpcErrorCode.THREAT_DETECTED > JsonRpcErrorCode.PARSE_ERROR


class TestErrorCodeLookup:
    """Test error code lookup functionality."""

    def test_lookup_by_name(self):
        """Error code can be looked up by name."""
        code = JsonRpcErrorCode["PARSE_ERROR"]
        assert code.value == -32700

    def test_lookup_by_value(self):
        """Error code can be looked up by value."""
        code = JsonRpcErrorCode(-32601)
        assert code == JsonRpcErrorCode.METHOD_NOT_FOUND

    def test_all_codes_accessible(self):
        """All error codes are accessible via enum."""
        expected_codes = [
            "PARSE_ERROR",
            "INVALID_REQUEST",
            "METHOD_NOT_FOUND",
            "INVALID_PARAMS",
            "INTERNAL_ERROR",
            "SERVER_ERROR",
            "THREAT_DETECTED",
        ]

        for name in expected_codes:
            assert hasattr(JsonRpcErrorCode, name)
            code = getattr(JsonRpcErrorCode, name)
            assert isinstance(code.value, int)
