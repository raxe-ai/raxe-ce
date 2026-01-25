"""Base view class with shared framing utilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from rich.console import RenderableType
from rich.style import Style
from rich.text import Text

from raxe.cli.dashboard.config import DashboardConfig, ViewState
from raxe.cli.dashboard.themes import ThemeColors
from raxe.cli.dashboard.widgets.ascii_box import AsciiBox


class BaseView(ABC):
    """Base class for dashboard views with shared framing utilities.

    Provides common layout methods to eliminate duplication between
    CompactView and DetailView.
    """

    # Layout constants
    MIN_WIDTH = 70
    MAX_WIDTH = 120

    def __init__(self, theme: ThemeColors, config: DashboardConfig):
        """Initialize the view.

        Args:
            theme: Theme for colors
            config: Dashboard configuration
        """
        self.theme = theme
        self.config = config

    @abstractmethod
    def render(self, data: Any, state: ViewState, terminal_width: int = 80) -> RenderableType:
        """Render the view. Must be implemented by subclasses."""
        ...

    def _clamp_width(self, terminal_width: int) -> int:
        """Clamp terminal width to reasonable bounds."""
        return max(self.MIN_WIDTH, min(terminal_width, self.MAX_WIDTH))

    def _frame_line(self, width: int, frame: int, animate: bool) -> Text:
        """Create a framed line with empty content.

        Args:
            width: Total width
            frame: Animation frame
            animate: Enable animation

        Returns:
            Rich Text with frame borders and empty content
        """
        result = Text()
        result.append_text(AsciiBox.frame_left(self.theme, frame, 0, animate))
        result.append(" " * (width - 2), style=Style(color=self.theme.background))
        result.append_text(AsciiBox.frame_right(self.theme, frame, 0, animate))
        return result

    def _frame_line_with_content(
        self,
        content: Text,
        width: int,
        frame: int,
        animate: bool,
        center: bool = False,
        padding: int = 1,
    ) -> Text:
        """Create a framed line with content.

        Args:
            content: Text content
            width: Total width
            frame: Animation frame
            animate: Enable animation
            center: Center the content
            padding: Padding on each side (default 1)

        Returns:
            Rich Text with frame and content
        """
        result = Text()
        result.append_text(AsciiBox.frame_left(self.theme, frame, 0, animate))
        result.append(" " * padding)

        content_width = len(content.plain)
        available = width - 2 - (padding * 2)  # Frame chars + padding

        if center and content_width < available:
            left_pad = (available - content_width) // 2
            result.append(" " * left_pad)
            result.append_text(content)
            right_pad = available - content_width - left_pad
            result.append(" " * right_pad)
        else:
            result.append_text(content)
            if content_width < available:
                result.append(" " * (available - content_width))

        result.append(" " * padding)
        result.append_text(AsciiBox.frame_right(self.theme, frame, 0, animate))
        return result

    def _inner_panel_top(self, title: str, width: int, frame: int) -> Text:
        """Render inner panel top border with title.

        Args:
            title: Panel title
            width: Inner panel width
            frame: Animation frame

        Returns:
            Rich Text with framed inner panel top
        """
        result = Text()
        animate = self.config.enable_animations
        result.append_text(AsciiBox.frame_left(self.theme, frame, 0, animate))
        result.append(" ")
        result.append_text(AsciiBox.inner_box_top(width, title, self.theme))
        result.append(" ")
        result.append_text(AsciiBox.frame_right(self.theme, frame, 0, animate))
        return result

    def _inner_panel_bottom(self, width: int, frame: int) -> Text:
        """Render inner panel bottom border.

        Args:
            width: Inner panel width
            frame: Animation frame

        Returns:
            Rich Text with framed inner panel bottom
        """
        result = Text()
        animate = self.config.enable_animations
        result.append_text(AsciiBox.frame_left(self.theme, frame, 0, animate))
        result.append(" ")
        result.append_text(AsciiBox.inner_box_bottom(width, self.theme))
        result.append(" ")
        result.append_text(AsciiBox.frame_right(self.theme, frame, 0, animate))
        return result

    def _inner_panel_content(self, content: Text, width: int, frame: int, animate: bool) -> Text:
        """Render inner panel content line with borders.

        Args:
            content: Content text
            width: Total width
            frame: Animation frame
            animate: Enable animation

        Returns:
            Rich Text with framed content
        """
        result = Text()
        result.append_text(AsciiBox.frame_left(self.theme, frame, 0, animate))
        result.append("  │ ", style=Style(color=self.theme.border))
        result.append_text(content)

        content_width = len(content.plain)
        padding = width - 10 - content_width
        if padding > 0:
            result.append(" " * padding)

        result.append(" │  ", style=Style(color=self.theme.border))
        result.append_text(AsciiBox.frame_right(self.theme, frame, 0, animate))
        return result

    def _pad_inner(self, content: Text, width: int) -> Text:
        """Pad content to fit inner panel width with side borders.

        Args:
            content: Content text
            width: Inner panel width

        Returns:
            Rich Text with inner borders
        """
        result = Text()
        result.append("│ ", style=Style(color=self.theme.border))
        result.append_text(content)
        padding = width - len(content.plain) - 4
        if padding > 0:
            result.append(" " * padding)
        result.append(" │", style=Style(color=self.theme.border))
        return result

    def _render_shortcut_line(self, shortcuts: list[tuple[str, str]]) -> Text:
        """Render a line of keyboard shortcuts.

        Args:
            shortcuts: List of (key, action) tuples

        Returns:
            Rich Text with formatted shortcuts
        """
        result = Text()
        for i, (key, action) in enumerate(shortcuts):
            if i > 0:
                result.append("  ", style=Style(color=self.theme.muted))
            result.append(f"[{key}]", style=Style(color=self.theme.accent))
            result.append(f" {action}", style=Style(color=self.theme.muted))
        return result
