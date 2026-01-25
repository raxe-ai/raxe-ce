"""Threat summary bar widget - displays severity counts."""

from __future__ import annotations

from typing import ClassVar

from rich.style import Style
from rich.text import Text

from raxe.cli.dashboard.data_provider import DashboardData
from raxe.cli.dashboard.themes import ThemeColors, get_severity_color


class ThreatBarWidget:
    """Displays threat counts by severity level.

    Shows severity badges with counts:
    ⬤ CRIT: 2   ⬤ HIGH: 5   ⬤ MED: 12   ⬤ LOW: 8   ⬤ INFO: 3
    """

    SEVERITY_ORDER: ClassVar[list[str]] = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    SEVERITY_ABBREV: ClassVar[dict[str, str]] = {
        "CRITICAL": "CRIT",
        "HIGH": "HIGH",
        "MEDIUM": "MED",
        "LOW": "LOW",
        "INFO": "INFO",
    }

    def __init__(self, theme: ThemeColors):
        """Initialize the widget.

        Args:
            theme: Theme for colors
        """
        self.theme = theme

    def render(self, data: DashboardData, frame: int = 0) -> Text:
        """Render the threat bar.

        Args:
            data: Dashboard data with severity counts
            frame: Animation frame (for pulsing CRITICAL)

        Returns:
            Rich Text with severity badges
        """
        result = Text()

        for i, severity in enumerate(self.SEVERITY_ORDER):
            count = data.threats_by_severity.get(severity, 0)
            color = get_severity_color(severity, self.theme)
            abbrev = self.SEVERITY_ABBREV[severity]

            # Add separator
            if i > 0:
                result.append("   ", style=Style(color=self.theme.muted))

            # Severity dot (pulse for critical with threats)
            dot_style = Style(color=color)
            if severity == "CRITICAL" and count > 0:
                # Pulse effect: alternate bold
                if frame % 4 < 2:
                    dot_style = Style(color=color, bold=True)

            result.append("⬤", style=dot_style)
            result.append(" ", style=Style(color=self.theme.muted))
            result.append(f"{abbrev}: ", style=Style(color=self.theme.muted))
            result.append(str(count), style=Style(color=color, bold=count > 0))

        return result

    def render_compact(self, data: DashboardData, frame: int = 0) -> Text:
        """Render a more compact version.

        Args:
            data: Dashboard data
            frame: Animation frame

        Returns:
            Rich Text with compact badges
        """
        result = Text()
        total = sum(data.threats_by_severity.values())

        if total == 0:
            result.append("No threats detected", style=Style(color=self.theme.ok))
            return result

        for severity in self.SEVERITY_ORDER:
            count = data.threats_by_severity.get(severity, 0)
            if count == 0:
                continue

            color = get_severity_color(severity, self.theme)

            if result.plain:
                result.append(" ", style=Style(color=self.theme.muted))

            result.append("⬤", style=Style(color=color))
            result.append(str(count), style=Style(color=color, bold=True))

        return result
