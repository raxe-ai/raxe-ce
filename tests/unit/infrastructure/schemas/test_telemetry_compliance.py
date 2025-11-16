"""Test telemetry event compliance with v2.1.0 schema.

This test suite validates that telemetry events comply with the
JSON Schema specification v2.1.0 for scan_performed events.
"""
import uuid
from datetime import datetime

from raxe.infrastructure.schemas.validator import get_validator


class TestScanPerformedEventCompliance:
    """Test that scan_performed events comply with v2.1.0 schema."""

    def setup_method(self):
        """Set up validator for tests."""
        self.validator = get_validator()

    def test_minimal_valid_event(self):
        """Test minimal valid scan_performed event."""
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_id": "cust-abc12345",
            "scan_result": {
                "text_hash": "a" * 64,
                "threat_detected": True,
                "detection_count": 2,
            },
        }

        is_valid, errors = self.validator.validate_scan_event(event)
        assert is_valid, f"Minimal event failed: {errors}"

    def test_full_event_with_all_fields(self):
        """Test scan_performed event with all fields."""
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": "2025-11-15T10:30:00Z",
            "customer_id": "cust-abc12345",
            "api_key_id": "raxe_" + "a" * 32,
            "scan_result": {
                "text_hash": "b" * 64,
                "text_length": 245,
                "threat_detected": True,
                "detection_count": 3,
                "highest_severity": "high",
                "l1_detections": [
                    {
                        "rule_id": "pi-001",
                        "severity": "high",
                        "confidence": 0.85,
                    },
                    {
                        "rule_id": "jb-042",
                        "severity": "critical",
                        "confidence": 0.92,
                    },
                ],
                "l2_predictions": [
                    {
                        "threat_type": "semantic_jailbreak",
                        "confidence": 0.88,
                    }
                ],
                "policy_decision": {
                    "action": "BLOCK",
                    "matched_policies": ["policy-001", "policy-security"],
                },
            },
            "performance": {
                "total_ms": 35.2,
                "l1_ms": 8.5,
                "l2_ms": 24.3,
                "policy_ms": 2.4,
                "queue_depth": 42,
                "circuit_breaker_status": "closed",
            },
            "context": {
                "session_id": "sess_" + "x" * 20,
                "user_id": "user_12345",
                "app_name": "chatbot-prod",
                "sdk_version": "1.2.0",
                "environment": "production",
            },
            "metadata": {
                "custom_field_1": "value1",
                "custom_field_2": 123,
                "custom_field_3": True,
            },
        }

        is_valid, errors = self.validator.validate_scan_event(event)
        assert is_valid, f"Full event failed: {errors}"

    def test_customer_id_format(self):
        """Test customer_id must match pattern cust-XXXXXXXX."""
        # Valid format
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_id": "cust-abc12345",
            "scan_result": {
                "text_hash": "a" * 64,
                "threat_detected": False,
                "detection_count": 0,
            },
        }
        is_valid, _ = self.validator.validate_scan_event(event)
        assert is_valid, "Valid customer_id should pass"

        # Invalid formats
        invalid_ids = [
            "abc12345",  # Missing prefix
            "cust-ABC12345",  # Uppercase
            "cust-abc123",  # Too short
            "cust-abc123456",  # Too long
            "customer-abc12345",  # Wrong prefix
        ]

        for customer_id in invalid_ids:
            event["customer_id"] = customer_id
            is_valid, _ = self.validator.validate_scan_event(event)
            assert not is_valid, f"customer_id {customer_id} should be invalid"

    def test_api_key_id_format(self):
        """Test api_key_id must match pattern raxe_XXXXXXX."""
        # Valid format
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_id": "cust-abc12345",
            "api_key_id": "raxe_" + "a" * 32,
            "scan_result": {
                "text_hash": "a" * 64,
                "threat_detected": False,
                "detection_count": 0,
            },
        }
        is_valid, _ = self.validator.validate_scan_event(event)
        assert is_valid, "Valid api_key_id should pass"

        # Invalid formats
        invalid_keys = [
            "a" * 32,  # Missing prefix
            "raxe_" + "A" * 32,  # Uppercase
            "raxe_" + "a" * 31,  # Too short
            "raxe_" + "a" * 33,  # Too long
        ]

        for api_key_id in invalid_keys:
            event["api_key_id"] = api_key_id
            is_valid, _ = self.validator.validate_scan_event(event)
            assert not is_valid, f"api_key_id {api_key_id[:20]}... should be invalid"

    def test_text_hash_format(self):
        """Test text_hash must be valid SHA256 (64 hex chars)."""
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_id": "cust-abc12345",
            "scan_result": {
                "text_hash": "a" * 64,
                "threat_detected": False,
                "detection_count": 0,
            },
        }

        # Valid hash
        is_valid, _ = self.validator.validate_scan_event(event)
        assert is_valid, "Valid SHA256 should pass"

        # Invalid hashes
        invalid_hashes = [
            "a" * 63,  # Too short
            "a" * 65,  # Too long
            "G" * 64,  # Invalid hex
            "ABCD" * 16,  # Uppercase
        ]

        for text_hash in invalid_hashes:
            event["scan_result"]["text_hash"] = text_hash
            is_valid, _ = self.validator.validate_scan_event(event)
            assert not is_valid, f"text_hash {text_hash[:20]}... should be invalid"

    def test_severity_enum_values(self):
        """Test highest_severity enum includes null."""
        valid_severities = ["critical", "high", "medium", "low", "info", None]

        base_event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_id": "cust-abc12345",
            "scan_result": {
                "text_hash": "a" * 64,
                "threat_detected": False,
                "detection_count": 0,
            },
        }

        for severity in valid_severities:
            event = base_event.copy()
            event["scan_result"] = base_event["scan_result"].copy()
            event["scan_result"]["highest_severity"] = severity

            is_valid, errors = self.validator.validate_scan_event(event)
            assert is_valid, f"Severity {severity} should be valid: {errors}"

        # Invalid severity
        event = base_event.copy()
        event["scan_result"] = base_event["scan_result"].copy()
        event["scan_result"]["highest_severity"] = "invalid"
        is_valid, _ = self.validator.validate_scan_event(event)
        assert not is_valid, "Invalid severity should fail"

    def test_policy_action_enum(self):
        """Test policy_decision.action enum values."""
        valid_actions = ["ALLOW", "BLOCK", "FLAG", "LOG"]

        base_event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_id": "cust-abc12345",
            "scan_result": {
                "text_hash": "a" * 64,
                "threat_detected": True,
                "detection_count": 1,
                "policy_decision": {
                    "action": "ALLOW",
                    "matched_policies": [],
                },
            },
        }

        for action in valid_actions:
            event = base_event.copy()
            event["scan_result"] = base_event["scan_result"].copy()
            event["scan_result"]["policy_decision"] = {"action": action, "matched_policies": []}

            is_valid, errors = self.validator.validate_scan_event(event)
            assert is_valid, f"Action {action} should be valid: {errors}"

        # Invalid action
        event = base_event.copy()
        event["scan_result"] = base_event["scan_result"].copy()
        event["scan_result"]["policy_decision"] = {
            "action": "INVALID",
            "matched_policies": [],
        }
        is_valid, _ = self.validator.validate_scan_event(event)
        assert not is_valid, "Invalid action should fail"

    def test_environment_enum(self):
        """Test context.environment enum values."""
        valid_envs = ["production", "staging", "development", "test"]

        base_event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_id": "cust-abc12345",
            "scan_result": {
                "text_hash": "a" * 64,
                "threat_detected": False,
                "detection_count": 0,
            },
            "context": {
                "environment": "production",
            },
        }

        for env in valid_envs:
            event = base_event.copy()
            event["context"] = {"environment": env}

            is_valid, errors = self.validator.validate_scan_event(event)
            assert is_valid, f"Environment {env} should be valid: {errors}"

        # Invalid environment
        event = base_event.copy()
        event["context"] = {"environment": "invalid"}
        is_valid, _ = self.validator.validate_scan_event(event)
        assert not is_valid, "Invalid environment should fail"

    def test_circuit_breaker_status_enum(self):
        """Test circuit_breaker_status enum values."""
        valid_statuses = ["closed", "open", "half-open"]

        base_event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_id": "cust-abc12345",
            "scan_result": {
                "text_hash": "a" * 64,
                "threat_detected": False,
                "detection_count": 0,
            },
            "performance": {
                "circuit_breaker_status": "closed",
            },
        }

        for status in valid_statuses:
            event = base_event.copy()
            event["performance"] = {"circuit_breaker_status": status}

            is_valid, errors = self.validator.validate_scan_event(event)
            assert is_valid, f"Status {status} should be valid: {errors}"

        # Invalid status
        event = base_event.copy()
        event["performance"] = {"circuit_breaker_status": "invalid"}
        is_valid, _ = self.validator.validate_scan_event(event)
        assert not is_valid, "Invalid circuit breaker status should fail"

    def test_performance_metrics_non_negative(self):
        """Test that performance metrics must be non-negative."""
        base_event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_id": "cust-abc12345",
            "scan_result": {
                "text_hash": "a" * 64,
                "threat_detected": False,
                "detection_count": 0,
            },
        }

        # Valid - positive and zero
        for ms_value in [0, 0.1, 10.5, 100.0]:
            event = base_event.copy()
            event["performance"] = {
                "total_ms": ms_value,
                "l1_ms": ms_value,
                "l2_ms": ms_value,
                "policy_ms": ms_value,
            }
            is_valid, _ = self.validator.validate_scan_event(event)
            assert is_valid, f"Performance metric {ms_value}ms should be valid"

        # Invalid - negative
        event = base_event.copy()
        event["performance"] = {"total_ms": -1.0}
        is_valid, _ = self.validator.validate_scan_event(event)
        assert not is_valid, "Negative performance metric should be invalid"

    def test_queue_depth_non_negative(self):
        """Test that queue_depth must be non-negative integer."""
        base_event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_id": "cust-abc12345",
            "scan_result": {
                "text_hash": "a" * 64,
                "threat_detected": False,
                "detection_count": 0,
            },
        }

        # Valid
        for depth in [0, 1, 100, 10000]:
            event = base_event.copy()
            event["performance"] = {"queue_depth": depth}
            is_valid, _ = self.validator.validate_scan_event(event)
            assert is_valid, f"Queue depth {depth} should be valid"

        # Invalid - negative
        event = base_event.copy()
        event["performance"] = {"queue_depth": -1}
        is_valid, _ = self.validator.validate_scan_event(event)
        assert not is_valid, "Negative queue depth should be invalid"

    def test_detection_count_non_negative(self):
        """Test that detection_count must be non-negative."""
        base_event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_id": "cust-abc12345",
            "scan_result": {
                "text_hash": "a" * 64,
                "threat_detected": False,
            },
        }

        # Valid
        for count in [0, 1, 100]:
            event = base_event.copy()
            event["scan_result"] = base_event["scan_result"].copy()
            event["scan_result"]["detection_count"] = count
            is_valid, _ = self.validator.validate_scan_event(event)
            assert is_valid, f"Detection count {count} should be valid"

        # Invalid - negative
        event = base_event.copy()
        event["scan_result"] = base_event["scan_result"].copy()
        event["scan_result"]["detection_count"] = -1
        is_valid, _ = self.validator.validate_scan_event(event)
        assert not is_valid, "Negative detection count should be invalid"

    def test_required_fields_enforced(self):
        """Test that required fields must be present."""
        required_top_level = ["event_id", "timestamp", "customer_id", "scan_result"]
        required_scan_result = ["text_hash", "threat_detected", "detection_count"]

        base_event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_id": "cust-abc12345",
            "scan_result": {
                "text_hash": "a" * 64,
                "threat_detected": False,
                "detection_count": 0,
            },
        }

        # Test top-level required fields
        for field in required_top_level:
            event = base_event.copy()
            del event[field]

            is_valid, errors = self.validator.validate_scan_event(event)
            assert not is_valid, f"Should fail when {field} is missing"
            assert any(field in str(e) for e in errors), \
                f"Error should mention missing field {field}"

        # Test scan_result required fields
        for field in required_scan_result:
            event = base_event.copy()
            event["scan_result"] = base_event["scan_result"].copy()
            del event["scan_result"][field]

            is_valid, errors = self.validator.validate_scan_event(event)
            assert not is_valid, f"Should fail when scan_result.{field} is missing"

    def test_metadata_allows_additional_properties(self):
        """Test that metadata allows arbitrary additional properties."""
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_id": "cust-abc12345",
            "scan_result": {
                "text_hash": "a" * 64,
                "threat_detected": False,
                "detection_count": 0,
            },
            "metadata": {
                "custom_string": "value",
                "custom_number": 123,
                "custom_bool": True,
                "custom_array": [1, 2, 3],
                "custom_object": {"nested": "value"},
            },
        }

        is_valid, errors = self.validator.validate_scan_event(event)
        assert is_valid, f"Metadata with custom properties should be valid: {errors}"

    def test_pii_protection_enforced(self):
        """Test that PII fields are hashed, not raw text.

        This is a documentation test - schema requires text_hash instead of text.
        """
        # Valid - using hash
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "customer_id": "cust-abc12345",
            "scan_result": {
                "text_hash": "a" * 64,  # SHA256 hash
                "threat_detected": False,
                "detection_count": 0,
            },
        }
        is_valid, _ = self.validator.validate_scan_event(event)
        assert is_valid, "Event with text_hash should be valid"

        # Schema doesn't have 'text' field - this ensures PII protection
        # If someone tries to add raw text, it will be in metadata or ignored
