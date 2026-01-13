"""Fixtures for tenant tests."""

import pytest

from raxe.domain.tenants.models import (
    App,
    PolicyMode,
    Tenant,
    TenantPolicy,
)


@pytest.fixture
def sample_tenant_policy() -> TenantPolicy:
    """Create a sample tenant policy for testing."""
    return TenantPolicy(
        policy_id="test_policy",
        name="Test Policy",
        tenant_id="acme",
        mode=PolicyMode.BALANCED,
        blocking_enabled=True,
    )


@pytest.fixture
def sample_tenant() -> Tenant:
    """Create a sample tenant for testing."""
    return Tenant(
        tenant_id="acme",
        name="Acme Corp",
        default_policy_id="balanced",
    )


@pytest.fixture
def sample_app() -> App:
    """Create a sample app for testing."""
    return App(
        app_id="chatbot",
        tenant_id="acme",
        name="Customer Support Bot",
        default_policy_id="strict",
    )


@pytest.fixture
def tenant_with_monitor() -> Tenant:
    """Tenant with monitor mode default."""
    return Tenant(
        tenant_id="dev_tenant",
        name="Development Tenant",
        default_policy_id="monitor",
    )


@pytest.fixture
def app_with_balanced() -> App:
    """App with balanced mode policy."""
    return App(
        app_id="prod_app",
        tenant_id="acme",
        name="Production App",
        default_policy_id="balanced",
    )


@pytest.fixture
def app_without_policy() -> App:
    """App without default policy (inherits from tenant)."""
    return App(
        app_id="basic_app",
        tenant_id="acme",
        name="Basic App",
        default_policy_id=None,
    )
