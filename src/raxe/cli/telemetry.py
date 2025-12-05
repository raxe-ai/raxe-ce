"""
CLI commands for telemetry management including DLQ operations.

Provides commands for:
- Viewing telemetry status
- Managing the Dead Letter Queue (DLQ)
- Flushing queues
- Enabling/disabling telemetry

Example usage:
    raxe telemetry status
    raxe telemetry dlq list
    raxe telemetry flush
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from raxe.cli.error_handler import handle_cli_error
from raxe.cli.output import console, display_error, display_success, display_warning
from raxe.infrastructure.config.yaml_config import RaxeConfig
from raxe.infrastructure.telemetry.dual_queue import DualQueue
from raxe.infrastructure.telemetry.sender import BatchSender


def _get_api_credentials() -> tuple[str | None, str | None, str | None]:
    """Get API key and installation_id with consistent priority chain.

    Priority for API key:
    1. RAXE_API_KEY environment variable (highest priority)
    2. credentials.json file
    3. config.yaml

    Installation ID is ALWAYS loaded from credentials (machine-specific).

    Returns:
        Tuple of (api_key, installation_id, source) where source indicates
        where the API key came from ("environment", "credentials", "config", or None).
    """
    import os
    from raxe.infrastructure.telemetry.credential_store import CredentialStore

    api_key: str | None = None
    installation_id: str | None = None
    source: str | None = None

    # Always get installation_id from credentials (machine-specific, not key-specific)
    try:
        credential_store = CredentialStore()
        credentials = credential_store.get_or_create(raise_on_expired=False)
        installation_id = credentials.installation_id
    except Exception:
        pass

    # Priority 1: Environment variable for API key
    env_api_key = os.environ.get("RAXE_API_KEY", "").strip()
    if env_api_key:
        api_key = env_api_key
        source = "environment"

    # Priority 2: Credentials file for API key (if not from env)
    if not api_key:
        try:
            credential_store = CredentialStore()
            credentials = credential_store.load()
            if credentials and credentials.api_key:
                api_key = credentials.api_key
                source = "credentials"
        except Exception:
            pass

    # Priority 3: Config file
    if not api_key:
        try:
            config = RaxeConfig.load()
            if config.core.api_key:
                api_key = config.core.api_key
                source = "config"
        except Exception:
            pass

    return api_key, installation_id, source


def _parse_duration(duration_str: str) -> int | None:
    """Parse a duration string (e.g., '7d', '24h', '30m') to days.

    Args:
        duration_str: Duration string with unit suffix (d=days, h=hours, m=minutes)

    Returns:
        Number of days (rounded up for partial days), or None if invalid

    Examples:
        >>> _parse_duration("7d")
        7
        >>> _parse_duration("24h")
        1
        >>> _parse_duration("30m")
        1
    """
    match = re.match(r"^(\d+)([dhm])$", duration_str.strip().lower())
    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "d":
        return value
    elif unit == "h":
        # Round up to at least 1 day
        return max(1, value // 24)
    elif unit == "m":
        # Round up to at least 1 day
        return max(1, value // (24 * 60))

    return None


def _format_relative_time(timestamp_str: str | None) -> str:
    """Format a timestamp as a relative time string.

    Args:
        timestamp_str: ISO format timestamp string or None

    Returns:
        Human-readable relative time string (e.g., "3s ago", "4m ago", "2h ago")
    """
    if not timestamp_str:
        return "unknown"

    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        delta = now - timestamp

        seconds = int(delta.total_seconds())

        if seconds < 0:
            return "in the future"
        elif seconds < 60:
            return f"{seconds}s ago"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours}h ago"
        else:
            days = seconds // 86400
            return f"{days}d ago"

    except (ValueError, TypeError):
        return "unknown"


def _mask_api_key(api_key: str | None) -> str:
    """Mask API key for display, showing only last 3 characters.

    Args:
        api_key: The API key to mask

    Returns:
        Masked API key string (e.g., "raxe_live_***abc")
    """
    if not api_key:
        return "(not configured)"

    if len(api_key) <= 6:
        return "***"

    # Show prefix and last 3 characters
    if api_key.startswith("raxe_"):
        parts = api_key.split("_")
        if len(parts) >= 3:
            return f"raxe_{parts[1]}_***{api_key[-3:]}"
        return f"raxe_***{api_key[-3:]}"

    return f"***{api_key[-3:]}"


def _get_tier_name(api_key: str | None) -> str:
    """Determine the tier name from the API key prefix.

    Args:
        api_key: The API key to analyze

    Returns:
        Tier name string (e.g., "Pro tier", "Enterprise tier", "Free tier")
    """
    if not api_key:
        return "Free tier"

    if "enterprise" in api_key.lower():
        return "Enterprise tier"
    elif "pro" in api_key.lower():
        return "Pro tier"
    elif "test" in api_key.lower():
        return "Test tier"

    return "Pro tier"


def _get_queue_instance() -> DualQueue | None:
    """Get the singleton DualQueue instance from the orchestrator.

    This ensures all telemetry operations (enqueueing and flushing)
    use the SAME queue instance, preventing events from being stuck.

    Returns:
        The orchestrator's DualQueue instance (singleton), or None if
        telemetry is disabled or initialization failed.
    """
    from raxe.application.telemetry_orchestrator import get_orchestrator

    orchestrator = get_orchestrator()
    # Ensure orchestrator is initialized (creates the queue)
    if orchestrator._queue is None:
        if not orchestrator._ensure_initialized():
            # Telemetry disabled or initialization failed
            return None
    return orchestrator._queue


def _get_config() -> RaxeConfig:
    """Load RAXE configuration.

    Returns:
        Loaded RaxeConfig instance
    """
    return RaxeConfig.load()


def _check_telemetry_disable_permission() -> bool:
    """Check if telemetry can be disabled based on cached server permissions.

    Reads the cached permissions from the credential store. If no cached
    permissions exist or they are stale, defaults to denying disable
    (fail-safe behavior for CLI).

    Returns:
        True if telemetry can be disabled, False if tier does not allow it.

    Note:
        This uses cached server permissions from the last health check.
        If the cache is stale (>24 hours), we deny disable as a safety measure.
    """
    try:
        from raxe.infrastructure.telemetry.credential_store import CredentialStore

        store = CredentialStore()
        credentials = store.load()

        if credentials is None:
            # No credentials - deny (new users should not disable)
            return False

        # Check if we have cached permissions
        if credentials.last_health_check is None:
            # Never done health check - check tier from key type
            # Temporary keys cannot disable telemetry
            if credentials.key_type == "temporary":
                return False
            # Live/test keys might be able to - allow but server will enforce
            return True

        # If health check is stale (>24h), deny as safety measure
        if credentials.is_health_check_stale(max_age_hours=24):
            # Stale cache - deny to be safe
            return False

        # Use cached permission
        return credentials.can_disable_telemetry

    except Exception:
        # On error, deny (fail-safe)
        return False


def _get_cached_tier() -> str:
    """Get the cached tier name from credentials.

    Returns:
        Tier name string (e.g., "Community", "Pro", "Enterprise")
    """
    try:
        from raxe.infrastructure.telemetry.credential_store import CredentialStore

        store = CredentialStore()
        credentials = store.load()

        if credentials is None:
            return "Free"

        # Capitalize tier for display
        return credentials.tier.capitalize()

    except Exception:
        return "Unknown"


@click.group()
def telemetry() -> None:
    """Manage telemetry settings and view status."""
    pass


@telemetry.command("status")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show total events (including telemetry) instead of just scans",
)
@handle_cli_error
def status(output_format: str, verbose: bool) -> None:
    """Display telemetry status and queue statistics.

    Shows comprehensive telemetry information including:
    - Connection status and endpoint
    - API key and tier information
    - Circuit breaker state
    - Queue depths and statistics
    - Recent shipping activity

    Examples:
        raxe telemetry status
        raxe telemetry status --format json
    """
    # Load configuration
    config = _get_config()

    # Get API key and installation_id using consistent helper
    api_key, installation_id, api_key_source = _get_api_credentials()

    # Get tier from credentials if available
    tier_from_credentials: str | None = None
    if api_key_source == "credentials":
        try:
            from raxe.infrastructure.telemetry.credential_store import CredentialStore
            credential_store = CredentialStore()
            credentials = credential_store.load()
            if credentials:
                tier_from_credentials = credentials.tier
        except Exception:
            pass

    # Get queue stats
    queue = _get_queue_instance()
    stats = queue.get_stats()

    # Resolve endpoint (fallback to centralized config if empty)
    endpoint = config.telemetry.endpoint
    if not endpoint:
        from raxe.infrastructure.config.endpoints import get_telemetry_endpoint
        endpoint = get_telemetry_endpoint()

    # Get circuit breaker state
    try:
        sender = BatchSender(
            endpoint=endpoint,
            api_key=api_key,
            installation_id=installation_id,
        )
        circuit_state = sender.get_circuit_state()
    except Exception:
        circuit_state = "unknown"

    # Determine tier display
    if tier_from_credentials:
        tier_display = tier_from_credentials.capitalize() + " tier"
    else:
        tier_display = _get_tier_name(api_key)

    # Build status data
    status_data: dict[str, Any] = {
        "endpoint": endpoint,
        "schema_version": "0.0.1",
        "api_key": _mask_api_key(api_key),
        "tier": tier_display,
        "telemetry_enabled": config.telemetry.enabled,
        "circuit_breaker_state": circuit_state.upper(),
        "queues": {
            "critical": {
                "count": stats.get("critical_count", 0),
                "oldest": stats.get("oldest_critical"),
            },
            "standard": {
                "count": stats.get("standard_count", 0),
                "oldest": stats.get("oldest_standard"),
            },
            "dlq": {
                "count": stats.get("dlq_count", 0),
            },
        },
        "retry_pending": stats.get("retry_pending", 0),
        "total_queued": stats.get("total_queued", 0),
        "lifetime_stats": {
            "scans_sent_total": stats.get("scans_sent_total", 0),
            "events_sent_total": stats.get("events_sent_total", 0),
            "batches_sent_total": stats.get("batches_sent_total", 0),
        },
    }

    queue.close()

    if output_format == "json":
        console.print_json(data=status_data)
        return

    # Text output with tree-style formatting
    from raxe.cli.branding import print_logo

    print_logo(console, compact=True)
    console.print()

    console.print("[bold cyan]Telemetry Status[/bold cyan]")
    console.print()

    # Connection info
    connection_status = "connected" if circuit_state == "closed" else "degraded"
    endpoint_display = endpoint.replace("https://", "").split("/")[0]

    content = Text()
    content.append(f"Endpoint: {endpoint_display} ({connection_status})\n", style="white")
    content.append("Schema Version: 1.0.0\n", style="white")
    api_key_display = _mask_api_key(api_key)
    content.append(f"API Key: {api_key_display} ({tier_display})\n", style="white")
    telemetry_status = "Enabled" if config.telemetry.enabled else "Disabled"
    telemetry_color = "green" if config.telemetry.enabled else "yellow"
    content.append(f"Telemetry: {telemetry_status}\n", style=telemetry_color)
    content.append("\n")

    # Circuit breaker
    if circuit_state == "closed":
        cb_color = "green"
    elif circuit_state == "half_open":
        cb_color = "yellow"
    else:
        cb_color = "red"
    content.append("Circuit Breaker: ", style="white")
    content.append(f"{circuit_state.upper()}\n", style=cb_color)

    # Queue depths
    critical_count = stats.get("critical_count", 0)
    standard_count = stats.get("standard_count", 0)
    dlq_count = stats.get("dlq_count", 0)

    oldest_critical = _format_relative_time(stats.get("oldest_critical"))
    oldest_standard = _format_relative_time(stats.get("oldest_standard"))

    critical_info = f"{critical_count:,} events"
    if critical_count > 0:
        critical_info += f" (oldest: {oldest_critical})"

    standard_info = f"{standard_count:,} events"
    if standard_count > 0:
        standard_info += f" (oldest: {oldest_standard})"

    content.append(f"Critical Queue: {critical_info}\n", style="white")
    content.append(f"Standard Queue: {standard_info}\n", style="white")
    dlq_style = "white" if dlq_count == 0 else "yellow"
    content.append(f"Dead Letter Queue: {dlq_count} events\n", style=dlq_style)

    # Lifetime stats
    events_sent_total = stats.get("events_sent_total", 0)
    scans_sent_total = stats.get("scans_sent_total", 0)
    batches_sent_total = stats.get("batches_sent_total", 0)
    content.append("\n")

    # Show scans by default (matches Portal), show all events with --verbose
    if verbose:
        content.append(f"Events Sent (total): {events_sent_total:,}\n", style="green")
        content.append(f"  - Scans: {scans_sent_total:,}\n", style="dim")
        content.append(f"  - Telemetry: {events_sent_total - scans_sent_total:,}\n", style="dim")
    else:
        content.append(f"Scans Sent (total): {scans_sent_total:,}\n", style="green")
    content.append(f"Batches Sent (total): {batches_sent_total:,}\n", style="dim")

    console.print(Panel(content, border_style="cyan", padding=(1, 2)))
    console.print()


@telemetry.group("dlq")
def dlq() -> None:
    """Manage the Dead Letter Queue (DLQ)."""
    pass


@dlq.command("list")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--limit",
    type=int,
    default=100,
    help="Maximum number of events to list (default: 100)",
)
@handle_cli_error
def dlq_list(output_format: str, limit: int) -> None:
    """List events in the Dead Letter Queue.

    Shows failed events that have exceeded maximum retry attempts.
    Use this to inspect failed events and decide whether to retry or clear them.

    Examples:
        raxe telemetry dlq list
        raxe telemetry dlq list --format json
        raxe telemetry dlq list --limit 50
    """
    queue = _get_queue_instance()
    events = queue.get_dlq_events(limit=limit)
    queue.close()

    if output_format == "json":
        console.print_json(data={"events": events, "count": len(events)})
        return

    # Text output
    from raxe.cli.branding import print_logo

    print_logo(console, compact=True)
    console.print()

    if not events:
        console.print("[green]Dead Letter Queue is empty[/green]")
        console.print()
        return

    console.print(f"[bold cyan]Dead Letter Queue ({len(events)} events)[/bold cyan]")
    console.print()

    # Create table
    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("Event ID", style="cyan", no_wrap=True, width=18)
    table.add_column("Type", style="white", width=12)
    table.add_column("Failed At", style="yellow", width=12)
    table.add_column("Reason", style="red")

    for event in events:
        event_id = event.get("event_id", "unknown")
        event_type = event.get("event_type", "unknown")
        failed_at = _format_relative_time(event.get("failed_at"))
        reason = event.get("failure_reason", "Unknown error")

        # Build reason string
        server_code = event.get("server_error_code")
        server_msg = event.get("server_error_message")

        if server_code:
            if server_msg:
                reason = f"{server_code}: {server_msg}"
            else:
                reason = f"HTTP {server_code}"
        elif event.get("retry_count", 0) >= 3:
            reason = f"Max retries exceeded ({event.get('retry_count', 0)})"

        # Truncate event_id for display
        event_id_display = f"{event_id[:12]}..." if len(event_id) > 15 else event_id

        # Truncate reason if too long
        if len(reason) > 40:
            reason = reason[:37] + "..."

        table.add_row(event_id_display, event_type, failed_at, reason)

    console.print(table)
    console.print()


@dlq.command("show")
@click.argument("event_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text)",
)
@handle_cli_error
def dlq_show(event_id: str, output_format: str) -> None:
    """Show details of a specific DLQ event.

    Displays full information about a failed event including:
    - Event metadata (ID, type, timestamps)
    - Failure details (reason, error codes)
    - Sanitized payload

    Examples:
        raxe telemetry dlq show evt_abc123
        raxe telemetry dlq show evt_abc123 --format json
    """
    queue = _get_queue_instance()
    events = queue.get_dlq_events(limit=1000)
    queue.close()

    # Find the matching event
    event = None
    for e in events:
        if e.get("event_id", "").startswith(event_id) or e.get("event_id") == event_id:
            event = e
            break

    if not event:
        display_error("Event not found", f"No event found with ID: {event_id}")
        return

    if output_format == "json":
        console.print_json(data=event)
        return

    # Text output
    from raxe.cli.branding import print_logo

    print_logo(console, compact=True)
    console.print()

    console.print(f"[bold cyan]Event: {event.get('event_id')}[/bold cyan]")
    console.print()

    # Event details
    content = Text()
    content.append(f"Type: {event.get('event_type', 'unknown')}\n", style="white")
    content.append(f"Priority: {event.get('priority', 'unknown')}\n", style="white")
    content.append(f"Created: {event.get('created_at', 'unknown')}\n", style="white")
    content.append(f"Failed: {event.get('failed_at', 'unknown')}\n", style="yellow")
    content.append(f"Retries: {event.get('retry_count', 0)}\n", style="white")
    content.append("\n")

    # Error details
    server_code = event.get("server_error_code")
    server_msg = event.get("server_error_message")
    reason = event.get("failure_reason", "Unknown error")

    content.append("[bold]Error Details:[/bold]\n", style="red")
    if server_code:
        content.append(f"  HTTP Code: {server_code}\n", style="red")
    if server_msg:
        content.append(f"  Server Message: {server_msg}\n", style="red")
    content.append(f"  Reason: {reason}\n", style="red")

    console.print(Panel(content, border_style="cyan", padding=(1, 2)))
    console.print()

    # Sanitized payload
    payload = event.get("payload", {})
    if payload:
        console.print("[bold cyan]Payload (sanitized):[/bold cyan]")
        console.print_json(data=payload)
        console.print()


@dlq.command("clear")
@click.option(
    "--older-than",
    "older_than",
    type=str,
    help="Only clear events older than this duration (e.g., 7d, 24h)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Skip confirmation prompt",
)
@handle_cli_error
def dlq_clear(older_than: str | None, force: bool) -> None:
    """Clear events from the Dead Letter Queue.

    Permanently removes failed events from the DLQ.
    Use --older-than to selectively remove old events.

    Examples:
        raxe telemetry dlq clear
        raxe telemetry dlq clear --older-than 7d
        raxe telemetry dlq clear --force
    """
    queue = _get_queue_instance()

    # Get current count
    stats = queue.get_stats()
    current_count = stats.get("dlq_count", 0)

    if current_count == 0:
        console.print("[green]Dead Letter Queue is already empty[/green]")
        queue.close()
        return

    # Parse older_than if provided
    older_than_days: int | None = None
    if older_than:
        older_than_days = _parse_duration(older_than)
        if older_than_days is None:
            display_error(
                "Invalid duration format",
                f"Got '{older_than}', expected format like '7d', '24h', or '30m'",
            )
            queue.close()
            return

    # Confirm action
    if not force:
        if older_than_days:
            msg = f"Are you sure you want to delete events older than {older_than} from DLQ?"
        else:
            msg = f"Are you sure you want to permanently delete {current_count} failed events?"

        if not click.confirm(msg):
            console.print("[yellow]Operation cancelled[/yellow]")
            queue.close()
            return

    # Clear events
    cleared = queue.clear_dlq(older_than_days=older_than_days)
    queue.close()

    if older_than_days:
        display_success(f"Cleared {cleared} events older than {older_than} from Dead Letter Queue.")
    else:
        display_success(f"Cleared {cleared} events from Dead Letter Queue.")


@dlq.command("retry")
@click.argument("event_id", required=False)
@click.option(
    "--all",
    "retry_all",
    is_flag=True,
    help="Retry all events in the DLQ",
)
@handle_cli_error
def dlq_retry(event_id: str | None, retry_all: bool) -> None:
    """Retry failed events from the Dead Letter Queue.

    Moves events back to the main queue for reprocessing.
    Specify an event ID or use --all to retry all events.

    Examples:
        raxe telemetry dlq retry evt_abc123
        raxe telemetry dlq retry --all
    """
    if not event_id and not retry_all:
        display_error(
            "No events specified",
            "Provide an event ID or use --all to retry all events",
        )
        return

    queue = _get_queue_instance()

    if retry_all:
        # Retry all events
        count = queue.retry_dlq_events()
        queue.close()

        if count == 0:
            console.print("[yellow]No events in Dead Letter Queue to retry[/yellow]")
        else:
            display_success(f"Moved {count} events from DLQ back to queue for retry.")
        return

    # Retry specific event
    # First find the full event ID
    events = queue.get_dlq_events(limit=1000)
    full_event_id = None
    for e in events:
        if e.get("event_id", "").startswith(event_id) or e.get("event_id") == event_id:
            full_event_id = e.get("event_id")
            break

    if not full_event_id:
        display_error("Event not found", f"No event found with ID: {event_id}")
        queue.close()
        return

    count = queue.retry_dlq_events([full_event_id])
    queue.close()

    if count > 0:
        display_success(f"Moved event {full_event_id} back to queue for retry.")
    else:
        display_warning(f"Failed to retry event {full_event_id}.")


@telemetry.command("flush")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text)",
)
@handle_cli_error
def flush(output_format: str) -> None:
    """Flush telemetry queues immediately.

    Forces immediate processing of all queued telemetry events.
    Use this before shutting down or when you need immediate delivery.

    Examples:
        raxe telemetry flush
        raxe telemetry flush --format json
    """
    import time

    start_time = time.time()

    # Get queue stats before flush
    queue = _get_queue_instance()
    stats_before = queue.get_stats()

    critical_before = stats_before.get("critical_count", 0)
    standard_before = stats_before.get("standard_count", 0)
    total_before = critical_before + standard_before

    if total_before == 0:
        if output_format == "json":
            console.print_json(
                data={
                    "status": "ok",
                    "message": "No events to flush",
                    "critical_shipped": 0,
                    "standard_shipped": 0,
                    "total_shipped": 0,
                    "duration_seconds": 0,
                }
            )
        else:
            console.print("[green]No events to flush - queues are empty[/green]")
        queue.close()
        return

    # Load config for sender
    config = _get_config()

    if not config.telemetry.enabled:
        if output_format == "json":
            console.print_json(
                data={
                    "status": "error",
                    "message": "Telemetry is disabled",
                }
            )
        else:
            display_warning("Telemetry is disabled. Enable it to flush events.")
        queue.close()
        return

    # Get API key and installation_id using consistent helper
    api_key, installation_id, _ = _get_api_credentials()

    # Get endpoint (fall back to centralized endpoints if config is empty)
    endpoint = config.telemetry.endpoint
    if not endpoint:
        from raxe.infrastructure.config.endpoints import get_telemetry_endpoint
        endpoint = get_telemetry_endpoint()

    # Process critical events
    critical_shipped = 0
    standard_shipped = 0
    errors: list[str] = []

    try:
        # NOTE: Don't pass api_key_id - let the sender compute it from api_key.
        # This ensures events are tagged with the CURRENT key's ID, not a stale
        # ID from queue state. The backend uses the authenticated key's ID for
        # event correlation (key_info.key_id).
        sender = BatchSender(
            endpoint=endpoint,
            api_key=api_key,
            installation_id=installation_id,
        )

        # Flush critical queue
        while True:
            events = queue.dequeue_critical(batch_size=100)
            if not events:
                break

            try:
                sender.send_batch(events)
                event_ids: list[str] = [
                    str(e.get("event_id")) for e in events if e.get("event_id") is not None
                ]
                queue.mark_batch_sent(event_ids)
                critical_shipped += len(events)
            except Exception as e:
                errors.append(f"Critical batch failed: {e}")
                event_ids_failed: list[str] = [
                    str(ev.get("event_id")) for ev in events if ev.get("event_id") is not None
                ]
                queue.mark_batch_failed(event_ids_failed, str(e), retry_delay_seconds=60)
                break

        # Flush standard queue
        while True:
            events = queue.dequeue_standard(batch_size=100)
            if not events:
                break

            try:
                sender.send_batch(events)
                event_ids = [
                    str(e.get("event_id")) for e in events if e.get("event_id") is not None
                ]
                queue.mark_batch_sent(event_ids)
                standard_shipped += len(events)
            except Exception as e:
                errors.append(f"Standard batch failed: {e}")
                event_ids_failed = [
                    str(ev.get("event_id")) for ev in events if ev.get("event_id") is not None
                ]
                queue.mark_batch_failed(event_ids_failed, str(e), retry_delay_seconds=60)
                break

    except Exception as e:
        errors.append(f"Sender initialization failed: {e}")

    queue.close()
    duration = time.time() - start_time

    total_shipped = critical_shipped + standard_shipped

    if output_format == "json":
        console.print_json(
            data={
                "status": "ok" if not errors else "partial",
                "critical_shipped": critical_shipped,
                "standard_shipped": standard_shipped,
                "total_shipped": total_shipped,
                "duration_seconds": round(duration, 2),
                "errors": errors if errors else None,
            }
        )
        return

    # Text output
    from raxe.cli.branding import print_logo

    print_logo(console, compact=True)
    console.print()

    console.print("[bold cyan]Flushing telemetry queues...[/bold cyan]")
    console.print()

    content = Text()
    content.append(f"Critical queue: {critical_shipped} events shipped\n", style="white")
    content.append(f"Standard queue: {standard_shipped} events shipped\n", style="white")
    content.append(f"Total: {total_shipped} events shipped in {duration:.1f}s\n", style="green")

    if errors:
        content.append("\n")
        content.append("[bold yellow]Warnings:[/bold yellow]\n", style="yellow")
        for error in errors:
            content.append(f"  - {error}\n", style="yellow")

    console.print(Panel(content, border_style="cyan" if not errors else "yellow", padding=(1, 2)))
    console.print()


@telemetry.command("disable")
@handle_cli_error
def disable() -> None:
    """Disable telemetry collection.

    Note: Telemetry cannot be disabled on the free tier.
    Telemetry helps improve RAXE for everyone and contains no personal data.

    Examples:
        raxe telemetry disable
    """
    config = _get_config()

    # Check cached server permissions first
    can_disable = _check_telemetry_disable_permission()

    if not can_disable:
        # Get tier for display
        tier = _get_cached_tier()

        console.print()
        console.print(
            "[red bold]Error: Telemetry cannot be disabled on your current tier.[/red bold]"
        )
        console.print()
        console.print(f"[dim]Your tier: {tier}[/dim]")
        console.print()
        console.print("Telemetry helps improve RAXE for everyone and contains no personal data.")
        console.print(
            "Only anonymized detection metadata is collected (rule IDs, severity levels)."
        )
        console.print()
        from raxe.infrastructure.config.endpoints import get_console_url
        console_url = get_console_url()
        console.print(
            "[cyan]Upgrade to Pro at:[/cyan] "
            f"[blue underline]{console_url}/upgrade[/blue underline]"
        )
        console.print()
        return

    # Update configuration
    config_path = Path.home() / ".raxe" / "config.yaml"
    config.telemetry.enabled = False
    config.save(config_path)

    display_success("Telemetry disabled.")
    console.print()
    console.print("[dim]Note: No further telemetry events will be sent.[/dim]")
    console.print("[dim]Existing queued events will be preserved but not shipped.[/dim]")
    console.print()


@telemetry.command("enable")
@handle_cli_error
def enable() -> None:
    """Enable telemetry collection.

    Telemetry helps improve RAXE detection accuracy across the community.
    Only anonymized metadata is collected - no prompts, responses, or PII.

    Examples:
        raxe telemetry enable
    """
    config_path = Path.home() / ".raxe" / "config.yaml"
    config = _get_config()

    if config.telemetry.enabled:
        console.print("[green]Telemetry is already enabled.[/green]")
        return

    config.telemetry.enabled = True
    config.save(config_path)

    display_success("Telemetry enabled.")
    console.print()
    console.print("[dim]Privacy guarantee: Only anonymized detection metadata is collected.[/dim]")
    console.print("[dim]No prompts, responses, or personal data is ever transmitted.[/dim]")
    console.print()


# Alias for 'set' command to match naming convention
@telemetry.command("config")
@click.argument("key")
@click.argument("value")
@handle_cli_error
def telemetry_config(key: str, value: str) -> None:
    """Set telemetry configuration values.

    Allows adjusting telemetry-specific settings without editing the config file.

    Available keys:
        batch_size: Number of events per batch (default: 50)
        flush_interval: Seconds between flushes (default: 300)

    Examples:
        raxe telemetry config batch_size 100
        raxe telemetry config flush_interval 60
    """
    config_path = Path.home() / ".raxe" / "config.yaml"
    config = _get_config()

    # Map keys to config attributes
    key_map = {
        "batch_size": ("batch_size", int),
        "flush_interval": ("flush_interval", int),
        "endpoint": ("endpoint", str),
    }

    if key not in key_map:
        valid_keys = ", ".join(key_map.keys())
        display_error(f"Unknown key: {key}", f"Valid keys: {valid_keys}")
        return

    attr_name, value_type = key_map[key]

    try:
        typed_value = value_type(value)
    except ValueError:
        display_error(f"Invalid value for {key}", f"Expected {value_type.__name__}, got: {value}")
        return

    setattr(config.telemetry, attr_name, typed_value)

    # Validate
    errors = config.validate()
    if errors:
        for error in errors:
            display_error("Validation error", error)
        return

    config.save(config_path)
    display_success(f"Set telemetry.{key} = {value}")


# =============================================================================
# Endpoint Management Commands
# =============================================================================


@telemetry.group("endpoint")
def endpoint() -> None:
    """Manage telemetry endpoint configuration.

    Configure which backend endpoint the CLI uses for telemetry.
    Supports different environments (production, development, staging)
    and custom endpoint URLs.
    """
    pass


@endpoint.command("show")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text)",
)
@handle_cli_error
def endpoint_show(output_format: str) -> None:
    """Show current endpoint configuration.

    Displays the current telemetry endpoint URL and environment settings.

    Examples:
        raxe telemetry endpoint show
        raxe telemetry endpoint show --format json
    """
    from raxe.infrastructure.config.endpoints import get_endpoint_info, Endpoint

    info = get_endpoint_info()

    if output_format == "json":
        console.print_json(data=info)
        return

    # Text output
    from raxe.cli.branding import print_logo

    print_logo(console, compact=True)
    console.print()

    console.print("[bold cyan]Endpoint Configuration[/bold cyan]")
    console.print()

    content = Text()
    content.append(f"Environment: {info['environment']}\n", style="green")
    content.append(f"Source: {info['environment_source']}\n", style="dim")
    content.append("\n")

    content.append("[bold]Active Endpoints:[/bold]\n", style="cyan")
    for name, url in info["endpoints"].items():
        content.append(f"  {name}: ", style="white")
        content.append(f"{url}\n", style="blue")

    if info.get("overrides"):
        content.append("\n")
        content.append("[bold]Active Overrides:[/bold]\n", style="yellow")
        for name, url in info["overrides"].items():
            content.append(f"  {name}: {url}\n", style="yellow")

    if info.get("env_vars"):
        content.append("\n")
        content.append("[bold]Environment Variables:[/bold]\n", style="dim")
        for name, value in info["env_vars"].items():
            content.append(f"  {name}: {value}\n", style="dim")

    console.print(Panel(content, border_style="cyan", padding=(1, 2)))
    console.print()


@endpoint.command("set")
@click.argument("url")
@handle_cli_error
def endpoint_set(url: str) -> None:
    """Set a custom telemetry endpoint URL.

    Overrides the default endpoint for telemetry transmission.
    Use this for enterprise deployments or custom backend installations.

    Examples:
        raxe telemetry endpoint set https://custom.example.com/v1/telemetry
    """
    from raxe.infrastructure.config.endpoints import set_endpoint, Endpoint

    try:
        set_endpoint(Endpoint.TELEMETRY, url)
        display_success(f"Telemetry endpoint set to: {url}")
        console.print()
        console.print("[dim]Note: This override is session-only.[/dim]")
        console.print("[dim]For persistent changes, set RAXE_TELEMETRY_ENDPOINT environment variable.[/dim]")
        console.print()
    except ValueError as e:
        display_error("Invalid URL", str(e))


@endpoint.command("reset")
@handle_cli_error
def endpoint_reset() -> None:
    """Reset endpoint to default for current environment.

    Clears any runtime overrides and returns to using the
    environment-default endpoint.

    Examples:
        raxe telemetry endpoint reset
    """
    from raxe.infrastructure.config.endpoints import reset_endpoint, get_telemetry_endpoint, Endpoint

    reset_endpoint(Endpoint.TELEMETRY)
    current = get_telemetry_endpoint()
    display_success(f"Endpoint reset to default: {current}")


@endpoint.command("test")
@click.option(
    "--timeout",
    type=float,
    default=10.0,
    help="Connection timeout in seconds (default: 10)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text)",
)
@handle_cli_error
def endpoint_test(timeout: float, output_format: str) -> None:
    """Test connectivity to all endpoints.

    Performs DNS resolution and HTTP connectivity tests
    for each configured endpoint.

    Examples:
        raxe telemetry endpoint test
        raxe telemetry endpoint test --timeout 5
    """
    from raxe.infrastructure.config.endpoints import test_all_endpoints, Endpoint

    results = test_all_endpoints(timeout_seconds=timeout)

    if output_format == "json":
        json_data = {
            ep.value: {
                "url": status.url,
                "dns_resolved": status.dns_resolved,
                "reachable": status.reachable,
                "response_time_ms": status.response_time_ms,
                "http_status": status.http_status,
                "error": status.error,
            }
            for ep, status in results.items()
        }
        console.print_json(data=json_data)
        return

    # Text output
    from raxe.cli.branding import print_logo

    print_logo(console, compact=True)
    console.print()

    console.print("[bold cyan]Endpoint Connectivity Test[/bold cyan]")
    console.print()

    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("Endpoint", style="cyan", no_wrap=True, width=15)
    table.add_column("DNS", style="white", width=5)
    table.add_column("HTTP", style="white", width=5)
    table.add_column("Time (ms)", style="white", width=10)
    table.add_column("Status", style="white")

    for ep, status in results.items():
        dns_icon = "[green]✓[/green]" if status.dns_resolved else "[red]✗[/red]"
        http_icon = "[green]✓[/green]" if status.reachable else "[red]✗[/red]"

        time_str = f"{status.response_time_ms:.0f}" if status.response_time_ms else "-"

        if status.reachable and status.http_status:
            if status.http_status < 400:
                status_str = f"[green]{status.http_status} OK[/green]"
            elif status.http_status == 401:
                status_str = f"[yellow]{status.http_status} (needs auth)[/yellow]"
            else:
                status_str = f"[red]{status.http_status}[/red]"
        elif status.error:
            status_str = f"[red]{status.error[:30]}...[/red]" if len(status.error) > 30 else f"[red]{status.error}[/red]"
        else:
            status_str = "[dim]-[/dim]"

        table.add_row(ep.value, dns_icon, http_icon, time_str, status_str)

    console.print(table)
    console.print()

    # Summary
    total = len(results)
    reachable = sum(1 for s in results.values() if s.reachable)

    if reachable == total:
        console.print(f"[green]All {total} endpoints reachable[/green]")
    else:
        console.print(f"[yellow]{reachable}/{total} endpoints reachable[/yellow]")
    console.print()


@endpoint.command("use")
@click.argument(
    "environment",
    type=click.Choice(["production", "prod", "staging", "stage", "development", "dev", "local"]),
)
@handle_cli_error
def endpoint_use(environment: str) -> None:
    """Switch to a predefined environment.

    Changes all endpoints to use the specified environment's defaults.

    Available environments:
        production (prod)  - Production endpoints
        staging (stage)    - Staging endpoints
        development (dev)  - Development/test endpoints
        local              - Local development server

    Examples:
        raxe telemetry endpoint use dev
        raxe telemetry endpoint use production
    """
    from raxe.infrastructure.config.endpoints import (
        save_environment,
        Environment,
        get_endpoint_info,
    )

    env_map = {
        "production": Environment.PRODUCTION,
        "prod": Environment.PRODUCTION,
        "staging": Environment.STAGING,
        "stage": Environment.STAGING,
        "development": Environment.DEVELOPMENT,
        "dev": Environment.DEVELOPMENT,
        "local": Environment.LOCAL,
    }

    env = env_map[environment]
    save_environment(env)  # Persist to config file

    info = get_endpoint_info()

    display_success(f"Switched to {env.value} environment")
    console.print()
    console.print("[bold]Active endpoints:[/bold]")
    for name, url in info["endpoints"].items():
        console.print(f"  {name}: [blue]{url}[/blue]")
    console.print()
    console.print("[dim]Saved to ~/.raxe/config.yaml[/dim]")
    console.print()
