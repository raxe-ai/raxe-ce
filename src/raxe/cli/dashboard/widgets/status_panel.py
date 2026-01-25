"""Status panel widget - displays system health indicators."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.style import Style
from rich.text import Text

from raxe.cli.dashboard.data_provider import DashboardData
from raxe.cli.dashboard.themes import ThemeColors


class StatusPanelWidget:
    """Displays system status with health indicators.

    Shows:
    ◉ RULES: 462    ◉ ML MODEL: ACTIVE    ◉ LAST SCAN: 45s ago
    """

    def __init__(self, theme: ThemeColors):
        """Initialize the widget.

        Args:
            theme: Theme for colors
        """
        self.theme = theme

    def render(self, data: DashboardData, frame: int = 0) -> Text:
        """Render the status panel.

        Args:
            data: Dashboard data
            frame: Animation frame (for pulsing indicators)

        Returns:
            Rich Text with status indicators
        """
        result = Text()

        # Rules status
        rules_ok = data.rules_loaded > 0
        result.append_text(self._render_indicator("RULES", rules_ok, frame))
        result.append(f": {data.rules_loaded}", style=Style(color=self.theme.foreground))
        result.append("    ", style=Style(color=self.theme.muted))

        # ML Model status
        ml_ok = data.ml_model_loaded
        result.append_text(self._render_indicator("ML MODEL", ml_ok, frame))
        status_text = "ACTIVE" if ml_ok else "OFF"
        result.append(f": {status_text}", style=Style(color=self.theme.foreground))
        result.append("    ", style=Style(color=self.theme.muted))

        # Last scan
        last_scan_str = self._format_last_scan(data.last_scan_time)
        result.append_text(self._render_indicator("LAST SCAN", True, frame))
        result.append(f": {last_scan_str}", style=Style(color=self.theme.foreground))

        return result

    def _render_indicator(self, label: str, ok: bool, frame: int) -> Text:
        """Render a status indicator.

        Args:
            label: Status label
            ok: True if healthy
            frame: Animation frame

        Returns:
            Rich Text with indicator
        """
        result = Text()

        # Indicator dot
        if ok:
            color = self.theme.ok
            char = "◉"
        else:
            color = self.theme.error
            # Pulse error indicators
            char = "◉" if frame % 4 < 2 else "○"

        result.append(char, style=Style(color=color))
        result.append(" ", style=Style(color=self.theme.muted))
        result.append(label, style=Style(color=self.theme.muted))

        return result

    def _format_last_scan(self, timestamp: datetime | None) -> str:
        """Format last scan timestamp as relative time.

        Args:
            timestamp: Last scan datetime

        Returns:
            Relative time string (e.g., "45s ago")
        """
        if timestamp is None:
            return "Never"

        now = datetime.now(timezone.utc)
        delta = now - timestamp

        seconds = int(delta.total_seconds())

        if seconds < 60:
            return f"{seconds}s ago"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours}h ago"
        else:
            days = seconds // 86400
            return f"{days}d ago"

    def render_expanded(self, data: DashboardData, frame: int = 0) -> list[Text]:
        """Render expanded multi-line version.

        Args:
            data: Dashboard data
            frame: Animation frame

        Returns:
            List of Rich Text lines
        """
        lines = []

        # Rules
        line1 = Text()
        rules_ok = data.rules_loaded > 0
        line1.append_text(self._render_indicator("Rules", rules_ok, frame))
        line1.append(f": {data.rules_loaded} loaded", style=Style(color=self.theme.foreground))
        lines.append(line1)

        # ML Model
        line2 = Text()
        ml_ok = data.ml_model_loaded
        line2.append_text(self._render_indicator("ML Model", ml_ok, frame))
        status = "Active" if ml_ok else "Disabled"
        line2.append(f": {status}", style=Style(color=self.theme.foreground))
        lines.append(line2)

        # Last Scan
        line3 = Text()
        line3.append_text(self._render_indicator("Last Scan", True, frame))
        last_scan_str = self._format_last_scan(data.last_scan_time)
        line3.append(f": {last_scan_str}", style=Style(color=self.theme.foreground))
        lines.append(line3)

        # Refresh time
        line4 = Text()
        refresh_str = data.last_refresh.strftime("%H:%M:%S")
        line4.append_text(self._render_indicator("Refresh", True, frame))
        line4.append(f": {refresh_str}", style=Style(color=self.theme.foreground))
        lines.append(line4)

        return lines
