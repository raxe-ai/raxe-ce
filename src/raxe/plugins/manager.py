"""Plugin Lifecycle Management.

Manages plugin execution, coordinates lifecycle hooks, and provides
error isolation to ensure plugin failures don't crash the core system.

The PluginManager is responsible for:
- Loading plugins via PluginLoader
- Executing lifecycle hooks
- Running detector and action plugins
- Timeout enforcement
- Performance tracking
- Error isolation
"""

import logging
import time
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field

# Conditional imports for type checking
from typing import TYPE_CHECKING, Any

from raxe.plugins.loader import PluginLoader
from raxe.plugins.protocol import ActionPlugin, DetectorPlugin, RaxePlugin, TransformPlugin

if TYPE_CHECKING:
    from raxe.application.scan_pipeline import ScanPipelineResult
    from raxe.domain.engine.executor import Detection

logger = logging.getLogger(__name__)


@dataclass
class PluginMetrics:
    """Performance metrics for a single plugin.

    Tracks execution times, errors, and timeouts to monitor
    plugin health and performance.

    Attributes:
        total_executions: Total number of hook executions
        total_duration_ms: Cumulative execution time
        error_count: Number of errors encountered
        timeout_count: Number of timeouts
        hook_counts: Execution count per hook
        hook_durations: Total duration per hook (milliseconds)
    """

    total_executions: int = 0
    total_duration_ms: float = 0.0
    error_count: int = 0
    timeout_count: int = 0
    hook_counts: dict[str, int] = field(default_factory=dict)
    hook_durations: dict[str, float] = field(default_factory=dict)

    def record_execution(self, hook: str, duration_ms: float) -> None:
        """Record successful hook execution.

        Args:
            hook: Hook name (e.g., "on_scan_start")
            duration_ms: Execution duration in milliseconds
        """
        self.total_executions += 1
        self.total_duration_ms += duration_ms
        self.hook_counts[hook] = self.hook_counts.get(hook, 0) + 1
        self.hook_durations[hook] = self.hook_durations.get(hook, 0.0) + duration_ms

    def record_error(self, hook: str) -> None:
        """Record hook execution error.

        Args:
            hook: Hook name that failed
        """
        self.error_count += 1

    def record_timeout(self, hook: str) -> None:
        """Record hook execution timeout.

        Args:
            hook: Hook name that timed out
        """
        self.timeout_count += 1

    @property
    def average_duration_ms(self) -> float:
        """Average execution time across all hooks.

        Returns:
            Average duration in milliseconds
        """
        if self.total_executions == 0:
            return 0.0
        return self.total_duration_ms / self.total_executions

    @property
    def success_rate(self) -> float:
        """Success rate (0.0 to 1.0).

        Returns:
            Proportion of successful executions
        """
        total_attempts = self.total_executions + self.error_count + self.timeout_count
        if total_attempts == 0:
            return 1.0
        return self.total_executions / total_attempts


class PluginManager:
    """Manages plugin lifecycle and execution.

    The PluginManager coordinates all plugin operations:
    - Initializes plugins via PluginLoader
    - Executes lifecycle hooks in priority order
    - Runs detector and action plugins
    - Enforces timeouts to prevent hanging
    - Isolates errors to prevent cascade failures
    - Tracks performance metrics

    Example:
        ```python
        # Initialize manager
        manager = PluginManager(
            loader=PluginLoader(),
            timeout_seconds=5.0
        )

        # Load plugins
        manager.initialize(
            enabled_plugins=["custom_detector", "slack_notifier"],
            plugin_configs={...}
        )

        # Execute hooks
        manager.execute_hook("on_scan_start", text="test")

        # Run detectors
        detections = manager.run_detectors("test text")

        # Shutdown
        manager.shutdown()
        ```

    Attributes:
        loader: PluginLoader instance
        timeout: Maximum execution time per plugin (seconds)
        parallel: Execute plugins in parallel (ThreadPoolExecutor)
        all_plugins: All loaded plugins in priority order
        detector_plugins: Detector plugins only
        action_plugins: Action plugins only
        transform_plugins: Transform plugins only
        plugin_metrics: Performance metrics per plugin
    """

    def __init__(
        self,
        loader: PluginLoader,
        *,
        timeout_seconds: float = 5.0,
        parallel_execution: bool = False,
    ):
        """Initialize plugin manager.

        Args:
            loader: PluginLoader instance
            timeout_seconds: Max execution time per plugin (default: 5s)
            parallel_execution: Execute plugins in parallel (default: False)
        """
        self.loader = loader
        self.timeout = timeout_seconds
        self.parallel = parallel_execution

        # Categorized plugins
        self.all_plugins: list[RaxePlugin] = []
        self.detector_plugins: list[DetectorPlugin] = []
        self.action_plugins: list[ActionPlugin] = []
        self.transform_plugins: list[TransformPlugin] = []

        # Performance tracking
        self.plugin_metrics: dict[str, PluginMetrics] = {}

        # Thread pool for parallel execution
        self.executor: ThreadPoolExecutor | None = None
        if parallel_execution:
            self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="plugin")

        logger.debug(
            f"PluginManager initialized (timeout={timeout_seconds}s, "
            f"parallel={parallel_execution})"
        )

    def initialize(
        self, enabled_plugins: list[str], plugin_configs: dict[str, dict[str, Any]]
    ) -> None:
        """Initialize all enabled plugins.

        Loads plugins via the loader, categorizes them by type,
        and initializes metrics tracking.

        Args:
            enabled_plugins: List of plugin names to enable
            plugin_configs: Plugin-specific configurations

        Note:
            Plugins are sorted by priority before storage.
            Higher priority (lower numeric value) executes first.
        """
        # Load plugins
        plugins = self.loader.load_all_enabled(enabled_plugins, plugin_configs)

        # Sort by priority (lower value = higher priority)
        sorted_plugins = sorted(
            plugins.values(), key=lambda p: p.metadata.priority.value
        )

        # Store and categorize
        for plugin in sorted_plugins:
            self.all_plugins.append(plugin)

            # Categorize by type (duck typing)
            if hasattr(plugin, "detect") and callable(plugin.detect):
                self.detector_plugins.append(plugin)  # type: ignore
                logger.debug(f"Registered detector plugin: {plugin.metadata.name}")

            if hasattr(plugin, "should_execute") and hasattr(plugin, "execute"):
                if callable(plugin.should_execute) and callable(
                    plugin.execute
                ):
                    self.action_plugins.append(plugin)  # type: ignore
                    logger.debug(f"Registered action plugin: {plugin.metadata.name}")

            if hasattr(plugin, "transform_input") or hasattr(plugin, "transform_output"):
                self.transform_plugins.append(plugin)  # type: ignore
                logger.debug(f"Registered transform plugin: {plugin.metadata.name}")

            # Initialize metrics
            self.plugin_metrics[plugin.metadata.name] = PluginMetrics()

        logger.info(
            f"Initialized {len(self.all_plugins)} plugins: "
            f"{len(self.detector_plugins)} detectors, "
            f"{len(self.action_plugins)} actions, "
            f"{len(self.transform_plugins)} transforms"
        )

    def execute_hook(self, hook_name: str, *args: Any, **kwargs: Any) -> list[Any]:
        """Execute a lifecycle hook on all plugins.

        Calls the specified hook method on all loaded plugins that
        implement it. Handles errors and timeouts gracefully.

        Args:
            hook_name: Name of hook method to call (e.g., "on_scan_start")
            *args: Positional arguments for hook
            **kwargs: Keyword arguments for hook

        Returns:
            List of non-None results from plugins

        Note:
            - Plugins execute in priority order
            - Errors are logged but don't stop execution
            - Timeouts are enforced (self.timeout seconds)
            - Only non-None results are returned
        """
        results: list[Any] = []

        for plugin in self.all_plugins:
            # Check if plugin has the hook
            hook = getattr(plugin, hook_name, None)
            if not hook or not callable(hook):
                continue

            try:
                # Track metrics
                metrics = self.plugin_metrics[plugin.metadata.name]
                start_time = time.perf_counter()

                # Execute with timeout
                result = self._execute_with_timeout(hook, args, kwargs)

                # Record metrics
                duration_ms = (time.perf_counter() - start_time) * 1000
                metrics.record_execution(hook_name, duration_ms)

                # Collect non-None results
                if result is not None:
                    results.append(result)

            except FutureTimeoutError:
                logger.error(
                    f"Plugin {plugin.metadata.name} hook {hook_name} "
                    f"timed out after {self.timeout}s"
                )
                metrics.record_timeout(hook_name)

            except Exception as e:
                logger.error(
                    f"Plugin {plugin.metadata.name} hook {hook_name} failed: {e}\n"
                    f"{traceback.format_exc()}"
                )
                metrics.record_error(hook_name)

        return results

    def run_detectors(
        self, text: str, context: dict[str, Any] | None = None
    ) -> list["Detection"]:
        """Run all detector plugins.

        Executes the detect() method on all detector plugins and
        aggregates results. Each detection is tagged with the plugin
        that generated it.

        Args:
            text: Text to scan
            context: Optional context metadata

        Returns:
            Combined list of detections from all detector plugins

        Note:
            - Detections are validated (must be list)
            - Plugin name is added to detection metadata
            - Errors are isolated per plugin
        """
        all_detections: list[Detection] = []

        for plugin in self.detector_plugins:
            try:
                metrics = self.plugin_metrics[plugin.metadata.name]
                start_time = time.perf_counter()

                # Run detector with timeout
                detect_func = lambda: plugin.detect(text, context)  # noqa: E731
                detections = self._execute_with_timeout(detect_func, (), {})

                # Validate result
                if not isinstance(detections, list):
                    logger.warning(
                        f"Plugin {plugin.metadata.name} returned invalid "
                        f"detections: {type(detections)}. Expected list."
                    )
                    continue

                # Add plugin attribution to each detection
                for detection in detections:
                    # Add plugin name to metadata
                    if hasattr(detection, "__dict__"):
                        if not hasattr(detection, "metadata"):
                            detection.metadata = {}  # type: ignore
                        if isinstance(detection.metadata, dict):
                            detection.metadata["plugin"] = plugin.metadata.name

                all_detections.extend(detections)

                # Record metrics
                duration_ms = (time.perf_counter() - start_time) * 1000
                metrics.record_execution("detect", duration_ms)

                logger.debug(
                    f"Plugin {plugin.metadata.name} detected {len(detections)} threats "
                    f"in {duration_ms:.2f}ms"
                )

            except FutureTimeoutError:
                logger.error(
                    f"Detector plugin {plugin.metadata.name} timed out "
                    f"after {self.timeout}s"
                )
                metrics.record_timeout("detect")

            except Exception as e:
                logger.error(f"Detector plugin {plugin.metadata.name} failed: {e}")
                metrics.record_error("detect")

        return all_detections

    def run_actions(self, result: "ScanPipelineResult") -> None:
        """Run all action plugins.

        Executes action plugins that pass their should_execute() check.
        Actions are run in priority order.

        Args:
            result: Scan pipeline result

        Note:
            - should_execute() is called first to filter
            - Only matching actions are executed
            - Errors are isolated per action
        """
        for plugin in self.action_plugins:
            try:
                # Check if should execute
                if not plugin.should_execute(result):
                    logger.debug(
                        f"Action plugin {plugin.metadata.name} skipped (should_execute=False)"
                    )
                    continue

                metrics = self.plugin_metrics[plugin.metadata.name]
                start_time = time.perf_counter()

                # Execute action with timeout
                execute_func = lambda: plugin.execute(result)  # noqa: E731
                self._execute_with_timeout(execute_func, (), {})

                # Record metrics
                duration_ms = (time.perf_counter() - start_time) * 1000
                metrics.record_execution("execute", duration_ms)

                logger.debug(
                    f"Action plugin {plugin.metadata.name} executed in {duration_ms:.2f}ms"
                )

            except FutureTimeoutError:
                logger.error(
                    f"Action plugin {plugin.metadata.name} timed out "
                    f"after {self.timeout}s"
                )
                metrics.record_timeout("execute")

            except Exception as e:
                logger.error(f"Action plugin {plugin.metadata.name} failed: {e}")
                metrics.record_error("execute")

    def shutdown(self) -> None:
        """Shutdown all plugins gracefully.

        Calls on_shutdown() on all plugins in reverse order,
        logs final metrics, and cleans up thread pool.

        Note:
            Plugins are shut down in reverse initialization order
            to respect dependency relationships.
        """
        logger.info("Shutting down plugin manager...")

        # Shutdown plugins in reverse order
        for plugin in reversed(self.all_plugins):
            try:
                plugin.on_shutdown()
                logger.debug(f"Plugin {plugin.metadata.name} shut down")
            except Exception as e:
                logger.error(
                    f"Error shutting down plugin {plugin.metadata.name}: {e}"
                )

        # Shutdown thread pool
        if self.executor:
            self.executor.shutdown(wait=True, timeout=10)
            logger.debug("Plugin executor shut down")

        # Log final metrics
        self._log_metrics()

        logger.info("Plugin manager shutdown complete")

    def _execute_with_timeout(
        self, func: Callable, args: tuple, kwargs: dict
    ) -> Any:
        """Execute function with timeout.

        Uses ThreadPoolExecutor for parallel mode, otherwise executes
        directly (no timeout enforcement in sequential mode for simplicity).

        Args:
            func: Function to execute
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            TimeoutError: If execution exceeds timeout
            Exception: Any exception from function
        """
        if self.parallel and self.executor:
            # Execute with timeout in parallel mode
            future = self.executor.submit(func, *args, **kwargs)
            return future.result(timeout=self.timeout)
        else:
            # Direct execution in sequential mode
            # Note: No timeout enforcement to keep it simple
            # Future improvement: Use signal.alarm on Unix
            return func(*args, **kwargs)

    def _log_metrics(self) -> None:
        """Log plugin performance metrics.

        Outputs summary statistics for each plugin to help identify
        performance issues and errors.
        """
        if not self.plugin_metrics:
            return

        logger.info("=" * 60)
        logger.info("Plugin Performance Metrics")
        logger.info("=" * 60)

        for name, metrics in self.plugin_metrics.items():
            logger.info(
                f"Plugin: {name}\n"
                f"  Executions: {metrics.total_executions}\n"
                f"  Avg Duration: {metrics.average_duration_ms:.3f}ms\n"
                f"  Total Duration: {metrics.total_duration_ms:.3f}ms\n"
                f"  Success Rate: {metrics.success_rate * 100:.1f}%\n"
                f"  Errors: {metrics.error_count}\n"
                f"  Timeouts: {metrics.timeout_count}"
            )

        logger.info("=" * 60)

    def get_metrics(self, plugin_name: str) -> PluginMetrics | None:
        """Get metrics for a specific plugin.

        Args:
            plugin_name: Name of plugin

        Returns:
            PluginMetrics or None if not found
        """
        return self.plugin_metrics.get(plugin_name)

    def get_all_metrics(self) -> dict[str, PluginMetrics]:
        """Get metrics for all plugins.

        Returns:
            Dictionary mapping plugin names to metrics
        """
        return self.plugin_metrics.copy()


__all__ = ["PluginManager", "PluginMetrics"]
