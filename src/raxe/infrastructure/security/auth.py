"""API key validation and parsing.

Validates RAXE API keys without network calls.
"""
import re
from dataclasses import dataclass
from enum import Enum


class KeyType(Enum):
    """API key type."""

    LIVE = "live"
    TEST = "test"


class AuthError(Exception):
    """Authentication error."""

    pass


@dataclass(frozen=True)
class APIKey:
    """
    Parsed API key.

    Format: raxe_{live|test}_{customer_id}_{random}
    Example: raxe_live_cust_abc123_a1b2c3d4e5f6
    """

    raw_key: str
    key_type: KeyType
    customer_id: str
    random_suffix: str

    @classmethod
    def parse(cls, key: str) -> "APIKey":
        """
        Parse API key.

        Args:
            key: Raw API key string

        Returns:
            Parsed APIKey object

        Raises:
            AuthError: If key format invalid
        """
        if not key:
            raise AuthError("API key cannot be empty")

        # Expected format: raxe_{live|test}_{customer_id}_{random}
        # Pattern allows case-insensitive matching for entire key
        pattern = r"^raxe_(live|test)_([a-z0-9_]+)_([a-z0-9]+)$"
        match = re.match(pattern, key.lower())

        if not match:
            raise AuthError(
                "Invalid API key format. "
                "Expected: raxe_{live|test}_{customer_id}_{random}"
            )

        key_type_str, customer_id, random_suffix = match.groups()

        # Validate customer ID format (already lowercase from above)
        if not customer_id.startswith("cust_"):
            raise AuthError("Customer ID must start with 'cust_'")

        # Validate random suffix length
        if len(random_suffix) < 12:
            raise AuthError("Random suffix must be at least 12 characters")

        return cls(
            raw_key=key,
            key_type=KeyType(key_type_str.lower()),
            customer_id=customer_id,
            random_suffix=random_suffix,
        )

    @property
    def is_live(self) -> bool:
        """True if live key."""
        return self.key_type == KeyType.LIVE

    @property
    def is_test(self) -> bool:
        """True if test key."""
        return self.key_type == KeyType.TEST


class APIKeyValidator:
    """
    Validate API keys.

    Offline validation only - no network calls.
    Cloud validation happens separately (optional).
    """

    def validate_key(self, key: str) -> APIKey:
        """
        Validate and parse API key.

        Args:
            key: Raw API key string

        Returns:
            Parsed and validated APIKey

        Raises:
            AuthError: If key invalid
        """
        # Parse key
        api_key = APIKey.parse(key)

        # Additional validation
        self._validate_customer_id(api_key.customer_id)

        return api_key

    def _validate_customer_id(self, customer_id: str) -> None:
        """Validate customer ID format."""
        if len(customer_id) < 10:
            raise AuthError("Customer ID too short")

        if len(customer_id) > 50:
            raise AuthError("Customer ID too long")

        # Only lowercase alphanumeric and underscore
        if not re.match(r"^cust_[a-z0-9_]+$", customer_id):
            raise AuthError("Customer ID contains invalid characters")

    def extract_customer_id(self, key: str) -> str:
        """
        Extract customer ID from key.

        Args:
            key: API key

        Returns:
            Customer ID
        """
        api_key = self.validate_key(key)
        return api_key.customer_id
