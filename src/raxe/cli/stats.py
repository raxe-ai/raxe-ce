"""
RAXE stats command - Show local statistics and analytics.
"""

import json
from datetime import datetime, timedelta, timezone

import click

from raxe.cli.output import console, display_error
from raxe.infrastructure.analytics.aggregator import DataAggregator
from raxe.infrastructure.analytics.engine import AnalyticsEngine
from raxe.infrastructure.analytics.streaks import StreakTracker
from raxe.utils.error_sanitizer import sanitize_error_message


@click.command()
@click.option(
    "--format",
    "output_format",  # Map --format to output_format parameter
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--global",
    "show_global",
    is_flag=True,
    help="Show global platform statistics",
)
@click.option(
    "--retention",
    is_flag=True,
    help="Show retention analysis for your cohort",
)
@click.option(
    "--export",
    type=click.Path(),
    help="Export stats to JSON file",
)
def stats(output_format: str, show_global: bool, retention: bool, export: str | None) -> None:
    """
    Show local RAXE statistics and analytics.

    Displays comprehensive statistics about your RAXE usage including:
      - Scan history and performance metrics
      - Threat detection statistics
      - Engagement streaks and achievements
      - Global community statistics (--global)
      - Retention analysis (--retention)

    \b
    Examples:
      raxe stats                    # Show your statistics
      raxe stats --global           # Show global platform stats
      raxe stats --retention        # Show retention analysis
      raxe stats --format json      # Output as JSON
      raxe stats --export stats.json # Export to file
    """
    # Show compact logo for text output
    if output_format == "text":
        from raxe.cli.branding import print_logo
        print_logo(console, compact=True)
        console.print()

    try:
        # Initialize analytics components
        engine = AnalyticsEngine()
        aggregator = DataAggregator()
        streak_tracker = StreakTracker()

        # Get installation ID (use a stable identifier)
        # In production, this would come from installation tracking
        installation_id = _get_installation_id()

        if show_global:
            # Show global statistics
            stats_data = engine.get_global_stats()
            if output_format == "json":
                console.print_json(data=stats_data)
            else:
                _display_global_stats(stats_data)
        elif retention:
            # Show retention analysis
            # Use installation date's cohort (simplified - use 30 days ago)
            cohort_date = (datetime.now().date() - timedelta(days=30))
            retention_data = engine.calculate_retention(cohort_date)
            if output_format == "json":
                console.print_json(data=retention_data)
            else:
                _display_retention_stats(retention_data)
        else:
            # Show user-specific statistics
            user_stats = engine.get_user_stats(installation_id)
            streak_info = streak_tracker.get_streak_info()
            progress = streak_tracker.get_progress_summary()
            unlocked = streak_tracker.get_unlocked_achievements()

            stats_data = {
                "user": {
                    "installation_id": user_stats.installation_id,
                    "installation_date": user_stats.installation_date.isoformat() if user_stats.installation_date else None,
                    "time_to_first_scan_seconds": user_stats.time_to_first_scan_seconds,
                    "total_scans": user_stats.total_scans,
                    "threats_detected": user_stats.threats_detected,
                    "detection_rate": user_stats.detection_rate,
                    "last_scan": user_stats.last_scan.isoformat() if user_stats.last_scan else None,
                    "avg_scan_time_ms": user_stats.avg_scan_time_ms,
                    "l1_detections": user_stats.l1_detections,
                    "l2_detections": user_stats.l2_detections
                },
                "streaks": streak_info,
                "achievements": {
                    "progress": progress,
                    "unlocked": [a.to_dict() for a in unlocked]
                }
            }

            if export:
                # Export to file
                with open(export, 'w') as f:
                    json.dump(stats_data, f, indent=2)
                console.print(f"[green]Stats exported to {export}[/green]")
            elif output_format == "json":
                console.print_json(data=stats_data)
            else:
                _display_user_stats(user_stats, streak_info, progress, unlocked)

        # Clean up
        engine.close()
        aggregator.close()

    except Exception as e:
        display_error("Failed to retrieve statistics", sanitize_error_message(e))
        raise click.Abort() from e


def _get_installation_id() -> str:
    """
    Get stable installation ID.

    In production, this would be tracked during installation.
    For now, generate a consistent ID based on machine.
    """
    import hashlib
    import platform

    # Create a stable ID from machine info
    machine_info = f"{platform.node()}-{platform.machine()}"
    return hashlib.sha256(machine_info.encode()).hexdigest()[:16]


def _display_user_stats(user_stats, streak_info: dict, progress: dict, unlocked: list) -> None:
    """Display user statistics in text format."""
    console.print()
    console.print("[bold cyan]📊 Your RAXE Statistics[/bold cyan]")
    console.print()

    # Installation info
    console.print("[bold]Installation[/bold]")
    if user_stats.installation_date:
        # Ensure both datetimes are timezone-aware for correct comparison
        now = datetime.now(timezone.utc)
        install_date = user_stats.installation_date
        if install_date.tzinfo is None:
            # If install_date is naive, assume UTC
            install_date = install_date.replace(tzinfo=timezone.utc)

        days_installed = (now - install_date).days
        console.print(f"  └─ Installed: {days_installed} days ago ({user_stats.installation_date.date()})")
    else:
        console.print("  └─ Installed: Unknown")

    if user_stats.time_to_first_scan_seconds is not None:
        console.print(f"  └─ Time to first scan: {user_stats.time_to_first_scan_seconds:.0f} seconds ⚡")
    console.print()

    # Usage statistics
    console.print("[bold]Usage[/bold]")
    console.print(f"  └─ Total scans: {user_stats.total_scans:,}")
    console.print(f"  └─ Threats detected: {user_stats.threats_detected} ({user_stats.detection_rate:.1f}%)")
    if user_stats.last_scan:
        # Ensure both datetimes are timezone-aware for correct comparison
        now = datetime.now(timezone.utc)
        last_scan = user_stats.last_scan
        if last_scan.tzinfo is None:
            # If last_scan is naive, assume UTC
            last_scan = last_scan.replace(tzinfo=timezone.utc)

        last_scan_ago = now - last_scan
        if last_scan_ago.days > 0:
            console.print(f"  └─ Last scan: {last_scan_ago.days} days ago")
        elif last_scan_ago.seconds > 3600:
            console.print(f"  └─ Last scan: {last_scan_ago.seconds // 3600} hours ago")
        else:
            console.print(f"  └─ Last scan: {last_scan_ago.seconds // 60} minutes ago")
    console.print()

    # Streak info
    console.print("[bold]Streak[/bold]")
    current_streak = streak_info.get("current_streak", 0)
    longest_streak = streak_info.get("longest_streak", 0)

    if current_streak > 0:
        console.print(f"  └─ Current: {current_streak} days 🔥")
    else:
        console.print("  └─ Current: 0 days (start scanning to build your streak!)")

    console.print(f"  └─ Longest: {longest_streak} days")
    console.print()

    # Performance
    console.print("[bold]Performance[/bold]")
    console.print(f"  └─ Avg scan time: {user_stats.avg_scan_time_ms:.1f}ms")
    console.print(f"  └─ L1 detections: {user_stats.l1_detections}")
    console.print(f"  └─ L2 detections: {user_stats.l2_detections}")
    console.print()

    # Achievements
    console.print("[bold]Achievements[/bold]")
    console.print(f"  └─ Unlocked: {progress['unlocked']}/{progress['total_achievements']} ({progress['completion_percentage']:.0f}%)")
    console.print(f"  └─ Total points: {progress['total_points']}")

    if unlocked:
        console.print()
        console.print("  [dim]Recent unlocks:[/dim]")
        for achievement in unlocked[:3]:  # Show last 3
            console.print(f"    {achievement.icon} {achievement.name}")
    console.print()


def _display_global_stats(stats_data: dict) -> None:
    """Display global statistics in text format."""
    console.print()
    console.print("[bold cyan]🌍 RAXE Global Statistics[/bold cyan]")
    console.print()

    # Community
    community = stats_data.get("community", {})
    console.print("[bold]Community[/bold]")
    console.print(f"  └─ Total users: {community.get('total_users', 0):,}")
    console.print(f"  └─ Active this week: {community.get('active_this_week', 0):,}")
    console.print(f"  └─ Scans performed: {community.get('total_scans', 0):,}")
    console.print()

    # Threats
    threats = stats_data.get("threats", {})
    console.print("[bold]Threats Detected[/bold]")
    console.print(f"  └─ Total: {threats.get('total_detected', 0):,} ({threats.get('detection_rate', 0):.1f}%)")
    console.print(f"  └─ Critical threats: {threats.get('critical_threats', 0):,}")

    severity_breakdown = threats.get("by_severity", {})
    if severity_breakdown:
        console.print("  └─ By severity:")
        for severity, count in severity_breakdown.items():
            console.print(f"      • {severity.capitalize()}: {count:,}")
    console.print()

    # Performance
    performance = stats_data.get("performance", {})
    console.print("[bold]Performance[/bold]")
    console.print(f"  └─ Avg scan time: {performance.get('avg_scan_time_ms', 0):.1f}ms")
    console.print(f"  └─ P95 latency: {performance.get('p95_latency_ms', 0):.1f}ms")
    console.print()


def _display_retention_stats(retention_data: dict) -> None:
    """Display retention statistics in text format."""
    console.print()
    console.print("[bold cyan]📈 Retention Analysis[/bold cyan]")
    console.print()

    cohort_date = retention_data.get("cohort_date")
    cohort_size = retention_data.get("cohort_size", 0)

    console.print(f"[bold]Your Cohort (Installed {cohort_date})[/bold]")
    console.print(f"  └─ Cohort size: {cohort_size:,} users")
    console.print()

    if cohort_size > 0:
        console.print("[bold]Retention Rates[/bold]")
        console.print(f"  └─ Day 1: {retention_data.get('day_1', 0):.1f}%")
        console.print(f"  └─ Day 7: {retention_data.get('day_7', 0):.1f}%")
        console.print(f"  └─ Day 30: {retention_data.get('day_30', 0):.1f}%")
    else:
        console.print("[yellow]No data available for this cohort[/yellow]")

    console.print()


if __name__ == "__main__":
    stats()
