"""Tests for OpenClaw CLI commands.

TDD: These tests define expected behavior for OpenClaw integration commands.
"""

import importlib
import json

import pytest
from click.testing import CliRunner


@pytest.fixture
def openclaw_module():
    """Import the openclaw CLI module dynamically."""
    return importlib.import_module("raxe.cli.openclaw")


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_openclaw_path(tmp_path):
    """Create a mock OpenClaw directory structure."""
    openclaw_dir = tmp_path / ".openclaw"
    openclaw_dir.mkdir()
    hooks_dir = openclaw_dir / "hooks"
    hooks_dir.mkdir()

    # Create a minimal openclaw.json config
    config_file = openclaw_dir / "openclaw.json"
    config_file.write_text(
        json.dumps(
            {
                "hooks": {
                    "internal": {
                        "enabled": True,
                        "entries": {},
                    }
                }
            },
            indent=2,
        )
    )

    return openclaw_dir


class TestOpenClawCommandRegistration:
    """Tests for OpenClaw command registration."""

    def test_openclaw_command_registered(self, openclaw_module):
        """Test that openclaw command group is registered."""
        assert hasattr(openclaw_module, "openclaw")
        assert openclaw_module.openclaw is not None

    def test_install_subcommand_available(self, openclaw_module, runner):
        """Test that install subcommand is available."""
        result = runner.invoke(openclaw_module.openclaw, ["install", "--help"])
        assert result.exit_code == 0
        assert "install" in result.output.lower() or "Install" in result.output

    def test_uninstall_subcommand_available(self, openclaw_module, runner):
        """Test that uninstall subcommand is available."""
        result = runner.invoke(openclaw_module.openclaw, ["uninstall", "--help"])
        assert result.exit_code == 0
        assert "uninstall" in result.output.lower() or "Uninstall" in result.output

    def test_status_subcommand_available(self, openclaw_module, runner):
        """Test that status subcommand is available."""
        result = runner.invoke(openclaw_module.openclaw, ["status", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output.lower() or "Status" in result.output


class TestOpenClawInstall:
    """Tests for openclaw install command."""

    def test_install_success(self, openclaw_module, runner, mock_openclaw_path, monkeypatch):
        """Test successful installation."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        # Monkeypatch the factory function
        monkeypatch.setattr(
            openclaw_module,
            "_get_openclaw_paths",
            lambda: OpenClawPaths(openclaw_dir=mock_openclaw_path),
        )

        result = runner.invoke(openclaw_module.openclaw, ["install"])

        assert result.exit_code == 0
        # Should show success message
        assert "success" in result.output.lower() or "installed" in result.output.lower()

        # Verify hook files were created
        raxe_hook_dir = mock_openclaw_path / "hooks" / "raxe-security"
        assert raxe_hook_dir.exists()
        assert (raxe_hook_dir / "handler.ts").exists()
        assert (raxe_hook_dir / "HOOK.md").exists()

        # Verify config was updated
        config = json.loads((mock_openclaw_path / "openclaw.json").read_text())
        assert "raxe-security" in config["hooks"]["internal"]["entries"]

    def test_install_openclaw_not_found_shows_error(
        self, openclaw_module, runner, tmp_path, monkeypatch
    ):
        """Test error when OpenClaw is not installed."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        # Point to empty directory (no openclaw.json)
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.setattr(
            openclaw_module,
            "_get_openclaw_paths",
            lambda: OpenClawPaths(openclaw_dir=empty_dir),
        )

        result = runner.invoke(openclaw_module.openclaw, ["install"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "not installed" in result.output.lower()

    def test_install_already_configured_without_force(
        self, openclaw_module, runner, mock_openclaw_path, monkeypatch
    ):
        """Test install when already configured (without --force)."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        monkeypatch.setattr(
            openclaw_module,
            "_get_openclaw_paths",
            lambda: OpenClawPaths(openclaw_dir=mock_openclaw_path),
        )

        # First install
        runner.invoke(openclaw_module.openclaw, ["install"])

        # Second install without force
        result = runner.invoke(openclaw_module.openclaw, ["install"])

        assert result.exit_code != 0
        assert "already" in result.output.lower()

    def test_install_force_overwrites(
        self, openclaw_module, runner, mock_openclaw_path, monkeypatch
    ):
        """Test install with --force overwrites existing configuration."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        monkeypatch.setattr(
            openclaw_module,
            "_get_openclaw_paths",
            lambda: OpenClawPaths(openclaw_dir=mock_openclaw_path),
        )

        # First install
        runner.invoke(openclaw_module.openclaw, ["install"])

        # Second install with force
        result = runner.invoke(openclaw_module.openclaw, ["install", "--force"])

        assert result.exit_code == 0
        assert "success" in result.output.lower() or "installed" in result.output.lower()


class TestOpenClawUninstall:
    """Tests for openclaw uninstall command."""

    def test_uninstall_success(self, openclaw_module, runner, mock_openclaw_path, monkeypatch):
        """Test successful uninstallation."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        monkeypatch.setattr(
            openclaw_module,
            "_get_openclaw_paths",
            lambda: OpenClawPaths(openclaw_dir=mock_openclaw_path),
        )

        # First install
        runner.invoke(openclaw_module.openclaw, ["install"])

        # Then uninstall (with --force to skip confirmation)
        result = runner.invoke(openclaw_module.openclaw, ["uninstall", "--force"])

        assert result.exit_code == 0
        assert (
            "success" in result.output.lower()
            or "removed" in result.output.lower()
            or "uninstalled" in result.output.lower()
        )

        # Verify hook files were removed
        raxe_hook_dir = mock_openclaw_path / "hooks" / "raxe-security"
        assert not raxe_hook_dir.exists()

        # Verify config was updated
        config = json.loads((mock_openclaw_path / "openclaw.json").read_text())
        assert "raxe-security" not in config["hooks"]["internal"]["entries"]

    def test_uninstall_not_configured_shows_info(
        self, openclaw_module, runner, mock_openclaw_path, monkeypatch
    ):
        """Test uninstall when not configured shows informational message."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        monkeypatch.setattr(
            openclaw_module,
            "_get_openclaw_paths",
            lambda: OpenClawPaths(openclaw_dir=mock_openclaw_path),
        )

        # Don't install, just try to uninstall
        result = runner.invoke(openclaw_module.openclaw, ["uninstall", "--force"])

        # Should succeed but show info that it wasn't configured
        assert result.exit_code == 0
        assert "not" in result.output.lower()

    def test_uninstall_prompts_for_confirmation(
        self, openclaw_module, runner, mock_openclaw_path, monkeypatch
    ):
        """Test uninstall prompts for confirmation without --force."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        monkeypatch.setattr(
            openclaw_module,
            "_get_openclaw_paths",
            lambda: OpenClawPaths(openclaw_dir=mock_openclaw_path),
        )

        # Install first
        runner.invoke(openclaw_module.openclaw, ["install"])

        # Try to uninstall without --force, answer no
        result = runner.invoke(openclaw_module.openclaw, ["uninstall"], input="n\n")

        # Should abort
        assert result.exit_code != 0 or "abort" in result.output.lower()


class TestOpenClawStatus:
    """Tests for openclaw status command."""

    def test_status_not_installed(self, openclaw_module, runner, tmp_path, monkeypatch):
        """Test status when OpenClaw is not installed."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.setattr(
            openclaw_module,
            "_get_openclaw_paths",
            lambda: OpenClawPaths(openclaw_dir=empty_dir),
        )

        result = runner.invoke(openclaw_module.openclaw, ["status"])

        assert result.exit_code == 0
        assert "not installed" in result.output.lower() or "not found" in result.output.lower()

    def test_status_configured(self, openclaw_module, runner, mock_openclaw_path, monkeypatch):
        """Test status when RAXE is configured."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        monkeypatch.setattr(
            openclaw_module,
            "_get_openclaw_paths",
            lambda: OpenClawPaths(openclaw_dir=mock_openclaw_path),
        )

        # Install first
        runner.invoke(openclaw_module.openclaw, ["install"])

        # Check status
        result = runner.invoke(openclaw_module.openclaw, ["status"])

        assert result.exit_code == 0
        assert "installed" in result.output.lower() or "enabled" in result.output.lower()

    def test_status_not_configured(self, openclaw_module, runner, mock_openclaw_path, monkeypatch):
        """Test status when OpenClaw exists but RAXE is not configured."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        monkeypatch.setattr(
            openclaw_module,
            "_get_openclaw_paths",
            lambda: OpenClawPaths(openclaw_dir=mock_openclaw_path),
        )

        # Don't install, just check status
        result = runner.invoke(openclaw_module.openclaw, ["status"])

        assert result.exit_code == 0
        assert "not" in result.output.lower()

    def test_status_json_output(self, openclaw_module, runner, mock_openclaw_path, monkeypatch):
        """Test status with --json output."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        monkeypatch.setattr(
            openclaw_module,
            "_get_openclaw_paths",
            lambda: OpenClawPaths(openclaw_dir=mock_openclaw_path),
        )

        # Install first
        runner.invoke(openclaw_module.openclaw, ["install"])

        # Check status with JSON output
        result = runner.invoke(openclaw_module.openclaw, ["status", "--json"])

        assert result.exit_code == 0
        # Should be valid JSON
        data = json.loads(result.output)
        assert "openclaw_installed" in data
        assert "raxe_configured" in data
        assert data["raxe_configured"] is True
