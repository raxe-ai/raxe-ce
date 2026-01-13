"""Security tests for tenant infrastructure.

Tests for:
- Path traversal prevention
- Tenant ID validation
- Fail-closed behavior
"""

import pytest

from raxe.infrastructure.tenants.yaml_repository import (
    InvalidEntityIdError,
    YamlAppRepository,
    YamlPolicyRepository,
    YamlTenantRepository,
    validate_entity_id,
)


class TestEntityIdValidation:
    """Tests for entity ID validation to prevent path traversal."""

    def test_valid_simple_id(self):
        """Simple alphanumeric IDs are valid."""
        assert validate_entity_id("acme", "tenant") == "acme"
        assert validate_entity_id("bunny123", "tenant") == "bunny123"

    def test_valid_id_with_hyphens(self):
        """IDs with hyphens are valid."""
        assert validate_entity_id("acme-corp", "tenant") == "acme-corp"
        assert validate_entity_id("my-app-v2", "app") == "my-app-v2"

    def test_valid_id_with_underscores(self):
        """IDs with underscores are valid."""
        assert validate_entity_id("acme_corp", "tenant") == "acme_corp"
        assert validate_entity_id("my_app_v2", "app") == "my_app_v2"

    def test_path_traversal_dot_dot_slash_rejected(self):
        """Path traversal with ../ is rejected."""
        with pytest.raises(InvalidEntityIdError, match="Invalid tenant ID"):
            validate_entity_id("../admin", "tenant")

    def test_path_traversal_dot_dot_backslash_rejected(self):
        """Path traversal with ..\\ is rejected."""
        with pytest.raises(InvalidEntityIdError, match="Invalid tenant ID"):
            validate_entity_id("..\\admin", "tenant")

    def test_absolute_path_rejected(self):
        """Absolute paths are rejected."""
        with pytest.raises(InvalidEntityIdError, match="Invalid tenant ID"):
            validate_entity_id("/etc/passwd", "tenant")

    def test_hidden_directory_rejected(self):
        """Hidden directories (starting with .) are rejected."""
        with pytest.raises(InvalidEntityIdError, match="Invalid tenant ID"):
            validate_entity_id(".hidden", "tenant")

    def test_empty_id_rejected(self):
        """Empty IDs are rejected."""
        with pytest.raises(InvalidEntityIdError, match="Invalid tenant ID"):
            validate_entity_id("", "tenant")

    def test_whitespace_only_rejected(self):
        """Whitespace-only IDs are rejected."""
        with pytest.raises(InvalidEntityIdError, match="Invalid tenant ID"):
            validate_entity_id("   ", "tenant")

    def test_id_with_spaces_rejected(self):
        """IDs with spaces are rejected."""
        with pytest.raises(InvalidEntityIdError, match="Invalid tenant ID"):
            validate_entity_id("acme corp", "tenant")

    def test_id_with_special_chars_rejected(self):
        """IDs with special characters are rejected."""
        with pytest.raises(InvalidEntityIdError, match="Invalid"):
            validate_entity_id("acme@corp", "tenant")
        with pytest.raises(InvalidEntityIdError, match="Invalid"):
            validate_entity_id("acme$corp", "app")

    def test_unicode_path_traversal_rejected(self):
        """Unicode path traversal attempts are rejected."""
        # Various unicode representations of ../
        with pytest.raises(InvalidEntityIdError):
            validate_entity_id("．．/admin", "tenant")  # Fullwidth dots

    def test_null_byte_rejected(self):
        """Null bytes are rejected."""
        with pytest.raises(InvalidEntityIdError):
            validate_entity_id("acme\x00.yaml", "tenant")

    def test_reserved_names_rejected(self):
        """Reserved names like _global are rejected."""
        with pytest.raises(InvalidEntityIdError, match="reserved"):
            validate_entity_id("_global", "tenant")


class TestTenantRepositoryPathSecurity:
    """Tests that repositories use validation."""

    def test_get_tenant_validates_id(self, tmp_path):
        """get_tenant validates tenant_id."""
        repo = YamlTenantRepository(tmp_path)
        with pytest.raises(InvalidEntityIdError):
            repo.get_tenant("../malicious")

    def test_save_tenant_validates_id(self, tmp_path):
        """save_tenant validates tenant_id in the tenant object."""
        from raxe.domain.tenants.models import Tenant

        repo = YamlTenantRepository(tmp_path)
        # Create tenant with malicious ID - should fail validation
        tenant = Tenant(
            tenant_id="../malicious",
            name="Malicious",
            default_policy_id="balanced",
        )
        with pytest.raises(InvalidEntityIdError):
            repo.save_tenant(tenant)

    def test_delete_tenant_validates_id(self, tmp_path):
        """delete_tenant validates tenant_id."""
        repo = YamlTenantRepository(tmp_path)
        with pytest.raises(InvalidEntityIdError):
            repo.delete_tenant("../malicious")


class TestPolicyRepositoryPathSecurity:
    """Tests that policy repository uses validation."""

    def test_get_policy_validates_ids(self, tmp_path):
        """get_policy validates both policy_id and tenant_id."""
        repo = YamlPolicyRepository(tmp_path)

        with pytest.raises(InvalidEntityIdError):
            repo.get_policy("../malicious", "acme")

        with pytest.raises(InvalidEntityIdError):
            repo.get_policy("valid-policy", "../malicious")


class TestAppRepositoryPathSecurity:
    """Tests that app repository uses validation."""

    def test_get_app_validates_ids(self, tmp_path):
        """get_app validates both app_id and tenant_id."""
        repo = YamlAppRepository(tmp_path)

        with pytest.raises(InvalidEntityIdError):
            repo.get_app("../malicious", "acme")

        with pytest.raises(InvalidEntityIdError):
            repo.get_app("valid-app", "../malicious")
