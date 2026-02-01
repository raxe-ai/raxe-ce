"""Tests for tenant domain models.

TDD: These tests are written BEFORE implementation.
"""

from dataclasses import FrozenInstanceError

import pytest

from raxe.domain.tenants.models import (
    App,
    PolicyMode,
    PolicyResolutionResult,
    Tenant,
    TenantPolicy,
)


class TestPolicyMode:
    """Tests for PolicyMode enum."""

    def test_policy_mode_values(self) -> None:
        """PolicyMode enum has correct string values."""
        assert PolicyMode.MONITOR.value == "monitor"
        assert PolicyMode.BALANCED.value == "balanced"
        assert PolicyMode.STRICT.value == "strict"
        assert PolicyMode.CUSTOM.value == "custom"

    def test_policy_mode_from_string(self) -> None:
        """PolicyMode can be created from string value."""
        assert PolicyMode("monitor") == PolicyMode.MONITOR
        assert PolicyMode("balanced") == PolicyMode.BALANCED
        assert PolicyMode("strict") == PolicyMode.STRICT

    def test_policy_mode_invalid_raises(self) -> None:
        """Invalid mode string raises ValueError."""
        with pytest.raises(ValueError):
            PolicyMode("invalid_mode")


class TestTenantPolicy:
    """Tests for TenantPolicy dataclass."""

    def test_tenant_policy_creation(self) -> None:
        """TenantPolicy can be created with required fields."""
        policy = TenantPolicy(
            policy_id="test_pol",
            name="Test Policy",
            tenant_id="acme",
            mode=PolicyMode.BALANCED,
            blocking_enabled=True,
        )
        assert policy.policy_id == "test_pol"
        assert policy.name == "Test Policy"
        assert policy.tenant_id == "acme"
        assert policy.mode == PolicyMode.BALANCED
        assert policy.blocking_enabled is True

    def test_tenant_policy_defaults(self) -> None:
        """TenantPolicy has correct default values."""
        policy = TenantPolicy(
            policy_id="test",
            name="Test",
            tenant_id="acme",
            mode=PolicyMode.BALANCED,
            blocking_enabled=True,
        )
        assert policy.block_severity_threshold == "HIGH"
        assert policy.block_confidence_threshold == 0.85
        assert policy.l2_enabled is True
        assert policy.l2_threat_threshold == 0.35
        assert policy.telemetry_detail == "standard"

    def test_tenant_policy_validation_empty_id(self) -> None:
        """Empty policy_id raises ValueError."""
        with pytest.raises(ValueError, match="policy_id cannot be empty"):
            TenantPolicy(
                policy_id="",
                name="Test",
                tenant_id="acme",
                mode=PolicyMode.BALANCED,
                blocking_enabled=True,
            )

    def test_tenant_policy_validation_empty_name(self) -> None:
        """Empty name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            TenantPolicy(
                policy_id="test",
                name="",
                tenant_id="acme",
                mode=PolicyMode.BALANCED,
                blocking_enabled=True,
            )

    def test_tenant_policy_confidence_bounds_high(self) -> None:
        """Confidence threshold > 1 raises ValueError."""
        with pytest.raises(ValueError, match="block_confidence_threshold must be 0-1"):
            TenantPolicy(
                policy_id="test",
                name="Test",
                tenant_id="acme",
                mode=PolicyMode.BALANCED,
                blocking_enabled=True,
                block_confidence_threshold=1.5,
            )

    def test_tenant_policy_confidence_bounds_low(self) -> None:
        """Confidence threshold < 0 raises ValueError."""
        with pytest.raises(ValueError, match="block_confidence_threshold must be 0-1"):
            TenantPolicy(
                policy_id="test",
                name="Test",
                tenant_id="acme",
                mode=PolicyMode.BALANCED,
                blocking_enabled=True,
                block_confidence_threshold=-0.1,
            )

    def test_tenant_policy_confidence_bounds_valid(self) -> None:
        """Valid confidence thresholds (0, 0.5, 1) are accepted."""
        for threshold in [0.0, 0.5, 1.0]:
            policy = TenantPolicy(
                policy_id="test",
                name="Test",
                tenant_id="acme",
                mode=PolicyMode.BALANCED,
                blocking_enabled=True,
                block_confidence_threshold=threshold,
            )
            assert policy.block_confidence_threshold == threshold

    def test_tenant_policy_l2_threshold_bounds(self) -> None:
        """L2 threshold validation."""
        with pytest.raises(ValueError, match="l2_threat_threshold must be 0-1"):
            TenantPolicy(
                policy_id="test",
                name="Test",
                tenant_id="acme",
                mode=PolicyMode.BALANCED,
                blocking_enabled=True,
                l2_threat_threshold=1.5,
            )

    def test_tenant_policy_immutable(self) -> None:
        """TenantPolicy is immutable (frozen)."""
        policy = TenantPolicy(
            policy_id="test",
            name="Test",
            tenant_id="acme",
            mode=PolicyMode.BALANCED,
            blocking_enabled=True,
        )
        with pytest.raises(FrozenInstanceError):
            policy.name = "Changed"  # type: ignore[misc]

    def test_tenant_policy_global_preset_has_none_tenant_id(self) -> None:
        """Global presets have tenant_id=None."""
        policy = TenantPolicy(
            policy_id="balanced",
            name="Balanced Mode",
            tenant_id=None,  # Global preset
            mode=PolicyMode.BALANCED,
            blocking_enabled=True,
        )
        assert policy.tenant_id is None

    def test_tenant_policy_severity_threshold_validation(self) -> None:
        """Invalid severity threshold raises ValueError."""
        with pytest.raises(ValueError, match="block_severity_threshold must be"):
            TenantPolicy(
                policy_id="test",
                name="Test",
                tenant_id="acme",
                mode=PolicyMode.BALANCED,
                blocking_enabled=True,
                block_severity_threshold="INVALID",
            )

    def test_tenant_policy_valid_severity_thresholds(self) -> None:
        """Valid severity thresholds are accepted."""
        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            policy = TenantPolicy(
                policy_id="test",
                name="Test",
                tenant_id="acme",
                mode=PolicyMode.BALANCED,
                blocking_enabled=True,
                block_severity_threshold=severity,
            )
            assert policy.block_severity_threshold == severity

    def test_tenant_policy_telemetry_detail_validation(self) -> None:
        """Invalid telemetry detail raises ValueError."""
        with pytest.raises(ValueError, match="telemetry_detail must be"):
            TenantPolicy(
                policy_id="test",
                name="Test",
                tenant_id="acme",
                mode=PolicyMode.BALANCED,
                blocking_enabled=True,
                telemetry_detail="invalid",
            )


class TestTenant:
    """Tests for Tenant dataclass."""

    def test_tenant_creation(self) -> None:
        """Tenant can be created with required fields."""
        tenant = Tenant(
            tenant_id="acme",
            name="Acme Corp",
            default_policy_id="balanced",
        )
        assert tenant.tenant_id == "acme"
        assert tenant.name == "Acme Corp"
        assert tenant.default_policy_id == "balanced"

    def test_tenant_defaults(self) -> None:
        """Tenant has correct default values."""
        tenant = Tenant(
            tenant_id="acme",
            name="Acme Corp",
            default_policy_id="balanced",
        )
        assert tenant.partner_id is None
        assert tenant.tier == "free"
        assert tenant.created_at is None

    def test_tenant_validation_empty_id(self) -> None:
        """Empty tenant_id raises ValueError."""
        with pytest.raises(ValueError, match="tenant_id cannot be empty"):
            Tenant(
                tenant_id="",
                name="Acme Corp",
                default_policy_id="balanced",
            )

    def test_tenant_validation_empty_name(self) -> None:
        """Empty name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            Tenant(
                tenant_id="acme",
                name="",
                default_policy_id="balanced",
            )

    def test_tenant_validation_empty_policy_id(self) -> None:
        """Empty default_policy_id raises ValueError."""
        with pytest.raises(ValueError, match="default_policy_id cannot be empty"):
            Tenant(
                tenant_id="acme",
                name="Acme Corp",
                default_policy_id="",
            )

    def test_tenant_immutable(self) -> None:
        """Tenant is immutable (frozen)."""
        tenant = Tenant(
            tenant_id="acme",
            name="Acme Corp",
            default_policy_id="balanced",
        )
        with pytest.raises(FrozenInstanceError):
            tenant.name = "Changed"  # type: ignore[misc]

    def test_tenant_tier_validation(self) -> None:
        """Invalid tier raises ValueError."""
        with pytest.raises(ValueError, match="tier must be"):
            Tenant(
                tenant_id="acme",
                name="Acme Corp",
                default_policy_id="balanced",
                tier="invalid_tier",
            )

    def test_tenant_valid_tiers(self) -> None:
        """Valid tiers are accepted."""
        for tier in ["free", "pro", "enterprise"]:
            tenant = Tenant(
                tenant_id="acme",
                name="Acme Corp",
                default_policy_id="balanced",
                tier=tier,
            )
            assert tenant.tier == tier

    def test_tenant_with_partner(self) -> None:
        """Tenant can have partner_id for B2B2C model."""
        tenant = Tenant(
            tenant_id="customer_123",
            name="Customer 123",
            default_policy_id="balanced",
            partner_id="partner_net",
        )
        assert tenant.partner_id == "partner_net"


class TestApp:
    """Tests for App dataclass."""

    def test_app_creation(self) -> None:
        """App can be created with required fields."""
        app = App(
            app_id="chatbot",
            tenant_id="acme",
            name="Customer Support Bot",
        )
        assert app.app_id == "chatbot"
        assert app.tenant_id == "acme"
        assert app.name == "Customer Support Bot"

    def test_app_defaults(self) -> None:
        """App has correct default values."""
        app = App(
            app_id="chatbot",
            tenant_id="acme",
            name="Bot",
        )
        assert app.default_policy_id is None  # Inherits from tenant
        assert app.created_at is None

    def test_app_validation_empty_app_id(self) -> None:
        """Empty app_id raises ValueError."""
        with pytest.raises(ValueError, match="app_id cannot be empty"):
            App(
                app_id="",
                tenant_id="acme",
                name="Bot",
            )

    def test_app_validation_empty_tenant_id(self) -> None:
        """Empty tenant_id raises ValueError."""
        with pytest.raises(ValueError, match="tenant_id cannot be empty"):
            App(
                app_id="chatbot",
                tenant_id="",
                name="Bot",
            )

    def test_app_validation_empty_name(self) -> None:
        """Empty name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            App(
                app_id="chatbot",
                tenant_id="acme",
                name="",
            )

    def test_app_immutable(self) -> None:
        """App is immutable (frozen)."""
        app = App(
            app_id="chatbot",
            tenant_id="acme",
            name="Bot",
        )
        with pytest.raises(FrozenInstanceError):
            app.name = "Changed"  # type: ignore[misc]

    def test_app_with_default_policy(self) -> None:
        """App can override tenant's default policy."""
        app = App(
            app_id="secure_app",
            tenant_id="acme",
            name="Secure App",
            default_policy_id="strict",
        )
        assert app.default_policy_id == "strict"


class TestPolicyResolutionResult:
    """Tests for PolicyResolutionResult dataclass."""

    def test_resolution_result_creation(self, sample_tenant_policy: TenantPolicy) -> None:
        """PolicyResolutionResult can be created."""
        result = PolicyResolutionResult(
            policy=sample_tenant_policy,
            resolution_source="tenant",
            resolution_path=["request:None", "app:chatbot", "tenant:acme"],
        )
        assert result.policy == sample_tenant_policy
        assert result.resolution_source == "tenant"
        assert len(result.resolution_path) == 3

    def test_resolution_result_immutable(self, sample_tenant_policy: TenantPolicy) -> None:
        """PolicyResolutionResult is immutable."""
        result = PolicyResolutionResult(
            policy=sample_tenant_policy,
            resolution_source="tenant",
            resolution_path=["tenant:acme"],
        )
        with pytest.raises(FrozenInstanceError):
            result.resolution_source = "app"  # type: ignore[misc]

    def test_resolution_source_validation(self, sample_tenant_policy: TenantPolicy) -> None:
        """Invalid resolution_source raises ValueError."""
        with pytest.raises(ValueError, match="resolution_source must be"):
            PolicyResolutionResult(
                policy=sample_tenant_policy,
                resolution_source="invalid_source",
                resolution_path=["tenant:acme"],
            )

    def test_resolution_source_valid_values(self, sample_tenant_policy: TenantPolicy) -> None:
        """Valid resolution sources are accepted."""
        for source in ["request", "app", "tenant", "partner", "system_default"]:
            result = PolicyResolutionResult(
                policy=sample_tenant_policy,
                resolution_source=source,
                resolution_path=["test"],
            )
            assert result.resolution_source == source
