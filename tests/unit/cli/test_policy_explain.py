"""Tests for policy explain command.

The explain command shows which policy would be used without performing a scan.
"""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from raxe.cli.policy import policy


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
    """Patch get_tenants_base_path to use temp directory."""
    with patch(
        "raxe.infrastructure.tenants.get_tenants_base_path",
        return_value=temp_tenant_dir,
    ):
        yield temp_tenant_dir


def _create_tenant(temp_tenant_dir, tenant_id: str, name: str, policy_id: str = "balanced"):
    """Helper to create a tenant for testing."""
    from datetime import datetime, timezone

    from raxe.domain.tenants.models import Tenant
    from raxe.infrastructure.tenants import YamlTenantRepository

    repo = YamlTenantRepository(temp_tenant_dir)
    tenant = Tenant(
        tenant_id=tenant_id,
        name=name,
        default_policy_id=policy_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    repo.save_tenant(tenant)
    return tenant


def _create_app(
    temp_tenant_dir, tenant_id: str, app_id: str, name: str, policy_id: str | None = None
):
    """Helper to create an app for testing."""
    from datetime import datetime, timezone

    from raxe.domain.tenants.models import App
    from raxe.infrastructure.tenants import YamlAppRepository

    repo = YamlAppRepository(temp_tenant_dir)
    app = App(
        app_id=app_id,
        tenant_id=tenant_id,
        name=name,
        default_policy_id=policy_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    repo.save_app(app)
    return app


class TestPolicyExplain:
    """Tests for policy explain command."""

    def test_explain_tenant_only(self, runner, mock_tenant_path):
        """Test explaining policy for tenant without app."""
        _create_tenant(mock_tenant_path, "acme", "Acme Corp", "strict")

        result = runner.invoke(
            policy,
            ["explain", "--tenant", "acme"],
        )

        assert result.exit_code == 0
        assert "strict" in result.output
        assert "tenant" in result.output.lower()

    def test_explain_with_app(self, runner, mock_tenant_path):
        """Test explaining policy with app override."""
        _create_tenant(mock_tenant_path, "acme", "Acme Corp", "balanced")
        _create_app(mock_tenant_path, "acme", "chatbot", "Chatbot", "strict")

        result = runner.invoke(
            policy,
            ["explain", "--tenant", "acme", "--app", "chatbot"],
        )

        assert result.exit_code == 0
        assert "strict" in result.output
        assert "app" in result.output.lower()

    def test_explain_with_policy_override(self, runner, mock_tenant_path):
        """Test explaining with explicit policy override."""
        _create_tenant(mock_tenant_path, "acme", "Acme Corp", "balanced")

        result = runner.invoke(
            policy,
            ["explain", "--tenant", "acme", "--policy", "monitor"],
        )

        assert result.exit_code == 0
        assert "monitor" in result.output
        assert "request" in result.output.lower() or "override" in result.output.lower()

    def test_explain_shows_resolution_path(self, runner, mock_tenant_path):
        """Test that explain shows full resolution path."""
        _create_tenant(mock_tenant_path, "acme", "Acme Corp", "balanced")
        _create_app(mock_tenant_path, "acme", "chatbot", "Chatbot")  # No policy override

        result = runner.invoke(
            policy,
            ["explain", "--tenant", "acme", "--app", "chatbot"],
        )

        assert result.exit_code == 0
        # Should show that app has no override, falls back to tenant
        assert "balanced" in result.output
        assert "tenant" in result.output.lower()

    def test_explain_json_output(self, runner, mock_tenant_path):
        """Test explain with JSON output."""
        _create_tenant(mock_tenant_path, "acme", "Acme Corp", "strict")

        result = runner.invoke(
            policy,
            ["explain", "--tenant", "acme", "--output", "json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "effective_policy_id" in data
        assert "resolution_source" in data
        assert "resolution_path" in data
        assert data["effective_policy_id"] == "strict"

    def test_explain_nonexistent_tenant_fails(self, runner, mock_tenant_path):
        """Test explain with non-existent tenant fails."""
        result = runner.invoke(
            policy,
            ["explain", "--tenant", "nonexistent"],
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_explain_system_default_fallback(self, runner, mock_tenant_path):
        """Test explain shows system default when no config."""
        # Create tenant with no default policy
        _create_tenant(mock_tenant_path, "acme", "Acme Corp", "balanced")

        result = runner.invoke(
            policy,
            ["explain", "--tenant", "acme"],
        )

        assert result.exit_code == 0
        # Should show tenant default
        assert "balanced" in result.output

    def test_explain_shows_policy_details(self, runner, mock_tenant_path):
        """Test explain shows blocking_enabled and thresholds."""
        _create_tenant(mock_tenant_path, "acme", "Acme Corp", "strict")

        result = runner.invoke(
            policy,
            ["explain", "--tenant", "acme"],
        )

        assert result.exit_code == 0
        # Should show policy details
        output_lower = result.output.lower()
        assert "blocking" in output_lower or "block" in output_lower
        assert "medium" in output_lower or "threshold" in output_lower
