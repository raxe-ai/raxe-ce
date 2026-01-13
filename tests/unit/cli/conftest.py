"""Shared fixtures for CLI tests."""

from contextlib import ExitStack
from unittest.mock import patch

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    """Create CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_tenant_dir(tmp_path):
    """Create a temporary tenant directory."""
    tenant_dir = tmp_path / "tenants"
    tenant_dir.mkdir()
    return tenant_dir


@pytest.fixture
def mock_tenant_path(temp_tenant_dir):
    """Fixture that patches get_tenants_base_path in all required locations.

    This ensures proper test isolation by patching:
    - CLI modules (for display paths in tenant.py)
    - Infrastructure layer (for actual storage - used by TenantService)
    """
    with ExitStack() as stack:
        # Patch in tenant CLI (still uses get_tenants_base_path for display paths)
        stack.enter_context(
            patch("raxe.cli.tenant.get_tenants_base_path", return_value=temp_tenant_dir)
        )
        # Patch in infrastructure.tenants (where TenantService/factory gets base path)
        stack.enter_context(
            patch(
                "raxe.infrastructure.tenants.get_tenants_base_path",
                return_value=temp_tenant_dir,
            )
        )
        yield temp_tenant_dir


def create_test_tenant(runner, tenant_id: str = "acme", name: str = "Acme Corp"):
    """Helper to create a tenant for testing.

    Should only be called inside mock_tenant_path context.
    """
    from raxe.cli.tenant import tenant as tenant_cmd

    result = runner.invoke(tenant_cmd, ["create", "--name", name, "--id", tenant_id])
    return result
