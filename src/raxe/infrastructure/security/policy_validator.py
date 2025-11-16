"""Policy validation and security checks.

Validates customer policies before loading.
"""
import base64
import hashlib
import json
from typing import Any

from raxe.infrastructure.security.auth import APIKeyValidator
from raxe.infrastructure.security.signatures import SignatureVerifier


class PolicyValidationError(Exception):
    """Policy validation failed."""

    pass


class PolicyValidator:
    """
    Validate customer policies.

    Ensures policies are:
    1. Signed correctly (if from cloud)
    2. Match the customer's API key
    3. Valid schema
    """

    def __init__(self) -> None:
        """Initialize validators."""
        self.key_validator = APIKeyValidator()
        self._sig_verifier: SignatureVerifier | None = None  # Lazy init only if needed

    def validate_policy(self, policy_data: dict[str, Any], api_key: str) -> None:
        """
        Validate policy data.

        Args:
            policy_data: Policy JSON data
            api_key: Customer's API key

        Raises:
            PolicyValidationError: If validation fails
        """
        # Parse API key
        try:
            parsed_key = self.key_validator.validate_key(api_key)
        except Exception as e:
            raise PolicyValidationError(f"Invalid API key: {e}") from e

        # Check customer ID match
        policy_customer_id = policy_data.get("customer_id")
        if not policy_customer_id:
            raise PolicyValidationError("Policy missing customer_id")

        if policy_customer_id != parsed_key.customer_id:
            raise PolicyValidationError(
                f"Policy customer_id mismatch: "
                f"{policy_customer_id} != {parsed_key.customer_id}"
            )

        # Verify signature if present
        signature = policy_data.get("signature")
        if signature:
            self._verify_policy_signature(policy_data, signature)

        # Validate schema
        self._validate_policy_schema(policy_data)

    @property
    def sig_verifier(self) -> SignatureVerifier:
        """Lazy-load signature verifier."""
        if self._sig_verifier is None:
            self._sig_verifier = SignatureVerifier()
        return self._sig_verifier

    @sig_verifier.setter
    def sig_verifier(self, value: SignatureVerifier) -> None:
        """Allow setting custom verifier for testing."""
        self._sig_verifier = value

    def _verify_policy_signature(
        self, policy_data: dict[str, Any], signature: str
    ) -> None:
        """Verify policy signature."""
        # Extract policies content (everything except signature)
        policy_content = {
            k: v
            for k, v in policy_data.items()
            if k not in ["signature", "signature_algorithm"]
        }

        # Hash content
        content_str = json.dumps(policy_content, sort_keys=True)
        content_hash = hashlib.sha256(content_str.encode()).digest()

        # Verify signature
        sig_algorithm = policy_data.get("signature_algorithm", "ed25519")

        if sig_algorithm != "ed25519":
            raise PolicyValidationError(
                f"Unsupported signature algorithm: {sig_algorithm}"
            )

        try:
            sig_b64 = signature.split(":", 1)[1]
            sig_bytes = base64.b64decode(sig_b64)

            self.sig_verifier.public_key.verify(sig_bytes, content_hash)
        except Exception as e:
            raise PolicyValidationError(f"Signature verification failed: {e}") from e

    def _validate_policy_schema(self, policy_data: dict[str, Any]) -> None:
        """Validate policy schema structure."""
        required_fields = ["customer_id", "policies"]

        for field in required_fields:
            if field not in policy_data:
                raise PolicyValidationError(f"Missing required field: {field}")

        # Validate policies is a list
        if not isinstance(policy_data["policies"], list):
            raise PolicyValidationError("policies must be a list")
