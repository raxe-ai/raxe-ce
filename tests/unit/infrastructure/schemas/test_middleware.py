"""Tests for schema validation middleware."""
import pytest

from raxe.infrastructure.schemas.middleware import (
    SchemaValidationMiddleware,
    validate_request,
    validate_response,
)


class TestSchemaValidationMiddleware:
    """Test schema validation middleware."""

    def test_middleware_initialization(self):
        """Test middleware initializes correctly."""
        middleware = SchemaValidationMiddleware()
        assert middleware.schema_dir.exists()
        assert len(middleware._validators) == 0

    def test_validate_telemetry_scan_performed(self):
        """Test telemetry validation for scan_performed events."""
        middleware = SchemaValidationMiddleware()

        valid_event = {
            "event_type": "scan_performed",
            "event_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "2024-01-01T00:00:00Z",
            "customer_id": "cust-abc12345",
            "api_key_id": "raxe_" + "a" * 32,
            "scan_result": {
                "text_hash": "a" * 64,
                "text_length": 100,
                "threat_detected": True,
                "detection_count": 2,
                "highest_severity": "high",
            },
            "performance": {
                "total_ms": 15.2,
                "l1_ms": 10.5,
            },
            "context": {
                "sdk_version": "1.0.0",
                "environment": "production",
            },
        }

        assert middleware.validate_telemetry(valid_event) is True

    def test_validate_telemetry_invalid_event(self):
        """Test telemetry validation rejects invalid events."""
        middleware = SchemaValidationMiddleware()

        invalid_event = {
            "event_type": "scan_performed",
            # Missing required fields
            "text_hash": "invalid",  # Too short
        }

        assert middleware.validate_telemetry(invalid_event) is False

    def test_validate_telemetry_unknown_type(self):
        """Test telemetry validation handles unknown event types."""
        middleware = SchemaValidationMiddleware()

        unknown_event = {
            "event_type": "unknown_event",
            "data": "some data",
        }

        assert middleware.validate_telemetry(unknown_event) is False

    def test_validate_scan_request_defaults(self):
        """Test scan request validation applies defaults."""
        middleware = SchemaValidationMiddleware()

        minimal_request = {
            "enabled_tiers": ["core"]
        }
        normalized = middleware.validate_scan_request(minimal_request)

        assert normalized["enabled_tiers"] == ["core"]
        assert "max_text_length" in normalized or "max_scan_duration_ms" in normalized

    def test_validate_scan_request_custom(self):
        """Test scan request validation with custom values."""
        middleware = SchemaValidationMiddleware()

        custom_request = {
            "enabled_tiers": ["core", "community"],
            "l1_enabled": True,
            "l2_enabled": False,
        }

        normalized = middleware.validate_scan_request(custom_request)

        assert normalized["enabled_tiers"] == ["core", "community"]
        assert normalized["l1_enabled"] is True
        assert normalized["l2_enabled"] is False

    def test_validate_scan_request_invalid(self):
        """Test scan request validation rejects invalid config."""
        middleware = SchemaValidationMiddleware()

        invalid_request = {
            "timeout_ms": -100,  # Negative timeout
        }

        with pytest.raises(ValueError, match="Invalid scan configuration"):
            middleware.validate_scan_request(invalid_request)

    def test_validate_ml_output_valid(self):
        """Test ML output validation for valid predictions."""
        middleware = SchemaValidationMiddleware()

        valid_output = {
            "predictions": [
                {
                    "threat_type": "semantic_jailbreak",
                    "confidence": 0.95,
                }
            ],
            "confidence": 0.95,
            "model_version": "v1.0.0",
            "processing_time_ms": 50.5,
        }

        assert middleware.validate_ml_output(valid_output) is True

    def test_validate_ml_output_invalid(self):
        """Test ML output validation rejects invalid data."""
        middleware = SchemaValidationMiddleware()

        invalid_output = {
            "predictions": [
                {
                    "threat_type": "invalid_type",
                    "confidence": 1.5,  # Out of range
                }
            ],
        }

        assert middleware.validate_ml_output(invalid_output) is False

    def test_request_decorator(self):
        """Test request validation decorator."""
        middleware = SchemaValidationMiddleware()

        @middleware.validate_request("v1.0.0/config/scan_config")
        def process_scan(config):
            return f"Processing with tiers: {config['enabled_tiers']}"

        # Valid request should work
        valid_config = {
            "enabled_tiers": ["core"]
        }
        result = process_scan(valid_config)
        assert "core" in result

        # Invalid request should raise
        invalid_config = {"timeout_ms": -1}
        with pytest.raises(ValueError, match="Invalid request"):
            process_scan(invalid_config)

    def test_response_decorator(self):
        """Test response validation decorator."""
        middleware = SchemaValidationMiddleware()

        @middleware.validate_response("v2.1.0/events/scan_performed")
        def get_telemetry_event():
            return {
                "event_type": "scan_performed",
                "event_id": "123e4567-e89b-12d3-a456-426614174000",
                "timestamp": "2024-01-01T00:00:00Z",
                "customer_id": "cust-abc12345",
                "api_key_id": "raxe_" + "a" * 32,
                "scan_result": {
                    "text_hash": "a" * 64,
                    "text_length": 100,
                    "threat_detected": False,
                    "detection_count": 0,
                },
                "performance": {
                    "total_ms": 10.0,
                    "l1_ms": 5.0,
                },
                "context": {
                    "sdk_version": "1.0.0",
                    "environment": "production",
                },
            }

        # Should not raise for valid response
        result = get_telemetry_event()
        assert result["event_type"] == "scan_performed"

    def test_response_decorator_with_object(self):
        """Test response validation with object having to_dict method."""
        middleware = SchemaValidationMiddleware()

        class MockResult:
            def to_dict(self):
                return {
                    "event_type": "scan_performed",
                    "event_id": "123e4567-e89b-12d3-a456-426614174000",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "customer_id": "cust-abc12345",
                    "api_key_id": "raxe_" + "b" * 32,
                    "scan_result": {
                        "text_hash": "b" * 64,
                        "text_length": 50,
                        "threat_detected": True,
                        "detection_count": 1,
                        "highest_severity": "low",
                    },
                    "performance": {
                        "total_ms": 8.0,
                        "l1_ms": 3.0,
                    },
                    "context": {
                        "sdk_version": "1.0.0",
                        "environment": "test",
                    },
                }

        @middleware.validate_response("v2.1.0/events/scan_performed")
        def get_result():
            return MockResult()

        # Should handle object with to_dict
        result = get_result()
        assert hasattr(result, 'to_dict')

    def test_global_decorators(self):
        """Test global convenience decorators."""

        @validate_request("v1.0.0/config/scan_config")
        def scan_with_config(config):
            return config["enabled_tiers"][0]

        @validate_response("v2.1.0/events/scan_performed")
        def create_event():
            return {
                "event_type": "scan_performed",
                "event_id": "123e4567-e89b-12d3-a456-426614174000",
                "timestamp": "2024-01-01T00:00:00Z",
                "customer_id": "cust-abc12345",
                "api_key_id": "raxe_" + "c" * 32,
                "scan_result": {
                    "text_hash": "c" * 64,
                    "text_length": 10,
                    "threat_detected": False,
                    "detection_count": 0,
                },
                "performance": {
                    "total_ms": 2.0,
                    "l1_ms": 1.0,
                },
                "context": {
                    "sdk_version": "1.0.0",
                    "environment": "development",
                },
            }

        # Test request decorator
        tier = scan_with_config({
            "enabled_tiers": ["core"]
        })
        assert tier == "core"

        # Test response decorator
        event = create_event()
        assert event["event_id"] == "123e4567-e89b-12d3-a456-426614174000"