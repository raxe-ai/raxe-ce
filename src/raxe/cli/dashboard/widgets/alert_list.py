"""Alert list widget - navigable list of recent alerts."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text

from raxe.cli.dashboard.config import ViewState
from raxe.cli.dashboard.data_provider import AlertItem
from raxe.cli.dashboard.themes import ThemeColors, get_severity_color


class AlertListWidget:
    """Navigable list of recent alerts.

    Displays alerts with:
    - Selection indicator (▶ for selected)
    - Timestamp
    - Severity badge
    - Rule IDs
    - Prompt preview
    """

    def __init__(self, theme: ThemeColors, max_visible: int = 15):
        """Initialize the widget.

        Args:
            theme: Theme for colors
            max_visible: Maximum alerts to show
        """
        self.theme = theme
        self.max_visible = max_visible

    def render(
        self,
        alerts: list[AlertItem],
        state: ViewState,
        width: int = 50,
    ) -> list[Text]:
        """Render the alert list.

        Args:
            alerts: List of alerts to display
            state: Current view state (for selection)
            width: Available width

        Returns:
            List of Rich Text lines
        """
        lines: list[Text] = []

        if not alerts:
            line = Text()
            line.append("  No recent alerts", style=Style(color=self.theme.muted, italic=True))
            lines.append(line)
            return lines

        visible_alerts = alerts[: self.max_visible]

        for i, alert in enumerate(visible_alerts):
            line = self._render_alert_line(alert, i, state, width)
            lines.append(line)

        # Pad to max_visible if needed
        while len(lines) < self.max_visible:
            lines.append(Text())

        return lines

    def _render_alert_line(
        self,
        alert: AlertItem,
        index: int,
        state: ViewState,
        width: int,
    ) -> Text:
        """Render a single alert line.

        Args:
            alert: Alert to render
            index: Index in list
            state: View state for selection
            width: Available width

        Returns:
            Rich Text for the alert
        """
        line = Text()
        is_selected = index == state.selected_index
        is_new = alert.scan_id in state.new_alert_ids

        # Selection/new indicator - show both states clearly
        if is_new and is_selected:
            # New + selected: show star with arrow
            line.append("★", style=Style(color=self.theme.warn, bold=True, blink=True))
            line.append("▶", style=Style(color=self.theme.accent, bold=True))
        elif is_new:
            # New but not selected: show star
            line.append("★ ", style=Style(color=self.theme.warn, bold=True, blink=True))
        elif is_selected:
            # Selected but not new: show arrow
            line.append("▶ ", style=Style(color=self.theme.accent, bold=True))
        else:
            line.append("  ", style=Style(color=self.theme.muted))

        # Determine highlight level: new > selected > normal
        is_highlighted = is_selected or is_new

        # Timestamp (HH:MM format) - flash color for new alerts
        time_str = alert.timestamp.strftime("%H:%M")
        if is_new:
            time_style = Style(color=self.theme.warn, bold=True)
        elif is_highlighted:
            time_style = Style(color=self.theme.accent)
        else:
            time_style = Style(color=self.theme.muted)
        line.append(time_str, style=time_style)
        line.append(" ", style=Style(color=self.theme.muted))

        # Severity badge (dot + space + abbreviation)
        sev_color = get_severity_color(alert.severity, self.theme)
        sev_abbrev = self._severity_abbrev(alert.severity)
        sev_style = Style(color=sev_color, bold=True)
        line.append("⬤ ", style=sev_style)  # Space after dot
        line.append(sev_abbrev.ljust(4), style=sev_style)
        line.append(" ", style=Style(color=self.theme.muted))

        # Rule IDs (first 2)
        rules_str = self._format_rules(alert.rule_ids)
        rules_style = Style(color=self.theme.foreground if is_highlighted else self.theme.muted)
        line.append(rules_str.ljust(12), style=rules_style)
        line.append(" ", style=Style(color=self.theme.muted))

        # Prompt preview (fill remaining width)
        # Components: indicator(2) + time(5) + spaces + dot+sev(6) + rules(12)
        used_width = 2 + 5 + 1 + 2 + 4 + 1 + 12 + 1  # = 28
        preview_width = max(10, width - used_width)
        preview = self._truncate(alert.prompt_preview, preview_width)
        if is_new:
            preview_style = Style(color=self.theme.warn, bold=True)
        elif is_highlighted:
            preview_style = Style(color=self.theme.foreground)
        else:
            preview_style = Style(color=self.theme.muted)
        line.append(preview, style=preview_style)

        return line

    def _severity_abbrev(self, severity: str) -> str:
        """Get abbreviated severity name."""
        abbrevs = {
            "CRITICAL": "CRIT",
            "HIGH": "HIGH",
            "MEDIUM": "MED",
            "LOW": "LOW",
            "INFO": "INFO",
        }
        return abbrevs.get(severity.upper(), severity[:4].upper())

    def _format_rules(self, rule_ids: list[str], max_width: int = 12) -> str:
        """Format rule IDs for display, truncating to fit width."""
        if not rule_ids:
            return ""

        # Just show first rule, truncated
        first_rule = rule_ids[0]
        extra = len(rule_ids) - 1

        if extra > 0:
            # Reserve space for "+N" suffix
            suffix = f"+{extra}"
            available = max_width - len(suffix)
            if len(first_rule) > available:
                first_rule = first_rule[: available - 1] + "…"
            return first_rule + suffix
        else:
            if len(first_rule) > max_width:
                return first_rule[: max_width - 1] + "…"
            return first_rule

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text with ellipsis."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 2] + ".."

    def render_footer(self, alerts: list[AlertItem], state: ViewState) -> Text:
        """Render the list footer with navigation hint.

        Args:
            alerts: List of alerts
            state: View state

        Returns:
            Rich Text footer
        """
        line = Text()
        line.append("[↑↓]", style=Style(color=self.theme.accent))
        line.append(" Navigate  ", style=Style(color=self.theme.muted))
        line.append("[Enter]", style=Style(color=self.theme.accent))
        line.append(" Expand", style=Style(color=self.theme.muted))

        return line
