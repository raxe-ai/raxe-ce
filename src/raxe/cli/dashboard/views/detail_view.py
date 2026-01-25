"""Detail view - expanded alert details."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.style import Style
from rich.text import Text

from raxe.cli.dashboard.config import DashboardConfig, ViewState
from raxe.cli.dashboard.data_provider import AlertItem
from raxe.cli.dashboard.themes import (
    ThemeColors,
    get_severity_color,
    render_gradient_bar,
)
from raxe.cli.dashboard.views.base_view import BaseView
from raxe.cli.dashboard.widgets.ascii_box import AsciiBox


class DetailView(BaseView):
    """Expanded alert detail view.

    Shows full alert information:
    - Severity with confidence bar
    - Detection info (rule, family, layer, timestamp)
    - Full prompt content
    - Technical details (pattern, score, hash)
    - Action buttons
    """

    def __init__(self, theme: ThemeColors, config: DashboardConfig):
        """Initialize the view."""
        super().__init__(theme, config)

    def render(
        self,
        alert: AlertItem | None,
        state: ViewState,
        terminal_width: int = 80,
    ) -> RenderableType:
        """Render the detail view."""
        frame = state.frame_count
        animate = self.config.enable_animations
        width = self._clamp_width(terminal_width)

        lines: list[Text] = []

        # Top border
        lines.append(AsciiBox.frame_top(width, self.theme, frame, animate))

        # Header
        lines.append(self._render_header(width, frame, animate))

        # Divider
        lines.append(AsciiBox.frame_divider(width, self.theme, frame, animate))

        if alert is None:
            lines.append(self._frame_line(width, frame, animate))
            error_text = Text("Alert not found", style=Style(color=self.theme.error))
            lines.append(
                self._frame_line_with_content(error_text, width, frame, animate, center=True)
            )
            lines.append(self._frame_line(width, frame, animate))
        else:
            # Severity section
            lines.append(self._frame_line(width, frame, animate))
            lines.extend(self._render_severity_section(alert, width, frame, animate))

            # Detection info section
            lines.append(self._frame_line(width, frame, animate))
            lines.extend(self._render_detection_section(alert, width, frame, animate))

            # Prompt content section
            lines.append(self._frame_line(width, frame, animate))
            lines.extend(self._render_prompt_section(alert, width, frame, animate))

            # Technical details section
            lines.append(self._frame_line(width, frame, animate))
            lines.extend(self._render_technical_section(alert, width, frame, animate))

            lines.append(self._frame_line(width, frame, animate))

        # Footer divider
        lines.append(AsciiBox.frame_divider(width, self.theme, frame, animate))

        # Action buttons
        shortcuts = [
            ("S", "Suppress"),
            ("E", "Export"),
            ("C", "Copy Hash"),
            ("↑↓", "Prev/Next Alert"),
        ]
        lines.append(
            self._frame_line_with_content(
                self._render_shortcut_line(shortcuts), width, frame, animate
            )
        )

        # Bottom border
        lines.append(AsciiBox.frame_bottom(width, self.theme, frame, animate))

        return Group(*lines)

    def _render_header(self, width: int, frame: int, animate: bool) -> Text:
        """Render the header line."""
        result = Text()
        result.append_text(AsciiBox.frame_left(self.theme, frame, 0, animate))
        result.append("  ")

        result.append("◀ ", style=Style(color=self.theme.accent))
        result.append("ALERT DETAILS", style=Style(color=self.theme.foreground, bold=True))

        # Right side: back hint
        back_text = "[ESC] Back"
        padding = width - 4 - len("◀ ALERT DETAILS") - len(back_text) - 4
        result.append(" " * padding)
        result.append(back_text, style=Style(color=self.theme.muted))

        result.append("  ")
        result.append_text(AsciiBox.frame_right(self.theme, frame, 0, animate))
        return result

    def _render_severity_section(
        self, alert: AlertItem, width: int, frame: int, animate: bool
    ) -> list[Text]:
        """Render the severity section."""
        lines = []

        lines.append(self._inner_panel_top(" SEVERITY ", width - 4, frame))

        sev_line = Text()
        sev_color = get_severity_color(alert.severity, self.theme)

        sev_line.append("    ", style=Style(color=self.theme.background))
        sev_line.append("⬤ ", style=Style(color=sev_color, bold=True))
        sev_line.append(alert.severity, style=Style(color=sev_color, bold=True))
        sev_line.append("   ", style=Style(color=self.theme.background))

        # Confidence bar
        bar = render_gradient_bar(alert.confidence, 20, self.theme)
        sev_line.append_text(bar)
        sev_line.append("  ", style=Style(color=self.theme.background))
        conf_pct = f"{alert.confidence * 100:.1f}% confidence"
        sev_line.append(conf_pct, style=Style(color=self.theme.muted))

        lines.append(self._inner_panel_content(sev_line, width, frame, animate))
        lines.append(self._inner_panel_bottom(width - 4, frame))

        return lines

    def _render_detection_section(
        self, alert: AlertItem, width: int, frame: int, animate: bool
    ) -> list[Text]:
        """Render detection info section."""
        lines = []

        lines.append(self._inner_panel_top(" DETECTION INFO ", width - 4, frame))

        # Rule ID(s)
        if len(alert.rule_ids) > 1:
            rule_str = ", ".join(alert.rule_ids[:4])
            if len(alert.rule_ids) > 4:
                rule_str += f" (+{len(alert.rule_ids) - 4} more)"
            lines.append(
                self._render_info_line("Rules:", rule_str, width, frame, animate, highlight=True)
            )
        else:
            rule_id = alert.rule_ids[0] if alert.rule_ids else "N/A"
            lines.append(
                self._render_info_line("Rule ID:", rule_id, width, frame, animate, highlight=True)
            )

        # Rule description (full width - 20 for labels and padding)
        if alert.descriptions:
            max_desc_width = width - 24
            rule_name = alert.descriptions[0][:max_desc_width]
            lines.append(self._render_info_line("Rule Name:", rule_name, width, frame, animate))

        # Detection counts
        lines.append(
            self._render_info_line(
                "Detections:", f"{alert.detection_count} total", width, frame, animate
            )
        )

        # Layer breakdown
        layer_parts = []
        if alert.l1_detections > 0:
            layer_parts.append(f"L1: {alert.l1_detections}")
        if alert.l2_detections > 0:
            layer_parts.append(f"L2: {alert.l2_detections}")
        layer_str = " │ ".join(layer_parts) if layer_parts else "Unknown"
        lines.append(self._render_info_line("Layer:", layer_str, width, frame, animate))

        # Timestamp
        ts_str = alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        lines.append(self._render_info_line("Timestamp:", ts_str, width, frame, animate))

        # Scan ID
        lines.append(self._render_info_line("Scan ID:", f"#{alert.scan_id}", width, frame, animate))

        lines.append(self._inner_panel_bottom(width - 4, frame))
        return lines

    def _render_prompt_section(
        self, alert: AlertItem, width: int, frame: int, animate: bool
    ) -> list[Text]:
        """Render prompt content section."""
        lines = []

        lines.append(self._inner_panel_top(" PROMPT CONTENT ", width - 4, frame))

        prompt_text = alert.prompt_text or alert.prompt_preview
        if not prompt_text or prompt_text == "[No preview]":
            prompt_text = "(Prompt content not available)"

        max_width = width - 10
        wrapped_lines = self._wrap_text(prompt_text, max_width)

        for wrapped in wrapped_lines[:8]:
            prompt_line = Text()
            prompt_line.append("  ", style=Style(color=self.theme.background))
            prompt_line.append('"', style=Style(color=self.theme.muted))
            prompt_line.append(wrapped, style=Style(color=self.theme.foreground))
            prompt_line.append('"', style=Style(color=self.theme.muted))
            lines.append(self._inner_panel_content(prompt_line, width, frame, animate))

        if len(wrapped_lines) > 8:
            more_line = Text()
            more_text = f"  ... ({len(wrapped_lines) - 8} more lines)"
            more_line.append(more_text, style=Style(color=self.theme.muted, italic=True))
            lines.append(self._inner_panel_content(more_line, width, frame, animate))

        lines.append(self._inner_panel_bottom(width - 4, frame))
        return lines

    def _render_technical_section(
        self, alert: AlertItem, width: int, frame: int, animate: bool
    ) -> list[Text]:
        """Render technical details section."""
        lines = []

        lines.append(self._inner_panel_top(" TECHNICAL DETAILS ", width - 4, frame))

        # Confidence score with visual indicator
        conf_pct = alert.confidence * 100
        conf_level = "HIGH" if conf_pct >= 80 else "MEDIUM" if conf_pct >= 50 else "LOW"
        conf_str = f"{alert.confidence:.3f} ({conf_pct:.1f}% - {conf_level})"
        lines.append(self._render_info_line("Confidence:", conf_str, width, frame, animate))

        # L2 Score (if L2 was triggered)
        if alert.l2_detections > 0:
            l2_str = "Score > threshold (L2 triggered)"
            lines.append(self._render_info_line("L2 Analysis:", l2_str, width, frame, animate))

        # Prompt hash (show more of it)
        hash_display = f"sha256:{alert.prompt_hash[:24]}..."
        lines.append(self._render_info_line("Hash:", hash_display, width, frame, animate))

        # Event ID
        if alert.event_id:
            lines.append(self._render_info_line("Event ID:", alert.event_id, width, frame, animate))

        lines.append(self._inner_panel_bottom(width - 4, frame))
        return lines

    def _render_info_line(
        self, label: str, value: str, width: int, frame: int, animate: bool, highlight: bool = False
    ) -> Text:
        """Render a labeled info line."""
        line = Text()
        line.append(f"  {label.ljust(14)}", style=Style(color=self.theme.muted))
        value_color = self.theme.accent if highlight else self.theme.foreground
        line.append(value, style=Style(color=value_color))
        return self._inner_panel_content(line, width, frame, animate)

    def _wrap_text(self, text: str, max_width: int) -> list[str]:
        """Wrap text to fit width."""
        words = text.split()
        lines = []
        current_line: list[str] = []
        current_width = 0

        for word in words:
            if current_width + len(word) + 1 <= max_width:
                current_line.append(word)
                current_width += len(word) + 1
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_width = len(word)

        if current_line:
            lines.append(" ".join(current_line))

        return lines or [""]
