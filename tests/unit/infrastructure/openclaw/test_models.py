"""Tests for OpenClaw infrastructure models.

TDD: These tests define expected behavior for OpenClaw path resolution.
"""

import os
from pathlib import Path

import pytest


class TestOpenClawPaths:
    """Tests for OpenClawPaths dataclass."""

    def test_default_paths_use_home_dir(self, monkeypatch):
        """Test that default paths are based on home directory."""
        # Set a known home directory
        monkeypatch.setenv("HOME", "/home/testuser")

        from importlib import reload

        import raxe.infrastructure.openclaw.models as models

        reload(models)  # Reload to pick up new HOME

        paths = models.OpenClawPaths()

        # Should use ~/.openclaw as base
        assert str(paths.openclaw_dir).endswith(".openclaw")

    def test_paths_resolve_to_absolute(self):
        """Test that all paths resolve to absolute paths."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths()

        assert paths.openclaw_dir.is_absolute()
        assert paths.config_file.is_absolute()
        assert paths.hooks_dir.is_absolute()
        assert paths.raxe_hook_dir.is_absolute()

    def test_raxe_hook_dir_inside_hooks_dir(self):
        """Test that RAXE hook directory is inside hooks directory."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths()

        # raxe_hook_dir should be a subdirectory of hooks_dir
        assert str(paths.raxe_hook_dir).startswith(str(paths.hooks_dir))
        assert paths.raxe_hook_dir.name == "raxe-security"

    def test_handler_file_path(self):
        """Test handler.ts file path is correctly computed."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths()

        assert paths.handler_file.parent == paths.raxe_hook_dir
        assert paths.handler_file.name == "handler.ts"

    def test_hook_md_file_path(self):
        """Test HOOK.md file path is correctly computed."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths()

        assert paths.hook_md_file.parent == paths.raxe_hook_dir
        assert paths.hook_md_file.name == "HOOK.md"

    def test_package_json_file_path(self):
        """Test package.json file path is correctly computed."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths()

        assert paths.package_json_file.parent == paths.raxe_hook_dir
        assert paths.package_json_file.name == "package.json"

    def test_custom_base_path(self, tmp_path):
        """Test that a custom base path can be provided."""
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        custom_base = tmp_path / ".openclaw-test"
        paths = OpenClawPaths(openclaw_dir=custom_base)

        assert paths.openclaw_dir == custom_base
        assert paths.config_file == custom_base / "openclaw.json"
        assert paths.hooks_dir == custom_base / "hooks"

    def test_openclaw_home_env_var(self, monkeypatch, tmp_path):
        """Test that OPENCLAW_HOME environment variable is respected."""
        custom_home = tmp_path / "custom-openclaw"
        monkeypatch.setenv("OPENCLAW_HOME", str(custom_home))

        from importlib import reload

        import raxe.infrastructure.openclaw.models as models

        reload(models)  # Reload to pick up new env var

        paths = models.OpenClawPaths()

        assert paths.openclaw_dir == custom_home
        assert paths.config_file == custom_home / "openclaw.json"
        assert paths.hooks_dir == custom_home / "hooks"


class TestOpenClawConfig:
    """Tests for OpenClawConfig dataclass."""

    def test_default_config_values(self):
        """Test default configuration values."""
        from raxe.infrastructure.openclaw.models import OpenClawConfig

        config = OpenClawConfig()

        assert config.hooks is not None
        assert config.hooks.get("internal", {}).get("enabled") is True

    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        from raxe.infrastructure.openclaw.models import OpenClawConfig

        data = {
            "hooks": {
                "internal": {
                    "enabled": True,
                    "entries": {
                        "some-hook": {"enabled": True},
                    },
                }
            }
        }

        config = OpenClawConfig.from_dict(data)

        assert config.hooks["internal"]["entries"]["some-hook"]["enabled"] is True

    def test_config_to_dict(self):
        """Test converting config to dictionary."""
        from raxe.infrastructure.openclaw.models import OpenClawConfig

        config = OpenClawConfig()
        data = config.to_dict()

        assert isinstance(data, dict)
        assert "hooks" in data
