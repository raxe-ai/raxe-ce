"""Progress indicators for RAXE initialization.

Provides context-aware progress display for CLI:
- Interactive terminals: Rich spinners with live updates
- CI/CD environments: Plain timestamped text
- Quiet mode: Silent (errors only)

Usage:
    from raxe.cli.progress import create_progress_indicator
    from raxe.cli.progress_context import detect_progress_mode

    mode = detect_progress_mode(quiet=False, no_color=False)
    progress = create_progress_indicator(mode)

    progress.start("Initializing RAXE...")
    progress.update_component("rules", "complete", 633, {"count": 460})
    progress.update_component("ml_model", "complete", 2150)
    progress.complete(2933)
"""

import sys
import time
from abc import ABC, abstractmethod
from typing import ClassVar, Literal

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

ComponentStatus = Literal["loading", "complete", "error"]


class ProgressIndicator(ABC):
    """Abstract base for progress indicators.

    All progress implementations must inherit from this class
    and implement the required methods.
    """

    @abstractmethod
    def start(self, message: str) -> None:
        """Start showing progress.

        Args:
            message: Main progress message (e.g., "Initializing RAXE...")
        """
        pass

    @abstractmethod
    def update_component(
        self,
        name: str,
        status: ComponentStatus,
        duration_ms: float,
        metadata: dict | None = None,
    ) -> None:
        """Update status of a component.

        Args:
            name: Component identifier (rules, ml_model, warmup)
            status: Current status (loading, complete, error)
            duration_ms: Time taken in milliseconds (0 if loading)
            metadata: Optional metadata (e.g., {"count": 460} for rules)
        """
        pass

    @abstractmethod
    def complete(self, total_duration_ms: float) -> None:
        """Mark initialization as complete.

        Args:
            total_duration_ms: Total initialization time
        """
        pass

    @abstractmethod
    def error(self, component: str, message: str) -> None:
        """Report component failure.

        Args:
            component: Component that failed
            message: Error message
        """
        pass


class NullProgress(ProgressIndicator):
    """No-op progress for when no callback provided.

    Used internally when SDK is used without CLI progress.
    """

    def start(self, message: str) -> None:
        pass

    def update_component(
        self,
        name: str,
        status: ComponentStatus,
        duration_ms: float,
        metadata: dict | None = None,
    ) -> None:
        pass

    def complete(self, total_duration_ms: float) -> None:
        pass

    def error(self, component: str, message: str) -> None:
        pass


class InteractiveProgress(ProgressIndicator):
    """Rich progress for interactive terminals.

    Features:
    - Live-updating spinners
    - Color-coded status
    - Transient display (clears after completion)
    """

    # Component display configuration
    COMPONENT_LABELS: ClassVar[dict] = {
        "rules": {
            "loading": "Loading detection rules",
            "complete": "Loaded {count} rules",
        },
        "ml_model": {
            "loading": "Loading ML model",
            "complete": "Loaded ML model",
        },
        "warmup": {
            "loading": "Warming up components",
            "complete": "Components ready",
        },
    }

    def __init__(self):
        self.console = Console()
        self.components = {}
        self.live = None
        self.start_time = None
        self.main_message = ""
        self.rules_count = 0  # Track for display

    def start(self, message: str) -> None:
        """Start showing progress with live updates."""
        self.start_time = time.time()
        self.main_message = message

        # Initialize components in order
        self.components = {
            "rules": {"status": "loading", "duration_ms": 0},
            "ml_model": {"status": "loading", "duration_ms": 0},
            "warmup": {"status": "loading", "duration_ms": 0},
        }

        # Start live display (transient=True makes it disappear after stop)
        self.live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=10,  # 10 FPS for smooth spinner
            transient=True,
        )
        self.live.start()

    def update_component(
        self,
        name: str,
        status: ComponentStatus,
        duration_ms: float,
        metadata: dict | None = None,
    ) -> None:
        """Update component status with live refresh."""
        if name not in self.components:
            return

        self.components[name]["status"] = status
        self.components[name]["duration_ms"] = duration_ms

        # Store metadata for display (e.g., rules count)
        if metadata:
            if name == "rules" and "count" in metadata:
                self.rules_count = metadata["count"]

        if self.live:
            self.live.update(self._render())

    def complete(self, total_duration_ms: float) -> None:
        """Show completion and clear after delay."""
        if not self.live:
            return

        # Update to completion state
        final_render = self._render_complete(total_duration_ms)
        self.live.update(final_render)

        # Wait for user to read (500ms)
        time.sleep(0.5)

        # Stop live display (transient will auto-clear)
        self.live.stop()

    def error(self, component: str, message: str) -> None:
        """Show error panel."""
        if self.live:
            self.live.stop()

        error_text = Text()
        error_text.append("✗ ", style="red bold")
        error_text.append(f"Initialization failed: {component}\n", style="red")
        error_text.append(message, style="dim")

        self.console.print(Panel(error_text, border_style="red"))

    def _render(self) -> Panel:
        """Render current progress state."""
        content = Text()

        # Header
        content.append("🔧 ", style="cyan")
        content.append(self.main_message, style="cyan bold")
        content.append("\n")

        # Component status lines
        for name, data in self.components.items():
            content.append("  ")  # Indent

            if data["status"] == "loading":
                content.append("⏳ ", style="cyan")
                label = self._get_label(name, "loading")
                content.append(label, style="white")
                content.append("...\n")

            elif data["status"] == "complete":
                content.append("✓ ", style="green")
                label = self._get_label(name, "complete")
                content.append(label, style="green")
                content.append(
                    f" ({data['duration_ms']:.0f}ms)", style="dim white"
                )
                content.append("\n")

            elif data["status"] == "error":
                content.append("✗ ", style="red")
                label = self._get_label(name, "error")
                content.append(label, style="red")
                content.append("\n")

        return Panel(content, border_style="cyan", padding=(0, 1))

    def _render_complete(self, total_ms: float) -> Panel:
        """Render completion state."""
        content = Text()
        content.append("✓ ", style="green bold")
        content.append("Ready to scan", style="green bold")
        content.append(
            f" (Total: {total_ms:.0f}ms, one-time)", style="dim white"
        )

        return Panel(content, border_style="green", padding=(0, 1))

    def _get_label(self, name: str, status: str) -> str:
        """Get human-readable label for component."""
        labels = self.COMPONENT_LABELS.get(name, {})
        label_template = labels.get(status, name)

        # Format with variables (e.g., rules count)
        if name == "rules" and status == "complete":
            return label_template.format(count=self.rules_count)

        return label_template


class SimpleProgress(ProgressIndicator):
    """Plain text progress for CI/CD environments.

    Features:
    - No ANSI codes
    - Timestamped messages
    - Minimal output
    - Log-parser friendly
    """

    def __init__(self):
        self.start_time = None

    def start(self, message: str) -> None:
        """Print start message with timestamp."""
        self._log(message)

    def update_component(
        self,
        name: str,
        status: ComponentStatus,
        duration_ms: float,
        metadata: dict | None = None,
    ) -> None:
        """Print component completion (skip loading state)."""
        if status == "complete":
            label = self._get_label(name, metadata)
            self._log(f"{label} ({duration_ms:.0f}ms)")

    def complete(self, total_duration_ms: float) -> None:
        """Print completion message."""
        self._log(
            f"Initialization complete ({total_duration_ms:.0f}ms, one-time)"
        )

    def error(self, component: str, message: str) -> None:
        """Print error message."""
        self._log(f"ERROR: {component} - {message}")

    def _log(self, message: str) -> None:
        """Print timestamped message to stderr."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}", file=sys.stderr)

    def _get_label(self, name: str, metadata: dict | None = None) -> str:
        """Get simple label for component."""
        labels = {
            "rules": "Loaded detection rules",
            "ml_model": "Loaded ML model",
            "warmup": "Components ready",
        }

        label = labels.get(name, name)

        # Add count for rules
        if name == "rules" and metadata and "count" in metadata:
            label = f"Loaded {metadata['count']} rules"

        return label


class QuietProgress(ProgressIndicator):
    """Silent progress for --quiet mode.

    Only errors are shown (can't suppress errors).
    """

    def start(self, message: str) -> None:
        pass

    def update_component(
        self,
        name: str,
        status: ComponentStatus,
        duration_ms: float,
        metadata: dict | None = None,
    ) -> None:
        pass

    def complete(self, total_duration_ms: float) -> None:
        pass

    def error(self, component: str, message: str) -> None:
        # Errors must always be shown
        pass


def create_progress_indicator(mode: str) -> ProgressIndicator:
    """Factory function to create appropriate progress indicator.

    Args:
        mode: Progress mode (interactive, simple, quiet)

    Returns:
        Appropriate ProgressIndicator instance
    """
    if mode == "interactive":
        return InteractiveProgress()
    elif mode == "simple":
        return SimpleProgress()
    elif mode == "quiet":
        return QuietProgress()
    else:
        # Safe default for unknown modes
        return SimpleProgress()
