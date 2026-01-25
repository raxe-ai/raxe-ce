"""Compact view - main dashboard overview."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.console import Group, RenderableType
from rich.style import Style
from rich.text import Text

from raxe import __version__
from raxe.cli.dashboard.config import DashboardConfig, ViewState
from raxe.cli.dashboard.data_provider import DashboardData
from raxe.cli.dashboard.themes import ThemeColors, render_logo
from raxe.cli.dashboard.views.base_view import BaseView
from raxe.cli.dashboard.widgets.alert_list import AlertListWidget
from raxe.cli.dashboard.widgets.ascii_box import AsciiBox
from raxe.cli.dashboard.widgets.latency_gauge import LatencyGaugeWidget
from raxe.cli.dashboard.widgets.sparkline import SparklineWidget
from raxe.cli.dashboard.widgets.status_panel import StatusPanelWidget
from raxe.cli.dashboard.widgets.threat_bar import ThreatBarWidget


class CompactView(BaseView):
    """Main dashboard compact view.

    Renders the full dashboard with:
    - Header with RAXE logo and timestamp
    - Threat summary bar
    - Alert feed (navigable)
    - 24h trend sparklines
    - Performance metrics
    - System status
    - Keyboard help footer
    """

    # Layout constants
    ALERT_LIST_WIDTH = 52  # Wider for more prompt preview
    SIDEBAR_WIDTH = 22

    def __init__(self, theme: ThemeColors, config: DashboardConfig):
        """Initialize the view."""
        super().__init__(theme, config)

        # Initialize widgets
        self.threat_bar = ThreatBarWidget(theme)
        self.alert_list = AlertListWidget(theme, max_visible=config.max_alerts_visible)
        self.sparkline = SparklineWidget(theme)
        self.latency_gauge = LatencyGaugeWidget(theme)
        self.status_panel = StatusPanelWidget(theme)

    def render(
        self, data: DashboardData, state: ViewState, terminal_width: int = 80
    ) -> RenderableType:
        """Render the compact view."""
        frame = state.frame_count
        animate = self.config.enable_animations
        width = self._clamp_width(terminal_width)

        lines: list[Text] = []

        # Top border with chroma animation
        lines.append(AsciiBox.frame_top(width, self.theme, frame, animate))

        # Empty line
        lines.append(self._frame_line(width, frame, animate))

        # Logo section (if enabled)
        if self.config.show_logo:
            lines.extend(self._render_logo_section(width, frame, animate))
            lines.append(self._frame_line(width, frame, animate))

        # Divider
        lines.append(AsciiBox.frame_divider(width, self.theme, frame, animate))

        # Threat summary section
        lines.append(self._inner_panel_top(" THREATS TODAY ", width - 4, frame))
        threat_content = self.threat_bar.render(data, frame)
        lines.append(
            self._frame_line_with_content(
                self._pad_inner(threat_content, width - 4), width, frame, animate
            )
        )
        lines.append(self._inner_panel_bottom(width - 4, frame))

        # Main content area: Alert Feed (left) + Sidebar (right)
        lines.append(self._inner_panel_top(" LIVE ALERT FEED ", width - 4, frame))
        lines.extend(self._render_alert_section(data, state, width, frame, animate))
        lines.append(self._inner_panel_bottom(width - 4, frame))

        # Status section
        lines.append(self._inner_panel_top(" SYSTEM STATUS ", width - 4, frame))
        status_content = self.status_panel.render(data, frame)
        lines.append(
            self._frame_line_with_content(
                self._pad_inner(status_content, width - 4), width, frame, animate
            )
        )
        lines.append(self._inner_panel_bottom(width - 4, frame))

        # Help overlay (if enabled)
        if state.show_help:
            lines.append(self._frame_line(width, frame, animate))
            lines.extend(self._render_help_overlay(width, frame))

        # Footer divider
        lines.append(AsciiBox.frame_divider(width, self.theme, frame, animate))

        # Keyboard help
        shortcuts = [
            ("Q", "Quit"),
            ("R", "Refresh"),
            ("↑↓", "Select"),
            ("Enter", "Details"),
            ("?", "Help"),
        ]
        lines.append(
            self._frame_line_with_content(
                self._render_shortcut_line(shortcuts), width, frame, animate
            )
        )

        # Bottom border
        lines.append(AsciiBox.frame_bottom(width, self.theme, frame, animate))

        return Group(*lines)

    def _render_logo_section(self, width: int, frame: int, animate: bool) -> list[Text]:
        """Render the logo with timestamp and version."""
        lines = []
        logo = render_logo(self.theme, small=False)
        logo_lines = logo.plain.split("\n")

        now = datetime.now(timezone.utc)
        time_str = now.strftime("%H:%M:%S")

        for i, logo_line in enumerate(logo_lines):
            content = Text()
            content.append(logo_line, style=Style(color=self.theme.accent))

            # Add timestamp/status on right side
            padding = 40 - len(logo_line)
            if padding > 0:
                content.append(" " * padding)

            if i == 0:
                content.append(time_str, style=Style(color=self.theme.accent, bold=True))
            elif i == 1:
                content.append("────────", style=Style(color=self.theme.muted))
            elif i == 2:
                content.append("SECURITY OPS", style=Style(color=self.theme.foreground))
            elif i == 3:
                content.append(f"v{__version__}", style=Style(color=self.theme.muted))

            lines.append(self._frame_line_with_content(content, width, frame, animate))

        return lines

    def _render_alert_section(
        self, data: DashboardData, state: ViewState, width: int, frame: int, animate: bool
    ) -> list[Text]:
        """Render alert list with sidebar."""
        lines = []

        # Get widget outputs
        alert_lines = self.alert_list.render(data.recent_alerts, state, width=self.ALERT_LIST_WIDTH)
        spark_lines = self.sparkline.render_dual(data.hourly_scans, data.hourly_threats, width=14)
        latency_lines = self.latency_gauge.render(data, bar_width=5, max_latency=50.0)

        # Build sidebar content rows
        sidebar_rows: list[Text | str] = []

        # 24H Trends header
        header = Text()
        header.append("─ 24H TRENDS ─", style=Style(color=self.theme.accent))
        sidebar_rows.append(header)
        sidebar_rows.extend(spark_lines)
        sidebar_rows.append("")  # spacer

        # Performance header
        perf_header = Text()
        perf_header.append("─ PERFORMANCE ─", style=Style(color=self.theme.accent))
        sidebar_rows.append(perf_header)
        sidebar_rows.extend(latency_lines)

        # Combine alert list with sidebar
        for i, alert_line in enumerate(alert_lines[: self.config.max_alerts_visible]):
            combined = Text()

            # Alert content (left side)
            alert_text = alert_line.plain if alert_line.plain else ""
            combined.append_text(alert_line)

            # Padding between columns
            padding_needed = self.ALERT_LIST_WIDTH - len(alert_text)
            if padding_needed > 0:
                combined.append(" " * padding_needed)

            combined.append(" │ ", style=Style(color=self.theme.border))

            # Sidebar content (right side)
            if i < len(sidebar_rows):
                row = sidebar_rows[i]
                if isinstance(row, Text):
                    combined.append_text(row)
                else:
                    combined.append(row, style=Style(color=self.theme.muted))

            lines.append(
                self._frame_line_with_content(
                    self._pad_inner(combined, width - 4), width, frame + i, animate
                )
            )

        # Navigation hint
        nav_hint = self.alert_list.render_footer(data.recent_alerts, state)
        lines.append(
            self._frame_line_with_content(
                self._pad_inner(nav_hint, width - 4), width, frame, animate
            )
        )

        return lines

    def _render_help_overlay(self, width: int, frame: int) -> list[Text]:
        """Render full help overlay panel."""
        animate = self.config.enable_animations
        lines: list[Text] = []

        lines.append(self._inner_panel_top(" KEYBOARD SHORTCUTS ", width - 4, frame))

        help_sections = [
            (
                "Navigation",
                [
                    ("↑ / k", "Move selection up"),
                    ("↓ / j", "Move selection down"),
                    ("Enter", "Expand selected alert"),
                ],
            ),
            (
                "Actions",
                [
                    ("R", "Force refresh data"),
                    ("E", "Export view to JSON"),
                    ("?", "Toggle this help"),
                ],
            ),
            (
                "General",
                [
                    ("Q", "Quit dashboard"),
                    ("Esc", "Back from detail view"),
                ],
            ),
            (
                "In Detail View",
                [
                    ("S", "Show suppress command"),
                    ("E", "Export alert to JSON"),
                    ("C", "Copy prompt hash"),
                    ("↑↓", "Navigate alerts"),
                ],
            ),
        ]

        for section_title, shortcuts in help_sections:
            header = Text()
            header.append(f"  {section_title}", style=Style(color=self.theme.accent, bold=True))
            padded = self._pad_inner(header, width - 4)
            lines.append(self._frame_line_with_content(padded, width, frame, animate))

            for key, description in shortcuts:
                line = Text()
                line.append("    ", style=Style(color=self.theme.background))
                line.append(f"[{key}]".ljust(12), style=Style(color=self.theme.foreground))
                line.append(description, style=Style(color=self.theme.muted))
                padded_line = self._pad_inner(line, width - 4)
                lines.append(self._frame_line_with_content(padded_line, width, frame, animate))

            lines.append(self._frame_line(width, frame, animate))

        lines.append(self._inner_panel_bottom(width - 4, frame))

        close_hint = Text()
        close_hint.append("Press ", style=Style(color=self.theme.muted))
        close_hint.append("[?]", style=Style(color=self.theme.accent))
        close_hint.append(" to close help", style=Style(color=self.theme.muted))
        lines.append(self._frame_line_with_content(close_hint, width, frame, animate, center=True))

        return lines
