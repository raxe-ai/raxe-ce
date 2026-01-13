"""Repository protocols for multi-tenant policy management (PURE - NO IMPLEMENTATION).

This module defines the interfaces (Protocols) for persistence operations.
Infrastructure layer provides concrete implementations.

NO I/O operations in this layer:
- NO database calls
- NO file operations
- NO network requests
"""

from typing import Protocol

from raxe.domain.tenants.models import App, Tenant, TenantPolicy


class TenantRepository(Protocol):
    """Repository interface for Tenant persistence.

    Implementations should handle loading/saving tenants to storage
    (YAML files, database, etc.).
    """

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        """Get a tenant by ID.

        Args:
            tenant_id: Unique tenant identifier

        Returns:
            Tenant if found, None otherwise
        """
        ...

    def save_tenant(self, tenant: Tenant) -> None:
        """Save a tenant to storage.

        Creates or updates the tenant.

        Args:
            tenant: Tenant to save
        """
        ...

    def delete_tenant(self, tenant_id: str) -> bool:
        """Delete a tenant from storage.

        Args:
            tenant_id: ID of tenant to delete

        Returns:
            True if deleted, False if not found
        """
        ...

    def list_tenants(self) -> list[Tenant]:
        """List all tenants.

        Returns:
            List of all tenants
        """
        ...

    def tenant_exists(self, tenant_id: str) -> bool:
        """Check if a tenant exists.

        Args:
            tenant_id: ID to check

        Returns:
            True if tenant exists
        """
        ...


class PolicyRepository(Protocol):
    """Repository interface for TenantPolicy persistence.

    Implementations should handle loading/saving policies to storage.
    Policies can be global (tenant_id=None) or tenant-specific.
    """

    def get_policy(self, policy_id: str, tenant_id: str | None = None) -> TenantPolicy | None:
        """Get a policy by ID.

        Args:
            policy_id: Unique policy identifier
            tenant_id: Tenant ID to scope lookup, or None for global policies

        Returns:
            TenantPolicy if found, None otherwise
        """
        ...

    def save_policy(self, policy: TenantPolicy) -> None:
        """Save a policy to storage.

        Creates or updates the policy.

        Args:
            policy: TenantPolicy to save
        """
        ...

    def delete_policy(self, policy_id: str, tenant_id: str | None = None) -> bool:
        """Delete a policy from storage.

        Args:
            policy_id: ID of policy to delete
            tenant_id: Tenant ID to scope deletion, or None for global

        Returns:
            True if deleted, False if not found
        """
        ...

    def list_policies(self, tenant_id: str | None = None) -> list[TenantPolicy]:
        """List policies.

        Args:
            tenant_id: Filter by tenant ID, or None for all policies

        Returns:
            List of policies
        """
        ...

    def get_all_policies_as_registry(self) -> dict[str, TenantPolicy]:
        """Get all policies as a lookup dictionary.

        Returns:
            Dictionary mapping policy_id -> TenantPolicy
        """
        ...


class AppRepository(Protocol):
    """Repository interface for App persistence.

    Implementations should handle loading/saving apps to storage.
    Apps are always scoped to a tenant.
    """

    def get_app(self, app_id: str, tenant_id: str) -> App | None:
        """Get an app by ID within a tenant.

        Args:
            app_id: Unique app identifier within tenant
            tenant_id: Tenant the app belongs to

        Returns:
            App if found, None otherwise
        """
        ...

    def save_app(self, app: App) -> None:
        """Save an app to storage.

        Creates or updates the app.

        Args:
            app: App to save
        """
        ...

    def delete_app(self, app_id: str, tenant_id: str) -> bool:
        """Delete an app from storage.

        Args:
            app_id: ID of app to delete
            tenant_id: Tenant the app belongs to

        Returns:
            True if deleted, False if not found
        """
        ...

    def list_apps(self, tenant_id: str) -> list[App]:
        """List all apps for a tenant.

        Args:
            tenant_id: Tenant to list apps for

        Returns:
            List of apps belonging to the tenant
        """
        ...
