"""Policy validation and security verification.

Validates policies for security:
- Cryptographic signature verification (for cloud policies)
- Customer ID matching
- Schema validation
"""
import hashlib
import json

from raxe.domain.policies.models import Policy
from raxe.infrastructure.security.auth import APIKey
from raxe.infrastructure.security.signatures import SignatureVerifier


class PolicyValidationError(Exception):
    """Policy validation failed."""
    pass


class PolicyValidator:
    """Validate policies for security and correctness.

    Performs multi-layer validation:
    1. Schema validation (already done by domain models)
    2. Customer ID matching (policy ownership)
    3. Signature verification (for cloud policies)
    """

    def __init__(
        self,
        signature_verifier: SignatureVerifier | None = None,
    ) -> None:
        """Initialize validator.

        Args:
            signature_verifier: Signature verifier (None = create default)
        """
        self.signature_verifier = signature_verifier

    def validate_policies(
        self,
        policies: list[Policy],
        api_key: APIKey,
        *,
        require_signature: bool = False,
        signature: str | None = None,
    ) -> list[Policy]:
        """Validate policies for customer.

        Args:
            policies: Policies to validate
            api_key: API key (for customer ID matching)
            require_signature: If True, signature verification required
            signature: Cryptographic signature (for cloud policies)

        Returns:
            List of validated policies (may be filtered)

        Raises:
            PolicyValidationError: If validation fails
        """
        # 1. Verify signature if required
        if require_signature:
            if not signature:
                raise PolicyValidationError(
                    "Signature required but not provided"
                )
            self._verify_signature(policies, signature)

        # 2. Filter policies by customer ID
        customer_policies = self._filter_by_customer(
            policies,
            api_key.customer_id,
        )

        # 3. Validate individual policies (domain validation already done)
        for policy in customer_policies:
            self._validate_policy(policy, api_key)

        return customer_policies

    def validate_local_policies(
        self,
        policies: list[Policy],
        api_key: APIKey | None = None,
    ) -> list[Policy]:
        """Validate locally loaded policies (no signature required).

        Args:
            policies: Policies from local file
            api_key: Optional API key for customer filtering

        Returns:
            List of validated policies

        Raises:
            PolicyValidationError: If validation fails
        """
        # No signature verification for local files
        # Customer can manage their own .raxe/policies.yaml

        if api_key:
            # Filter by customer if API key provided
            return self._filter_by_customer(policies, api_key.customer_id)

        # No filtering - return all policies
        return policies

    def _verify_signature(
        self,
        policies: list[Policy],
        signature: str,
    ) -> None:
        """Verify cryptographic signature on policies.

        Args:
            policies: Policies to verify
            signature: Signature string

        Raises:
            PolicyValidationError: If signature invalid
        """
        if not self.signature_verifier:
            raise PolicyValidationError(
                "Signature verification requested but no verifier available"
            )

        # Create canonical representation of policies for signing
        policy_data = self._canonical_policy_data(policies)

        # Hash the data
        data_hash = hashlib.sha256(
            json.dumps(policy_data, sort_keys=True).encode()
        ).digest()

        # Verify signature
        try:
            # Note: SignatureVerifier is designed for file-based verification
            # We'll use a simpler approach for policy data
            if not signature.startswith("ed25519:"):
                raise PolicyValidationError(
                    "Invalid signature format (must start with 'ed25519:')"
                )

            import base64
            sig_b64 = signature.split(":", 1)[1]
            signature_bytes = base64.b64decode(sig_b64)

            # Verify using public key
            self.signature_verifier.public_key.verify(signature_bytes, data_hash)

        except Exception as e:
            raise PolicyValidationError(
                f"Policy signature verification failed: {e}"
            ) from e

    def _filter_by_customer(
        self,
        policies: list[Policy],
        customer_id: str,
    ) -> list[Policy]:
        """Filter policies to only those owned by customer.

        Args:
            policies: All policies
            customer_id: Customer ID to filter by

        Returns:
            Policies belonging to customer
        """
        return [
            policy for policy in policies
            if policy.customer_id == customer_id
        ]

    def _validate_policy(
        self,
        policy: Policy,
        api_key: APIKey,
    ) -> None:
        """Validate single policy.

        Args:
            policy: Policy to validate
            api_key: API key for context

        Raises:
            PolicyValidationError: If policy invalid for this customer
        """
        # Verify customer ID match
        if policy.customer_id != api_key.customer_id:
            raise PolicyValidationError(
                f"Policy {policy.policy_id} customer_id mismatch: "
                f"expected {api_key.customer_id}, got {policy.customer_id}"
            )

        # Additional validation could go here:
        # - Check policy not expired
        # - Validate webhook URLs are authorized
        # - Check priority within allowed range

    def _canonical_policy_data(
        self,
        policies: list[Policy],
    ) -> dict:
        """Create canonical representation of policies for signing.

        Args:
            policies: Policies to represent

        Returns:
            Dictionary representation suitable for hashing
        """
        return {
            "version": "0.0.1",
            "policies": [
                {
                    "id": p.policy_id,
                    "customer_id": p.customer_id,
                    "name": p.name,
                    "action": p.action.value,
                    "priority": p.priority,
                }
                for p in sorted(policies, key=lambda x: x.policy_id)
            ],
        }
