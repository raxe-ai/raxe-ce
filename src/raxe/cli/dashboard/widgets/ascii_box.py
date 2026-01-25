"""ASCII box-drawing utilities with chroma animation."""

from __future__ import annotations

from typing import ClassVar

from rich.style import Style
from rich.text import Text

from raxe.cli.dashboard.themes import ThemeColors, get_chroma_color


class AsciiBox:
    """Box-drawing utilities with RGB chroma animation.

    Creates borders and boxes using Unicode box-drawing characters
    with optional animated color cycling.
    """

    # Double-line box characters (outer frame)
    DOUBLE: ClassVar[dict[str, str]] = {
        "tl": "╔",
        "tr": "╗",
        "bl": "╚",
        "br": "╝",
        "h": "═",
        "v": "║",
        "lt": "╠",  # Left T
        "rt": "╣",  # Right T
        "tt": "╦",  # Top T
        "bt": "╩",  # Bottom T
        "cross": "╬",
    }

    # Single-line box characters (inner panels)
    SINGLE: ClassVar[dict[str, str]] = {
        "tl": "┌",
        "tr": "┐",
        "bl": "└",
        "br": "┘",
        "h": "─",
        "v": "│",
        "lt": "├",
        "rt": "┤",
        "tt": "┬",
        "bt": "┴",
        "cross": "┼",
    }

    @classmethod
    def horizontal_line(
        cls,
        width: int,
        theme: ThemeColors,
        frame: int = 0,
        animate: bool = True,
        double: bool = True,
    ) -> Text:
        """Create a horizontal line with optional chroma animation.

        Args:
            width: Line width in characters
            theme: Theme for colors
            frame: Animation frame number
            animate: Enable color cycling
            double: Use double-line characters

        Returns:
            Rich Text with colored line
        """
        char = cls.DOUBLE["h"] if double else cls.SINGLE["h"]
        result = Text()

        for i in range(width):
            if animate:
                color = get_chroma_color(frame, i, theme)
            else:
                color = theme.border
            result.append(char, style=Style(color=color))

        return result

    @classmethod
    def vertical_line(
        cls,
        height: int,
        theme: ThemeColors,
        frame: int = 0,
        animate: bool = True,
        double: bool = True,
    ) -> list[Text]:
        """Create vertical line segments with optional chroma animation.

        Args:
            height: Line height in characters
            theme: Theme for colors
            frame: Animation frame number
            animate: Enable color cycling
            double: Use double-line characters

        Returns:
            List of Rich Text, one per row
        """
        char = cls.DOUBLE["v"] if double else cls.SINGLE["v"]
        result = []

        for i in range(height):
            if animate:
                color = get_chroma_color(frame, i, theme)
            else:
                color = theme.border
            result.append(Text(char, style=Style(color=color)))

        return result

    @classmethod
    def frame_top(
        cls,
        width: int,
        theme: ThemeColors,
        frame: int = 0,
        animate: bool = True,
    ) -> Text:
        """Create top frame line with corners.

        Args:
            width: Total width including corners
            theme: Theme for colors
            frame: Animation frame number
            animate: Enable color cycling

        Returns:
            Rich Text with ╔═══...═══╗
        """
        result = Text()

        # Left corner
        color = get_chroma_color(frame, 0, theme) if animate else theme.border
        result.append(cls.DOUBLE["tl"], style=Style(color=color))

        # Middle
        for i in range(width - 2):
            color = get_chroma_color(frame, i + 1, theme) if animate else theme.border
            result.append(cls.DOUBLE["h"], style=Style(color=color))

        # Right corner
        color = get_chroma_color(frame, width - 1, theme) if animate else theme.border
        result.append(cls.DOUBLE["tr"], style=Style(color=color))

        return result

    @classmethod
    def frame_bottom(
        cls,
        width: int,
        theme: ThemeColors,
        frame: int = 0,
        animate: bool = True,
    ) -> Text:
        """Create bottom frame line with corners.

        Args:
            width: Total width including corners
            theme: Theme for colors
            frame: Animation frame number
            animate: Enable color cycling

        Returns:
            Rich Text with ╚═══...═══╝
        """
        result = Text()

        # Left corner
        color = get_chroma_color(frame, 0, theme) if animate else theme.border
        result.append(cls.DOUBLE["bl"], style=Style(color=color))

        # Middle
        for i in range(width - 2):
            color = get_chroma_color(frame, i + 1, theme) if animate else theme.border
            result.append(cls.DOUBLE["h"], style=Style(color=color))

        # Right corner
        color = get_chroma_color(frame, width - 1, theme) if animate else theme.border
        result.append(cls.DOUBLE["br"], style=Style(color=color))

        return result

    @classmethod
    def frame_divider(
        cls,
        width: int,
        theme: ThemeColors,
        frame: int = 0,
        animate: bool = True,
    ) -> Text:
        """Create horizontal divider with T-joints.

        Args:
            width: Total width including joints
            theme: Theme for colors
            frame: Animation frame number
            animate: Enable color cycling

        Returns:
            Rich Text with ╠═══...═══╣
        """
        result = Text()

        # Left T
        color = get_chroma_color(frame, 0, theme) if animate else theme.border
        result.append(cls.DOUBLE["lt"], style=Style(color=color))

        # Middle
        for i in range(width - 2):
            color = get_chroma_color(frame, i + 1, theme) if animate else theme.border
            result.append(cls.DOUBLE["h"], style=Style(color=color))

        # Right T
        color = get_chroma_color(frame, width - 1, theme) if animate else theme.border
        result.append(cls.DOUBLE["rt"], style=Style(color=color))

        return result

    @classmethod
    def frame_left(
        cls,
        theme: ThemeColors,
        frame: int = 0,
        row: int = 0,
        animate: bool = True,
    ) -> Text:
        """Create left frame edge.

        Args:
            theme: Theme for colors
            frame: Animation frame number
            row: Row index for animation offset
            animate: Enable color cycling

        Returns:
            Rich Text with ║
        """
        color = get_chroma_color(frame, row, theme) if animate else theme.border
        return Text(cls.DOUBLE["v"], style=Style(color=color))

    @classmethod
    def frame_right(
        cls,
        theme: ThemeColors,
        frame: int = 0,
        row: int = 0,
        animate: bool = True,
    ) -> Text:
        """Create right frame edge.

        Args:
            theme: Theme for colors
            frame: Animation frame number
            row: Row index for animation offset
            animate: Enable color cycling

        Returns:
            Rich Text with ║
        """
        color = get_chroma_color(frame, row, theme) if animate else theme.border
        return Text(cls.DOUBLE["v"], style=Style(color=color))

    @classmethod
    def inner_box_top(
        cls,
        width: int,
        title: str | None = None,
        theme: ThemeColors | None = None,
    ) -> Text:
        """Create inner panel top border with optional title.

        Args:
            width: Total width
            title: Optional title text
            theme: Theme for colors

        Returns:
            Rich Text with ┌─ TITLE ──...──┐
        """
        result = Text()
        border_color = theme.border if theme else "white"
        title_color = theme.accent if theme else "cyan"

        result.append(cls.SINGLE["tl"], style=Style(color=border_color))

        if title:
            result.append(cls.SINGLE["h"], style=Style(color=border_color))
            result.append(" ", style=Style(color=border_color))
            result.append(title, style=Style(color=title_color, bold=True))
            result.append(" ", style=Style(color=border_color))
            remaining = width - len(title) - 5
            result.append(cls.SINGLE["h"] * remaining, style=Style(color=border_color))
        else:
            result.append(cls.SINGLE["h"] * (width - 2), style=Style(color=border_color))

        result.append(cls.SINGLE["tr"], style=Style(color=border_color))

        return result

    @classmethod
    def inner_box_bottom(
        cls,
        width: int,
        theme: ThemeColors | None = None,
    ) -> Text:
        """Create inner panel bottom border.

        Args:
            width: Total width
            theme: Theme for colors

        Returns:
            Rich Text with └──...──┘
        """
        result = Text()
        border_color = theme.border if theme else "white"

        result.append(cls.SINGLE["bl"], style=Style(color=border_color))
        result.append(cls.SINGLE["h"] * (width - 2), style=Style(color=border_color))
        result.append(cls.SINGLE["br"], style=Style(color=border_color))

        return result
