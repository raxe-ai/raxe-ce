"""End-to-end integration tests for OpenClaw integration.

Tests the complete install/uninstall/status cycle:
- Install creates all required files and config entries
- Status correctly reports state
- Uninstall cleanly removes all artifacts
- Edge cases like partial installs are handled

These tests use real file system operations (in temp directories) to verify
end-to-end functionality.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from raxe.infrastructure.openclaw import (
    ConfigLoadError,
    OpenClawConfigManager,
    OpenClawHookManager,
)
from raxe.infrastructure.openclaw.models import OpenClawPaths


@pytest.fixture
def openclaw_home(tmp_path: Path) -> Path:
    """Create a mock ~/.openclaw directory structure.

    Returns:
        Path to the openclaw directory
    """
    openclaw_dir = tmp_path / ".openclaw"
    openclaw_dir.mkdir()

    # Create hooks directory
    hooks_dir = openclaw_dir / "hooks"
    hooks_dir.mkdir()

    # Create minimal openclaw.json config
    config_file = openclaw_dir / "openclaw.json"
    config_file.write_text(
        json.dumps(
            {
                "hooks": {
                    "internal": {
                        "enabled": True,
                        "entries": {
                            "existing-hook": {"enabled": True},
                        },
                    }
                },
                "other_settings": {"key": "value"},
            },
            indent=2,
        )
    )

    return openclaw_dir


class TestFullInstallUninstallCycle:
    """Test complete install/uninstall workflow."""

    def test_install_creates_all_required_artifacts(self, openclaw_home: Path):
        """Test that install creates all required files and config entries."""
        paths = OpenClawPaths(openclaw_dir=openclaw_home)
        config_manager = OpenClawConfigManager(paths)
        hook_manager = OpenClawHookManager(paths)

        # Verify initial state
        assert not config_manager.is_raxe_configured()
        assert not hook_manager.hook_files_exist()

        # Install
        hook_manager.install_hook_files()
        config_manager.add_raxe_hook_entry()

        # Verify all artifacts created
        assert paths.raxe_hook_dir.exists()
        assert paths.handler_file.exists()
        assert paths.hook_md_file.exists()
        assert config_manager.is_raxe_configured()

        # Verify handler.ts content
        handler_content = paths.handler_file.read_text()
        assert "handler" in handler_content.lower()
        assert "scanMessage" in handler_content or "scan" in handler_content.lower()

        # Verify HOOK.md content
        hook_md_content = paths.hook_md_file.read_text()
        assert "RAXE" in hook_md_content
        assert "Security" in hook_md_content or "security" in hook_md_content.lower()

    def test_uninstall_removes_all_artifacts(self, openclaw_home: Path):
        """Test that uninstall removes all files and config entries."""
        paths = OpenClawPaths(openclaw_dir=openclaw_home)
        config_manager = OpenClawConfigManager(paths)
        hook_manager = OpenClawHookManager(paths)

        # Install first
        hook_manager.install_hook_files()
        config_manager.add_raxe_hook_entry()

        # Verify installed
        assert config_manager.is_raxe_configured()
        assert hook_manager.hook_files_exist()

        # Uninstall
        hook_manager.remove_hook_files()
        config_manager.remove_raxe_hook_entry()

        # Verify all artifacts removed
        assert not paths.raxe_hook_dir.exists()
        assert not config_manager.is_raxe_configured()
        assert not hook_manager.hook_files_exist()

    def test_install_preserves_existing_hooks(self, openclaw_home: Path):
        """Test that install doesn't affect existing hooks."""
        paths = OpenClawPaths(openclaw_dir=openclaw_home)
        config_manager = OpenClawConfigManager(paths)
        hook_manager = OpenClawHookManager(paths)

        # Install RAXE
        hook_manager.install_hook_files()
        config_manager.add_raxe_hook_entry()

        # Verify existing hook is preserved
        config = config_manager.load_config()
        entries = config["hooks"]["internal"]["entries"]
        assert "existing-hook" in entries
        assert "raxe-security" in entries

    def test_uninstall_preserves_existing_hooks(self, openclaw_home: Path):
        """Test that uninstall doesn't affect existing hooks."""
        paths = OpenClawPaths(openclaw_dir=openclaw_home)
        config_manager = OpenClawConfigManager(paths)
        hook_manager = OpenClawHookManager(paths)

        # Install then uninstall
        hook_manager.install_hook_files()
        config_manager.add_raxe_hook_entry()
        hook_manager.remove_hook_files()
        config_manager.remove_raxe_hook_entry()

        # Verify existing hook is preserved
        config = config_manager.load_config()
        entries = config["hooks"]["internal"]["entries"]
        assert "existing-hook" in entries
        assert entries["existing-hook"]["enabled"] is True

    def test_reinstall_overwrites_existing(self, openclaw_home: Path):
        """Test that reinstall properly overwrites existing installation."""
        paths = OpenClawPaths(openclaw_dir=openclaw_home)
        config_manager = OpenClawConfigManager(paths)
        hook_manager = OpenClawHookManager(paths)

        # First install
        hook_manager.install_hook_files()
        config_manager.add_raxe_hook_entry()

        # Modify handler file
        paths.handler_file.write_text("// modified")

        # Reinstall
        hook_manager.install_hook_files()

        # Verify file was restored
        handler_content = paths.handler_file.read_text()
        assert "scanMessage" in handler_content or "handler" in handler_content.lower()


class TestPartialInstallRecovery:
    """Test handling of partial/corrupted installations."""

    def test_status_detects_partial_install_config_only(self, openclaw_home: Path):
        """Test detection of config-only partial install."""
        paths = OpenClawPaths(openclaw_dir=openclaw_home)
        config_manager = OpenClawConfigManager(paths)
        hook_manager = OpenClawHookManager(paths)

        # Add config entry without files
        config_manager.add_raxe_hook_entry()

        # Status should show mismatch
        assert config_manager.is_raxe_configured()
        assert not hook_manager.hook_files_exist()

    def test_status_detects_partial_install_files_only(self, openclaw_home: Path):
        """Test detection of files-only partial install."""
        paths = OpenClawPaths(openclaw_dir=openclaw_home)
        config_manager = OpenClawConfigManager(paths)
        hook_manager = OpenClawHookManager(paths)

        # Create files without config entry
        hook_manager.install_hook_files()

        # Status should show mismatch
        assert not config_manager.is_raxe_configured()
        assert hook_manager.hook_files_exist()

    def test_force_install_fixes_partial(self, openclaw_home: Path):
        """Test that force install fixes partial installation."""
        paths = OpenClawPaths(openclaw_dir=openclaw_home)
        config_manager = OpenClawConfigManager(paths)
        hook_manager = OpenClawHookManager(paths)

        # Create partial install (files only)
        hook_manager.install_hook_files()

        # Force reinstall (simulated by running both operations)
        hook_manager.install_hook_files()
        config_manager.add_raxe_hook_entry()

        # Should be fully installed now
        assert config_manager.is_raxe_configured()
        assert hook_manager.hook_files_exist()


class TestBackupAndRecovery:
    """Test config backup functionality."""

    def test_backup_creates_timestamped_copy(self, openclaw_home: Path):
        """Test that backup creates a timestamped copy of config."""
        paths = OpenClawPaths(openclaw_dir=openclaw_home)
        config_manager = OpenClawConfigManager(paths)

        # Create backup
        backup_path = config_manager.backup_config()

        # Verify backup exists
        assert backup_path.exists()
        assert "backup" in backup_path.name
        assert backup_path.suffix.startswith(".json") or ".backup." in backup_path.name

        # Verify backup content matches original
        original_content = paths.config_file.read_text()
        backup_content = backup_path.read_text()
        assert original_content == backup_content

    def test_backup_before_install(self, openclaw_home: Path):
        """Test that backup preserves original config before install."""
        paths = OpenClawPaths(openclaw_dir=openclaw_home)
        config_manager = OpenClawConfigManager(paths)

        # Backup then install
        backup_path = config_manager.backup_config()
        config_manager.add_raxe_hook_entry()

        # Verify backup has original (without raxe-security)
        backup_content = json.loads(backup_path.read_text())
        assert "raxe-security" not in backup_content["hooks"]["internal"]["entries"]

        # Verify current has raxe-security
        current_config = config_manager.load_config()
        assert "raxe-security" in current_config["hooks"]["internal"]["entries"]


class TestOpenClawNotInstalled:
    """Test behavior when OpenClaw is not installed."""

    def test_is_openclaw_installed_returns_false(self, tmp_path: Path):
        """Test detection of missing OpenClaw."""
        paths = OpenClawPaths(openclaw_dir=tmp_path / ".openclaw")

        # Don't create the directory
        config_manager = OpenClawConfigManager(paths)

        assert not config_manager.is_openclaw_installed()

    def test_load_config_raises_on_missing(self, tmp_path: Path):
        """Test that load_config raises when config is missing."""
        paths = OpenClawPaths(openclaw_dir=tmp_path / ".openclaw")
        config_manager = OpenClawConfigManager(paths)

        with pytest.raises(ConfigLoadError):
            config_manager.load_config()

    def test_is_raxe_configured_returns_false(self, tmp_path: Path):
        """Test that is_raxe_configured returns False when OpenClaw missing."""
        paths = OpenClawPaths(openclaw_dir=tmp_path / ".openclaw")
        config_manager = OpenClawConfigManager(paths)

        # Should return False, not raise
        assert not config_manager.is_raxe_configured()
