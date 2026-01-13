"""Tests for policy CLI commands."""

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


def _create_tenant(runner, temp_tenant_dir, tenant_id: str, name: str):
    """Helper to create a tenant for testing."""
    from raxe.cli.tenant import tenant as tenant_cmd

    with patch("raxe.cli.tenant.get_tenants_base_path", return_value=temp_tenant_dir):
        runner.invoke(tenant_cmd, ["create", "--name", name, "--id", tenant_id])


class TestPolicyPresets:
    """Tests for raxe policy presets command."""

    def test_list_presets_table(self, runner):
        """Test listing global presets in table format."""
        result = runner.invoke(policy, ["presets"])

        assert result.exit_code == 0
        assert "monitor" in result.output.lower()
        assert "balanced" in result.output.lower()
        assert "strict" in result.output.lower()

    def test_list_presets_json(self, runner):
        """Test listing global presets in JSON format."""
        result = runner.invoke(policy, ["presets", "--output", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 3
        policy_ids = {p["policy_id"] for p in data}
        assert policy_ids == {"monitor", "balanced", "strict"}


class TestPolicyList:
    """Tests for raxe policy list command."""

    def test_list_without_tenant_shows_presets(self, runner):
        """Test listing without tenant shows global presets."""
        result = runner.invoke(policy, ["list"])

        assert result.exit_code == 0
        assert "monitor" in result.output.lower() or "balanced" in result.output.lower()

    def test_list_with_tenant_empty(self, runner, temp_tenant_dir):
        """Test listing tenant policies when none exist."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            result = runner.invoke(policy, ["list", "--tenant", "acme"])

        assert result.exit_code == 0
        # Now shows available policies (presets + any custom)
        assert "available policies" in result.output.lower()
        # Should show preset policies
        assert "preset" in result.output.lower()
        assert "balanced" in result.output.lower()

    def test_list_with_tenant_has_policies(self, runner, temp_tenant_dir):
        """Test listing tenant policies when policies exist."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            # Create a custom policy
            runner.invoke(
                policy,
                ["create", "--tenant", "acme", "--mode", "strict", "--name", "High Security"],
            )
            result = runner.invoke(policy, ["list", "--tenant", "acme"])

        assert result.exit_code == 0
        assert "high security" in result.output.lower() or "strict" in result.output.lower()

    def test_list_json_output(self, runner, temp_tenant_dir):
        """Test listing policies with JSON output."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            runner.invoke(
                policy,
                ["create", "--tenant", "acme", "--mode", "strict", "--name", "High Security"],
            )
            result = runner.invoke(policy, ["list", "--tenant", "acme", "--output", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)


class TestPolicyCreate:
    """Tests for raxe policy create command."""

    def test_create_policy_success(self, runner, temp_tenant_dir):
        """Test creating a policy successfully."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            result = runner.invoke(
                policy,
                ["create", "--tenant", "acme", "--mode", "strict", "--name", "High Security"],
            )

        assert result.exit_code == 0
        assert "created" in result.output.lower() or "high security" in result.output.lower()

    def test_create_policy_with_custom_id(self, runner, temp_tenant_dir):
        """Test creating a policy with custom ID."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            result = runner.invoke(
                policy,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--mode",
                    "strict",
                    "--name",
                    "High Security",
                    "--id",
                    "high-sec",
                ],
            )

        assert result.exit_code == 0
        assert "high-sec" in result.output or "created" in result.output.lower()

    def test_create_policy_requires_tenant(self, runner, temp_tenant_dir):
        """Test that creating a policy requires tenant ID."""
        result = runner.invoke(
            policy,
            ["create", "--mode", "strict", "--name", "High Security"],
        )

        assert result.exit_code != 0
        assert "tenant" in result.output.lower() or "required" in result.output.lower()

    def test_create_policy_invalid_tenant(self, runner, temp_tenant_dir):
        """Test creating policy for non-existent tenant fails."""
        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            result = runner.invoke(
                policy,
                ["create", "--tenant", "nonexistent", "--mode", "strict", "--name", "Test"],
            )

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_create_policy_all_modes(self, runner, temp_tenant_dir):
        """Test creating policies with all valid modes."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        for mode in ["monitor", "balanced", "strict"]:
            with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
                result = runner.invoke(
                    policy,
                    [
                        "create",
                        "--tenant",
                        "acme",
                        "--mode",
                        mode,
                        "--name",
                        f"Test {mode}",
                        "--id",
                        f"test-{mode}",
                    ],
                )
            assert result.exit_code == 0, f"Failed for mode {mode}: {result.output}"


class TestPolicyShow:
    """Tests for raxe policy show command."""

    def test_show_preset_policy(self, runner):
        """Test showing a global preset policy."""
        result = runner.invoke(policy, ["show", "balanced"])

        assert result.exit_code == 0
        assert "balanced" in result.output.lower()

    def test_show_preset_policy_json(self, runner):
        """Test showing a global preset policy in JSON."""
        result = runner.invoke(policy, ["show", "strict", "--output", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["policy_id"] == "strict"
        assert data["mode"] == "strict"

    def test_show_tenant_policy(self, runner, temp_tenant_dir):
        """Test showing a tenant-specific policy."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            runner.invoke(
                policy,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--mode",
                    "strict",
                    "--name",
                    "High Security",
                    "--id",
                    "high-sec",
                ],
            )
            result = runner.invoke(policy, ["show", "high-sec", "--tenant", "acme"])

        assert result.exit_code == 0
        assert "high-sec" in result.output or "high security" in result.output.lower()

    def test_show_nonexistent_policy(self, runner):
        """Test showing a policy that doesn't exist."""
        result = runner.invoke(policy, ["show", "nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()


class TestPolicyDelete:
    """Tests for raxe policy delete command."""

    def test_delete_policy_success(self, runner, temp_tenant_dir):
        """Test deleting a policy successfully."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            runner.invoke(
                policy,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--mode",
                    "strict",
                    "--name",
                    "High Security",
                    "--id",
                    "high-sec",
                ],
            )
            result = runner.invoke(policy, ["delete", "high-sec", "--tenant", "acme", "--force"])

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    def test_delete_nonexistent_policy(self, runner, temp_tenant_dir):
        """Test deleting a policy that doesn't exist."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            result = runner.invoke(policy, ["delete", "nonexistent", "--tenant", "acme", "--force"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_delete_requires_tenant(self, runner):
        """Test that delete requires tenant ID."""
        result = runner.invoke(policy, ["delete", "some-policy", "--force"])

        assert result.exit_code != 0
        assert "tenant" in result.output.lower() or "required" in result.output.lower()

    def test_delete_requires_force_or_confirmation(self, runner, temp_tenant_dir):
        """Test that delete requires --force or confirmation."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            runner.invoke(
                policy,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--mode",
                    "strict",
                    "--name",
                    "High Security",
                    "--id",
                    "high-sec",
                ],
            )
            result = runner.invoke(policy, ["delete", "high-sec", "--tenant", "acme"], input="n\n")

        # Either prompts or requires --force
        assert (
            "abort" in result.output.lower()
            or result.exit_code == 1
            or "y/n" in result.output.lower()
        )

    def test_cannot_delete_global_preset(self, runner, temp_tenant_dir):
        """Test that global presets cannot be deleted."""
        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            result = runner.invoke(policy, ["delete", "balanced", "--tenant", "acme", "--force"])

        # Should fail - cannot delete global presets
        assert (
            result.exit_code != 0
            or "cannot" in result.output.lower()
            or "not found" in result.output.lower()
        )


class TestPolicyCreateCustomMode:
    """Tests for creating policies with custom mode."""

    def test_create_custom_policy_with_thresholds(self, runner, temp_tenant_dir):
        """Test creating a custom policy with explicit thresholds."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            result = runner.invoke(
                policy,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--mode",
                    "custom",
                    "--name",
                    "Custom Security Policy",
                    "--blocking",
                    "--severity-threshold",
                    "MEDIUM",
                    "--confidence-threshold",
                    "0.7",
                    "--l2",
                    "--l2-threshold",
                    "0.4",
                    "--telemetry",
                    "verbose",
                ],
            )

        assert result.exit_code == 0
        assert "created" in result.output.lower()
        assert "custom" in result.output.lower()

    def test_create_custom_policy_shows_thresholds(self, runner, temp_tenant_dir):
        """Test that custom policy shows all threshold values."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            result = runner.invoke(
                policy,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--mode",
                    "custom",
                    "--name",
                    "My Custom",
                    "--severity-threshold",
                    "MEDIUM",
                ],
            )

        assert result.exit_code == 0
        # Should show MEDIUM threshold since it's custom mode
        assert "MEDIUM" in result.output or "medium" in result.output.lower()

    def test_create_policy_custom_mode_included(self, runner):
        """Test that custom is a valid mode option."""
        # This should show help with custom as an option
        result = runner.invoke(policy, ["create", "--help"])
        assert "custom" in result.output.lower()

    def test_create_preset_ignores_threshold_options(self, runner, temp_tenant_dir):
        """Test that threshold options are ignored for preset modes with warning."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            result = runner.invoke(
                policy,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--mode",
                    "strict",
                    "--name",
                    "Strict But Custom Threshold",
                    "--severity-threshold",
                    "LOW",  # Should be ignored for strict mode
                ],
            )

        assert result.exit_code == 0
        # Should show warning about ignoring threshold options
        assert "warning" in result.output.lower() or "ignored" in result.output.lower()


class TestPolicyUpdate:
    """Tests for raxe policy update command."""

    def test_update_policy_success(self, runner, temp_tenant_dir):
        """Test updating a policy successfully."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            # Create policy first
            runner.invoke(
                policy,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--mode",
                    "balanced",
                    "--name",
                    "Test",
                    "--id",
                    "test-policy",
                ],
            )
            # Update it
            result = runner.invoke(
                policy,
                ["update", "test-policy", "--tenant", "acme", "--severity-threshold", "MEDIUM"],
            )

        assert result.exit_code == 0
        assert "updated" in result.output.lower()

    def test_update_policy_increments_version(self, runner, temp_tenant_dir):
        """Test that updating a policy increments its version."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            # Create policy
            runner.invoke(
                policy,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--mode",
                    "balanced",
                    "--name",
                    "Test",
                    "--id",
                    "ver-test",
                ],
            )
            # Update it
            result = runner.invoke(
                policy,
                ["update", "ver-test", "--tenant", "acme", "--name", "Updated Name"],
            )

        assert result.exit_code == 0
        # Should show version increment
        assert "1" in result.output and "2" in result.output  # version: 1 → 2

    def test_update_policy_changes_mode_to_custom(self, runner, temp_tenant_dir):
        """Test that updating thresholds changes mode to custom."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            runner.invoke(
                policy,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--mode",
                    "balanced",
                    "--name",
                    "Test",
                    "--id",
                    "mode-test",
                ],
            )
            result = runner.invoke(
                policy,
                ["update", "mode-test", "--tenant", "acme", "--severity-threshold", "LOW"],
            )

        assert result.exit_code == 0
        # Mode should change from balanced to custom
        assert "custom" in result.output.lower()

    def test_update_nonexistent_policy(self, runner, temp_tenant_dir):
        """Test updating a policy that doesn't exist."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            result = runner.invoke(
                policy,
                ["update", "nonexistent", "--tenant", "acme", "--name", "New Name"],
            )

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_cannot_update_global_preset(self, runner, temp_tenant_dir):
        """Test that global presets cannot be updated."""
        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            result = runner.invoke(
                policy,
                ["update", "balanced", "--tenant", "acme", "--name", "Modified Balanced"],
            )

        assert result.exit_code != 0
        assert "cannot" in result.output.lower()

    def test_update_requires_at_least_one_change(self, runner, temp_tenant_dir):
        """Test that update requires at least one option to change."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            runner.invoke(
                policy,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--mode",
                    "balanced",
                    "--name",
                    "Test",
                    "--id",
                    "no-change",
                ],
            )
            result = runner.invoke(
                policy,
                ["update", "no-change", "--tenant", "acme"],  # No changes specified
            )

        # Should warn or fail when no changes specified
        assert "warning" in result.output.lower() or result.exit_code != 0


class TestPolicyVersion:
    """Tests for policy version tracking."""

    def test_new_policy_has_version_1(self, runner, temp_tenant_dir):
        """Test that new policies start at version 1."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            runner.invoke(
                policy,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--mode",
                    "strict",
                    "--name",
                    "Test",
                    "--id",
                    "v1-test",
                ],
            )
            result = runner.invoke(
                policy, ["show", "v1-test", "--tenant", "acme", "--output", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["version"] == 1

    def test_policy_json_includes_version_fields(self, runner, temp_tenant_dir):
        """Test that policy JSON includes version, created_at, updated_at."""
        _create_tenant(runner, temp_tenant_dir, "acme", "Acme Corp")

        with patch("raxe.cli.policy.get_tenants_base_path", return_value=temp_tenant_dir):
            runner.invoke(
                policy,
                [
                    "create",
                    "--tenant",
                    "acme",
                    "--mode",
                    "strict",
                    "--name",
                    "Test",
                    "--id",
                    "fields-test",
                ],
            )
            result = runner.invoke(
                policy, ["show", "fields-test", "--tenant", "acme", "--output", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "version" in data
        assert "created_at" in data
        assert "updated_at" in data
