"""CLI commands for managing agents under MSSPs/customers.

Commands:
- raxe agent list --mssp <mssp_id> [--customer <customer_id>] [--output json|table]
- raxe agent status --mssp <mssp_id> --customer <customer_id> <agent_id>
"""

import json
import sys

import click
from rich.table import Table

from raxe.application.mssp_service import create_mssp_service
from raxe.cli.exit_codes import EXIT_CONFIG_ERROR, EXIT_INVALID_INPUT, EXIT_SCAN_ERROR
from raxe.cli.output import console, display_success
from raxe.infrastructure.agent.registry import get_agent_registry
from raxe.infrastructure.mssp.yaml_repository import (
    CustomerNotFoundError,
    MSSPNotFoundError,
)


class AgentNotFoundError(Exception):
    """Raised when an agent is not found."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"Agent '{agent_id}' not found")


@click.group()
def agent():
    """Manage agents within MSSPs/customers."""
    pass


@agent.command("list")
@click.option(
    "--mssp",
    "mssp_id",
    required=True,
    help="MSSP identifier",
)
@click.option(
    "--customer",
    "customer_id",
    help="Customer identifier (optional, lists all if not specified)",
)
@click.option(
    "--output",
    "--format",
    "-o",
    "-f",
    "output",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table)",
)
def list_agents(mssp_id: str, customer_id: str | None, output: str):
    """List agents for an MSSP or customer.

    \b
    Examples:
        raxe agent list --mssp mssp_yourcompany
        raxe agent list --mssp mssp_yourcompany --customer cust_acme
        raxe agent list --mssp mssp_yourcompany --output json
    """
    service = create_mssp_service()

    # Verify MSSP exists
    try:
        service.get_mssp(mssp_id)
    except MSSPNotFoundError as e:
        console.print(f"[red]Error:[/red] MSSP '{e.mssp_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)

    # Verify customer exists if specified
    if customer_id:
        try:
            service.get_customer(mssp_id, customer_id)
        except CustomerNotFoundError as e:
            console.print(f"[red]Error:[/red] Customer '{e.customer_id}' not found")
            sys.exit(EXIT_CONFIG_ERROR)

    # Get agents from registry (populated by heartbeat service)
    registry = get_agent_registry()
    agents = registry.list_agents_with_status(mssp_id=mssp_id, customer_id=customer_id)

    if not agents:
        if output == "json":
            click.echo("[]")
        else:
            console.print("[yellow]No agents found[/yellow]")
            console.print()
            console.print("Agents are registered when they send heartbeats.")
            console.print("Deploy RAXE SDK with your customer API key to register agents.")
        return

    if output == "json":
        click.echo(json.dumps(agents, indent=2, default=str))
    else:
        table = Table(title=f"Agents ({len(agents)})", show_header=True)
        table.add_column("Agent ID", style="cyan", no_wrap=True)
        table.add_column("Customer", style="white")
        table.add_column("Status", style="yellow")
        table.add_column("Version", style="dim")
        table.add_column("Last Heartbeat", style="dim", no_wrap=True)

        for a in agents:
            status_style = "green" if a.get("status") == "online" else "red"
            table.add_row(
                a.get("agent_id", ""),
                a.get("customer_id", ""),
                f"[{status_style}]{a.get('status', 'unknown')}[/{status_style}]",
                a.get("version", ""),
                a.get("last_heartbeat", "")[:19] if a.get("last_heartbeat") else "Never",
            )

        console.print(table)
        console.print()


@agent.command("status")
@click.option(
    "--mssp",
    "mssp_id",
    required=True,
    help="MSSP identifier",
)
@click.option(
    "--customer",
    "customer_id",
    required=True,
    help="Customer identifier",
)
@click.argument("agent_id")
@click.option(
    "--output",
    "--format",
    "-o",
    "-f",
    "output",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table)",
)
def agent_status(mssp_id: str, customer_id: str, agent_id: str, output: str):
    """Show status of a specific agent.

    \b
    Examples:
        raxe agent status --mssp mssp_yourcompany --customer cust_acme agent_xyz
        raxe agent status --mssp mssp_yourcompany --customer cust_acme agent_xyz --output json
    """
    service = create_mssp_service()

    # Verify MSSP exists
    try:
        service.get_mssp(mssp_id)
    except MSSPNotFoundError as e:
        console.print(f"[red]Error:[/red] MSSP '{e.mssp_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)

    # Verify customer exists
    try:
        service.get_customer(mssp_id, customer_id)
    except CustomerNotFoundError as e:
        console.print(f"[red]Error:[/red] Customer '{e.customer_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)

    # Look up agent from registry
    registry = get_agent_registry()
    agent_data = registry.get_agent_with_status(agent_id)

    if not agent_data:
        console.print(f"[red]Error:[/red] Agent '{agent_id}' not found")
        console.print()
        console.print("Agents are registered when they send heartbeats.")
        console.print("Ensure the agent is deployed and configured with the correct API key.")
        sys.exit(EXIT_CONFIG_ERROR)

    # Verify agent belongs to the specified MSSP/customer
    if agent_data.get("mssp_id") != mssp_id:
        console.print(f"[red]Error:[/red] Agent '{agent_id}' does not belong to MSSP '{mssp_id}'")
        sys.exit(EXIT_INVALID_INPUT)
    if agent_data.get("customer_id") != customer_id:
        console.print(
            f"[red]Error:[/red] Agent '{agent_id}' does not belong to customer '{customer_id}'"
        )
        sys.exit(EXIT_INVALID_INPUT)

    if output == "json":
        click.echo(json.dumps(agent_data, indent=2, default=str))
    else:
        # Display as formatted table
        table = Table(title=f"Agent Status: {agent_id}", show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        status = agent_data.get("status", "unknown")
        status_style = {
            "online": "green",
            "degraded": "yellow",
            "offline": "red",
        }.get(status, "dim")

        table.add_row("Agent ID", agent_data.get("agent_id", ""))
        table.add_row("Status", f"[{status_style}]{status}[/{status_style}]")
        table.add_row("MSSP", agent_data.get("mssp_id", ""))
        table.add_row("Customer", agent_data.get("customer_id", ""))
        table.add_row("Version", agent_data.get("version", ""))
        table.add_row("Platform", agent_data.get("platform", ""))
        table.add_row("Integration", agent_data.get("integration") or "direct")
        first_seen = agent_data.get("first_seen", "")
        table.add_row("First Seen", first_seen[:19] if first_seen else "N/A")
        last_hb = agent_data.get("last_heartbeat", "")
        table.add_row("Last Heartbeat", last_hb[:19] if last_hb else "Never")
        table.add_row("Uptime", f"{agent_data.get('uptime_seconds', 0):.0f}s")
        table.add_row("Total Scans", str(agent_data.get("scans_total", 0)))
        table.add_row("Total Threats", str(agent_data.get("threats_total", 0)))

        console.print(table)
        console.print()


@agent.command("register")
@click.option(
    "--mssp",
    "mssp_id",
    required=True,
    help="MSSP identifier",
)
@click.option(
    "--customer",
    "customer_id",
    required=True,
    help="Customer identifier",
)
@click.option(
    "--version",
    "version",
    default="",
    help="Agent version (e.g., '0.10.0')",
)
@click.option(
    "--platform",
    "platform",
    default="",
    help="Platform (darwin, linux, win32)",
)
@click.option(
    "--integration",
    "integration",
    default=None,
    help="Integration type (langchain, crewai, etc.)",
)
@click.argument("agent_id")
def register_agent(
    mssp_id: str,
    customer_id: str,
    agent_id: str,
    version: str,
    platform: str,
    integration: str | None,
):
    """Register a new agent manually.

    \b
    Examples:
        raxe agent register --mssp mssp_yourcompany --customer cust_acme agent_xyz
        raxe agent register --mssp mssp_yourcompany --customer cust_acme agent_xyz \\
            --version 0.10.0 --platform darwin
    """
    import platform as plat

    service = create_mssp_service()

    # Verify MSSP exists
    try:
        service.get_mssp(mssp_id)
    except MSSPNotFoundError as e:
        console.print(f"[red]Error:[/red] MSSP '{e.mssp_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)

    # Verify customer exists
    try:
        service.get_customer(mssp_id, customer_id)
    except CustomerNotFoundError as e:
        console.print(f"[red]Error:[/red] Customer '{e.customer_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)

    # Use current platform if not specified
    if not platform:
        platform = plat.system().lower()
        if platform == "windows":
            platform = "win32"

    # Register via heartbeat
    registry = get_agent_registry()
    _status_change = registry.register_heartbeat(
        agent_id=agent_id,
        mssp_id=mssp_id,
        customer_id=customer_id,
        version=version,
        platform=platform,
        integration=integration,
        uptime_seconds=0,
        scans=0,
        threats=0,
    )

    display_success(f"Registered agent '{agent_id}'")
    console.print(f"  MSSP: {mssp_id}")
    console.print(f"  Customer: {customer_id}")
    if version:
        console.print(f"  Version: {version}")
    console.print(f"  Platform: {platform}")
    console.print("  Status: [green]online[/green]")


@agent.command("heartbeat")
@click.argument("agent_id")
@click.option(
    "--scans",
    default=0,
    help="Scans since last heartbeat",
)
@click.option(
    "--threats",
    default=0,
    help="Threats since last heartbeat",
)
def send_heartbeat(agent_id: str, scans: int, threats: int):
    """Send a heartbeat for an agent.

    \b
    Examples:
        raxe agent heartbeat agent_xyz
        raxe agent heartbeat agent_xyz --scans 10 --threats 2
    """
    registry = get_agent_registry()
    record = registry.get_agent(agent_id)

    if not record:
        console.print(f"[red]Error:[/red] Agent '{agent_id}' not found")
        console.print()
        console.print("Register the agent first with: raxe agent register")
        sys.exit(EXIT_CONFIG_ERROR)

    # Send heartbeat with current uptime
    from datetime import datetime, timezone

    first_seen = datetime.fromisoformat(record.first_seen.replace("Z", "+00:00"))
    uptime = (datetime.now(timezone.utc) - first_seen).total_seconds()

    registry.register_heartbeat(
        agent_id=agent_id,
        mssp_id=record.mssp_id,
        customer_id=record.customer_id,
        version=record.version,
        platform=record.platform,
        integration=record.integration,
        uptime_seconds=uptime,
        scans=scans,
        threats=threats,
    )

    display_success(f"Heartbeat sent for '{agent_id}'")
    console.print("  Status: [green]online[/green]")
    console.print(f"  Uptime: {uptime:.0f}s")


@agent.command("unregister")
@click.argument("agent_id")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
def unregister_agent(agent_id: str, force: bool):
    """Unregister an agent.

    \b
    Examples:
        raxe agent unregister agent_xyz
        raxe agent unregister agent_xyz --force
    """
    registry = get_agent_registry()
    record = registry.get_agent(agent_id)

    if not record:
        console.print(f"[red]Error:[/red] Agent '{agent_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)

    if not force:
        console.print(f"About to unregister agent '{agent_id}'")
        console.print(f"  MSSP: {record.mssp_id}")
        console.print(f"  Customer: {record.customer_id}")
        console.print()
        if not click.confirm("Are you sure?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

    removed = registry.remove_agent(agent_id)

    if removed:
        display_success(f"Unregistered agent '{agent_id}'")
    else:
        console.print("[red]Error:[/red] Failed to unregister agent")
        sys.exit(EXIT_SCAN_ERROR)


# Export the group
__all__ = ["agent"]
