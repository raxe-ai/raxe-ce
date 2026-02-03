"""CLI commands for OpenClaw integration.

Commands:
- raxe openclaw install [--force] [--no-backup]
- raxe openclaw uninstall [--force]
- raxe openclaw status [--json]
"""

from __future__ import annotations

import json
import sys

import click
from rich.console import Console

from raxe.infrastructure.openclaw import (
    ConfigLoadError,
    OpenClawConfigManager,
    OpenClawHookManager,
)
from raxe.infrastructure.openclaw.models import OpenClawPaths as _OpenClawPathsClass

console = Console()


def _get_openclaw_paths() -> _OpenClawPathsClass:
    """Factory function for OpenClawPaths (allows monkeypatching in tests)."""
    return _OpenClawPathsClass()


@click.group()
def openclaw() -> None:
    """OpenClaw integration commands.

    Manage RAXE threat detection integration with OpenClaw,
    a self-hosted personal AI assistant platform.
    """
    pass


@openclaw.command("install")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force reinstall even if already configured",
)
@click.option(
    "--no-backup",
    is_flag=True,
    help="Skip creating a backup of openclaw.json",
)
def install(force: bool, no_backup: bool) -> None:
    """Install RAXE security hook into OpenClaw.

    This command:
    1. Creates the raxe-security hook directory
    2. Writes handler.ts and HOOK.md files
    3. Updates openclaw.json to enable the hook

    \b
    Examples:
        raxe openclaw install
        raxe openclaw install --force
    """
    paths = _get_openclaw_paths()
    config_manager = OpenClawConfigManager(paths)
    hook_manager = OpenClawHookManager(paths)

    # Check if OpenClaw is installed
    if not config_manager.is_openclaw_installed():
        console.print(
            f"[red]Error:[/red] OpenClaw not found. Expected config at: {paths.config_file}"
        )
        console.print("\n[dim]Make sure OpenClaw is installed and configured.[/dim]")
        sys.exit(1)

    # Check if already configured
    if config_manager.is_raxe_configured() and not force:
        console.print("[yellow]Warning:[/yellow] RAXE is already configured in OpenClaw.")
        console.print("\nUse [bold]--force[/bold] to reinstall.")
        sys.exit(1)

    try:
        # Create backup unless disabled
        if not no_backup:
            backup_path = config_manager.backup_config()
            console.print(f"[dim]Created backup: {backup_path}[/dim]")

        # Install hook files
        hook_manager.install_hook_files()
        console.print("[green]✓[/green] Installed hook files")

        # Add hook entry to config
        config_manager.add_raxe_hook_entry()
        console.print("[green]✓[/green] Updated openclaw.json")

        console.print("\n[green bold]RAXE security hook installed successfully![/green bold]")
        console.print(f"\n[dim]Hook location: {paths.raxe_hook_dir}[/dim]")

    except ConfigLoadError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except OSError as e:
        console.print(f"[red]Error:[/red] Failed to write files: {e}")
        sys.exit(1)


@openclaw.command("uninstall")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
def uninstall(force: bool) -> None:
    """Remove RAXE security hook from OpenClaw.

    This command:
    1. Removes the raxe-security hook directory
    2. Removes the hook entry from openclaw.json

    \b
    Examples:
        raxe openclaw uninstall
        raxe openclaw uninstall --force
    """
    paths = _get_openclaw_paths()
    config_manager = OpenClawConfigManager(paths)
    hook_manager = OpenClawHookManager(paths)

    # Check if OpenClaw is installed
    if not config_manager.is_openclaw_installed():
        console.print("[yellow]Info:[/yellow] OpenClaw not found. Nothing to uninstall.")
        return

    # Check if RAXE is configured
    if not config_manager.is_raxe_configured() and not hook_manager.hook_files_exist():
        console.print("[yellow]Info:[/yellow] RAXE is not configured in OpenClaw.")
        return

    # Confirm unless force flag is set
    if not force:
        if not click.confirm("Remove RAXE security hook from OpenClaw?"):
            console.print("[yellow]Aborted.[/yellow]")
            sys.exit(1)

    try:
        # Remove hook files
        if hook_manager.hook_files_exist():
            hook_manager.remove_hook_files()
            console.print("[green]✓[/green] Removed hook files")

        # Remove hook entry from config
        if config_manager.is_raxe_configured():
            config_manager.remove_raxe_hook_entry()
            console.print("[green]✓[/green] Updated openclaw.json")

        console.print("\n[green bold]RAXE security hook uninstalled successfully![/green bold]")

    except ConfigLoadError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except OSError as e:
        console.print(f"[red]Error:[/red] Failed to remove files: {e}")
        sys.exit(1)


@openclaw.command("status")
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output status as JSON",
)
def status(output_json: bool) -> None:
    """Show RAXE OpenClaw integration status.

    \b
    Examples:
        raxe openclaw status
        raxe openclaw status --json
    """
    paths = _get_openclaw_paths()
    config_manager = OpenClawConfigManager(paths)
    hook_manager = OpenClawHookManager(paths)

    # Gather status
    openclaw_installed = config_manager.is_openclaw_installed()
    raxe_configured = config_manager.is_raxe_configured() if openclaw_installed else False
    hook_files_exist = hook_manager.hook_files_exist()

    status_data = {
        "openclaw_installed": openclaw_installed,
        "raxe_configured": raxe_configured,
        "hook_files_exist": hook_files_exist,
        "openclaw_dir": str(paths.openclaw_dir),
        "raxe_hook_dir": str(paths.raxe_hook_dir),
    }

    if output_json:
        click.echo(json.dumps(status_data, indent=2))
        return

    # Human-readable output
    console.print("[bold]OpenClaw Integration Status[/bold]\n")

    if not openclaw_installed:
        console.print("[yellow]⚠[/yellow]  OpenClaw is [yellow]not installed[/yellow]")
        console.print(f"   Expected config: {paths.config_file}")
        return

    console.print("[green]✓[/green]  OpenClaw is [green]installed[/green]")
    console.print(f"   Config: {paths.config_file}")

    if raxe_configured:
        console.print("[green]✓[/green]  RAXE hook is [green]enabled[/green]")
    else:
        console.print("[yellow]⚠[/yellow]  RAXE hook is [yellow]not configured[/yellow]")

    if hook_files_exist:
        console.print("[green]✓[/green]  Hook files [green]exist[/green]")
    else:
        console.print("[yellow]⚠[/yellow]  Hook files [yellow]missing[/yellow]")

    console.print(f"\n   Hook directory: {paths.raxe_hook_dir}")

    # Show partial install warning
    if raxe_configured != hook_files_exist:
        console.print(
            "\n[yellow]Warning:[/yellow] Partial installation detected. "
            "Run [bold]raxe openclaw install --force[/bold] to fix."
        )
