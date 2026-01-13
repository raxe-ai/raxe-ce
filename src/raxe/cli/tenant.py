"""CLI commands for managing tenants.

Commands:
- raxe tenant create --name <name> [--id <id>] [--policy <policy>]
- raxe tenant list [--output json|table]
- raxe tenant show <id> [--output json|table]
- raxe tenant delete <id> [--force]
- raxe tenant set-policy <id> <policy>
"""

import json
import sys

import click
from rich.console import Console
from rich.table import Table

from raxe.domain.tenants.presets import GLOBAL_PRESETS
from raxe.infrastructure.tenants import (
    YamlPolicyRepository,
    YamlTenantRepository,
    get_tenants_base_path,
)

console = Console()


def _slugify(name: str) -> str:
    """Convert a name to a URL-safe slug.

    Args:
        name: Human-readable name

    Returns:
        Lowercase slug with hyphens
    """
    import re

    # Convert to lowercase, replace spaces/underscores with hyphens
    slug = name.lower().strip()
    slug = re.sub(r"[\s_]+", "-", slug)
    # Remove non-alphanumeric characters except hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Remove consecutive hyphens
    slug = re.sub(r"-+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    return slug or "tenant"


@click.group()
def tenant():
    """Manage tenants for multi-tenant policy isolation."""
    pass


@tenant.command("create")
@click.option(
    "--name",
    "-n",
    required=True,
    help="Human-readable tenant name (e.g., 'Acme Corp')",
)
@click.option(
    "--id",
    "tenant_id",
    help="Tenant identifier (auto-generated from name if not provided)",
)
@click.option(
    "--policy",
    "-p",
    type=click.Choice(["monitor", "balanced", "strict"]),
    default="balanced",
    help="Default policy mode (default: balanced)",
)
def create_tenant(name: str, tenant_id: str | None, policy: str):
    """Create a new tenant.

    Creates tenant configuration at ~/.raxe/tenants/<tenant_id>/

    \b
    Examples:
        raxe tenant create --name "Acme Corp"
        raxe tenant create --name "Bunny CDN" --id bunny --policy strict
    """
    from datetime import datetime, timezone

    from raxe.domain.tenants.models import Tenant

    # Generate ID if not provided
    if not tenant_id:
        tenant_id = _slugify(name)

    base_path = get_tenants_base_path()
    repo = YamlTenantRepository(base_path)

    # Check if tenant already exists
    existing = repo.get_tenant(tenant_id)
    if existing:
        console.print(f"[red]Error:[/red] Tenant '{tenant_id}' already exists")
        sys.exit(1)

    # Create tenant
    now = datetime.now(timezone.utc).isoformat()
    tenant_obj = Tenant(
        tenant_id=tenant_id,
        name=name,
        default_policy_id=policy,
        created_at=now,
    )

    # Save tenant
    repo.save_tenant(tenant_obj)

    console.print(f"[green]✓[/green] Created tenant '{name}'")
    console.print()
    console.print(f"  ID: [cyan]{tenant_id}[/cyan]")
    console.print(f"  Name: {name}")
    console.print(f"  Default Policy: [yellow]{policy}[/yellow]")
    console.print(f"  Path: {base_path / tenant_id}")
    console.print()


@tenant.command("list")
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
def list_tenants(output: str):
    """List all tenants.

    \b
    Examples:
        raxe tenant list
        raxe tenant list --output json
        raxe tenant list --format json
    """
    base_path = get_tenants_base_path()
    repo = YamlTenantRepository(base_path)

    tenants = repo.list_tenants()

    if not tenants:
        if output == "json":
            console.print("[]")
        else:
            console.print("[yellow]No tenants found[/yellow]")
            console.print()
            cmd = "raxe tenant create --name 'My Tenant'"
            console.print(f"Create a tenant with: [cyan]{cmd}[/cyan]")
        return

    if output == "json":
        data = [
            {
                "tenant_id": t.tenant_id,
                "name": t.name,
                "default_policy_id": t.default_policy_id,
                "tier": t.tier,
                "created_at": t.created_at,
            }
            for t in tenants
        ]
        console.print(json.dumps(data, indent=2))
    else:
        table = Table(title=f"Tenants ({len(tenants)})", show_header=True)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="white")
        table.add_column("Default Policy", style="yellow")
        table.add_column("Tier", style="dim")
        table.add_column("Created", style="dim", no_wrap=True)

        for t in sorted(tenants, key=lambda x: x.tenant_id):
            created = t.created_at[:10] if t.created_at else "Unknown"
            table.add_row(t.tenant_id, t.name, t.default_policy_id, t.tier, created)

        console.print(table)
        console.print()


@tenant.command("show")
@click.argument("tenant_id")
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
def show_tenant(tenant_id: str, output: str):
    """Show details of a specific tenant.

    \b
    Examples:
        raxe tenant show acme
        raxe tenant show acme --output json
        raxe tenant show acme --format json
    """
    base_path = get_tenants_base_path()
    repo = YamlTenantRepository(base_path)

    tenant_obj = repo.get_tenant(tenant_id)

    if not tenant_obj:
        console.print(f"[red]Error:[/red] Tenant '{tenant_id}' not found")
        sys.exit(1)

    if output == "json":
        data = {
            "tenant_id": tenant_obj.tenant_id,
            "name": tenant_obj.name,
            "default_policy_id": tenant_obj.default_policy_id,
            "tier": tenant_obj.tier,
            "partner_id": tenant_obj.partner_id,
            "created_at": tenant_obj.created_at,
        }
        console.print(json.dumps(data, indent=2))
    else:
        console.print()
        console.print("[bold]Tenant Details[/bold]")
        console.print()
        console.print(f"  ID: [cyan]{tenant_obj.tenant_id}[/cyan]")
        console.print(f"  Name: {tenant_obj.name}")
        console.print(f"  Default Policy: [yellow]{tenant_obj.default_policy_id}[/yellow]")
        console.print(f"  Tier: {tenant_obj.tier}")
        if tenant_obj.partner_id:
            console.print(f"  Partner: {tenant_obj.partner_id}")
        created = tenant_obj.created_at[:10] if tenant_obj.created_at else "Unknown"
        console.print(f"  Created: {created}")
        console.print(f"  Path: {base_path / tenant_id}")
        console.print()

        # Show available policies
        policy_repo = YamlPolicyRepository(base_path)
        policies = policy_repo.list_policies(tenant_id)

        if policies:
            console.print("[bold]Custom Policies:[/bold]")
            for p in policies:
                console.print(f"  - {p.policy_id}: {p.name} ({p.mode.value})")
            console.print()


@tenant.command("delete")
@click.argument("tenant_id")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
def delete_tenant(tenant_id: str, force: bool):
    """Delete a tenant and all its configuration.

    WARNING: This deletes all tenant policies, suppressions, and rules.

    \b
    Examples:
        raxe tenant delete acme --force
    """
    base_path = get_tenants_base_path()
    repo = YamlTenantRepository(base_path)

    # Check tenant exists
    tenant_obj = repo.get_tenant(tenant_id)
    if not tenant_obj:
        console.print(f"[red]Error:[/red] Tenant '{tenant_id}' not found")
        sys.exit(1)

    if not force:
        msg = f"This will delete tenant '{tenant_obj.name}' and all its data."
        console.print(f"[yellow]Warning:[/yellow] {msg}")
        if not click.confirm("Are you sure?"):
            console.print("[dim]Aborted[/dim]")
            sys.exit(1)

    # Delete tenant directory
    import shutil

    tenant_path = base_path / tenant_id
    if tenant_path.exists():
        shutil.rmtree(tenant_path)

    console.print(f"[green]✓[/green] Deleted tenant '{tenant_id}'")
    console.print()


@tenant.command("set-policy")
@click.argument("tenant_id")
@click.argument("policy", type=click.Choice(["monitor", "balanced", "strict"]))
def set_tenant_policy(tenant_id: str, policy: str):
    """Set the default policy for a tenant.

    \b
    Examples:
        raxe tenant set-policy acme strict
        raxe tenant set-policy bunny monitor
    """

    from raxe.domain.tenants.models import Tenant

    base_path = get_tenants_base_path()
    repo = YamlTenantRepository(base_path)

    # Get existing tenant
    tenant_obj = repo.get_tenant(tenant_id)
    if not tenant_obj:
        console.print(f"[red]Error:[/red] Tenant '{tenant_id}' not found")
        sys.exit(1)

    # Validate policy exists
    if policy not in GLOBAL_PRESETS:
        console.print(f"[red]Error:[/red] Invalid policy '{policy}'")
        console.print(f"Valid policies: {', '.join(GLOBAL_PRESETS.keys())}")
        sys.exit(1)

    old_policy = tenant_obj.default_policy_id

    # Create updated tenant (frozen dataclass, must recreate)
    updated_tenant = Tenant(
        tenant_id=tenant_obj.tenant_id,
        name=tenant_obj.name,
        default_policy_id=policy,
        partner_id=tenant_obj.partner_id,
        tier=tenant_obj.tier,
        created_at=tenant_obj.created_at,
    )

    # Save updated tenant
    repo.save_tenant(updated_tenant)

    console.print(f"[green]✓[/green] Updated default policy for '{tenant_id}'")
    console.print()
    console.print(f"  Old policy: [dim]{old_policy}[/dim]")
    console.print(f"  New policy: [yellow]{policy}[/yellow]")
    console.print()


# Export the group
__all__ = ["tenant"]
