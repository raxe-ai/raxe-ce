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

from raxe.cli.l2_formatter import L2ResultFormatter
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


def display_scan_result(result: ScanPipelineResult, no_color: bool = False, explain: bool = False) -> None:
    """
    Display scan result with rich formatting.

    Args:
        result: Scan pipeline result from Raxe client
        no_color: Disable colored output
        explain: Show detailed explanations for detections (default: False)
    """
    if no_color:
        console = Console(no_color=True, force_terminal=False)
    else:
        console = Console()

    if result.scan_result.has_threats:
        _display_threat_detected(result, console, explain=explain)
    else:
        _display_safe(result, console)

    # Add privacy footer (always visible)
    _display_privacy_footer(console)


def _display_threat_detected(result: ScanPipelineResult, console: Console, explain: bool = False) -> None:
    """Display threat detection results.

    Args:
        result: Scan pipeline result
        console: Rich console instance
        explain: Show detailed explanations for detections (default: False)
    """
    # Header
    highest = result.scan_result.combined_severity
    icon = get_severity_icon(highest)
    color = get_severity_color(highest)

    header = Text()
    header.append(f"{icon} ", style=f"{color} bold")
    header.append("THREAT DETECTED", style=f"{color} bold")

    console.print(Panel(header, border_style=color, width=80, padding=(0, 1)))
    console.print()

    # Detections table with modern styling
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        box=None,  # Cleaner look without box
        padding=(0, 1)
    )
    table.add_column("Rule", style="cyan", no_wrap=True, width=14)
    table.add_column("Severity", style="bold", width=10)
    table.add_column("Confidence", justify="right", width=12)
    table.add_column("Description", style="white")

    # Add L1 detections
    for detection in result.scan_result.l1_result.detections:
        severity_color = get_severity_color(detection.severity)
        severity_text = Text(detection.severity.value.upper(), style=severity_color)

        # Format confidence as percentage
        confidence_pct = f"{detection.confidence * 100:.1f}%"

        # Message - truncate if too long, include flag indicator
        message = getattr(detection, "message", "No description available")
        is_flagged = getattr(detection, "is_flagged", False)
        suppression_reason = getattr(detection, "suppression_reason", None)

        if is_flagged:
            # Show flag indicator for flagged detections
            message = f"[FLAG] {message}"
            if suppression_reason:
                message = f"{message} (flagged: {suppression_reason})"
        if len(message) > 60:
            message = message[:57] + "..."

        # Add flag indicator to rule column if flagged
        rule_display = detection.rule_id
        if is_flagged:
            rule_display = f"[yellow]{detection.rule_id}[/yellow]"

        table.add_row(rule_display, severity_text, confidence_pct, message)

    # Add L2 predictions
    if result.scan_result.l2_result and result.scan_result.l2_result.has_predictions:
        for prediction in result.scan_result.l2_result.predictions:
            # Map L2 confidence to severity (simple heuristic)
            if prediction.confidence >= 0.8:
                pred_severity = Severity.HIGH
            elif prediction.confidence >= 0.6:
                pred_severity = Severity.MEDIUM
            else:
                pred_severity = Severity.LOW

            severity_color = get_severity_color(pred_severity)
            severity_text = Text(pred_severity.value.upper(), style=severity_color)

            # Format confidence as percentage
            confidence_pct = f"{prediction.confidence * 100:.1f}%"

            # Use threat type as rule ID and explanation as message
            rule_id = f"L2-{prediction.threat_type.value}"
            message = prediction.explanation or f"{prediction.threat_type.value} detected"
            if len(message) > 60:
                message = message[:57] + "..."

            table.add_row(rule_id, severity_text, confidence_pct, message)

    console.print(table)
    console.print()

    # Display detailed L1 explanations only if --explain flag is used
    if explain:
        _display_detection_explanations(result.scan_result.l1_result.detections, console)

    # Display L2 ML detection details with hierarchical scoring
    # In explain mode, show L2 analysis even when below threshold
    if result.scan_result.l2_result:
        has_predictions = result.scan_result.l2_result.has_predictions
        if has_predictions or explain:
            formatter = L2ResultFormatter()
            formatter.format_predictions(
                result.scan_result.l2_result,
                console,
                explain=explain,
                show_below_threshold=explain and not has_predictions,
            )

    # Summary with cleaner layout
    total_detections = len(result.scan_result.l1_result.detections)
    if result.scan_result.l2_result:
        total_detections += len(result.scan_result.l2_result.predictions)

    summary = Text()
    summary.append("Summary: ", style="bold")
    summary.append(f"{total_detections} detection(s) • ", style="")
    summary.append("Severity: ", style="dim")
    summary.append(f"{highest.value.upper()}", style=get_severity_color(highest))
    summary.append(f" • Scan time: {result.duration_ms:.2f}ms", style="dim")

    console.print(summary)
    console.print()


def _display_safe(result: ScanPipelineResult, console: Console) -> None:
    """Display safe scan results."""
    # Create content with scan details
    content = Text()
    content.append("🟢 ", style="green bold")
    content.append("SAFE", style="green bold")
    content.append("\n\n", style="")
    content.append("No threats detected", style="green")
    content.append("\n", style="")
    content.append(f"Scan time: {result.duration_ms:.2f}ms", style="dim")

    console.print(Panel(
        content,
        border_style="green",
        width=80,
        padding=(1, 2)
    ))
    console.print()


def _display_detection_explanations(detections: list, console: Console) -> None:
    """Display detailed explanations for each detection.

    Args:
        detections: List of Detection objects
        console: Rich console instance
    """
    for detection in detections:
        # Only show explanations if at least one field is populated
        has_explanation = (
            getattr(detection, 'risk_explanation', '') or
            getattr(detection, 'remediation_advice', '') or
            getattr(detection, 'docs_url', '')
        )

        if not has_explanation:
            continue

        # Create explanation panel
        explanation_content = Text()

        # Rule header
        explanation_content.append(f"\n{detection.rule_id}", style="cyan bold")
        explanation_content.append(f" - {detection.severity.value.upper()}\n\n", style=get_severity_color(detection.severity))

        # Risk explanation
        risk_explanation = getattr(detection, 'risk_explanation', '')
        if risk_explanation:
            explanation_content.append("Why This Matters:\n", style="yellow bold")
            explanation_content.append(f"{risk_explanation}\n\n", style="white")

        # Remediation advice
        remediation_advice = getattr(detection, 'remediation_advice', '')
        if remediation_advice:
            explanation_content.append("What To Do:\n", style="green bold")
            explanation_content.append(f"{remediation_advice}\n\n", style="white")

        # Documentation URL
        docs_url = getattr(detection, 'docs_url', '')
        if docs_url:
            explanation_content.append("Learn More: ", style="blue bold")
            explanation_content.append(f"{docs_url}\n", style="blue underline")

        console.print(Panel(
            explanation_content,
            border_style="dim",
            width=80,
            padding=(1, 2),
            title="Detection Details",
            title_align="left"
        ))
        console.print()


def _display_privacy_footer(console: Console) -> None:
    """Display privacy guarantee footer."""
    privacy_text = Text()
    privacy_text.append("🔒 ", style="cyan")
    privacy_text.append(
        "Your data stayed private - scanned locally, nothing sent to cloud.",
        style="cyan"
    )
    console.print(privacy_text)
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

    console.print(Panel(error_text, border_style="red", width=80, padding=(0, 1)))
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
