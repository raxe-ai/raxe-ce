"""CLI branding and visual elements for RAXE.

This module provides:
- ASCII logo (easy to customize)
- Color schemes
- Branded help messages
- Visual separators

CUSTOMIZATION GUIDE:
====================
To change the logo style, edit the LOGO and LOGO_COMPACT constants below.
Each logo is a list of (text, color) tuples.

Available colors: "cyan", "blue", "green", "yellow", "red", "magenta", "dim cyan", "dim white"
Available borders: ╔═╗ ║ ╚═╝ (double) or ┌─┐ │ └─┘ (single) or ╭─╮ │ ╰─╯ (rounded)
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ═══════════════════════════════════════════════════════════════════════════
# COLOR SCHEME CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
COLORS = {
    "primary": "cyan",      # Main brand color (logo top)
    "secondary": "blue",    # Secondary actions (logo bottom)
    "success": "green",     # Safe/success states
    "warning": "yellow",    # Warnings
    "danger": "red",        # Threats/errors
    "muted": "dim white",   # Helper text
    "accent": "magenta",    # Highlights
}

# ═══════════════════════════════════════════════════════════════════════════
# LOGO CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
# Style: 1980s Retro Grid (Tron-inspired)
# To change: Edit the ASCII art below, keeping the (text, color) tuple format

# FULL LOGO - Shown on welcome screen (when running: raxe)
# Format: List of (line_text, color) tuples
# Colors transition from cyan → blue for gradient effect
LOGO = [
    ("╔═══════════════════════════════╗", "cyan"),        # Top border
    ("║                               ║", "cyan"),        # Spacing
    ("║   ██▀▀█ ▄▀▀▄ █▄ ▄█ ██▀▀▀      ║", "cyan"),       # R A X E (line 1)
    ("║   ██▄▄█ █▄▄█  ▄█▄  ██▄▄       ║", "cyan"),       # R A X E (line 2)
    ("║   ██  █ █  █ █▀ ▀█ ██▄▄▄      ║", "blue"),       # R A X E (line 3) - gradient starts
    ("║                               ║", "blue"),        # Spacing
    ("║   AI Security Engine          ║", "dim cyan"),   # Tagline
    ("║                               ║", "cyan"),        # Spacing
    ("╚═══════════════════════════════╝", "cyan"),        # Bottom border
]

# COMPACT LOGO - Shown on command headers (scan, test, stats, etc.)
# Smaller version for minimal space usage
LOGO_COMPACT = [
    ("┌──────────────────────┐", "cyan"),                # Top border
    ("│  █▀▀▄ ▄▀▄ ▀▄▀ █▀▀    │", "cyan"),               # RAXE (compact, line 1)
    ("│  █ ▀█ █▀█ ▄▀▄ █▄▄    │", "blue"),                # RAXE (compact, line 2)
    ("└──────────────────────┘", "blue"),                # Bottom border
]

# Tagline
TAGLINE = "AI Security for LLMs • Privacy-First Threat Detection"
VERSION_TAGLINE = "v1.0.0 • Community Edition"


def print_logo(console: Console, compact: bool = False):
    """Print RAXE logo with cyan→blue gradient.

    Logo is left-aligned for consistent positioning.

    Args:
        console: Rich console instance
        compact: Use compact version for command headers
    """
    logo_lines = LOGO_COMPACT if compact else LOGO

    # Print each line left-aligned
    for line, color in logo_lines:
        console.print(line, style=color)


def print_welcome_banner(console: Console):
    """Print welcome banner for interactive mode."""
    print_logo(console, compact=False)
    console.print()
    console.print(TAGLINE, style="dim cyan")
    console.print(VERSION_TAGLINE, style="dim white")
    console.print()

    # Quick start guide
    help_table = Table.grid(padding=(0, 2))
    help_table.add_column(style="cyan", justify="right")
    help_table.add_column(style="white")

    help_table.add_row("Quick Start:", "")
    help_table.add_row("  raxe scan", "Scan text for threats")
    help_table.add_row("  raxe stats", "View your statistics")
    help_table.add_row("  raxe test", "Test configuration")
    help_table.add_row("  raxe --help", "Show all commands")

    console.print(Panel(
        help_table,
        title="[bold cyan]Getting Started[/bold cyan]",
        border_style="cyan",
        padding=(1, 2)
    ))
    console.print()


def format_command_group(title: str, commands: list[tuple[str, str]]) -> Table:
    """Format a group of commands as a table.

    Args:
        title: Group title
        commands: List of (command, description) tuples

    Returns:
        Rich Table with formatted commands
    """
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", justify="left", width=20)
    table.add_column(style="white")

    for cmd, desc in commands:
        table.add_row(f"  {cmd}", desc)

    return Panel(
        table,
        title=f"[bold cyan]{title}[/bold cyan]",
        border_style="cyan",
        padding=(0, 1),
        width=80  # Fixed width to prevent stretching
    )


def print_help_menu(console: Console):
    """Print enhanced help menu with grouped commands."""
    print_logo(console, compact=False)
    console.print()
    console.print(TAGLINE, style="dim cyan")
    console.print()

    # Core Commands
    core_commands = [
        ("raxe scan <text>", "Scan text for security threats"),
        ("raxe init", "Initialize RAXE configuration"),
        ("raxe test", "Test your configuration"),
        ("raxe stats", "View usage statistics & achievements"),
    ]

    # Analysis Commands
    analysis_commands = [
        ("raxe batch <file>", "Scan multiple prompts from file"),
        ("raxe repl", "Interactive scanning mode"),
        ("raxe export", "Export scan history"),
    ]

    # Configuration Commands
    config_commands = [
        ("raxe rules", "Manage detection rules"),
        ("raxe tune", "Fine-tune detection settings"),
        ("raxe doctor", "Diagnose issues"),
    ]

    # Advanced Commands
    advanced_commands = [
        ("raxe profile", "Performance profiling"),
        ("raxe --verbose", "Enable detailed logging"),
        ("raxe --help", "Show this help message"),
    ]

    # Left-align all panels
    console.print(format_command_group("Core Commands", core_commands))
    console.print()
    console.print(format_command_group("Analysis", analysis_commands))
    console.print()
    console.print(format_command_group("Configuration", config_commands))
    console.print()
    console.print(format_command_group("Advanced", advanced_commands))
    console.print()

    # Footer
    footer = Text()
    footer.append("🐛 Issues: ", style="dim")
    footer.append("github.com/raxe-ai/raxe-ce/issues", style="cyan underline")

    console.print(Panel(
        footer,
        border_style="dim",
        padding=(0, 2),
        width=80  # Fixed width to match other panels
    ))


def print_section_header(console: Console, title: str, icon: str = ""):
    """Print a section header with optional icon.

    Args:
        console: Rich console instance
        title: Section title
        icon: Optional emoji/icon
    """
    header = Text()
    if icon:
        header.append(f"{icon} ", style="bold")
    header.append(title, style="bold cyan")

    console.print()
    console.print(header)
    console.print("─" * 80, style="dim cyan")


def print_success(console: Console, message: str):
    """Print a success message with icon."""
    console.print(f"✓ {message}", style="bold green")


def print_error(console: Console, message: str):
    """Print an error message with icon."""
    console.print(f"✗ {message}", style="bold red")


def print_warning(console: Console, message: str):
    """Print a warning message with icon."""
    console.print(f"⚠ {message}", style="bold yellow")


def print_info(console: Console, message: str):
    """Print an info message with icon."""
    console.print(f"ℹ {message}", style="bold cyan")
