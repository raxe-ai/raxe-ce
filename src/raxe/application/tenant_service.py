"""Application service for tenant management.

Orchestrates tenant, policy, and app operations:
- Business logic validation (slug generation, timestamps, uniqueness)
- Repository coordination via RepositoryFactory
- Domain model creation with proper defaults
- Error handling with typed exceptions

This service is the single point of entry for all tenant management
operations. CLI and SDK consumers should use this service rather than
directly accessing repositories.

CRITICAL: This is application layer - orchestrates but doesn't contain
business logic. All pure logic in domain layer, all I/O through repositories.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from raxe.domain.tenants.models import App, PolicyMode, PolicyResolutionResult, Tenant, TenantPolicy
from raxe.domain.tenants.presets import GLOBAL_PRESETS
from raxe.domain.tenants.resolver import resolve_policy
from raxe.infrastructure.tenants.factory import RepositoryFactory
from raxe.infrastructure.tenants.utils import build_policy_registry, get_available_policies, slugify

from .tenant_exceptions import (
    AppNotFoundError,
    DuplicateEntityError,
    ImmutablePresetError,
    PolicyNotFoundError,
    PolicyValidationError,
    TenantNotFoundError,
)

if TYPE_CHECKING:
    from raxe.infrastructure.tenants.yaml_repository import (
        YamlAppRepository,
        YamlPolicyRepository,
        YamlTenantRepository,
    )

logger = logging.getLogger(__name__)


# =============================================================================
# Data Transfer Objects
# =============================================================================


@dataclass
class CreateTenantRequest:
    """Request DTO for creating a tenant.

    Attributes:
        name: Human-readable tenant name (required).
        tenant_id: Optional ID (auto-generated from name if not provided).
        default_policy_id: Default policy (default: "balanced").
        tier: Subscription tier (default: "free").
        partner_id: Optional partner ID for B2B2C model.
    """

    name: str
    tenant_id: str | None = None
    default_policy_id: str = "balanced"
    tier: str = "free"
    partner_id: str | None = None


@dataclass
class CreatePolicyRequest:
    """Request DTO for creating a policy.

    For mode="custom", threshold options are used.
    For preset modes, threshold options are ignored and preset values used.

    Attributes:
        tenant_id: Owner tenant ID (required).
        name: Human-readable policy name (required).
        mode: Policy mode (monitor/balanced/strict/custom).
        policy_id: Optional ID (auto-generated from name if not provided).
        blocking_enabled: Override blocking (custom mode only).
        block_severity_threshold: Severity threshold (custom mode only).
        block_confidence_threshold: Confidence threshold (custom mode only).
        l2_enabled: L2 ML detection enabled (custom mode only).
        l2_threat_threshold: L2 threat threshold (custom mode only).
        telemetry_detail: Telemetry detail level (custom mode only).
    """

    tenant_id: str
    name: str
    mode: str  # Will be converted to PolicyMode
    policy_id: str | None = None
    blocking_enabled: bool | None = None
    block_severity_threshold: str | None = None
    block_confidence_threshold: float | None = None
    l2_enabled: bool | None = None
    l2_threat_threshold: float | None = None
    telemetry_detail: str | None = None


@dataclass
class UpdatePolicyRequest:
    """Request DTO for updating a policy.

    Only non-None fields are updated. Any threshold update changes mode to custom.

    Attributes:
        policy_id: Policy to update (required).
        tenant_id: Owner tenant ID (required).
        name: New policy name (optional).
        blocking_enabled: New blocking setting (optional).
        block_severity_threshold: New severity threshold (optional).
        block_confidence_threshold: New confidence threshold (optional).
        l2_enabled: New L2 setting (optional).
        l2_threat_threshold: New L2 threshold (optional).
        telemetry_detail: New telemetry level (optional).
    """

    policy_id: str
    tenant_id: str
    name: str | None = None
    blocking_enabled: bool | None = None
    block_severity_threshold: str | None = None
    block_confidence_threshold: float | None = None
    l2_enabled: bool | None = None
    l2_threat_threshold: float | None = None
    telemetry_detail: str | None = None


@dataclass
class CreateAppRequest:
    """Request DTO for creating an app.

    Attributes:
        tenant_id: Owner tenant ID (required).
        name: Human-readable app name (required).
        app_id: Optional ID (auto-generated from name if not provided).
        default_policy_id: Policy override (optional, inherits from tenant if None).
    """

    tenant_id: str
    name: str
    app_id: str | None = None
    default_policy_id: str | None = None


# =============================================================================
# TenantService
# =============================================================================


class TenantService:
    """Application service for tenant management.

    Coordinates tenant, policy, and app operations through the application layer.
    Uses RepositoryFactory for repository access, ensuring consistent base paths.

    This service:
    - Validates business rules (uniqueness, existence, immutability)
    - Generates IDs from names using slugify
    - Handles timestamps (created_at, updated_at)
    - Delegates persistence to repositories
    - Raises typed exceptions for error handling

    Example:
        >>> service = TenantService()
        >>> tenant = service.create_tenant(CreateTenantRequest(name="Acme Corp"))
        >>> print(f"Created tenant: {tenant.tenant_id}")

        >>> # With custom base path (testing)
        >>> service = TenantService(base_path=tmp_path)
    """

    def __init__(self, base_path: Path | None = None) -> None:
        """Initialize service with repository factory.

        Args:
            base_path: Override base path for tenant storage.
                If None, uses default from get_tenants_base_path().
                Use this for testing with isolated directories.
        """
        self._factory = RepositoryFactory(base_path)

    @property
    def base_path(self) -> Path:
        """Get the resolved base path for tenant storage."""
        return self._factory.base_path

    # =========================================================================
    # Repository Access (internal)
    # =========================================================================

    def _get_tenant_repo(self) -> YamlTenantRepository:
        """Get tenant repository."""
        return self._factory.get_tenant_repo()

    def _get_policy_repo(self) -> YamlPolicyRepository:
        """Get policy repository."""
        repo = self._factory.get_policy_repo()
        return repo  # type: ignore[return-value]  # Factory returns base type

    def _get_app_repo(self) -> YamlAppRepository:
        """Get app repository."""
        return self._factory.get_app_repo()

    def _get_timestamp(self) -> str:
        """Get current UTC timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    # =========================================================================
    # Tenant Operations
    # =========================================================================

    def create_tenant(self, request: CreateTenantRequest) -> Tenant:
        """Create a new tenant.

        Args:
            request: Tenant creation parameters.

        Returns:
            Created Tenant domain object.

        Raises:
            DuplicateEntityError: If tenant_id already exists.
            PolicyValidationError: If default_policy_id is invalid.

        Example:
            >>> service = TenantService()
            >>> tenant = service.create_tenant(
            ...     CreateTenantRequest(name="Acme Corp", default_policy_id="strict")
            ... )
            >>> print(tenant.tenant_id)  # "acme-corp"
        """
        repo = self._get_tenant_repo()

        # Generate tenant_id if not provided
        tenant_id = request.tenant_id or slugify(request.name, fallback="tenant")

        # Check for duplicates
        existing = repo.get_tenant(tenant_id)
        if existing:
            raise DuplicateEntityError("tenant", tenant_id)

        # Validate default_policy_id exists (global preset only for new tenants)
        if request.default_policy_id not in GLOBAL_PRESETS:
            valid_policies = list(GLOBAL_PRESETS.keys())
            raise PolicyValidationError(
                f"Invalid default policy '{request.default_policy_id}'",
                policy_id=request.default_policy_id,
                constraint=f"must be one of {valid_policies}",
            )

        # Create tenant domain object
        tenant = Tenant(
            tenant_id=tenant_id,
            name=request.name,
            default_policy_id=request.default_policy_id,
            partner_id=request.partner_id,
            tier=request.tier,
            created_at=self._get_timestamp(),
        )

        # Persist
        repo.save_tenant(tenant)

        logger.info(f"Created tenant: {tenant_id}")
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant:
        """Get a tenant by ID.

        Args:
            tenant_id: Tenant identifier.

        Returns:
            Tenant domain object.

        Raises:
            TenantNotFoundError: If tenant does not exist.
        """
        repo = self._get_tenant_repo()
        tenant = repo.get_tenant(tenant_id)

        if not tenant:
            raise TenantNotFoundError(tenant_id)

        return tenant

    def list_tenants(self) -> list[Tenant]:
        """List all tenants.

        Returns:
            List of Tenant domain objects, sorted by tenant_id.
        """
        repo = self._get_tenant_repo()
        tenants = repo.list_tenants()
        return sorted(tenants, key=lambda t: t.tenant_id)

    def delete_tenant(self, tenant_id: str) -> None:
        """Delete a tenant and all associated data.

        Deletes the tenant directory including all policies and apps.

        Args:
            tenant_id: Tenant identifier.

        Raises:
            TenantNotFoundError: If tenant does not exist.

        Warning:
            This is a destructive operation. The CLI should confirm with user.
        """
        repo = self._get_tenant_repo()

        # Verify tenant exists
        tenant = repo.get_tenant(tenant_id)
        if not tenant:
            raise TenantNotFoundError(tenant_id)

        # Delete entire tenant directory
        tenant_path = self.base_path / tenant_id
        if tenant_path.exists():
            shutil.rmtree(tenant_path)

        logger.info(f"Deleted tenant: {tenant_id}")

    def set_tenant_policy(self, tenant_id: str, policy_id: str) -> Tenant:
        """Set the default policy for a tenant.

        Args:
            tenant_id: Tenant identifier.
            policy_id: Policy ID (global preset or tenant-specific).

        Returns:
            Updated Tenant domain object.

        Raises:
            TenantNotFoundError: If tenant does not exist.
            PolicyNotFoundError: If policy_id is invalid.
        """
        repo = self._get_tenant_repo()

        # Get existing tenant
        tenant = repo.get_tenant(tenant_id)
        if not tenant:
            raise TenantNotFoundError(tenant_id)

        # Validate policy exists
        available = get_available_policies(tenant_id, base_path=self.base_path)
        if policy_id not in available:
            raise PolicyNotFoundError(policy_id, tenant_id=tenant_id)

        # Create updated tenant (frozen dataclass)
        updated_tenant = Tenant(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            default_policy_id=policy_id,
            partner_id=tenant.partner_id,
            tier=tenant.tier,
            created_at=tenant.created_at,
        )

        # Persist
        repo.save_tenant(updated_tenant)

        logger.info(f"Updated tenant {tenant_id} policy to {policy_id}")
        return updated_tenant

    # =========================================================================
    # Policy Operations
    # =========================================================================

    def create_policy(self, request: CreatePolicyRequest) -> TenantPolicy:
        """Create a custom policy for a tenant.

        Args:
            request: Policy creation parameters.

        Returns:
            Created TenantPolicy domain object.

        Raises:
            TenantNotFoundError: If tenant does not exist.
            DuplicateEntityError: If policy_id already exists for tenant.
            PolicyValidationError: If parameters are invalid.
        """
        tenant_repo = self._get_tenant_repo()
        policy_repo = self._get_policy_repo()

        # Verify tenant exists
        tenant = tenant_repo.get_tenant(request.tenant_id)
        if not tenant:
            raise TenantNotFoundError(request.tenant_id)

        # Generate policy_id if not provided
        policy_id = request.policy_id or slugify(request.name, fallback="policy")

        # Check for duplicates
        existing = policy_repo.get_policy(policy_id, request.tenant_id)
        if existing:
            raise DuplicateEntityError("policy", policy_id, tenant_id=request.tenant_id)

        # Validate mode
        try:
            mode = PolicyMode(request.mode)
        except ValueError as e:
            valid_modes = [m.value for m in PolicyMode]
            raise PolicyValidationError(
                f"Invalid mode '{request.mode}'",
                field="mode",
                value=request.mode,
                constraint=f"must be one of {valid_modes}",
            ) from e

        # Determine final values based on mode
        if mode == PolicyMode.CUSTOM:
            # Custom mode uses provided values with balanced defaults
            final_blocking = (
                request.blocking_enabled if request.blocking_enabled is not None else True
            )
            final_severity = request.block_severity_threshold or "HIGH"
            final_confidence = (
                request.block_confidence_threshold
                if request.block_confidence_threshold is not None
                else 0.85
            )
            final_l2 = request.l2_enabled if request.l2_enabled is not None else True
            final_l2_threshold = (
                request.l2_threat_threshold if request.l2_threat_threshold is not None else 0.35
            )
            final_telemetry = request.telemetry_detail or "standard"
        else:
            # Preset modes use preset values
            base_preset = GLOBAL_PRESETS.get(mode.value)
            if not base_preset:
                raise PolicyValidationError(f"Invalid mode '{request.mode}'")

            final_blocking = base_preset.blocking_enabled
            final_severity = base_preset.block_severity_threshold
            final_confidence = base_preset.block_confidence_threshold
            final_l2 = base_preset.l2_enabled
            final_l2_threshold = base_preset.l2_threat_threshold
            final_telemetry = base_preset.telemetry_detail

        now = self._get_timestamp()

        # Create policy domain object
        policy = TenantPolicy(
            policy_id=policy_id,
            name=request.name,
            tenant_id=request.tenant_id,
            mode=mode,
            blocking_enabled=final_blocking,
            block_severity_threshold=final_severity,
            block_confidence_threshold=final_confidence,
            l2_enabled=final_l2,
            l2_threat_threshold=final_l2_threshold,
            telemetry_detail=final_telemetry,
            version=1,
            created_at=now,
            updated_at=now,
        )

        # Persist
        policy_repo.save_policy(policy)

        logger.info(f"Created policy {policy_id} for tenant {request.tenant_id}")
        return policy

    def get_policy(self, policy_id: str, tenant_id: str | None = None) -> TenantPolicy:
        """Get a policy by ID.

        Args:
            policy_id: Policy identifier.
            tenant_id: Tenant ID for tenant-specific policies.
                If None, only global presets are searched.

        Returns:
            TenantPolicy domain object.

        Raises:
            PolicyNotFoundError: If policy does not exist.
        """
        # Check global presets first
        if policy_id in GLOBAL_PRESETS:
            return GLOBAL_PRESETS[policy_id]

        # Check tenant-specific policies
        if tenant_id:
            policy_repo = self._get_policy_repo()
            policy = policy_repo.get_policy(policy_id, tenant_id)
            if policy:
                return policy

        raise PolicyNotFoundError(policy_id, tenant_id=tenant_id)

    def list_policies(self, tenant_id: str | None = None) -> list[TenantPolicy]:
        """List policies available for a tenant.

        Args:
            tenant_id: Tenant ID. If None, returns only global presets.

        Returns:
            List of TenantPolicy objects (global presets + tenant-specific).

        Raises:
            TenantNotFoundError: If tenant_id provided but tenant doesn't exist.
        """
        policies: list[TenantPolicy] = list(GLOBAL_PRESETS.values())

        if tenant_id:
            # Verify tenant exists
            tenant_repo = self._get_tenant_repo()
            if not tenant_repo.get_tenant(tenant_id):
                raise TenantNotFoundError(tenant_id)

            # Add tenant-specific policies
            policy_repo = self._get_policy_repo()
            tenant_policies = policy_repo.list_policies(tenant_id)
            policies.extend(tenant_policies)

        return sorted(policies, key=lambda p: p.policy_id)

    def update_policy(self, request: UpdatePolicyRequest) -> TenantPolicy:
        """Update an existing custom policy.

        Global presets cannot be updated.

        Args:
            request: Policy update parameters.

        Returns:
            Updated TenantPolicy domain object.

        Raises:
            TenantNotFoundError: If tenant does not exist.
            PolicyNotFoundError: If policy does not exist.
            ImmutablePresetError: If attempting to update a global preset.
        """
        # Cannot update global presets
        if request.policy_id in GLOBAL_PRESETS:
            raise ImmutablePresetError(request.policy_id, operation="update")

        tenant_repo = self._get_tenant_repo()
        policy_repo = self._get_policy_repo()

        # Verify tenant exists
        if not tenant_repo.get_tenant(request.tenant_id):
            raise TenantNotFoundError(request.tenant_id)

        # Get existing policy
        existing = policy_repo.get_policy(request.policy_id, request.tenant_id)
        if not existing:
            raise PolicyNotFoundError(request.policy_id, tenant_id=request.tenant_id)

        # Determine new mode (any threshold change switches to custom)
        new_mode = existing.mode
        has_threshold_change = any(
            [
                request.blocking_enabled is not None,
                request.block_severity_threshold is not None,
                request.block_confidence_threshold is not None,
                request.l2_enabled is not None,
                request.l2_threat_threshold is not None,
            ]
        )
        if has_threshold_change:
            new_mode = PolicyMode.CUSTOM

        # Merge values (use new if provided, else keep existing)
        updated_policy = TenantPolicy(
            policy_id=existing.policy_id,
            name=request.name if request.name is not None else existing.name,
            tenant_id=existing.tenant_id,
            mode=new_mode,
            blocking_enabled=(
                request.blocking_enabled
                if request.blocking_enabled is not None
                else existing.blocking_enabled
            ),
            block_severity_threshold=(
                request.block_severity_threshold
                if request.block_severity_threshold
                else existing.block_severity_threshold
            ),
            block_confidence_threshold=(
                request.block_confidence_threshold
                if request.block_confidence_threshold is not None
                else existing.block_confidence_threshold
            ),
            l2_enabled=(
                request.l2_enabled if request.l2_enabled is not None else existing.l2_enabled
            ),
            l2_threat_threshold=(
                request.l2_threat_threshold
                if request.l2_threat_threshold is not None
                else existing.l2_threat_threshold
            ),
            telemetry_detail=(
                request.telemetry_detail if request.telemetry_detail else existing.telemetry_detail
            ),
            version=existing.version + 1,
            created_at=existing.created_at,
            updated_at=self._get_timestamp(),
        )

        # Persist
        policy_repo.save_policy(updated_policy)

        logger.info(f"Updated policy {request.policy_id} (v{updated_policy.version})")
        return updated_policy

    def delete_policy(self, policy_id: str, tenant_id: str) -> None:
        """Delete a custom policy.

        Global presets cannot be deleted.

        Args:
            policy_id: Policy identifier.
            tenant_id: Tenant that owns the policy.

        Raises:
            TenantNotFoundError: If tenant does not exist.
            PolicyNotFoundError: If policy does not exist.
            ImmutablePresetError: If attempting to delete a global preset.
        """
        # Cannot delete global presets
        if policy_id in GLOBAL_PRESETS:
            raise ImmutablePresetError(policy_id, operation="delete")

        tenant_repo = self._get_tenant_repo()
        policy_repo = self._get_policy_repo()

        # Verify tenant exists
        if not tenant_repo.get_tenant(tenant_id):
            raise TenantNotFoundError(tenant_id)

        # Verify policy exists
        existing = policy_repo.get_policy(policy_id, tenant_id)
        if not existing:
            raise PolicyNotFoundError(policy_id, tenant_id=tenant_id)

        # Delete
        policy_repo.delete_policy(policy_id, tenant_id)

        logger.info(f"Deleted policy {policy_id} from tenant {tenant_id}")

    def explain_policy(
        self,
        tenant_id: str,
        app_id: str | None = None,
        policy_id: str | None = None,
    ) -> PolicyResolutionResult:
        """Explain which policy would be used for a given context.

        Args:
            tenant_id: Tenant identifier.
            app_id: Optional app ID.
            policy_id: Optional request-time policy override.

        Returns:
            PolicyResolutionResult with resolved policy and resolution path.

        Raises:
            TenantNotFoundError: If tenant does not exist.
            AppNotFoundError: If app_id provided but app doesn't exist.
        """
        tenant_repo = self._get_tenant_repo()
        app_repo = self._get_app_repo()

        # Verify tenant exists
        tenant = tenant_repo.get_tenant(tenant_id)
        if not tenant:
            raise TenantNotFoundError(tenant_id)

        # Load app if specified
        app = None
        if app_id:
            app = app_repo.get_app(app_id, tenant_id)
            if not app:
                raise AppNotFoundError(app_id, tenant_id)

        # Build policy registry
        registry = build_policy_registry(tenant_id, base_path=self.base_path)

        # Resolve policy (pure domain function)
        resolution = resolve_policy(
            request_policy_id=policy_id,
            app=app,
            tenant=tenant,
            policy_registry=registry,
        )

        return resolution

    # =========================================================================
    # App Operations
    # =========================================================================

    def create_app(self, request: CreateAppRequest) -> App:
        """Create a new app within a tenant.

        Args:
            request: App creation parameters.

        Returns:
            Created App domain object.

        Raises:
            TenantNotFoundError: If tenant does not exist.
            DuplicateEntityError: If app_id already exists in tenant.
            PolicyNotFoundError: If default_policy_id is invalid.
        """
        tenant_repo = self._get_tenant_repo()
        app_repo = self._get_app_repo()

        # Verify tenant exists
        if not tenant_repo.get_tenant(request.tenant_id):
            raise TenantNotFoundError(request.tenant_id)

        # Generate app_id if not provided
        app_id = request.app_id or slugify(request.name, fallback="app")

        # Check for duplicates
        existing = app_repo.get_app(app_id, request.tenant_id)
        if existing:
            raise DuplicateEntityError("app", app_id, tenant_id=request.tenant_id)

        # Validate default_policy_id if provided
        if request.default_policy_id:
            available = get_available_policies(request.tenant_id, base_path=self.base_path)
            if request.default_policy_id not in available:
                raise PolicyNotFoundError(request.default_policy_id, tenant_id=request.tenant_id)

        # Create app domain object
        app = App(
            app_id=app_id,
            tenant_id=request.tenant_id,
            name=request.name,
            default_policy_id=request.default_policy_id,
            created_at=self._get_timestamp(),
        )

        # Persist
        app_repo.save_app(app)

        logger.info(f"Created app {app_id} in tenant {request.tenant_id}")
        return app

    def get_app(self, app_id: str, tenant_id: str) -> App:
        """Get an app by ID.

        Args:
            app_id: App identifier.
            tenant_id: Tenant that owns the app.

        Returns:
            App domain object.

        Raises:
            TenantNotFoundError: If tenant does not exist.
            AppNotFoundError: If app does not exist.
        """
        tenant_repo = self._get_tenant_repo()
        app_repo = self._get_app_repo()

        # Verify tenant exists
        if not tenant_repo.get_tenant(tenant_id):
            raise TenantNotFoundError(tenant_id)

        app = app_repo.get_app(app_id, tenant_id)
        if not app:
            raise AppNotFoundError(app_id, tenant_id)

        return app

    def list_apps(self, tenant_id: str) -> list[App]:
        """List all apps in a tenant.

        Args:
            tenant_id: Tenant identifier.

        Returns:
            List of App domain objects, sorted by app_id.

        Raises:
            TenantNotFoundError: If tenant does not exist.
        """
        tenant_repo = self._get_tenant_repo()
        app_repo = self._get_app_repo()

        # Verify tenant exists
        if not tenant_repo.get_tenant(tenant_id):
            raise TenantNotFoundError(tenant_id)

        apps = app_repo.list_apps(tenant_id)
        return sorted(apps, key=lambda a: a.app_id)

    def delete_app(self, app_id: str, tenant_id: str) -> None:
        """Delete an app from a tenant.

        Args:
            app_id: App identifier.
            tenant_id: Tenant that owns the app.

        Raises:
            TenantNotFoundError: If tenant does not exist.
            AppNotFoundError: If app does not exist.
        """
        tenant_repo = self._get_tenant_repo()
        app_repo = self._get_app_repo()

        # Verify tenant exists
        if not tenant_repo.get_tenant(tenant_id):
            raise TenantNotFoundError(tenant_id)

        # Verify app exists
        existing = app_repo.get_app(app_id, tenant_id)
        if not existing:
            raise AppNotFoundError(app_id, tenant_id)

        # Delete
        app_repo.delete_app(app_id, tenant_id)

        logger.info(f"Deleted app {app_id} from tenant {tenant_id}")

    def set_app_policy(self, app_id: str, tenant_id: str, policy_id: str | None) -> App:
        """Set or clear the default policy for an app.

        Args:
            app_id: App identifier.
            tenant_id: Tenant that owns the app.
            policy_id: Policy ID to set, or None to inherit from tenant.

        Returns:
            Updated App domain object.

        Raises:
            TenantNotFoundError: If tenant does not exist.
            AppNotFoundError: If app does not exist.
            PolicyNotFoundError: If policy_id is invalid.
        """
        tenant_repo = self._get_tenant_repo()
        app_repo = self._get_app_repo()

        # Verify tenant exists
        if not tenant_repo.get_tenant(tenant_id):
            raise TenantNotFoundError(tenant_id)

        # Get existing app
        existing = app_repo.get_app(app_id, tenant_id)
        if not existing:
            raise AppNotFoundError(app_id, tenant_id)

        # Validate policy if provided
        if policy_id:
            available = get_available_policies(tenant_id, base_path=self.base_path)
            if policy_id not in available:
                raise PolicyNotFoundError(policy_id, tenant_id=tenant_id)

        # Create updated app (frozen dataclass)
        updated_app = App(
            app_id=existing.app_id,
            tenant_id=existing.tenant_id,
            name=existing.name,
            default_policy_id=policy_id,
            created_at=existing.created_at,
        )

        # Persist
        app_repo.save_app(updated_app)

        logger.info(f"Updated app {app_id} policy to {policy_id or '(inherit)'}")
        return updated_app


# =============================================================================
# Convenience Factory Function
# =============================================================================


def create_tenant_service(base_path: Path | None = None) -> TenantService:
    """Create a TenantService with default configuration.

    Factory function for consistent service instantiation.

    Args:
        base_path: Override base path for testing.
            If None, uses default from get_tenants_base_path().

    Returns:
        TenantService instance.

    Example:
        >>> service = create_tenant_service()
        >>> tenants = service.list_tenants()

        >>> # For testing
        >>> service = create_tenant_service(base_path=tmp_path)
    """
    return TenantService(base_path=base_path)
