"""Tests for policy validation."""
import base64
import hashlib
import json

import pytest

from raxe.infrastructure.security.policy_validator import (
    PolicyValidationError,
    PolicyValidator,
)
from raxe.infrastructure.security.signatures import CRYPTO_AVAILABLE

# Skip signature tests if cryptography not available
signature_tests = pytest.mark.skipif(
    not CRYPTO_AVAILABLE, reason="cryptography package not installed"
)


class TestPolicyValidator:
    """Test PolicyValidator class."""

    def test_validate_policy_valid(self):
        """Test validating valid policy."""
        validator = PolicyValidator()

        policy_data = {
            "customer_id": "cust_test123",
            "policies": [
                {"action": "block", "severity": "high"},
                {"action": "alert", "severity": "medium"},
            ],
        }

        api_key = "raxe_live_cust_test123_randomsuffix123"

        # Should not raise
        validator.validate_policy(policy_data, api_key)

    def test_validate_policy_invalid_api_key(self):
        """Test validating policy with invalid API key."""
        validator = PolicyValidator()

        policy_data = {
            "customer_id": "cust_test123",
            "policies": [],
        }

        with pytest.raises(PolicyValidationError, match="Invalid API key"):
            validator.validate_policy(policy_data, "invalid_key")

    def test_validate_policy_missing_customer_id(self):
        """Test validating policy without customer_id."""
        validator = PolicyValidator()

        policy_data = {
            "policies": [],
        }

        api_key = "raxe_live_cust_test123_randomsuffix123"

        with pytest.raises(PolicyValidationError, match="missing customer_id"):
            validator.validate_policy(policy_data, api_key)

    def test_validate_policy_customer_id_mismatch(self):
        """Test validating policy with mismatched customer ID."""
        validator = PolicyValidator()

        policy_data = {
            "customer_id": "cust_different",
            "policies": [],
        }

        api_key = "raxe_live_cust_test123_randomsuffix123"

        with pytest.raises(PolicyValidationError, match="customer_id mismatch"):
            validator.validate_policy(policy_data, api_key)

    def test_validate_policy_missing_policies_field(self):
        """Test validating policy without policies field."""
        validator = PolicyValidator()

        policy_data = {
            "customer_id": "cust_test123",
        }

        api_key = "raxe_live_cust_test123_randomsuffix123"

        with pytest.raises(PolicyValidationError, match="Missing required field: policies"):
            validator.validate_policy(policy_data, api_key)

    def test_validate_policy_invalid_policies_type(self):
        """Test validating policy with non-list policies."""
        validator = PolicyValidator()

        policy_data = {
            "customer_id": "cust_test123",
            "policies": {"action": "block"},  # Dict instead of list
        }

        api_key = "raxe_live_cust_test123_randomsuffix123"

        with pytest.raises(PolicyValidationError, match="policies must be a list"):
            validator.validate_policy(policy_data, api_key)

    def test_validate_policy_empty_policies(self):
        """Test validating policy with empty policies list."""
        validator = PolicyValidator()

        policy_data = {
            "customer_id": "cust_test123",
            "policies": [],
        }

        api_key = "raxe_live_cust_test123_randomsuffix123"

        # Empty policies list is valid
        validator.validate_policy(policy_data, api_key)

    @signature_tests
    def test_validate_policy_invalid_signature_algorithm(self):
        """Test validating policy with unsupported signature algorithm."""
        validator = PolicyValidator()

        policy_data = {
            "customer_id": "cust_test123",
            "policies": [],
            "signature": "rsa:signature_here",
            "signature_algorithm": "rsa",
        }

        api_key = "raxe_live_cust_test123_randomsuffix123"

        with pytest.raises(
            PolicyValidationError, match="Unsupported signature algorithm"
        ):
            validator.validate_policy(policy_data, api_key)

    @signature_tests
    def test_validate_policy_invalid_signature_format(self):
        """Test validating policy with invalid signature format."""
        validator = PolicyValidator()

        policy_data = {
            "customer_id": "cust_test123",
            "policies": [],
            "signature": "invalid_format",
            "signature_algorithm": "ed25519",
        }

        api_key = "raxe_live_cust_test123_randomsuffix123"

        with pytest.raises(PolicyValidationError, match="Signature verification failed"):
            validator.validate_policy(policy_data, api_key)

    @signature_tests
    def test_validate_policy_wrong_signature(self):
        """Test validating policy with wrong signature."""
        validator = PolicyValidator()

        policy_data = {
            "customer_id": "cust_test123",
            "policies": [{"action": "block"}],
            "signature": "ed25519:" + base64.b64encode(b"0" * 64).decode(),
            "signature_algorithm": "ed25519",
        }

        api_key = "raxe_live_cust_test123_randomsuffix123"

        with pytest.raises(PolicyValidationError, match="Signature verification failed"):
            validator.validate_policy(policy_data, api_key)

    @signature_tests
    def test_validate_policy_valid_signature(self):
        """Test validating policy with valid signature."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        # Generate key pair
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

        # Create policy content
        policy_content = {
            "customer_id": "cust_test123",
            "policies": [{"action": "block", "severity": "high"}],
        }

        # Sign it
        content_str = json.dumps(policy_content, sort_keys=True)
        content_hash = hashlib.sha256(content_str.encode()).digest()
        signature_bytes = private_key.sign(content_hash)
        sig_b64 = base64.b64encode(signature_bytes).decode()

        # Add signature to policy
        policy_data = {
            **policy_content,
            "signature": f"ed25519:{sig_b64}",
            "signature_algorithm": "ed25519",
        }

        # Create validator with custom public key
        from raxe.infrastructure.security.signatures import SignatureVerifier

        validator = PolicyValidator()
        validator.sig_verifier = SignatureVerifier(public_key_pem=public_pem)

        api_key = "raxe_live_cust_test123_randomsuffix123"

        # Should validate successfully
        validator.validate_policy(policy_data, api_key)

    def test_validate_policy_complex_structure(self):
        """Test validating policy with complex policy structure."""
        validator = PolicyValidator()

        policy_data = {
            "customer_id": "cust_test123",
            "policies": [
                {
                    "action": "block",
                    "severity": "critical",
                    "rule_packs": ["core", "custom"],
                },
                {
                    "action": "alert",
                    "severity": "medium",
                    "notifications": ["email", "slack"],
                },
                {
                    "action": "log",
                    "severity": "low",
                },
            ],
        }

        api_key = "raxe_live_cust_test123_randomsuffix123"

        # Complex structure should validate
        validator.validate_policy(policy_data, api_key)
