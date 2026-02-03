"""OpenClaw config file manager.

Handles reading, writing, and modifying the openclaw.json config file.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from raxe.infrastructure.openclaw.models import OpenClawPaths


class ConfigLoadError(Exception):
    """Error loading OpenClaw configuration."""

    pass


class OpenClawConfigManager:
    """Manager for OpenClaw configuration file.

    Handles reading, writing, and modifying openclaw.json,
    with support for backup and rollback operations.
    """

    RAXE_HOOK_NAME = "raxe-security"

    def __init__(self, paths: OpenClawPaths | None = None) -> None:
        """Initialize config manager.

        Args:
            paths: OpenClawPaths instance (uses defaults if None)
        """
        self.paths = paths or OpenClawPaths()

    def is_openclaw_installed(self) -> bool:
        """Check if OpenClaw is installed.

        Returns:
            True if openclaw.json config file exists
        """
        return self.paths.config_file.exists()

    def load_config(self) -> dict[str, Any]:
        """Load OpenClaw configuration.

        Returns:
            Dictionary containing openclaw.json content

        Raises:
            ConfigLoadError: If config file cannot be read or parsed
        """
        if not self.paths.config_file.exists():
            raise ConfigLoadError(f"Config file not found: {self.paths.config_file}")

        try:
            content = self.paths.config_file.read_text()
            return cast(dict[str, Any], json.loads(content))
        except json.JSONDecodeError as e:
            raise ConfigLoadError(f"Invalid JSON in config file: {e}") from e
        except OSError as e:
            raise ConfigLoadError(f"Error reading config file: {e}") from e

    def save_config(self, config: dict[str, Any]) -> None:
        """Save OpenClaw configuration.

        Args:
            config: Dictionary to write to openclaw.json
        """
        content = json.dumps(config, indent=2)
        self.paths.config_file.write_text(content)

    def backup_config(self) -> Path:
        """Create a backup of the current config file.

        Returns:
            Path to the backup file

        Raises:
            ConfigLoadError: If config file doesn't exist
        """
        if not self.paths.config_file.exists():
            raise ConfigLoadError("No config file to backup")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.paths.config_file.with_suffix(f".json.backup.{timestamp}")

        # Copy content to backup
        content = self.paths.config_file.read_text()
        backup_path.write_text(content)

        return backup_path

    def is_raxe_configured(self) -> bool:
        """Check if RAXE hook is configured.

        Returns:
            True if raxe-security hook entry exists in config
        """
        if not self.is_openclaw_installed():
            return False

        try:
            config = self.load_config()
            entries = config.get("hooks", {}).get("internal", {}).get("entries", {})
            return self.RAXE_HOOK_NAME in entries
        except ConfigLoadError:
            return False

    def add_raxe_hook_entry(self) -> None:
        """Add RAXE security hook entry to config.

        Preserves existing hook entries and adds raxe-security.
        """
        config = self.load_config()

        # Ensure structure exists
        if "hooks" not in config:
            config["hooks"] = {}
        if "internal" not in config["hooks"]:
            config["hooks"]["internal"] = {"enabled": True, "entries": {}}
        if "entries" not in config["hooks"]["internal"]:
            config["hooks"]["internal"]["entries"] = {}

        # Add RAXE hook entry
        config["hooks"]["internal"]["entries"][self.RAXE_HOOK_NAME] = {
            "enabled": True,
        }

        self.save_config(config)

    def remove_raxe_hook_entry(self) -> None:
        """Remove RAXE security hook entry from config."""
        config = self.load_config()

        entries = config.get("hooks", {}).get("internal", {}).get("entries", {})

        if self.RAXE_HOOK_NAME in entries:
            del entries[self.RAXE_HOOK_NAME]
            self.save_config(config)
