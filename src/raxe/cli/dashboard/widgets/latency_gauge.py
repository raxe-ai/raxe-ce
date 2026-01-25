"""Latency gauge widget - displays performance metrics with visual bars."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text

from raxe.cli.dashboard.data_provider import DashboardData
from raxe.cli.dashboard.themes import ThemeColors, render_gradient_bar


class LatencyGaugeWidget:
    """Displays latency metrics with color-coded progress bars.

    Shows metrics like:
    AVG  4.2ms ████░░░
    P95  8.1ms █████░░
    """

    # Thresholds for color coding (ms)
    GOOD_THRESHOLD = 10.0  # Green below this
    WARN_THRESHOLD = 50.0  # Yellow below this, red above

    def __init__(self, theme: ThemeColors):
        """Initialize the widget.

        Args:
            theme: Theme for colors
        """
        self.theme = theme

    def render(
        self,
        data: DashboardData,
        bar_width: int = 8,
        max_latency: float = 100.0,
    ) -> list[Text]:
        """Render latency metrics.

        Args:
            data: Dashboard data with latency metrics
            bar_width: Width of progress bars
            max_latency: Maximum latency for bar scale

        Returns:
            List of Rich Text lines
        """
        metrics = [
            ("AVG", data.avg_latency_ms),
            ("P95", data.p95_latency_ms),
            ("L1", data.l1_avg_ms),
            ("L2", data.l2_avg_ms),
        ]

        lines = []
        for label, value in metrics:
            line = self._render_metric(label, value, bar_width, max_latency)
            lines.append(line)

        return lines

    def _render_metric(
        self,
        label: str,
        value: float,
        bar_width: int,
        max_latency: float,
    ) -> Text:
        """Render a single metric line.

        Args:
            label: Metric label
            value: Latency value in ms
            bar_width: Width of bar
            max_latency: Maximum for scale

        Returns:
            Rich Text line
        """
        result = Text()

        # Label
        result.append(label.ljust(4), style=Style(color=self.theme.muted))

        # Value
        value_str = f"{value:5.1f}ms"
        value_color = self._get_latency_color(value)
        result.append(value_str, style=Style(color=value_color))
        result.append(" ", style=Style(color=self.theme.muted))

        # Bar
        bar_value = min(1.0, value / max_latency)
        bar = render_gradient_bar(bar_value, bar_width, self.theme)
        result.append_text(bar)

        return result

    def _get_latency_color(self, value: float) -> str:
        """Get color based on latency value.

        Args:
            value: Latency in ms

        Returns:
            Hex color string
        """
        if value < self.GOOD_THRESHOLD:
            return self.theme.ok
        elif value < self.WARN_THRESHOLD:
            return self.theme.warn
        else:
            return self.theme.error

    def render_compact(self, data: DashboardData) -> Text:
        """Render a compact single-line version.

        Args:
            data: Dashboard data

        Returns:
            Rich Text line
        """
        result = Text()

        result.append("Latency: ", style=Style(color=self.theme.muted))

        avg_color = self._get_latency_color(data.avg_latency_ms)
        result.append(f"{data.avg_latency_ms:.1f}ms", style=Style(color=avg_color, bold=True))

        result.append(" (P95: ", style=Style(color=self.theme.muted))

        p95_color = self._get_latency_color(data.p95_latency_ms)
        result.append(f"{data.p95_latency_ms:.1f}ms", style=Style(color=p95_color))

        result.append(")", style=Style(color=self.theme.muted))

        return result
