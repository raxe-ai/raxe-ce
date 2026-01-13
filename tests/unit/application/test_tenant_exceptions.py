"""Tests for tenant service exceptions.

Tests cover:
- Exception hierarchy and inheritance
- Error message formatting
- Details dictionary handling
- Specific exception types
"""

import pytest

from raxe.application.tenant_exceptions import (
    AppNotFoundError,
    DuplicateEntityError,
    EntityNotFoundError,
    ImmutablePresetError,
    PolicyNotFoundError,
    PolicyValidationError,
    TenantNotFoundError,
    TenantServiceError,
)


class TestTenantServiceError:
    """Tests for base TenantServiceError class."""

    def test_basic_message(self):
        """Basic exception with message only."""
        exc = TenantServiceError("Something went wrong")
        assert str(exc) == "Something went wrong"
        assert exc.message == "Something went wrong"
        assert exc.details == {}

    def test_message_with_details(self):
        """Exception with details dictionary."""
        exc = TenantServiceError(
            "Operation failed", details={"operation": "create", "entity": "tenant"}
        )
        assert "Something" not in str(exc)
        assert "operation=create" in str(exc)
        assert "entity=tenant" in str(exc)
        assert exc.details == {"operation": "create", "entity": "tenant"}

    def test_inherits_from_exception(self):
        """TenantServiceError inherits from Exception."""
        exc = TenantServiceError("test")
        assert isinstance(exc, Exception)


class TestEntityNotFoundError:
    """Tests for EntityNotFoundError base class."""

    def test_without_tenant_context(self):
        """Entity not found without tenant context."""
        exc = EntityNotFoundError("tenant", "acme")
        assert "Tenant 'acme' not found" in str(exc)
        assert exc.entity_type == "tenant"
        assert exc.entity_id == "acme"
        assert exc.tenant_id is None

    def test_with_tenant_context(self):
        """Entity not found with tenant context."""
        exc = EntityNotFoundError("policy", "strict-v2", tenant_id="acme")
        assert "Policy 'strict-v2' not found in tenant 'acme'" in str(exc)
        assert exc.entity_type == "policy"
        assert exc.entity_id == "strict-v2"
        assert exc.tenant_id == "acme"

    def test_inherits_from_tenant_service_error(self):
        """EntityNotFoundError inherits from TenantServiceError."""
        exc = EntityNotFoundError("app", "chatbot")
        assert isinstance(exc, TenantServiceError)


class TestTenantNotFoundError:
    """Tests for TenantNotFoundError."""

    def test_message_format(self):
        """Tenant not found message format."""
        exc = TenantNotFoundError("acme")
        assert "Tenant 'acme' not found" in str(exc)
        assert exc.message == "Tenant 'acme' not found"

    def test_entity_type_is_tenant(self):
        """Entity type is 'tenant'."""
        exc = TenantNotFoundError("test")
        assert exc.entity_type == "tenant"
        assert exc.entity_id == "test"

    def test_inherits_from_entity_not_found(self):
        """TenantNotFoundError inherits from EntityNotFoundError."""
        exc = TenantNotFoundError("acme")
        assert isinstance(exc, EntityNotFoundError)
        assert isinstance(exc, TenantServiceError)


class TestPolicyNotFoundError:
    """Tests for PolicyNotFoundError."""

    def test_without_tenant(self):
        """Policy not found without tenant context."""
        exc = PolicyNotFoundError("custom-policy")
        assert "Policy 'custom-policy' not found" in str(exc)
        assert exc.tenant_id is None

    def test_with_tenant(self):
        """Policy not found with tenant context."""
        exc = PolicyNotFoundError("my-policy", tenant_id="acme")
        assert "Policy 'my-policy' not found in tenant 'acme'" in str(exc)
        assert exc.tenant_id == "acme"

    def test_entity_type_is_policy(self):
        """Entity type is 'policy'."""
        exc = PolicyNotFoundError("test")
        assert exc.entity_type == "policy"


class TestAppNotFoundError:
    """Tests for AppNotFoundError."""

    def test_message_format(self):
        """App not found message format."""
        exc = AppNotFoundError("chatbot", tenant_id="acme")
        assert "App 'chatbot' not found in tenant 'acme'" in str(exc)

    def test_entity_type_is_app(self):
        """Entity type is 'app'."""
        exc = AppNotFoundError("bot", "tenant1")
        assert exc.entity_type == "app"
        assert exc.entity_id == "bot"
        assert exc.tenant_id == "tenant1"


class TestDuplicateEntityError:
    """Tests for DuplicateEntityError."""

    def test_without_tenant(self):
        """Duplicate entity without tenant context."""
        exc = DuplicateEntityError("tenant", "acme")
        assert "Tenant 'acme' already exists" in str(exc)
        assert exc.entity_type == "tenant"
        assert exc.entity_id == "acme"
        assert exc.tenant_id is None

    def test_with_tenant(self):
        """Duplicate entity with tenant context."""
        exc = DuplicateEntityError("policy", "strict", tenant_id="acme")
        assert "Policy 'strict' already exists in tenant 'acme'" in str(exc)
        assert exc.tenant_id == "acme"

    def test_app_duplicate(self):
        """Duplicate app within tenant."""
        exc = DuplicateEntityError("app", "chatbot", tenant_id="acme")
        assert "App 'chatbot' already exists in tenant 'acme'" in str(exc)

    def test_inherits_from_tenant_service_error(self):
        """DuplicateEntityError inherits from TenantServiceError."""
        exc = DuplicateEntityError("tenant", "test")
        assert isinstance(exc, TenantServiceError)


class TestPolicyValidationError:
    """Tests for PolicyValidationError."""

    def test_basic_message(self):
        """Basic validation error message."""
        exc = PolicyValidationError("Invalid configuration")
        assert str(exc) == "Invalid configuration"

    def test_with_all_details(self):
        """Validation error with all details."""
        exc = PolicyValidationError(
            "Invalid threshold",
            policy_id="my-policy",
            field="confidence_threshold",
            value=1.5,
            constraint="must be 0-1",
        )
        assert "Invalid threshold" in str(exc)
        assert "policy_id=my-policy" in str(exc)
        assert "field=confidence_threshold" in str(exc)
        assert "value=1.5" in str(exc)
        assert "constraint=must be 0-1" in str(exc)

    def test_partial_details(self):
        """Validation error with some details."""
        exc = PolicyValidationError("Invalid mode", field="mode", value="unknown")
        assert "field=mode" in str(exc)
        assert "value=unknown" in str(exc)
        assert "policy_id" not in str(exc)


class TestImmutablePresetError:
    """Tests for ImmutablePresetError."""

    def test_default_operation(self):
        """Default operation is 'modify'."""
        exc = ImmutablePresetError("balanced")
        assert "Cannot modify global preset 'balanced'" in str(exc)
        assert exc.preset_id == "balanced"
        assert exc.operation == "modify"

    def test_delete_operation(self):
        """Delete operation message."""
        exc = ImmutablePresetError("strict", operation="delete")
        assert "Cannot delete global preset 'strict'" in str(exc)
        assert exc.operation == "delete"

    def test_update_operation(self):
        """Update operation message."""
        exc = ImmutablePresetError("monitor", operation="update")
        assert "Cannot update global preset 'monitor'" in str(exc)

    def test_inherits_from_tenant_service_error(self):
        """ImmutablePresetError inherits from TenantServiceError."""
        exc = ImmutablePresetError("balanced")
        assert isinstance(exc, TenantServiceError)


class TestExceptionHierarchy:
    """Tests for exception hierarchy relationships."""

    def test_all_inherit_from_base(self):
        """All custom exceptions inherit from TenantServiceError."""
        exceptions = [
            TenantNotFoundError("test"),
            PolicyNotFoundError("test"),
            AppNotFoundError("test", "tenant"),
            DuplicateEntityError("tenant", "test"),
            PolicyValidationError("test"),
            ImmutablePresetError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, TenantServiceError)

    def test_not_found_hierarchy(self):
        """Not found exceptions form hierarchy."""
        tenant_exc = TenantNotFoundError("test")
        policy_exc = PolicyNotFoundError("test")
        app_exc = AppNotFoundError("test", "tenant")

        for exc in [tenant_exc, policy_exc, app_exc]:
            assert isinstance(exc, EntityNotFoundError)
            assert isinstance(exc, TenantServiceError)

    def test_can_catch_all_with_base(self):
        """Can catch all exceptions with TenantServiceError."""
        exceptions_to_test = [
            lambda: TenantNotFoundError("test"),
            lambda: PolicyNotFoundError("test"),
            lambda: AppNotFoundError("test", "tenant"),
            lambda: DuplicateEntityError("tenant", "test"),
            lambda: PolicyValidationError("test"),
            lambda: ImmutablePresetError("test"),
        ]

        for exc_factory in exceptions_to_test:
            try:
                raise exc_factory()
            except TenantServiceError:
                pass  # Should be caught
            except Exception:
                pytest.fail("Exception not caught by TenantServiceError")
