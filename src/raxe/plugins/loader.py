"""Plugin Discovery and Loading.

Discovers and loads RAXE plugins from multiple sources while handling
errors gracefully. Supports loading from:
- User plugins: ~/.raxe/plugins/
- System plugins: /usr/local/raxe/plugins/
- Environment override: RAXE_PLUGIN_PATH

All plugin loading is fail-safe - individual plugin failures do not
crash the system.
"""

import importlib.util
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from raxe.plugins.protocol import RaxePlugin

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PluginInfo:
    """Information about a discovered plugin.

    Attributes:
        name: Plugin name (directory name)
        path: Path to plugin directory
        plugin_file: Path to plugin.py file
        loaded: True if plugin was successfully loaded
        error: Error message if loading failed
    """

    name: str
    path: Path
    plugin_file: Path
    loaded: bool = False
    error: str | None = None


class PluginLoader:
    """Discovers and loads RAXE plugins safely.

    The loader discovers plugins from multiple paths, validates them
    against the plugin protocol, and loads them dynamically. All operations
    are designed to be fail-safe - individual plugin failures are logged
    but don't crash the system.

    Example:
        ```python
        loader = PluginLoader()
        plugins = loader.discover_plugins()
        for info in plugins:
            plugin = loader.load_plugin(info.path, config={})
            if plugin:
                print(f"Loaded: {plugin.metadata.name}")
        ```

    Attributes:
        plugin_paths: List of directories to search for plugins
        loaded_plugins: Dictionary of successfully loaded plugins
        failed_plugins: Dictionary of plugins that failed to load
    """

    def __init__(self) -> None:
        """Initialize plugin loader.

        Discovers plugin paths from standard locations and environment.
        """
        self.plugin_paths = self._discover_paths()
        self.loaded_plugins: dict[str, RaxePlugin] = {}
        self.failed_plugins: dict[str, str] = {}  # name -> error message

        logger.debug(f"Plugin loader initialized with paths: {self.plugin_paths}")

    def _discover_paths(self) -> list[Path]:
        """Discover all plugin directories.

        Search order (highest to lowest priority):
        1. User plugins: ~/.raxe/plugins/
        2. System plugins: /usr/local/raxe/plugins/
        3. Environment override: RAXE_PLUGIN_PATH

        Returns:
            List of valid plugin directory paths

        Note:
            Only returns paths that actually exist.
        """
        paths: list[Path] = []

        # 1. User plugins (highest priority)
        user_path = Path.home() / ".raxe" / "plugins"
        if user_path.exists() and user_path.is_dir():
            paths.append(user_path)
            logger.debug(f"Found user plugin path: {user_path}")

        # 2. System plugins
        system_path = Path("/usr/local/raxe/plugins")
        if system_path.exists() and system_path.is_dir():
            paths.append(system_path)
            logger.debug(f"Found system plugin path: {system_path}")

        # 3. Environment override (can be colon-separated list)
        env_path = os.getenv("RAXE_PLUGIN_PATH")
        if env_path:
            for path_str in env_path.split(":"):
                path = Path(path_str).expanduser().resolve()
                if path.exists() and path.is_dir():
                    paths.append(path)
                    logger.debug(f"Found env plugin path: {path}")
                else:
                    logger.warning(f"RAXE_PLUGIN_PATH includes non-existent path: {path}")

        return paths

    def discover_plugins(self) -> list[PluginInfo]:
        """Find all available plugins.

        Scans all plugin paths for valid plugin directories. A valid
        plugin directory must contain a plugin.py file.

        Returns:
            List of discovered plugin information

        Note:
            This only discovers plugins, it doesn't load them.
            Use load_plugin() to actually load a plugin.
        """
        plugins: list[PluginInfo] = []

        for base_path in self.plugin_paths:
            logger.debug(f"Scanning plugin path: {base_path}")

            try:
                for plugin_dir in base_path.iterdir():
                    # Skip non-directories
                    if not plugin_dir.is_dir():
                        continue

                    # Skip hidden directories
                    if plugin_dir.name.startswith("."):
                        continue

                    # Check for plugin.py
                    plugin_file = plugin_dir / "plugin.py"
                    if not plugin_file.exists():
                        logger.debug(
                            f"Skipping {plugin_dir.name}: no plugin.py found"
                        )
                        continue

                    # Create plugin info
                    info = PluginInfo(
                        name=plugin_dir.name,
                        path=plugin_dir,
                        plugin_file=plugin_file,
                    )
                    plugins.append(info)
                    logger.debug(f"Discovered plugin: {info.name}")

            except Exception as e:
                logger.warning(f"Error scanning plugin path {base_path}: {e}")

        logger.info(f"Discovered {len(plugins)} plugins")
        return plugins

    def load_plugin(
        self, plugin_path: Path, config: dict[str, Any]
    ) -> RaxePlugin | None:
        """Load a single plugin safely.

        Dynamically loads a plugin module, validates it implements the
        RaxePlugin protocol, and initializes it with configuration.

        Args:
            plugin_path: Path to plugin directory
            config: Plugin-specific configuration

        Returns:
            Loaded plugin instance or None if loading failed

        Note:
            All exceptions are caught and logged. Failed plugins are
            recorded in self.failed_plugins but don't crash the loader.

        Example:
            ```python
            plugin = loader.load_plugin(
                Path("~/.raxe/plugins/my_plugin"),
                config={"api_key": "secret"}
            )
            if plugin:
                print(f"Loaded: {plugin.metadata.name}")
            ```
        """
        plugin_name = plugin_path.name
        plugin_file = plugin_path / "plugin.py"

        if not plugin_file.exists():
            error = f"Plugin file not found: {plugin_file}"
            self.failed_plugins[plugin_name] = error
            logger.error(error)
            return None

        try:
            # Create module spec
            spec = importlib.util.spec_from_file_location(
                f"raxe_plugin_{plugin_name}", plugin_file
            )

            if not spec or not spec.loader:
                raise ImportError(f"Cannot create module spec for {plugin_file}")

            # Load module
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            # Get plugin instance
            if not hasattr(module, "plugin"):
                raise AttributeError(
                    f"Plugin module must define 'plugin' variable. "
                    f"Add: plugin = MyPlugin() at end of {plugin_file}"
                )

            plugin = module.plugin

            # Validate plugin implements protocol
            if not hasattr(plugin, "metadata"):
                raise TypeError(
                    "Plugin must have 'metadata' property implementing PluginMetadata"
                )

            if not hasattr(plugin, "on_init"):
                raise TypeError("Plugin must implement 'on_init' method")

            # Get metadata to validate
            metadata = plugin.metadata
            logger.debug(
                f"Loading plugin: {metadata.name} v{metadata.version} by {metadata.author}"
            )

            # Initialize plugin with configuration
            try:
                plugin.on_init(config)
            except Exception as init_error:
                raise RuntimeError(
                    f"Plugin initialization failed: {init_error}"
                ) from init_error

            # Store successfully loaded plugin
            self.loaded_plugins[plugin_name] = plugin
            logger.info(
                f"Successfully loaded plugin: {metadata.name} v{metadata.version}"
            )

            return plugin

        except Exception as e:
            error_msg = f"Failed to load plugin {plugin_name}: {e}"
            self.failed_plugins[plugin_name] = str(e)
            logger.warning(error_msg)
            return None

    def load_all_enabled(
        self, enabled_plugins: list[str], plugin_configs: dict[str, dict[str, Any]]
    ) -> dict[str, RaxePlugin]:
        """Load all enabled plugins.

        Discovers plugins and loads only those that are explicitly enabled
        in the configuration.

        Args:
            enabled_plugins: List of plugin names to enable
            plugin_configs: Dictionary of plugin-specific configurations

        Returns:
            Dictionary of successfully loaded plugins (name -> plugin)

        Example:
            ```python
            plugins = loader.load_all_enabled(
                enabled_plugins=["custom_detector", "slack_notifier"],
                plugin_configs={
                    "custom_detector": {"patterns": [...]},
                    "slack_notifier": {"webhook_url": "..."}
                }
            )
            ```
        """
        loaded: dict[str, RaxePlugin] = {}

        # Discover all available plugins
        all_plugins = self.discover_plugins()
        logger.debug(f"Found {len(all_plugins)} plugins, enabling {len(enabled_plugins)}")

        # Load only enabled plugins
        for plugin_info in all_plugins:
            if plugin_info.name not in enabled_plugins:
                logger.debug(f"Skipping disabled plugin: {plugin_info.name}")
                continue

            # Get plugin-specific config
            plugin_config = plugin_configs.get(plugin_info.name, {})

            # Load plugin
            plugin = self.load_plugin(plugin_info.path, plugin_config)
            if plugin:
                loaded[plugin_info.name] = plugin
            else:
                logger.warning(f"Failed to load enabled plugin: {plugin_info.name}")

        logger.info(
            f"Loaded {len(loaded)}/{len(enabled_plugins)} enabled plugins"
        )
        return loaded

    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin.

        Calls on_shutdown() and removes from loaded plugins.

        Args:
            plugin_name: Name of plugin to unload

        Returns:
            True if unloaded successfully, False if not found
        """
        plugin = self.loaded_plugins.get(plugin_name)
        if not plugin:
            return False

        try:
            # Call shutdown hook
            plugin.on_shutdown()
        except Exception as e:
            logger.warning(f"Error during plugin shutdown {plugin_name}: {e}")

        # Remove from loaded plugins
        del self.loaded_plugins[plugin_name]
        logger.info(f"Unloaded plugin: {plugin_name}")
        return True

    def unload_all(self) -> None:
        """Unload all plugins.

        Calls on_shutdown() on all loaded plugins in reverse order.
        """
        # Unload in reverse order
        plugin_names = list(self.loaded_plugins.keys())
        for name in reversed(plugin_names):
            self.unload_plugin(name)

        logger.info("All plugins unloaded")

    def get_plugin(self, name: str) -> RaxePlugin | None:
        """Get a loaded plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None if not loaded
        """
        return self.loaded_plugins.get(name)

    def list_loaded(self) -> list[str]:
        """Get list of loaded plugin names.

        Returns:
            List of plugin names that are currently loaded
        """
        return list(self.loaded_plugins.keys())

    def list_failed(self) -> dict[str, str]:
        """Get dictionary of failed plugins.

        Returns:
            Dictionary mapping plugin names to error messages
        """
        return self.failed_plugins.copy()


__all__ = ["PluginInfo", "PluginLoader"]
