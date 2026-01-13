"""Tests for tenant infrastructure utilities.

Tests cover:
- slugify(): Pure function for URL-safe slug generation
- get_available_policies(): I/O function for policy listing
- build_policy_registry(): I/O function for registry building
- verify_tenant_exists(): I/O function for tenant verification
"""

from raxe.infrastructure.tenants.utils import (
    build_policy_registry,
    get_available_policies,
    slugify,
    verify_tenant_exists,
)


class TestSlugify:
    """Tests for slugify() pure function."""

    def test_basic_conversion(self):
        """Basic name converts to lowercase with hyphens."""
        assert slugify("My Cool Project") == "my-cool-project"

    def test_uppercase(self):
        """Uppercase is converted to lowercase."""
        assert slugify("UPPERCASE") == "uppercase"

    def test_mixed_case(self):
        """Mixed case is normalized to lowercase."""
        assert slugify("CamelCaseExample") == "camelcaseexample"

    def test_special_characters_removed(self):
        """Special characters are stripped."""
        assert slugify("special@#$chars") == "specialchars"

    def test_spaces_become_hyphens(self):
        """Spaces become hyphens."""
        assert slugify("multiple spaces") == "multiple-spaces"

    def test_underscores_become_hyphens(self):
        """Underscores become hyphens."""
        assert slugify("with_underscores") == "with-underscores"

    def test_mixed_separators(self):
        """Mixed spaces and underscores become single hyphens."""
        assert slugify("multiple   spaces___underscores") == "multiple-spaces-underscores"

    def test_strips_whitespace(self):
        """Leading/trailing whitespace is stripped."""
        assert slugify("  padded  ") == "padded"

    def test_consecutive_hyphens_collapsed(self):
        """Multiple consecutive hyphens become one."""
        assert slugify("a--b---c") == "a-b-c"

    def test_leading_hyphens_removed(self):
        """Leading hyphens are removed."""
        assert slugify("-leading") == "leading"

    def test_trailing_hyphens_removed(self):
        """Trailing hyphens are removed."""
        assert slugify("trailing-") == "trailing"

    def test_leading_and_trailing_hyphens_removed(self):
        """Both leading and trailing hyphens are removed."""
        assert slugify("-both-ends-") == "both-ends"

    def test_empty_returns_default_fallback(self):
        """Empty string returns default fallback 'entity'."""
        assert slugify("") == "entity"

    def test_empty_returns_custom_fallback(self):
        """Empty string returns custom fallback when provided."""
        assert slugify("", fallback="tenant") == "tenant"
        assert slugify("", fallback="policy") == "policy"
        assert slugify("", fallback="app") == "app"

    def test_only_special_chars_returns_fallback(self):
        """String with only special chars returns fallback."""
        assert slugify("@#$%") == "entity"
        assert slugify("@#$%", fallback="tenant") == "tenant"

    def test_only_hyphens_returns_fallback(self):
        """String of only hyphens returns fallback."""
        assert slugify("---") == "entity"
        assert slugify("---", fallback="policy") == "policy"

    def test_only_spaces_returns_fallback(self):
        """String of only spaces returns fallback."""
        assert slugify("   ") == "entity"

    def test_only_underscores_returns_fallback(self):
        """String of only underscores returns fallback."""
        assert slugify("___") == "entity"

    def test_numeric_only_allowed(self):
        """Numeric-only strings are valid slugs."""
        assert slugify("123") == "123"
        assert slugify("2024") == "2024"

    def test_alphanumeric_preserved(self):
        """Alphanumeric content is preserved."""
        assert slugify("abc123") == "abc123"
        assert slugify("Project2024") == "project2024"

    def test_hyphens_in_name_preserved(self):
        """Existing hyphens in name are preserved."""
        assert slugify("already-hyphenated") == "already-hyphenated"

    def test_mixed_valid_complex(self):
        """Complex mixed input produces expected output."""
        assert slugify("Project-V2_Beta") == "project-v2-beta"
        assert slugify("  Acme Corp 2024!  ") == "acme-corp-2024"

    def test_unicode_characters_stripped(self):
        """Unicode characters are stripped (only a-z0-9- allowed)."""
        assert slugify("café") == "caf"
        assert slugify("naïve") == "nave"

    def test_real_world_tenant_names(self):
        """Real-world tenant name examples work correctly."""
        assert slugify("Acme Corporation") == "acme-corporation"
        assert slugify("Bunny.net CDN") == "bunnynet-cdn"
        assert slugify("First National Bank") == "first-national-bank"
        assert slugify("My App (Production)") == "my-app-production"


class TestGetAvailablePolicies:
    """Tests for get_available_policies() I/O function."""

    def test_returns_global_presets_for_nonexistent_tenant(self, tmp_path):
        """Non-existent tenant returns only global presets."""
        policies = get_available_policies("nonexistent", base_path=tmp_path)
        assert "monitor" in policies
        assert "balanced" in policies
        assert "strict" in policies
        assert len(policies) == 3

    def test_includes_tenant_custom_policies(self, tmp_path):
        """Tenant-specific policies are included in results."""
        from datetime import datetime, timezone

        from raxe.domain.tenants.models import PolicyMode, Tenant, TenantPolicy
        from raxe.infrastructure.tenants import YamlPolicyRepository, YamlTenantRepository

        # Create tenant
        tenant_repo = YamlTenantRepository(tmp_path)
        tenant = Tenant(
            tenant_id="test-tenant",
            name="Test Tenant",
            default_policy_id="balanced",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        tenant_repo.save_tenant(tenant)

        # Create custom policy
        policy_repo = YamlPolicyRepository(tmp_path)
        custom_policy = TenantPolicy(
            policy_id="custom-strict",
            name="Custom Strict",
            tenant_id="test-tenant",
            mode=PolicyMode.STRICT,
            blocking_enabled=True,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        policy_repo.save_policy(custom_policy)

        # Verify custom policy is included
        policies = get_available_policies("test-tenant", base_path=tmp_path)
        assert "custom-strict" in policies
        assert len(policies) == 4  # 3 presets + 1 custom

    def test_global_presets_listed_first(self, tmp_path):
        """Global presets appear before tenant-specific policies."""
        policies = get_available_policies("any-tenant", base_path=tmp_path)
        # First three should be the global presets
        assert policies[:3] == ["monitor", "balanced", "strict"]


class TestBuildPolicyRegistry:
    """Tests for build_policy_registry() I/O function."""

    def test_returns_global_presets_for_nonexistent_tenant(self, tmp_path):
        """Non-existent tenant returns only global presets in registry."""
        registry = build_policy_registry("nonexistent", base_path=tmp_path)
        assert "monitor" in registry
        assert "balanced" in registry
        assert "strict" in registry
        assert len(registry) == 3

    def test_includes_tenant_custom_policies(self, tmp_path):
        """Tenant-specific policies are included in registry."""
        from datetime import datetime, timezone

        from raxe.domain.tenants.models import PolicyMode, Tenant, TenantPolicy
        from raxe.infrastructure.tenants import YamlPolicyRepository, YamlTenantRepository

        # Create tenant
        tenant_repo = YamlTenantRepository(tmp_path)
        tenant = Tenant(
            tenant_id="test-tenant",
            name="Test Tenant",
            default_policy_id="balanced",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        tenant_repo.save_tenant(tenant)

        # Create custom policy
        policy_repo = YamlPolicyRepository(tmp_path)
        custom_policy = TenantPolicy(
            policy_id="custom-monitor",
            name="Custom Monitor",
            tenant_id="test-tenant",
            mode=PolicyMode.MONITOR,
            blocking_enabled=False,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        policy_repo.save_policy(custom_policy)

        # Verify custom policy is in registry
        registry = build_policy_registry("test-tenant", base_path=tmp_path)
        assert "custom-monitor" in registry
        assert registry["custom-monitor"].policy_id == "custom-monitor"

    def test_registry_values_are_tenant_policy_objects(self, tmp_path):
        """Registry values are TenantPolicy objects."""
        from raxe.domain.tenants.models import TenantPolicy

        registry = build_policy_registry("any-tenant", base_path=tmp_path)
        for policy_id, policy in registry.items():
            assert isinstance(policy, TenantPolicy)
            assert policy.policy_id == policy_id


class TestVerifyTenantExists:
    """Tests for verify_tenant_exists() I/O function."""

    def test_returns_false_for_nonexistent_tenant(self, tmp_path):
        """Non-existent tenant returns False."""
        assert verify_tenant_exists("nonexistent", base_path=tmp_path) is False

    def test_returns_true_for_existing_tenant(self, tmp_path):
        """Existing tenant returns True."""
        from datetime import datetime, timezone

        from raxe.domain.tenants.models import Tenant
        from raxe.infrastructure.tenants import YamlTenantRepository

        # Create tenant
        tenant_repo = YamlTenantRepository(tmp_path)
        tenant = Tenant(
            tenant_id="existing-tenant",
            name="Existing Tenant",
            default_policy_id="balanced",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        tenant_repo.save_tenant(tenant)

        # Verify exists
        assert verify_tenant_exists("existing-tenant", base_path=tmp_path) is True

    def test_returns_false_after_tenant_deleted(self, tmp_path):
        """Deleted tenant returns False."""
        from datetime import datetime, timezone

        from raxe.domain.tenants.models import Tenant
        from raxe.infrastructure.tenants import YamlTenantRepository

        # Create and then delete tenant
        tenant_repo = YamlTenantRepository(tmp_path)
        tenant = Tenant(
            tenant_id="temp-tenant",
            name="Temp Tenant",
            default_policy_id="balanced",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        tenant_repo.save_tenant(tenant)
        assert verify_tenant_exists("temp-tenant", base_path=tmp_path) is True

        tenant_repo.delete_tenant("temp-tenant")
        assert verify_tenant_exists("temp-tenant", base_path=tmp_path) is False
