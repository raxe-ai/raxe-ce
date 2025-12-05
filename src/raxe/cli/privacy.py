"""
Privacy information and data handling details for RAXE CLI.

Displays RAXE's privacy guarantees and user data handling practices.
"""

import click
from rich.console import Console
from rich.text import Text


@click.command("privacy")
def privacy_command():
    """Show RAXE privacy guarantees and data handling."""
    console = Console()

    # Title
    title = Text()
    title.append("🔒 ", style="cyan bold")
    title.append("RAXE Privacy Guarantees", style="cyan bold")
    console.print()
    console.print(title)
    console.print()

    # Data Handling Section
    console.print("[bold cyan]Data Handling:[/bold cyan]")
    console.print("  [green]✓[/green] Prompts hashed with SHA-256 (never stored as plaintext)")
    console.print("  [green]✓[/green] Only hashes and metadata logged locally")
    console.print("  [green]✓[/green] No data transmitted to external servers")
    console.print("  [green]✓[/green] Telemetry sends: rule IDs, timings, severity (NO prompt content)")
    console.print()

    # Local Storage Section
    console.print("[bold cyan]Local Storage:[/bold cyan]")
    console.print("  Scan history: ~/.raxe/scan_history.db (hashes only)")
    console.print("  Logs: ~/.raxe/logs/ (PII auto-redacted)")
    console.print()

    # Controls Section
    console.print("[bold cyan]Controls:[/bold cyan]")
    console.print("  Disable telemetry: [cyan]raxe init --no-telemetry[/cyan]")
    console.print("  Clear history: [cyan]raxe history clear[/cyan]")
    console.print("  View logs: [cyan]cat ~/.raxe/logs/latest.log[/cyan]")
    console.print()

    # What RAXE Never Collects
    console.print("[bold cyan]What RAXE Never Collects:[/bold cyan]")
    warning_items = [
        "Plaintext prompts or user input",
        "Personal identifiable information (PII)",
        "User credentials or API keys",
        "Complete system configuration",
        "Geographic location data",
    ]
    for item in warning_items:
        console.print(f"  [red]✗[/red] {item}")
    console.print()

    # Privacy Best Practices
    console.print("[bold cyan]Privacy Best Practices:[/bold cyan]")
    practices = [
        "Review logs regularly: cat ~/.raxe/logs/latest.log",
        "Disable telemetry if you prefer no external communication",
        "Clear scan history before sharing your machine",
        "Use --no-color flag if storing output in non-terminal formats",
    ]
    for i, practice in enumerate(practices, 1):
        console.print(f"  {i}. {practice}")
    console.print()

    # Data Retention
    console.print("[bold cyan]Data Retention:[/bold cyan]")
    console.print("  Hashes in database: Indefinite (until manually cleared)")
    console.print("  Logs: Rotated every 7 days (old logs auto-deleted)")
    console.print("  Telemetry: No long-term retention (30-day retention policy)")
    console.print()

    # Compliance Notice
    compliance = Text()
    compliance.append("ℹ️  ", style="blue")
    compliance.append("For more information about RAXE's privacy practices, visit: ", style="dim")
    compliance.append("https://docs.raxe.ai/privacy", style="blue underline")
    console.print(compliance)
    console.print()
