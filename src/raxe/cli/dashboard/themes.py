"""Dashboard themes - RAXE brand colors and visual styles."""

from __future__ import annotations

from dataclasses import dataclass

from rich.style import Style
from rich.text import Text


@dataclass
class ThemeColors:
    """Color palette for a theme."""

    # Gradient colors (for chroma animation)
    gradient: list[str]

    # Severity colors
    critical: str
    high: str
    medium: str
    low: str
    info: str

    # UI colors
    background: str
    foreground: str
    border: str
    accent: str
    muted: str

    # Status colors
    ok: str
    warn: str
    error: str


# RAXE Brand Theme - Cyan (#1CE3FE) to Magenta (#F002DB)
RAXE_THEME = ThemeColors(
    gradient=[
        "#1CE3FE",  # Cyan (start)
        "#5BC4F7",  # Light blue
        "#8AA5F0",  # Blue-purple
        "#B986E9",  # Purple
        "#D867E2",  # Pink-purple
        "#F002DB",  # Magenta (end)
    ],
    critical="#F002DB",  # Magenta
    high="#D867E2",  # Pink-purple
    medium="#B986E9",  # Purple
    low="#5BC4F7",  # Light blue
    info="#1CE3FE",  # Cyan
    background="#0D0D0D",
    foreground="#FFFFFF",
    border="#5BC4F7",
    accent="#1CE3FE",
    muted="#666666",
    ok="#1CE3FE",  # Cyan
    warn="#B986E9",  # Purple
    error="#F002DB",  # Magenta
)

# Matrix Theme - Classic green
MATRIX_THEME = ThemeColors(
    gradient=[
        "#00FF00",
        "#33FF33",
        "#66FF66",
        "#99FF99",
        "#66FF66",
        "#33FF33",
    ],
    critical="#FF0000",
    high="#FF6600",
    medium="#FFFF00",
    low="#00FF00",
    info="#00FFFF",
    background="#000000",
    foreground="#00FF00",
    border="#00FF00",
    accent="#00FFFF",
    muted="#003300",
    ok="#00FF00",
    warn="#FFFF00",
    error="#FF0000",
)

# Cyber Theme - Cyan and magenta alternate
CYBER_THEME = ThemeColors(
    gradient=[
        "#00FFFF",
        "#FF00FF",
        "#00FFFF",
        "#FF00FF",
        "#00FFFF",
        "#FF00FF",
    ],
    critical="#FF00FF",
    high="#FF0080",
    medium="#8000FF",
    low="#0080FF",
    info="#00FFFF",
    background="#0A0A1A",
    foreground="#FFFFFF",
    border="#00FFFF",
    accent="#FF00FF",
    muted="#404060",
    ok="#00FFFF",
    warn="#FF00FF",
    error="#FF0040",
)

THEMES: dict[str, ThemeColors] = {
    "raxe": RAXE_THEME,
    "matrix": MATRIX_THEME,
    "cyber": CYBER_THEME,
}


def get_theme(name: str) -> ThemeColors:
    """Get a theme by name."""
    return THEMES.get(name, RAXE_THEME)


def get_severity_color(severity: str, theme: ThemeColors) -> str:
    """Get the color for a severity level."""
    severity_map = {
        "CRITICAL": theme.critical,
        "HIGH": theme.high,
        "MEDIUM": theme.medium,
        "LOW": theme.low,
        "INFO": theme.info,
    }
    return severity_map.get(severity.upper(), theme.muted)


def get_severity_style(severity: str, theme: ThemeColors) -> Style:
    """Get a Rich Style for a severity level."""
    color = get_severity_color(severity, theme)
    if severity.upper() == "CRITICAL":
        return Style(color=color, bold=True, blink=True)
    elif severity.upper() == "HIGH":
        return Style(color=color, bold=True)
    return Style(color=color)


def get_chroma_color(frame: int, position: int, theme: ThemeColors) -> str:
    """Get the color for a position in the chroma animation.

    Creates a "chasing" effect where colors move around the border.

    Args:
        frame: Current animation frame
        position: Position along the border (0 to N)
        theme: Theme with gradient colors

    Returns:
        Hex color string
    """
    gradient = theme.gradient
    offset = frame % len(gradient)
    color_index = (position + offset) % len(gradient)
    return gradient[color_index]


def interpolate_gradient(position: float, theme: ThemeColors) -> str:
    """Interpolate a color along the gradient.

    Args:
        position: Position from 0.0 (start) to 1.0 (end)
        theme: Theme with gradient colors

    Returns:
        Hex color string (nearest gradient color)
    """
    gradient = theme.gradient
    index = int(position * (len(gradient) - 1))
    index = max(0, min(index, len(gradient) - 1))
    return gradient[index]


def render_gradient_text(text: str, theme: ThemeColors) -> Text:
    """Render text with gradient coloring (each character a different color).

    Args:
        text: Text to colorize
        theme: Theme with gradient colors

    Returns:
        Rich Text with gradient coloring
    """
    result = Text()
    gradient = theme.gradient
    for i, char in enumerate(text):
        color_index = int((i / max(1, len(text) - 1)) * (len(gradient) - 1))
        color_index = max(0, min(color_index, len(gradient) - 1))
        result.append(char, style=Style(color=gradient[color_index]))
    return result


def render_gradient_bar(
    value: float, width: int, theme: ThemeColors, filled_char: str = "█", empty_char: str = "░"
) -> Text:
    """Render a progress bar with gradient fill.

    Args:
        value: Fill percentage (0.0 to 1.0)
        width: Total bar width in characters
        theme: Theme with gradient colors
        filled_char: Character for filled portion
        empty_char: Character for empty portion

    Returns:
        Rich Text with gradient-colored bar
    """
    filled = int(value * width)
    filled = max(0, min(filled, width))

    bar = Text()
    for i in range(filled):
        color = interpolate_gradient(i / max(1, width - 1), theme)
        bar.append(filled_char, style=Style(color=color))

    if filled < width:
        bar.append(empty_char * (width - filled), style=Style(color=theme.muted))

    return bar


# RAXE ASCII Logo
RAXE_LOGO = """\
██████╗  █████╗ ██╗  ██╗███████╗
██╔══██╗██╔══██╗╚██╗██╔╝██╔════╝
██████╔╝███████║ ╚███╔╝ █████╗
██╔══██╗██╔══██║ ██╔██╗ ██╔══╝
██║  ██║██║  ██║██╔╝ ██╗███████╗
╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝"""

# Smaller logo variant
RAXE_LOGO_SMALL = "▓▓▓ RAXE ▓▓▓"


def render_logo(theme: ThemeColors, small: bool = False) -> Text:
    """Render the RAXE logo with gradient coloring.

    Args:
        theme: Theme with gradient colors
        small: Use smaller logo variant

    Returns:
        Rich Text with gradient-colored logo
    """
    if small:
        return render_gradient_text(RAXE_LOGO_SMALL, theme)

    # For large logo, color by column position
    lines = RAXE_LOGO.split("\n")
    max_width = max(len(line) for line in lines)

    result = Text()
    for i, line in enumerate(lines):
        for j, char in enumerate(line):
            if char != " ":
                color = interpolate_gradient(j / max(1, max_width - 1), theme)
                result.append(char, style=Style(color=color, bold=True))
            else:
                result.append(char)
        if i < len(lines) - 1:
            result.append("\n")

    return result
