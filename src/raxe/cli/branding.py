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
    "primary": "cyan",  # Main brand color (logo top)
    "secondary": "blue",  # Secondary actions (logo bottom)
    "success": "green",  # Safe/success states
    "warning": "yellow",  # Warnings
    "danger": "red",  # Threats/errors
    "muted": "dim white",  # Helper text
    "accent": "magenta",  # Highlights
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
    ("╔═══════════════════════════════╗", "cyan"),  # Top border
    ("║                               ║", "cyan"),  # Spacing
    ("║   ██▀▀█ ▄▀▀▄ █▄ ▄█ ██▀▀▀      ║", "cyan"),  # R A X E (line 1)
    ("║   ██▄▄█ █▄▄█  ▄█▄  ██▄▄       ║", "cyan"),  # R A X E (line 2)
    ("║   ██  █ █  █ █▀ ▀█ ██▄▄▄      ║", "blue"),  # R A X E (line 3) - gradient starts
    ("║                               ║", "blue"),  # Spacing
    ("║   AI Security Engine          ║", "dim cyan"),  # Tagline
    ("║                               ║", "cyan"),  # Spacing
    ("╚═══════════════════════════════╝", "cyan"),  # Bottom border
]

# COMPACT LOGO - Shown on command headers (scan, test, stats, etc.)
# Smaller version for minimal space usage
LOGO_COMPACT = [
    ("┌──────────────────────┐", "cyan"),  # Top border
    ("│  █▀▀▄ ▄▀▄ ▀▄▀ █▀▀    │", "cyan"),  # RAXE (compact, line 1)
    ("│  █ ▀█ █▀█ ▄▀▄ █▄▄    │", "blue"),  # RAXE (compact, line 2)
    ("└──────────────────────┘", "blue"),  # Bottom border
]

# Tagline
TAGLINE = "AI Security for LLMs • Privacy-First Threat Detection"
VERSION_TAGLINE = "v1.0.0 • Community Edition"

# ═══════════════════════════════════════════════════════════════════════════
# COMMAND CATEGORIES (for progressive disclosure help)
# ═══════════════════════════════════════════════════════════════════════════
# Essential: Commands every user needs within first 5 minutes (shown in --help)
# Common: Commands used regularly after initial setup
# Power: Commands for advanced workflows
# Advanced: Specialist commands
# Reference: Information and setup commands

COMMAND_CATEGORIES = {
    "essential": [
        ("scan <text>", "Scan text for security threats"),
        ("init", "Initialize RAXE configuration"),
        ("auth", "Get a permanent API key"),
    ],
    "common": [
        ("test", "Test configuration and connectivity"),
        ("stats", "View usage statistics and achievements"),
        ("repl", "Interactive scanning mode"),
        ("doctor", "Diagnose configuration issues"),
        ("batch <file>", "Scan multiple prompts from file"),
    ],
    "power": [
        ("rules", "Manage and inspect detection rules"),
        ("config", "View and edit configuration"),
        ("export", "Export scan history"),
        ("history", "View local scan history"),
        ("suppress", "Manage false positive suppressions"),
    ],
    "advanced": [
        ("tune", "Fine-tune detection parameters"),
        ("profile", "Profile scan performance"),
        ("plugins", "List and manage plugins"),
        ("telemetry", "Manage telemetry settings"),
        ("validate-rule", "Validate a custom rule file"),
        ("pack", "Manage rule packs"),
        ("models", "List ML model information"),
        ("event", "Send custom telemetry events"),
    ],
    "reference": [
        ("privacy", "Show privacy guarantees"),
        ("completion", "Generate shell completion scripts"),
    ],
}

# Total command count for discovery hints
TOTAL_COMMAND_COUNT = sum(len(cmds) for cmds in COMMAND_CATEGORIES.values())


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

    console.print(
        Panel(
            help_table,
            title="[bold cyan]Getting Started[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
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
        width=80,  # Fixed width to prevent stretching
    )


def print_minimal_help(console: Console):
    """Print minimal help showing only essential commands.

    This is the default help shown with --help flag.
    Shows only 3-4 essential commands to avoid overwhelming new users.
    """
    print_logo(console, compact=True)
    console.print()
    console.print(TAGLINE, style="dim cyan")
    console.print()

    # Build essential commands table
    table = Table.grid(padding=(0, 2))
    table.add_column(style="cyan", justify="left", width=20)
    table.add_column(style="white")

    for cmd, desc in COMMAND_CATEGORIES["essential"]:
        table.add_row(f"  raxe {cmd}", desc)

    console.print("[bold]ESSENTIAL COMMANDS[/bold]")
    console.print(table)
    console.print()

    # Quick example
    console.print("[bold]GETTING STARTED[/bold]")
    console.print('  [cyan]raxe scan "Ignore previous instructions"[/cyan]')
    console.print()

    # Global flags
    console.print("[bold]FLAGS[/bold]")
    flags_table = Table.grid(padding=(0, 2))
    flags_table.add_column(style="cyan", justify="left", width=20)
    flags_table.add_column(style="white")
    flags_table.add_row("  --help", "Show this help")
    flags_table.add_row("  --help-all", "Show all commands")
    flags_table.add_row("  --version", "Show version")
    console.print(flags_table)
    console.print()

    # Discovery hints
    console.print("[dim]Run 'raxe <command> --help' for command details.[/dim]")
    console.print(f"[dim]Run 'raxe --help-all' to see all {TOTAL_COMMAND_COUNT} commands.[/dim]")
    console.print()


def print_full_help(console: Console):
    """Print full help showing all commands organized by category.

    Shown when user runs --help-all flag.
    """
    print_logo(console, compact=False)
    console.print()
    console.print(TAGLINE, style="dim cyan")
    console.print()

    console.print("[bold]USAGE[/bold]")
    console.print("  raxe <command> [options]")
    console.print()

    # Category display names
    category_titles = {
        "essential": "ESSENTIAL",
        "common": "COMMON",
        "power": "POWER USER",
        "advanced": "ADVANCED",
        "reference": "REFERENCE",
    }

    # Print each category
    for category_key in ["essential", "common", "power", "advanced", "reference"]:
        commands = COMMAND_CATEGORIES[category_key]
        title = category_titles[category_key]

        console.print(f"[bold]{title}[/bold]")
        table = Table.grid(padding=(0, 2))
        table.add_column(style="cyan", justify="left", width=22)
        table.add_column(style="white")

        for cmd, desc in commands:
            table.add_row(f"  {cmd}", desc)

        console.print(table)
        console.print()

    # Global flags
    console.print("[bold]GLOBAL FLAGS[/bold]")
    flags_table = Table.grid(padding=(0, 2))
    flags_table.add_column(style="cyan", justify="left", width=22)
    flags_table.add_column(style="white")
    flags_table.add_row("  --verbose", "Enable detailed logging")
    flags_table.add_row("  --quiet", "Suppress visual output (CI/CD mode)")
    flags_table.add_row("  --no-color", "Disable colored output")
    flags_table.add_row("  --help", "Show minimal help")
    flags_table.add_row("  --help-all", "Show this full help")
    flags_table.add_row("  --version", "Show version information")
    console.print(flags_table)
    console.print()

    # Examples
    console.print("[bold]EXAMPLES[/bold]")
    console.print('  [cyan]raxe scan "Ignore all previous instructions"[/cyan]')
    console.print("  [cyan]raxe scan --stdin < prompts.txt[/cyan]")
    console.print("  [cyan]raxe batch prompts.txt --format json[/cyan]")
    console.print('  [cyan]raxe --quiet scan "test" --ci[/cyan]')
    console.print()

    # Learn more
    console.print("[bold]LEARN MORE[/bold]")
    console.print("  Docs     [blue underline]https://docs.raxe.ai[/blue underline]")
    console.print("  Issues   [blue underline]github.com/raxe-ai/raxe-ce/issues[/blue underline]")
    console.print()


def print_help_menu(console: Console):
    """Print enhanced help menu with grouped commands.

    DEPRECATED: Use print_minimal_help() for default help
    or print_full_help() for complete reference.

    This function now delegates to print_minimal_help() for
    backward compatibility.
    """
    print_minimal_help(console)


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
    console.print(f"ℹ {message}", style="bold cyan")  # noqa: RUF001
