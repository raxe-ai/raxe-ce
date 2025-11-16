"""
Rich output formatting utilities for RAXE CLI.

Provides beautiful, colored terminal output for scan results and other CLI commands.
"""

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from raxe.domain.rules.models import Severity
from raxe.sdk.client import ScanPipelineResult

# Global console instance
console = Console()


# Severity color mapping
SEVERITY_COLORS = {
    Severity.CRITICAL: "red bold",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "blue",
    Severity.INFO: "green",
}

SEVERITY_ICONS = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🔵",
    Severity.INFO: "🟢",
}


def get_severity_color(severity: Severity) -> str:
    """Get rich color string for severity level."""
    return SEVERITY_COLORS.get(severity, "white")


def get_severity_icon(severity: Severity) -> str:
    """Get icon for severity level."""
    return SEVERITY_ICONS.get(severity, "⚪")


def display_scan_result(result: ScanPipelineResult, no_color: bool = False) -> None:
    """
    Display scan result with rich formatting.

    Args:
        result: Scan pipeline result from Raxe client
        no_color: Disable colored output
    """
    if no_color:
        console = Console(no_color=True, force_terminal=False)
    else:
        console = Console()

    if result.scan_result.has_threats:
        _display_threat_detected(result, console)
    else:
        _display_safe(result, console)


def _display_threat_detected(result: ScanPipelineResult, console: Console) -> None:
    """Display threat detection results."""
    # Header
    highest = result.scan_result.combined_severity
    icon = get_severity_icon(highest)
    color = get_severity_color(highest)

    header = Text()
    header.append(f"{icon} ", style=color)
    header.append("THREAT DETECTED", style=f"{color} bold")

    console.print(Panel(header, border_style=color))
    console.print()

    # Detections table
    table = Table(title="Detection Details", show_header=True, header_style="bold cyan")
    table.add_column("Rule ID", style="cyan", no_wrap=True)
    table.add_column("Severity", style="bold")
    table.add_column("Confidence", justify="right")
    table.add_column("Message", style="white")

    for detection in result.scan_result.l1_result.detections:
        severity_color = get_severity_color(detection.severity)
        severity_text = Text(detection.severity.value.upper(), style=severity_color)

        # Format confidence as percentage
        confidence_pct = f"{detection.confidence * 100:.1f}%"

        # Message
        message = getattr(detection, "message", "No description available")

        table.add_row(detection.rule_id, severity_text, confidence_pct, message)

    console.print(table)
    console.print()

    # Summary
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Total detections: {len(result.scan_result.l1_result.detections)}")
    console.print(f"  Highest severity: [{get_severity_color(highest)}]{highest.value}[/]")
    console.print(f"  Scan time: {result.duration_ms:.2f}ms")
    console.print()


def _display_safe(result: ScanPipelineResult, console: Console) -> None:
    """Display safe scan results."""
    # Header
    header = Text()
    header.append("🟢 ", style="green")
    header.append("SAFE", style="green bold")

    console.print(Panel(header, border_style="green"))
    console.print()
    console.print("[green]No threats detected[/green]")
    console.print(f"  Scan time: {result.duration_ms:.2f}ms")
    console.print()


def display_stats(stats: dict[str, Any]) -> None:
    """
    Display statistics in a formatted table.

    Args:
        stats: Statistics dictionary from Raxe client
    """
    table = Table(title="RAXE Statistics", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", justify="right", style="white")

    for key, value in stats.items():
        # Format key nicely
        display_key = key.replace("_", " ").title()
        table.add_row(display_key, str(value))

    console.print(table)
    console.print()


def create_progress_bar(description: str) -> Progress:
    """
    Create a rich progress bar for long operations.

    Args:
        description: Description of the operation

    Returns:
        Progress bar instance
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )


def display_error(message: str, details: str | None = None) -> None:
    """
    Display an error message with rich formatting.

    Args:
        message: Error message
        details: Optional error details
    """
    error_text = Text()
    error_text.append("❌ ", style="red bold")
    error_text.append("ERROR", style="red bold")

    console.print(Panel(error_text, border_style="red"))
    console.print()
    console.print(f"[red]{message}[/red]")

    if details:
        console.print()
        console.print("[dim]Details:[/dim]")
        console.print(f"[dim]{details}[/dim]")

    console.print()


def display_success(message: str, details: str | None = None) -> None:
    """
    Display a success message with rich formatting.

    Args:
        message: Success message
        details: Optional success details
    """
    success_text = Text()
    success_text.append("✓ ", style="green bold")
    success_text.append(message, style="green")

    console.print(success_text)

    if details:
        console.print(f"[dim]{details}[/dim]")

    console.print()


def display_warning(message: str, details: str | None = None) -> None:
    """
    Display a warning message with rich formatting.

    Args:
        message: Warning message
        details: Optional warning details
    """
    warning_text = Text()
    warning_text.append("⚠️  ", style="yellow bold")
    warning_text.append(message, style="yellow")

    console.print(warning_text)

    if details:
        console.print(f"[dim]{details}[/dim]")

    console.print()


def display_info(message: str, details: str | None = None) -> None:
    """
    Display an info message with rich formatting.

    Args:
        message: Info message
        details: Optional info details
    """
    info_text = Text()
    info_text.append("ℹ️  ", style="blue bold")
    info_text.append(message, style="blue")

    console.print(info_text)

    if details:
        console.print(f"[dim]{details}[/dim]")

    console.print()
