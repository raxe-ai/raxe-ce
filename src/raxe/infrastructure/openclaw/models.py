"""Models for OpenClaw infrastructure.

These dataclasses define the configuration and path structures
for OpenClaw integration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _get_default_openclaw_dir() -> Path:
    """Get default OpenClaw directory, respecting OPENCLAW_HOME env var."""
    openclaw_home = os.environ.get("OPENCLAW_HOME")
    if openclaw_home:
        return Path(openclaw_home)
    return Path.home() / ".openclaw"


@dataclass
class OpenClawPaths:
    """Paths for OpenClaw configuration and hooks.

    Attributes:
        openclaw_dir: Base OpenClaw directory (default: $OPENCLAW_HOME or ~/.openclaw)
        config_file: OpenClaw config file (openclaw.json)
        hooks_dir: Directory containing hooks
        raxe_hook_dir: Directory for RAXE security hook
        handler_file: Path to handler.ts file
        hook_md_file: Path to HOOK.md metadata file
    """

    openclaw_dir: Path = field(default_factory=_get_default_openclaw_dir)

    @property
    def config_file(self) -> Path:
        """Get path to openclaw.json config file."""
        return self.openclaw_dir / "openclaw.json"

    @property
    def hooks_dir(self) -> Path:
        """Get path to hooks directory."""
        return self.openclaw_dir / "hooks"

    @property
    def raxe_hook_dir(self) -> Path:
        """Get path to raxe-security hook directory."""
        return self.hooks_dir / "raxe-security"

    @property
    def handler_file(self) -> Path:
        """Get path to handler.ts file."""
        return self.raxe_hook_dir / "handler.ts"

    @property
    def hook_md_file(self) -> Path:
        """Get path to HOOK.md metadata file."""
        return self.raxe_hook_dir / "HOOK.md"

    @property
    def package_json_file(self) -> Path:
        """Get path to package.json file (required for ES module support)."""
        return self.raxe_hook_dir / "package.json"


@dataclass
class OpenClawConfig:
    """OpenClaw configuration structure.

    Represents the structure of openclaw.json with focus on
    the hooks configuration that RAXE modifies.
    """

    hooks: dict[str, Any] = field(
        default_factory=lambda: {
            "internal": {
                "enabled": True,
                "entries": {},
            }
        }
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpenClawConfig:
        """Create config from dictionary.

        Args:
            data: Dictionary from openclaw.json

        Returns:
            OpenClawConfig instance
        """
        return cls(hooks=data.get("hooks", {"internal": {"enabled": True, "entries": {}}}))

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary.

        Returns:
            Dictionary suitable for writing to openclaw.json
        """
        return {
            "hooks": self.hooks,
        }
