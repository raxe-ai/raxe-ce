"""Apply policy use case.

Orchestrates policy loading, validation, and evaluation.
Coordinates between infrastructure (loading) and domain (evaluation).
"""
from enum import Enum
from pathlib import Path

from raxe.domain.engine.executor import Detection, ScanResult
from raxe.domain.policies.evaluator import evaluate_policies, filter_policies_by_customer
from raxe.domain.policies.models import Policy, PolicyDecision
from raxe.infrastructure.policies.api_client import PolicyAPIClient
from raxe.infrastructure.policies.validator import PolicyValidator
from raxe.infrastructure.policies.yaml_loader import YAMLPolicyLoader
from raxe.infrastructure.security.auth import APIKey


class PolicySource(Enum):
    """Source of policy configuration."""
    LOCAL_FILE = "local_file"      # .raxe/policies.yaml
    API = "api"                      # Cloud API download
    INLINE = "inline"                # Programmatic policies


class ApplyPolicyUseCase:
    """Apply policies to scan results.

    Orchestrates the complete policy workflow:
    1. Load policies from configured source
    2. Validate policies (signatures, customer ID)
    3. Evaluate policies against detections
    4. Return decisions for enforcement

    Application layer - coordinates domain + infrastructure.
    """

    def __init__(
        self,
        yaml_loader: YAMLPolicyLoader | None = None,
        api_client: PolicyAPIClient | None = None,
        validator: PolicyValidator | None = None,
    ) -> None:
        """Initialize use case with dependencies.

        Args:
            yaml_loader: YAML policy loader (None = create default)
            api_client: API client (None = create default)
            validator: Policy validator (None = create default)
        """
        self.yaml_loader = yaml_loader or YAMLPolicyLoader()
        self.api_client = api_client or PolicyAPIClient()
        self.validator = validator or PolicyValidator()

    def apply_to_detection(
        self,
        detection: Detection,
        *,
        policy_source: PolicySource = PolicySource.LOCAL_FILE,
        policy_file: Path | None = None,
        api_key: APIKey | None = None,
        inline_policies: list[Policy] | None = None,
    ) -> PolicyDecision:
        """Apply policies to a single detection.

        Args:
            detection: Detection to evaluate
            policy_source: Where to load policies from
            policy_file: Path to local policy file (for LOCAL_FILE source)
            api_key: API key (for API source or customer filtering)
            inline_policies: Policies to use (for INLINE source)

        Returns:
            PolicyDecision with final action and metadata

        Raises:
            ValueError: If required parameters missing for source
        """
        # Load policies based on source
        policies = self._load_policies(
            policy_source=policy_source,
            policy_file=policy_file,
            api_key=api_key,
            inline_policies=inline_policies,
        )

        # Evaluate policies (pure domain logic)
        return evaluate_policies(detection, policies)

    def apply_to_scan_result(
        self,
        scan_result: ScanResult,
        *,
        policy_source: PolicySource = PolicySource.LOCAL_FILE,
        policy_file: Path | None = None,
        api_key: APIKey | None = None,
        inline_policies: list[Policy] | None = None,
    ) -> dict[str, PolicyDecision]:
        """Apply policies to all detections in scan result.

        Args:
            scan_result: Scan result with detections
            policy_source: Where to load policies from
            policy_file: Path to local policy file (for LOCAL_FILE source)
            api_key: API key (for API source or customer filtering)
            inline_policies: Policies to use (for INLINE source)

        Returns:
            Dict mapping detection versioned_rule_id to PolicyDecision

        Raises:
            ValueError: If required parameters missing for source
        """
        # Load policies once
        policies = self._load_policies(
            policy_source=policy_source,
            policy_file=policy_file,
            api_key=api_key,
            inline_policies=inline_policies,
        )

        # Evaluate each detection
        decisions: dict[str, PolicyDecision] = {}
        for detection in scan_result.detections:
            decision = evaluate_policies(detection, policies)
            decisions[detection.versioned_rule_id] = decision

        return decisions

    def load_policies_from_file(
        self,
        policy_file: Path,
        api_key: APIKey | None = None,
    ) -> list[Policy]:
        """Load and validate policies from YAML file.

        Public helper method for loading policies separately.

        Args:
            policy_file: Path to policy YAML file
            api_key: Optional API key for customer filtering

        Returns:
            List of validated policies

        Raises:
            PolicyLoadError: If file invalid
            PolicyValidationError: If validation fails
        """
        # Load from file (infrastructure)
        policies = self.yaml_loader.load_from_file(policy_file)

        # Validate (infrastructure)
        validated = self.validator.validate_local_policies(
            policies,
            api_key=api_key,
        )

        return validated

    def load_policies_from_api(
        self,
        api_key: APIKey,
        *,
        use_cache_on_error: bool = True,
    ) -> list[Policy]:
        """Load and validate policies from cloud API.

        Public helper method for loading policies separately.

        Args:
            api_key: API key for authentication
            use_cache_on_error: Fall back to cache on API error

        Returns:
            List of validated policies

        Raises:
            PolicyAPIError: If API call fails and no cache
            PolicyValidationError: If validation fails
        """
        # Fetch from API (infrastructure)
        policies = self.api_client.fetch_policies(
            api_key,
            use_cache_on_error=use_cache_on_error,
        )

        # Validate (infrastructure)
        # Note: API policies don't require signature validation here
        # because they're already validated server-side
        validated = self.validator.validate_policies(
            policies,
            api_key=api_key,
            require_signature=False,
        )

        return validated

    def _load_policies(
        self,
        *,
        policy_source: PolicySource,
        policy_file: Path | None = None,
        api_key: APIKey | None = None,
        inline_policies: list[Policy] | None = None,
    ) -> list[Policy]:
        """Load policies from configured source.

        Args:
            policy_source: Where to load from
            policy_file: Path to local file
            api_key: API key for cloud/filtering
            inline_policies: Inline policies

        Returns:
            List of loaded and validated policies

        Raises:
            ValueError: If required parameters missing
        """
        if policy_source == PolicySource.LOCAL_FILE:
            if not policy_file:
                # Default location
                policy_file = Path.home() / ".raxe" / "policies.yaml"

            # File might not exist - return empty policies
            if not policy_file.exists():
                return []

            return self.load_policies_from_file(policy_file, api_key=api_key)

        elif policy_source == PolicySource.API:
            if not api_key:
                raise ValueError("api_key required for API policy source")

            return self.load_policies_from_api(api_key)

        elif policy_source == PolicySource.INLINE:
            if inline_policies is None:
                return []

            # Validate inline policies
            if api_key:
                # Filter by customer
                return filter_policies_by_customer(
                    inline_policies,
                    api_key.customer_id,
                )

            return inline_policies

        else:
            raise ValueError(f"Unknown policy source: {policy_source}")


# Convenience functions for common use cases

def apply_policies_to_detection(
    detection: Detection,
    policies: list[Policy],
) -> PolicyDecision:
    """Apply policies to detection (simple interface).

    Convenience wrapper for direct policy evaluation.

    Args:
        detection: Detection to evaluate
        policies: Policies to apply

    Returns:
        PolicyDecision
    """
    return evaluate_policies(detection, policies)


def should_block_detection(
    detection: Detection,
    policies: list[Policy],
) -> bool:
    """Determine if detection should be blocked by policies.

    Convenience helper for enforcement.

    Args:
        detection: Detection to check
        policies: Policies to apply

    Returns:
        True if detection should be blocked
    """
    decision = evaluate_policies(detection, policies)
    return decision.should_block
