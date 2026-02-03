"""CLI commands for managing MSSPs.

Commands:
- raxe mssp create --id <id> --name <name> --webhook-url <url> --webhook-secret <secret>
- raxe mssp list [--output json|table]
- raxe mssp show <id> [--output json|table]
- raxe mssp delete <id> [--force]
- raxe mssp test-webhook <id>
"""

import json
import os
import sys

import click
from rich.console import Console
from rich.table import Table

from raxe.application.mssp_service import (
    CreateMSSPRequest,
    create_mssp_service,
)
from raxe.domain.mssp.models import MSSPTier
from raxe.infrastructure.mssp import get_mssp_base_path
from raxe.infrastructure.mssp.yaml_repository import (
    DuplicateMSSPError,
    MSSPNotFoundError,
)

console = Console()


@click.group()
def mssp():
    """Manage MSSPs for partner ecosystem."""
    pass


@mssp.command("create")
@click.option(
    "--id",
    "mssp_id",
    required=True,
    help="MSSP identifier (must start with 'mssp_')",
)
@click.option(
    "--name",
    "-n",
    required=True,
    help="Human-readable MSSP name (e.g., 'Your Security Services')",
)
@click.option(
    "--webhook-url",
    required=True,
    help="Webhook endpoint URL (HTTPS required except localhost)",
)
@click.option(
    "--webhook-secret",
    required=True,
    help="Shared secret for webhook signature verification",
)
@click.option(
    "--tier",
    type=click.Choice(["starter", "professional", "enterprise"]),
    default="starter",
    help="MSSP subscription tier (default: starter)",
)
@click.option(
    "--max-customers",
    type=int,
    default=10,
    help="Maximum number of customers (default: 10)",
)
def create_mssp(
    mssp_id: str,
    name: str,
    webhook_url: str,
    webhook_secret: str,
    tier: str,
    max_customers: int,
):
    """Create a new MSSP.

    Creates MSSP configuration at ~/.raxe/mssp/<mssp_id>/

    \b
    Examples:
        raxe mssp create --id mssp_yourcompany --name "Your Security Services" \\
            --webhook-url https://soc.yourcompany.com/raxe/alerts \\
            --webhook-secret my_secret_key
    """
    service = create_mssp_service()
    base_path = get_mssp_base_path()

    try:
        request = CreateMSSPRequest(
            mssp_id=mssp_id,
            name=name,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
            tier=MSSPTier(tier),
            max_customers=max_customers,
        )
        mssp_obj = service.create_mssp(request)

        console.print(f"[green]✓[/green] Created MSSP '{mssp_obj.name}'")
        console.print()
        console.print(f"  ID: [cyan]{mssp_obj.mssp_id}[/cyan]")
        console.print(f"  Name: {mssp_obj.name}")
        console.print(f"  Tier: [yellow]{mssp_obj.tier.value}[/yellow]")
        console.print(f"  Max Customers: {mssp_obj.max_customers}")
        console.print(f"  Webhook URL: {webhook_url}")
        console.print(f"  Path: {base_path / mssp_obj.mssp_id}")
        console.print()
    except DuplicateMSSPError as e:
        console.print(f"[red]Error:[/red] MSSP '{e.mssp_id}' already exists")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@mssp.command("list")
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
def list_mssps(output: str):
    """List all MSSPs.

    \b
    Examples:
        raxe mssp list
        raxe mssp list --output json
    """
    service = create_mssp_service()
    mssps = service.list_mssps()

    if not mssps:
        if output == "json":
            console.print("[]")
        else:
            console.print("[yellow]No MSSPs found[/yellow]")
            console.print()
            console.print("Create an MSSP with: [cyan]raxe mssp create ...[/cyan]")
        return

    if output == "json":
        data = [
            {
                "mssp_id": m.mssp_id,
                "name": m.name,
                "tier": m.tier.value,
                "max_customers": m.max_customers,
                "created_at": m.created_at,
            }
            for m in mssps
        ]
        console.print(json.dumps(data, indent=2))
    else:
        table = Table(title=f"MSSPs ({len(mssps)})", show_header=True)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="white")
        table.add_column("Tier", style="yellow")
        table.add_column("Max Customers", style="dim")
        table.add_column("Created", style="dim", no_wrap=True)

        for m in sorted(mssps, key=lambda x: x.mssp_id):
            created = m.created_at[:10] if m.created_at else "Unknown"
            table.add_row(m.mssp_id, m.name, m.tier.value, str(m.max_customers), created)

        console.print(table)
        console.print()


@mssp.command("show")
@click.argument("mssp_id")
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
def show_mssp(mssp_id: str, output: str):
    """Show details of a specific MSSP.

    \b
    Examples:
        raxe mssp show mssp_yourcompany
        raxe mssp show mssp_yourcompany --output json
    """
    service = create_mssp_service()
    base_path = get_mssp_base_path()

    try:
        mssp_obj = service.get_mssp(mssp_id)
    except MSSPNotFoundError:
        console.print(f"[red]Error:[/red] MSSP '{mssp_id}' not found")
        sys.exit(1)

    if output == "json":
        data = {
            "mssp_id": mssp_obj.mssp_id,
            "name": mssp_obj.name,
            "tier": mssp_obj.tier.value,
            "max_customers": mssp_obj.max_customers,
            "webhook_url": mssp_obj.webhook_config.url if mssp_obj.webhook_config else None,
            "created_at": mssp_obj.created_at,
            "updated_at": mssp_obj.updated_at,
        }
        console.print(json.dumps(data, indent=2))
    else:
        console.print()
        console.print("[bold]MSSP Details[/bold]")
        console.print()
        console.print(f"  ID: [cyan]{mssp_obj.mssp_id}[/cyan]")
        console.print(f"  Name: {mssp_obj.name}")
        console.print(f"  Tier: [yellow]{mssp_obj.tier.value}[/yellow]")
        console.print(f"  Max Customers: {mssp_obj.max_customers}")
        if mssp_obj.webhook_config:
            console.print(f"  Webhook URL: {mssp_obj.webhook_config.url}")
        created = mssp_obj.created_at[:10] if mssp_obj.created_at else "Unknown"
        console.print(f"  Created: {created}")
        console.print(f"  Path: {base_path / mssp_id}")
        console.print()

        # Show customers
        customers = service.list_customers(mssp_id)
        if customers:
            console.print("[bold]Customers:[/bold]")
            for c in customers:
                console.print(f"  - {c.customer_id}: {c.name} ({c.data_mode.value})")
            console.print()


@mssp.command("delete")
@click.argument("mssp_id")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
def delete_mssp(mssp_id: str, force: bool):
    """Delete an MSSP and all its data.

    WARNING: This deletes all MSSP customers and configurations.

    \b
    Examples:
        raxe mssp delete mssp_yourcompany --force
    """
    service = create_mssp_service()

    # Check MSSP exists first
    try:
        mssp_obj = service.get_mssp(mssp_id)
    except MSSPNotFoundError:
        console.print(f"[red]Error:[/red] MSSP '{mssp_id}' not found")
        sys.exit(1)

    if not force:
        msg = f"This will delete MSSP '{mssp_obj.name}' and all its customers."
        console.print(f"[yellow]Warning:[/yellow] {msg}")
        if not click.confirm("Are you sure?"):
            console.print("[dim]Aborted[/dim]")
            sys.exit(1)

    service.delete_mssp(mssp_id)
    console.print(f"[green]✓[/green] Deleted MSSP '{mssp_id}'")
    console.print()


@mssp.command("test-webhook")
@click.argument("mssp_id")
def test_webhook(mssp_id: str):
    """Test webhook connectivity for an MSSP.

    Sends a test event to the configured webhook endpoint.

    \b
    Examples:
        raxe mssp test-webhook mssp_yourcompany
    """
    import time

    import requests

    from raxe.infrastructure.webhooks.signing import WebhookSigner

    service = create_mssp_service()

    try:
        mssp_obj = service.get_mssp(mssp_id)
    except MSSPNotFoundError:
        console.print(f"[red]Error:[/red] MSSP '{mssp_id}' not found")
        sys.exit(1)

    if not mssp_obj.webhook_config:
        console.print(f"[red]Error:[/red] MSSP '{mssp_id}' has no webhook configured")
        sys.exit(1)

    webhook_url = mssp_obj.webhook_config.url
    webhook_secret = mssp_obj.webhook_config.secret

    console.print(f"Testing webhook: {webhook_url}")

    # Build test payload
    test_payload = {
        "event_type": "test",
        "mssp_id": mssp_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "message": "This is a test event from RAXE CLI",
    }

    # Sign and send
    body = json.dumps(test_payload).encode()
    signer = WebhookSigner(webhook_secret)
    headers = signer.get_signature_headers(body)
    headers["Content-Type"] = "application/json"

    try:
        # Allow skipping SSL verification for testing with self-signed certs
        verify_ssl = os.environ.get("RAXE_SKIP_SSL_VERIFY", "").lower() != "true"
        if not verify_ssl:
            # Suppress InsecureRequestWarning when SSL verification is intentionally disabled
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.post(
            webhook_url,
            data=body,
            headers=headers,
            timeout=mssp_obj.webhook_config.timeout_seconds,
            verify=verify_ssl,
        )

        if response.ok:
            console.print(f"[green]✓[/green] Webhook test successful (HTTP {response.status_code})")
        else:
            console.print(f"[red]✗[/red] Webhook test failed (HTTP {response.status_code})")
            console.print(f"  Response: {response.text[:200]}")
            sys.exit(1)
    except requests.RequestException as e:
        console.print(f"[red]✗[/red] Webhook test failed: {e}")
        sys.exit(1)


@mssp.command("cleanup")
@click.option(
    "--retention-days",
    type=int,
    default=90,
    help="Delete audit logs older than N days (default: 90)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be deleted without actually deleting",
)
def cleanup_retention(retention_days: int, dry_run: bool):
    """Clean up old audit logs based on retention policy.

    Deletes MSSP audit log files older than the specified retention period.
    Use --dry-run to preview what would be deleted.

    \b
    Examples:
        raxe mssp cleanup --retention-days 30
        raxe mssp cleanup --dry-run
    """
    from datetime import timedelta
    from pathlib import Path

    from raxe.infrastructure.audit.mssp_audit_logger import get_mssp_audit_logger

    logger = get_mssp_audit_logger()

    if dry_run:
        # Preview mode - count files that would be deleted
        from datetime import datetime, timezone

        log_dir = Path(logger.config.log_directory).expanduser()
        if not log_dir.exists():
            console.print("[dim]No audit logs found[/dim]")
            return

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        would_delete = 0

        for log_file in log_dir.glob("mssp_audit_*.jsonl"):
            try:
                date_str = log_file.stem.replace("mssp_audit_", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if file_date < cutoff_date:
                    console.print(f"  Would delete: {log_file.name}")
                    would_delete += 1
            except ValueError:
                continue

        if would_delete > 0:
            console.print(f"\n[yellow]Would delete {would_delete} file(s)[/yellow]")
        else:
            console.print("[green]No files older than {retention_days} days[/green]")
    else:
        # Actually delete
        deleted = logger.cleanup_old_logs(retention_days=retention_days)

        if deleted > 0:
            console.print(f"[green]✓[/green] Deleted {deleted} audit log file(s)")
        else:
            console.print(f"[dim]No audit logs older than {retention_days} days[/dim]")


# Export the group
__all__ = ["mssp"]
