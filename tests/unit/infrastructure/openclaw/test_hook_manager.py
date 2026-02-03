"""Tests for OpenClaw hook manager.

TDD: These tests define expected behavior for OpenClaw hook file management.
"""

import pytest


@pytest.fixture
def mock_openclaw_path(tmp_path):
    """Create a mock OpenClaw directory structure."""
    openclaw_dir = tmp_path / ".openclaw"
    openclaw_dir.mkdir()
    hooks_dir = openclaw_dir / "hooks"
    hooks_dir.mkdir()
    return openclaw_dir


class TestOpenClawHookManager:
    """Tests for OpenClawHookManager."""

    def test_install_hook_files_creates_directory(self, mock_openclaw_path):
        """Test install creates the raxe-security hook directory."""
        from raxe.infrastructure.openclaw.hook_manager import OpenClawHookManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawHookManager(paths)

        manager.install_hook_files()

        assert paths.raxe_hook_dir.exists()
        assert paths.raxe_hook_dir.is_dir()

    def test_install_hook_files_writes_handler_ts(self, mock_openclaw_path):
        """Test install writes handler.ts file."""
        from raxe.infrastructure.openclaw.hook_manager import OpenClawHookManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawHookManager(paths)

        manager.install_hook_files()

        assert paths.handler_file.exists()
        content = paths.handler_file.read_text()
        # Should contain TypeScript handler code
        assert "handler" in content.lower() or "export" in content.lower()

    def test_install_hook_files_writes_hook_md(self, mock_openclaw_path):
        """Test install writes HOOK.md metadata file with frontmatter."""
        from raxe.infrastructure.openclaw.hook_manager import OpenClawHookManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawHookManager(paths)

        manager.install_hook_files()

        assert paths.hook_md_file.exists()
        content = paths.hook_md_file.read_text()
        # Should contain YAML frontmatter with name and description
        assert "---" in content  # Frontmatter delimiters
        assert "name: raxe-security" in content
        assert "description:" in content
        # Should have emoji for OpenClaw display
        assert "emoji:" in content

    def test_install_hook_files_writes_package_json(self, mock_openclaw_path):
        """Test install writes package.json for ES module support."""
        from raxe.infrastructure.openclaw.hook_manager import OpenClawHookManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawHookManager(paths)

        manager.install_hook_files()

        assert paths.package_json_file.exists()
        content = paths.package_json_file.read_text()
        # Should contain ES module type declaration
        assert '"type": "module"' in content

    def test_remove_hook_files_deletes_directory(self, mock_openclaw_path):
        """Test remove deletes the entire raxe-security directory."""
        from raxe.infrastructure.openclaw.hook_manager import OpenClawHookManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawHookManager(paths)

        # First install
        manager.install_hook_files()
        assert paths.raxe_hook_dir.exists()

        # Then remove
        manager.remove_hook_files()
        assert not paths.raxe_hook_dir.exists()

    def test_hook_files_exist_true(self, mock_openclaw_path):
        """Test hook_files_exist returns true when files exist."""
        from raxe.infrastructure.openclaw.hook_manager import OpenClawHookManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawHookManager(paths)

        manager.install_hook_files()

        assert manager.hook_files_exist() is True

    def test_hook_files_exist_false(self, mock_openclaw_path):
        """Test hook_files_exist returns false when files don't exist."""
        from raxe.infrastructure.openclaw.hook_manager import OpenClawHookManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawHookManager(paths)

        assert manager.hook_files_exist() is False

    def test_hook_files_exist_partial(self, mock_openclaw_path):
        """Test hook_files_exist returns false for partial install."""
        from raxe.infrastructure.openclaw.hook_manager import OpenClawHookManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths(openclaw_dir=mock_openclaw_path)
        manager = OpenClawHookManager(paths)

        # Create directory but only some files (missing package.json)
        paths.raxe_hook_dir.mkdir(parents=True)
        paths.handler_file.write_text("// partial")
        paths.hook_md_file.write_text("# Partial")

        # Should return false because package.json is missing
        assert manager.hook_files_exist() is False

    def test_get_handler_content(self):
        """Test getting embedded handler content."""
        from raxe.infrastructure.openclaw.hook_manager import OpenClawHookManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths()
        manager = OpenClawHookManager(paths)

        content = manager.get_handler_content()

        assert content is not None
        assert len(content) > 0

    def test_get_hook_md_content(self):
        """Test getting embedded HOOK.md content."""
        from raxe.infrastructure.openclaw.hook_manager import OpenClawHookManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths()
        manager = OpenClawHookManager(paths)

        content = manager.get_hook_md_content()

        assert content is not None
        assert len(content) > 0

    def test_get_package_json_content(self):
        """Test getting embedded package.json content."""
        from raxe.infrastructure.openclaw.hook_manager import OpenClawHookManager
        from raxe.infrastructure.openclaw.models import OpenClawPaths

        paths = OpenClawPaths()
        manager = OpenClawHookManager(paths)

        content = manager.get_package_json_content()

        assert content is not None
        assert len(content) > 0
        assert '"type": "module"' in content
