"""Secure credential storage for RAXE API keys.

Provides secure storage for API credentials with:
- chmod 600 protection (owner read/write only)
- Temporary key generation for zero-friction onboarding
- Key upgrade support from temporary to permanent
- Expiry tracking for temporary keys (14 days)

File format (credentials.json):
{
    "api_key": "raxe_temp_...",
    "key_type": "temporary",
    "installation_id": "inst_...",
    "created_at": "2025-01-26T00:00:00Z",
    "expires_at": "2025-02-09T00:00:00Z",
    "first_seen_at": null
}

Security:
- File created with chmod 600 (Unix)
- Warns if permissions too permissive on load
- API key values never logged
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import secrets
import stat
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

logger = logging.getLogger(__name__)

# Key format validation patterns (from spec section 2.2)
# Allows alphanumeric, hyphens, and underscores in the random suffix
# (underscores are valid in base64url encoding used by backend)
KEY_PATTERNS: dict[str, re.Pattern[str]] = {
    "temporary": re.compile(r"^raxe_temp_[a-zA-Z0-9_\-]{32}$"),
    "live": re.compile(r"^raxe_live_[a-zA-Z0-9_\-]{32}$"),
    "test": re.compile(r"^raxe_test_[a-zA-Z0-9_\-]{32}$"),
}

# Combined pattern for any valid key
ANY_KEY_PATTERN = re.compile(r"^raxe_(live|test|temp)_[a-zA-Z0-9_\-]{32}$")

# Temporary key expiry (14 days from creation)
TEMP_KEY_EXPIRY_DAYS = 14

# Default credential file location
DEFAULT_CREDENTIAL_DIR = Path.home() / ".raxe"
DEFAULT_CREDENTIAL_FILE = DEFAULT_CREDENTIAL_DIR / "credentials.json"


def compute_key_id(api_key: str) -> str:
    """Compute BigQuery-compatible key ID from API key.

    The key ID is a truncated SHA256 hash of the API key, prefixed with "key_".
    This allows the server to link historical events across key upgrades
    without storing the actual API key values.

    Args:
        api_key: The full API key (e.g., "raxe_temp_b32a43d2...")

    Returns:
        The key ID (e.g., "key_23cc2f9f21f9")

    Example:
        >>> compute_key_id("raxe_temp_abc123def456789012345678901234")
        'key_...'  # 12 hex chars after "key_" prefix
    """
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    return f"key_{key_hash[:12]}"


class CredentialError(Exception):
    """Error related to credential storage or validation."""


def _get_default_console_keys_url() -> str:
    """Get default console keys URL from centralized endpoints."""
    from raxe.infrastructure.config.endpoints import get_console_url
    return f"{get_console_url()}/keys"


class CredentialExpiredError(CredentialError):
    """API key has expired.

    This exception is raised when a temporary API key has exceeded its
    14-day expiry period. Users should obtain a permanent key from the
    RAXE console.

    Attributes:
        message: Human-readable message explaining the expiry.
        console_url: URL where users can get a new permanent key.
        days_expired: Number of days past the expiry date.
    """

    @staticmethod
    def get_default_console_url() -> str:
        """Get default console URL from centralized endpoints."""
        return _get_default_console_keys_url()

    def __init__(
        self,
        message: str,
        *,
        console_url: str | None = None,
        days_expired: int = 0,
    ) -> None:
        """Initialize CredentialExpiredError.

        Args:
            message: Human-readable error message.
            console_url: URL to get a new key (uses centralized endpoint if None).
            days_expired: Number of days past expiry (0 if just expired).
        """
        super().__init__(message)
        self.console_url = console_url or _get_default_console_keys_url()
        self.days_expired = days_expired


class InvalidKeyFormatError(CredentialError):
    """API key format is invalid."""


@dataclass
class KeyUpgradeInfo:
    """Information about a key upgrade for telemetry event creation.

    Contains both the old and new key information needed to create
    a key_upgrade telemetry event with proper key IDs for server-side
    event linking.

    Attributes:
        previous_key_id: BigQuery-compatible ID for previous key (e.g., "key_23cc2f9f21f9").
        new_key_id: BigQuery-compatible ID for new key (e.g., "key_7ce219b525f1").
        previous_key_type: Previous key type ("temporary", "live", or "test").
        new_key_type: New key type ("live" or "test").
        days_on_previous: Number of days the previous key was in use (if known).
        new_credentials: The newly saved Credentials object.
    """

    previous_key_id: str | None
    new_key_id: str
    previous_key_type: str | None
    new_key_type: str
    days_on_previous: int | None
    new_credentials: "Credentials"


@dataclass
class Credentials:
    """Credential data model.

    Represents stored API credentials with type and expiry information.

    Attributes:
        api_key: The RAXE API key (raxe_temp_*, raxe_live_*, or raxe_test_*)
        key_type: Type of key - temporary, live, or test
        installation_id: Unique installation identifier (inst_{hex16})
        created_at: ISO 8601 timestamp when credentials were created
        expires_at: ISO 8601 timestamp when key expires (temporary keys only)
        first_seen_at: Server-provided timestamp of first use (optional)
        can_disable_telemetry: Whether the key tier allows disabling telemetry
        offline_mode: Whether offline mode is permitted for this tier
        tier: Key tier (temporary, community, pro, enterprise)
        last_health_check: ISO 8601 timestamp of last server health check
    """

    api_key: str
    key_type: Literal["temporary", "live", "test"]
    installation_id: str
    created_at: str  # ISO 8601
    expires_at: str | None  # For temp keys (14 days from creation)
    first_seen_at: str | None  # Server-provided

    # Cached server permissions (from /v1/health response)
    can_disable_telemetry: bool = False
    offline_mode: bool = False
    tier: str = "temporary"
    last_health_check: str | None = None  # ISO 8601 timestamp

    def is_expired(self) -> bool:
        """Check if the credential has expired.

        Returns:
            True if the key has expired, False otherwise.
            Permanent keys (live/test) never expire.
        """
        if self.expires_at is None:
            return False

        try:
            expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            return now >= expiry
        except (ValueError, TypeError):
            # If we can't parse expiry, assume not expired
            logger.warning("Could not parse expires_at, assuming not expired")
            return False

    def is_temporary(self) -> bool:
        """Check if this is a temporary key.

        Returns:
            True if key_type is "temporary", False otherwise.
        """
        return self.key_type == "temporary"

    def days_until_expiry(self) -> int | None:
        """Calculate days remaining until expiry.

        Returns:
            Number of days until expiry (0 if expired, None if no expiry).
        """
        if self.expires_at is None:
            return None

        try:
            expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = expiry - now

            if delta.total_seconds() <= 0:
                return 0

            return delta.days
        except (ValueError, TypeError):
            return None

    def days_since_expiry(self) -> int | None:
        """Calculate days since expiry (for expired keys).

        Returns:
            Number of days past expiry (0 if not yet expired, None if no expiry).
        """
        if self.expires_at is None:
            return None

        try:
            expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = now - expiry

            if delta.total_seconds() <= 0:
                return 0

            return delta.days
        except (ValueError, TypeError):
            return None

    def is_health_check_stale(self, max_age_hours: int = 24) -> bool:
        """Check if the cached health check is stale.

        Args:
            max_age_hours: Maximum age in hours before health check is stale.

        Returns:
            True if health check is stale or missing, False otherwise.
        """
        if self.last_health_check is None:
            return True

        try:
            from datetime import timedelta

            last_check = datetime.fromisoformat(
                self.last_health_check.replace("Z", "+00:00")
            )
            now = datetime.now(timezone.utc)
            age = now - last_check

            return age > timedelta(hours=max_age_hours)
        except (ValueError, TypeError):
            return True

    def to_dict(self) -> dict[str, str | None]:
        """Convert credentials to dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, str | None]) -> Credentials:
        """Create Credentials from dictionary.

        Args:
            data: Dictionary with credential fields.

        Returns:
            Credentials instance.

        Raises:
            ValueError: If required fields are missing.
        """
        required_fields = ["api_key", "key_type", "installation_id", "created_at"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        return cls(
            api_key=data["api_key"],  # type: ignore[arg-type]
            key_type=data["key_type"],  # type: ignore[arg-type]
            installation_id=data["installation_id"],  # type: ignore[arg-type]
            created_at=data["created_at"],  # type: ignore[arg-type]
            expires_at=data.get("expires_at"),
            first_seen_at=data.get("first_seen_at"),
            # Server permission fields (with defaults for backward compatibility)
            can_disable_telemetry=data.get("can_disable_telemetry", False),  # type: ignore[arg-type]
            offline_mode=data.get("offline_mode", False),  # type: ignore[arg-type]
            tier=data.get("tier", "temporary"),  # type: ignore[arg-type]
            last_health_check=data.get("last_health_check"),
        )


def validate_key_format(api_key: str) -> Literal["temporary", "live", "test"]:
    """Validate API key format and return type.

    Args:
        api_key: The API key to validate.

    Returns:
        The key type (temporary, live, or test).

    Raises:
        InvalidKeyFormatError: If the key format is invalid.
    """
    if not api_key:
        raise InvalidKeyFormatError("API key cannot be empty")

    if not ANY_KEY_PATTERN.match(api_key):
        raise InvalidKeyFormatError(
            "Invalid API key format. Expected: raxe_{live|test|temp}_{32 chars}"
        )

    # Determine key type
    if api_key.startswith("raxe_temp_"):
        return "temporary"
    elif api_key.startswith("raxe_live_"):
        return "live"
    elif api_key.startswith("raxe_test_"):
        return "test"
    else:
        raise InvalidKeyFormatError("Unknown key type prefix")


def _generate_installation_id() -> str:
    """Generate a unique installation identifier.

    Format: inst_{uuid4_hex[:16]}

    Returns:
        Installation ID string.
    """
    hex_id = uuid4().hex[:16]
    return f"inst_{hex_id}"


def _generate_temp_key() -> str:
    """Generate a temporary API key.

    Format: raxe_temp_{secrets.token_hex(16)}

    Returns:
        Temporary API key string (32 hex chars after prefix).
    """
    # token_hex(16) generates 32 hex characters
    return f"raxe_temp_{secrets.token_hex(16)}"


def _get_utc_now_iso() -> str:
    """Get current UTC time in ISO 8601 format.

    Returns:
        ISO 8601 formatted timestamp with Z suffix.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_windows() -> bool:
    """Check if running on Windows.

    Returns:
        True if running on Windows, False otherwise.
    """
    return platform.system() == "Windows"


def _set_secure_permissions(path: Path) -> None:
    """Set secure file permissions (chmod 600).

    On Unix-like systems, sets file to owner read/write only.
    On Windows, this is a no-op (Windows uses ACLs).

    Args:
        path: Path to the file.
    """
    if _is_windows():
        # Windows uses ACLs, skip chmod
        logger.debug("Skipping chmod on Windows")
        return

    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        logger.debug("Set file permissions to 600")
    except OSError as e:
        logger.warning(f"Failed to set file permissions: {e}")


def _check_permissions(path: Path) -> bool:
    """Check if file permissions are secure.

    Args:
        path: Path to the file to check.

    Returns:
        True if permissions are secure (600 or better), False otherwise.
    """
    if _is_windows():
        # Windows uses ACLs, assume OK
        return True

    try:
        mode = path.stat().st_mode
        # Check if group or world readable/writable
        insecure_bits = (
            stat.S_IRGRP  # Group read
            | stat.S_IWGRP  # Group write
            | stat.S_IROTH  # World read
            | stat.S_IWOTH  # World write
        )
        return (mode & insecure_bits) == 0
    except OSError:
        return True  # Can't check, assume OK


class CredentialStore:
    """Secure credential storage with chmod 600 protection.

    Manages API credentials for RAXE telemetry with secure storage
    and support for temporary key generation.

    Location: ~/.raxe/credentials.json (default)

    Example:
        >>> store = CredentialStore()
        >>> creds = store.get_or_create()
        >>> print(f"Using key type: {creds.key_type}")
        Using key type: temporary

        >>> # Upgrade to permanent key
        >>> creds = store.upgrade_key("raxe_live_abc123...", "live")
        >>> print(f"Upgraded to: {creds.key_type}")
        Upgraded to: live
    """

    def __init__(self, credential_path: Path | None = None) -> None:
        """Initialize credential store.

        Args:
            credential_path: Custom path to credentials file.
                           Defaults to ~/.raxe/credentials.json
        """
        self._credential_path = credential_path or DEFAULT_CREDENTIAL_FILE
        self._cached_credentials: Credentials | None = None

    @property
    def credential_path(self) -> Path:
        """Get the credential file path.

        Returns:
            Path to the credentials file.
        """
        return self._credential_path

    def load(self) -> Credentials | None:
        """Load credentials from file.

        Returns:
            Credentials if file exists and is valid, None otherwise.

        Raises:
            CredentialError: If file exists but cannot be parsed.
        """
        if not self._credential_path.exists():
            logger.debug("Credential file does not exist")
            return None

        # Check permissions and warn if insecure
        if not _check_permissions(self._credential_path):
            logger.warning(
                "Credential file has insecure permissions. Consider running: chmod 600 %s",
                self._credential_path,
            )

        try:
            with open(self._credential_path, encoding="utf-8") as f:
                data = json.load(f)

            credentials = Credentials.from_dict(data)

            # Validate key format
            try:
                validate_key_format(credentials.api_key)
            except InvalidKeyFormatError as e:
                raise CredentialError(f"Invalid stored API key: {e}") from e

            # Log without exposing key value
            logger.debug(
                "Loaded credentials: type=%s, installation=%s",
                credentials.key_type,
                credentials.installation_id,
            )

            self._cached_credentials = credentials
            return credentials

        except json.JSONDecodeError as e:
            raise CredentialError(f"Invalid JSON in credential file: {e}") from e
        except ValueError as e:
            raise CredentialError(f"Invalid credential format: {e}") from e

    def save(self, credentials: Credentials) -> None:
        """Save credentials with chmod 600.

        Args:
            credentials: Credentials to save.

        Raises:
            CredentialError: If file cannot be written.
        """
        # Validate key format before saving
        try:
            validate_key_format(credentials.api_key)
        except InvalidKeyFormatError as e:
            raise CredentialError(f"Cannot save invalid API key: {e}") from e

        # Ensure parent directory exists
        self._credential_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Write to file
            with open(self._credential_path, "w", encoding="utf-8") as f:
                json.dump(credentials.to_dict(), f, indent=2)

            # Set secure permissions
            _set_secure_permissions(self._credential_path)

            # Log without exposing key value
            logger.info(
                "Saved credentials: type=%s, installation=%s",
                credentials.key_type,
                credentials.installation_id,
            )

            self._cached_credentials = credentials

        except OSError as e:
            raise CredentialError(f"Failed to write credential file: {e}") from e

    def generate_temp_credentials(self) -> Credentials:
        """Generate temporary credentials for zero-friction onboarding.

        Creates new temporary credentials with:
        - installation_id: inst_{uuid4_hex[:16]}
        - temp key: raxe_temp_{secrets.token_hex(16)}
        - expiry: now + 14 days

        Returns:
            Newly generated temporary credentials.
        """
        now = _get_utc_now_iso()
        expiry = datetime.now(timezone.utc)
        expiry = expiry.replace(day=expiry.day)  # Keep same time

        # Calculate expiry (14 days from now)
        from datetime import timedelta

        expiry_dt = datetime.now(timezone.utc) + timedelta(days=TEMP_KEY_EXPIRY_DAYS)
        expires_at = expiry_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        credentials = Credentials(
            api_key=_generate_temp_key(),
            key_type="temporary",
            installation_id=_generate_installation_id(),
            created_at=now,
            expires_at=expires_at,
            first_seen_at=None,
        )

        # Log without exposing key value
        logger.info(
            "Generated temporary credentials: installation=%s, expires=%s",
            credentials.installation_id,
            credentials.expires_at,
        )

        return credentials

    def upgrade_key(
        self,
        new_api_key: str,
        key_type: Literal["live", "test"],
    ) -> Credentials:
        """Upgrade from temporary to permanent key.

        Preserves installation_id from existing credentials if available.

        Args:
            new_api_key: The new permanent API key.
            key_type: Type of the new key (live or test).

        Returns:
            Updated credentials with the new key.

        Raises:
            InvalidKeyFormatError: If the new key format is invalid.
            CredentialError: If key_type doesn't match the new key prefix.

        Note:
            For telemetry event creation with key IDs, use upgrade_key_with_info()
            instead, which returns KeyUpgradeInfo containing both old and new key IDs.
        """
        upgrade_info = self.upgrade_key_with_info(new_api_key, key_type)
        return upgrade_info.new_credentials

    def upgrade_key_with_info(
        self,
        new_api_key: str,
        key_type: Literal["live", "test"],
    ) -> KeyUpgradeInfo:
        """Upgrade from temporary to permanent key with full upgrade information.

        Preserves installation_id from existing credentials if available.
        Returns KeyUpgradeInfo containing both old and new key IDs for
        telemetry event creation.

        Args:
            new_api_key: The new permanent API key.
            key_type: Type of the new key (live or test).

        Returns:
            KeyUpgradeInfo with old/new key IDs and the new credentials.

        Raises:
            InvalidKeyFormatError: If the new key format is invalid.
            CredentialError: If key_type doesn't match the new key prefix.

        Example:
            >>> store = CredentialStore()
            >>> info = store.upgrade_key_with_info("raxe_live_abc...", "live")
            >>> event = create_key_upgrade_event(
            ...     previous_key_type="temp",
            ...     new_key_type="community",
            ...     previous_key_id=info.previous_key_id,
            ...     new_key_id=info.new_key_id,
            ...     days_on_previous=info.days_on_previous,
            ... )
        """
        # Validate key format
        detected_type = validate_key_format(new_api_key)

        # Check for temporary key first (cannot upgrade to temp)
        if detected_type == "temporary":
            raise CredentialError("Cannot upgrade to a temporary key")

        if detected_type != key_type:
            raise CredentialError(
                f"Key type mismatch: provided '{key_type}' but key is '{detected_type}'"
            )

        # Load existing credentials to preserve installation_id and capture old key info
        existing = self.load()
        installation_id = existing.installation_id if existing else _generate_installation_id()

        # Capture old key information for telemetry event
        previous_key_id: str | None = None
        previous_key_type: str | None = None
        days_on_previous: int | None = None

        if existing:
            previous_key_id = compute_key_id(existing.api_key)
            previous_key_type = existing.key_type
            # Calculate days on previous key
            try:
                created = datetime.fromisoformat(
                    existing.created_at.replace("Z", "+00:00")
                )
                now = datetime.now(timezone.utc)
                days_on_previous = (now - created).days
            except (ValueError, TypeError):
                days_on_previous = None

        # Determine tier based on key type (live keys default to community tier)
        tier = "community" if key_type == "live" else "test"

        credentials = Credentials(
            api_key=new_api_key,
            key_type=key_type,
            installation_id=installation_id,
            created_at=_get_utc_now_iso(),
            expires_at=None,  # Permanent keys don't expire
            first_seen_at=None,
            tier=tier,
        )

        # Save the upgraded credentials
        self.save(credentials)

        # Compute new key ID
        new_key_id = compute_key_id(new_api_key)

        logger.info(
            "Upgraded to permanent key: type=%s, installation=%s",
            key_type,
            installation_id,
        )

        return KeyUpgradeInfo(
            previous_key_id=previous_key_id,
            new_key_id=new_key_id,
            previous_key_type=previous_key_type,
            new_key_type=key_type,
            days_on_previous=days_on_previous,
            new_credentials=credentials,
        )

    def get_or_create(self, *, raise_on_expired: bool = True) -> Credentials:
        """Load existing or generate new temp credentials.

        Priority chain:
        1. RAXE_API_KEY environment variable (highest - explicit override)
        2. ~/.raxe/credentials.json file
        3. Generate new temp credentials (last resort)

        Args:
            raise_on_expired: If True, raises CredentialExpiredError when
                credentials are expired. If False, returns expired credentials
                for caller to handle. Defaults to True.

        Returns:
            Existing credentials if valid, or newly generated temp credentials.

        Raises:
            CredentialExpiredError: If credentials are expired and raise_on_expired is True.
        """
        # Priority 1: Check RAXE_API_KEY environment variable first
        env_api_key = os.environ.get("RAXE_API_KEY", "").strip()
        if env_api_key:
            try:
                key_type = validate_key_format(env_api_key)
                # Create credentials from env var (don't persist to file)
                # Try to preserve installation_id from existing file if available
                existing = self.load()
                installation_id = (
                    existing.installation_id if existing else _generate_installation_id()
                )
                return Credentials(
                    api_key=env_api_key,
                    key_type=key_type,
                    installation_id=installation_id,
                    created_at=_get_utc_now_iso(),
                    expires_at=None,  # Env var keys don't have local expiry tracking
                    first_seen_at=None,
                )
            except InvalidKeyFormatError:
                logger.warning(
                    "Invalid RAXE_API_KEY format in environment, falling back to file"
                )

        # Priority 2: Try to load from credentials.json file
        try:
            credentials = self.load()
            if credentials is not None:
                # Check if expired
                if credentials.is_expired():
                    days_expired = credentials.days_since_expiry() or 0
                    console_url = CredentialExpiredError.get_default_console_url()

                    # Build helpful error message
                    if days_expired == 0:
                        expiry_text = "today"
                    elif days_expired == 1:
                        expiry_text = "1 day ago"
                    else:
                        expiry_text = f"{days_expired} days ago"

                    message = (
                        f"Your temporary API key expired {expiry_text}. "
                        f"Get a permanent key at: {console_url}\n"
                        "Or run: raxe auth login"
                    )

                    logger.warning(
                        "credentials_expired",
                        extra={
                            "days_expired": days_expired,
                            "key_type": credentials.key_type,
                            "installation_id": credentials.installation_id,
                        },
                    )

                    if raise_on_expired:
                        raise CredentialExpiredError(
                            message,
                            console_url=console_url,
                            days_expired=days_expired,
                        )
                    # Return expired credentials if caller wants to handle it
                return credentials
        except CredentialError as e:
            # Re-raise CredentialExpiredError, catch other CredentialErrors
            if isinstance(e, CredentialExpiredError):
                raise
            logger.warning("Failed to load credentials: %s", e)

        # Generate new temp credentials
        credentials = self.generate_temp_credentials()

        # Save them
        self.save(credentials)

        return credentials

    def delete(self) -> bool:
        """Delete credentials file.

        Returns:
            True if file was deleted, False if it didn't exist.
        """
        if not self._credential_path.exists():
            logger.debug("Credential file does not exist, nothing to delete")
            return False

        try:
            self._credential_path.unlink()
            self._cached_credentials = None
            logger.info("Deleted credential file")
            return True
        except OSError as e:
            logger.error("Failed to delete credential file: %s", e)
            return False

    def update_first_seen(self, first_seen_at: str) -> Credentials | None:
        """Update the first_seen_at timestamp from server.

        Args:
            first_seen_at: ISO 8601 timestamp from server health check.

        Returns:
            Updated credentials, or None if no credentials loaded.
        """
        credentials = self.load()
        if credentials is None:
            return None

        if credentials.first_seen_at is not None:
            # Already set, don't overwrite
            return credentials

        # Create updated credentials (preserve all fields)
        updated = Credentials(
            api_key=credentials.api_key,
            key_type=credentials.key_type,
            installation_id=credentials.installation_id,
            created_at=credentials.created_at,
            expires_at=credentials.expires_at,
            first_seen_at=first_seen_at,
            can_disable_telemetry=credentials.can_disable_telemetry,
            offline_mode=credentials.offline_mode,
            tier=credentials.tier,
            last_health_check=credentials.last_health_check,
        )

        self.save(updated)
        return updated

    def update_from_health(self, health_response: dict) -> Credentials | None:
        """Update cached permissions from /v1/health response.

        This method updates the server-side permission cache from a health
        check response. It should be called after a successful health check
        to keep the local cache in sync with server-side permissions.

        Args:
            health_response: Dictionary from /v1/health response containing:
                - can_disable_telemetry: bool
                - offline_mode: bool (optional)
                - tier: str (temporary, community, pro, enterprise)
                - server_time: str (ISO 8601)

        Returns:
            Updated credentials, or None if no credentials loaded.

        Example:
            >>> store = CredentialStore()
            >>> health = shipper.check_health()
            >>> store.update_from_health({
            ...     "can_disable_telemetry": True,
            ...     "tier": "pro",
            ...     "server_time": "2025-01-26T12:00:00Z"
            ... })
        """
        credentials = self.load()
        if credentials is None:
            return None

        # Extract permissions from health response
        can_disable = health_response.get("can_disable_telemetry", False)
        offline_mode = health_response.get("offline_mode", False)
        tier = health_response.get("tier", credentials.tier)
        server_time = health_response.get("server_time", _get_utc_now_iso())

        # Create updated credentials with new permissions
        updated = Credentials(
            api_key=credentials.api_key,
            key_type=credentials.key_type,
            installation_id=credentials.installation_id,
            created_at=credentials.created_at,
            expires_at=credentials.expires_at,
            first_seen_at=credentials.first_seen_at,
            can_disable_telemetry=can_disable,
            offline_mode=offline_mode,
            tier=tier,
            last_health_check=server_time,
        )

        self.save(updated)

        logger.debug(
            "Updated credentials from health check: tier=%s, can_disable_telemetry=%s",
            tier,
            can_disable,
        )

        return updated
