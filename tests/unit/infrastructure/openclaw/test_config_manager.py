"""Tests for OpenClaw config manager.

TDD: These tests define expected behavior for OpenClaw config file management.
"""

import json
from pathlib import Path

import pytest


@pytest.fixture
def mock_openclaw_path(tmp_path):
    """Create a mock OpenClaw directory structure."""
    openclaw_dir = tmp_path / ".openclaw"
    openclaw_dir.mkdir()
    hooks_dir = openclaw_dir / "hooks"
    hooks_dir.mkdir()
    return openclaw_dir


@pytest.fixture
def valid_config():
    """Create a valid OpenClaw config."""
    return {
        "hooks": {
            "internal": {
                "enabled": True,
                "entries": {},
            }
        }
    }


class TestOpenClawConfigManager:
    """Tests for OpenClawConfigManager."""

    def test_is_openclaw_installed_true_when_config_exists(self, mock_openclaw_path, valid_config):
        """Test detecting OpenClaw installation when config exists."""
        from raxe.infrastructure.openclaw.config_manager import OpenClawConfigManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        # Create config file
        config_file = mock_openclaw_path / "openclaw.json"
        config_file.write_text(json.dumps(valid_config))

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawConfigManager(paths)

        assert manager.is_openclaw_installed() is True

    def test_is_openclaw_installed_false_when_missing(self, tmp_path):
        """Test detecting OpenClaw is not installed when config missing."""
        from raxe.infrastructure.openclaw.config_manager import OpenClawConfigManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths(openclaw_dir=tmp_path / "nonexistent")
        manager = OpenClawConfigManager(paths)

        assert manager.is_openclaw_installed() is False

    def test_load_config_parses_json(self, mock_openclaw_path, valid_config):
        """Test loading config parses JSON correctly."""
        from raxe.infrastructure.openclaw.config_manager import OpenClawConfigManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        config_file = mock_openclaw_path / "openclaw.json"
        config_file.write_text(json.dumps(valid_config))

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawConfigManager(paths)
        config = manager.load_config()

        assert config is not None
        assert config["hooks"]["internal"]["enabled"] is True

    def test_load_config_handles_invalid_json(self, mock_openclaw_path):
        """Test loading config handles invalid JSON gracefully."""
        from raxe.infrastructure.openclaw.config_manager import (
            ConfigLoadError,
            OpenClawConfigManager,
        )
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        config_file = mock_openclaw_path / "openclaw.json"
        config_file.write_text("{ invalid json }")

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawConfigManager(paths)

        with pytest.raises(ConfigLoadError):
            manager.load_config()

    def test_backup_config_creates_timestamped_file(self, mock_openclaw_path, valid_config):
        """Test backup creates timestamped backup file."""
        from raxe.infrastructure.openclaw.config_manager import OpenClawConfigManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        config_file = mock_openclaw_path / "openclaw.json"
        config_file.write_text(json.dumps(valid_config))

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawConfigManager(paths)

        backup_path = manager.backup_config()

        assert backup_path.exists()
        assert "openclaw.json.backup" in backup_path.name
        # Backup should contain original content
        assert json.loads(backup_path.read_text()) == valid_config

    def test_add_raxe_hook_entry_preserves_existing(self, mock_openclaw_path, valid_config):
        """Test adding RAXE hook preserves existing hooks."""
        from raxe.infrastructure.openclaw.config_manager import OpenClawConfigManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        # Add an existing hook
        valid_config["hooks"]["internal"]["entries"]["existing-hook"] = {"enabled": True}
        config_file = mock_openclaw_path / "openclaw.json"
        config_file.write_text(json.dumps(valid_config))

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawConfigManager(paths)
        manager.add_raxe_hook_entry()

        # Reload and verify
        new_config = json.loads(config_file.read_text())
        entries = new_config["hooks"]["internal"]["entries"]

        assert "existing-hook" in entries
        assert "raxe-security" in entries
        assert entries["raxe-security"]["enabled"] is True

    def test_remove_raxe_hook_entry(self, mock_openclaw_path, valid_config):
        """Test removing RAXE hook entry."""
        from raxe.infrastructure.openclaw.config_manager import OpenClawConfigManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        # Add RAXE hook
        valid_config["hooks"]["internal"]["entries"]["raxe-security"] = {"enabled": True}
        config_file = mock_openclaw_path / "openclaw.json"
        config_file.write_text(json.dumps(valid_config))

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawConfigManager(paths)
        manager.remove_raxe_hook_entry()

        # Reload and verify
        new_config = json.loads(config_file.read_text())
        entries = new_config["hooks"]["internal"]["entries"]

        assert "raxe-security" not in entries

    def test_is_raxe_configured_true(self, mock_openclaw_path, valid_config):
        """Test is_raxe_configured returns true when configured."""
        from raxe.infrastructure.openclaw.config_manager import OpenClawConfigManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        valid_config["hooks"]["internal"]["entries"]["raxe-security"] = {"enabled": True}
        config_file = mock_openclaw_path / "openclaw.json"
        config_file.write_text(json.dumps(valid_config))

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawConfigManager(paths)

        assert manager.is_raxe_configured() is True

    def test_is_raxe_configured_false(self, mock_openclaw_path, valid_config):
        """Test is_raxe_configured returns false when not configured."""
        from raxe.infrastructure.openclaw.config_manager import OpenClawConfigManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        config_file = mock_openclaw_path / "openclaw.json"
        config_file.write_text(json.dumps(valid_config))

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawConfigManager(paths)

        assert manager.is_raxe_configured() is False

    def test_save_config(self, mock_openclaw_path, valid_config):
        """Test saving config writes JSON correctly."""
        from raxe.infrastructure.openclaw.config_manager import OpenClawConfigManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        config_file = mock_openclaw_path / "openclaw.json"
        config_file.write_text(json.dumps(valid_config))

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawConfigManager(paths)

        # Modify and save
        valid_config["hooks"]["internal"]["entries"]["test"] = {"enabled": True}
        manager.save_config(valid_config)

        # Verify
        saved = json.loads(config_file.read_text())
        assert saved["hooks"]["internal"]["entries"]["test"]["enabled"] is True
