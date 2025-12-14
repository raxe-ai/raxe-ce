"""CLI commands for authentication and API key management.

Provides commands for:
- Device flow authentication (recommended): Opens browser for one-click setup
- Manual authentication: Opens RAXE Console for copy-paste key setup
- Validating API key configuration
- Checking remote API key status

Example usage:
    raxe auth              # Device flow (recommended)
    raxe auth connect      # Same as above
    raxe auth login        # Manual key setup
    raxe auth status
    raxe auth status --remote
"""

from __future__ import annotations

import os
import time
import webbrowser
from datetime import datetime, timezone
from typing import Optional

import click
import httpx
from rich.table import Table

from raxe.cli.error_handler import handle_cli_error
from raxe.cli.output import console, display_error, display_success


# Console URLs - resolved via centralized endpoints module
def _get_console_url() -> str:
    """Get console URL from centralized endpoints."""
    from raxe.infrastructure.config.endpoints import get_console_url
    return get_console_url()


def _get_api_base_url() -> str:
    """Get API base URL from centralized endpoints."""
    from raxe.infrastructure.config.endpoints import get_api_base
    return get_api_base()


def _get_cli_session_endpoint() -> str:
    """Get CLI session endpoint from centralized endpoints."""
    from raxe.infrastructure.config.endpoints import get_cli_session_endpoint
    return get_cli_session_endpoint()


def _get_cli_link_endpoint() -> str:
    """Get CLI link endpoint from centralized endpoints."""
    from raxe.infrastructure.config.endpoints import Endpoint, get_endpoint
    return get_endpoint(Endpoint.CLI_LINK)


def _get_console_keys_url() -> str:
    """Get console keys URL."""
    return f"{_get_console_url()}/keys"

# Polling configuration
POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 300  # 5 minutes


@click.group(invoke_without_command=True)
@click.option(
    "--no-link-history",
    is_flag=True,
    default=False,
    help="Do not link existing CLI history to the new account",
)
@click.pass_context
def auth(ctx, no_link_history: bool) -> None:
    """Manage authentication and API keys.

    Run without subcommand for interactive device flow authentication.
    """
    if ctx.invoked_subcommand is None:
        # Default to connect flow when no subcommand
        ctx.invoke(auth_connect, no_link_history=no_link_history)


def _get_current_key_id_from_telemetry() -> Optional[str]:
    """Get the current api_key_id from telemetry state.

    This ensures the temp_key_id sent during authentication matches
    what telemetry events are using, enabling proper event linking
    when upgrading from temporary to permanent keys.

    Returns:
        The api_key_id from telemetry state, or None if not available.
    """
    try:
        from raxe.application.telemetry_orchestrator import get_orchestrator
        orchestrator = get_orchestrator()
        return orchestrator.get_current_api_key_id()
    except Exception:
        # Gracefully handle any initialization errors
        return None


@auth.command("connect")
@click.option(
    "--no-link-history",
    is_flag=True,
    default=False,
    help="Do not link existing CLI history to the new account",
)
@handle_cli_error
def auth_connect(no_link_history: bool) -> None:
    """Connect CLI to your RAXE account (recommended).

    Opens your browser for one-click authentication.
    Your CLI will be automatically configured.

    By default, any existing CLI history from a temporary key will be
    automatically linked to your account. Use --no-link-history to
    skip this and start fresh.

    Examples:
        raxe auth
        raxe auth connect
        raxe auth --no-link-history
    """
    from rich.prompt import Confirm

    from raxe.cli.branding import print_logo
    from raxe.infrastructure.telemetry.credential_store import (
        CredentialStore,
        compute_key_id,
    )

    print_logo(console, compact=True)
    console.print()
    console.print("[bold cyan]RAXE CLI Authentication[/bold cyan]")
    console.print()

    # Get current credentials
    store = CredentialStore()
    credentials = store.load()
    temp_key_id: Optional[str] = None
    installation_id: Optional[str] = None

    # Only detect temp_key_id if we want to link history (default behavior)
    if not no_link_history:
        # Priority 1: Get key_id from telemetry state (ensures consistency with events)
        temp_key_id = _get_current_key_id_from_telemetry()

        # Priority 2: Fall back to computing from credentials
        if temp_key_id is None and credentials and credentials.api_key:
            temp_key_id = compute_key_id(credentials.api_key)

    if credentials:
        installation_id = credentials.installation_id

        # Check if already authenticated with a permanent key
        if credentials.api_key and credentials.api_key.startswith("raxe_live_"):
            masked_key = f"{credentials.api_key[:15]}...{credentials.api_key[-4:]}"
            console.print(f"[green]Already authenticated![/green]")
            console.print(f"  API Key: [cyan]{masked_key}[/cyan]")
            console.print()

            if not Confirm.ask("Re-authenticate with a different account?", default=False):
                console.print()
                console.print("[dim]Run [cyan]raxe auth status[/cyan] to see details[/dim]")
                return

            console.print()

    # Create CLI session
    console.print("[dim]Creating authentication session...[/dim]")

    try:
        session_data = _create_cli_session(temp_key_id, installation_id)
    except Exception as e:
        display_error(
            "Failed to create session",
            details=str(e),
        )
        console.print()
        console.print("[dim]Falling back to manual authentication:[/dim]")
        console.print(f"  Visit: [blue underline]{_get_console_keys_url()}[/blue underline]")
        console.print("  Then run: [cyan]raxe config set api_key YOUR_KEY[/cyan]")
        return

    session_id = session_data["session_id"]
    connect_url = session_data["connect_url"]
    scan_count = session_data.get("scan_count", 0)

    # Show scan preview if any (only when linking history)
    # We show "scans" (not "events") for consistency with Portal metrics
    if scan_count > 0 and not no_link_history:
        console.print()
        console.print(f"[green]Found {scan_count:,} scans from your CLI history![/green]")
        console.print("[dim]   These will be linked to your account.[/dim]")
    elif no_link_history:
        console.print()
        console.print("[dim]History linking disabled (--no-link-history)[/dim]")

    console.print()
    console.print("[cyan]Opening browser...[/cyan]")
    console.print()

    # Open browser
    try:
        webbrowser.open(connect_url)
        console.print("[dim]If browser doesn't open, visit:[/dim]")
        console.print(f"[blue underline]{connect_url}[/blue underline]")
    except Exception:
        console.print("[yellow]Could not open browser. Please visit:[/yellow]")
        console.print(f"[blue underline]{connect_url}[/blue underline]")

    console.print()

    # Poll for completion
    with console.status("[cyan]Waiting for authentication...[/cyan]") as status:
        start_time = time.time()

        while time.time() - start_time < POLL_TIMEOUT_SECONDS:
            try:
                result = _poll_cli_session(session_id)

                if result["status"] == "completed":
                    # Success! Save the new key
                    api_key = result["api_key"]
                    linked_scans = result.get("linked_scans", 0)
                    user_email = result.get("user_email", "")

                    # Save to credentials
                    _save_new_credentials(store, api_key, credentials)

                    # Show success
                    console.print()
                    console.print("[bold green]CLI Connected Successfully![/bold green]")
                    console.print()

                    # Display info table
                    table = Table(show_header=False, box=None, padding=(0, 2))
                    table.add_column("Label", style="dim")
                    table.add_column("Value")

                    masked_key = f"{api_key[:15]}...{api_key[-4:]}"
                    table.add_row("API Key:", f"[green]{masked_key}[/green]")
                    if user_email:
                        table.add_row("Account:", user_email)
                    if linked_scans > 0:
                        table.add_row("Scans Linked:", f"[green]{linked_scans:,}[/green]")

                    console.print(table)
                    console.print()
                    console.print(f"[dim]View your dashboard:[/dim] [blue underline]{_get_console_url()}/portal[/blue underline]")
                    console.print()
                    return

                elif result["status"] == "expired":
                    display_error(
                        "Session expired",
                        details="Please run `raxe auth` again.",
                    )
                    return

                # Still pending, continue polling
                time.sleep(POLL_INTERVAL_SECONDS)

            except httpx.HTTPError:
                # Network error, retry
                status.update("[yellow]Connection issue, retrying...[/yellow]")
                time.sleep(POLL_INTERVAL_SECONDS)
            except Exception as e:
                # Processing error - don't retry, show actual error
                console.print()
                display_error(
                    "Authentication failed",
                    details=str(e),
                )
                return

        # Timeout
        console.print()
        display_error(
            "Authentication timed out",
            details="Please complete the authentication in your browser within 5 minutes.",
        )
        console.print()
        console.print("[dim]You can also set your API key manually:[/dim]")
        console.print("[cyan]  raxe config set api_key YOUR_API_KEY[/cyan]")


def _create_cli_session(
    temp_key_id: Optional[str],
    installation_id: Optional[str],
) -> dict:
    """Create a CLI auth session on the server.

    Args:
        temp_key_id: BigQuery-compatible ID of current temp key (if any).
        installation_id: Installation ID for this CLI instance.

    Returns:
        Session data containing session_id, connect_url, and events_count.

    Raises:
        Exception: If session creation fails.
    """
    with httpx.Client(timeout=10) as client:
        response = client.post(
            _get_cli_session_endpoint(),
            json={
                "temp_key_id": temp_key_id,
                "installation_id": installation_id,
            },
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            raise Exception(data.get("error", "Failed to create session"))

        return data["data"]


def _poll_cli_session(session_id: str) -> dict:
    """Poll for CLI session status.

    Args:
        session_id: Session ID to check.

    Returns:
        Session status data containing status and optionally api_key.

    Raises:
        Exception: If polling fails.
    """
    with httpx.Client(timeout=10) as client:
        response = client.get(f"{_get_cli_session_endpoint()}/{session_id}")
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            raise Exception(data.get("error", "Failed to check session"))

        return data["data"]


def _save_new_credentials(
    store,  # CredentialStore
    api_key: str,
    old_credentials,  # Credentials | None
) -> None:
    """Save new API key and send upgrade event.

    Args:
        store: CredentialStore instance.
        api_key: New API key from authentication.
        old_credentials: Previous credentials (may be None).
    """
    from raxe.domain.telemetry.events import create_key_upgrade_event
    from raxe.infrastructure.telemetry.credential_store import compute_key_id

    # Compute key IDs for upgrade event
    old_key_id: Optional[str] = None
    old_key_type = "temp"
    days_on_previous: Optional[int] = None

    if old_credentials and old_credentials.api_key:
        old_key_id = compute_key_id(old_credentials.api_key)
        if old_credentials.api_key.startswith("raxe_live_"):
            old_key_type = "community"
        elif old_credentials.api_key.startswith("raxe_test_"):
            old_key_type = "test"
        else:
            old_key_type = "temp"
        # Calculate days on previous key
        try:
            created = datetime.fromisoformat(
                old_credentials.created_at.replace("Z", "+00:00")
            )
            now = datetime.now(timezone.utc)
            days_on_previous = (now - created).days
        except (ValueError, TypeError, AttributeError):
            days_on_previous = None

    new_key_id = compute_key_id(api_key)

    # Determine new key type
    if api_key.startswith("raxe_live_"):
        new_key_type = "community"
    elif api_key.startswith("raxe_test_"):
        new_key_type = "test"
    else:
        new_key_type = "community"  # Default for connected keys

    # Update credentials file
    store.upgrade_key(api_key, "live" if new_key_type == "community" else "test")

    # Send upgrade event (fire and forget)
    try:
        from raxe.infrastructure.telemetry.sender import BatchSender

        # Get config for endpoint
        try:
            from raxe.infrastructure.config.yaml_config import RaxeConfig
            config = RaxeConfig.load()
            endpoint = getattr(config.telemetry, "endpoint", None)
        except Exception:
            endpoint = None

        if not endpoint:
            endpoint = f"{_get_api_base_url()}/v1/telemetry"

        # Create upgrade event
        event = create_key_upgrade_event(
            previous_key_type=old_key_type,
            new_key_type=new_key_type,
            previous_key_id=old_key_id,
            new_key_id=new_key_id,
            days_on_previous=days_on_previous,
            conversion_trigger="cli_connect",
        )

        # Get installation_id for sender
        installation_id = None
        if old_credentials:
            installation_id = old_credentials.installation_id

        # Send via batch sender - use old_key_id for correlation (preserves temp key_id)
        sender = BatchSender(
            endpoint=endpoint,
            api_key=api_key,
            installation_id=installation_id or "inst_unknown",
            api_key_id=old_key_id,  # Correlate upgrade event with temp key_id
        )

        # Convert event to dict for sending
        from raxe.domain.telemetry.events import event_to_dict
        sender.send_batch([event_to_dict(event)])

    except Exception:
        pass  # Don't fail auth on telemetry error


@auth.command("login")
@handle_cli_error
def auth_login() -> None:
    """Open RAXE Console to manage API keys (manual).

    For automatic CLI connection, use: raxe auth

    Examples:
        raxe auth login
    """
    console.print()
    console.print("[cyan]Opening RAXE Console in your browser...[/cyan]")
    console.print()

    # Open the console URL in default browser
    try:
        webbrowser.open(_get_console_keys_url())
        display_success(f"Opened {_get_console_keys_url()}")
    except Exception as e:
        console.print(f"[yellow]Could not open browser automatically: {e}[/yellow]")
        console.print()
        console.print(f"Please visit: [blue underline]{_get_console_keys_url()}[/blue underline]")

    console.print()
    console.print("[dim]After creating your API key, configure it with:[/dim]")
    console.print("[cyan]  raxe config set api_key YOUR_API_KEY[/cyan]")
    console.print()
    console.print("[dim]Or set the environment variable:[/dim]")
    console.print("[cyan]  export RAXE_API_KEY=YOUR_API_KEY[/cyan]")
    console.print()


@auth.command("link")
@click.argument("code")
@handle_cli_error
def auth_link(code: str) -> None:
    """Link CLI to an existing API key using a link code.

    Get a link code from the RAXE Console by clicking "Link CLI" on any
    API key card. Then run this command with the code.

    This preserves your CLI's historical telemetry data and links it
    to the selected API key.

    NOTE: This command requires existing CLI history (from prior usage).
    For first-time setup, use 'raxe auth' instead.

    Examples:
        raxe auth link ABC123
        raxe link ABC123
    """
    from rich.prompt import Confirm

    from raxe.cli.branding import print_logo
    from raxe.infrastructure.telemetry.credential_store import (
        CredentialStore,
        compute_key_id,
    )

    print_logo(console, compact=True)
    console.print()
    console.print("[bold cyan]Link CLI to API Key[/bold cyan]")
    console.print()

    # Normalize link code
    normalized_code = code.upper().strip()
    if len(normalized_code) != 6:
        display_error(
            "Invalid link code format",
            details="Link codes are 6 characters. Example: ABC123",
        )
        return

    # Get current credentials
    store = CredentialStore()
    credentials = store.load()
    temp_key_id: Optional[str] = None

    # Priority 1: Get key_id from telemetry state (ensures consistency with events)
    temp_key_id = _get_current_key_id_from_telemetry()

    # Priority 2: Fall back to computing from credentials
    if temp_key_id is None and credentials and credentials.api_key:
        temp_key_id = compute_key_id(credentials.api_key)

    if credentials and credentials.api_key:
        # Check if already authenticated with a permanent key
        if credentials.api_key.startswith("raxe_live_"):
            masked_key = f"{credentials.api_key[:15]}...{credentials.api_key[-4:]}"
            console.print(f"[green]Already authenticated![/green]")
            console.print(f"  API Key: [cyan]{masked_key}[/cyan]")
            console.print()

            if not Confirm.ask("Replace with a different key?", default=False):
                console.print()
                console.print("[dim]Run [cyan]raxe auth status[/cyan] to see details[/dim]")
                return

            console.print()
        else:
            console.print(f"[dim]Current key ID: {temp_key_id}[/dim]")
    else:
        # No credentials at all - link code requires existing CLI history
        console.print("[yellow]No CLI history found.[/yellow]")
        console.print()
        console.print("The [cyan]raxe link[/cyan] command is used to link existing CLI history")
        console.print("to an API key you've already created in the Console.")
        console.print()
        console.print("[bold]For first-time setup, use:[/bold]")
        console.print("  [cyan]raxe auth[/cyan]  - Connect your CLI to your RAXE account")
        console.print()
        return

    console.print()

    # Call the link API
    try:
        with console.status("[cyan]Linking CLI to API key...[/cyan]"):
            result = _link_cli_to_key(normalized_code, temp_key_id)

        if result.get("success"):
            api_key = result["api_key"]
            key_id = result["key_id"]
            events_count = result.get("events_count", 0)
            message = result.get("message", "")

            # Save new credentials
            _save_new_credentials(store, api_key, credentials)

            # Show success
            console.print("[bold green]CLI Linked Successfully![/bold green]")
            console.print()

            # Display info table
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column("Label", style="dim")
            table.add_column("Value")

            masked_key = f"{api_key[:15]}...{api_key[-4:]}"
            table.add_row("API Key:", f"[green]{masked_key}[/green]")
            table.add_row("Key ID:", key_id)
            if events_count > 0:
                table.add_row("Events Linked:", f"[green]{events_count:,}[/green]")

            console.print(table)
            console.print()
            if message:
                console.print(f"[dim]{message}[/dim]")
                console.print()
            console.print(f"[dim]View your dashboard:[/dim] [blue underline]{_get_console_url()}/portal[/blue underline]")
            console.print()
        else:
            display_error(
                "Link failed",
                details=result.get("error", {}).get("message", "Unknown error"),
            )

    except Exception as e:
        display_error(
            "Failed to link CLI",
            details=str(e),
        )
        console.print()
        console.print("[dim]Make sure the link code is correct and hasn't expired.[/dim]")
        console.print("[dim]Get a new code from the RAXE Console: [/dim]")
        console.print(f"[blue underline]{_get_console_url()}/api-keys[/blue underline]")


def _link_cli_to_key(code: str, temp_key_id: Optional[str]) -> dict:
    """Call the CLI link API to link temp key data to an existing key.

    Args:
        code: The 6-character link code from Console.
        temp_key_id: The current temp key ID (if any).

    Returns:
        Response data containing success, api_key, key_id, events_count, message.

    Raises:
        Exception: If the link fails.
    """
    with httpx.Client(timeout=30) as client:
        response = client.post(
            _get_cli_link_endpoint(),
            json={
                "code": code,
                "temp_key_id": temp_key_id or "",
            },
        )

        data = response.json()

        # Handle HTTP errors
        if response.status_code != 200:
            if not data.get("success"):
                return {
                    "success": False,
                    "error": data.get("error", {"message": f"HTTP {response.status_code}"}),
                }
            response.raise_for_status()

        if not data.get("success"):
            return {
                "success": False,
                "error": data.get("error", {"message": "Unknown error"}),
            }

        return data.get("data", {})


@auth.command("status")
@click.option(
    "--remote",
    "-r",
    is_flag=True,
    default=False,
    help="Check status with remote server (requires network)",
)
@handle_cli_error
def auth_status(remote: bool) -> None:
    """Show current authentication status.

    Displays information about the configured API key:
    - Whether an API key is configured
    - Key type (temporary, live, test)
    - Key tier (if determinable)

    Use --remote to fetch real-time information from the server including:
    - Actual days remaining (server-calculated)
    - Events sent today / remaining
    - Rate limits
    - Feature flags

    Examples:
        raxe auth status
        raxe auth status --remote
        raxe auth status -r
    """
    import os

    from raxe.cli.branding import print_logo
    from raxe.infrastructure.config.yaml_config import RaxeConfig
    from raxe.infrastructure.telemetry.credential_store import CredentialStore

    print_logo(console, compact=True)
    console.print()

    # Load API key with fallback chain:
    # 1. RAXE_API_KEY environment variable (highest priority)
    # 2. config.yaml (explicit user config)
    # 3. credentials.json (auto-generated from raxe auth)
    api_key = None
    api_key_source = None

    # Priority 1: Environment variable
    env_api_key = os.environ.get("RAXE_API_KEY", "").strip()
    if env_api_key:
        api_key = env_api_key
        api_key_source = "environment"

    # Priority 2: config.yaml
    if not api_key:
        try:
            config = RaxeConfig.load()
            if config.core.api_key:
                api_key = config.core.api_key
                api_key_source = "config"
        except Exception:
            pass

    # Priority 3: credentials.json
    if not api_key:
        try:
            store = CredentialStore()
            credentials = store.load()
            if credentials:
                api_key = credentials.api_key
                api_key_source = "credentials"
        except Exception:
            pass

    if not api_key:
        console.print("[bold cyan]Authentication Status[/bold cyan]")
        console.print()
        console.print("[yellow]No API key configured[/yellow]")
        console.print()
        console.print("To get an API key:")
        console.print("  1. Run: [cyan]raxe auth[/cyan]")
        console.print("  2. Complete authentication in your browser")
        console.print()
        console.print("Or manually:")
        console.print("  1. Run: [cyan]raxe auth login[/cyan]")
        console.print("  2. Create a key in the RAXE Console")
        console.print("  3. Configure it: [cyan]raxe config set api_key YOUR_KEY[/cyan]")
        console.print()
        console.print(f"Or visit: [blue underline]{_get_console_keys_url()}[/blue underline]")
        console.print()
        return

    if remote:
        _display_remote_status(api_key, config)
    else:
        _display_local_status(api_key, api_key_source)


def _display_local_status(api_key: str, source: str | None = None) -> None:
    """Display local-only authentication status.

    Args:
        api_key: The configured API key
        source: Where the key was loaded from (environment, config, credentials)
    """
    console.print("[bold cyan]Authentication Status[/bold cyan]")
    console.print()

    # Determine key type from prefix
    if api_key.startswith("raxe_live_"):
        key_type = "Live (production)"
        key_style = "green"
    elif api_key.startswith("raxe_test_"):
        key_type = "Test"
        key_style = "yellow"
    elif api_key.startswith("raxe_temp_"):
        key_type = "Temporary (14-day expiry)"
        key_style = "yellow"
    else:
        key_type = "Unknown format"
        key_style = "red"

    # Mask the key for display
    if len(api_key) > 15:
        masked_key = f"{api_key[:12]}...{api_key[-4:]}"
    else:
        masked_key = "***"

    console.print(f"  API Key: [{key_style}]{masked_key}[/{key_style}]")
    console.print(f"  Type: [{key_style}]{key_type}[/{key_style}]")

    # Show source of the key
    if source:
        source_display = {
            "environment": "RAXE_API_KEY env var",
            "config": "~/.raxe/config.yaml",
            "credentials": "~/.raxe/credentials.json",
        }.get(source, source)
        console.print(f"  Source: [dim]{source_display}[/dim]")

    # For temporary keys, show days remaining from credentials file
    if api_key.startswith("raxe_temp_"):
        _display_temp_key_expiry()
        console.print()
        console.print(f"Get a permanent key at: [blue underline]{_get_console_keys_url()}[/blue underline]")
        console.print("Or run: [cyan]raxe auth[/cyan]")

    console.print()
    console.print("[dim]Use --remote flag for real-time server information[/dim]")
    console.print()


def _display_temp_key_expiry() -> None:
    """Display days remaining for temporary key from credentials file.

    Reads the credentials file to get the expires_at field and
    calculates the remaining days until expiry.
    """
    try:
        from raxe.infrastructure.telemetry.credential_store import CredentialStore

        store = CredentialStore()
        credentials = store.load()

        if credentials is None or not credentials.is_temporary():
            console.print()
            console.print("[yellow]Temporary keys expire after 14 days.[/yellow]")
            return

        days_remaining = credentials.days_until_expiry()

        if days_remaining is None:
            console.print()
            console.print("[yellow]Temporary keys expire after 14 days.[/yellow]")
            return

        console.print()

        if days_remaining <= 0:
            console.print("[red bold]  Expiry: EXPIRED[/red bold]")
        elif days_remaining == 1:
            console.print("[red bold]  Expiry: Expires TODAY[/red bold]")
        elif days_remaining <= 3:
            console.print(f"[red]  Expiry: {days_remaining} days remaining[/red]")
        elif days_remaining <= 7:
            console.print(f"[yellow]  Expiry: {days_remaining} days remaining[/yellow]")
        else:
            console.print(f"[green]  Expiry: {days_remaining} days remaining[/green]")

    except Exception:
        # Fallback to generic message if we can't read credentials
        console.print()
        console.print("[yellow]Temporary keys expire after 14 days.[/yellow]")


def _display_remote_status(api_key: str, config) -> None:
    """Display authentication status from remote server.

    Makes a request to the /v1/health endpoint to get real-time
    information about the API key.

    Args:
        api_key: The configured API key
        config: The RaxeConfig object
    """
    from raxe.infrastructure.telemetry.health_client import (
        AuthenticationError,
        HealthCheckError,
        NetworkError,
        TimeoutError,
        check_health,
    )

    console.print("[bold cyan]Authentication Status (Remote)[/bold cyan]")
    console.print()

    # Mask the key for display
    if len(api_key) > 15:
        masked_key = f"{api_key[:12]}...{api_key[-4:]}"
    else:
        masked_key = "***"

    # Get endpoint from config or use default
    endpoint = getattr(config.telemetry, "endpoint", None)
    if endpoint:
        # Extract base URL from telemetry endpoint
        # e.g., "https://api.raxe.ai/v1/telemetry" -> "https://api.raxe.ai"
        if endpoint.endswith("/v1/telemetry"):
            endpoint = endpoint.rsplit("/v1/telemetry", 1)[0]

    try:
        # Show spinner while fetching
        with console.status("[cyan]Fetching status from server...[/cyan]"):
            if endpoint:
                response = check_health(api_key, endpoint=endpoint)
            else:
                response = check_health(api_key)

        # Display key info
        _display_key_info_table(masked_key, response)

    except AuthenticationError as e:
        display_error(
            "Invalid or expired API key",
            details=str(e),
        )
        console.print()
        console.print(f"Get a new key at: [blue underline]{_get_console_keys_url()}[/blue underline]")
        console.print("Or run: [cyan]raxe auth[/cyan]")
        console.print()

    except NetworkError:
        display_error(
            "Could not reach server",
            details="Check your network connection and try again.",
        )
        console.print()
        console.print("[dim]Showing local status instead:[/dim]")
        console.print()
        _display_local_status(api_key)

    except TimeoutError:
        display_error(
            "Server timeout",
            details="The server took too long to respond. Please try again.",
        )
        console.print()
        console.print("[dim]Showing local status instead:[/dim]")
        console.print()
        _display_local_status(api_key)

    except HealthCheckError as e:
        display_error(
            "Health check failed",
            details=str(e),
        )
        console.print()
        console.print("[dim]Showing local status instead:[/dim]")
        console.print()
        _display_local_status(api_key)


def _display_key_info_table(masked_key: str, response) -> None:
    """Display formatted key information table.

    Args:
        masked_key: Masked API key for display
        response: HealthResponse from server
    """
    # Determine key type display
    key_type_display = response.key_type.capitalize()
    if response.key_type == "temp":
        key_type_display = "Temporary"
    elif response.key_type == "live":
        key_type_display = "Live (production)"

    # Key type style
    if response.key_type == "live":
        key_style = "green"
    elif response.key_type in ("test", "temp"):
        key_style = "yellow"
    else:
        key_style = "white"

    # Create main info table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Label", style="dim")
    table.add_column("Value")

    table.add_row("API Key:", f"[{key_style}]{masked_key}[/{key_style}]")
    table.add_row("Type:", f"[{key_style}]{key_type_display}[/{key_style}]")
    table.add_row("Tier:", response.tier.capitalize())

    console.print(table)
    console.print()

    # Trial status section (for temp keys)
    if response.trial_status and response.trial_status.is_trial:
        console.print("[bold]Trial Status:[/bold]")
        trial_table = Table(show_header=False, box=None, padding=(0, 2))
        trial_table.add_column("Label", style="dim")
        trial_table.add_column("Value")

        days = response.days_remaining
        if days is not None:
            if days <= 3:
                days_style = "red bold"
            elif days <= 7:
                days_style = "yellow"
            else:
                days_style = "green"
            trial_table.add_row("Days Remaining:", f"[{days_style}]{days}[/{days_style}]")

        if response.trial_status.scans_during_trial > 0:
            trial_table.add_row(
                "Scans During Trial:",
                f"{response.trial_status.scans_during_trial:,}",
            )
        if response.trial_status.threats_detected_during_trial > 0:
            trial_table.add_row(
                "Threats Detected:",
                f"{response.trial_status.threats_detected_during_trial:,}",
            )

        console.print(trial_table)
        console.print()

    # Usage section
    console.print("[bold]Usage Today:[/bold]")
    usage_table = Table(show_header=False, box=None, padding=(0, 2))
    usage_table.add_column("Label", style="dim")
    usage_table.add_column("Value")

    usage_table.add_row("Events Sent:", f"{response.events_today:,}")
    usage_table.add_row("Events Remaining:", f"{response.events_remaining:,}")

    console.print(usage_table)
    console.print()

    # Rate limits section
    console.print("[bold]Rate Limits:[/bold]")
    rate_table = Table(show_header=False, box=None, padding=(0, 2))
    rate_table.add_column("Label", style="dim")
    rate_table.add_column("Value")

    rate_table.add_row("Requests/min:", f"{response.rate_limit_rpm:,}")
    rate_table.add_row("Events/day:", f"{response.rate_limit_daily:,}")

    console.print(rate_table)
    console.print()

    # Features section
    console.print("[bold]Features:[/bold]")
    features_table = Table(show_header=False, box=None, padding=(0, 2))
    features_table.add_column("Label", style="dim")
    features_table.add_column("Value")

    telemetry_status = "[green]Yes[/green]" if response.can_disable_telemetry else "[yellow]No[/yellow]"
    offline_status = "[green]Yes[/green]" if response.offline_mode else "[yellow]No[/yellow]"

    features_table.add_row("Can Disable Telemetry:", telemetry_status)
    features_table.add_row("Offline Mode:", offline_status)

    console.print(features_table)
    console.print()

    # Upgrade prompt for temp/community keys
    if response.key_type == "temp" or response.tier in ("temporary", "community"):
        console.print("[dim]" + "-" * 50 + "[/dim]")
        console.print()
        if response.key_type == "temp":
            console.print("[yellow]Upgrade to a permanent key for uninterrupted service.[/yellow]")
        else:
            console.print("[cyan]Upgrade to Pro for higher limits and more features.[/cyan]")
        console.print(f"Visit: [blue underline]{_get_console_keys_url()}[/blue underline]")
        console.print("Or run: [cyan]raxe auth[/cyan]")
        console.print()
