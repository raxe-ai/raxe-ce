"""Tests for API key validation."""

import pytest

from raxe.infrastructure.security.auth import (
    APIKey,
    APIKeyValidator,
    AuthError,
    KeyType,
)


class TestAPIKey:
    """Test APIKey parsing."""

    def test_parse_valid_live_key(self):
        """Test parsing valid live key."""
        key = "raxe_live_cust_abc123_a1b2c3d4e5f6g7h8"

        api_key = APIKey.parse(key)

        assert api_key.raw_key == key
        assert api_key.key_type == KeyType.LIVE
        assert api_key.customer_id == "cust_abc123"
        assert api_key.random_suffix == "a1b2c3d4e5f6g7h8"
        assert api_key.is_live
        assert not api_key.is_test

    def test_parse_valid_test_key(self):
        """Test parsing valid test key."""
        key = "raxe_test_cust_xyz789_z9y8x7w6v5u4t3s2"

        api_key = APIKey.parse(key)

        assert api_key.raw_key == key
        assert api_key.key_type == KeyType.TEST
        assert api_key.customer_id == "cust_xyz789"
        assert api_key.random_suffix == "z9y8x7w6v5u4t3s2"
        assert api_key.is_test
        assert not api_key.is_live

    def test_parse_empty_key(self):
        """Test parsing empty key raises error."""
        with pytest.raises(AuthError, match="cannot be empty"):
            APIKey.parse("")

    def test_parse_invalid_prefix(self):
        """Test parsing key with wrong prefix."""
        invalid_keys = [
            "invalid_live_cust_abc123_randomsuffix123",
            "rax_live_cust_abc123_randomsuffix123",
            "raxe_prod_cust_abc123_randomsuffix123",
        ]

        for invalid_key in invalid_keys:
            with pytest.raises(AuthError, match="Invalid API key format"):
                APIKey.parse(invalid_key)

    def test_parse_invalid_key_type(self):
        """Test parsing key with invalid type."""
        with pytest.raises(AuthError, match="Invalid API key format"):
            APIKey.parse("raxe_prod_cust_abc123_randomsuffix123")

    def test_parse_missing_customer_prefix(self):
        """Test parsing key without cust_ prefix."""
        with pytest.raises(AuthError, match="must start with 'cust_'"):
            APIKey.parse("raxe_live_abc123_randomsuffix123")

    def test_parse_short_random_suffix(self):
        """Test parsing key with too short random suffix."""
        with pytest.raises(AuthError, match="at least 12 characters"):
            APIKey.parse("raxe_live_cust_abc123_short")

    def test_parse_valid_min_length_suffix(self):
        """Test parsing key with minimum valid random suffix."""
        key = "raxe_live_cust_abc123_123456789012"  # Exactly 12 chars

        api_key = APIKey.parse(key)
        assert api_key.random_suffix == "123456789012"

    def test_parse_case_insensitive_type(self):
        """Test parsing is case-insensitive for key type."""
        keys = [
            "raxe_LIVE_cust_abc123_randomsuffix123",
            "raxe_Live_cust_abc123_randomsuffix123",
            "RAXE_LIVE_CUST_ABC123_RANDOMSUFFIX123",
        ]

        for key in keys:
            api_key = APIKey.parse(key)
            assert api_key.key_type == KeyType.LIVE

    def test_parse_special_characters_in_customer_id(self):
        """Test parsing customer ID with underscores."""
        key = "raxe_live_cust_my_company_123_randomsuffix123"

        api_key = APIKey.parse(key)
        assert api_key.customer_id == "cust_my_company_123"

    def test_parse_long_customer_id(self):
        """Test parsing with long customer ID."""
        key = "raxe_live_cust_very_long_customer_identifier_with_underscores_randomsuffix123"

        api_key = APIKey.parse(key)
        assert api_key.customer_id == "cust_very_long_customer_identifier_with_underscores"


class TestAPIKeyValidator:
    """Test APIKeyValidator class."""

    def test_validate_valid_key(self):
        """Test validating valid key."""
        validator = APIKeyValidator()
        key = "raxe_live_cust_test123_randomsuffix123"

        api_key = validator.validate_key(key)

        assert api_key.customer_id == "cust_test123"
        assert api_key.is_live

    def test_validate_customer_id_too_short(self):
        """Test validating customer ID that's too short."""
        validator = APIKeyValidator()
        # "cust_ab" is only 7 chars, minimum is 10
        key = "raxe_live_cust_ab_randomsuffix123"

        with pytest.raises(AuthError, match="too short"):
            validator.validate_key(key)

    def test_validate_customer_id_too_long(self):
        """Test validating customer ID that's too long."""
        validator = APIKeyValidator()
        # Create customer ID > 50 chars
        long_id = "cust_" + "a" * 50
        key = f"raxe_live_{long_id}_randomsuffix123"

        with pytest.raises(AuthError, match="too long"):
            validator.validate_key(key)

    def test_validate_customer_id_invalid_chars(self):
        """Test validating customer ID with invalid characters."""
        validator = APIKeyValidator()

        invalid_keys = [
            "raxe_live_cust_abc-123_randomsuffix123",  # Hyphen
            "raxe_live_cust_abc.123_randomsuffix123",  # Dot
        ]

        for invalid_key in invalid_keys:
            # These fail at regex parse level, not customer ID validation
            with pytest.raises(AuthError):
                validator.validate_key(invalid_key)

    def test_validate_customer_id_valid_chars(self):
        """Test validating customer ID with all valid characters."""
        validator = APIKeyValidator()
        key = "raxe_live_cust_abc123_randomsuffix123"

        api_key = validator.validate_key(key)
        assert api_key.customer_id == "cust_abc123"

    def test_extract_customer_id(self):
        """Test extracting customer ID from key."""
        validator = APIKeyValidator()
        key = "raxe_live_cust_test123_randomsuffix123"

        customer_id = validator.extract_customer_id(key)

        assert customer_id == "cust_test123"

    def test_extract_customer_id_invalid_key(self):
        """Test extracting customer ID from invalid key raises error."""
        validator = APIKeyValidator()

        with pytest.raises(AuthError):
            validator.extract_customer_id("invalid_key")

    def test_validate_key_live_and_test(self):
        """Test validating both live and test keys."""
        validator = APIKeyValidator()

        live_key = "raxe_live_cust_abc123_randomsuffix123"
        test_key = "raxe_test_cust_abc123_randomsuffix123"

        live_api_key = validator.validate_key(live_key)
        test_api_key = validator.validate_key(test_key)

        assert live_api_key.is_live
        assert test_api_key.is_test
        assert live_api_key.customer_id == test_api_key.customer_id
