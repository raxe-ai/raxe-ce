"""Tests for TenantService application service.

Tests cover:
- Tenant CRUD operations
- Policy CRUD operations
- App CRUD operations
- Policy resolution and explanation
- Error handling and validation
- Factory function
"""

from datetime import datetime

import pytest

from raxe.application.tenant_exceptions import (
    AppNotFoundError,
    DuplicateEntityError,
    ImmutablePresetError,
    PolicyNotFoundError,
    PolicyValidationError,
    TenantNotFoundError,
)
from raxe.application.tenant_service import (
    CreateAppRequest,
    CreatePolicyRequest,
    CreateTenantRequest,
    TenantService,
    UpdatePolicyRequest,
    create_tenant_service,
)
from raxe.domain.tenants.models import PolicyMode


class TestTenantServiceInit:
    """Tests for TenantService initialization."""

    def test_init_with_default_path(self):
        """Service without base_path uses default on access."""
        service = TenantService()
        # base_path is lazily resolved via factory
        assert service._factory is not None

    def test_init_with_custom_path(self, tmp_path):
        """Service with custom base_path uses it directly."""
        service = TenantService(base_path=tmp_path)
        assert service.base_path == tmp_path

    def test_factory_function(self, tmp_path):
        """create_tenant_service returns configured service."""
        service = create_tenant_service(base_path=tmp_path)
        assert isinstance(service, TenantService)
        assert service.base_path == tmp_path


class TestTenantCRUD:
    """Tests for tenant CRUD operations."""

    def test_create_tenant_basic(self, tmp_path):
        """Create tenant with basic parameters."""
        service = TenantService(base_path=tmp_path)

        tenant = service.create_tenant(CreateTenantRequest(name="Acme Corp"))

        assert tenant.tenant_id == "acme-corp"
        assert tenant.name == "Acme Corp"
        assert tenant.default_policy_id == "balanced"
        assert tenant.tier == "free"
        assert tenant.created_at is not None

    def test_create_tenant_with_custom_id(self, tmp_path):
        """Create tenant with explicit tenant_id."""
        service = TenantService(base_path=tmp_path)

        tenant = service.create_tenant(
            CreateTenantRequest(name="Acme Corp", tenant_id="acme-custom")
        )

        assert tenant.tenant_id == "acme-custom"

    def test_create_tenant_with_strict_policy(self, tmp_path):
        """Create tenant with strict default policy."""
        service = TenantService(base_path=tmp_path)

        tenant = service.create_tenant(CreateTenantRequest(name="Bank", default_policy_id="strict"))

        assert tenant.default_policy_id == "strict"

    def test_create_tenant_with_partner(self, tmp_path):
        """Create tenant with partner_id."""
        service = TenantService(base_path=tmp_path)

        tenant = service.create_tenant(
            CreateTenantRequest(name="Customer", partner_id="partner-net")
        )

        assert tenant.partner_id == "partner-net"

    def test_create_tenant_with_tier(self, tmp_path):
        """Create tenant with custom tier."""
        service = TenantService(base_path=tmp_path)

        tenant = service.create_tenant(CreateTenantRequest(name="Enterprise", tier="enterprise"))

        assert tenant.tier == "enterprise"

    def test_create_tenant_duplicate_raises(self, tmp_path):
        """Creating duplicate tenant raises DuplicateEntityError."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Acme"))

        with pytest.raises(DuplicateEntityError) as exc:
            service.create_tenant(CreateTenantRequest(name="Acme"))

        assert exc.value.entity_type == "tenant"
        assert exc.value.entity_id == "acme"

    def test_create_tenant_invalid_policy_raises(self, tmp_path):
        """Creating tenant with invalid policy raises PolicyValidationError."""
        service = TenantService(base_path=tmp_path)

        with pytest.raises(PolicyValidationError) as exc:
            service.create_tenant(CreateTenantRequest(name="Test", default_policy_id="nonexistent"))

        assert "nonexistent" in str(exc.value)

    def test_get_tenant_success(self, tmp_path):
        """Get existing tenant."""
        service = TenantService(base_path=tmp_path)
        created = service.create_tenant(CreateTenantRequest(name="Test"))

        retrieved = service.get_tenant(created.tenant_id)

        assert retrieved.tenant_id == created.tenant_id
        assert retrieved.name == created.name

    def test_get_tenant_not_found_raises(self, tmp_path):
        """Getting non-existent tenant raises TenantNotFoundError."""
        service = TenantService(base_path=tmp_path)

        with pytest.raises(TenantNotFoundError) as exc:
            service.get_tenant("nonexistent")

        assert exc.value.entity_id == "nonexistent"

    def test_list_tenants_empty(self, tmp_path):
        """List tenants when none exist."""
        service = TenantService(base_path=tmp_path)

        tenants = service.list_tenants()

        assert tenants == []

    def test_list_tenants_multiple(self, tmp_path):
        """List multiple tenants sorted by ID."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Zebra"))
        service.create_tenant(CreateTenantRequest(name="Alpha"))
        service.create_tenant(CreateTenantRequest(name="Beta"))

        tenants = service.list_tenants()

        assert len(tenants) == 3
        assert tenants[0].tenant_id == "alpha"
        assert tenants[1].tenant_id == "beta"
        assert tenants[2].tenant_id == "zebra"

    def test_delete_tenant_success(self, tmp_path):
        """Delete existing tenant."""
        service = TenantService(base_path=tmp_path)
        tenant = service.create_tenant(CreateTenantRequest(name="ToDelete"))

        service.delete_tenant(tenant.tenant_id)

        with pytest.raises(TenantNotFoundError):
            service.get_tenant(tenant.tenant_id)

    def test_delete_tenant_not_found_raises(self, tmp_path):
        """Deleting non-existent tenant raises TenantNotFoundError."""
        service = TenantService(base_path=tmp_path)

        with pytest.raises(TenantNotFoundError):
            service.delete_tenant("nonexistent")

    def test_set_tenant_policy_success(self, tmp_path):
        """Set tenant default policy."""
        service = TenantService(base_path=tmp_path)
        tenant = service.create_tenant(CreateTenantRequest(name="Test"))
        assert tenant.default_policy_id == "balanced"

        updated = service.set_tenant_policy(tenant.tenant_id, "strict")

        assert updated.default_policy_id == "strict"

    def test_set_tenant_policy_not_found_raises(self, tmp_path):
        """Setting policy on non-existent tenant raises TenantNotFoundError."""
        service = TenantService(base_path=tmp_path)

        with pytest.raises(TenantNotFoundError):
            service.set_tenant_policy("nonexistent", "strict")

    def test_set_tenant_policy_invalid_raises(self, tmp_path):
        """Setting invalid policy raises PolicyNotFoundError."""
        service = TenantService(base_path=tmp_path)
        tenant = service.create_tenant(CreateTenantRequest(name="Test"))

        with pytest.raises(PolicyNotFoundError):
            service.set_tenant_policy(tenant.tenant_id, "nonexistent-policy")


class TestPolicyCRUD:
    """Tests for policy CRUD operations."""

    def test_create_policy_basic(self, tmp_path):
        """Create policy with basic parameters."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        policy = service.create_policy(
            CreatePolicyRequest(tenant_id="test", name="Custom Strict", mode="strict")
        )

        assert policy.policy_id == "custom-strict"
        assert policy.name == "Custom Strict"
        assert policy.tenant_id == "test"
        assert policy.mode == PolicyMode.STRICT
        assert policy.version == 1
        assert policy.created_at is not None

    def test_create_policy_custom_mode(self, tmp_path):
        """Create policy with custom mode and thresholds."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        policy = service.create_policy(
            CreatePolicyRequest(
                tenant_id="test",
                name="Custom",
                mode="custom",
                blocking_enabled=True,
                block_severity_threshold="MEDIUM",
                block_confidence_threshold=0.7,
                l2_enabled=False,
            )
        )

        assert policy.mode == PolicyMode.CUSTOM
        assert policy.blocking_enabled is True
        assert policy.block_severity_threshold == "MEDIUM"
        assert policy.block_confidence_threshold == 0.7
        assert policy.l2_enabled is False

    def test_create_policy_preset_mode_ignores_thresholds(self, tmp_path):
        """Preset modes ignore provided thresholds and use preset values."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        policy = service.create_policy(
            CreatePolicyRequest(
                tenant_id="test",
                name="My Monitor",
                mode="monitor",
                blocking_enabled=True,  # Should be ignored
            )
        )

        # Monitor mode should have blocking=False regardless
        assert policy.mode == PolicyMode.MONITOR
        assert policy.blocking_enabled is False

    def test_create_policy_tenant_not_found(self, tmp_path):
        """Creating policy for non-existent tenant raises TenantNotFoundError."""
        service = TenantService(base_path=tmp_path)

        with pytest.raises(TenantNotFoundError):
            service.create_policy(
                CreatePolicyRequest(tenant_id="nonexistent", name="Test", mode="balanced")
            )

    def test_create_policy_duplicate_raises(self, tmp_path):
        """Creating duplicate policy raises DuplicateEntityError."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        service.create_policy(CreatePolicyRequest(tenant_id="test", name="Custom", mode="strict"))

        with pytest.raises(DuplicateEntityError) as exc:
            service.create_policy(
                CreatePolicyRequest(tenant_id="test", name="Custom", mode="balanced")
            )

        assert exc.value.entity_type == "policy"
        assert exc.value.tenant_id == "test"

    def test_create_policy_invalid_mode_raises(self, tmp_path):
        """Creating policy with invalid mode raises PolicyValidationError."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        with pytest.raises(PolicyValidationError) as exc:
            service.create_policy(
                CreatePolicyRequest(tenant_id="test", name="Test", mode="invalid")
            )

        assert "invalid" in str(exc.value).lower()

    def test_get_policy_global_preset(self, tmp_path):
        """Get global preset policy."""
        service = TenantService(base_path=tmp_path)

        policy = service.get_policy("balanced")

        assert policy.policy_id == "balanced"
        assert policy.tenant_id is None  # Global preset

    def test_get_policy_tenant_specific(self, tmp_path):
        """Get tenant-specific policy."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        created = service.create_policy(
            CreatePolicyRequest(tenant_id="test", name="Custom", mode="strict")
        )

        policy = service.get_policy("custom", tenant_id="test")

        assert policy.policy_id == created.policy_id

    def test_get_policy_not_found_raises(self, tmp_path):
        """Getting non-existent policy raises PolicyNotFoundError."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        with pytest.raises(PolicyNotFoundError):
            service.get_policy("nonexistent", tenant_id="test")

    def test_list_policies_global_only(self, tmp_path):
        """List policies without tenant returns global presets."""
        service = TenantService(base_path=tmp_path)

        policies = service.list_policies()

        policy_ids = [p.policy_id for p in policies]
        assert "monitor" in policy_ids
        assert "balanced" in policy_ids
        assert "strict" in policy_ids

    def test_list_policies_with_tenant(self, tmp_path):
        """List policies with tenant includes tenant-specific."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        service.create_policy(CreatePolicyRequest(tenant_id="test", name="Custom", mode="strict"))

        policies = service.list_policies(tenant_id="test")

        policy_ids = [p.policy_id for p in policies]
        assert "monitor" in policy_ids
        assert "balanced" in policy_ids
        assert "strict" in policy_ids
        assert "custom" in policy_ids

    def test_list_policies_tenant_not_found_raises(self, tmp_path):
        """Listing policies for non-existent tenant raises TenantNotFoundError."""
        service = TenantService(base_path=tmp_path)

        with pytest.raises(TenantNotFoundError):
            service.list_policies(tenant_id="nonexistent")

    def test_update_policy_success(self, tmp_path):
        """Update existing policy."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        service.create_policy(CreatePolicyRequest(tenant_id="test", name="Custom", mode="balanced"))

        updated = service.update_policy(
            UpdatePolicyRequest(policy_id="custom", tenant_id="test", name="Custom Updated")
        )

        assert updated.name == "Custom Updated"
        assert updated.version == 2

    def test_update_policy_threshold_changes_to_custom_mode(self, tmp_path):
        """Updating thresholds changes mode to custom."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        original = service.create_policy(
            CreatePolicyRequest(tenant_id="test", name="Test", mode="balanced")
        )
        assert original.mode == PolicyMode.BALANCED

        updated = service.update_policy(
            UpdatePolicyRequest(
                policy_id="test",
                tenant_id="test",
                block_confidence_threshold=0.5,
            )
        )

        assert updated.mode == PolicyMode.CUSTOM
        assert updated.block_confidence_threshold == 0.5

    def test_update_policy_global_preset_raises(self, tmp_path):
        """Updating global preset raises ImmutablePresetError."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        with pytest.raises(ImmutablePresetError) as exc:
            service.update_policy(
                UpdatePolicyRequest(policy_id="balanced", tenant_id="test", name="Changed")
            )

        assert exc.value.preset_id == "balanced"
        assert exc.value.operation == "update"

    def test_delete_policy_success(self, tmp_path):
        """Delete existing policy."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        service.create_policy(CreatePolicyRequest(tenant_id="test", name="ToDelete", mode="strict"))

        service.delete_policy("todelete", tenant_id="test")

        with pytest.raises(PolicyNotFoundError):
            service.get_policy("todelete", tenant_id="test")

    def test_delete_policy_global_preset_raises(self, tmp_path):
        """Deleting global preset raises ImmutablePresetError."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        with pytest.raises(ImmutablePresetError) as exc:
            service.delete_policy("strict", tenant_id="test")

        assert exc.value.operation == "delete"


class TestAppCRUD:
    """Tests for app CRUD operations."""

    def test_create_app_basic(self, tmp_path):
        """Create app with basic parameters."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        app = service.create_app(CreateAppRequest(tenant_id="test", name="Customer Chatbot"))

        assert app.app_id == "customer-chatbot"
        assert app.name == "Customer Chatbot"
        assert app.tenant_id == "test"
        assert app.default_policy_id is None  # Inherit from tenant
        assert app.created_at is not None

    def test_create_app_with_policy(self, tmp_path):
        """Create app with explicit policy."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        app = service.create_app(
            CreateAppRequest(tenant_id="test", name="Secure Bot", default_policy_id="strict")
        )

        assert app.default_policy_id == "strict"

    def test_create_app_tenant_not_found_raises(self, tmp_path):
        """Creating app for non-existent tenant raises TenantNotFoundError."""
        service = TenantService(base_path=tmp_path)

        with pytest.raises(TenantNotFoundError):
            service.create_app(CreateAppRequest(tenant_id="nonexistent", name="Bot"))

    def test_create_app_duplicate_raises(self, tmp_path):
        """Creating duplicate app raises DuplicateEntityError."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        service.create_app(CreateAppRequest(tenant_id="test", name="Bot"))

        with pytest.raises(DuplicateEntityError) as exc:
            service.create_app(CreateAppRequest(tenant_id="test", name="Bot"))

        assert exc.value.entity_type == "app"

    def test_create_app_invalid_policy_raises(self, tmp_path):
        """Creating app with invalid policy raises PolicyNotFoundError."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        with pytest.raises(PolicyNotFoundError):
            service.create_app(
                CreateAppRequest(tenant_id="test", name="Bot", default_policy_id="nonexistent")
            )

    def test_get_app_success(self, tmp_path):
        """Get existing app."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        created = service.create_app(CreateAppRequest(tenant_id="test", name="Bot"))

        app = service.get_app("bot", tenant_id="test")

        assert app.app_id == created.app_id

    def test_get_app_tenant_not_found_raises(self, tmp_path):
        """Getting app from non-existent tenant raises TenantNotFoundError."""
        service = TenantService(base_path=tmp_path)

        with pytest.raises(TenantNotFoundError):
            service.get_app("bot", tenant_id="nonexistent")

    def test_get_app_not_found_raises(self, tmp_path):
        """Getting non-existent app raises AppNotFoundError."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        with pytest.raises(AppNotFoundError):
            service.get_app("nonexistent", tenant_id="test")

    def test_list_apps_empty(self, tmp_path):
        """List apps when none exist."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        apps = service.list_apps(tenant_id="test")

        assert apps == []

    def test_list_apps_multiple_sorted(self, tmp_path):
        """List multiple apps sorted by ID."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        service.create_app(CreateAppRequest(tenant_id="test", name="Zebra App"))
        service.create_app(CreateAppRequest(tenant_id="test", name="Alpha App"))

        apps = service.list_apps(tenant_id="test")

        assert len(apps) == 2
        assert apps[0].app_id == "alpha-app"
        assert apps[1].app_id == "zebra-app"

    def test_delete_app_success(self, tmp_path):
        """Delete existing app."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        service.create_app(CreateAppRequest(tenant_id="test", name="ToDelete"))

        service.delete_app("todelete", tenant_id="test")

        with pytest.raises(AppNotFoundError):
            service.get_app("todelete", tenant_id="test")

    def test_delete_app_not_found_raises(self, tmp_path):
        """Deleting non-existent app raises AppNotFoundError."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        with pytest.raises(AppNotFoundError):
            service.delete_app("nonexistent", tenant_id="test")

    def test_set_app_policy_success(self, tmp_path):
        """Set app policy override."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        service.create_app(CreateAppRequest(tenant_id="test", name="Bot"))

        updated = service.set_app_policy("bot", "test", "strict")

        assert updated.default_policy_id == "strict"

    def test_set_app_policy_clear(self, tmp_path):
        """Clear app policy to inherit from tenant."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        service.create_app(
            CreateAppRequest(tenant_id="test", name="Bot", default_policy_id="strict")
        )

        updated = service.set_app_policy("bot", "test", None)

        assert updated.default_policy_id is None

    def test_set_app_policy_invalid_raises(self, tmp_path):
        """Setting invalid policy raises PolicyNotFoundError."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        service.create_app(CreateAppRequest(tenant_id="test", name="Bot"))

        with pytest.raises(PolicyNotFoundError):
            service.set_app_policy("bot", "test", "nonexistent")


class TestPolicyExplanation:
    """Tests for policy resolution and explanation."""

    def test_explain_tenant_default(self, tmp_path):
        """Explain policy resolves to tenant default."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test", default_policy_id="strict"))

        result = service.explain_policy(tenant_id="test")

        assert result.policy.policy_id == "strict"
        assert result.resolution_source == "tenant"

    def test_explain_app_override(self, tmp_path):
        """Explain policy with app override."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        service.create_app(
            CreateAppRequest(tenant_id="test", name="Bot", default_policy_id="strict")
        )

        result = service.explain_policy(tenant_id="test", app_id="bot")

        assert result.policy.policy_id == "strict"
        assert result.resolution_source == "app"

    def test_explain_request_override(self, tmp_path):
        """Explain policy with request override."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        result = service.explain_policy(tenant_id="test", policy_id="monitor")

        assert result.policy.policy_id == "monitor"
        assert result.resolution_source == "request"

    def test_explain_resolution_path_tracked(self, tmp_path):
        """Resolution path tracks full chain."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        service.create_app(CreateAppRequest(tenant_id="test", name="Bot"))

        result = service.explain_policy(tenant_id="test", app_id="bot")

        assert isinstance(result.resolution_path, list)
        assert len(result.resolution_path) > 0

    def test_explain_tenant_not_found_raises(self, tmp_path):
        """Explaining policy for non-existent tenant raises TenantNotFoundError."""
        service = TenantService(base_path=tmp_path)

        with pytest.raises(TenantNotFoundError):
            service.explain_policy(tenant_id="nonexistent")

    def test_explain_app_not_found_raises(self, tmp_path):
        """Explaining policy for non-existent app raises AppNotFoundError."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        with pytest.raises(AppNotFoundError):
            service.explain_policy(tenant_id="test", app_id="nonexistent")


class TestSlugGeneration:
    """Tests for automatic slug/ID generation."""

    def test_tenant_id_from_name(self, tmp_path):
        """Tenant ID auto-generated from name."""
        service = TenantService(base_path=tmp_path)

        tenant = service.create_tenant(CreateTenantRequest(name="Acme Corporation"))

        assert tenant.tenant_id == "acme-corporation"

    def test_policy_id_from_name(self, tmp_path):
        """Policy ID auto-generated from name."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        policy = service.create_policy(
            CreatePolicyRequest(tenant_id="test", name="My Strict Policy", mode="strict")
        )

        assert policy.policy_id == "my-strict-policy"

    def test_app_id_from_name(self, tmp_path):
        """App ID auto-generated from name."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        app = service.create_app(CreateAppRequest(tenant_id="test", name="Customer Support Bot"))

        assert app.app_id == "customer-support-bot"

    def test_explicit_id_overrides_generated(self, tmp_path):
        """Explicit ID overrides auto-generation."""
        service = TenantService(base_path=tmp_path)

        tenant = service.create_tenant(
            CreateTenantRequest(name="Long Name Here", tenant_id="short")
        )

        assert tenant.tenant_id == "short"


class TestTimestampHandling:
    """Tests for timestamp generation."""

    def test_tenant_created_at_populated(self, tmp_path):
        """Tenant created_at is populated."""
        service = TenantService(base_path=tmp_path)

        tenant = service.create_tenant(CreateTenantRequest(name="Test"))

        assert tenant.created_at is not None
        # Verify it's a valid ISO format timestamp
        datetime.fromisoformat(tenant.created_at.replace("Z", "+00:00"))

    def test_policy_timestamps_populated(self, tmp_path):
        """Policy created_at and updated_at are populated."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        policy = service.create_policy(
            CreatePolicyRequest(tenant_id="test", name="Test", mode="balanced")
        )

        assert policy.created_at is not None
        assert policy.updated_at is not None

    def test_policy_updated_at_changes_on_update(self, tmp_path):
        """Policy updated_at changes after update."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))
        original = service.create_policy(
            CreatePolicyRequest(tenant_id="test", name="Test", mode="balanced")
        )

        # Small delay to ensure different timestamp
        import time

        time.sleep(0.01)

        updated = service.update_policy(
            UpdatePolicyRequest(policy_id="test", tenant_id="test", name="Test Updated")
        )

        assert updated.created_at == original.created_at
        assert updated.updated_at != original.updated_at

    def test_app_created_at_populated(self, tmp_path):
        """App created_at is populated."""
        service = TenantService(base_path=tmp_path)
        service.create_tenant(CreateTenantRequest(name="Test"))

        app = service.create_app(CreateAppRequest(tenant_id="test", name="Bot"))

        assert app.created_at is not None
