"""Dashboard orchestrator - main controller for the security dashboard."""

from __future__ import annotations

import json
import sys
import time
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console, RenderableType
from rich.live import Live

from raxe.cli.dashboard.config import DashboardConfig, ViewState
from raxe.cli.dashboard.data_provider import DashboardData, DashboardDataProvider
from raxe.cli.dashboard.themes import get_theme

if TYPE_CHECKING:
    from raxe.cli.dashboard.views.compact_view import CompactView
    from raxe.cli.dashboard.views.detail_view import DetailView


class DashboardOrchestrator:
    """Main controller for the security dashboard.

    Handles:
    - Rich.Live display lifecycle
    - Keyboard input (non-blocking)
    - View state management (compact/detail)
    - Animation frame counting
    - Data refresh coordination
    """

    def __init__(
        self,
        config: DashboardConfig | None = None,
        console: Console | None = None,
    ):
        """Initialize the dashboard orchestrator.

        Args:
            config: Dashboard configuration (uses defaults if None)
            console: Rich Console instance (creates new if None)
        """
        self.config = config or DashboardConfig()
        self.console = console or Console()
        self.theme = get_theme(self.config.theme)

        # State management
        self.state = ViewState()
        self.running = False

        # Data provider
        self.data_provider = DashboardDataProvider(
            history_days=self.config.history_days,
            cache_ttl_seconds=self.config.cache_ttl_seconds,
        )

        # Views (lazy loaded)
        self._compact_view: CompactView | None = None
        self._detail_view: DetailView | None = None

    @property
    def compact_view(self) -> CompactView:
        """Get or create the compact view."""
        if self._compact_view is None:
            from raxe.cli.dashboard.views.compact_view import CompactView

            self._compact_view = CompactView(self.theme, self.config)
        return self._compact_view

    @property
    def detail_view(self) -> DetailView:
        """Get or create the detail view."""
        if self._detail_view is None:
            from raxe.cli.dashboard.views.detail_view import DetailView

            self._detail_view = DetailView(self.theme, self.config)
        return self._detail_view

    def start(self) -> None:
        """Start the dashboard.

        This enters the main display loop and blocks until the user
        quits (with 'q' key).
        """
        self.running = True

        # Initialize known alerts (so initial alerts don't flash)
        data = self.data_provider.get_data()
        self.state.known_alert_ids = {alert.scan_id for alert in data.recent_alerts}

        # Use alternate screen for clean exit
        with Live(
            self._render(),
            console=self.console,
            refresh_per_second=10,  # 10 FPS for responsive input
            screen=True,  # Alternate screen buffer
            transient=False,
        ) as live:
            self._run_loop(live)

    def _run_loop(self, live: Live) -> None:
        """Main event loop.

        Uses select() to wait for either keyboard input OR timeout,
        providing instant response to keypresses while limiting CPU usage.

        Args:
            live: Rich Live instance
        """
        # Try to set up keyboard input
        keyboard_available = self._setup_keyboard()

        last_refresh = time.time()
        last_render = 0.0
        render_interval = 1.0 / 30  # 30 FPS max for smooth animations

        try:
            while self.running:
                # Wait for input OR timeout (event-driven, not polling)
                # This gives instant response to keypresses
                self._wait_for_input_or_timeout(render_interval)

                current_time = time.time()
                had_input = False

                # Process ALL available keyboard input (drain buffer)
                if keyboard_available:
                    while True:
                        key = self._read_key()
                        if key:
                            self._handle_key(key)
                            had_input = True
                        else:
                            break

                # Refresh data if needed
                if current_time - last_refresh >= self.config.refresh_interval_seconds:
                    self.data_provider.force_refresh()
                    last_refresh = current_time
                    self._detect_new_alerts()

                # Update display (immediate after input, or on timer)
                if had_input or (current_time - last_render >= render_interval):
                    self.state.frame_count += 1
                    live.update(self._render())
                    last_render = current_time

        finally:
            self._cleanup_keyboard()

    def _wait_for_input_or_timeout(self, timeout: float) -> bool:
        """Wait for keyboard input or timeout, whichever comes first.

        This is the key to responsive input - we don't poll, we wait
        for events. Returns immediately when a key is pressed.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if input is available, False if timeout
        """
        if sys.platform == "win32":
            # Windows: Use small sleep intervals and check kbhit
            import msvcrt

            end_time = time.time() + timeout
            while time.time() < end_time:
                if msvcrt.kbhit():  # type: ignore[attr-defined]
                    return True
                time.sleep(0.001)  # 1ms granularity on Windows
            return False
        else:
            # Unix/macOS: Use select() for true event-driven waiting
            import select

            try:
                readable, _, _ = select.select([sys.stdin], [], [], timeout)
                return bool(readable)
            except Exception:
                time.sleep(timeout)
                return False

    def _render(self) -> RenderableType:
        """Render the current view.

        Returns:
            Rich renderable for display
        """
        data = self.data_provider.get_data()

        # Get current terminal width for responsive layout
        terminal_width = self.console.size.width

        if self.state.mode == "detail" and self.state.selected_alert_id is not None:
            # Get full alert details for detail view
            alert = self.data_provider.get_alert_details(self.state.selected_alert_id)
            return self.detail_view.render(alert, self.state, terminal_width)
        else:
            return self.compact_view.render(data, self.state, terminal_width)

    def _handle_key(self, key: str) -> None:
        """Handle keyboard input.

        Args:
            key: Key character pressed
        """
        data = self.data_provider.get_data()

        if self.state.mode == "compact":
            self._handle_compact_key(key, data)
        else:
            self._handle_detail_key(key)

    def _handle_compact_key(self, key: str, data: DashboardData) -> None:
        """Handle keyboard input in compact view.

        Args:
            key: Key character pressed
            data: Current dashboard data
        """
        if key in ("q", "Q"):
            self.running = False

        elif key in ("r", "R"):
            self.data_provider.force_refresh()

        elif key in ("j", "\x1b[B"):  # j or down arrow
            # Move selection down
            if data.recent_alerts:
                max_idx = min(len(data.recent_alerts) - 1, self.config.max_alerts_visible - 1)
                self.state.selected_index = min(self.state.selected_index + 1, max_idx)

        elif key in ("k", "\x1b[A"):  # k or up arrow
            # Move selection up
            self.state.selected_index = max(0, self.state.selected_index - 1)

        elif key in ("\r", "\n", "\x1b[C"):  # Enter or Right arrow
            # Expand selected alert
            if data.recent_alerts and 0 <= self.state.selected_index < len(data.recent_alerts):
                alert = data.recent_alerts[self.state.selected_index]
                self.state.selected_alert_id = alert.scan_id
                self.state.mode = "detail"

        elif key == "?":
            self.state.show_help = not self.state.show_help

    def _handle_detail_key(self, key: str) -> None:
        """Handle keyboard input in detail view.

        Args:
            key: Key character pressed
        """
        if key in ("q", "\x1b", "\x1b[D"):  # q or Escape or Left arrow
            # Back to compact view
            self.state.mode = "compact"
            self.state.selected_alert_id = None

        elif key in ("j", "\x1b[B"):  # j or down arrow
            # Next alert
            self._navigate_alert(1)

        elif key in ("k", "\x1b[A"):  # k or up arrow
            # Previous alert
            self._navigate_alert(-1)

        elif key in ("e", "E"):
            # Export alert to JSON
            self._export_current_alert()

        elif key in ("c", "C"):
            # Copy hash to clipboard
            self._copy_hash_to_clipboard()

        elif key in ("s", "S"):
            # Suppress rule - show message (full implementation needs suppress command)
            self.state.status_message = "Suppress: Use 'raxe suppress <rule_id>'"
            self.state.status_message_time = time.time()

    def _navigate_alert(self, direction: int) -> None:
        """Navigate to next/previous alert.

        Args:
            direction: +1 for next, -1 for previous
        """
        data = self.data_provider.get_data()
        if not data.recent_alerts:
            return

        # Find current index
        current_idx = None
        for i, alert in enumerate(data.recent_alerts):
            if alert.scan_id == self.state.selected_alert_id:
                current_idx = i
                break

        if current_idx is None:
            return

        # Calculate new index
        new_idx = current_idx + direction
        if 0 <= new_idx < len(data.recent_alerts):
            self.state.selected_index = new_idx
            self.state.selected_alert_id = data.recent_alerts[new_idx].scan_id

    def _export_current_alert(self) -> None:
        """Export current alert to JSON file."""
        if self.state.selected_alert_id is None:
            return

        alert = self.data_provider.get_alert_details(self.state.selected_alert_id)
        if alert is None:
            self.state.status_message = "Export failed: Alert not found"
            self.state.status_message_time = time.time()
            return

        # Build export data
        export_data = {
            "scan_id": alert.scan_id,
            "timestamp": alert.timestamp.isoformat(),
            "severity": alert.severity,
            "rule_ids": alert.rule_ids,
            "descriptions": alert.descriptions,
            "detection_count": alert.detection_count,
            "confidence": alert.confidence,
            "prompt_hash": alert.prompt_hash,
            "l1_detections": alert.l1_detections,
            "l2_detections": alert.l2_detections,
            "event_id": alert.event_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

        # Write to file
        filename = f"raxe_alert_{alert.scan_id}_{int(time.time())}.json"
        filepath = Path.cwd() / filename
        with filepath.open("w") as f:
            json.dump(export_data, f, indent=2)

        self.state.status_message = f"Exported: {filename}"
        self.state.status_message_time = time.time()

    def _copy_hash_to_clipboard(self) -> None:
        """Copy current alert's prompt hash to clipboard."""
        if self.state.selected_alert_id is None:
            return

        alert = self.data_provider.get_alert_details(self.state.selected_alert_id)
        if alert is None:
            self.state.status_message = "Copy failed: Alert not found"
            self.state.status_message_time = time.time()
            return

        # Try to copy to clipboard
        try:
            import subprocess

            # Use pbcopy on macOS, xclip on Linux
            if sys.platform == "darwin":
                subprocess.run(  # noqa: S603
                    ["pbcopy"],  # noqa: S607
                    input=alert.prompt_hash.encode(),
                    check=True,
                )
            elif sys.platform.startswith("linux"):
                subprocess.run(  # noqa: S603
                    ["xclip", "-selection", "clipboard"],  # noqa: S607
                    input=alert.prompt_hash.encode(),
                    check=True,
                )
            else:
                # Windows - use clip
                subprocess.run(  # noqa: S603
                    ["clip"],  # noqa: S607
                    input=alert.prompt_hash.encode(),
                    check=True,
                )

            self.state.status_message = f"Copied: {alert.prompt_hash[:20]}..."
            self.state.status_message_time = time.time()
        except Exception:
            self.state.status_message = f"Hash: {alert.prompt_hash}"
            self.state.status_message_time = time.time()

    # Keyboard handling (platform-specific)

    def _setup_keyboard(self) -> bool:
        """Set up non-blocking keyboard input.

        Returns:
            True if keyboard input is available
        """
        if sys.platform == "win32":
            # Windows - msvcrt is always available
            return True

        try:
            import termios
            import tty

            self._old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
            return True
        except Exception:
            return False

    def _cleanup_keyboard(self) -> None:
        """Restore terminal settings."""
        if sys.platform == "win32":
            return

        # Terminal cleanup can fail in various edge cases - that's OK
        with suppress(Exception):
            import termios

            if hasattr(self, "_old_settings"):
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)

    def _read_key(self) -> str | None:
        """Read a key without blocking.

        Returns:
            Key character if available, None otherwise
        """
        if sys.platform == "win32":
            return self._read_key_windows()
        else:
            return self._read_key_unix()

    def _read_key_windows(self) -> str | None:
        """Read key on Windows."""
        # Non-blocking key read can fail - return None to indicate no key
        with suppress(Exception):
            import msvcrt

            if msvcrt.kbhit():  # type: ignore[attr-defined]
                ch = msvcrt.getch()  # type: ignore[attr-defined]
                # Handle special keys (arrows)
                if ch in (b"\x00", b"\xe0"):
                    ch2 = msvcrt.getch()  # type: ignore[attr-defined]
                    if ch2 == b"H":  # Up
                        return "\x1b[A"
                    elif ch2 == b"P":  # Down
                        return "\x1b[B"
                return str(ch.decode("utf-8", errors="ignore"))
        return None

    def _read_key_unix(self) -> str | None:
        """Read key on Unix/macOS."""
        import fcntl
        import os
        import select

        try:
            # Check if input is available (non-blocking)
            if not select.select([sys.stdin], [], [], 0)[0]:
                return None

            ch = sys.stdin.read(1)

            # Handle escape sequences (arrows come as \x1b[A, \x1b[B, etc.)
            if ch == "\x1b":
                # Set non-blocking mode to read remaining escape sequence bytes
                fd = sys.stdin.fileno()
                old_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)

                try:
                    # Try to read the rest of escape sequence
                    try:
                        ch2 = sys.stdin.read(1)
                        if ch2 == "[":
                            try:
                                ch3 = sys.stdin.read(1)
                                return f"\x1b[{ch3}"
                            except (OSError, BlockingIOError):
                                return "\x1b["
                        elif ch2:
                            return f"\x1b{ch2}"
                        else:
                            return "\x1b"
                    except (OSError, BlockingIOError):
                        return "\x1b"  # Just escape key
                finally:
                    # Restore blocking mode
                    fcntl.fcntl(fd, fcntl.F_SETFL, old_flags)

            return ch

        except Exception:
            return None

    def _detect_new_alerts(self) -> None:
        """Detect newly arrived alerts and mark them for flash animation."""
        data = self.data_provider.get_data()

        # Get current alert IDs
        current_ids = {alert.scan_id for alert in data.recent_alerts}

        # Find new alerts (in current but not in known)
        new_ids = current_ids - self.state.known_alert_ids

        if new_ids:
            # Mark new alerts for flash effect
            self.state.new_alert_ids = new_ids
            self.state.new_alert_flash_until = time.time() + 2.0  # Flash for 2 seconds

        # Update known alerts
        self.state.known_alert_ids = current_ids

        # Clear flash effect after duration
        if time.time() > self.state.new_alert_flash_until:
            self.state.new_alert_ids = set()

    def stop(self) -> None:
        """Stop the dashboard gracefully."""
        self.running = False
