"""Exceptions for tenant management operations.

Application-layer exceptions that represent business logic failures.
These exceptions are raised by TenantService and handled by CLI/SDK.

Exception Hierarchy:
- TenantServiceError (base)
  - EntityNotFoundError
    - TenantNotFoundError
    - PolicyNotFoundError
    - AppNotFoundError
  - DuplicateEntityError
  - PolicyValidationError
  - ImmutablePresetError
"""

from __future__ import annotations

from typing import Any


class TenantServiceError(Exception):
    """Base exception for tenant service operations.

    All tenant service exceptions inherit from this class.
    Provides consistent error handling across CLI and SDK consumers.

    Attributes:
        message: Human-readable error description.
        details: Optional dictionary with additional context.
    """

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        """Initialize exception.

        Args:
            message: Human-readable error description.
            details: Optional additional context for debugging.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """Return string representation."""
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({detail_str})"
        return self.message


# =============================================================================
# Entity Not Found Errors
# =============================================================================


class EntityNotFoundError(TenantServiceError):
    """Base exception for entity not found errors.

    Attributes:
        entity_type: Type of entity ("tenant", "policy", "app").
        entity_id: Identifier of the missing entity.
    """

    def __init__(
        self,
        entity_type: str,
        entity_id: str,
        *,
        tenant_id: str | None = None,
    ) -> None:
        """Initialize exception.

        Args:
            entity_type: Type of entity not found.
            entity_id: ID of the missing entity.
            tenant_id: Tenant context (for policy/app lookups).
        """
        details = {"entity_type": entity_type, "entity_id": entity_id}
        if tenant_id:
            details["tenant_id"] = tenant_id

        message = f"{entity_type.capitalize()} '{entity_id}' not found"
        if tenant_id:
            message += f" in tenant '{tenant_id}'"

        super().__init__(message, details=details)
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.tenant_id = tenant_id


class TenantNotFoundError(EntityNotFoundError):
    """Raised when a tenant does not exist.

    Example:
        >>> raise TenantNotFoundError("acme")
        TenantNotFoundError: Tenant 'acme' not found
    """

    def __init__(self, tenant_id: str) -> None:
        """Initialize exception.

        Args:
            tenant_id: ID of the missing tenant.
        """
        super().__init__("tenant", tenant_id)


class PolicyNotFoundError(EntityNotFoundError):
    """Raised when a policy does not exist.

    For global presets, tenant_id is None.
    For tenant-specific policies, tenant_id is required.

    Example:
        >>> raise PolicyNotFoundError("my-policy", tenant_id="acme")
        PolicyNotFoundError: Policy 'my-policy' not found in tenant 'acme'
    """

    def __init__(self, policy_id: str, *, tenant_id: str | None = None) -> None:
        """Initialize exception.

        Args:
            policy_id: ID of the missing policy.
            tenant_id: Tenant context for tenant-specific policies.
        """
        super().__init__("policy", policy_id, tenant_id=tenant_id)


class AppNotFoundError(EntityNotFoundError):
    """Raised when an app does not exist.

    Example:
        >>> raise AppNotFoundError("chatbot", tenant_id="acme")
        AppNotFoundError: App 'chatbot' not found in tenant 'acme'
    """

    def __init__(self, app_id: str, tenant_id: str) -> None:
        """Initialize exception.

        Args:
            app_id: ID of the missing app.
            tenant_id: Tenant that should contain the app.
        """
        super().__init__("app", app_id, tenant_id=tenant_id)


# =============================================================================
# Duplicate Entity Errors
# =============================================================================


class DuplicateEntityError(TenantServiceError):
    """Raised when attempting to create an entity that already exists.

    Attributes:
        entity_type: Type of entity ("tenant", "policy", "app").
        entity_id: Identifier of the existing entity.
        tenant_id: Tenant context (for policy/app).
    """

    def __init__(
        self,
        entity_type: str,
        entity_id: str,
        *,
        tenant_id: str | None = None,
    ) -> None:
        """Initialize exception.

        Args:
            entity_type: Type of entity that exists.
            entity_id: ID of the existing entity.
            tenant_id: Tenant context (for policy/app).
        """
        details = {"entity_type": entity_type, "entity_id": entity_id}
        if tenant_id:
            details["tenant_id"] = tenant_id

        message = f"{entity_type.capitalize()} '{entity_id}' already exists"
        if tenant_id:
            message += f" in tenant '{tenant_id}'"

        super().__init__(message, details=details)
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.tenant_id = tenant_id


# =============================================================================
# Validation Errors
# =============================================================================


class PolicyValidationError(TenantServiceError):
    """Raised when policy validation fails.

    Example:
        >>> raise PolicyValidationError(
        ...     "Invalid policy",
        ...     policy_id="my-policy",
        ...     field="confidence_threshold",
        ...     value=1.5,
        ...     constraint="must be 0-1"
        ... )
    """

    def __init__(
        self,
        message: str,
        *,
        policy_id: str | None = None,
        field: str | None = None,
        value: object = None,
        constraint: str | None = None,
    ) -> None:
        """Initialize exception.

        Args:
            message: Error description.
            policy_id: Policy being validated.
            field: Field that failed validation.
            value: Invalid value.
            constraint: Constraint that was violated.
        """
        details: dict[str, Any] = {}
        if policy_id:
            details["policy_id"] = policy_id
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = value
        if constraint:
            details["constraint"] = constraint

        super().__init__(message, details=details)


class ImmutablePresetError(TenantServiceError):
    """Raised when attempting to modify or delete a global preset.

    Global presets (monitor, balanced, strict) are immutable system policies.

    Example:
        >>> raise ImmutablePresetError("balanced", operation="delete")
        ImmutablePresetError: Cannot delete global preset 'balanced'
    """

    def __init__(self, preset_id: str, *, operation: str = "modify") -> None:
        """Initialize exception.

        Args:
            preset_id: ID of the global preset.
            operation: Operation attempted ("modify", "delete", "update").
        """
        message = f"Cannot {operation} global preset '{preset_id}'"
        super().__init__(message, details={"preset_id": preset_id, "operation": operation})
        self.preset_id = preset_id
        self.operation = operation
