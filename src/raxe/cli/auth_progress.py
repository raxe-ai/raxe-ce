"""Visual progress display for CLI authentication flow.

Provides real-time feedback during the browser authentication polling phase
with progress bar, countdown timer, and state-based help messages.

States:
- INITIAL (0-30s): Simple waiting message
- WAITING (30s-150s): Progress continues
- HELP (150s / 50%): Show troubleshooting help
- WARNING (225s / 75%): Yellow warning about time
- CRITICAL (270s / 90%): Red countdown, urgent

Example usage:
    from raxe.cli.auth_progress import AuthProgress, AuthState, render_auth_progress
    from rich.live import Live

    progress = AuthProgress(connect_url="https://...")
    with Live(render_auth_progress(progress), refresh_per_second=4) as live:
        while not done:
            progress.update_elapsed(time.time() - start)
            live.update(render_auth_progress(progress))
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.text import Text

if TYPE_CHECKING:
    pass


class AuthState(Enum):
    """Authentication progress states."""

    INITIAL = "initial"  # 0-30s
    WAITING = "waiting"  # 30s-150s
    HELP = "help"  # 150s (50% mark)
    WARNING = "warning"  # 225s-270s (75%-90%)
    CRITICAL = "critical"  # 270s-300s (90%-100%)
    SUCCESS = "success"
    TIMEOUT = "timeout"
    EXPIRED = "expired"
    ERROR = "error"
    NETWORK_ISSUE = "network_issue"


# State transition thresholds (percentage of total time)
HELP_THRESHOLD_PCT = 50  # Show help at 50%
WARNING_THRESHOLD_PCT = 75  # Yellow warning at 75%
CRITICAL_THRESHOLD_PCT = 90  # Red countdown at 90%

# Spinner frames for different states
SPINNER_FRAMES = ["*", "o", "O", "o"]
SPINNER_WARNING = "!"
SPINNER_NETWORK = "~"


@dataclass
class AuthProgress:
    """Tracks authentication progress state.

    Attributes:
        connect_url: The URL for browser authentication
        total_seconds: Total timeout in seconds (default 300 = 5 min)
        elapsed_seconds: Time elapsed since start
        state: Current auth state
        error_message: Error message if in error state
        help_shown: Whether help message has been shown (one-time)
    """

    connect_url: str = ""
    total_seconds: float = 300.0
    elapsed_seconds: float = 0.0
    state: AuthState = AuthState.INITIAL
    error_message: str = ""
    help_shown: bool = False
    _spinner_index: int = field(default=0, repr=False)
    _last_spinner_time: float = field(default_factory=time.time, repr=False)

    @property
    def remaining_seconds(self) -> float:
        """Seconds remaining until timeout."""
        return max(0, self.total_seconds - self.elapsed_seconds)

    @property
    def progress_percent(self) -> float:
        """Progress as percentage (0-100)."""
        return min(100, (self.elapsed_seconds / self.total_seconds) * 100)

    @property
    def remaining_formatted(self) -> str:
        """Remaining time as MM:SS string."""
        remaining = int(self.remaining_seconds)
        mins, secs = divmod(remaining, 60)
        return f"{mins}:{secs:02d}"

    def update_elapsed(self, elapsed: float) -> None:
        """Update elapsed time and recalculate state.

        Args:
            elapsed: Seconds elapsed since authentication started
        """
        self.elapsed_seconds = elapsed
        self._update_state()

    def _update_state(self) -> None:
        """Update state based on elapsed time."""
        # Don't override terminal states
        if self.state in (
            AuthState.SUCCESS,
            AuthState.TIMEOUT,
            AuthState.EXPIRED,
            AuthState.ERROR,
        ):
            return

        # Network issues are transient - they'll be cleared by caller
        if self.state == AuthState.NETWORK_ISSUE:
            return

        pct = self.progress_percent

        if pct >= CRITICAL_THRESHOLD_PCT:
            self.state = AuthState.CRITICAL
        elif pct >= WARNING_THRESHOLD_PCT:
            self.state = AuthState.WARNING
        elif pct >= HELP_THRESHOLD_PCT:
            self.state = AuthState.HELP
        elif pct >= 10:  # After first 30 seconds
            self.state = AuthState.WAITING
        else:
            self.state = AuthState.INITIAL

    def set_network_issue(self) -> None:
        """Mark as having network issues."""
        self.state = AuthState.NETWORK_ISSUE

    def clear_network_issue(self) -> None:
        """Clear network issue state and recalculate."""
        if self.state == AuthState.NETWORK_ISSUE:
            self.state = AuthState.INITIAL  # Will be recalculated
            self._update_state()

    def set_success(self) -> None:
        """Mark authentication as successful."""
        self.state = AuthState.SUCCESS

    def set_expired(self) -> None:
        """Mark session as expired."""
        self.state = AuthState.EXPIRED

    def set_timeout(self) -> None:
        """Mark as timed out."""
        self.state = AuthState.TIMEOUT

    def set_error(self, message: str) -> None:
        """Mark as error with message."""
        self.state = AuthState.ERROR
        self.error_message = message

    def get_spinner_frame(self) -> str:
        """Get current spinner frame with animation."""
        now = time.time()

        # Update spinner every 250ms
        if now - self._last_spinner_time >= 0.25:
            self._spinner_index = (self._spinner_index + 1) % len(SPINNER_FRAMES)
            self._last_spinner_time = now

        # Special spinners for different states
        if self.state == AuthState.NETWORK_ISSUE:
            return SPINNER_NETWORK
        if self.state in (AuthState.WARNING, AuthState.CRITICAL):
            return SPINNER_WARNING

        return SPINNER_FRAMES[self._spinner_index]


def _get_state_style(state: AuthState) -> str:
    """Get Rich style for a given state."""
    return {
        AuthState.INITIAL: "cyan",
        AuthState.WAITING: "cyan",
        AuthState.HELP: "cyan",
        AuthState.WARNING: "yellow",
        AuthState.CRITICAL: "red",
        AuthState.SUCCESS: "green",
        AuthState.NETWORK_ISSUE: "yellow",
        AuthState.ERROR: "red",
        AuthState.TIMEOUT: "red",
        AuthState.EXPIRED: "red",
    }.get(state, "white")


def _render_progress_bar(percent: float, width: int = 50) -> str:
    """Render a text-based progress bar.

    Args:
        percent: Progress percentage (0-100)
        width: Width of the bar in characters

    Returns:
        String like "[====                                          ] 12%"
    """
    filled = int(width * percent / 100)
    empty = width - filled
    bar = "=" * filled + " " * empty
    return f"[{bar}] {percent:.0f}%"


def _get_help_text(state: AuthState, connect_url: str) -> Text:
    """Get contextual help text for a given state.

    Args:
        state: Current auth state
        connect_url: URL for browser auth

    Returns:
        Rich Text object with help content
    """
    text = Text()

    if state == AuthState.HELP:
        text.append("Taking a while? Try these:\n\n", style="bold")
        text.append("  * Browser didn't open?\n", style="white")
        text.append("    Copy this URL: ", style="dim")
        text.append(connect_url, style="blue underline")
        text.append("\n\n", style="")
        text.append("  * Already completed?\n", style="white")
        text.append(
            "    Check the browser tab - you may need to click 'Authorize'\n\n",
            style="dim",
        )
        text.append("  * Wrong account?\n", style="white")
        text.append(
            "    Sign out in browser, then refresh the page",
            style="dim",
        )

    elif state == AuthState.WARNING:
        text.append("Running low on time!\n\n", style="yellow bold")
        text.append("If you're having trouble, you can:\n", style="white")
        text.append("  - Press ", style="dim")
        text.append("Ctrl+C", style="cyan")
        text.append(" to cancel and try again\n", style="dim")
        text.append("  - Set your API key manually:\n", style="dim")
        text.append("    raxe config set api_key YOUR_KEY", style="cyan")

    elif state == AuthState.CRITICAL:
        text.append("Almost out of time!\n\n", style="red bold")
        text.append(
            "Complete authentication now or the session will expire.",
            style="white",
        )

    elif state == AuthState.NETWORK_ISSUE:
        text.append("Network hiccup detected. Will keep trying...\n", style="yellow")
        text.append(
            "Check your internet connection if this persists.",
            style="dim",
        )

    return text


def render_auth_progress(progress: AuthProgress) -> Panel:
    """Render the authentication progress display.

    Creates a Rich Panel showing:
    - Spinner and status message
    - Time remaining countdown
    - Progress bar
    - State-specific help text

    Args:
        progress: Current AuthProgress state

    Returns:
        Rich Panel for display with Live
    """
    content = Text()
    state = progress.state
    style = _get_state_style(state)

    # Spinner and status line
    spinner = progress.get_spinner_frame()
    content.append(f"  [{spinner}]  ", style=f"{style} bold")

    if state == AuthState.NETWORK_ISSUE:
        content.append("Connection issue, retrying...", style="yellow")
    else:
        content.append("Waiting for browser authentication", style="bold")

    content.append("\n\n", style="")

    # Instruction line
    content.append("       Complete sign-in in your browser to continue.\n", style="")

    # Time remaining
    time_style = (
        "red bold"
        if state == AuthState.CRITICAL
        else ("yellow" if state == AuthState.WARNING else "dim")
    )
    content.append("       Time remaining: ", style="")
    content.append(progress.remaining_formatted, style=time_style)
    content.append("\n\n", style="")

    # Progress bar
    bar = _render_progress_bar(progress.progress_percent)
    content.append(f"       {bar}\n", style="")

    # State-specific help section
    if state in (AuthState.HELP, AuthState.WARNING, AuthState.CRITICAL, AuthState.NETWORK_ISSUE):
        content.append("\n  ", style="")
        content.append("-" * 60, style="dim")
        content.append("\n\n", style="")
        content.append(_get_help_text(state, progress.connect_url))

    return Panel(
        content,
        border_style=style,
        width=70,
        padding=(0, 1),
    )


def render_cancelled_message() -> Text:
    """Render message for when user cancels with Ctrl+C."""
    text = Text()
    text.append("\n\nAuthentication cancelled.\n\n", style="yellow")
    text.append("You can:\n", style="white")
    text.append("  - Run ", style="dim")
    text.append("raxe auth", style="cyan")
    text.append(" again when ready\n", style="dim")
    text.append("  - Set your key manually: ", style="dim")
    text.append("raxe config set api_key YOUR_KEY\n", style="cyan")
    text.append("  - Get a key at: ", style="dim")
    text.append("https://console.raxe.ai/keys", style="blue underline")
    text.append("\n", style="")
    return text


def render_timeout_message() -> Text:
    """Render message for authentication timeout."""
    text = Text()
    text.append("\n\nWhat to do:\n", style="white")
    text.append("  1. Run ", style="dim")
    text.append("raxe auth", style="cyan")
    text.append(" again to get a fresh session\n", style="dim")
    text.append("  2. Make sure to complete browser sign-in within 5 minutes\n\n", style="dim")
    text.append("Or set your API key manually:\n", style="white")
    text.append("  - Visit: ", style="dim")
    text.append("https://console.raxe.ai/keys\n", style="blue underline")
    text.append("  - Then run: ", style="dim")
    text.append("raxe config set api_key YOUR_API_KEY", style="cyan")
    text.append("\n", style="")
    return text


__all__ = [
    "CRITICAL_THRESHOLD_PCT",
    "HELP_THRESHOLD_PCT",
    "WARNING_THRESHOLD_PCT",
    "AuthProgress",
    "AuthState",
    "render_auth_progress",
    "render_cancelled_message",
    "render_timeout_message",
]
