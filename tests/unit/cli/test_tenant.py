"""Tests for tenant CLI commands."""

import json

from raxe.cli.tenant import tenant

# Fixtures (runner, temp_tenant_dir, mock_tenant_path) are provided by conftest.py


class TestTenantCreate:
    """Tests for raxe tenant create command."""

    def test_create_tenant_success(self, runner, mock_tenant_path):
        """Test creating a tenant successfully."""
        result = runner.invoke(tenant, ["create", "--name", "Acme Corp", "--id", "acme"])

        assert result.exit_code == 0
        assert "acme" in result.output
        assert "Acme Corp" in result.output

    def test_create_tenant_auto_id(self, runner, mock_tenant_path):
        """Test creating a tenant with auto-generated ID."""
        result = runner.invoke(tenant, ["create", "--name", "Acme Corp"])

        assert result.exit_code == 0
        # Should generate an ID based on name
        assert "Acme Corp" in result.output

    def test_create_tenant_with_policy(self, runner, mock_tenant_path):
        """Test creating a tenant with default policy."""
        result = runner.invoke(
            tenant, ["create", "--name", "Acme Corp", "--id", "acme", "--policy", "strict"]
        )

        assert result.exit_code == 0
        assert "strict" in result.output.lower() or "Acme Corp" in result.output

    def test_create_tenant_duplicate_id_fails(self, runner, mock_tenant_path):
        """Test that creating tenant with duplicate ID fails."""
        # Create first tenant
        runner.invoke(tenant, ["create", "--name", "Acme Corp", "--id", "acme"])
        # Try to create with same ID
        result = runner.invoke(tenant, ["create", "--name", "Other Corp", "--id", "acme"])

        assert result.exit_code != 0
        assert "already exists" in result.output.lower() or "error" in result.output.lower()


class TestTenantList:
    """Tests for raxe tenant list command."""

    def test_list_tenants_empty(self, runner, mock_tenant_path):
        """Test listing tenants when none exist."""
        result = runner.invoke(tenant, ["list"])

        assert result.exit_code == 0
        assert "no tenants" in result.output.lower() or "empty" in result.output.lower()

    def test_list_tenants_with_data(self, runner, mock_tenant_path):
        """Test listing tenants with data."""
        # Create tenants
        runner.invoke(tenant, ["create", "--name", "Acme Corp", "--id", "acme"])
        runner.invoke(tenant, ["create", "--name", "Partner CDN", "--id", "partner"])

        # List tenants
        result = runner.invoke(tenant, ["list"])

        assert result.exit_code == 0
        assert "acme" in result.output or "Acme" in result.output

    def test_list_tenants_json_output(self, runner, mock_tenant_path):
        """Test listing tenants with JSON output."""
        runner.invoke(tenant, ["create", "--name", "Acme Corp", "--id", "acme"])
        result = runner.invoke(tenant, ["list", "--output", "json"])

        assert result.exit_code == 0
        # Should be valid JSON
        data = json.loads(result.output)
        assert isinstance(data, list)
        if data:
            assert "tenant_id" in data[0] or "id" in data[0]


class TestTenantShow:
    """Tests for raxe tenant show command."""

    def test_show_tenant_details(self, runner, mock_tenant_path):
        """Test showing tenant details."""
        runner.invoke(tenant, ["create", "--name", "Acme Corp", "--id", "acme"])
        result = runner.invoke(tenant, ["show", "acme"])

        assert result.exit_code == 0
        assert "acme" in result.output or "Acme" in result.output

    def test_show_nonexistent_tenant(self, runner, mock_tenant_path):
        """Test showing a tenant that doesn't exist."""
        result = runner.invoke(tenant, ["show", "nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_show_tenant_json_output(self, runner, mock_tenant_path):
        """Test showing tenant with JSON output."""
        runner.invoke(tenant, ["create", "--name", "Acme Corp", "--id", "acme"])
        result = runner.invoke(tenant, ["show", "acme", "--output", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)


class TestTenantDelete:
    """Tests for raxe tenant delete command."""

    def test_delete_tenant_success(self, runner, mock_tenant_path):
        """Test deleting a tenant successfully."""
        runner.invoke(tenant, ["create", "--name", "Acme Corp", "--id", "acme"])
        result = runner.invoke(tenant, ["delete", "acme", "--force"])

        assert result.exit_code == 0
        assert "deleted" in result.output.lower() or "removed" in result.output.lower()

    def test_delete_nonexistent_tenant(self, runner, mock_tenant_path):
        """Test deleting a tenant that doesn't exist."""
        result = runner.invoke(tenant, ["delete", "nonexistent", "--force"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_delete_requires_force_or_confirmation(self, runner, mock_tenant_path):
        """Test that delete requires --force or confirmation."""
        runner.invoke(tenant, ["create", "--name", "Acme Corp", "--id", "acme"])
        # Without --force, should prompt for confirmation (we simulate declining)
        result = runner.invoke(tenant, ["delete", "acme"], input="n\n")

        # Either prompts or requires --force
        assert (
            "abort" in result.output.lower()
            or result.exit_code == 1
            or "y/n" in result.output.lower()
        )


class TestTenantSetPolicy:
    """Tests for raxe tenant set-policy command."""

    def test_set_tenant_policy(self, runner, mock_tenant_path):
        """Test setting tenant default policy."""
        runner.invoke(tenant, ["create", "--name", "Acme Corp", "--id", "acme"])
        result = runner.invoke(tenant, ["set-policy", "acme", "strict"])

        assert result.exit_code == 0
        assert "strict" in result.output.lower()

    def test_set_invalid_policy(self, runner, mock_tenant_path):
        """Test setting an invalid policy fails."""
        runner.invoke(tenant, ["create", "--name", "Acme Corp", "--id", "acme"])
        result = runner.invoke(tenant, ["set-policy", "acme", "invalid-policy"])

        assert result.exit_code != 0
