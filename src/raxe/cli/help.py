"""RAXE help command for error codes and command reference.

Provides detailed help for error codes with:
- Description and common causes
- Remediation steps and examples
- Related error codes
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import click
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from raxe.cli.output import console
from raxe.domain.errors.error_catalog import (
    get_error_info,
    list_by_category,
    list_error_codes,
)

if TYPE_CHECKING:
    pass


def is_error_code(arg: str) -> bool:
    """Check if argument looks like an error code.

    Error codes match pattern: {CATEGORY}-{NUMBER}
    where CATEGORY is uppercase letters and NUMBER is 3 digits.
    """
    return bool(re.match(r"^[A-Za-z]+-\d{3}$", arg))


def display_error_help(code: str) -> None:
    """Display detailed help for an error code."""
    info = get_error_info(code)

    if not info:
        suggestions = _find_similar_codes(code)
        console.print(f"[red]Error code not found: {code}[/red]")
        if suggestions:
            console.print(f"[yellow]Did you mean: {', '.join(suggestions)}?[/yellow]")
        console.print()
        console.print("Use [cyan]raxe help --list[/cyan] to see all error codes")
        return

    # Header
    header = Text()
    header.append(f"[{info.code}] ", style="bold red")
    header.append(info.title, style="bold white")

    console.print(Panel(header, border_style="red", padding=(0, 1)))
    console.print()

    # Description
    console.print("[bold]Description[/bold]")
    console.print(f"  {info.description}")
    console.print()

    # Causes
    if info.causes:
        console.print("[bold]Common Causes[/bold]")
        for cause in info.causes:
            console.print(f"  [dim]>[/dim] {cause}")
        console.print()

    # Primary fix
    if info.remediation:
        console.print("[bold yellow]Fix[/bold yellow]")
        console.print(f"  [cyan]{info.remediation}[/cyan]")
        console.print()

    # Additional steps
    if info.additional_steps:
        console.print("[bold]Additional Steps[/bold]")
        for i, step in enumerate(info.additional_steps, 1):
            console.print(f"  {i}. {step}")
        console.print()

    # Examples
    if info.examples:
        console.print("[bold]Examples[/bold]")
        for example in info.examples:
            console.print(f"  [dim]$[/dim] [cyan]{example}[/cyan]")
        console.print()

    # See also
    if info.see_also:
        console.print("[bold]See Also[/bold]")
        console.print(f"  Related errors: {', '.join(info.see_also)}")
        console.print()

    # Documentation link
    console.print(f"[blue]Documentation:[/blue] [blue underline]{info.doc_url}[/blue underline]")
    console.print()


def display_category_errors(category: str) -> None:
    """Display all errors in a category."""
    errors = list_by_category(category)

    if not errors:
        console.print(f"[red]Unknown category: {category}[/red]")
        console.print("Valid categories: CFG, RULE, SEC, DB, VAL, INFRA")
        return

    table = Table(
        title=f"[bold]{category} Errors[/bold]",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Code", style="red", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Fix", style="cyan", max_width=40)

    for info in sorted(errors, key=lambda e: e.code):
        fix = info.remediation[:37] + "..." if len(info.remediation) > 40 else info.remediation
        table.add_row(info.code, info.title, fix)

    console.print(table)


def display_all_errors() -> None:
    """Display overview of all error codes."""
    categories = {
        "CFG": ("001-099", "Configuration errors"),
        "RULE": ("100-199", "Rule errors"),
        "SEC": ("200-299", "Security errors"),
        "DB": ("300-399", "Database errors"),
        "VAL": ("400-499", "Validation errors"),
        "INFRA": ("500-599", "Infrastructure errors"),
    }

    table = Table(
        title="[bold]RAXE Error Code Categories[/bold]",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Category", style="red", no_wrap=True)
    table.add_column("Range", style="yellow", no_wrap=True)
    table.add_column("Count", justify="right", no_wrap=True)
    table.add_column("Description", style="white")

    for cat, (range_str, desc) in categories.items():
        count = len(list_by_category(cat))
        table.add_row(cat, range_str, str(count), desc)

    console.print(table)
    console.print()
    console.print("[dim]Usage:[/dim]")
    console.print("  [cyan]raxe help CFG-001[/cyan]        Show help for specific error")
    console.print("  [cyan]raxe help --category CFG[/cyan]  List all CFG errors")
    console.print("  [cyan]raxe help --list[/cyan]         List all error codes")


def display_help_topics() -> None:
    """Display main help topics overview."""
    from raxe.cli.branding import print_logo

    print_logo(console, compact=True)
    console.print()

    table = Table(
        title="[bold cyan]Help Topics[/bold cyan]",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Topic", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")

    topics = [
        ("raxe help scan", "Scanning text for security threats"),
        ("raxe help config", "Configuration management"),
        ("raxe help rules", "Detection rule management"),
        ("raxe help auth", "Authentication and API keys"),
        ("raxe help CFG-001", "Help for specific error code"),
        ("raxe help --list", "List all error codes"),
    ]

    for topic, desc in topics:
        table.add_row(topic, desc)

    console.print(table)
    console.print()
    console.print("[blue]Full documentation:[/blue] https://docs.raxe.ai")


def _find_similar_codes(code: str) -> list[str]:
    """Find error codes similar to the given input."""
    code_upper = code.upper()
    all_codes = list_error_codes()

    if "-" in code_upper:
        category = code_upper.split("-")[0]
        return [c for c in all_codes if c.startswith(category)][:5]

    return [c for c in all_codes if c.startswith(code_upper.split("-")[0])][:5]


@click.command("help")
@click.argument("topic", required=False)
@click.option(
    "--category",
    "-c",
    help="Show errors in category (CFG, RULE, SEC, DB, VAL, INFRA)",
)
@click.option(
    "--list",
    "list_all",
    is_flag=True,
    help="List all error codes",
)
@click.pass_context
def help_command(
    ctx: click.Context, topic: str | None, category: str | None, list_all: bool
) -> None:
    """Show help for error codes and commands.

    \b
    Examples:
      raxe help CFG-001           Show help for error code
      raxe help scan              Show help for scan command
      raxe help --category CFG    List all configuration errors
      raxe help --list            List all error codes
      raxe help                   Show help topics overview

    \b
    Error Code Categories:
      CFG     Configuration errors (001-099)
      RULE    Rule errors (100-199)
      SEC     Security errors (200-299)
      DB      Database errors (300-399)
      VAL     Validation errors (400-499)
      INFRA   Infrastructure errors (500-599)
    """
    # Handle --list flag
    if list_all:
        display_all_errors()
        return

    # Handle --category flag
    if category:
        if category.lower() == "all":
            display_all_errors()
        else:
            display_category_errors(category.upper())
        return

    # Handle topic argument
    if topic:
        # Check if it's an error code
        if is_error_code(topic):
            display_error_help(topic.upper())
            return

        # Try to delegate to command's --help
        root = ctx.find_root()
        if root and hasattr(root, "command") and hasattr(root.command, "commands"):
            cli = root.command
            if topic in cli.commands:
                cmd = cli.commands[topic]
                with ctx.scope() as scoped:
                    click.echo(cmd.get_help(scoped))
                return

        # Not found
        console.print(f"[red]Unknown topic: {topic}[/red]")
        console.print()
        console.print("Use [cyan]raxe help[/cyan] to see available topics")
        console.print("Use [cyan]raxe help --list[/cyan] to see error codes")
        return

    # No arguments - show overview
    display_help_topics()
