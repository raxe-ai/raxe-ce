"""CLI commands for managing suppressions.

Commands:
- raxe suppress add <pattern> <reason>
- raxe suppress list
- raxe suppress remove <pattern>
- raxe suppress show <pattern>
- raxe suppress clear
- raxe suppress audit
"""
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from raxe.domain.suppression_factory import create_suppression_manager

console = Console()


@click.group()
def suppress():
    """Manage false positive suppressions."""
    pass


@suppress.command("add")
@click.argument("pattern")
@click.argument("reason", nargs=-1, required=True)
@click.option(
    "--config",
    type=click.Path(),
    help="Path to .raxeignore file (default: ./.raxeignore)",
)
@click.option(
    "--expires",
    help="Expiration date (ISO format: 2025-12-31T23:59:59Z)",
)
@click.option(
    "--save",
    is_flag=True,
    help="Save to .raxeignore file",
)
def add_suppression(pattern: str, reason: tuple[str], config: str | None, expires: str | None, save: bool):
    """Add a suppression rule.

    Examples:
        raxe suppress add pi-001 "False positive in documentation"
        raxe suppress add "pi-*" "Suppress all prompt injection rules"
        raxe suppress add "*-injection" "Too sensitive" --save
        raxe suppress add jb-001 "Temporary fix" --expires 2025-12-31T23:59:59Z
    """
    # Join reason parts
    reason_str = " ".join(reason)

    # Initialize manager
    config_path = Path(config) if config else None
    manager = create_suppression_manager(config_path=config_path)

    try:
        # Add suppression
        suppression = manager.add_suppression(
            pattern=pattern,
            reason=reason_str,
            created_by="cli",
            expires_at=expires,
        )

        # Save to file if requested
        if save:
            manager.save_to_file()
            console.print(f"[green]✓[/green] Added suppression and saved to {manager.config_path}")
        else:
            console.print(f"[green]✓[/green] Added suppression: {pattern}")

        # Show details
        console.print()
        console.print(f"  Pattern: [cyan]{suppression.pattern}[/cyan]")
        console.print(f"  Reason: {suppression.reason}")
        console.print(f"  Created: {suppression.created_at}")
        if suppression.expires_at:
            console.print(f"  Expires: [yellow]{suppression.expires_at}[/yellow]")

        console.print()
        console.print("[dim]Tip: Use --save to persist to .raxeignore file[/dim]")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@suppress.command("list")
@click.option(
    "--config",
    type=click.Path(),
    help="Path to .raxeignore file (default: ./.raxeignore)",
)
@click.option(
    "--format",
    type=click.Choice(["table", "json", "text"]),
    default="table",
    help="Output format (default: table)",
)
def list_suppressions(config: str | None, format: str):
    """List all active suppressions.

    Examples:
        raxe suppress list
        raxe suppress list --format json
    """
    # Initialize manager
    config_path = Path(config) if config else None
    manager = create_suppression_manager(config_path=config_path)

    suppressions = manager.get_suppressions()

    if not suppressions:
        console.print("[yellow]No active suppressions found[/yellow]")
        console.print()
        console.print(f"Add suppressions with: [cyan]raxe suppress add <pattern> <reason>[/cyan]")
        console.print(f"Or create {manager.config_path}")
        return

    if format == "json":
        import json
        output = [
            {
                "pattern": s.pattern,
                "reason": s.reason,
                "created_at": s.created_at,
                "created_by": s.created_by,
                "expires_at": s.expires_at,
            }
            for s in suppressions
        ]
        console.print(json.dumps(output, indent=2))

    elif format == "text":
        for s in suppressions:
            console.print(f"{s.pattern}  # {s.reason}")

    else:  # table
        table = Table(title=f"Active Suppressions ({len(suppressions)})", show_header=True)
        table.add_column("Pattern", style="cyan", no_wrap=True)
        table.add_column("Reason", style="white")
        table.add_column("Created", style="dim", no_wrap=True)
        table.add_column("Expires", style="yellow", no_wrap=True)

        for s in sorted(suppressions, key=lambda x: x.pattern):
            table.add_row(
                s.pattern,
                s.reason[:50] + "..." if len(s.reason) > 50 else s.reason,
                s.created_at[:10],  # Just the date
                s.expires_at[:10] if s.expires_at else "Never",
            )

        console.print(table)
        console.print()
        console.print(f"Total: [bold]{len(suppressions)}[/bold] active suppressions")


@suppress.command("remove")
@click.argument("pattern")
@click.option(
    "--config",
    type=click.Path(),
    help="Path to .raxeignore file (default: ./.raxeignore)",
)
@click.option(
    "--save",
    is_flag=True,
    help="Save changes to .raxeignore file",
)
def remove_suppression(pattern: str, config: str | None, save: bool):
    """Remove a suppression rule.

    Examples:
        raxe suppress remove pi-001
        raxe suppress remove "pi-*" --save
    """
    # Initialize manager
    config_path = Path(config) if config else None
    manager = create_suppression_manager(config_path=config_path)

    # Remove suppression
    removed = manager.remove_suppression(pattern, created_by="cli")

    if not removed:
        console.print(f"[yellow]Suppression not found:[/yellow] {pattern}")
        console.print()
        console.print("Available patterns:")
        for s in manager.get_suppressions():
            console.print(f"  - {s.pattern}")
        sys.exit(1)

    # Save to file if requested
    if save:
        manager.save_to_file()
        console.print(f"[green]✓[/green] Removed suppression and saved to {manager.config_path}")
    else:
        console.print(f"[green]✓[/green] Removed suppression: {pattern}")

    console.print()
    console.print("[dim]Tip: Use --save to persist changes to .raxeignore file[/dim]")


@suppress.command("show")
@click.argument("pattern")
@click.option(
    "--config",
    type=click.Path(),
    help="Path to .raxeignore file (default: ./.raxeignore)",
)
def show_suppression(pattern: str, config: str | None):
    """Show details of a specific suppression.

    Examples:
        raxe suppress show pi-001
        raxe suppress show "pi-*"
    """
    # Initialize manager
    config_path = Path(config) if config else None
    manager = create_suppression_manager(config_path=config_path)

    suppression = manager.get_suppression(pattern)

    if not suppression:
        console.print(f"[yellow]Suppression not found:[/yellow] {pattern}")
        sys.exit(1)

    # Show details
    console.print()
    console.print(f"[bold]Suppression Details[/bold]")
    console.print()
    console.print(f"  Pattern: [cyan]{suppression.pattern}[/cyan]")
    console.print(f"  Reason: {suppression.reason}")
    console.print(f"  Created: {suppression.created_at}")
    console.print(f"  Created by: {suppression.created_by or 'Unknown'}")

    if suppression.expires_at:
        expired = suppression.is_expired()
        status = "[red]EXPIRED[/red]" if expired else "[green]Active[/green]"
        console.print(f"  Expires: {suppression.expires_at} ({status})")
    else:
        console.print(f"  Expires: Never")

    # Show matching examples
    console.print()
    console.print("[bold]Example Matches:[/bold]")
    example_rules = ["pi-001", "pi-002", "jb-regex-basic", "pii-email", "cmd-injection"]
    for rule_id in example_rules:
        if suppression.matches(rule_id):
            console.print(f"  [green]✓[/green] {rule_id}")

    # Get audit log for this pattern
    console.print()
    console.print("[bold]Recent Activity:[/bold]")
    audit_log = manager.get_audit_log(limit=5, pattern=pattern)

    if audit_log:
        for entry in audit_log:
            action = entry["action"]
            timestamp = entry["created_at"][:19]  # Trim microseconds
            console.print(f"  [{timestamp}] {action}")
    else:
        console.print("  [dim]No activity recorded[/dim]")

    console.print()


@suppress.command("clear")
@click.option(
    "--config",
    type=click.Path(),
    help="Path to .raxeignore file (default: ./.raxeignore)",
)
@click.option(
    "--save",
    is_flag=True,
    help="Save changes to .raxeignore file",
)
@click.confirmation_option(
    prompt="Are you sure you want to clear all suppressions?"
)
def clear_suppressions(config: str | None, save: bool):
    """Clear all suppressions.

    Examples:
        raxe suppress clear
        raxe suppress clear --save
    """
    # Initialize manager
    config_path = Path(config) if config else None
    manager = create_suppression_manager(config_path=config_path)

    # Clear all
    count = manager.clear_all(created_by="cli")

    # Save to file if requested
    if save:
        manager.save_to_file()
        console.print(f"[green]✓[/green] Cleared {count} suppressions and saved to {manager.config_path}")
    else:
        console.print(f"[green]✓[/green] Cleared {count} suppressions")


@suppress.command("audit")
@click.option(
    "--config",
    type=click.Path(),
    help="Path to .raxeignore file (default: ./.raxeignore)",
)
@click.option(
    "--limit",
    type=int,
    default=50,
    help="Maximum entries to show (default: 50)",
)
@click.option(
    "--pattern",
    help="Filter by pattern",
)
@click.option(
    "--action",
    type=click.Choice(["added", "removed", "applied"]),
    help="Filter by action type",
)
def audit_log(config: str | None, limit: int, pattern: str | None, action: str | None):
    """Show suppression audit log.

    Examples:
        raxe suppress audit
        raxe suppress audit --limit 100
        raxe suppress audit --pattern "pi-*"
        raxe suppress audit --action applied
    """
    # Initialize manager
    config_path = Path(config) if config else None
    manager = create_suppression_manager(config_path=config_path)

    # Get audit log
    entries = manager.get_audit_log(limit=limit, pattern=pattern, action=action)

    if not entries:
        console.print("[yellow]No audit entries found[/yellow]")
        return

    # Create table
    table = Table(title=f"Suppression Audit Log ({len(entries)} entries)", show_header=True)
    table.add_column("Timestamp", style="dim", no_wrap=True)
    table.add_column("Action", style="cyan", no_wrap=True)
    table.add_column("Pattern", style="yellow")
    table.add_column("Rule ID", style="white")
    table.add_column("Reason", style="white")

    for entry in entries:
        timestamp = entry["created_at"][:19]  # Trim microseconds
        action_str = entry["action"]
        pattern_str = entry["pattern"]
        rule_id = entry.get("rule_id") or "-"
        reason_str = entry["reason"][:40] + "..." if len(entry["reason"]) > 40 else entry["reason"]

        # Color code actions
        if action_str == "added":
            action_color = "[green]"
        elif action_str == "removed":
            action_color = "[red]"
        else:  # applied
            action_color = "[blue]"

        table.add_row(
            timestamp,
            f"{action_color}{action_str}[/{action_color[1:]}",
            pattern_str,
            rule_id,
            reason_str,
        )

    console.print(table)

    # Show statistics
    console.print()
    stats = manager.get_statistics()
    console.print("[bold]Statistics:[/bold]")
    console.print(f"  Active suppressions: {stats['total_active']}")
    console.print(f"  Total added: {stats['total_added']}")
    console.print(f"  Total removed: {stats['total_removed']}")
    console.print(f"  Total applied: {stats['total_applied']}")
    console.print(f"  Applied (last 30 days): {stats['recent_applications_30d']}")
    console.print()


@suppress.command("stats")
@click.option(
    "--config",
    type=click.Path(),
    help="Path to .raxeignore file (default: ./.raxeignore)",
)
def suppression_stats(config: str | None):
    """Show suppression statistics.

    Examples:
        raxe suppress stats
    """
    # Initialize manager
    config_path = Path(config) if config else None
    manager = create_suppression_manager(config_path=config_path)

    stats = manager.get_statistics()

    console.print()
    console.print("[bold cyan]Suppression Statistics[/bold cyan]")
    console.print()

    # Create stats table
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="white")
    table.add_column("Value", style="cyan", justify="right")

    table.add_row("Active Suppressions", str(stats["total_active"]))
    table.add_row("Total Added", str(stats["total_added"]))
    table.add_row("Total Removed", str(stats["total_removed"]))
    table.add_row("Total Applied", str(stats["total_applied"]))
    table.add_row("Applied (30 days)", str(stats["recent_applications_30d"]))

    console.print(table)
    console.print()


# Export the group
__all__ = ["suppress"]
