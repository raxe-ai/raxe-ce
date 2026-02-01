"""Tests for YAML tenant/policy/app repositories.

TDD: These tests are written BEFORE implementation.
"""

from pathlib import Path

from raxe.domain.tenants.models import (
    App,
    PolicyMode,
    Tenant,
    TenantPolicy,
)
from raxe.infrastructure.tenants.yaml_repository import (
    YamlAppRepository,
    YamlPolicyRepository,
    YamlTenantRepository,
)


class TestYamlTenantRepository:
    """Tests for YamlTenantRepository."""

    def test_init_creates_base_path(self, tmp_path: Path) -> None:
        """Repository creates base path on init."""
        base_path = tmp_path / "tenants"
        repo = YamlTenantRepository(base_path)
        # Base path should be set
        assert repo.base_path == base_path

    def test_save_and_get_tenant(self, tmp_path: Path) -> None:
        """Can save and retrieve a tenant."""
        repo = YamlTenantRepository(tmp_path)
        tenant = Tenant(
            tenant_id="acme",
            name="Acme Corp",
            default_policy_id="balanced",
        )

        repo.save_tenant(tenant)
        loaded = repo.get_tenant("acme")

        assert loaded is not None
        assert loaded.tenant_id == "acme"
        assert loaded.name == "Acme Corp"
        assert loaded.default_policy_id == "balanced"

    def test_get_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """Getting nonexistent tenant returns None."""
        repo = YamlTenantRepository(tmp_path)
        assert repo.get_tenant("nonexistent") is None

    def test_delete_tenant(self, tmp_path: Path) -> None:
        """Can delete a tenant."""
        repo = YamlTenantRepository(tmp_path)
        tenant = Tenant(
            tenant_id="acme",
            name="Acme Corp",
            default_policy_id="balanced",
        )

        repo.save_tenant(tenant)
        assert repo.get_tenant("acme") is not None

        result = repo.delete_tenant("acme")
        assert result is True
        assert repo.get_tenant("acme") is None

    def test_delete_nonexistent_returns_false(self, tmp_path: Path) -> None:
        """Deleting nonexistent tenant returns False."""
        repo = YamlTenantRepository(tmp_path)
        assert repo.delete_tenant("nonexistent") is False

    def test_list_tenants(self, tmp_path: Path) -> None:
        """Can list all tenants."""
        repo = YamlTenantRepository(tmp_path)

        tenant1 = Tenant(tenant_id="acme", name="Acme", default_policy_id="balanced")
        tenant2 = Tenant(tenant_id="beta", name="Beta", default_policy_id="strict")

        repo.save_tenant(tenant1)
        repo.save_tenant(tenant2)

        tenants = repo.list_tenants()
        assert len(tenants) == 2
        tenant_ids = {t.tenant_id for t in tenants}
        assert tenant_ids == {"acme", "beta"}

    def test_list_tenants_empty(self, tmp_path: Path) -> None:
        """Listing tenants when none exist returns empty list."""
        repo = YamlTenantRepository(tmp_path)
        assert repo.list_tenants() == []

    def test_tenant_exists(self, tmp_path: Path) -> None:
        """Can check if tenant exists."""
        repo = YamlTenantRepository(tmp_path)
        tenant = Tenant(tenant_id="acme", name="Acme", default_policy_id="balanced")

        assert repo.tenant_exists("acme") is False
        repo.save_tenant(tenant)
        assert repo.tenant_exists("acme") is True

    def test_tenant_with_partner(self, tmp_path: Path) -> None:
        """Tenant with partner_id is saved correctly."""
        repo = YamlTenantRepository(tmp_path)
        tenant = Tenant(
            tenant_id="customer_123",
            name="Customer 123",
            default_policy_id="balanced",
            partner_id="partner_net",
            tier="enterprise",
        )

        repo.save_tenant(tenant)
        loaded = repo.get_tenant("customer_123")

        assert loaded is not None
        assert loaded.partner_id == "partner_net"
        assert loaded.tier == "enterprise"


class TestYamlPolicyRepository:
    """Tests for YamlPolicyRepository."""

    def test_save_and_get_policy(self, tmp_path: Path) -> None:
        """Can save and retrieve a policy."""
        repo = YamlPolicyRepository(tmp_path)
        policy = TenantPolicy(
            policy_id="custom_strict",
            name="Custom Strict",
            tenant_id="acme",
            mode=PolicyMode.STRICT,
            blocking_enabled=True,
        )

        repo.save_policy(policy)
        loaded = repo.get_policy("custom_strict", tenant_id="acme")

        assert loaded is not None
        assert loaded.policy_id == "custom_strict"
        assert loaded.mode == PolicyMode.STRICT

    def test_get_global_policy(self, tmp_path: Path) -> None:
        """Can save and retrieve global policy (tenant_id=None)."""
        repo = YamlPolicyRepository(tmp_path)
        policy = TenantPolicy(
            policy_id="global_monitor",
            name="Global Monitor",
            tenant_id=None,
            mode=PolicyMode.MONITOR,
            blocking_enabled=False,
        )

        repo.save_policy(policy)
        loaded = repo.get_policy("global_monitor", tenant_id=None)

        assert loaded is not None
        assert loaded.tenant_id is None

    def test_get_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """Getting nonexistent policy returns None."""
        repo = YamlPolicyRepository(tmp_path)
        assert repo.get_policy("nonexistent") is None

    def test_delete_policy(self, tmp_path: Path) -> None:
        """Can delete a policy."""
        repo = YamlPolicyRepository(tmp_path)
        policy = TenantPolicy(
            policy_id="test",
            name="Test",
            tenant_id="acme",
            mode=PolicyMode.BALANCED,
            blocking_enabled=True,
        )

        repo.save_policy(policy)
        assert repo.get_policy("test", tenant_id="acme") is not None

        result = repo.delete_policy("test", tenant_id="acme")
        assert result is True
        assert repo.get_policy("test", tenant_id="acme") is None

    def test_list_policies_by_tenant(self, tmp_path: Path) -> None:
        """Can list policies for a specific tenant."""
        repo = YamlPolicyRepository(tmp_path)

        policy1 = TenantPolicy(
            policy_id="p1",
            name="Policy 1",
            tenant_id="acme",
            mode=PolicyMode.BALANCED,
            blocking_enabled=True,
        )
        policy2 = TenantPolicy(
            policy_id="p2",
            name="Policy 2",
            tenant_id="acme",
            mode=PolicyMode.STRICT,
            blocking_enabled=True,
        )
        policy3 = TenantPolicy(
            policy_id="p3",
            name="Policy 3",
            tenant_id="other",
            mode=PolicyMode.MONITOR,
            blocking_enabled=False,
        )

        repo.save_policy(policy1)
        repo.save_policy(policy2)
        repo.save_policy(policy3)

        acme_policies = repo.list_policies(tenant_id="acme")
        assert len(acme_policies) == 2
        policy_ids = {p.policy_id for p in acme_policies}
        assert policy_ids == {"p1", "p2"}

    def test_get_all_policies_as_registry(self, tmp_path: Path) -> None:
        """Can get all policies as lookup dictionary."""
        repo = YamlPolicyRepository(tmp_path)

        policy = TenantPolicy(
            policy_id="custom",
            name="Custom",
            tenant_id="acme",
            mode=PolicyMode.BALANCED,
            blocking_enabled=True,
        )
        repo.save_policy(policy)

        registry = repo.get_all_policies_as_registry()
        assert "custom" in registry
        assert registry["custom"].policy_id == "custom"


class TestYamlAppRepository:
    """Tests for YamlAppRepository."""

    def test_save_and_get_app(self, tmp_path: Path) -> None:
        """Can save and retrieve an app."""
        repo = YamlAppRepository(tmp_path)
        app = App(
            app_id="chatbot",
            tenant_id="acme",
            name="Customer Support Bot",
            default_policy_id="strict",
        )

        repo.save_app(app)
        loaded = repo.get_app("chatbot", tenant_id="acme")

        assert loaded is not None
        assert loaded.app_id == "chatbot"
        assert loaded.name == "Customer Support Bot"
        assert loaded.default_policy_id == "strict"

    def test_get_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """Getting nonexistent app returns None."""
        repo = YamlAppRepository(tmp_path)
        assert repo.get_app("nonexistent", tenant_id="acme") is None

    def test_delete_app(self, tmp_path: Path) -> None:
        """Can delete an app."""
        repo = YamlAppRepository(tmp_path)
        app = App(
            app_id="chatbot",
            tenant_id="acme",
            name="Bot",
        )

        repo.save_app(app)
        assert repo.get_app("chatbot", tenant_id="acme") is not None

        result = repo.delete_app("chatbot", tenant_id="acme")
        assert result is True
        assert repo.get_app("chatbot", tenant_id="acme") is None

    def test_list_apps_for_tenant(self, tmp_path: Path) -> None:
        """Can list all apps for a tenant."""
        repo = YamlAppRepository(tmp_path)

        app1 = App(app_id="app1", tenant_id="acme", name="App 1")
        app2 = App(app_id="app2", tenant_id="acme", name="App 2")
        app3 = App(app_id="app3", tenant_id="other", name="App 3")

        repo.save_app(app1)
        repo.save_app(app2)
        repo.save_app(app3)

        acme_apps = repo.list_apps(tenant_id="acme")
        assert len(acme_apps) == 2
        app_ids = {a.app_id for a in acme_apps}
        assert app_ids == {"app1", "app2"}

    def test_list_apps_empty(self, tmp_path: Path) -> None:
        """Listing apps for tenant with no apps returns empty list."""
        repo = YamlAppRepository(tmp_path)
        assert repo.list_apps(tenant_id="acme") == []

    def test_app_without_default_policy(self, tmp_path: Path) -> None:
        """App without default_policy_id is saved correctly."""
        repo = YamlAppRepository(tmp_path)
        app = App(
            app_id="basic",
            tenant_id="acme",
            name="Basic App",
            default_policy_id=None,
        )

        repo.save_app(app)
        loaded = repo.get_app("basic", tenant_id="acme")

        assert loaded is not None
        assert loaded.default_policy_id is None


class TestYamlRepositoryErrorHandling:
    """Tests for error handling in YAML repositories."""

    def test_tenant_get_invalid_yaml(self, tmp_path: Path) -> None:
        """Getting tenant with invalid YAML returns None."""
        repo = YamlTenantRepository(tmp_path)
        tenant_dir = tmp_path / "acme"
        tenant_dir.mkdir(parents=True)
        tenant_file = tenant_dir / "tenant.yaml"
        tenant_file.write_text("invalid: yaml: content: {{")

        result = repo.get_tenant("acme")
        assert result is None

    def test_tenant_get_missing_tenant_key(self, tmp_path: Path) -> None:
        """Getting tenant with missing 'tenant' key returns None."""
        repo = YamlTenantRepository(tmp_path)
        tenant_dir = tmp_path / "acme"
        tenant_dir.mkdir(parents=True)
        tenant_file = tenant_dir / "tenant.yaml"
        tenant_file.write_text("version: '1.0'\nother_key: value\n")

        result = repo.get_tenant("acme")
        assert result is None

    def test_tenant_get_invalid_data(self, tmp_path: Path) -> None:
        """Getting tenant with invalid data returns None."""
        repo = YamlTenantRepository(tmp_path)
        tenant_dir = tmp_path / "acme"
        tenant_dir.mkdir(parents=True)
        tenant_file = tenant_dir / "tenant.yaml"
        # Missing required fields
        tenant_file.write_text("version: '1.0'\ntenant:\n  name: 'Incomplete'\n")

        result = repo.get_tenant("acme")
        assert result is None

    def test_tenant_list_skips_invalid(self, tmp_path: Path) -> None:
        """Listing tenants skips invalid ones."""
        repo = YamlTenantRepository(tmp_path)

        # Create valid tenant
        valid = Tenant(tenant_id="valid", name="Valid", default_policy_id="balanced")
        repo.save_tenant(valid)

        # Create invalid tenant
        invalid_dir = tmp_path / "invalid"
        invalid_dir.mkdir(parents=True)
        (invalid_dir / "tenant.yaml").write_text("invalid: yaml: {{")

        tenants = repo.list_tenants()
        assert len(tenants) == 1
        assert tenants[0].tenant_id == "valid"

    def test_policy_get_invalid_yaml(self, tmp_path: Path) -> None:
        """Getting policy with invalid YAML returns None."""
        repo = YamlPolicyRepository(tmp_path)
        policy_dir = tmp_path / "acme" / "policies"
        policy_dir.mkdir(parents=True)
        policy_file = policy_dir / "broken.yaml"
        policy_file.write_text("invalid: yaml: content: {{")

        result = repo.get_policy("broken", tenant_id="acme")
        assert result is None

    def test_policy_get_missing_policy_key(self, tmp_path: Path) -> None:
        """Getting policy with missing 'policy' key returns None."""
        repo = YamlPolicyRepository(tmp_path)
        policy_dir = tmp_path / "acme" / "policies"
        policy_dir.mkdir(parents=True)
        policy_file = policy_dir / "test.yaml"
        policy_file.write_text("version: '1.0'\nother_key: value\n")

        result = repo.get_policy("test", tenant_id="acme")
        assert result is None

    def test_policy_get_invalid_mode(self, tmp_path: Path) -> None:
        """Getting policy with invalid mode returns None."""
        repo = YamlPolicyRepository(tmp_path)
        policy_dir = tmp_path / "acme" / "policies"
        policy_dir.mkdir(parents=True)
        policy_file = policy_dir / "bad.yaml"
        policy_file.write_text(
            "version: '1.0'\npolicy:\n  policy_id: bad\n  name: Bad\n  mode: invalid_mode\n"
        )

        result = repo.get_policy("bad", tenant_id="acme")
        assert result is None

    def test_policy_delete_nonexistent_returns_false(self, tmp_path: Path) -> None:
        """Deleting nonexistent policy returns False."""
        repo = YamlPolicyRepository(tmp_path)
        result = repo.delete_policy("nonexistent", tenant_id="acme")
        assert result is False

    def test_app_get_invalid_yaml(self, tmp_path: Path) -> None:
        """Getting app with invalid YAML returns None."""
        repo = YamlAppRepository(tmp_path)
        app_dir = tmp_path / "acme" / "apps"
        app_dir.mkdir(parents=True)
        app_file = app_dir / "broken.yaml"
        app_file.write_text("invalid: yaml: content: {{")

        result = repo.get_app("broken", tenant_id="acme")
        assert result is None

    def test_app_get_missing_app_key(self, tmp_path: Path) -> None:
        """Getting app with missing 'app' key returns None."""
        repo = YamlAppRepository(tmp_path)
        app_dir = tmp_path / "acme" / "apps"
        app_dir.mkdir(parents=True)
        app_file = app_dir / "test.yaml"
        app_file.write_text("version: '1.0'\nother_key: value\n")

        result = repo.get_app("test", tenant_id="acme")
        assert result is None

    def test_app_get_invalid_data(self, tmp_path: Path) -> None:
        """Getting app with invalid data returns None."""
        repo = YamlAppRepository(tmp_path)
        app_dir = tmp_path / "acme" / "apps"
        app_dir.mkdir(parents=True)
        app_file = app_dir / "bad.yaml"
        # Missing required fields
        app_file.write_text("version: '1.0'\napp:\n  name: 'Incomplete'\n")

        result = repo.get_app("bad", tenant_id="acme")
        assert result is None

    def test_app_delete_nonexistent_returns_false(self, tmp_path: Path) -> None:
        """Deleting nonexistent app returns False."""
        repo = YamlAppRepository(tmp_path)
        result = repo.delete_app("nonexistent", tenant_id="acme")
        assert result is False
