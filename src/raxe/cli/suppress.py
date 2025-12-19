"""CLI commands for managing suppressions.

Commands:
- raxe suppress add <pattern> --reason <reason>
- raxe suppress list
- raxe suppress remove <pattern>
- raxe suppress show <pattern>
- raxe suppress clear
- raxe suppress audit [--limit N]
"""
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from raxe.domain.suppression import SuppressionAction, SuppressionValidationError
from raxe.domain.suppression_factory import (
    create_suppression_manager,
    create_suppression_manager_with_yaml,
)

console = Console()


# Valid pattern examples for error messages
PATTERN_EXAMPLES = """
Valid pattern examples:
  pi-001         - Suppress specific rule
  pi-*           - Suppress all prompt injection rules
  jb-*           - Suppress all jailbreak rules
  pi-00*         - Suppress rules pi-001, pi-002, etc.
"""


@click.group()
def suppress():
    """Manage false positive suppressions."""
    pass


@suppress.command("add")
@click.argument("pattern")
@click.option(
    "--reason", "-r",
    required=True,
    help="Reason for suppression (required for audit trail)",
)
@click.option(
    "--action", "-a",
    type=click.Choice(["SUPPRESS", "FLAG", "LOG"], case_sensitive=False),
    default="SUPPRESS",
    help="Action to take when matched (default: SUPPRESS)",
)
@click.option(
    "--config",
    type=click.Path(),
    help="Path to suppressions.yaml (default: ./.raxe/suppressions.yaml)",
)
@click.option(
    "--expires",
    help="Expiration date (ISO format: 2025-12-31 or 2025-12-31T23:59:59Z)",
)
def add_suppression(
    pattern: str,
    reason: str,
    action: str,
    config: str | None,
    expires: str | None,
):
    """Add a suppression rule to configuration.

    Creates or updates .raxe/suppressions.yaml with the new suppression.
    The config file is automatically created if it doesn't exist.

    \b
    Examples:
        raxe suppress add pi-001 --reason "Known false positive"
        raxe suppress add "pi-*" --reason "Suppress all PI rules" --action FLAG
        raxe suppress add jb-001 --reason "Temp fix" --expires 2025-12-31

    \b
    Actions:
        SUPPRESS  Remove detection from results entirely (default)
        FLAG      Keep detection but mark for review
        LOG       Keep detection for logging/metrics only
    """
    # Initialize manager with YAML format (creates config dir if needed)
    config_path = Path(config) if config else None
    manager = create_suppression_manager_with_yaml(yaml_path=config_path)

    try:
        # Parse action
        suppression_action = SuppressionAction(action.upper())

        # Add suppression
        suppression = manager.add_suppression(
            pattern=pattern,
            reason=reason,
            action=suppression_action,
            created_by="cli",
            expires_at=expires,
        )

        # Always save to file (YAML format auto-saves)
        manager.save_to_file()

        console.print(f"[green]✓[/green] Added suppression and saved to {manager.config_path}")

        # Show details
        console.print()
        console.print(f"  Pattern: [cyan]{suppression.pattern}[/cyan]")
        console.print(f"  Reason: {suppression.reason}")
        console.print(f"  Action: [yellow]{suppression.action.value}[/yellow]")
        console.print(f"  Created: {suppression.created_at[:10]}")
        if suppression.expires_at:
            console.print(f"  Expires: [yellow]{suppression.expires_at[:10]}[/yellow]")
        console.print()

    except SuppressionValidationError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print(PATTERN_EXAMPLES)
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@suppress.command("list")
@click.option(
    "--config",
    type=click.Path(),
    help="Path to suppressions.yaml (default: ./.raxe/suppressions.yaml)",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["table", "json", "text"]),
    default="table",
    help="Output format (default: table)",
)
def list_suppressions(config: str | None, output_format: str):
    """List all active suppressions from config.

    \b
    Examples:
        raxe suppress list
        raxe suppress list --format json
    """
    # Initialize manager with YAML format
    config_path = Path(config) if config else None
    manager = create_suppression_manager_with_yaml(yaml_path=config_path)

    suppressions = manager.get_suppressions()

    if not suppressions:
        console.print("[yellow]No active suppressions found[/yellow]")
        console.print()
        console.print(
            "Add suppressions with: [cyan]raxe suppress add <pattern> --reason \"...\"[/cyan]"
        )
        console.print(f"Or create {manager.config_path}")
        return

    if output_format == "json":
        import json
        output = [
            {
                "pattern": s.pattern,
                "reason": s.reason,
                "action": s.action.value,
                "created_at": s.created_at,
                "created_by": s.created_by,
                "expires_at": s.expires_at,
            }
            for s in suppressions
        ]
        console.print(json.dumps(output, indent=2))

    elif output_format == "text":
        for s in suppressions:
            action_suffix = f" [{s.action.value}]" if s.action != SuppressionAction.SUPPRESS else ""
            console.print(f"{s.pattern}{action_suffix}  # {s.reason}")

    else:  # table
        table = Table(title=f"Active Suppressions ({len(suppressions)})", show_header=True)
        table.add_column("Pattern", style="cyan", no_wrap=True)
        table.add_column("Action", style="yellow", no_wrap=True)
        table.add_column("Reason", style="white")
        table.add_column("Expires", style="dim", no_wrap=True)

        for s in sorted(suppressions, key=lambda x: x.pattern):
            # Color code actions
            action_color = {
                SuppressionAction.SUPPRESS: "green",
                SuppressionAction.FLAG: "yellow",
                SuppressionAction.LOG: "blue",
            }.get(s.action, "white")

            table.add_row(
                s.pattern,
                f"[{action_color}]{s.action.value}[/{action_color}]",
                s.reason[:40] + "..." if len(s.reason) > 40 else s.reason,
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
    help="Path to suppressions.yaml (default: ./.raxe/suppressions.yaml)",
)
def remove_suppression(pattern: str, config: str | None):
    """Remove a suppression rule from config.

    \b
    Examples:
        raxe suppress remove pi-001
        raxe suppress remove "pi-*"
    """
    # Initialize manager with YAML format
    config_path = Path(config) if config else None
    manager = create_suppression_manager_with_yaml(yaml_path=config_path)

    # Remove suppression
    removed = manager.remove_suppression(pattern, created_by="cli")

    if not removed:
        console.print(f"[yellow]Warning: Suppression not found:[/yellow] {pattern}")
        console.print()

        # Show available patterns
        suppressions = manager.get_suppressions()
        if suppressions:
            console.print("Available patterns:")
            for s in suppressions:
                console.print(f"  - {s.pattern}")
        else:
            console.print("No active suppressions configured.")
        return  # Warning, not error - pattern might have been already removed

    # Always save to file
    manager.save_to_file()
    console.print(f"[green]✓[/green] Removed suppression: {pattern}")
    console.print(f"  Saved to: {manager.config_path}")
    console.print()


@suppress.command("show")
@click.argument("pattern")
@click.option(
    "--config",
    type=click.Path(),
    help="Path to suppressions.yaml (default: ./.raxe/suppressions.yaml)",
)
def show_suppression(pattern: str, config: str | None):
    """Show details of a specific suppression.

    \b
    Examples:
        raxe suppress show pi-001
        raxe suppress show "pi-*"
    """
    # Initialize manager with YAML format
    config_path = Path(config) if config else None
    manager = create_suppression_manager_with_yaml(yaml_path=config_path)

    suppression = manager.get_suppression(pattern)

    if not suppression:
        console.print(f"[yellow]Suppression not found:[/yellow] {pattern}")
        sys.exit(1)

    # Show details
    console.print()
    console.print("[bold]Suppression Details[/bold]")
    console.print()
    console.print(f"  Pattern: [cyan]{suppression.pattern}[/cyan]")
    console.print(f"  Reason: {suppression.reason}")
    console.print(f"  Action: [yellow]{suppression.action.value}[/yellow]")
    created_date = suppression.created_at[:10] if suppression.created_at else "Unknown"
    console.print(f"  Created: {created_date}")
    console.print(f"  Created by: {suppression.created_by or 'Unknown'}")

    if suppression.expires_at:
        expired = suppression.is_expired()
        status = "[red]EXPIRED[/red]" if expired else "[green]Active[/green]"
        console.print(f"  Expires: {suppression.expires_at[:10]} ({status})")
    else:
        console.print("  Expires: Never")

    # Show matching examples
    console.print()
    console.print("[bold]Example Matches:[/bold]")
    example_rules = ["pi-001", "pi-002", "jb-regex-basic", "pii-email", "cmd-injection"]
    matched = False
    for rule_id in example_rules:
        if suppression.matches(rule_id):
            console.print(f"  [green]✓[/green] {rule_id}")
            matched = True
    if not matched:
        console.print("  [dim]No example matches[/dim]")

    # Get audit log for this pattern
    console.print()
    console.print("[bold]Recent Activity:[/bold]")
    audit_entries = manager.get_audit_log(limit=5, pattern=pattern)

    if audit_entries:
        for entry in audit_entries:
            action_str = entry["action"]
            timestamp = entry["created_at"][:19]  # Trim microseconds
            console.print(f"  [{timestamp}] {action_str}")
    else:
        console.print("  [dim]No activity recorded[/dim]")

    console.print()


@suppress.command("clear")
@click.option(
    "--config",
    type=click.Path(),
    help="Path to suppressions.yaml (default: ./.raxe/suppressions.yaml)",
)
@click.confirmation_option(
    prompt="Are you sure you want to clear all suppressions?"
)
def clear_suppressions(config: str | None):
    """Clear all suppressions from config.

    \b
    Examples:
        raxe suppress clear
    """
    # Initialize manager with YAML format
    config_path = Path(config) if config else None
    manager = create_suppression_manager_with_yaml(yaml_path=config_path)

    # Clear all
    count = manager.clear_all(created_by="cli")

    # Always save to file
    manager.save_to_file()
    console.print(f"[green]✓[/green] Cleared {count} suppressions")
    console.print(f"  Saved to: {manager.config_path}")


@suppress.command("audit")
@click.option(
    "--config",
    type=click.Path(),
    help="Path to suppressions.yaml (default: ./.raxe/suppressions.yaml)",
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

    Note: Audit logging requires SQLite database (automatically used with YAML config).

    \b
    Examples:
        raxe suppress audit
        raxe suppress audit --limit 50
        raxe suppress audit --pattern "pi-*"
        raxe suppress audit --action applied
    """
    # Initialize manager (uses CompositeRepository with SQLite for audit)
    config_path = Path(config) if config else None
    manager = create_suppression_manager(config_path=config_path)

    # Get audit log
    entries = manager.get_audit_log(limit=limit, pattern=pattern, action=action)

    if not entries:
        console.print("[yellow]No audit entries found[/yellow]")
        console.print()
        console.print(
            "[dim]Note: Audit log tracks add/remove operations and applications.[/dim]"
        )
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
    help="Path to suppressions.yaml (default: ./.raxe/suppressions.yaml)",
)
def suppression_stats(config: str | None):
    """Show suppression statistics.

    \b
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

    # Show breakdown by action type if available
    by_action = stats.get("by_action_type", {})
    if by_action:
        console.print()
        console.print("[bold]By Action Type:[/bold]")
        for action_type, count in sorted(by_action.items()):
            color = {
                "SUPPRESS": "green",
                "FLAG": "yellow",
                "LOG": "blue",
            }.get(action_type, "white")
            console.print(f"  [{color}]{action_type}[/{color}]: {count}")

    console.print()


# Export the group
__all__ = ["suppress"]
