"""CLI commands for managing customers under MSSPs.

Commands:
- raxe customer create --mssp <mssp_id> --id <id> --name <name>
- raxe customer list --mssp <mssp_id> [--output json|table]
- raxe customer show --mssp <mssp_id> <customer_id> [--output json|table]
- raxe customer configure --mssp <mssp_id> <customer_id> [options]
- raxe customer delete --mssp <mssp_id> <customer_id> [--force]
"""

import json
import sys

import click
from rich.table import Table

from raxe.application.mssp_service import (
    ConfigureCustomerRequest,
    CreateCustomerRequest,
    create_mssp_service,
)
from raxe.cli.exit_codes import EXIT_CONFIG_ERROR, EXIT_INVALID_INPUT, EXIT_SCAN_ERROR
from raxe.cli.output import console, display_success
from raxe.domain.mssp.models import DataMode
from raxe.infrastructure.mssp.yaml_repository import (
    CustomerNotFoundError,
    DuplicateCustomerError,
    MSSPNotFoundError,
)


@click.group()
def customer():
    """Manage customers within MSSPs."""
    pass


@customer.command("create")
@click.option(
    "--mssp",
    "mssp_id",
    required=True,
    help="Parent MSSP identifier",
)
@click.option(
    "--id",
    "customer_id",
    required=True,
    help="Customer identifier (must start with 'cust_')",
)
@click.option(
    "--name",
    "-n",
    required=True,
    help="Human-readable customer name (e.g., 'Acme Corp')",
)
@click.option(
    "--data-mode",
    type=click.Choice(["full", "privacy_safe"]),
    default="privacy_safe",
    help="Data privacy mode (default: privacy_safe)",
)
@click.option(
    "--retention-days",
    type=int,
    default=30,
    help="Data retention period in days (1-365, default: 30)",
)
@click.option(
    "--heartbeat-threshold",
    type=int,
    default=300,
    help="Agent heartbeat threshold in seconds (60-3600, default: 300)",
)
def create_customer(
    mssp_id: str,
    customer_id: str,
    name: str,
    data_mode: str,
    retention_days: int,
    heartbeat_threshold: int,
):
    """Create a new customer under an MSSP.

    Creates customer configuration at ~/.raxe/mssp/<mssp_id>/customers/<customer_id>/

    \b
    Examples:
        raxe customer create --mssp mssp_yourcompany --id cust_acme --name "Acme Corp"
        raxe customer create --mssp mssp_yourcompany --id cust_acme --name "Acme Corp" \\
            --data-mode full --retention-days 90
    """
    service = create_mssp_service()

    try:
        request = CreateCustomerRequest(
            customer_id=customer_id,
            mssp_id=mssp_id,
            name=name,
            data_mode=DataMode(data_mode),
            retention_days=retention_days,
            heartbeat_threshold_seconds=heartbeat_threshold,
        )
        customer_obj = service.create_customer(request)

        display_success(f"Created customer '{customer_obj.name}'")
        console.print(f"  ID: [cyan]{customer_obj.customer_id}[/cyan]")
        console.print(f"  MSSP: {customer_obj.mssp_id}")
        console.print(f"  Name: {customer_obj.name}")
        console.print(f"  Data Mode: [yellow]{customer_obj.data_mode.value}[/yellow]")
        console.print(f"  Retention Days: {customer_obj.retention_days}")
        console.print(f"  Heartbeat Threshold: {customer_obj.heartbeat_threshold_seconds}s")
        console.print()
    except MSSPNotFoundError as e:
        console.print(f"[red]Error:[/red] MSSP '{e.mssp_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)
    except DuplicateCustomerError as e:
        msg = f"Customer '{e.customer_id}' already exists in MSSP '{e.mssp_id}'"
        console.print(f"[red]Error:[/red] {msg}")
        sys.exit(EXIT_INVALID_INPUT)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(EXIT_INVALID_INPUT)


@customer.command("list")
@click.option(
    "--mssp",
    "mssp_id",
    required=True,
    help="Parent MSSP identifier",
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
def list_customers(mssp_id: str, output: str):
    """List all customers for an MSSP.

    \b
    Examples:
        raxe customer list --mssp mssp_yourcompany
        raxe customer list --mssp mssp_yourcompany --output json
    """
    service = create_mssp_service()

    try:
        customers = service.list_customers(mssp_id)
    except MSSPNotFoundError as e:
        console.print(f"[red]Error:[/red] MSSP '{e.mssp_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)

    if not customers:
        if output == "json":
            console.print("[]")
        else:
            console.print("[yellow]No customers found[/yellow]")
            console.print()
            cmd = f"raxe customer create --mssp {mssp_id} --id cust_example --name 'Example'"
            console.print(f"Create a customer with: [cyan]{cmd}[/cyan]")
        return

    if output == "json":
        data = [
            {
                "customer_id": c.customer_id,
                "mssp_id": c.mssp_id,
                "name": c.name,
                "data_mode": c.data_mode.value,
                "retention_days": c.retention_days,
                "heartbeat_threshold_seconds": c.heartbeat_threshold_seconds,
                "created_at": c.created_at,
            }
            for c in customers
        ]
        console.print(json.dumps(data, indent=2))
    else:
        table = Table(title=f"Customers for {mssp_id} ({len(customers)})", show_header=True)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="white")
        table.add_column("Data Mode", style="yellow")
        table.add_column("Retention", style="dim")
        table.add_column("Created", style="dim", no_wrap=True)

        for c in sorted(customers, key=lambda x: x.customer_id):
            created = c.created_at[:10] if c.created_at else "Unknown"
            table.add_row(
                c.customer_id,
                c.name,
                c.data_mode.value,
                f"{c.retention_days}d",
                created,
            )

        console.print(table)
        console.print()


@customer.command("show")
@click.option(
    "--mssp",
    "mssp_id",
    required=True,
    help="Parent MSSP identifier",
)
@click.argument("customer_id")
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
def show_customer(mssp_id: str, customer_id: str, output: str):
    """Show details of a specific customer.

    \b
    Examples:
        raxe customer show --mssp mssp_yourcompany cust_acme
        raxe customer show --mssp mssp_yourcompany cust_acme --output json
    """
    service = create_mssp_service()

    try:
        customer_obj = service.get_customer(mssp_id, customer_id)
    except MSSPNotFoundError as e:
        console.print(f"[red]Error:[/red] MSSP '{e.mssp_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)
    except CustomerNotFoundError as e:
        console.print(f"[red]Error:[/red] Customer '{e.customer_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)

    if output == "json":
        data = {
            "customer_id": customer_obj.customer_id,
            "mssp_id": customer_obj.mssp_id,
            "name": customer_obj.name,
            "data_mode": customer_obj.data_mode.value,
            "data_fields": customer_obj.data_fields,
            "retention_days": customer_obj.retention_days,
            "heartbeat_threshold_seconds": customer_obj.heartbeat_threshold_seconds,
            "webhook_url": customer_obj.webhook_config.url if customer_obj.webhook_config else None,
            "created_at": customer_obj.created_at,
            "updated_at": customer_obj.updated_at,
        }
        console.print(json.dumps(data, indent=2))
    else:
        console.print()
        console.print("[bold]Customer Details[/bold]")
        console.print()
        console.print(f"  ID: [cyan]{customer_obj.customer_id}[/cyan]")
        console.print(f"  MSSP: {customer_obj.mssp_id}")
        console.print(f"  Name: {customer_obj.name}")
        console.print(f"  Data Mode: [yellow]{customer_obj.data_mode.value}[/yellow]")
        if customer_obj.data_fields:
            console.print(f"  Data Fields: {', '.join(customer_obj.data_fields)}")
        console.print(f"  Retention: {customer_obj.retention_days} days")
        console.print(f"  Heartbeat Threshold: {customer_obj.heartbeat_threshold_seconds}s")
        if customer_obj.webhook_config:
            console.print(f"  Webhook Override: {customer_obj.webhook_config.url}")
        created = customer_obj.created_at[:10] if customer_obj.created_at else "Unknown"
        console.print(f"  Created: {created}")
        console.print()


@customer.command("configure")
@click.option(
    "--mssp",
    "mssp_id",
    required=True,
    help="Parent MSSP identifier",
)
@click.argument("customer_id")
@click.option(
    "--data-mode",
    type=click.Choice(["full", "privacy_safe"]),
    help="Data privacy mode",
)
@click.option(
    "--data-fields",
    help="Comma-separated list of data fields (e.g., 'prompt,response,matched_text')",
)
@click.option(
    "--retention-days",
    type=int,
    help="Data retention period in days (1-365)",
)
@click.option(
    "--heartbeat-threshold",
    type=int,
    help="Agent heartbeat threshold in seconds (60-3600)",
)
@click.option(
    "--webhook-url",
    help="Customer-specific webhook URL override",
)
@click.option(
    "--webhook-secret",
    help="Webhook secret (required if --webhook-url is set)",
)
def configure_customer(
    mssp_id: str,
    customer_id: str,
    data_mode: str | None,
    data_fields: str | None,
    retention_days: int | None,
    heartbeat_threshold: int | None,
    webhook_url: str | None,
    webhook_secret: str | None,
):
    """Configure an existing customer.

    \b
    Examples:
        raxe customer configure --mssp mssp_yourcompany cust_acme --data-mode full
        raxe customer configure --mssp mssp_yourcompany cust_acme \\
            --data-fields prompt,response,matched_text
        raxe customer configure --mssp mssp_yourcompany cust_acme --retention-days 90
    """
    service = create_mssp_service()

    # Validate retention days
    if retention_days is not None and not (1 <= retention_days <= 365):
        console.print("[red]Error:[/red] retention-days must be between 1 and 365")
        sys.exit(EXIT_INVALID_INPUT)

    # Validate heartbeat threshold
    if heartbeat_threshold is not None and not (60 <= heartbeat_threshold <= 3600):
        console.print("[red]Error:[/red] heartbeat-threshold must be between 60 and 3600")
        sys.exit(EXIT_INVALID_INPUT)

    # Validate webhook config
    if webhook_url and not webhook_secret:
        console.print("[red]Error:[/red] --webhook-secret is required when --webhook-url is set")
        sys.exit(EXIT_INVALID_INPUT)

    # Validate webhook URL is HTTPS
    if webhook_url:
        from urllib.parse import urlparse

        parsed = urlparse(webhook_url)
        is_localhost = parsed.netloc.startswith("localhost") or parsed.netloc.startswith(
            "127.0.0.1"
        )
        if parsed.scheme != "https" and not is_localhost:
            console.print("[red]Error:[/red] Webhook URL must use HTTPS (except localhost)")
            sys.exit(EXIT_INVALID_INPUT)

    try:
        # Parse data fields
        parsed_data_fields = None
        if data_fields:
            parsed_data_fields = [f.strip() for f in data_fields.split(",")]

        request = ConfigureCustomerRequest(
            customer_id=customer_id,
            mssp_id=mssp_id,
            data_mode=DataMode(data_mode) if data_mode else None,
            data_fields=parsed_data_fields,
            retention_days=retention_days,
            heartbeat_threshold_seconds=heartbeat_threshold,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )
        customer_obj = service.configure_customer(request)

        display_success(f"Updated customer '{customer_obj.customer_id}'")
        console.print(f"  Data Mode: [yellow]{customer_obj.data_mode.value}[/yellow]")
        if customer_obj.data_fields:
            console.print(f"  Data Fields: {', '.join(customer_obj.data_fields)}")
        console.print(f"  Retention: {customer_obj.retention_days} days")
        console.print(f"  Heartbeat Threshold: {customer_obj.heartbeat_threshold_seconds}s")
        if customer_obj.webhook_config:
            console.print(f"  Webhook Override: {customer_obj.webhook_config.url}")
        console.print()
    except MSSPNotFoundError as e:
        console.print(f"[red]Error:[/red] MSSP '{e.mssp_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)
    except CustomerNotFoundError as e:
        console.print(f"[red]Error:[/red] Customer '{e.customer_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(EXIT_INVALID_INPUT)


@customer.command("delete")
@click.option(
    "--mssp",
    "mssp_id",
    required=True,
    help="Parent MSSP identifier",
)
@click.argument("customer_id")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
def delete_customer(mssp_id: str, customer_id: str, force: bool):
    """Delete a customer.

    \b
    Examples:
        raxe customer delete --mssp mssp_yourcompany cust_acme --force
    """
    service = create_mssp_service()

    # Check customer exists first
    try:
        customer_obj = service.get_customer(mssp_id, customer_id)
    except MSSPNotFoundError as e:
        console.print(f"[red]Error:[/red] MSSP '{e.mssp_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)
    except CustomerNotFoundError as e:
        console.print(f"[red]Error:[/red] Customer '{e.customer_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)

    if not force:
        msg = f"This will delete customer '{customer_obj.name}'."
        console.print(f"[yellow]Warning:[/yellow] {msg}")
        if not click.confirm("Are you sure?"):
            console.print("[dim]Aborted[/dim]")
            return

    service.delete_customer(mssp_id, customer_id)
    display_success(f"Deleted customer '{customer_id}'")


# SIEM Subgroup
@customer.group("siem")
def customer_siem():
    """Manage SIEM integration for a customer.

    Configure per-customer SIEM routing to Splunk, CrowdStrike, or Sentinel.
    """
    pass


@customer_siem.command("configure")
@click.option(
    "--mssp",
    "mssp_id",
    required=True,
    help="Parent MSSP identifier",
)
@click.argument("customer_id")
@click.option(
    "--type",
    "siem_type",
    required=True,
    type=click.Choice(["splunk", "crowdstrike", "sentinel", "cef", "arcsight"]),
    help="SIEM platform type",
)
@click.option(
    "--url",
    "endpoint_url",
    required=True,
    help="SIEM ingestion endpoint URL",
)
@click.option(
    "--token",
    "auth_token",
    required=True,
    help="Authentication token for the SIEM",
)
@click.option(
    "--batch-size",
    type=int,
    default=100,
    help="Maximum events per batch (default: 100)",
)
@click.option(
    "--index",
    help="Splunk index name (Splunk only)",
)
@click.option(
    "--source",
    help="Splunk source identifier (Splunk only)",
)
@click.option(
    "--workspace-id",
    help="Azure Log Analytics workspace ID (Sentinel only)",
)
@click.option(
    "--log-type",
    help="Custom log type name (Sentinel only, default: RaxeThreatDetection)",
)
@click.option(
    "--repository",
    help="LogScale repository name (CrowdStrike only)",
)
@click.option(
    "--parser",
    help="LogScale parser name (CrowdStrike only, default: raxe)",
)
# CEF-specific options
@click.option(
    "--transport",
    type=click.Choice(["http", "tcp", "udp"]),
    default="http",
    help="CEF transport protocol (CEF only, default: http)",
)
@click.option(
    "--port",
    "syslog_port",
    type=int,
    help="Syslog port for CEF (CEF only, default: 514 for UDP, 6514 for TLS)",
)
@click.option(
    "--tls",
    "use_tls",
    is_flag=True,
    help="Use TLS for TCP transport (CEF only)",
)
@click.option(
    "--facility",
    type=int,
    default=16,
    help="Syslog facility code (CEF only, default: 16 = local0)",
)
# ArcSight-specific options
@click.option(
    "--smart-connector-id",
    help="ArcSight SmartConnector ID (ArcSight only)",
)
@click.option(
    "--device-vendor",
    default="RAXE",
    help="ArcSight device vendor (ArcSight only, default: RAXE)",
)
@click.option(
    "--device-product",
    default="ThreatDetection",
    help="ArcSight device product (ArcSight only, default: ThreatDetection)",
)
def configure_siem(
    mssp_id: str,
    customer_id: str,
    siem_type: str,
    endpoint_url: str,
    auth_token: str,
    batch_size: int,
    index: str | None,
    source: str | None,
    workspace_id: str | None,
    log_type: str | None,
    repository: str | None,
    parser: str | None,
    # CEF options
    transport: str,
    syslog_port: int | None,
    use_tls: bool,
    facility: int,
    # ArcSight options
    smart_connector_id: str | None,
    device_vendor: str,
    device_product: str,
):
    """Configure SIEM integration for a customer.

    Each customer can have their own SIEM configuration, allowing routing
    to different platforms (Splunk, CrowdStrike, Sentinel, CEF, ArcSight).

    \b
    Examples:
        # Configure Splunk
        raxe customer siem configure --mssp mssp_yourcompany cust_acme \\
            --type splunk \\
            --url https://splunk.company.com:8088/services/collector/event \\
            --token "your-hec-token" \\
            --index security

        # Configure CrowdStrike
        raxe customer siem configure --mssp mssp_yourcompany cust_acme \\
            --type crowdstrike \\
            --url https://cloud.us.humio.com/api/v1/ingest/hec \\
            --token "your-ingest-token"

        # Configure Sentinel
        raxe customer siem configure --mssp mssp_yourcompany cust_acme \\
            --type sentinel \\
            --url https://workspace.ods.opinsights.azure.com/api/logs \\
            --token "your-shared-key" \\
            --workspace-id "workspace-id"

        # Configure CEF over HTTP
        raxe customer siem configure --mssp mssp_yourcompany cust_acme \\
            --type cef \\
            --url https://collector.company.com/cef \\
            --token "your-token"

        # Configure CEF over Syslog UDP
        raxe customer siem configure --mssp mssp_yourcompany cust_acme \\
            --type cef \\
            --url syslog://siem.company.com \\
            --token "not-used" \\
            --transport udp --port 514

        # Configure CEF over Syslog TCP with TLS
        raxe customer siem configure --mssp mssp_yourcompany cust_acme \\
            --type cef \\
            --url syslog://siem.company.com \\
            --token "not-used" \\
            --transport tcp --port 6514 --tls

        # Configure ArcSight SmartConnector
        raxe customer siem configure --mssp mssp_yourcompany cust_acme \\
            --type arcsight \\
            --url https://arcsight.company.com/receiver/v1/events \\
            --token "your-token" \\
            --smart-connector-id "sc-001"
    """
    from dataclasses import replace

    from raxe.domain.siem.config import SIEMConfig, SIEMType

    service = create_mssp_service()

    try:
        # Get existing customer
        customer_obj = service.get_customer(mssp_id, customer_id)

        # Build extra config based on SIEM type
        extra: dict = {}
        if siem_type == "splunk":
            if index:
                extra["index"] = index
            if source:
                extra["source"] = source
        elif siem_type == "sentinel":
            if workspace_id:
                extra["workspace_id"] = workspace_id
            if log_type:
                extra["log_type"] = log_type
        elif siem_type == "crowdstrike":
            if repository:
                extra["repository"] = repository
            if parser:
                extra["parser"] = parser
        elif siem_type == "cef":
            extra["transport"] = transport
            if syslog_port:
                extra["port"] = syslog_port
            extra["facility"] = facility
            if use_tls:
                extra["use_tls"] = True
        elif siem_type == "arcsight":
            if smart_connector_id:
                extra["smart_connector_id"] = smart_connector_id
            extra["device_vendor"] = device_vendor
            extra["device_product"] = device_product

        # Create SIEM config
        siem_config = SIEMConfig(
            siem_type=SIEMType.from_string(siem_type),
            endpoint_url=endpoint_url,
            auth_token=auth_token,
            batch_size=batch_size,
            extra=extra,
        )

        # Update customer with SIEM config
        # Since MSSPCustomer is frozen, create a new instance
        from raxe.infrastructure.mssp import get_mssp_base_path
        from raxe.infrastructure.mssp.yaml_repository import YamlCustomerRepository

        base_path = get_mssp_base_path()
        repo = YamlCustomerRepository(base_path, mssp_id)

        updated_customer = replace(customer_obj, siem_config=siem_config)
        repo.update(updated_customer)

        display_success(f"Configured SIEM for customer '{customer_id}'")
        console.print(f"  Type: [cyan]{siem_type}[/cyan]")
        console.print(f"  Endpoint: {endpoint_url}")
        console.print(f"  Batch Size: {batch_size}")
        if extra:
            for k, v in extra.items():
                console.print(f"  {k.replace('_', ' ').title()}: {v}")
        console.print()

    except MSSPNotFoundError as e:
        console.print(f"[red]Error:[/red] MSSP '{e.mssp_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)
    except CustomerNotFoundError as e:
        console.print(f"[red]Error:[/red] Customer '{e.customer_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(EXIT_INVALID_INPUT)


@customer_siem.command("show")
@click.option(
    "--mssp",
    "mssp_id",
    required=True,
    help="Parent MSSP identifier",
)
@click.argument("customer_id")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table)",
)
def show_siem(mssp_id: str, customer_id: str, output: str):
    """Show SIEM configuration for a customer.

    \b
    Examples:
        raxe customer siem show --mssp mssp_yourcompany cust_acme
        raxe customer siem show --mssp mssp_yourcompany cust_acme --output json
    """
    service = create_mssp_service()

    try:
        customer_obj = service.get_customer(mssp_id, customer_id)
    except MSSPNotFoundError as e:
        console.print(f"[red]Error:[/red] MSSP '{e.mssp_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)
    except CustomerNotFoundError as e:
        console.print(f"[red]Error:[/red] Customer '{e.customer_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)

    siem_config = customer_obj.siem_config

    if siem_config is None:
        if output == "json":
            console.print(json.dumps({"configured": False}))
        else:
            console.print(f"[yellow]No SIEM configured for {customer_id}[/yellow]")
            console.print()
            console.print("Configure with:")
            console.print(
                f"  raxe customer siem configure --mssp {mssp_id} {customer_id} --type splunk ..."
            )
        return

    if output == "json":
        data = {
            "configured": True,
            "type": siem_config.siem_type.value,
            "endpoint_url": siem_config.endpoint_url,
            "enabled": siem_config.enabled,
            "batch_size": siem_config.batch_size,
            "flush_interval_seconds": siem_config.flush_interval_seconds,
            "extra": siem_config.extra,
        }
        console.print(json.dumps(data, indent=2))
    else:
        console.print()
        console.print(f"[bold]SIEM Configuration for {customer_id}[/bold]")
        console.print()
        console.print(f"  Type: [cyan]{siem_config.siem_type.value}[/cyan]")
        console.print(f"  Endpoint: {siem_config.endpoint_url}")
        console.print(f"  Enabled: {'Yes' if siem_config.enabled else 'No'}")
        console.print(f"  Batch Size: {siem_config.batch_size}")
        console.print(f"  Flush Interval: {siem_config.flush_interval_seconds}s")
        if siem_config.extra:
            console.print("  Extra Config:")
            for k, v in siem_config.extra.items():
                console.print(f"    {k}: {v}")
        console.print()


@customer_siem.command("test")
@click.option(
    "--mssp",
    "mssp_id",
    required=True,
    help="Parent MSSP identifier",
)
@click.argument("customer_id")
def test_siem(mssp_id: str, customer_id: str):
    """Test SIEM connectivity for a customer.

    Performs a health check on the configured SIEM endpoint.

    \b
    Examples:
        raxe customer siem test --mssp mssp_yourcompany cust_acme
    """
    service = create_mssp_service()

    try:
        customer_obj = service.get_customer(mssp_id, customer_id)
    except MSSPNotFoundError as e:
        console.print(f"[red]Error:[/red] MSSP '{e.mssp_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)
    except CustomerNotFoundError as e:
        console.print(f"[red]Error:[/red] Customer '{e.customer_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)

    siem_config = customer_obj.siem_config
    if siem_config is None:
        console.print(f"[yellow]No SIEM configured for {customer_id}[/yellow]")
        sys.exit(EXIT_CONFIG_ERROR)

    from raxe.infrastructure.siem import create_siem_adapter

    console.print(f"Testing {siem_config.siem_type.value} connectivity...")

    try:
        adapter = create_siem_adapter(siem_config)
        is_healthy = adapter.health_check()
        adapter.close()

        if is_healthy:
            display_success("SIEM endpoint is reachable")
            console.print(f"  Endpoint: {siem_config.endpoint_url}")
        else:
            console.print("[red]✗[/red] SIEM endpoint health check failed")
            console.print(f"  Endpoint: {siem_config.endpoint_url}")
            sys.exit(EXIT_SCAN_ERROR)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(EXIT_SCAN_ERROR)


@customer_siem.command("disable")
@click.option(
    "--mssp",
    "mssp_id",
    required=True,
    help="Parent MSSP identifier",
)
@click.argument("customer_id")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
def disable_siem(mssp_id: str, customer_id: str, force: bool):
    """Disable SIEM integration for a customer.

    Removes the SIEM configuration from the customer.

    \b
    Examples:
        raxe customer siem disable --mssp mssp_yourcompany cust_acme --force
    """
    from dataclasses import replace

    service = create_mssp_service()

    try:
        customer_obj = service.get_customer(mssp_id, customer_id)
    except MSSPNotFoundError as e:
        console.print(f"[red]Error:[/red] MSSP '{e.mssp_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)
    except CustomerNotFoundError as e:
        console.print(f"[red]Error:[/red] Customer '{e.customer_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)

    if customer_obj.siem_config is None:
        console.print(f"[yellow]No SIEM configured for {customer_id}[/yellow]")
        return

    if not force:
        siem_type = customer_obj.siem_config.siem_type.value
        console.print(f"[yellow]Warning:[/yellow] This will remove {siem_type} SIEM configuration.")
        if not click.confirm("Are you sure?"):
            console.print("[dim]Aborted[/dim]")
            return

    from raxe.infrastructure.config.yaml_config import get_config_path
    from raxe.infrastructure.mssp.yaml_repository import YamlCustomerRepository

    base_path = get_config_path() / "mssp"
    repo = YamlCustomerRepository(base_path, mssp_id)

    updated_customer = replace(customer_obj, siem_config=None)
    repo.update(updated_customer)

    display_success(f"Disabled SIEM for customer '{customer_id}'")


# Export the group
__all__ = ["customer"]
