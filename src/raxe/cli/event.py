"""CLI commands for event lookup from the RAXE portal.

Provides commands to look up scan events by ID and display detailed information
with rich formatting. Events are retrieved from the RAXE console API.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import click
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from raxe.cli.output import console, display_error, display_warning
from raxe.infrastructure.config.endpoints import get_console_url
from raxe.infrastructure.database.scan_history import ScanHistoryDB
from raxe.infrastructure.telemetry.credential_store import CredentialStore
from raxe.utils.logging import get_logger

logger = get_logger(__name__)

# Event ID validation pattern: evt_{16 hex chars}
EVENT_ID_PATTERN = re.compile(r"^evt_[a-f0-9]{16}$")

# Severity color mapping for consistent display
SEVERITY_COLORS = {
    "critical": "red bold",
    "high": "red",
    "medium": "yellow",
    "low": "blue",
    "none": "green",
}

SEVERITY_ICONS = {
    "critical": "[red bold]!!![/red bold]",
    "high": "[red]!![/red]",
    "medium": "[yellow]![/yellow]",
    "low": "[blue]o[/blue]",
    "none": "[green]*[/green]",
}


@dataclass
class EventData:
    """Parsed event data from the portal API.

    Attributes:
        event_id: Unique event identifier (evt_xxx format)
        timestamp: ISO 8601 timestamp when scan occurred
        severity: Highest severity level detected
        detections: List of detection details
        prompt_hash: SHA256 hash of the scanned prompt
        prompt_length: Length of the original prompt in characters
        scan_duration_ms: Scan duration in milliseconds
        prompt_text: Optional full prompt text (only if --show-prompt)
    """

    event_id: str
    timestamp: str
    severity: str
    detections: list[dict[str, Any]]
    prompt_hash: str
    prompt_length: int | None = None
    scan_duration_ms: float | None = None
    prompt_text: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "EventData":
        """Create EventData from API response.

        Args:
            data: API response dictionary

        Returns:
            EventData instance
        """
        return cls(
            event_id=data.get("event_id", ""),
            timestamp=data.get("timestamp", ""),
            severity=data.get("severity", data.get("highest_severity", "none")),
            detections=data.get("detections", []),
            prompt_hash=data.get("prompt_hash", ""),
            prompt_length=data.get("prompt_length"),
            scan_duration_ms=data.get("scan_duration_ms"),
            prompt_text=data.get("prompt_text"),
        )


def validate_event_id(event_id: str) -> bool:
    """Validate event ID format.

    Args:
        event_id: Event ID to validate

    Returns:
        True if valid, False otherwise
    """
    return EVENT_ID_PATTERN.match(event_id) is not None


def format_relative_time(iso_timestamp: str) -> str:
    """Format ISO timestamp as relative time.

    Args:
        iso_timestamp: ISO 8601 timestamp string

    Returns:
        Human-readable relative time string (e.g., "2 hours ago")
    """
    try:
        # Parse the timestamp
        timestamp_str = iso_timestamp.replace("Z", "+00:00")
        event_time = datetime.fromisoformat(timestamp_str)
        now = datetime.now(timezone.utc)

        delta = now - event_time
        seconds = int(delta.total_seconds())

        if seconds < 0:
            return "in the future"
        elif seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''} ago"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = seconds // 86400
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 2592000:
            weeks = seconds // 604800
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        else:
            months = seconds // 2592000
            return f"{months} month{'s' if months != 1 else ''} ago"
    except (ValueError, TypeError):
        return ""


def fetch_event_from_local(event_id: str) -> EventData | None:
    """Fetch event data from local scan history database.

    This is the preferred lookup method as it contains full prompt text
    stored locally for privacy.

    Args:
        event_id: Event ID to look up

    Returns:
        EventData if found, None otherwise
    """
    try:
        db = ScanHistoryDB()
        scan = db.get_by_event_id(event_id)

        if scan is None:
            logger.debug("Event not found in local history: %s", event_id)
            return None

        # Get detections for this scan
        detections = db.get_detections(scan.id) if scan.id else []

        # Prompt text is now stored directly on the scan record
        prompt_text = scan.prompt_text

        return EventData(
            event_id=event_id,
            timestamp=scan.timestamp.isoformat() if scan.timestamp else "",
            severity=scan.highest_severity or "none",
            detections=[
                {
                    "rule_id": d.rule_id,
                    "severity": d.severity,
                    "confidence": d.confidence,
                    "description": d.description or f"{d.category or 'Detection'}: {d.rule_id}",
                    "layer": d.detection_layer,
                }
                for d in detections
            ],
            prompt_hash=scan.prompt_hash or "",
            prompt_length=len(prompt_text) if prompt_text else None,
            scan_duration_ms=scan.total_duration_ms,
            prompt_text=prompt_text,
        )

    except Exception as e:
        logger.debug("Failed to fetch from local history: %s", e)
        return None


def fetch_event_from_portal(event_id: str, show_prompt: bool = False) -> EventData | None:
    """Fetch event data from the RAXE portal API.

    Args:
        event_id: Event ID to look up
        show_prompt: Whether to request full prompt text

    Returns:
        EventData if found, None otherwise

    Raises:
        Exception: If API request fails
    """
    # Get credentials for authentication
    store = CredentialStore()
    credentials = store.load()

    if credentials is None:
        logger.debug("No credentials found, cannot fetch event")
        return None

    # Build API URL
    console_base = get_console_url()
    api_url = f"{console_base}/api/events/{event_id}"

    if show_prompt:
        api_url += "?include_prompt=true"

    logger.debug("Fetching event from: %s", api_url)

    # Make API request
    try:
        req = urllib.request.Request(api_url, method="GET")
        req.add_header("Authorization", f"Bearer {credentials.api_key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "raxe-cli/event-lookup")

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            return EventData.from_api_response(data)

    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.debug("Event not found: %s", event_id)
            return None
        elif e.code == 401:
            logger.warning("Authentication failed for event lookup")
            raise Exception("Authentication failed. Try running: raxe auth login") from e
        elif e.code == 403:
            logger.warning("Access denied for event lookup")
            raise Exception("Access denied. You may not have permission to view this event.") from e
        else:
            raise Exception(f"API request failed with status {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise Exception(f"Network error: {e.reason}") from e


def display_event_rich(event: EventData, show_prompt: bool = False) -> None:
    """Display event details with rich formatting.

    Args:
        event: Event data to display
        show_prompt: Whether to show full prompt text
    """
    severity_lower = event.severity.lower()
    severity_color = SEVERITY_COLORS.get(severity_lower, "white")
    severity_icon = SEVERITY_ICONS.get(severity_lower, "")

    # Calculate relative time
    relative_time = format_relative_time(event.timestamp)
    timestamp_display = event.timestamp
    if relative_time:
        timestamp_display = f"{event.timestamp} ({relative_time})"

    # Build header
    header_text = Text()
    header_text.append("  EVENT DETAILS", style="bold cyan")
    header_text.append("  " * 20)  # Spacer
    header_text.append(f"{event.event_id}", style="cyan dim")

    console.print(Panel(header_text, border_style="cyan", padding=(0, 1)))
    console.print()

    # Event metadata section
    console.print("[bold]  Timestamp:[/bold]    ", end="")
    console.print(f"[white]{timestamp_display}[/white]")

    console.print("[bold]  Severity:[/bold]     ", end="")
    console.print(f"[{severity_color}]{event.severity.upper()}[/{severity_color}] {severity_icon}")

    detection_count = len(event.detections)
    if detection_count == 0:
        console.print("[bold]  Detections:[/bold]   [green]No threats found[/green]")
    else:
        console.print(f"[bold]  Detections:[/bold]   [yellow]{detection_count} threat{'s' if detection_count != 1 else ''} found[/yellow]")

    if event.scan_duration_ms is not None:
        console.print(f"[bold]  Scan Time:[/bold]    [white]{event.scan_duration_ms:.1f}ms[/white]")

    console.print()

    # Separate L1 and L2 detections
    l1_detections = [d for d in event.detections if d.get("layer", "L1") == "L1"]
    l2_detections = [d for d in event.detections if d.get("layer", "L1") == "L2"]

    # L1 Detections table
    if l1_detections:
        console.print(f"[bold blue]  L1 RULE-BASED DETECTIONS[/bold blue] [dim]({len(l1_detections)} rules matched)[/dim]")
        console.print("  " + "-" * 70)

        table = Table(
            show_header=True,
            header_style="bold cyan",
            box=None,
            padding=(0, 1),
        )
        table.add_column("Rule", style="cyan", no_wrap=True, width=10)
        table.add_column("Severity", style="bold", width=10)
        table.add_column("Confidence", justify="right", width=12)
        table.add_column("Description", style="white")

        for detection in l1_detections:
            det_severity = detection.get("severity", "unknown").lower()
            det_color = SEVERITY_COLORS.get(det_severity, "white")
            severity_text = Text(det_severity.upper(), style=det_color)

            confidence = detection.get("confidence", 0)
            confidence_str = f"{confidence * 100:.1f}%" if isinstance(confidence, float) else str(confidence)

            description = detection.get("description", detection.get("message", "-"))
            if len(description) > 60:
                description = description[:57] + "..."

            rule_id = detection.get("rule_id", "-")

            table.add_row(
                rule_id,
                severity_text,
                confidence_str,
                description,
            )

        console.print(table)
        console.print()

    # L2 ML Classification block
    if l2_detections:
        console.print("[bold magenta]  L2 ML CLASSIFICATION[/bold magenta]")
        console.print()

        for detection in l2_detections:
            det_severity = detection.get("severity", "unknown").lower()
            det_color = SEVERITY_COLORS.get(det_severity, "white")

            confidence = detection.get("confidence", 0)
            confidence_pct = f"{confidence * 100:.0f}%" if isinstance(confidence, float) else str(confidence)

            # Extract threat type from rule_id (e.g., "L2-context_manipulation" -> "Context Manipulation")
            rule_id = detection.get("rule_id", "-")
            threat_type = rule_id.replace("L2-", "").replace("_", " ").title()

            # Get the classification/family from description
            description = detection.get("description", "")
            # Parse description like "L2 ML Detection: pi_instruction_override"
            family = ""
            if ":" in description:
                family = description.split(":")[-1].strip()

            # Build the L2 block content using Text with proper styling
            l2_content = Text()

            # Severity icon based on level
            if det_severity == "critical":
                l2_content.append("  🔴 ", style="red bold")
            elif det_severity == "high":
                l2_content.append("  🟠 ", style="red")
            elif det_severity == "medium":
                l2_content.append("  🟡 ", style="yellow")
            else:
                l2_content.append("  🔵 ", style="blue")

            l2_content.append(f"{threat_type}", style=f"{det_color} bold")
            if family:
                l2_content.append(f" ({family})", style="dim")
            l2_content.append("\n")
            l2_content.append(f"  Risk Score: ", style="white")
            l2_content.append(f"{confidence_pct}", style=det_color)
            l2_content.append(f"  •  Severity: ", style="white")
            l2_content.append(f"{det_severity.upper()}", style=det_color)

            console.print(Panel(
                l2_content,
                border_style="magenta",
                padding=(0, 2),
            ))
        console.print()

    # Handle case with no detections
    if not event.detections:
        console.print("[bold cyan]  DETECTIONS[/bold cyan]")
        console.print("  " + "-" * 70)
        console.print("  [green]No threats detected[/green]")
        console.print()

    # Prompt section
    console.print("[bold cyan]  PROMPT[/bold cyan]")
    console.print("  " + "-" * 70)

    # Show prompt length if available
    length_info = f"Length: {event.prompt_length} chars" if event.prompt_length else "Length: unknown"
    hash_info = f"Hash: {event.prompt_hash[:20]}..." if len(event.prompt_hash) > 20 else f"Hash: {event.prompt_hash}"

    console.print(f"  [dim]{length_info} | {hash_info}[/dim]")

    if show_prompt and event.prompt_text:
        console.print()
        console.print("[yellow]  WARNING: Displaying sensitive prompt content[/yellow]")
        console.print()
        # Display prompt in a box for clarity
        console.print(Panel(
            event.prompt_text,
            border_style="yellow",
            title="[yellow]Prompt Content[/yellow]",
            padding=(1, 2),
        ))
    elif show_prompt and not event.prompt_text:
        console.print("  [yellow]Prompt text not available (may not be stored for privacy)[/yellow]")
    else:
        console.print("  [dim]Use --show-prompt to reveal (contains sensitive content)[/dim]")

    console.print()

    # Actions section
    console.print("[bold cyan]  ACTIONS[/bold cyan]")
    console.print("  " + "-" * 70)

    portal_url = f"{get_console_url()}/portal/events/{event.event_id}"
    console.print(f"  [bold]Portal:[/bold]    [blue underline]{portal_url}[/blue underline]")

    # Show suppress command suggestion for detected threats
    if event.detections:
        first_rule_id = event.detections[0].get("rule_id", "RULE_ID")
        console.print(f'  [bold]Suppress:[/bold]  [cyan]raxe suppress add {first_rule_id} --reason "..."[/cyan]')

    console.print()

    # What to do next section for threats
    if detection_count > 0:
        next_steps = Text()
        next_steps.append("\n")
        next_steps.append("What to do next:\n\n", style="bold yellow")
        next_steps.append("  1. ", style="white")
        next_steps.append("Review the detection details above\n", style="dim")
        next_steps.append("  2. ", style="white")
        next_steps.append("Visit the portal link for full analysis\n", style="dim")
        next_steps.append("  3. ", style="white")
        next_steps.append("If false positive, add a suppression rule\n", style="dim")
        next_steps.append("  4. ", style="white")
        next_steps.append("If legitimate threat, investigate the source\n", style="dim")

        console.print(Panel(
            next_steps,
            border_style="yellow",
            padding=(0, 2),
        ))


def display_event_json(event: EventData) -> None:
    """Display event details as JSON.

    Args:
        event: Event data to display
    """
    output = {
        "event_id": event.event_id,
        "timestamp": event.timestamp,
        "severity": event.severity,
        "detections": event.detections,
        "prompt_hash": event.prompt_hash,
        "prompt_length": event.prompt_length,
        "scan_duration_ms": event.scan_duration_ms,
        "portal_url": f"{get_console_url()}/portal/events/{event.event_id}",
    }

    if event.prompt_text:
        output["prompt_text"] = event.prompt_text

    console.print(json.dumps(output, indent=2))


@click.group()
def event() -> None:
    """Look up scan events by ID from the portal.

    Query the RAXE console for detailed event information including
    threat detections, timing, and actionable next steps.

    \b
    Examples:
      raxe event show evt_ae041c39a67744fd
      raxe event show evt_ae041c39a67744fd --show-prompt
      raxe event show evt_ae041c39a67744fd --format json
    """
    pass


@event.command("show")
@click.argument("event_id")
@click.option(
    "--show-prompt",
    is_flag=True,
    help="Reveal full prompt text (WARNING: contains sensitive content)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="rich",
    help="Output format (default: rich)",
)
def show_event(event_id: str, show_prompt: bool, output_format: str) -> None:
    """Show details for a specific scan event.

    Look up an event by its ID (evt_xxx format) and display detailed
    information including detections, timing, and next steps.

    \b
    Arguments:
      EVENT_ID    The event ID to look up (format: evt_{16 hex chars})

    \b
    Examples:
      raxe event show evt_ae041c39a67744fd
      raxe event show evt_ae041c39a67744fd --show-prompt
      raxe event show evt_ae041c39a67744fd --format json
    """
    # Validate event ID format
    if not validate_event_id(event_id):
        display_error(
            "Invalid event ID format",
            f"Expected format: evt_{{16 hex chars}}\n"
            f"Example: evt_ae041c39a67744fd\n"
            f"Received: {event_id}"
        )
        console.print()
        console.print("[dim]Hint: Event IDs are shown in scan output and the portal.[/dim]")
        raise click.Abort()

    # Show warning for --show-prompt
    if show_prompt:
        display_warning(
            "Prompt reveal requested",
            "Full prompt content will be displayed. This may contain sensitive information."
        )
        console.print()

    # Try local lookup first (contains full prompt text for privacy)
    event_data = fetch_event_from_local(event_id)
    source = "local"

    if event_data is None:
        # Fall back to portal lookup
        try:
            event_data = fetch_event_from_portal(event_id, show_prompt=show_prompt)
            source = "portal"
        except Exception as e:
            # Check if this might be a network/auth issue
            error_msg = str(e)
            if "Authentication" in error_msg or "401" in error_msg:
                display_error(
                    "Authentication required",
                    "You need to be logged in to view events.\n"
                    "Run: raxe auth login"
                )
            elif "network" in error_msg.lower() or "url" in error_msg.lower():
                display_error(
                    "Network error",
                    f"Could not connect to the RAXE portal.\n{error_msg}"
                )
            else:
                display_error("Failed to fetch event", error_msg)

            raise click.Abort() from e

    if event_data is None:
        _display_event_not_found(event_id)
        raise click.Abort()

    # Display the event
    if output_format == "json":
        display_event_json(event_data)
    else:
        display_event_rich(event_data, show_prompt=show_prompt)
        _display_privacy_footer(source)

    logger.info("event_show_completed", event_id=event_id, source=source)


def _display_privacy_footer(source: str) -> None:
    """Display privacy footer explaining local-only prompt storage.

    Args:
        source: Where the event was retrieved from ("local" or "portal")
    """
    console.print("[dim]" + "-" * 74 + "[/dim]")
    if source == "local":
        console.print(
            "[dim]  Privacy: Prompt text is stored locally on this device only.[/dim]"
        )
        console.print(
            "[dim]  Use [cyan]raxe event show <event_id> --show-prompt[/cyan] to view it.[/dim]"
        )
    else:
        console.print(
            "[dim]  Privacy: Prompt text is not available - only metadata is sent to the cloud.[/dim]"
        )
        console.print(
            "[dim]  Run the scan locally to store prompts for later retrieval.[/dim]"
        )
    console.print()


def _display_event_not_found(event_id: str) -> None:
    """Display helpful message when event is not found.

    Args:
        event_id: The event ID that was not found
    """
    console.print()
    display_error(
        f"Event not found: {event_id}",
        "The event could not be found. This may be because:"
    )
    console.print()
    console.print("  [dim]1.[/dim] The event ID is incorrect")
    console.print("  [dim]2.[/dim] The event has been deleted or expired")
    console.print("  [dim]3.[/dim] You don't have permission to view this event")
    console.print("  [dim]4.[/dim] The event was created with a different API key")
    console.print()
    console.print("[bold]Suggestions:[/bold]")
    console.print("  - Check scan output for the correct event ID")
    console.print("  - View recent events in the portal: ", end="")
    console.print(f"[blue underline]{get_console_url()}/portal/events[/blue underline]")
    console.print("  - Run a new scan: [cyan]raxe scan \"your text\"[/cyan]")
    console.print()


if __name__ == "__main__":
    event()
