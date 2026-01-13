"""Tests for app CLI commands."""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from raxe.cli.app import app


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


def _create_tenant(temp_tenant_dir, tenant_id: str, name: str):
    """Helper to create a tenant for testing."""
    from datetime import datetime, timezone

    from raxe.domain.tenants.models import Tenant
    from raxe.infrastructure.tenants import YamlTenantRepository

    repo = YamlTenantRepository(temp_tenant_dir)
    tenant = Tenant(
        tenant_id=tenant_id,
        name=name,
        default_policy_id="balanced",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    repo.save_tenant(tenant)
    return tenant


class TestAppCreate:
    """Tests for app create command."""

    def test_create_app_success(self, runner, temp_tenant_dir):
        """Test creating an app in a tenant."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            result = runner.invoke(
                app,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--name",
                    "Customer Bot",
                ],
            )

        assert result.exit_code == 0
        assert "Created app" in result.output
        assert "customer-bot" in result.output or "Customer Bot" in result.output

    def test_create_app_with_id(self, runner, temp_tenant_dir):
        """Test creating an app with explicit ID."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            result = runner.invoke(
                app,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--name",
                    "Support Bot",
                    "--id",
                    "support",
                ],
            )

        assert result.exit_code == 0
        assert "support" in result.output

    def test_create_app_with_policy(self, runner, temp_tenant_dir):
        """Test creating an app with policy override."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            result = runner.invoke(
                app,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--name",
                    "Trading Bot",
                    "--policy",
                    "strict",
                ],
            )

        assert result.exit_code == 0
        assert "strict" in result.output

    def test_create_app_nonexistent_tenant(self, runner, temp_tenant_dir):
        """Test creating app in non-existent tenant fails."""
        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            result = runner.invoke(
                app,
                [
                    "create",
                    "--tenant",
                    "nonexistent",
                    "--name",
                    "Test Bot",
                ],
            )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_create_app_invalid_policy(self, runner, temp_tenant_dir):
        """Test creating app with invalid policy fails."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            result = runner.invoke(
                app,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--name",
                    "Test Bot",
                    "--policy",
                    "nonexistent-policy",
                ],
            )

        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "error" in result.output.lower()

    def test_create_duplicate_app_fails(self, runner, temp_tenant_dir):
        """Test creating duplicate app fails."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            # Create first app
            runner.invoke(
                app,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--name",
                    "Bot",
                    "--id",
                    "bot",
                ],
            )

            # Try to create duplicate
            result = runner.invoke(
                app,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--name",
                    "Another Bot",
                    "--id",
                    "bot",
                ],
            )

        assert result.exit_code != 0
        assert "already exists" in result.output.lower()


class TestAppList:
    """Tests for app list command."""

    def test_list_apps_empty(self, runner, temp_tenant_dir):
        """Test listing apps when none exist."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            result = runner.invoke(app, ["list", "--tenant", "acme"])

        assert result.exit_code == 0
        assert "No apps found" in result.output

    def test_list_apps_table(self, runner, temp_tenant_dir):
        """Test listing apps in table format."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            # Create some apps
            runner.invoke(
                app,
                ["create", "--tenant", "acme", "--name", "Bot A", "--id", "bot-a"],
            )
            runner.invoke(
                app,
                ["create", "--tenant", "acme", "--name", "Bot B", "--id", "bot-b"],
            )

            result = runner.invoke(app, ["list", "--tenant", "acme"])

        assert result.exit_code == 0
        assert "bot-a" in result.output
        assert "bot-b" in result.output

    def test_list_apps_json(self, runner, temp_tenant_dir):
        """Test listing apps in JSON format."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            runner.invoke(
                app,
                ["create", "--tenant", "acme", "--name", "Bot", "--id", "bot"],
            )

            result = runner.invoke(app, ["list", "--tenant", "acme", "--output", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["app_id"] == "bot"

    def test_list_apps_nonexistent_tenant(self, runner, temp_tenant_dir):
        """Test listing apps for non-existent tenant fails."""
        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            result = runner.invoke(app, ["list", "--tenant", "nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestAppShow:
    """Tests for app show command."""

    def test_show_app_table(self, runner, temp_tenant_dir):
        """Test showing app details in table format."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            runner.invoke(
                app,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--name",
                    "Test Bot",
                    "--id",
                    "test-bot",
                    "--policy",
                    "strict",
                ],
            )

            result = runner.invoke(app, ["show", "--tenant", "acme", "test-bot"])

        assert result.exit_code == 0
        assert "test-bot" in result.output
        assert "Test Bot" in result.output
        assert "strict" in result.output

    def test_show_app_json(self, runner, temp_tenant_dir):
        """Test showing app details in JSON format."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            runner.invoke(
                app,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--name",
                    "Test Bot",
                    "--id",
                    "test-bot",
                ],
            )

            result = runner.invoke(
                app, ["show", "--tenant", "acme", "test-bot", "--output", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["app_id"] == "test-bot"
        assert data["name"] == "Test Bot"

    def test_show_app_not_found(self, runner, temp_tenant_dir):
        """Test showing non-existent app fails."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            result = runner.invoke(app, ["show", "--tenant", "acme", "nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestAppDelete:
    """Tests for app delete command."""

    def test_delete_app_with_force(self, runner, temp_tenant_dir):
        """Test deleting app with --force flag."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            runner.invoke(
                app,
                ["create", "--tenant", "acme", "--name", "Bot", "--id", "bot"],
            )

            result = runner.invoke(app, ["delete", "--tenant", "acme", "bot", "--force"])

        assert result.exit_code == 0
        assert "Deleted" in result.output

    def test_delete_nonexistent_app(self, runner, temp_tenant_dir):
        """Test deleting non-existent app fails."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            result = runner.invoke(app, ["delete", "--tenant", "acme", "nonexistent", "--force"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestAppSetPolicy:
    """Tests for app set-policy command."""

    def test_set_policy_success(self, runner, temp_tenant_dir):
        """Test setting app policy."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            runner.invoke(
                app,
                ["create", "--tenant", "acme", "--name", "Bot", "--id", "bot"],
            )

            result = runner.invoke(app, ["set-policy", "--tenant", "acme", "bot", "strict"])

        assert result.exit_code == 0
        assert "strict" in result.output

    def test_set_policy_inherit(self, runner, temp_tenant_dir):
        """Test removing policy override with 'inherit'."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            runner.invoke(
                app,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--name",
                    "Bot",
                    "--id",
                    "bot",
                    "--policy",
                    "strict",
                ],
            )

            result = runner.invoke(app, ["set-policy", "--tenant", "acme", "bot", "inherit"])

        assert result.exit_code == 0
        assert "inherit" in result.output.lower()

    def test_set_policy_invalid(self, runner, temp_tenant_dir):
        """Test setting invalid policy fails."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with patch(
            "raxe.cli.app.get_tenants_base_path",
            return_value=temp_tenant_dir,
        ):
            runner.invoke(
                app,
                ["create", "--tenant", "acme", "--name", "Bot", "--id", "bot"],
            )

            result = runner.invoke(app, ["set-policy", "--tenant", "acme", "bot", "invalid-policy"])

        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "error" in result.output.lower()

    def test_set_policy_all_presets(self, runner, temp_tenant_dir):
        """Test setting all preset policies."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        for preset in ["monitor", "balanced", "strict"]:
            with patch(
                "raxe.cli.app.get_tenants_base_path",
                return_value=temp_tenant_dir,
            ):
                runner.invoke(
                    app,
                    [
                        "create",
                        "--tenant",
                        "acme",
                        "--name",
                        f"Bot {preset}",
                        "--id",
                        f"bot-{preset}",
                    ],
                )

                result = runner.invoke(
                    app, ["set-policy", "--tenant", "acme", f"bot-{preset}", preset]
                )

            assert result.exit_code == 0
            assert preset in result.output
