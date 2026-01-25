"""Dashboard configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class DashboardConfig:
    """Configuration for the security dashboard."""

    # Refresh settings
    refresh_interval_seconds: float = 2.0
    cache_ttl_seconds: float = 1.0

    # Data settings
    history_days: int = 30
    max_alerts_visible: int = 8  # Matches sidebar height

    # View settings
    theme: Literal["raxe", "matrix", "cyber"] = "raxe"
    show_logo: bool = True
    show_sparklines: bool = True
    show_performance: bool = True

    # Animation settings
    enable_animations: bool = False  # Disabled for performance
    chroma_speed: float = 0.5  # Seconds per color cycle step

    # Keyboard shortcuts (customizable)
    keybindings: dict[str, str] = field(
        default_factory=lambda: {
            "quit": "q",
            "refresh": "r",
            "up": "k",
            "down": "j",
            "expand": "enter",
            "back": "escape",
            "export": "e",
            "suppress": "s",
            "copy_hash": "c",
            "help": "?",
        }
    )


@dataclass
class ViewState:
    """Current state of the dashboard view."""

    mode: Literal["compact", "detail"] = "compact"
    selected_index: int = 0
    selected_alert_id: int | None = None
    scroll_offset: int = 0
    frame_count: int = 0  # For animations
    show_help: bool = False

    # Status message (shown briefly after actions)
    status_message: str | None = None
    status_message_time: float = 0.0

    # Flash animation for new alerts
    known_alert_ids: set[int] = field(default_factory=set)
    new_alert_ids: set[int] = field(default_factory=set)
    new_alert_flash_until: float = 0.0  # Time when flash effect ends
