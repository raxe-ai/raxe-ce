"""Tests for tenant-scoped suppression CLI commands."""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from raxe.cli.suppress import suppress


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


class TestSuppressTenantScoped:
    """Tests for tenant-scoped suppression commands."""

    def test_add_suppression_with_tenant(self, runner, temp_tenant_dir):
        """Test adding a suppression for a specific tenant."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with (
            patch(
                "raxe.cli.suppress._get_tenant_suppression_path",
                return_value=temp_tenant_dir / "acme" / "suppressions.yaml",
            ),
            patch(
                "raxe.cli.suppress._verify_tenant_exists",
                return_value=True,
            ),
        ):
            result = runner.invoke(
                suppress,
                [
                    "add",
                    "pi-001",
                    "--reason",
                    "False positive in auth",
                    "--tenant",
                    "acme",
                ],
            )

        assert result.exit_code == 0
        assert "pi-001" in result.output or "Added" in result.output

    def test_add_suppression_nonexistent_tenant_fails(self, runner, temp_tenant_dir):
        """Test that adding suppression for non-existent tenant fails."""
        with patch(
            "raxe.cli.suppress._verify_tenant_exists",
            return_value=False,
        ):
            result = runner.invoke(
                suppress,
                [
                    "add",
                    "pi-001",
                    "--reason",
                    "Test",
                    "--tenant",
                    "nonexistent",
                ],
            )

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_list_suppressions_with_tenant(self, runner, temp_tenant_dir):
        """Test listing suppressions for a specific tenant."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        # Create suppression file
        suppression_dir = temp_tenant_dir / "acme"
        suppression_dir.mkdir(parents=True, exist_ok=True)

        with (
            patch(
                "raxe.cli.suppress._get_tenant_suppression_path",
                return_value=temp_tenant_dir / "acme" / "suppressions.yaml",
            ),
            patch(
                "raxe.cli.suppress._verify_tenant_exists",
                return_value=True,
            ),
        ):
            # First add a suppression
            runner.invoke(
                suppress,
                [
                    "add",
                    "pi-001",
                    "--reason",
                    "Test suppression",
                    "--tenant",
                    "acme",
                ],
            )
            # Then list
            result = runner.invoke(suppress, ["list", "--tenant", "acme"])

        assert result.exit_code == 0

    def test_list_suppressions_with_tenant_json(self, runner, temp_tenant_dir):
        """Test listing tenant suppressions in JSON format."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with (
            patch(
                "raxe.cli.suppress._get_tenant_suppression_path",
                return_value=temp_tenant_dir / "acme" / "suppressions.yaml",
            ),
            patch(
                "raxe.cli.suppress._verify_tenant_exists",
                return_value=True,
            ),
        ):
            # Add a suppression
            runner.invoke(
                suppress,
                [
                    "add",
                    "pi-001",
                    "--reason",
                    "Test suppression",
                    "--tenant",
                    "acme",
                ],
            )
            # List in JSON
            result = runner.invoke(suppress, ["list", "--tenant", "acme", "--output", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_remove_suppression_with_tenant(self, runner, temp_tenant_dir):
        """Test removing a suppression for a specific tenant."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with (
            patch(
                "raxe.cli.suppress._get_tenant_suppression_path",
                return_value=temp_tenant_dir / "acme" / "suppressions.yaml",
            ),
            patch(
                "raxe.cli.suppress._verify_tenant_exists",
                return_value=True,
            ),
        ):
            # Add then remove
            runner.invoke(
                suppress,
                [
                    "add",
                    "pi-001",
                    "--reason",
                    "Test suppression",
                    "--tenant",
                    "acme",
                ],
            )
            result = runner.invoke(suppress, ["remove", "pi-001", "--tenant", "acme"])

        assert result.exit_code == 0

    def test_show_suppression_with_tenant(self, runner, temp_tenant_dir):
        """Test showing suppression details for a specific tenant."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with (
            patch(
                "raxe.cli.suppress._get_tenant_suppression_path",
                return_value=temp_tenant_dir / "acme" / "suppressions.yaml",
            ),
            patch(
                "raxe.cli.suppress._verify_tenant_exists",
                return_value=True,
            ),
        ):
            # Add then show
            runner.invoke(
                suppress,
                [
                    "add",
                    "pi-001",
                    "--reason",
                    "Test suppression",
                    "--tenant",
                    "acme",
                ],
            )
            result = runner.invoke(suppress, ["show", "pi-001", "--tenant", "acme"])

        assert result.exit_code == 0
        assert "pi-001" in result.output

    def test_stats_with_tenant(self, runner, temp_tenant_dir):
        """Test suppression stats for a specific tenant."""
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")

        with (
            patch(
                "raxe.cli.suppress._get_tenant_suppression_path",
                return_value=temp_tenant_dir / "acme" / "suppressions.yaml",
            ),
            patch(
                "raxe.cli.suppress._verify_tenant_exists",
                return_value=True,
            ),
        ):
            result = runner.invoke(suppress, ["stats", "--tenant", "acme"])

        # Stats should work even with no suppressions
        assert result.exit_code == 0


class TestSuppressTenantIsolation:
    """Tests for verifying tenant isolation of suppressions."""

    def test_tenant_suppressions_are_isolated(self, runner, temp_tenant_dir):
        """Test that tenant A's suppressions don't affect tenant B."""
        _create_tenant(temp_tenant_dir, "tenant-a", "Tenant A")
        _create_tenant(temp_tenant_dir, "tenant-b", "Tenant B")

        def mock_path(tenant_id):
            return temp_tenant_dir / tenant_id / "suppressions.yaml"

        with patch(
            "raxe.cli.suppress._verify_tenant_exists",
            return_value=True,
        ):
            # Add suppression to tenant A
            with patch(
                "raxe.cli.suppress._get_suppression_config_path",
                side_effect=lambda c, t: mock_path(t) if t else None,
            ):
                runner.invoke(
                    suppress,
                    [
                        "add",
                        "pi-001",
                        "--reason",
                        "Tenant A suppression",
                        "--tenant",
                        "tenant-a",
                    ],
                )

                # List tenant B suppressions - should be empty or not contain pi-001
                result = runner.invoke(
                    suppress, ["list", "--tenant", "tenant-b", "--output", "json"]
                )

        assert result.exit_code == 0
        # Tenant B should have empty list or not have pi-001
        if result.output.strip():
            try:
                data = json.loads(result.output)
                patterns = [s.get("pattern") for s in data] if data else []
                assert "pi-001" not in patterns
            except json.JSONDecodeError:
                # Output might be "No suppressions" message
                pass
