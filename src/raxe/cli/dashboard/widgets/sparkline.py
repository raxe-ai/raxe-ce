"""Sparkline widget - trend visualization with gradient colors."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text

from raxe.cli.dashboard.themes import ThemeColors, interpolate_gradient


class SparklineWidget:
    """Renders trend sparklines with gradient coloring.

    Uses Unicode block characters for height visualization:
    ▁▂▃▄▅▆▇█
    """

    # Block characters ordered by height (space = 0, █ = max)
    BLOCKS = " ▁▂▃▄▅▆▇█"

    def __init__(self, theme: ThemeColors):
        """Initialize the widget.

        Args:
            theme: Theme for colors
        """
        self.theme = theme

    def render(
        self,
        values: list[int],
        width: int = 24,
        label: str | None = None,
        total: int | None = None,
        use_gradient: bool = True,
        highlight_nonzero: bool = False,
    ) -> Text:
        """Render a sparkline.

        Args:
            values: Data values (one per unit of time)
            width: Sparkline width in characters
            label: Optional label to prepend
            total: Optional total to append
            use_gradient: Use gradient coloring
            highlight_nonzero: Use different color for nonzero values

        Returns:
            Rich Text with sparkline
        """
        result = Text()

        # Add label if provided
        if label:
            result.append(label.ljust(10), style=Style(color=self.theme.muted))

        # Generate sparkline
        sparkline = self._generate_sparkline(values, width)

        for i, char in enumerate(sparkline):
            if use_gradient:
                color = interpolate_gradient(i / max(1, len(sparkline) - 1), self.theme)
            elif highlight_nonzero and char != " " and char != self.BLOCKS[0]:
                color = self.theme.error  # Highlight threats in error color
            else:
                color = self.theme.accent

            result.append(char, style=Style(color=color))

        # Add total if provided
        if total is not None:
            result.append(" ", style=Style(color=self.theme.muted))
            result.append(str(total).rjust(4), style=Style(color=self.theme.foreground))

        return result

    def _generate_sparkline(self, values: list[int], width: int) -> str:
        """Generate sparkline string from values.

        Args:
            values: Data values
            width: Target width

        Returns:
            String of block characters
        """
        if not values:
            return " " * width

        # Pad or truncate to width
        if len(values) < width:
            # Pad with zeros on the left (oldest data)
            values = [0] * (width - len(values)) + values
        elif len(values) > width:
            # Take most recent values
            values = values[-width:]

        # Normalize values to block indices
        max_val = max(values) if max(values) > 0 else 1
        max_block_idx = len(self.BLOCKS) - 1

        result = []
        for v in values:
            if v == 0:
                result.append(" ")
            else:
                # Map value to block character
                idx = int((v / max_val) * max_block_idx)
                idx = max(1, min(idx, max_block_idx))  # At least ▁ for nonzero
                result.append(self.BLOCKS[idx])

        return "".join(result)

    def render_dual(
        self,
        scans: list[int],
        threats: list[int],
        width: int = 20,
    ) -> list[Text]:
        """Render dual sparklines for scans and threats.

        Args:
            scans: Scan counts per time unit
            threats: Threat counts per time unit
            width: Sparkline width

        Returns:
            List of two Text lines
        """
        scan_total = sum(scans)
        threat_total = sum(threats)

        scan_line = self.render(
            scans,
            width=width,
            label="Scans",
            total=scan_total,
            use_gradient=True,
        )

        threat_line = self.render(
            threats,
            width=width,
            label="Alerts",
            total=threat_total,
            use_gradient=False,
            highlight_nonzero=True,
        )

        return [scan_line, threat_line]
