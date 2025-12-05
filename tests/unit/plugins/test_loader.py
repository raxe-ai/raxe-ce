"""Tests for plugin loader.

Tests plugin discovery, loading, and error handling.
"""

from unittest.mock import patch

from raxe.plugins.loader import PluginLoader


class TestPluginLoader:
    """Test PluginLoader functionality."""

    def test_discover_paths_includes_user_dir(self, tmp_path):
        """Test that user plugin directory is discovered."""
        # Create user plugin dir
        user_plugins = tmp_path / ".raxe" / "plugins"
        user_plugins.mkdir(parents=True)

        with patch("pathlib.Path.home", return_value=tmp_path):
            loader = PluginLoader()
            assert any(str(user_plugins) in str(p) for p in loader.plugin_paths)

    def test_discover_paths_includes_env_var(self, tmp_path, monkeypatch):
        """Test that RAXE_PLUGIN_PATH environment variable is used."""
        custom_path = tmp_path / "custom_plugins"
        custom_path.mkdir()

        monkeypatch.setenv("RAXE_PLUGIN_PATH", str(custom_path))

        loader = PluginLoader()
        assert any(str(custom_path) == str(p) for p in loader.plugin_paths)

    def test_discover_plugins_finds_valid_plugin(self, tmp_path):
        """Test discovering a valid plugin."""
        # Create plugin directory with plugin.py
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text(
            """
from raxe.plugins import RaxePlugin, PluginMetadata

class TestPlugin:
    @property
    def metadata(self):
        return PluginMetadata(
            name="test_plugin",
            version="0.0.1",
            author="Test",
            description="Test plugin"
        )

    def on_init(self, config):
        pass

plugin = TestPlugin()
"""
        )

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(PluginLoader, "_discover_paths", return_value=[tmp_path]):
                loader = PluginLoader()
                plugins = loader.discover_plugins()

                assert len(plugins) == 1
                assert plugins[0].name == "test_plugin"
                assert plugins[0].path == plugin_dir
                assert plugins[0].plugin_file == plugin_file

    def test_discover_plugins_skips_hidden_dirs(self, tmp_path):
        """Test that hidden directories are skipped."""
        # Create hidden plugin directory
        hidden_dir = tmp_path / ".hidden_plugin"
        hidden_dir.mkdir()
        (hidden_dir / "plugin.py").write_text("# test")

        with patch.object(PluginLoader, "_discover_paths", return_value=[tmp_path]):
            loader = PluginLoader()
            plugins = loader.discover_plugins()

            assert len(plugins) == 0

    def test_discover_plugins_skips_without_plugin_py(self, tmp_path):
        """Test that directories without plugin.py are skipped."""
        # Create directory without plugin.py
        plugin_dir = tmp_path / "no_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "readme.txt").write_text("Not a plugin")

        with patch.object(PluginLoader, "_discover_paths", return_value=[tmp_path]):
            loader = PluginLoader()
            plugins = loader.discover_plugins()

            assert len(plugins) == 0

    def test_load_plugin_success(self, tmp_path):
        """Test successfully loading a plugin."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text(
            """
from raxe.plugins import PluginMetadata, PluginPriority

class TestPlugin:
    @property
    def metadata(self):
        return PluginMetadata(
            name="test_plugin",
            version="0.0.1",
            author="Test",
            description="Test plugin",
            priority=PluginPriority.NORMAL,
        )

    def on_init(self, config):
        self.config = config

plugin = TestPlugin()
"""
        )

        loader = PluginLoader()
        plugin = loader.load_plugin(plugin_dir, {"setting": "value"})

        assert plugin is not None
        assert plugin.metadata.name == "test_plugin"
        assert plugin.metadata.version == "1.0.0"
        assert plugin.config == {"setting": "value"}  # type: ignore

    def test_load_plugin_missing_file(self, tmp_path):
        """Test loading plugin with missing plugin.py."""
        plugin_dir = tmp_path / "missing"
        plugin_dir.mkdir()

        loader = PluginLoader()
        plugin = loader.load_plugin(plugin_dir, {})

        assert plugin is None
        assert "missing" in loader.failed_plugins
        assert "not found" in loader.failed_plugins["missing"]

    def test_load_plugin_missing_plugin_variable(self, tmp_path):
        """Test loading plugin without 'plugin' variable."""
        plugin_dir = tmp_path / "no_var"
        plugin_dir.mkdir()

        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text(
            """
# Missing 'plugin = ...' export
class TestPlugin:
    pass
"""
        )

        loader = PluginLoader()
        plugin = loader.load_plugin(plugin_dir, {})

        assert plugin is None
        assert "no_var" in loader.failed_plugins
        assert "plugin" in loader.failed_plugins["no_var"].lower()

    def test_load_plugin_init_fails(self, tmp_path):
        """Test loading plugin where on_init raises error."""
        plugin_dir = tmp_path / "fail_init"
        plugin_dir.mkdir()

        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text(
            """
from raxe.plugins import PluginMetadata

class TestPlugin:
    @property
    def metadata(self):
        return PluginMetadata(
            name="fail_init",
            version="0.0.1",
            author="Test",
            description="Test"
        )

    def on_init(self, config):
        raise ValueError("Init failed!")

plugin = TestPlugin()
"""
        )

        loader = PluginLoader()
        plugin = loader.load_plugin(plugin_dir, {})

        assert plugin is None
        assert "fail_init" in loader.failed_plugins
        assert "Init failed!" in loader.failed_plugins["fail_init"]

    def test_load_all_enabled(self, tmp_path):
        """Test loading only enabled plugins."""
        # Create two plugins
        for name in ["plugin1", "plugin2", "plugin3"]:
            plugin_dir = tmp_path / name
            plugin_dir.mkdir()

            plugin_file = plugin_dir / "plugin.py"
            plugin_file.write_text(
                f"""
from raxe.plugins import PluginMetadata

class TestPlugin:
    @property
    def metadata(self):
        return PluginMetadata(
            name="{name}",
            version="0.0.1",
            author="Test",
            description="Test"
        )

    def on_init(self, config):
        pass

plugin = TestPlugin()
"""
            )

        with patch.object(PluginLoader, "_discover_paths", return_value=[tmp_path]):
            loader = PluginLoader()

            # Only enable plugin1 and plugin2
            loaded = loader.load_all_enabled(
                enabled_plugins=["plugin1", "plugin2"],
                plugin_configs={"plugin1": {}, "plugin2": {}},
            )

            assert len(loaded) == 2
            assert "plugin1" in loaded
            assert "plugin2" in loaded
            assert "plugin3" not in loaded

    def test_unload_plugin(self, tmp_path):
        """Test unloading a plugin."""
        plugin_dir = tmp_path / "unload_test"
        plugin_dir.mkdir()

        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text(
            """
from raxe.plugins import PluginMetadata

class TestPlugin:
    def __init__(self):
        self.shutdown_called = False

    @property
    def metadata(self):
        return PluginMetadata(
            name="unload_test",
            version="0.0.1",
            author="Test",
            description="Test"
        )

    def on_init(self, config):
        pass

    def on_shutdown(self):
        self.shutdown_called = True

plugin = TestPlugin()
"""
        )

        loader = PluginLoader()
        plugin = loader.load_plugin(plugin_dir, {})
        assert plugin is not None
        assert "unload_test" in loader.loaded_plugins

        # Unload
        result = loader.unload_plugin("unload_test")
        assert result is True
        assert "unload_test" not in loader.loaded_plugins
        assert plugin.shutdown_called  # type: ignore

    def test_unload_nonexistent_plugin(self):
        """Test unloading a plugin that doesn't exist."""
        loader = PluginLoader()
        result = loader.unload_plugin("nonexistent")
        assert result is False

    def test_get_plugin(self, tmp_path):
        """Test getting a loaded plugin by name."""
        plugin_dir = tmp_path / "get_test"
        plugin_dir.mkdir()

        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text(
            """
from raxe.plugins import PluginMetadata

class TestPlugin:
    @property
    def metadata(self):
        return PluginMetadata(
            name="get_test",
            version="0.0.1",
            author="Test",
            description="Test"
        )

    def on_init(self, config):
        pass

plugin = TestPlugin()
"""
        )

        loader = PluginLoader()
        loaded = loader.load_plugin(plugin_dir, {})
        assert loaded is not None

        # Get plugin
        retrieved = loader.get_plugin("get_test")
        assert retrieved is loaded

        # Get nonexistent
        nonexistent = loader.get_plugin("nonexistent")
        assert nonexistent is None

    def test_list_loaded(self, tmp_path):
        """Test listing loaded plugin names."""
        loader = PluginLoader()
        assert len(loader.list_loaded()) == 0

        # Create and load a plugin
        plugin_dir = tmp_path / "list_test"
        plugin_dir.mkdir()

        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text(
            """
from raxe.plugins import PluginMetadata

class TestPlugin:
    @property
    def metadata(self):
        return PluginMetadata(
            name="list_test",
            version="0.0.1",
            author="Test",
            description="Test"
        )

    def on_init(self, config):
        pass

plugin = TestPlugin()
"""
        )

        loader.load_plugin(plugin_dir, {})
        loaded = loader.list_loaded()
        assert len(loaded) == 1
        assert "list_test" in loaded
