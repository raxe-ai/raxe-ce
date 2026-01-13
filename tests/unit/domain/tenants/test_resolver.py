"""Tests for policy resolution engine.

TDD: These tests are written BEFORE implementation.
Tests the resolve_policy() function which implements the fallback chain:
Request → App → Tenant → System Default
"""

from raxe.domain.tenants.models import (
    App,
    PolicyMode,
    PolicyResolutionResult,
    Tenant,
    TenantPolicy,
)
from raxe.domain.tenants.presets import (
    GLOBAL_PRESETS,
)
from raxe.domain.tenants.resolver import resolve_policy


class TestResolveRequestOverride:
    """Tests for request-level policy override (highest priority)."""

    def test_request_policy_id_overrides_app(
        self,
        sample_tenant: Tenant,
        app_with_balanced: App,
    ) -> None:
        """Request-level policy_id overrides app default."""
        result = resolve_policy(
            request_policy_id="strict",
            app=app_with_balanced,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result.policy.policy_id == "strict"
        assert result.resolution_source == "request"

    def test_request_policy_id_overrides_tenant(
        self,
        sample_tenant: Tenant,
        app_without_policy: App,
    ) -> None:
        """Request-level policy_id overrides tenant default."""
        result = resolve_policy(
            request_policy_id="monitor",
            app=app_without_policy,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result.policy.policy_id == "monitor"
        assert result.resolution_source == "request"

    def test_request_policy_id_in_resolution_path(
        self,
        sample_tenant: Tenant,
    ) -> None:
        """Request override appears in resolution path."""
        result = resolve_policy(
            request_policy_id="strict",
            app=None,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        assert "request:strict" in result.resolution_path

    def test_request_invalid_policy_id_falls_back(
        self,
        sample_tenant: Tenant,
    ) -> None:
        """Invalid request policy_id falls back to next level."""
        result = resolve_policy(
            request_policy_id="nonexistent_policy",
            app=None,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        # Should fall back to tenant default (balanced)
        assert result.policy.policy_id == "balanced"
        assert result.resolution_source == "tenant"


class TestResolveAppDefault:
    """Tests for app-level default policy (second priority)."""

    def test_app_default_used_when_no_request(
        self,
        sample_tenant: Tenant,
        app_with_balanced: App,
    ) -> None:
        """App default used when no request override."""
        result = resolve_policy(
            request_policy_id=None,
            app=app_with_balanced,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result.policy.policy_id == "balanced"
        assert result.resolution_source == "app"

    def test_app_strict_policy(
        self,
        sample_tenant: Tenant,
        sample_app: App,  # Has default_policy_id="strict"
    ) -> None:
        """App with strict policy applies strict mode."""
        result = resolve_policy(
            request_policy_id=None,
            app=sample_app,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result.policy.policy_id == "strict"
        assert result.resolution_source == "app"

    def test_app_in_resolution_path(
        self,
        sample_tenant: Tenant,
        app_with_balanced: App,
    ) -> None:
        """App appears in resolution path."""
        result = resolve_policy(
            request_policy_id=None,
            app=app_with_balanced,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        assert f"app:{app_with_balanced.app_id}" in result.resolution_path


class TestResolveTenantDefault:
    """Tests for tenant-level default policy (third priority)."""

    def test_tenant_default_used_when_no_app_policy(
        self,
        sample_tenant: Tenant,
        app_without_policy: App,
    ) -> None:
        """Tenant default used when app has no default policy."""
        result = resolve_policy(
            request_policy_id=None,
            app=app_without_policy,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result.policy.policy_id == "balanced"  # sample_tenant default
        assert result.resolution_source == "tenant"

    def test_tenant_default_with_no_app(
        self,
        sample_tenant: Tenant,
    ) -> None:
        """Tenant default used when no app provided."""
        result = resolve_policy(
            request_policy_id=None,
            app=None,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result.policy.policy_id == "balanced"
        assert result.resolution_source == "tenant"

    def test_tenant_monitor_mode(
        self,
        tenant_with_monitor: Tenant,
    ) -> None:
        """Tenant with monitor mode default applies monitor."""
        result = resolve_policy(
            request_policy_id=None,
            app=None,
            tenant=tenant_with_monitor,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result.policy.policy_id == "monitor"
        assert result.resolution_source == "tenant"

    def test_tenant_in_resolution_path(
        self,
        sample_tenant: Tenant,
    ) -> None:
        """Tenant appears in resolution path."""
        result = resolve_policy(
            request_policy_id=None,
            app=None,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        assert f"tenant:{sample_tenant.tenant_id}" in result.resolution_path


class TestResolveSystemDefault:
    """Tests for system default fallback (lowest priority)."""

    def test_system_default_when_no_tenant(self) -> None:
        """System default (balanced) used when no tenant provided."""
        result = resolve_policy(
            request_policy_id=None,
            app=None,
            tenant=None,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result.policy.policy_id == "balanced"
        assert result.resolution_source == "system_default"

    def test_system_default_is_balanced(self) -> None:
        """System default is always balanced mode."""
        result = resolve_policy(
            request_policy_id=None,
            app=None,
            tenant=None,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result.policy.mode == PolicyMode.BALANCED
        assert result.policy.blocking_enabled is True

    def test_system_default_in_resolution_path(self) -> None:
        """System default appears in resolution path."""
        result = resolve_policy(
            request_policy_id=None,
            app=None,
            tenant=None,
            policy_registry=GLOBAL_PRESETS,
        )
        assert "system:balanced" in result.resolution_path


class TestResolutionPath:
    """Tests for resolution path tracking."""

    def test_full_resolution_path_request_override(
        self,
        sample_tenant: Tenant,
        app_with_balanced: App,
    ) -> None:
        """Resolution path shows all levels checked when request overrides."""
        result = resolve_policy(
            request_policy_id="strict",
            app=app_with_balanced,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        # Should show request was used
        assert result.resolution_path[0] == "request:strict"

    def test_full_resolution_path_app_default(
        self,
        sample_tenant: Tenant,
        app_with_balanced: App,
    ) -> None:
        """Resolution path shows levels checked when app default used."""
        result = resolve_policy(
            request_policy_id=None,
            app=app_with_balanced,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        # Should show request was None, then app was used
        assert "request:None" in result.resolution_path
        assert f"app:{app_with_balanced.app_id}" in result.resolution_path

    def test_full_resolution_path_tenant_fallback(
        self,
        sample_tenant: Tenant,
        app_without_policy: App,
    ) -> None:
        """Resolution path shows full chain when falling back to tenant."""
        result = resolve_policy(
            request_policy_id=None,
            app=app_without_policy,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        path = result.resolution_path
        assert "request:None" in path
        assert f"app:{app_without_policy.app_id}" in path
        assert f"tenant:{sample_tenant.tenant_id}" in path


class TestResolveWithCustomRegistry:
    """Tests for custom policy registry support."""

    def test_custom_policy_in_registry(
        self,
        sample_tenant: Tenant,
    ) -> None:
        """Custom policies can be added to registry."""
        custom_policy = TenantPolicy(
            policy_id="custom_strict",
            name="Custom Strict",
            tenant_id="acme",
            mode=PolicyMode.STRICT,
            blocking_enabled=True,
        )
        custom_registry = {**GLOBAL_PRESETS, "custom_strict": custom_policy}

        result = resolve_policy(
            request_policy_id="custom_strict",
            app=None,
            tenant=sample_tenant,
            policy_registry=custom_registry,
        )
        assert result.policy.policy_id == "custom_strict"
        assert result.resolution_source == "request"


class TestResolveReturnType:
    """Tests for PolicyResolutionResult return type."""

    def test_returns_policy_resolution_result(
        self,
        sample_tenant: Tenant,
    ) -> None:
        """resolve_policy returns PolicyResolutionResult."""
        result = resolve_policy(
            request_policy_id=None,
            app=None,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        assert isinstance(result, PolicyResolutionResult)

    def test_result_contains_valid_policy(
        self,
        sample_tenant: Tenant,
    ) -> None:
        """Result contains a valid TenantPolicy."""
        result = resolve_policy(
            request_policy_id=None,
            app=None,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        assert isinstance(result.policy, TenantPolicy)

    def test_result_resolution_source_valid(
        self,
        sample_tenant: Tenant,
    ) -> None:
        """Result has valid resolution_source."""
        result = resolve_policy(
            request_policy_id=None,
            app=None,
            tenant=sample_tenant,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result.resolution_source in {
            "request",
            "app",
            "tenant",
            "partner",
            "system_default",
        }
