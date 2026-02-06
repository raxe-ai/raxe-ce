"""CLI commands for managing policies.

Commands:
- raxe policy presets [--output json|table]
- raxe policy list [--tenant <id>] [--output json|table]
- raxe policy show <policy_id> [--tenant <id>] [--output json|table]
- raxe policy create --tenant <id> --mode <mode> --name <name> [--id <id>] [--threshold-opts]
- raxe policy update <policy_id> --tenant <id> [--name] [--threshold-opts]
- raxe policy delete <policy_id> --tenant <id> [--force]
- raxe policy explain --tenant <id> [--app <id>] [--policy <id>] [--output json|table]

Policy Modes:
- monitor: Log-only, no blocking (observe threats, build baseline)
- balanced: Block HIGH/CRITICAL threats with high confidence (default)
- strict: Block all threats from MEDIUM and above
- custom: Full customization of all settings (use --threshold-opts)
"""

import json
import sys

import click
from rich.table import Table

from raxe.application import (
    AppNotFoundError,
    CreatePolicyRequest,
    DuplicateEntityError,
    ImmutablePresetError,
    PolicyNotFoundError,
    TenantNotFoundError,
    UpdatePolicyRequest,
    create_tenant_service,
)
from raxe.cli.exit_codes import EXIT_CONFIG_ERROR, EXIT_INVALID_INPUT
from raxe.cli.output import console
from raxe.domain.tenants.models import TenantPolicy
from raxe.domain.tenants.presets import GLOBAL_PRESETS


def _policy_to_dict(p: TenantPolicy) -> dict:
    """Convert TenantPolicy to dictionary for JSON output."""
    return {
        "policy_id": p.policy_id,
        "name": p.name,
        "tenant_id": p.tenant_id,
        "mode": p.mode.value,
        "blocking_enabled": p.blocking_enabled,
        "block_severity_threshold": p.block_severity_threshold,
        "block_confidence_threshold": p.block_confidence_threshold,
        "l2_enabled": p.l2_enabled,
        "l2_threat_threshold": p.l2_threat_threshold,
        "telemetry_detail": p.telemetry_detail,
        "version": p.version,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


@click.group()
def policy():
    """Manage policies for multi-tenant threat detection."""
    pass


@policy.command("presets")
@click.option(
    "--output",
    "--format",
    "-o",
    "-f",
    "output",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table). Both --output and --format work.",
)
def list_presets(output: str):
    """List global policy presets (monitor, balanced, strict).

    \\b
    Examples:
        raxe policy presets
        raxe policy presets --output json
        raxe policy presets --format json
    """
    presets = list(GLOBAL_PRESETS.values())

    if output == "json":
        data = [_policy_to_dict(p) for p in presets]
        console.print(json.dumps(data, indent=2))
    else:
        table = Table(title="Global Policy Presets", show_header=True)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="white")
        table.add_column("Mode", style="yellow")
        table.add_column("Blocking", style="green")
        table.add_column("Severity Threshold", style="dim")

        for p in sorted(presets, key=lambda x: x.policy_id):
            blocking = "[green]Yes[/green]" if p.blocking_enabled else "[yellow]No[/yellow]"
            table.add_row(
                p.policy_id,
                p.name,
                p.mode.value,
                blocking,
                p.block_severity_threshold,
            )

        console.print(table)
        console.print()
        console.print("[dim]Use these presets with: raxe tenant create --policy <preset>[/dim]")
        console.print()


@policy.command("list")
@click.option(
    "--tenant",
    "-t",
    "tenant_id",
    help="Tenant ID (lists custom policies for tenant, or presets if not specified)",
)
@click.option(
    "--output",
    "--format",
    "-o",
    "-f",
    "output",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table). Both --output and --format work.",
)
def list_policies(tenant_id: str | None, output: str):
    """List policies for a tenant or global presets.

    \\b
    Examples:
        raxe policy list                    # Shows global presets
        raxe policy list --tenant acme      # Shows tenant's custom policies
        raxe policy list --tenant acme --output json
        raxe policy list --tenant acme --format json
    """
    if tenant_id is None:
        # Show global presets
        presets = list(GLOBAL_PRESETS.values())
        if output == "json":
            data = [_policy_to_dict(p) for p in presets]
            console.print(json.dumps(data, indent=2))
        else:
            table = Table(title="Global Policy Presets", show_header=True)
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Name", style="white")
            table.add_column("Mode", style="yellow")
            table.add_column("Blocking", style="green")

            for p in sorted(presets, key=lambda x: x.policy_id):
                blocking = "Yes" if p.blocking_enabled else "No"
                table.add_row(p.policy_id, p.name, p.mode.value, blocking)

            console.print(table)
            console.print()
            console.print("[dim]Tip: Use --tenant <id> to list tenant-specific policies[/dim]")
            console.print()
        return

    # Show tenant-specific policies
    service = create_tenant_service()

    try:
        tenant = service.get_tenant(tenant_id)
    except TenantNotFoundError:
        console.print(f"[red]Error:[/red] Tenant '{tenant_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)

    policies = service.list_policies(tenant_id)

    # Combine global presets with custom policies
    all_policies = list(GLOBAL_PRESETS.values()) + policies

    if output == "json":
        data = [_policy_to_dict(p) for p in all_policies]
        console.print(json.dumps(data, indent=2))
    else:
        # Show available policies (presets + custom)
        table = Table(title=f"Available Policies for {tenant_id}", show_header=True)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="white")
        table.add_column("Mode", style="yellow")
        table.add_column("Blocking", style="green")
        table.add_column("Type", style="dim")
        table.add_column("Default", style="magenta")

        # Show global presets first
        for p in sorted(GLOBAL_PRESETS.values(), key=lambda x: x.policy_id):
            blocking = "[green]Yes[/green]" if p.blocking_enabled else "[yellow]No[/yellow]"
            is_default = "✓" if p.policy_id == tenant.default_policy_id else ""
            table.add_row(
                p.policy_id,
                p.name,
                p.mode.value,
                blocking,
                "[dim]preset[/dim]",
                f"[magenta]{is_default}[/magenta]",
            )

        # Then custom policies
        for p in sorted(policies, key=lambda x: x.policy_id):
            blocking = "[green]Yes[/green]" if p.blocking_enabled else "[yellow]No[/yellow]"
            is_default = "✓" if p.policy_id == tenant.default_policy_id else ""
            table.add_row(
                p.policy_id,
                p.name,
                p.mode.value,
                blocking,
                "[cyan]custom[/cyan]",
                f"[magenta]{is_default}[/magenta]",
            )

        console.print(table)
        console.print()
        if not policies:
            console.print("[dim]Create custom policies with: raxe policy create --tenant ...[/dim]")
            console.print()


@policy.command("show")
@click.argument("policy_id")
@click.option(
    "--tenant",
    "-t",
    "tenant_id",
    help="Tenant ID (for tenant-specific policies)",
)
@click.option(
    "--output",
    "--format",
    "-o",
    "-f",
    "output",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table). Both --output and --format work.",
)
def show_policy(policy_id: str, tenant_id: str | None, output: str):
    """Show details of a specific policy.

    \\b
    Examples:
        raxe policy show balanced           # Show global preset
        raxe policy show my-policy --tenant acme
        raxe policy show strict --output json
        raxe policy show strict --format json
    """
    service = create_tenant_service()

    try:
        policy_obj = service.get_policy(policy_id, tenant_id)
    except PolicyNotFoundError:
        console.print(f"[red]Error:[/red] Policy '{policy_id}' not found")
        if not tenant_id:
            console.print("[dim]Tip: Use --tenant <id> for tenant-specific policies[/dim]")
        sys.exit(EXIT_CONFIG_ERROR)

    if output == "json":
        console.print(json.dumps(_policy_to_dict(policy_obj), indent=2))
    else:
        console.print()
        console.print("[bold]Policy Details[/bold]")
        console.print()
        console.print(f"  ID: [cyan]{policy_obj.policy_id}[/cyan]")
        console.print(f"  Name: {policy_obj.name}")
        console.print(f"  Mode: [yellow]{policy_obj.mode.value}[/yellow]")
        if policy_obj.tenant_id:
            console.print(f"  Tenant: {policy_obj.tenant_id}")
        else:
            console.print("  Tenant: [dim]Global Preset[/dim]")
        console.print()
        console.print("[bold]Blocking Configuration[/bold]")
        console.print()
        if policy_obj.blocking_enabled:
            blocking = "[green]Enabled[/green]"
        else:
            blocking = "[yellow]Disabled[/yellow]"
        console.print(f"  Blocking: {blocking}")
        console.print(f"  Severity Threshold: {policy_obj.block_severity_threshold}")
        console.print(f"  Confidence Threshold: {policy_obj.block_confidence_threshold}")
        console.print()
        console.print("[bold]L2 ML Detection[/bold]")
        console.print()
        l2 = "[green]Enabled[/green]" if policy_obj.l2_enabled else "[yellow]Disabled[/yellow]"
        console.print(f"  L2 Detection: {l2}")
        console.print(f"  Threat Threshold: {policy_obj.l2_threat_threshold}")
        console.print()
        console.print("[bold]Telemetry[/bold]")
        console.print()
        console.print(f"  Detail Level: {policy_obj.telemetry_detail}")
        console.print()
        console.print("[bold]Version Info[/bold]")
        console.print()
        console.print(f"  Version: {policy_obj.version}")
        if policy_obj.created_at:
            console.print(f"  Created: {policy_obj.created_at[:19]}")
        if policy_obj.updated_at:
            console.print(f"  Updated: {policy_obj.updated_at[:19]}")
        console.print()


@policy.command("create")
@click.option(
    "--tenant",
    "-t",
    "tenant_id",
    required=True,
    help="Tenant ID (required)",
)
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["monitor", "balanced", "strict", "custom"]),
    required=True,
    help="Policy mode (use 'custom' for full control over thresholds)",
)
@click.option(
    "--name",
    "-n",
    required=True,
    help="Human-readable policy name",
)
@click.option(
    "--id",
    "policy_id",
    help="Policy identifier (auto-generated from name if not provided)",
)
@click.option(
    "--blocking/--no-blocking",
    "blocking_enabled",
    default=None,
    help="Enable or disable blocking (custom mode only)",
)
@click.option(
    "--severity-threshold",
    type=click.Choice(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]),
    help="Block severity threshold (custom mode only)",
)
@click.option(
    "--confidence-threshold",
    type=click.FloatRange(0.0, 1.0),
    help="Block confidence threshold 0.0-1.0 (custom mode only)",
)
@click.option(
    "--l2/--no-l2",
    "l2_enabled",
    default=None,
    help="Enable or disable L2 ML detection (custom mode only)",
)
@click.option(
    "--l2-threshold",
    type=click.FloatRange(0.0, 1.0),
    help="L2 threat threshold 0.0-1.0 (custom mode only)",
)
@click.option(
    "--telemetry",
    type=click.Choice(["minimal", "standard", "verbose"]),
    help="Telemetry detail level (custom mode only)",
)
def create_policy(
    tenant_id: str,
    mode: str,
    name: str,
    policy_id: str | None,
    blocking_enabled: bool | None,
    severity_threshold: str | None,
    confidence_threshold: float | None,
    l2_enabled: bool | None,
    l2_threshold: float | None,
    telemetry: str | None,
):
    """Create a custom policy for a tenant.

    Use --mode custom for full control over all thresholds.

    \\b
    Examples:
        # Create policy based on preset
        raxe policy create --tenant acme --mode strict --name "High Security"

        # Create fully custom policy
        raxe policy create --tenant acme --mode custom --name "Custom Policy" \\
            --blocking --severity-threshold MEDIUM --confidence-threshold 0.7 \\
            --l2 --l2-threshold 0.4 --telemetry verbose
    """
    service = create_tenant_service()

    # Warn if threshold options provided for non-custom mode
    if mode != "custom":
        custom_options = [
            blocking_enabled is not None,
            severity_threshold is not None,
            confidence_threshold is not None,
            l2_enabled is not None,
            l2_threshold is not None,
            telemetry is not None,
        ]
        if any(custom_options):
            console.print(
                "[yellow]Warning:[/yellow] Threshold options are ignored for preset modes. "
                "Use --mode custom for full control."
            )

    # Build request
    request = CreatePolicyRequest(
        tenant_id=tenant_id,
        name=name,
        mode=mode,
        policy_id=policy_id,
        blocking_enabled=blocking_enabled,
        block_severity_threshold=severity_threshold,
        block_confidence_threshold=confidence_threshold,
        l2_enabled=l2_enabled,
        l2_threat_threshold=l2_threshold,
        telemetry_detail=telemetry,
    )

    try:
        policy_obj = service.create_policy(request)
    except TenantNotFoundError:
        console.print(f"[red]Error:[/red] Tenant '{tenant_id}' not found")
        console.print()
        console.print("Create a tenant first with:")
        console.print(f"  [cyan]raxe tenant create --name 'My Tenant' --id {tenant_id}[/cyan]")
        sys.exit(EXIT_CONFIG_ERROR)
    except DuplicateEntityError as e:
        console.print(
            f"[red]Error:[/red] Policy '{e.entity_id}' already exists for tenant '{tenant_id}'"
        )
        sys.exit(EXIT_INVALID_INPUT)

    console.print(f"[green]✓[/green] Created policy '{policy_obj.name}'")
    console.print()
    console.print(f"  ID: [cyan]{policy_obj.policy_id}[/cyan]")
    console.print(f"  Tenant: {policy_obj.tenant_id}")
    console.print(f"  Mode: [yellow]{policy_obj.mode.value}[/yellow]")
    console.print(f"  Version: {policy_obj.version}")
    if policy_obj.blocking_enabled:
        blocking = "[green]Enabled[/green]"
    else:
        blocking = "[yellow]Disabled[/yellow]"
    console.print(f"  Blocking: {blocking}")
    if policy_obj.mode.value == "custom":
        console.print(f"  Severity Threshold: {policy_obj.block_severity_threshold}")
        console.print(f"  Confidence Threshold: {policy_obj.block_confidence_threshold}")
        console.print(f"  L2 Detection: {'Enabled' if policy_obj.l2_enabled else 'Disabled'}")
        console.print(f"  L2 Threshold: {policy_obj.l2_threat_threshold}")
        console.print(f"  Telemetry: {policy_obj.telemetry_detail}")
    console.print()
    console.print("To use this policy:")
    tenant = policy_obj.tenant_id
    pol_id = policy_obj.policy_id
    console.print(f"  [cyan]raxe.scan(text, tenant_id='{tenant}', policy_id='{pol_id}')[/cyan]")
    console.print()


@policy.command("delete")
@click.argument("policy_id")
@click.option(
    "--tenant",
    "-t",
    "tenant_id",
    required=True,
    help="Tenant ID (required)",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
def delete_policy(policy_id: str, tenant_id: str, force: bool):
    """Delete a custom policy from a tenant.

    NOTE: Global presets (monitor, balanced, strict) cannot be deleted.

    \\b
    Examples:
        raxe policy delete my-policy --tenant acme --force
    """
    service = create_tenant_service()

    # Get policy first for confirmation prompt (also validates it exists)
    try:
        policy_obj = service.get_policy(policy_id, tenant_id)
    except PolicyNotFoundError:
        # Check if it's a global preset
        if policy_id in GLOBAL_PRESETS:
            console.print(f"[red]Error:[/red] Cannot delete global preset '{policy_id}'")
            console.print("[dim]Global presets are immutable system policies[/dim]")
        else:
            console.print(
                f"[red]Error:[/red] Policy '{policy_id}' not found for tenant '{tenant_id}'"
            )
        sys.exit(EXIT_CONFIG_ERROR)

    if not force:
        msg = f"This will delete policy '{policy_obj.name}' ({policy_id})."
        console.print(f"[yellow]Warning:[/yellow] {msg}")
        if not click.confirm("Are you sure?"):
            console.print("[dim]Aborted[/dim]")
            return

    try:
        service.delete_policy(policy_id, tenant_id)
    except ImmutablePresetError:
        console.print(f"[red]Error:[/red] Cannot delete global preset '{policy_id}'")
        console.print("[dim]Global presets are immutable system policies[/dim]")
        sys.exit(EXIT_INVALID_INPUT)
    except TenantNotFoundError:
        console.print(f"[red]Error:[/red] Tenant '{tenant_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)
    except PolicyNotFoundError:
        console.print(f"[red]Error:[/red] Policy '{policy_id}' not found for tenant '{tenant_id}'")
        sys.exit(EXIT_CONFIG_ERROR)

    console.print(f"[green]✓[/green] Deleted policy '{policy_id}'")
    console.print()


@policy.command("update")
@click.argument("policy_id")
@click.option(
    "--tenant",
    "-t",
    "tenant_id",
    required=True,
    help="Tenant ID (required)",
)
@click.option(
    "--name",
    "-n",
    help="New policy name",
)
@click.option(
    "--blocking/--no-blocking",
    "blocking_enabled",
    default=None,
    help="Enable or disable blocking",
)
@click.option(
    "--severity-threshold",
    type=click.Choice(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]),
    help="Block severity threshold",
)
@click.option(
    "--confidence-threshold",
    type=click.FloatRange(0.0, 1.0),
    help="Block confidence threshold 0.0-1.0",
)
@click.option(
    "--l2/--no-l2",
    "l2_enabled",
    default=None,
    help="Enable or disable L2 ML detection",
)
@click.option(
    "--l2-threshold",
    type=click.FloatRange(0.0, 1.0),
    help="L2 threat threshold 0.0-1.0",
)
@click.option(
    "--telemetry",
    type=click.Choice(["minimal", "standard", "verbose"]),
    help="Telemetry detail level",
)
def update_policy(
    policy_id: str,
    tenant_id: str,
    name: str | None,
    blocking_enabled: bool | None,
    severity_threshold: str | None,
    confidence_threshold: float | None,
    l2_enabled: bool | None,
    l2_threshold: float | None,
    telemetry: str | None,
):
    """Update an existing custom policy.

    NOTE: Global presets (monitor, balanced, strict) cannot be updated.
    Updates increment the policy version automatically.

    \\b
    Examples:
        raxe policy update my-policy --tenant acme --severity-threshold MEDIUM
        raxe policy update my-policy --tenant acme --no-blocking
        raxe policy update my-policy --tenant acme --name "New Name" --l2-threshold 0.5
    """
    service = create_tenant_service()

    # Check if any updates provided
    updates = [
        name is not None,
        blocking_enabled is not None,
        severity_threshold is not None,
        confidence_threshold is not None,
        l2_enabled is not None,
        l2_threshold is not None,
        telemetry is not None,
    ]
    if not any(updates):
        console.print("[yellow]Warning:[/yellow] No updates specified")
        console.print("[dim]Use --help to see available options[/dim]")
        sys.exit(EXIT_INVALID_INPUT)

    # Get existing policy for displaying change summary
    try:
        existing = service.get_policy(policy_id, tenant_id)
    except PolicyNotFoundError:
        # Check if it's a global preset
        if policy_id in GLOBAL_PRESETS:
            console.print(f"[red]Error:[/red] Cannot update global preset '{policy_id}'")
            console.print("[dim]Global presets are immutable. Create a custom policy:[/dim]")
            cmd = f"raxe policy create --tenant {tenant_id} --mode {policy_id} --name 'My Custom'"
            console.print(f"  [cyan]{cmd}[/cyan]")
        else:
            console.print(
                f"[red]Error:[/red] Policy '{policy_id}' not found for tenant '{tenant_id}'"
            )
        sys.exit(EXIT_CONFIG_ERROR)

    # Build update request
    request = UpdatePolicyRequest(
        policy_id=policy_id,
        tenant_id=tenant_id,
        name=name,
        blocking_enabled=blocking_enabled,
        block_severity_threshold=severity_threshold,
        block_confidence_threshold=confidence_threshold,
        l2_enabled=l2_enabled,
        l2_threat_threshold=l2_threshold,
        telemetry_detail=telemetry,
    )

    try:
        updated_policy = service.update_policy(request)
    except ImmutablePresetError:
        console.print(f"[red]Error:[/red] Cannot update global preset '{policy_id}'")
        console.print("[dim]Global presets are immutable. Create a custom policy instead:[/dim]")
        cmd = f"raxe policy create --tenant {tenant_id} --mode {policy_id} --name 'My Custom'"
        console.print(f"  [cyan]{cmd}[/cyan]")
        sys.exit(EXIT_INVALID_INPUT)
    except TenantNotFoundError:
        console.print(f"[red]Error:[/red] Tenant '{tenant_id}' not found")
        sys.exit(EXIT_CONFIG_ERROR)
    except PolicyNotFoundError:
        console.print(f"[red]Error:[/red] Policy '{policy_id}' not found for tenant '{tenant_id}'")
        sys.exit(EXIT_CONFIG_ERROR)

    console.print(f"[green]✓[/green] Updated policy '{policy_id}'")
    console.print()
    console.print(f"  Version: {existing.version} → [cyan]{updated_policy.version}[/cyan]")
    if name is not None:
        console.print(f"  Name: {existing.name} → [cyan]{updated_policy.name}[/cyan]")
    if updated_policy.mode != existing.mode:
        old_mode = existing.mode.value
        new_mode = updated_policy.mode.value
        console.print(f"  Mode: {old_mode} → [yellow]{new_mode}[/yellow]")
    if blocking_enabled is not None:
        old_blocking = "enabled" if existing.blocking_enabled else "disabled"
        new_blocking_str = "enabled" if updated_policy.blocking_enabled else "disabled"
        console.print(f"  Blocking: {old_blocking} → [cyan]{new_blocking_str}[/cyan]")
    if severity_threshold is not None:
        old_sev = existing.block_severity_threshold
        new_sev = updated_policy.block_severity_threshold
        console.print(f"  Severity Threshold: {old_sev} → [cyan]{new_sev}[/cyan]")
    if confidence_threshold is not None:
        old_conf = existing.block_confidence_threshold
        new_conf = updated_policy.block_confidence_threshold
        console.print(f"  Confidence Threshold: {old_conf} → [cyan]{new_conf}[/cyan]")
    if l2_enabled is not None:
        old_l2 = "enabled" if existing.l2_enabled else "disabled"
        new_l2_str = "enabled" if updated_policy.l2_enabled else "disabled"
        console.print(f"  L2 Detection: {old_l2} → [cyan]{new_l2_str}[/cyan]")
    if l2_threshold is not None:
        old_l2_thresh = existing.l2_threat_threshold
        new_l2_thresh = updated_policy.l2_threat_threshold
        console.print(f"  L2 Threshold: {old_l2_thresh} → [cyan]{new_l2_thresh}[/cyan]")
    if telemetry is not None:
        old_telem = existing.telemetry_detail
        new_telem = updated_policy.telemetry_detail
        console.print(f"  Telemetry: {old_telem} → [cyan]{new_telem}[/cyan]")
    console.print()


@policy.command("explain")
@click.option(
    "--tenant",
    "-t",
    "tenant_id",
    required=True,
    help="Tenant ID to explain policy for",
)
@click.option(
    "--app",
    "-a",
    "app_id",
    help="App ID (optional, shows app-level override)",
)
@click.option(
    "--policy",
    "-p",
    "policy_id",
    help="Policy ID override (simulates request-time override)",
)
@click.option(
    "--output",
    "--format",
    "-o",
    "-f",
    "output",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table). Both --output and --format work.",
)
def explain_policy(tenant_id: str, app_id: str | None, policy_id: str | None, output: str):
    """Explain which policy would be used for a given context.

    Shows the policy resolution path without performing a scan.
    Useful for debugging and understanding policy inheritance.

    \\b
    Examples:
        raxe policy explain --tenant acme
        raxe policy explain --tenant acme --app chatbot
        raxe policy explain --tenant acme --policy strict
    """
    service = create_tenant_service()

    try:
        resolution = service.explain_policy(
            tenant_id=tenant_id,
            app_id=app_id,
            policy_id=policy_id,
        )
    except TenantNotFoundError:
        console.print(f"[red]Error:[/red] Tenant '{tenant_id}' not found")
        console.print()
        console.print("Create a tenant first with:")
        console.print(f"  [cyan]raxe tenant create --name 'My Tenant' --id {tenant_id}[/cyan]")
        sys.exit(EXIT_CONFIG_ERROR)
    except AppNotFoundError:
        console.print(f"[red]Error:[/red] App '{app_id}' not found in tenant '{tenant_id}'")
        sys.exit(EXIT_CONFIG_ERROR)

    if output == "json":
        data = {
            "effective_policy_id": resolution.policy.policy_id,
            "effective_policy_mode": resolution.policy.mode.value,
            "resolution_source": resolution.resolution_source,
            "resolution_path": resolution.resolution_path,
            "blocking_enabled": resolution.policy.blocking_enabled,
            "block_severity_threshold": resolution.policy.block_severity_threshold,
            "block_confidence_threshold": resolution.policy.block_confidence_threshold,
        }
        console.print(json.dumps(data, indent=2))
    else:
        console.print()
        console.print("[bold]Policy Resolution Explanation[/bold]")
        console.print()

        # Context
        console.print("[bold]Context[/bold]")
        console.print()
        console.print(f"  Tenant: [cyan]{tenant_id}[/cyan]")
        if app_id:
            console.print(f"  App: [cyan]{app_id}[/cyan]")
        else:
            console.print("  App: [dim](not specified)[/dim]")
        if policy_id:
            console.print(f"  Policy Override: [yellow]{policy_id}[/yellow]")
        else:
            console.print("  Policy Override: [dim](none)[/dim]")
        console.print()

        # Resolution
        console.print("[bold]Resolution[/bold]")
        console.print()
        console.print(f"  Effective Policy: [green]{resolution.policy.policy_id}[/green]")
        console.print(f"  Mode: [yellow]{resolution.policy.mode.value}[/yellow]")
        console.print(f"  Source: {resolution.resolution_source}")
        console.print()

        # Resolution path
        console.print("[bold]Resolution Path[/bold]")
        console.print()
        for step in resolution.resolution_path:
            parts = step.split(":", 1)
            level = parts[0]
            value = parts[1] if len(parts) > 1 else ""

            if value == "None" or value == "":
                console.print(f"  • {level}: [dim](none specified)[/dim]")
            elif level == "request":
                console.print(f"  • {level}: [yellow]{value}[/yellow]")
            elif level == "app":
                console.print(f"  • {level}: [cyan]{value}[/cyan]")
            elif level == "tenant":
                console.print(f"  • {level}: [cyan]{value}[/cyan]")
            elif level == "system":
                console.print(f"  • system_default: [green]{value}[/green]")
            else:
                console.print(f"  • {step}")
        console.print()

        # Policy details
        console.print("[bold]Policy Details[/bold]")
        console.print()
        if resolution.policy.blocking_enabled:
            blocking = "[green]Enabled[/green]"
        else:
            blocking = "[yellow]Disabled (monitor mode)[/yellow]"
        console.print(f"  Blocking: {blocking}")
        sev_thresh = resolution.policy.block_severity_threshold
        conf_thresh = resolution.policy.block_confidence_threshold
        console.print(f"  Block Severity Threshold: {sev_thresh}")
        console.print(f"  Block Confidence Threshold: {conf_thresh}")
        console.print()


# Export the group
__all__ = ["policy"]
