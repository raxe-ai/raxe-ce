"""CLI commands for scan history management."""
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from raxe.infrastructure.database.scan_history import ScanHistoryDB
from raxe.utils.logging import get_logger

logger = get_logger(__name__)
console = Console()


@click.group()
def history() -> None:
    """View and manage scan history."""
    pass


@history.command()
@click.option("--limit", default=20, help="Number of scans to show")
@click.option("--severity", help="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)")
def list_scans(limit: int, severity: str | None) -> None:
    """List recent scans."""
    try:
        db = ScanHistoryDB()
        scans = db.list_scans(limit=limit, severity_filter=severity)

        if not scans:
            console.print("[yellow]No scans found[/yellow]")
            return

        # Create table
        table = Table(title="Recent Scans", show_header=True, header_style="bold cyan")
        table.add_column("ID", style="cyan")
        table.add_column("Timestamp", style="white")
        table.add_column("Threats", style="yellow")
        table.add_column("Severity", style="red")
        table.add_column("Duration (ms)", style="green")

        for scan in scans:
            # Format timestamp
            timestamp_str = scan.timestamp.strftime("%Y-%m-%d %H:%M:%S")

            # Severity with color
            severity_str = scan.highest_severity or "-"
            if scan.highest_severity == "CRITICAL":
                severity_color = "bright_red"
            elif scan.highest_severity == "HIGH":
                severity_color = "red"
            elif scan.highest_severity == "MEDIUM":
                severity_color = "yellow"
            else:
                severity_color = "white"

            table.add_row(
                str(scan.id),
                timestamp_str,
                str(scan.threats_found),
                f"[{severity_color}]{severity_str}[/{severity_color}]",
                f"{scan.total_duration_ms:.2f}" if scan.total_duration_ms else "-",
            )

        console.print(table)

        logger.info("history_list_completed", count=len(scans))

    except Exception as e:
        console.print(f"[red]Error listing scans:[/red] {e}")
        logger.error("history_list_failed", error=str(e))
        raise click.Abort() from e


@history.command()
@click.argument("scan_id", type=int)
def show(scan_id: int) -> None:
    """Show details for a specific scan."""
    try:
        db = ScanHistoryDB()
        scan = db.get_scan(scan_id)

        if not scan:
            console.print(f"[red]Scan {scan_id} not found[/red]")
            raise click.Abort()

        # Show scan info
        console.print(f"\n[bold]Scan #{scan.id}[/bold]")
        console.print(f"Timestamp: {scan.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        console.print(f"Prompt Hash: {scan.prompt_hash}")
        console.print(f"Threats Found: {scan.threats_found}")
        console.print(f"Highest Severity: {scan.highest_severity or 'None'}")

        # Performance metrics
        console.print("\n[bold]Performance:[/bold]")
        if scan.l1_duration_ms:
            console.print(f"  L1 Duration: {scan.l1_duration_ms:.2f} ms")
        if scan.l2_duration_ms:
            console.print(f"  L2 Duration: {scan.l2_duration_ms:.2f} ms")
        if scan.total_duration_ms:
            console.print(f"  Total Duration: {scan.total_duration_ms:.2f} ms")

        # Get detections
        detections = db.get_detections(scan_id)

        if detections:
            console.print(f"\n[bold]Detections ({len(detections)}):[/bold]")

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Rule ID", style="cyan")
            table.add_column("Severity", style="red")
            table.add_column("Confidence", style="yellow")
            table.add_column("Layer", style="green")
            table.add_column("Category", style="white")

            for detection in detections:
                table.add_row(
                    detection.rule_id,
                    detection.severity,
                    f"{detection.confidence:.2f}",
                    detection.detection_layer,
                    detection.category or "-",
                )

            console.print(table)

        logger.info("history_show_completed", scan_id=scan_id)

    except Exception as e:
        console.print(f"[red]Error showing scan:[/red] {e}")
        logger.error("history_show_failed", scan_id=scan_id, error=str(e))
        raise click.Abort() from e


@history.command()
@click.option("--days", default=30, help="Days to analyze")
def stats(days: int) -> None:
    """Show scan statistics."""
    try:
        db = ScanHistoryDB()
        stats = db.get_statistics(days=days)

        console.print(f"\n[bold]Scan Statistics (Last {days} days)[/bold]\n")

        # Summary
        console.print(f"Total Scans: {stats['total_scans']}")
        console.print(f"Scans with Threats: {stats['scans_with_threats']}")
        console.print(f"Threat Rate: {stats['threat_rate']:.1%}")

        # Severity breakdown
        if stats["severity_counts"]:
            console.print("\n[bold]Threats by Severity:[/bold]")
            for severity, count in stats["severity_counts"].items():
                console.print(f"  {severity}: {count}")

        # Performance
        console.print("\n[bold]Average Latencies:[/bold]")
        if stats["avg_l1_duration_ms"]:
            console.print(f"  L1: {stats['avg_l1_duration_ms']:.2f} ms")
        if stats["avg_l2_duration_ms"]:
            console.print(f"  L2: {stats['avg_l2_duration_ms']:.2f} ms")
        if stats["avg_total_duration_ms"]:
            console.print(f"  Total: {stats['avg_total_duration_ms']:.2f} ms")

        logger.info("history_stats_completed", days=days)

    except Exception as e:
        console.print(f"[red]Error getting statistics:[/red] {e}")
        logger.error("history_stats_failed", error=str(e))
        raise click.Abort() from e


@history.command()
@click.argument("scan_id", type=int)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Output file path (default: stdout)",
)
@click.option("--format", type=click.Choice(["json", "csv"]), default="json")
def export(scan_id: int, output: Path | None, output_format: str) -> None:
    """Export scan to JSON or CSV."""
    try:
        db = ScanHistoryDB()

        if output_format == "json":
            data = db.export_to_json(scan_id)
            json_str = json.dumps(data, indent=2)

            if output:
                output.write_text(json_str)
                console.print(f"[green]✓[/green] Exported to {output}")
            else:
                console.print(json_str)

        elif output_format == "csv":
            # Simple CSV export
            scan = db.get_scan(scan_id)
            detections = db.get_detections(scan_id)

            csv_lines = ["scan_id,timestamp,threats_found,highest_severity,duration_ms"]
            csv_lines.append(
                f"{scan.id},{scan.timestamp.isoformat()},{scan.threats_found},"
                f"{scan.highest_severity or ''},{scan.total_duration_ms or ''}"
            )

            csv_lines.append("\nrule_id,severity,confidence,layer,category")
            for d in detections:
                csv_lines.append(
                    f"{d.rule_id},{d.severity},{d.confidence},"
                    f"{d.detection_layer},{d.category or ''}"
                )

            csv_str = "\n".join(csv_lines)

            if output:
                output.write_text(csv_str)
                console.print(f"[green]✓[/green] Exported to {output}")
            else:
                console.print(csv_str)

        logger.info("history_export_completed", scan_id=scan_id, output_format =format)

    except Exception as e:
        console.print(f"[red]Error exporting scan:[/red] {e}")
        logger.error("history_export_failed", scan_id=scan_id, error=str(e))
        raise click.Abort() from e


@history.command()
@click.option("--days", default=90, help="Retention period in days")
@click.confirmation_option(prompt="Delete old scans?")
def clean(days: int) -> None:
    """Clean up old scan history."""
    try:
        db = ScanHistoryDB()
        count = db.cleanup_old_scans(retention_days=days)

        console.print(f"[green]✓[/green] Deleted {count} scans older than {days} days")

        logger.info("history_clean_completed", deleted_count=count, retention_days=days)

    except Exception as e:
        console.print(f"[red]Error cleaning history:[/red] {e}")
        logger.error("history_clean_failed", error=str(e))
        raise click.Abort() from e
