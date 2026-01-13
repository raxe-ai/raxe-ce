"""CLI commands for managing apps within tenants.

Commands:
- raxe app create --tenant <tenant_id> --name <name> [--id <id>] [--policy <policy>]
- raxe app list --tenant <tenant_id> [--output json|table]
- raxe app show <app_id> --tenant <tenant_id> [--output json|table]
- raxe app delete <app_id> --tenant <tenant_id> [--force]
- raxe app set-policy <app_id> <policy> --tenant <tenant_id>
"""

import json
import sys

import click
from rich.console import Console
from rich.table import Table

from raxe.domain.tenants.presets import GLOBAL_PRESETS
from raxe.infrastructure.tenants import (
    YamlAppRepository,
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
    return slug or "app"


def _verify_tenant_exists(tenant_id: str) -> bool:
    """Verify that a tenant exists.

    Args:
        tenant_id: Tenant identifier to check

    Returns:
        True if tenant exists, False otherwise
    """
    base_path = get_tenants_base_path()
    repo = YamlTenantRepository(base_path)
    return repo.get_tenant(tenant_id) is not None


def _get_available_policies(tenant_id: str) -> list[str]:
    """Get list of available policy IDs for a tenant.

    Returns global presets plus tenant-specific custom policies.

    Args:
        tenant_id: Tenant to get policies for

    Returns:
        List of policy IDs
    """
    # Start with global presets
    policies = list(GLOBAL_PRESETS.keys())

    # Add tenant-specific policies
    base_path = get_tenants_base_path()
    policy_repo = YamlPolicyRepository(base_path)
    tenant_policies = policy_repo.list_policies(tenant_id=tenant_id)
    for p in tenant_policies:
        if p.policy_id not in policies:
            policies.append(p.policy_id)

    return policies


@click.group()
def app():
    """Manage apps within tenants for app-level policy override."""
    pass


@app.command("create")
@click.option(
    "--tenant",
    "-t",
    "tenant_id",
    required=True,
    help="Tenant ID that owns this app",
)
@click.option(
    "--name",
    "-n",
    required=True,
    help="Human-readable app name (e.g., 'Customer Support Bot')",
)
@click.option(
    "--id",
    "app_id",
    help="App identifier (auto-generated from name if not provided)",
)
@click.option(
    "--policy",
    "-p",
    help="Default policy ID for this app (overrides tenant default)",
)
def create_app(tenant_id: str, name: str, app_id: str | None, policy: str | None):
    """Create a new app within a tenant.

    Apps allow app-level policy overrides within a tenant.

    \\b
    Examples:
        raxe app create --tenant acme --name "Customer Support Bot"
        raxe app create --tenant acme --name "Trading System" --policy strict
    """
    from datetime import datetime, timezone

    from raxe.domain.tenants.models import App

    # Verify tenant exists
    if not _verify_tenant_exists(tenant_id):
        console.print(f"[red]Error:[/red] Tenant '{tenant_id}' not found")
        sys.exit(1)

    # Generate app_id if not provided
    if not app_id:
        app_id = _slugify(name)

    base_path = get_tenants_base_path()
    repo = YamlAppRepository(base_path)

    # Check if app already exists
    existing = repo.get_app(app_id, tenant_id)
    if existing:
        console.print(f"[red]Error:[/red] App '{app_id}' already exists in tenant '{tenant_id}'")
        sys.exit(1)

    # Validate policy if provided
    if policy:
        available_policies = _get_available_policies(tenant_id)
        if policy not in available_policies:
            console.print(f"[red]Error:[/red] Invalid policy '{policy}'")
            console.print(f"Valid policies: {', '.join(available_policies)}")
            sys.exit(1)

    # Create app
    now = datetime.now(timezone.utc).isoformat()
    app_obj = App(
        app_id=app_id,
        tenant_id=tenant_id,
        name=name,
        default_policy_id=policy,
        created_at=now,
    )

    # Save app
    repo.save_app(app_obj)

    console.print(f"[green]\u2713[/green] Created app '{name}'")
    console.print()
    console.print(f"  ID: [cyan]{app_id}[/cyan]")
    console.print(f"  Tenant: {tenant_id}")
    console.print(f"  Name: {name}")
    if policy:
        console.print(f"  Policy: [yellow]{policy}[/yellow]")
    else:
        console.print("  Policy: [dim](inherits from tenant)[/dim]")
    console.print()


@app.command("list")
@click.option(
    "--tenant",
    "-t",
    "tenant_id",
    required=True,
    help="Tenant ID to list apps for",
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
def list_apps(tenant_id: str, output: str):
    """List all apps in a tenant.

    \\b
    Examples:
        raxe app list --tenant acme
        raxe app list --tenant acme --output json
        raxe app list --tenant acme --format json
    """
    # Verify tenant exists
    if not _verify_tenant_exists(tenant_id):
        console.print(f"[red]Error:[/red] Tenant '{tenant_id}' not found")
        sys.exit(1)

    base_path = get_tenants_base_path()
    repo = YamlAppRepository(base_path)

    apps = repo.list_apps(tenant_id)

    if not apps:
        if output == "json":
            console.print("[]")
        else:
            console.print(f"[yellow]No apps found in tenant '{tenant_id}'[/yellow]")
            console.print()
            cmd = f"raxe app create --tenant {tenant_id} --name 'My App'"
            console.print(f"Create an app with: [cyan]{cmd}[/cyan]")
        return

    if output == "json":
        data = [
            {
                "app_id": a.app_id,
                "tenant_id": a.tenant_id,
                "name": a.name,
                "default_policy_id": a.default_policy_id,
                "created_at": a.created_at,
            }
            for a in apps
        ]
        console.print(json.dumps(data, indent=2))
    else:
        table = Table(title=f"Apps in Tenant '{tenant_id}' ({len(apps)})", show_header=True)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="white")
        table.add_column("Policy", style="yellow")
        table.add_column("Created", style="dim", no_wrap=True)

        for a in sorted(apps, key=lambda x: x.app_id):
            created = a.created_at[:10] if a.created_at else "Unknown"
            policy_display = a.default_policy_id or "(inherit)"
            table.add_row(a.app_id, a.name, policy_display, created)

        console.print(table)
        console.print()


@app.command("show")
@click.argument("app_id")
@click.option(
    "--tenant",
    "-t",
    "tenant_id",
    required=True,
    help="Tenant ID that owns the app",
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
def show_app(app_id: str, tenant_id: str, output: str):
    """Show details of a specific app.

    \\b
    Examples:
        raxe app show chatbot --tenant acme
        raxe app show chatbot --tenant acme --output json
        raxe app show chatbot --tenant acme --format json
    """
    # Verify tenant exists
    if not _verify_tenant_exists(tenant_id):
        console.print(f"[red]Error:[/red] Tenant '{tenant_id}' not found")
        sys.exit(1)

    base_path = get_tenants_base_path()
    repo = YamlAppRepository(base_path)

    app_obj = repo.get_app(app_id, tenant_id)

    if not app_obj:
        console.print(f"[red]Error:[/red] App '{app_id}' not found in tenant '{tenant_id}'")
        sys.exit(1)

    if output == "json":
        data = {
            "app_id": app_obj.app_id,
            "tenant_id": app_obj.tenant_id,
            "name": app_obj.name,
            "default_policy_id": app_obj.default_policy_id,
            "created_at": app_obj.created_at,
        }
        console.print(json.dumps(data, indent=2))
    else:
        console.print()
        console.print("[bold]App Details[/bold]")
        console.print()
        console.print(f"  ID: [cyan]{app_obj.app_id}[/cyan]")
        console.print(f"  Tenant: {app_obj.tenant_id}")
        console.print(f"  Name: {app_obj.name}")
        if app_obj.default_policy_id:
            console.print(f"  Policy: [yellow]{app_obj.default_policy_id}[/yellow]")
        else:
            console.print("  Policy: [dim](inherits from tenant)[/dim]")
        created = app_obj.created_at[:10] if app_obj.created_at else "Unknown"
        console.print(f"  Created: {created}")
        console.print()


@app.command("delete")
@click.argument("app_id")
@click.option(
    "--tenant",
    "-t",
    "tenant_id",
    required=True,
    help="Tenant ID that owns the app",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
def delete_app(app_id: str, tenant_id: str, force: bool):
    """Delete an app from a tenant.

    \\b
    Examples:
        raxe app delete chatbot --tenant acme --force
    """
    # Verify tenant exists
    if not _verify_tenant_exists(tenant_id):
        console.print(f"[red]Error:[/red] Tenant '{tenant_id}' not found")
        sys.exit(1)

    base_path = get_tenants_base_path()
    repo = YamlAppRepository(base_path)

    # Check app exists
    app_obj = repo.get_app(app_id, tenant_id)
    if not app_obj:
        console.print(f"[red]Error:[/red] App '{app_id}' not found in tenant '{tenant_id}'")
        sys.exit(1)

    if not force:
        msg = f"This will delete app '{app_obj.name}' from tenant '{tenant_id}'."
        console.print(f"[yellow]Warning:[/yellow] {msg}")
        if not click.confirm("Are you sure?"):
            console.print("[dim]Aborted[/dim]")
            sys.exit(1)

    # Delete app
    repo.delete_app(app_id, tenant_id)

    console.print(f"[green]\u2713[/green] Deleted app '{app_id}'")
    console.print()


@app.command("set-policy")
@click.argument("app_id")
@click.argument("policy")
@click.option(
    "--tenant",
    "-t",
    "tenant_id",
    required=True,
    help="Tenant ID that owns the app",
)
def set_app_policy(app_id: str, policy: str, tenant_id: str):
    """Set the default policy for an app.

    Use 'inherit' to remove the policy override and inherit from tenant.

    \\b
    Examples:
        raxe app set-policy chatbot strict --tenant acme
        raxe app set-policy chatbot inherit --tenant acme
    """
    from raxe.domain.tenants.models import App

    # Verify tenant exists
    if not _verify_tenant_exists(tenant_id):
        console.print(f"[red]Error:[/red] Tenant '{tenant_id}' not found")
        sys.exit(1)

    base_path = get_tenants_base_path()
    repo = YamlAppRepository(base_path)

    # Get existing app
    app_obj = repo.get_app(app_id, tenant_id)
    if not app_obj:
        console.print(f"[red]Error:[/red] App '{app_id}' not found in tenant '{tenant_id}'")
        sys.exit(1)

    # Handle 'inherit' to remove policy override
    new_policy: str | None = None
    if policy.lower() != "inherit":
        # Validate policy exists
        available_policies = _get_available_policies(tenant_id)
        if policy not in available_policies:
            console.print(f"[red]Error:[/red] Invalid policy '{policy}'")
            console.print(f"Valid policies: {', '.join(available_policies)}")
            console.print("Use 'inherit' to remove policy override")
            sys.exit(1)
        new_policy = policy

    old_policy = app_obj.default_policy_id

    # Create updated app (frozen dataclass, must recreate)
    updated_app = App(
        app_id=app_obj.app_id,
        tenant_id=app_obj.tenant_id,
        name=app_obj.name,
        default_policy_id=new_policy,
        created_at=app_obj.created_at,
    )

    # Save updated app
    repo.save_app(updated_app)

    console.print(f"[green]\u2713[/green] Updated policy for app '{app_id}'")
    console.print()
    if old_policy:
        console.print(f"  Old policy: [dim]{old_policy}[/dim]")
    else:
        console.print("  Old policy: [dim](inherit)[/dim]")
    if new_policy:
        console.print(f"  New policy: [yellow]{new_policy}[/yellow]")
    else:
        console.print("  New policy: [dim](inherit from tenant)[/dim]")
    console.print()


# Export the group
__all__ = ["app"]
