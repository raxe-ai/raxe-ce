"""Tests for credential store module.

Tests cover:
- Credentials data model
- Key format validation
- CredentialStore operations (load, save, generate, upgrade, delete)
- File permissions (chmod 600)
- Expiry handling for temporary keys
"""

import json
import os
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from raxe.infrastructure.telemetry.credential_store import (
    ANY_KEY_PATTERN,
    KEY_PATTERNS,
    CredentialError,
    CredentialExpiredError,
    Credentials,
    CredentialStore,
    InvalidKeyFormatError,
    KeyUpgradeInfo,
    compute_key_id,
    validate_key_format,
)


class TestKeyPatterns:
    """Test key format validation patterns."""

    def test_temp_key_pattern_valid(self) -> None:
        """Test valid temporary key format."""
        valid_keys = [
            "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            "raxe_temp_00000000000000000000000000000000",
            "raxe_temp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "raxe_temp_abcdef1234567890ABCDEF1234567890",
        ]
        for key in valid_keys:
            assert KEY_PATTERNS["temporary"].match(key), f"Should match: {key}"

    def test_live_key_pattern_valid(self) -> None:
        """Test valid live key format."""
        valid_keys = [
            "raxe_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            "raxe_live_00000000000000000000000000000000",
        ]
        for key in valid_keys:
            assert KEY_PATTERNS["live"].match(key), f"Should match: {key}"

    def test_test_key_pattern_valid(self) -> None:
        """Test valid test key format."""
        valid_keys = [
            "raxe_test_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            "raxe_test_xyz789abc123def456xyz789abc123de",
        ]
        for key in valid_keys:
            assert KEY_PATTERNS["test"].match(key), f"Should match: {key}"

    def test_invalid_key_patterns(self) -> None:
        """Test invalid key formats are rejected."""
        invalid_keys = [
            "",
            "raxe_",
            "raxe_temp_",
            "raxe_temp_short",  # Too short
            "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6extra",  # Too long
            "raxe_invalid_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",  # Wrong type
            "raxe_temp_!!special!!characters!!here!!",  # Invalid chars
            "RAXE_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",  # Wrong case
        ]
        for key in invalid_keys:
            assert not ANY_KEY_PATTERN.match(key), f"Should not match: {key}"


class TestValidateKeyFormat:
    """Test validate_key_format function."""

    def test_validate_temporary_key(self) -> None:
        """Test validating temporary key returns correct type."""
        key = "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        assert validate_key_format(key) == "temporary"

    def test_validate_live_key(self) -> None:
        """Test validating live key returns correct type."""
        key = "raxe_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        assert validate_key_format(key) == "live"

    def test_validate_test_key(self) -> None:
        """Test validating test key returns correct type."""
        key = "raxe_test_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        assert validate_key_format(key) == "test"

    def test_validate_empty_key_raises(self) -> None:
        """Test empty key raises InvalidKeyFormatError."""
        with pytest.raises(InvalidKeyFormatError, match="cannot be empty"):
            validate_key_format("")

    def test_validate_invalid_format_raises(self) -> None:
        """Test invalid format raises InvalidKeyFormatError."""
        with pytest.raises(InvalidKeyFormatError, match="Invalid API key format"):
            validate_key_format("not_a_valid_key")

    def test_validate_wrong_prefix_raises(self) -> None:
        """Test wrong prefix raises InvalidKeyFormatError."""
        with pytest.raises(InvalidKeyFormatError, match="Invalid API key format"):
            validate_key_format("raxe_invalid_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6")


class TestCredentials:
    """Test Credentials data model."""

    def test_credentials_creation(self) -> None:
        """Test basic credentials creation."""
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at="2025-02-09T10:00:00Z",
            first_seen_at=None,
        )
        assert creds.api_key.startswith("raxe_temp_")
        assert creds.key_type == "temporary"
        assert creds.installation_id.startswith("inst_")

    def test_is_temporary_true(self) -> None:
        """Test is_temporary returns True for temporary keys."""
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at="2025-02-09T10:00:00Z",
            first_seen_at=None,
        )
        assert creds.is_temporary() is True

    def test_is_temporary_false_for_live(self) -> None:
        """Test is_temporary returns False for live keys."""
        creds = Credentials(
            api_key="raxe_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="live",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at=None,
            first_seen_at=None,
        )
        assert creds.is_temporary() is False

    def test_is_expired_no_expiry(self) -> None:
        """Test is_expired returns False when no expiry set."""
        creds = Credentials(
            api_key="raxe_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="live",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at=None,
            first_seen_at=None,
        )
        assert creds.is_expired() is False

    def test_is_expired_future_expiry(self) -> None:
        """Test is_expired returns False for future expiry."""
        future = datetime.now(timezone.utc) + timedelta(days=7)
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at=future.strftime("%Y-%m-%dT%H:%M:%SZ"),
            first_seen_at=None,
        )
        assert creds.is_expired() is False

    def test_is_expired_past_expiry(self) -> None:
        """Test is_expired returns True for past expiry."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at=past.strftime("%Y-%m-%dT%H:%M:%SZ"),
            first_seen_at=None,
        )
        assert creds.is_expired() is True

    def test_days_until_expiry_no_expiry(self) -> None:
        """Test days_until_expiry returns None when no expiry."""
        creds = Credentials(
            api_key="raxe_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="live",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at=None,
            first_seen_at=None,
        )
        assert creds.days_until_expiry() is None

    def test_days_until_expiry_future(self) -> None:
        """Test days_until_expiry returns positive days for future expiry."""
        future = datetime.now(timezone.utc) + timedelta(days=10)
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at=future.strftime("%Y-%m-%dT%H:%M:%SZ"),
            first_seen_at=None,
        )
        days = creds.days_until_expiry()
        assert days is not None
        assert days >= 9  # Allow for test timing

    def test_days_until_expiry_expired(self) -> None:
        """Test days_until_expiry returns 0 for expired key."""
        past = datetime.now(timezone.utc) - timedelta(days=5)
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at=past.strftime("%Y-%m-%dT%H:%M:%SZ"),
            first_seen_at=None,
        )
        assert creds.days_until_expiry() == 0

    def test_to_dict(self) -> None:
        """Test to_dict conversion."""
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at="2025-02-09T10:00:00Z",
            first_seen_at=None,
        )
        d = creds.to_dict()
        assert d["api_key"] == creds.api_key
        assert d["key_type"] == "temporary"
        assert d["installation_id"] == creds.installation_id
        assert d["expires_at"] == creds.expires_at
        assert d["first_seen_at"] is None

    def test_from_dict(self) -> None:
        """Test from_dict creation."""
        data = {
            "api_key": "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            "key_type": "temporary",
            "installation_id": "inst_abc123def456gh",
            "created_at": "2025-01-26T10:00:00Z",
            "expires_at": "2025-02-09T10:00:00Z",
            "first_seen_at": None,
        }
        creds = Credentials.from_dict(data)
        assert creds.api_key == data["api_key"]
        assert creds.key_type == "temporary"

    def test_from_dict_missing_field_raises(self) -> None:
        """Test from_dict raises on missing required field."""
        data = {
            "api_key": "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            # Missing key_type, installation_id, created_at
        }
        with pytest.raises(ValueError, match="Missing required field"):
            Credentials.from_dict(data)


class TestCredentialStore:
    """Test CredentialStore class."""

    def test_init_default_path(self) -> None:
        """Test default credential path is set."""
        store = CredentialStore()
        assert store.credential_path.name == "credentials.json"
        assert ".raxe" in str(store.credential_path)

    def test_init_custom_path(self, tmp_path: Path) -> None:
        """Test custom credential path."""
        custom_path = tmp_path / "custom_creds.json"
        store = CredentialStore(credential_path=custom_path)
        assert store.credential_path == custom_path

    def test_load_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """Test loading from nonexistent file returns None."""
        store = CredentialStore(credential_path=tmp_path / "missing.json")
        assert store.load() is None

    def test_load_valid_credentials(self, temp_credentials_file: Path) -> None:
        """Test loading valid credentials from file."""
        store = CredentialStore(credential_path=temp_credentials_file)
        creds = store.load()
        assert creds is not None
        assert creds.key_type == "temporary"
        assert creds.installation_id == "inst_abc123def456gh"

    def test_load_invalid_json_raises(self, tmp_path: Path) -> None:
        """Test loading invalid JSON raises CredentialError."""
        creds_file = tmp_path / "invalid.json"
        creds_file.write_text("not valid json {{{")
        store = CredentialStore(credential_path=creds_file)
        with pytest.raises(CredentialError, match="Invalid JSON"):
            store.load()

    def test_load_missing_fields_raises(self, tmp_path: Path) -> None:
        """Test loading file with missing fields raises."""
        creds_file = tmp_path / "incomplete.json"
        creds_file.write_text(json.dumps({"api_key": "raxe_temp_xxx"}))
        store = CredentialStore(credential_path=creds_file)
        with pytest.raises(CredentialError, match="Invalid credential format"):
            store.load()

    def test_save_creates_file(self, tmp_path: Path) -> None:
        """Test save creates credentials file."""
        creds_file = tmp_path / "new_creds.json"
        store = CredentialStore(credential_path=creds_file)
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at="2025-02-09T10:00:00Z",
            first_seen_at=None,
        )
        store.save(creds)
        assert creds_file.exists()

        # Verify contents
        with open(creds_file) as f:
            data = json.load(f)
        assert data["api_key"] == creds.api_key
        assert data["key_type"] == "temporary"

    def test_save_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test save creates parent directories if needed."""
        creds_file = tmp_path / "nested" / "dir" / "creds.json"
        store = CredentialStore(credential_path=creds_file)
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at="2025-02-09T10:00:00Z",
            first_seen_at=None,
        )
        store.save(creds)
        assert creds_file.exists()

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod not applicable on Windows")
    def test_save_sets_permissions_600(self, tmp_path: Path) -> None:
        """Test save sets file permissions to 600."""
        creds_file = tmp_path / "creds.json"
        store = CredentialStore(credential_path=creds_file)
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at="2025-02-09T10:00:00Z",
            first_seen_at=None,
        )
        store.save(creds)

        # Check permissions
        mode = creds_file.stat().st_mode
        assert (mode & stat.S_IRWXG) == 0  # No group permissions
        assert (mode & stat.S_IRWXO) == 0  # No other permissions
        assert (mode & stat.S_IRUSR) != 0  # Owner read
        assert (mode & stat.S_IWUSR) != 0  # Owner write

    def test_save_invalid_key_raises(self, tmp_path: Path) -> None:
        """Test save with invalid key format raises."""
        creds_file = tmp_path / "bad_creds.json"
        store = CredentialStore(credential_path=creds_file)
        creds = Credentials(
            api_key="invalid_key",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at="2025-02-09T10:00:00Z",
            first_seen_at=None,
        )
        with pytest.raises(CredentialError, match="Cannot save invalid API key"):
            store.save(creds)

    def test_generate_temp_credentials(self, tmp_path: Path) -> None:
        """Test generating temporary credentials."""
        store = CredentialStore(credential_path=tmp_path / "creds.json")
        creds = store.generate_temp_credentials()

        # Check key format
        assert creds.api_key.startswith("raxe_temp_")
        assert len(creds.api_key) == len("raxe_temp_") + 32
        validate_key_format(creds.api_key)  # Should not raise

        # Check installation_id format
        assert creds.installation_id.startswith("inst_")
        assert len(creds.installation_id) == len("inst_") + 16

        # Check key type
        assert creds.key_type == "temporary"

        # Check expiry is 14 days from now
        assert creds.expires_at is not None
        expiry = datetime.fromisoformat(creds.expires_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = expiry - now
        assert 13 <= delta.days <= 14  # Allow for test timing

        # Check first_seen_at is None
        assert creds.first_seen_at is None

    def test_get_or_create_loads_existing(self, temp_credentials_file: Path) -> None:
        """Test get_or_create loads existing credentials."""
        store = CredentialStore(credential_path=temp_credentials_file)
        creds = store.get_or_create()
        assert creds.api_key == "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        assert creds.installation_id == "inst_abc123def456gh"

    def test_get_or_create_generates_new(self, tmp_path: Path) -> None:
        """Test get_or_create generates new if no file."""
        creds_file = tmp_path / "new_creds.json"
        store = CredentialStore(credential_path=creds_file)
        creds = store.get_or_create()

        assert creds.api_key.startswith("raxe_temp_")
        assert creds.key_type == "temporary"
        assert creds_file.exists()  # File was created

    def test_get_or_create_returns_expired(self, tmp_path: Path) -> None:
        """Test get_or_create returns expired credentials when raise_on_expired=False."""
        # Create expired credentials
        creds_file = tmp_path / "expired_creds.json"
        past = datetime.now(timezone.utc) - timedelta(days=1)
        creds_file.write_text(
            json.dumps(
                {
                    "api_key": "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
                    "key_type": "temporary",
                    "installation_id": "inst_abc123def456gh",
                    "created_at": "2025-01-01T10:00:00Z",
                    "expires_at": past.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "first_seen_at": None,
                }
            )
        )

        store = CredentialStore(credential_path=creds_file)
        # Use raise_on_expired=False to get expired credentials back
        creds = store.get_or_create(raise_on_expired=False)

        # Should return expired credentials
        assert creds.is_expired() is True

    def test_get_or_create_raises_on_expired(self, tmp_path: Path) -> None:
        """Test get_or_create raises CredentialExpiredError by default for expired keys."""
        # Create expired credentials
        creds_file = tmp_path / "expired_creds.json"
        past = datetime.now(timezone.utc) - timedelta(days=1)
        creds_file.write_text(
            json.dumps(
                {
                    "api_key": "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
                    "key_type": "temporary",
                    "installation_id": "inst_abc123def456gh",
                    "created_at": "2025-01-01T10:00:00Z",
                    "expires_at": past.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "first_seen_at": None,
                }
            )
        )

        store = CredentialStore(credential_path=creds_file)

        # Should raise CredentialExpiredError by default
        with pytest.raises(CredentialExpiredError) as exc_info:
            store.get_or_create()

        # Verify error details
        assert exc_info.value.days_expired >= 1
        assert "console.raxe.ai" in exc_info.value.console_url

    def test_upgrade_key_live(self, temp_credentials_file: Path) -> None:
        """Test upgrading to live key."""
        store = CredentialStore(credential_path=temp_credentials_file)
        new_key = "raxe_live_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4"
        creds = store.upgrade_key(new_key, "live")

        assert creds.api_key == new_key
        assert creds.key_type == "live"
        # Should preserve installation_id
        assert creds.installation_id == "inst_abc123def456gh"
        # Permanent keys don't expire
        assert creds.expires_at is None

    def test_upgrade_key_test(self, tmp_path: Path) -> None:
        """Test upgrading to test key."""
        creds_file = tmp_path / "creds.json"
        store = CredentialStore(credential_path=creds_file)
        # First create temp credentials
        store.get_or_create()

        new_key = "raxe_test_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        creds = store.upgrade_key(new_key, "test")

        assert creds.api_key == new_key
        assert creds.key_type == "test"
        assert creds.expires_at is None

    def test_upgrade_key_type_mismatch_raises(self, tmp_path: Path) -> None:
        """Test upgrade with mismatched key type raises."""
        creds_file = tmp_path / "creds.json"
        store = CredentialStore(credential_path=creds_file)
        store.get_or_create()

        # Try to upgrade with live key but claim it's test
        live_key = "raxe_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        with pytest.raises(CredentialError, match="Key type mismatch"):
            store.upgrade_key(live_key, "test")

    def test_upgrade_to_temp_key_raises(self, tmp_path: Path) -> None:
        """Test upgrading to temporary key raises."""
        creds_file = tmp_path / "creds.json"
        store = CredentialStore(credential_path=creds_file)
        store.get_or_create()

        # Trying to upgrade with a temp key should fail regardless of key_type param
        temp_key = "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        with pytest.raises(CredentialError, match="Cannot upgrade to a temporary key"):
            store.upgrade_key(temp_key, "live")

    def test_delete_existing_file(self, temp_credentials_file: Path) -> None:
        """Test deleting existing credentials file."""
        store = CredentialStore(credential_path=temp_credentials_file)
        assert temp_credentials_file.exists()

        result = store.delete()
        assert result is True
        assert not temp_credentials_file.exists()

    def test_delete_nonexistent_file(self, tmp_path: Path) -> None:
        """Test deleting nonexistent file returns False."""
        creds_file = tmp_path / "missing.json"
        store = CredentialStore(credential_path=creds_file)

        result = store.delete()
        assert result is False

    def test_update_first_seen(self, temp_credentials_file: Path) -> None:
        """Test updating first_seen_at from server."""
        store = CredentialStore(credential_path=temp_credentials_file)
        first_seen = "2025-01-26T12:00:00Z"

        creds = store.update_first_seen(first_seen)
        assert creds is not None
        assert creds.first_seen_at == first_seen

        # Verify it was persisted
        loaded = store.load()
        assert loaded is not None
        assert loaded.first_seen_at == first_seen

    def test_update_first_seen_no_overwrite(self, tmp_path: Path) -> None:
        """Test first_seen_at is not overwritten if already set."""
        # Create credentials with first_seen_at already set
        creds_file = tmp_path / "creds.json"
        original_first_seen = "2025-01-25T10:00:00Z"
        creds_file.write_text(
            json.dumps(
                {
                    "api_key": "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
                    "key_type": "temporary",
                    "installation_id": "inst_abc123def456gh",
                    "created_at": "2025-01-25T10:00:00Z",
                    "expires_at": "2025-02-08T10:00:00Z",
                    "first_seen_at": original_first_seen,
                }
            )
        )

        store = CredentialStore(credential_path=creds_file)
        creds = store.update_first_seen("2025-01-26T12:00:00Z")

        # Should NOT overwrite
        assert creds is not None
        assert creds.first_seen_at == original_first_seen

    def test_update_first_seen_no_credentials(self, tmp_path: Path) -> None:
        """Test update_first_seen returns None when no credentials."""
        store = CredentialStore(credential_path=tmp_path / "missing.json")
        result = store.update_first_seen("2025-01-26T12:00:00Z")
        assert result is None


class TestPermissionWarnings:
    """Test file permission warnings."""

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod not applicable on Windows")
    def test_warns_on_insecure_permissions(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test warning is logged for insecure file permissions."""
        import logging

        # Create credentials file with insecure permissions
        creds_file = tmp_path / "insecure_creds.json"
        creds_file.write_text(
            json.dumps(
                {
                    "api_key": "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
                    "key_type": "temporary",
                    "installation_id": "inst_abc123def456gh",
                    "created_at": "2025-01-26T10:00:00Z",
                    "expires_at": "2025-02-09T10:00:00Z",
                    "first_seen_at": None,
                }
            )
        )
        # Make it world-readable
        os.chmod(creds_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH)

        with caplog.at_level(logging.WARNING):
            store = CredentialStore(credential_path=creds_file)
            store.load()

        assert "insecure permissions" in caplog.text.lower()


class TestKeyGeneration:
    """Test key and ID generation."""

    def test_generated_temp_keys_are_unique(self, tmp_path: Path) -> None:
        """Test that generated temp keys are unique."""
        store = CredentialStore(credential_path=tmp_path / "creds.json")
        keys = set()
        for _ in range(100):
            creds = store.generate_temp_credentials()
            assert creds.api_key not in keys
            keys.add(creds.api_key)

    def test_generated_installation_ids_are_unique(self, tmp_path: Path) -> None:
        """Test that generated installation IDs are unique."""
        store = CredentialStore(credential_path=tmp_path / "creds.json")
        ids = set()
        for _ in range(100):
            creds = store.generate_temp_credentials()
            assert creds.installation_id not in ids
            ids.add(creds.installation_id)

    def test_generated_keys_match_pattern(self, tmp_path: Path) -> None:
        """Test generated keys match required pattern."""
        store = CredentialStore(credential_path=tmp_path / "creds.json")
        for _ in range(10):
            creds = store.generate_temp_credentials()
            assert KEY_PATTERNS["temporary"].match(creds.api_key)


class TestServerPermissionFields:
    """Test server permission fields on Credentials."""

    def test_default_permission_values(self) -> None:
        """Test that new permission fields have correct defaults."""
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at="2025-02-09T10:00:00Z",
            first_seen_at=None,
        )
        assert creds.can_disable_telemetry is False
        assert creds.offline_mode is False
        assert creds.tier == "temporary"
        assert creds.last_health_check is None

    def test_permission_fields_round_trip(self, tmp_path: Path) -> None:
        """Test permission fields survive save/load cycle."""
        creds_file = tmp_path / "creds.json"
        store = CredentialStore(credential_path=creds_file)

        creds = Credentials(
            api_key="raxe_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="live",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at=None,
            first_seen_at=None,
            can_disable_telemetry=True,
            offline_mode=True,
            tier="pro",
            last_health_check="2025-01-26T12:00:00Z",
        )

        store.save(creds)
        loaded = store.load()

        assert loaded is not None
        assert loaded.can_disable_telemetry is True
        assert loaded.offline_mode is True
        assert loaded.tier == "pro"
        assert loaded.last_health_check == "2025-01-26T12:00:00Z"

    def test_from_dict_with_permission_fields(self) -> None:
        """Test from_dict handles permission fields."""
        data = {
            "api_key": "raxe_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            "key_type": "live",
            "installation_id": "inst_abc123def456gh",
            "created_at": "2025-01-26T10:00:00Z",
            "expires_at": None,
            "first_seen_at": None,
            "can_disable_telemetry": True,
            "offline_mode": False,
            "tier": "enterprise",
            "last_health_check": "2025-01-26T15:00:00Z",
        }
        creds = Credentials.from_dict(data)

        assert creds.can_disable_telemetry is True
        assert creds.offline_mode is False
        assert creds.tier == "enterprise"
        assert creds.last_health_check == "2025-01-26T15:00:00Z"

    def test_from_dict_backward_compatible(self) -> None:
        """Test from_dict works with old credentials without permission fields."""
        data = {
            "api_key": "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            "key_type": "temporary",
            "installation_id": "inst_abc123def456gh",
            "created_at": "2025-01-26T10:00:00Z",
            "expires_at": "2025-02-09T10:00:00Z",
            "first_seen_at": None,
            # No permission fields - simulating old credentials
        }
        creds = Credentials.from_dict(data)

        # Should use defaults
        assert creds.can_disable_telemetry is False
        assert creds.offline_mode is False
        assert creds.tier == "temporary"
        assert creds.last_health_check is None


class TestHealthCheckStale:
    """Test health check staleness checking."""

    def test_is_health_check_stale_no_check(self) -> None:
        """Test staleness when no health check was performed."""
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at="2025-02-09T10:00:00Z",
            first_seen_at=None,
            last_health_check=None,
        )
        assert creds.is_health_check_stale() is True

    def test_is_health_check_stale_recent(self) -> None:
        """Test recent health check is not stale."""
        # Use recent timestamp
        recent = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at="2025-02-09T10:00:00Z",
            first_seen_at=None,
            last_health_check=recent,
        )
        assert creds.is_health_check_stale(max_age_hours=24) is False

    def test_is_health_check_stale_old(self) -> None:
        """Test old health check is stale."""
        # Use old timestamp (48 hours ago)
        old = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at="2025-02-09T10:00:00Z",
            first_seen_at=None,
            last_health_check=old,
        )
        assert creds.is_health_check_stale(max_age_hours=24) is True

    def test_is_health_check_stale_custom_max_age(self) -> None:
        """Test staleness with custom max age."""
        # 2 hours ago
        two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at="2025-02-09T10:00:00Z",
            first_seen_at=None,
            last_health_check=two_hours_ago,
        )
        # Not stale with 24h max age
        assert creds.is_health_check_stale(max_age_hours=24) is False
        # Stale with 1h max age
        assert creds.is_health_check_stale(max_age_hours=1) is True


class TestUpdateFromHealth:
    """Test update_from_health method on CredentialStore."""

    def test_update_from_health_basic(self, tmp_path: Path) -> None:
        """Test basic health update."""
        creds_file = tmp_path / "creds.json"
        store = CredentialStore(credential_path=creds_file)

        # Create initial credentials
        creds = store.generate_temp_credentials()
        store.save(creds)

        # Update from health response
        health_response = {
            "can_disable_telemetry": True,
            "offline_mode": False,
            "tier": "pro",
            "server_time": "2025-01-26T12:00:00Z",
        }
        updated = store.update_from_health(health_response)

        assert updated is not None
        assert updated.can_disable_telemetry is True
        assert updated.tier == "pro"
        assert updated.last_health_check == "2025-01-26T12:00:00Z"
        # Original fields preserved
        assert updated.api_key == creds.api_key
        assert updated.installation_id == creds.installation_id

    def test_update_from_health_no_credentials(self, tmp_path: Path) -> None:
        """Test health update when no credentials exist."""
        creds_file = tmp_path / "missing.json"
        store = CredentialStore(credential_path=creds_file)

        result = store.update_from_health({
            "can_disable_telemetry": True,
            "tier": "pro",
        })
        assert result is None

    def test_update_from_health_persists(self, tmp_path: Path) -> None:
        """Test health update is persisted to file."""
        creds_file = tmp_path / "creds.json"
        store = CredentialStore(credential_path=creds_file)

        # Create initial credentials
        store.get_or_create(raise_on_expired=False)

        # Update from health response
        store.update_from_health({
            "can_disable_telemetry": True,
            "tier": "enterprise",
            "server_time": "2025-01-26T14:00:00Z",
        })

        # Load fresh to verify persistence
        new_store = CredentialStore(credential_path=creds_file)
        loaded = new_store.load()

        assert loaded is not None
        assert loaded.can_disable_telemetry is True
        assert loaded.tier == "enterprise"
        assert loaded.last_health_check == "2025-01-26T14:00:00Z"

    def test_update_from_health_preserves_first_seen(self, tmp_path: Path) -> None:
        """Test health update preserves first_seen_at."""
        creds_file = tmp_path / "creds.json"
        store = CredentialStore(credential_path=creds_file)

        # Create credentials with first_seen_at
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at="2025-02-09T10:00:00Z",
            first_seen_at="2025-01-26T10:30:00Z",
        )
        store.save(creds)

        # Update from health
        updated = store.update_from_health({
            "can_disable_telemetry": False,
            "tier": "community",
            "server_time": "2025-01-26T12:00:00Z",
        })

        assert updated is not None
        assert updated.first_seen_at == "2025-01-26T10:30:00Z"


class TestCredentialExpiredError:
    """Test CredentialExpiredError exception class."""

    def test_error_creation_with_defaults(self) -> None:
        """Test creating error with default values."""
        error = CredentialExpiredError("Key expired")
        assert str(error) == "Key expired"
        assert error.console_url == "https://console.raxe.ai/keys"
        assert error.days_expired == 0

    def test_error_creation_with_custom_values(self) -> None:
        """Test creating error with custom console URL and days."""
        error = CredentialExpiredError(
            "Custom message",
            console_url="https://custom.example.com/keys",
            days_expired=5,
        )
        assert str(error) == "Custom message"
        assert error.console_url == "https://custom.example.com/keys"
        assert error.days_expired == 5

    def test_error_is_credential_error_subclass(self) -> None:
        """Test CredentialExpiredError is a subclass of CredentialError."""
        error = CredentialExpiredError("Test")
        assert isinstance(error, CredentialError)


class TestCredentialsDaysSinceExpiry:
    """Test days_since_expiry method on Credentials."""

    def test_days_since_expiry_no_expiry(self) -> None:
        """Test days_since_expiry returns None when no expiry set."""
        creds = Credentials(
            api_key="raxe_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="live",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at=None,
            first_seen_at=None,
        )
        assert creds.days_since_expiry() is None

    def test_days_since_expiry_not_expired(self) -> None:
        """Test days_since_expiry returns 0 for not-yet-expired key."""
        future = datetime.now(timezone.utc) + timedelta(days=7)
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at=future.strftime("%Y-%m-%dT%H:%M:%SZ"),
            first_seen_at=None,
        )
        assert creds.days_since_expiry() == 0

    def test_days_since_expiry_expired_recently(self) -> None:
        """Test days_since_expiry returns 0 for key expired today."""
        # Expired a few hours ago
        past = datetime.now(timezone.utc) - timedelta(hours=6)
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at=past.strftime("%Y-%m-%dT%H:%M:%SZ"),
            first_seen_at=None,
        )
        assert creds.days_since_expiry() == 0

    def test_days_since_expiry_expired_5_days(self) -> None:
        """Test days_since_expiry returns correct days for expired key."""
        past = datetime.now(timezone.utc) - timedelta(days=5)
        creds = Credentials(
            api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            key_type="temporary",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at=past.strftime("%Y-%m-%dT%H:%M:%SZ"),
            first_seen_at=None,
        )
        days = creds.days_since_expiry()
        assert days is not None
        assert days >= 4  # Allow for test timing


class TestGetOrCreateExpiredMessages:
    """Test get_or_create error messages for different expiry durations."""

    def test_expired_today_message(self, tmp_path: Path) -> None:
        """Test error message for key expired today."""
        creds_file = tmp_path / "expired_today.json"
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        creds_file.write_text(
            json.dumps(
                {
                    "api_key": "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
                    "key_type": "temporary",
                    "installation_id": "inst_abc123def456gh",
                    "created_at": "2025-01-01T10:00:00Z",
                    "expires_at": past.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "first_seen_at": None,
                }
            )
        )

        store = CredentialStore(credential_path=creds_file)

        with pytest.raises(CredentialExpiredError) as exc_info:
            store.get_or_create()

        error = exc_info.value
        assert error.days_expired == 0
        assert "today" in str(error).lower()

    def test_expired_1_day_message(self, tmp_path: Path) -> None:
        """Test error message for key expired 1 day ago."""
        creds_file = tmp_path / "expired_1day.json"
        past = datetime.now(timezone.utc) - timedelta(days=1, hours=2)
        creds_file.write_text(
            json.dumps(
                {
                    "api_key": "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
                    "key_type": "temporary",
                    "installation_id": "inst_abc123def456gh",
                    "created_at": "2025-01-01T10:00:00Z",
                    "expires_at": past.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "first_seen_at": None,
                }
            )
        )

        store = CredentialStore(credential_path=creds_file)

        with pytest.raises(CredentialExpiredError) as exc_info:
            store.get_or_create()

        error = exc_info.value
        assert error.days_expired == 1
        assert "1 day ago" in str(error)

    def test_expired_multiple_days_message(self, tmp_path: Path) -> None:
        """Test error message for key expired multiple days ago."""
        creds_file = tmp_path / "expired_5days.json"
        past = datetime.now(timezone.utc) - timedelta(days=5)
        creds_file.write_text(
            json.dumps(
                {
                    "api_key": "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
                    "key_type": "temporary",
                    "installation_id": "inst_abc123def456gh",
                    "created_at": "2025-01-01T10:00:00Z",
                    "expires_at": past.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "first_seen_at": None,
                }
            )
        )

        store = CredentialStore(credential_path=creds_file)

        with pytest.raises(CredentialExpiredError) as exc_info:
            store.get_or_create()

        error = exc_info.value
        assert error.days_expired >= 4  # Allow for timing
        assert "days ago" in str(error)

    def test_message_includes_auth_command(self, tmp_path: Path) -> None:
        """Test error message includes auth command."""
        creds_file = tmp_path / "expired.json"
        past = datetime.now(timezone.utc) - timedelta(days=1)
        creds_file.write_text(
            json.dumps(
                {
                    "api_key": "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
                    "key_type": "temporary",
                    "installation_id": "inst_abc123def456gh",
                    "created_at": "2025-01-01T10:00:00Z",
                    "expires_at": past.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "first_seen_at": None,
                }
            )
        )

        store = CredentialStore(credential_path=creds_file)

        with pytest.raises(CredentialExpiredError) as exc_info:
            store.get_or_create()

        assert "raxe auth login" in str(exc_info.value)

    def test_non_expiring_key_never_raises(self, tmp_path: Path) -> None:
        """Test get_or_create never raises for permanent keys."""
        creds_file = tmp_path / "permanent_creds.json"
        creds_file.write_text(
            json.dumps(
                {
                    "api_key": "raxe_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
                    "key_type": "live",
                    "installation_id": "inst_abc123def456gh",
                    "created_at": "2025-01-01T10:00:00Z",
                    "expires_at": None,
                    "first_seen_at": None,
                }
            )
        )

        store = CredentialStore(credential_path=creds_file)
        creds = store.get_or_create(raise_on_expired=True)

        assert creds.is_expired() is False
        assert creds.key_type == "live"


class TestComputeKeyId:
    """Test compute_key_id utility function."""

    def test_returns_key_prefixed_hash(self) -> None:
        """Test compute_key_id returns key_ prefix with 12 hex chars."""
        api_key = "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        key_id = compute_key_id(api_key)

        assert key_id.startswith("key_")
        assert len(key_id) == 16  # "key_" (4) + 12 hex chars

    def test_is_deterministic(self) -> None:
        """Test same input produces same output."""
        api_key = "raxe_live_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4"
        key_id1 = compute_key_id(api_key)
        key_id2 = compute_key_id(api_key)

        assert key_id1 == key_id2

    def test_different_keys_produce_different_ids(self) -> None:
        """Test different keys produce different IDs."""
        key1 = "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        key2 = "raxe_temp_z9y8x7w6v5u4t3s2r1q0p9o8n7m6l5k4"

        key_id1 = compute_key_id(key1)
        key_id2 = compute_key_id(key2)

        assert key_id1 != key_id2

    def test_hex_suffix_is_valid(self) -> None:
        """Test the suffix is valid hexadecimal."""
        import re
        api_key = "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        key_id = compute_key_id(api_key)

        suffix = key_id[4:]  # Remove "key_" prefix
        assert re.match(r"^[a-f0-9]{12}$", suffix)

    def test_works_with_all_key_types(self) -> None:
        """Test compute_key_id works with temp, live, and test keys."""
        temp_key = "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        live_key = "raxe_live_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4"
        test_key = "raxe_test_m1n2o3p4q5r6s7t8u9v0w1x2y3z4a5b6"

        temp_id = compute_key_id(temp_key)
        live_id = compute_key_id(live_key)
        test_id = compute_key_id(test_key)

        # All should have the correct format
        assert temp_id.startswith("key_") and len(temp_id) == 16
        assert live_id.startswith("key_") and len(live_id) == 16
        assert test_id.startswith("key_") and len(test_id) == 16

        # All should be different
        assert len({temp_id, live_id, test_id}) == 3


class TestKeyUpgradeInfo:
    """Test KeyUpgradeInfo dataclass."""

    def test_creation_with_all_fields(self) -> None:
        """Test creating KeyUpgradeInfo with all fields."""
        creds = Credentials(
            api_key="raxe_live_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4",
            key_type="live",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at=None,
            first_seen_at=None,
        )

        info = KeyUpgradeInfo(
            previous_key_id="key_23cc2f9f21f9",
            new_key_id="key_7ce219b525f1",
            previous_key_type="temporary",
            new_key_type="live",
            days_on_previous=7,
            new_credentials=creds,
        )

        assert info.previous_key_id == "key_23cc2f9f21f9"
        assert info.new_key_id == "key_7ce219b525f1"
        assert info.previous_key_type == "temporary"
        assert info.new_key_type == "live"
        assert info.days_on_previous == 7
        assert info.new_credentials == creds

    def test_creation_with_none_previous(self) -> None:
        """Test creating KeyUpgradeInfo when no previous key exists."""
        creds = Credentials(
            api_key="raxe_live_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4",
            key_type="live",
            installation_id="inst_abc123def456gh",
            created_at="2025-01-26T10:00:00Z",
            expires_at=None,
            first_seen_at=None,
        )

        info = KeyUpgradeInfo(
            previous_key_id=None,
            new_key_id="key_7ce219b525f1",
            previous_key_type=None,
            new_key_type="live",
            days_on_previous=None,
            new_credentials=creds,
        )

        assert info.previous_key_id is None
        assert info.new_key_id == "key_7ce219b525f1"
        assert info.previous_key_type is None
        assert info.days_on_previous is None


class TestUpgradeKeyWithInfo:
    """Test upgrade_key_with_info method on CredentialStore."""

    def test_returns_key_upgrade_info(self, temp_credentials_file: Path) -> None:
        """Test upgrade_key_with_info returns KeyUpgradeInfo."""
        store = CredentialStore(credential_path=temp_credentials_file)
        new_key = "raxe_live_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4"

        info = store.upgrade_key_with_info(new_key, "live")

        assert isinstance(info, KeyUpgradeInfo)
        assert info.new_credentials.api_key == new_key
        assert info.new_credentials.key_type == "live"

    def test_captures_previous_key_id(self, temp_credentials_file: Path) -> None:
        """Test upgrade_key_with_info captures previous key ID."""
        store = CredentialStore(credential_path=temp_credentials_file)

        # Load existing to get the old key
        existing = store.load()
        assert existing is not None
        expected_prev_id = compute_key_id(existing.api_key)

        new_key = "raxe_live_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4"
        info = store.upgrade_key_with_info(new_key, "live")

        assert info.previous_key_id == expected_prev_id

    def test_captures_new_key_id(self, temp_credentials_file: Path) -> None:
        """Test upgrade_key_with_info computes new key ID."""
        store = CredentialStore(credential_path=temp_credentials_file)
        new_key = "raxe_live_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4"

        expected_new_id = compute_key_id(new_key)
        info = store.upgrade_key_with_info(new_key, "live")

        assert info.new_key_id == expected_new_id

    def test_captures_previous_key_type(self, temp_credentials_file: Path) -> None:
        """Test upgrade_key_with_info captures previous key type."""
        store = CredentialStore(credential_path=temp_credentials_file)
        new_key = "raxe_live_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4"

        info = store.upgrade_key_with_info(new_key, "live")

        assert info.previous_key_type == "temporary"

    def test_captures_new_key_type(self, temp_credentials_file: Path) -> None:
        """Test upgrade_key_with_info captures new key type."""
        store = CredentialStore(credential_path=temp_credentials_file)
        new_key = "raxe_live_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4"

        info = store.upgrade_key_with_info(new_key, "live")

        assert info.new_key_type == "live"

    def test_calculates_days_on_previous(self, tmp_path: Path) -> None:
        """Test upgrade_key_with_info calculates days on previous key."""
        # Create credentials from 5 days ago
        creds_file = tmp_path / "old_creds.json"
        five_days_ago = datetime.now(timezone.utc) - timedelta(days=5)
        future_expiry = datetime.now(timezone.utc) + timedelta(days=9)

        creds_file.write_text(
            json.dumps(
                {
                    "api_key": "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
                    "key_type": "temporary",
                    "installation_id": "inst_abc123def456gh",
                    "created_at": five_days_ago.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "expires_at": future_expiry.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "first_seen_at": None,
                }
            )
        )

        store = CredentialStore(credential_path=creds_file)
        new_key = "raxe_live_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4"

        info = store.upgrade_key_with_info(new_key, "live")

        assert info.days_on_previous is not None
        assert 4 <= info.days_on_previous <= 6  # Allow for timing variance

    def test_no_previous_when_no_existing_creds(self, tmp_path: Path) -> None:
        """Test upgrade_key_with_info handles no existing credentials."""
        creds_file = tmp_path / "new_creds.json"
        store = CredentialStore(credential_path=creds_file)
        new_key = "raxe_live_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4"

        info = store.upgrade_key_with_info(new_key, "live")

        assert info.previous_key_id is None
        assert info.previous_key_type is None
        assert info.days_on_previous is None

    def test_preserves_installation_id(self, temp_credentials_file: Path) -> None:
        """Test upgrade_key_with_info preserves installation ID."""
        store = CredentialStore(credential_path=temp_credentials_file)
        existing = store.load()
        assert existing is not None
        original_installation_id = existing.installation_id

        new_key = "raxe_live_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4"
        info = store.upgrade_key_with_info(new_key, "live")

        assert info.new_credentials.installation_id == original_installation_id

    def test_raises_on_invalid_key_format(self, temp_credentials_file: Path) -> None:
        """Test upgrade_key_with_info raises on invalid key format."""
        store = CredentialStore(credential_path=temp_credentials_file)

        with pytest.raises(InvalidKeyFormatError):
            store.upgrade_key_with_info("invalid_key", "live")

    def test_raises_on_temp_key_upgrade(self, temp_credentials_file: Path) -> None:
        """Test upgrade_key_with_info raises when upgrading to temp key."""
        store = CredentialStore(credential_path=temp_credentials_file)
        temp_key = "raxe_temp_z9y8x7w6v5u4t3s2r1q0p9o8n7m6l5k4"

        with pytest.raises(CredentialError, match="Cannot upgrade to a temporary key"):
            store.upgrade_key_with_info(temp_key, "live")

    def test_raises_on_key_type_mismatch(self, temp_credentials_file: Path) -> None:
        """Test upgrade_key_with_info raises on key type mismatch."""
        store = CredentialStore(credential_path=temp_credentials_file)
        live_key = "raxe_live_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4"

        with pytest.raises(CredentialError, match="Key type mismatch"):
            store.upgrade_key_with_info(live_key, "test")

    def test_upgrade_key_delegates_to_with_info(self, temp_credentials_file: Path) -> None:
        """Test upgrade_key uses upgrade_key_with_info internally."""
        store = CredentialStore(credential_path=temp_credentials_file)
        new_key = "raxe_live_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4"

        # Both methods should produce same credentials
        creds_via_upgrade = store.upgrade_key(new_key, "live")
        # Can't compare directly since upgrade_key already upgraded,
        # but we can verify the key was upgraded properly
        assert creds_via_upgrade.api_key == new_key
        assert creds_via_upgrade.key_type == "live"
