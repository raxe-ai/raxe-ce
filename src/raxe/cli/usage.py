"""MSSP usage reporting CLI command."""

import sys

import click
from rich.table import Table

from raxe.cli.exit_codes import EXIT_CONFIG_ERROR
from raxe.cli.output import console, no_color_option, quiet_option


@click.command()
@click.argument("mssp_id")
@no_color_option
@quiet_option
def usage(mssp_id: str) -> None:
    """Show usage metrics for an MSSP.

    Displays active agents, scan volumes, and threat counts per customer.

    \b
    Examples:
        raxe mssp usage mssp_yourcompany
    """
    from raxe.application.usage_metering import UsageMeteringService

    service = UsageMeteringService()

    try:
        summary = service.get_usage_summary(mssp_id)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    # Header
    console.print(f"\n[bold cyan]MSSP Usage Report: {mssp_id}[/bold cyan]")
    console.print(f"  Customers: {summary.total_customers}")
    console.print(f"  Active Agents: {summary.active_agents}")
    console.print()

    # Customer table
    table = Table(title="Customer Breakdown")
    table.add_column("Customer ID", style="cyan")
    table.add_column("Name")
    table.add_column("Active Agents", justify="right")
    table.add_column("Total Scans", justify="right")
    table.add_column("Total Threats", justify="right")

    for cu in summary.customer_usage:
        table.add_row(
            cu.customer_id,
            cu.customer_name,
            str(cu.active_agents),
            str(cu.total_scans),
            str(cu.total_threats),
        )

    console.print(table)
