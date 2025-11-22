"""
RAXE export command - Export scan history.
"""

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click

from raxe.cli.output import console, create_progress_bar, display_error, display_success


@click.command()
@click.option(
    "--format",
    type=click.Choice(["json", "csv"]),
    default="json",
    help="Output format (default: json)",
)
@click.option(
    "--output",
    type=click.Path(),
    help="Output file path (default: raxe_export.{format})",
)
@click.option(
    "--days",
    type=int,
    default=30,
    help="Days of history to export (default: 30)",
)
def export(output_format: str, output: str | None, days: int) -> None:
    """
    Export scan history to JSON or CSV.

    Exports local scan history including:
      - Scan timestamps
      - Detection results
      - Severity levels
      - Rule matches

    \b
    Examples:
      raxe export
      raxe export --format csv --output scans.csv
      raxe export --days 7 --format json
    """
    from raxe.cli.branding import print_logo

    # Show compact logo
    print_logo(console, compact=True)
    console.print()

    try:
        # Determine output file
        if output is None:
            output = f"raxe_export.{format}"

        output_path = Path(output)

        console.print(f"[cyan]Exporting {days} days of scan history...[/cyan]")
        console.print()

        # Load scan history (placeholder - will integrate with actual database)
        data = _load_scan_history(days)

        if not data:
            console.print("[yellow]No scan history found for the specified period[/yellow]")
            console.print()
            return

        # Export based on format
        with create_progress_bar("Exporting...") as progress:
            task = progress.add_task("Processing...", total=len(data))

            if output_format == "json":
                _export_json(output_path, data, progress, task)
            else:
                _export_csv(output_path, data, progress, task)

        console.print()
        display_success(
            f"Exported {len(data)} scans to {output_path}",
            f"Format: {format.upper()}, Period: {days} days",
        )

    except Exception as e:
        display_error("Export failed", str(e))
        raise click.Abort() from e


def _load_scan_history(days: int) -> list[dict]:
    """
    Load scan history from local database.

    Args:
        days: Number of days to look back

    Returns:
        List of scan records
    """
    # Placeholder implementation
    # In production, this would query the SQLite database
    # For now, return sample data

    datetime.now(timezone.utc) - timedelta(days=days)

    # TODO: Integrate with actual telemetry database
    # from raxe.infrastructure.telemetry.queue import TelemetryQueue
    # queue = TelemetryQueue()
    # return queue.get_history(since=cutoff_date)

    # Sample data for demonstration
    sample_data = [
        {
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
            "prompt_hash": f"hash_{i}",
            "has_threats": i % 3 == 0,
            "detection_count": 1 if i % 3 == 0 else 0,
            "highest_severity": "high" if i % 3 == 0 else "none",
            "duration_ms": 5.2 + (i * 0.1),
        }
        for i in range(min(10, days))  # Limit sample data
    ]

    return sample_data


def _export_json(output_path: Path, data: list[dict], progress, task) -> None:
    """
    Export data to JSON format.

    Args:
        output_path: Output file path
        data: Scan history data
        progress: Progress bar instance
        task: Progress task ID
    """
    with output_path.open("w") as f:
        json.dump(
            {
                "exported_at": datetime.now().isoformat(),
                "record_count": len(data),
                "scans": data,
            },
            f,
            indent=2,
        )
        progress.update(task, completed=len(data))


def _export_csv(output_path: Path, data: list[dict], progress, task) -> None:
    """
    Export data to CSV format.

    Args:
        output_path: Output file path
        data: Scan history data
        progress: Progress bar instance
        task: Progress task ID
    """
    if not data:
        return

    # Get all unique keys from data
    fieldnames = set()
    for record in data:
        fieldnames.update(record.keys())

    fieldnames = sorted(fieldnames)

    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i, record in enumerate(data):
            writer.writerow(record)
            progress.update(task, completed=i + 1)


if __name__ == "__main__":
    export()
