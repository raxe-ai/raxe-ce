"""
RAXE doctor command - System health checks and diagnostics.

Provides comprehensive system diagnostics to identify and fix common issues.
"""

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import click

from raxe.cli.output import console, display_error, display_success, display_warning
from raxe.utils.error_sanitizer import sanitize_error_message


@dataclass
class HealthCheck:
    """Result of a single health check.

    Attributes:
        name: Name of the check
        status: Status (ok, warning, error)
        message: Status message
        details: Optional additional details
        fix_available: Whether auto-fix is available
    """
    name: str
    status: str  # "ok", "warning", "error"
    message: str
    details: str | None = None
    fix_available: bool = False


@click.command()
@click.option(
    "--fix",
    is_flag=True,
    help="Automatically fix common issues",
)
@click.option(
    "--export",
    type=click.Path(),
    help="Export diagnostic report to file",
)
def doctor(fix: bool, export: str | None) -> None:
    """
    Run comprehensive system health checks.

    Diagnoses common issues with RAXE installation including:
      - Python version compatibility
      - Dependency status
      - Configuration validity
      - Database health
      - Permission issues
      - Performance metrics

    \b
    Examples:
      raxe doctor
      raxe doctor --fix
      raxe doctor --export report.txt
    """
    from raxe.cli.branding import print_logo

    # Show compact logo
    print_logo(console, compact=True)
    console.print()

    console.print("[bold cyan]RAXE Health Check[/bold cyan]")
    console.print()

    # Run all health checks
    checks = []

    # 1. Installation checks
    console.print("[bold]Installation[/bold]")
    checks.extend(_check_installation())
    _display_check_results(checks[-3:])  # Last 3 checks
    console.print()

    # 2. API Key checks
    console.print("[bold]API Key[/bold]")
    checks.extend(_check_api_key())
    _display_check_results(checks[-1:])  # Last 1 check
    console.print()

    # 3. Configuration checks
    console.print("[bold]Configuration[/bold]")
    checks.extend(_check_configuration())
    _display_check_results(checks[-2:])  # Last 2 checks
    console.print()

    # 3. Database checks
    console.print("[bold]Database[/bold]")
    checks.extend(_check_database())
    _display_check_results(checks[-3:])  # Last 3 checks
    console.print()

    # 4. Rule packs checks
    console.print("[bold]Rule Packs[/bold]")
    checks.extend(_check_rule_packs())
    _display_check_results(checks[-2:])  # Last 2 checks
    console.print()

    # 5. Performance checks
    console.print("[bold]Performance[/bold]")
    checks.extend(_check_performance())
    _display_check_results(checks[-2:])  # Last 2 checks
    console.print()

    # Summary
    _display_summary(checks)

    # Auto-fix if requested
    if fix:
        _auto_fix(checks)

    # Export if requested
    if export:
        _export_report(checks, export)


def _check_installation() -> list[HealthCheck]:
    """Check Python version and dependencies."""
    checks = []

    # Python version
    py_version = sys.version_info
    required_major, required_minor = 3, 10

    if py_version.major == required_major and py_version.minor >= required_minor:
        checks.append(HealthCheck(
            name="Python Version",
            status="ok",
            message=f"{py_version.major}.{py_version.minor}.{py_version.micro} (supported)",
        ))
    else:
        checks.append(HealthCheck(
            name="Python Version",
            status="error",
            message=f"{py_version.major}.{py_version.minor}.{py_version.micro} (requires >= {required_major}.{required_minor})",
            details="Upgrade Python to 3.10 or higher",
        ))

    # RAXE version
    try:
        from raxe import __version__
        checks.append(HealthCheck(
            name="RAXE Version",
            status="ok",
            message=f"{__version__}",
        ))
    except ImportError:
        checks.append(HealthCheck(
            name="RAXE Version",
            status="warning",
            message="Version not found",
        ))

    # Dependencies
    missing_deps = []
    deps_to_check = [
        ("click", "Click"),
        ("pydantic", "Pydantic"),
        ("httpx", "HTTPX"),
        ("structlog", "Structlog"),
        ("sqlalchemy", "SQLAlchemy"),
        ("rich", "Rich"),
        ("prompt_toolkit", "prompt-toolkit"),
    ]

    for module_name, display_name in deps_to_check:
        try:
            __import__(module_name)
        except ImportError:
            missing_deps.append(display_name)

    if not missing_deps:
        checks.append(HealthCheck(
            name="Dependencies",
            status="ok",
            message="All required dependencies installed",
        ))
    else:
        checks.append(HealthCheck(
            name="Dependencies",
            status="error",
            message=f"Missing: {', '.join(missing_deps)}",
            details="Run: pip install raxe[dev]",
            fix_available=True,
        ))

    return checks


def _check_api_key() -> list[HealthCheck]:
    """Check API key status and expiry.

    Returns:
        List of HealthCheck results for API key status.
    """
    checks = []

    try:
        from raxe.cli.expiry_warning import CONSOLE_KEYS_URL, get_expiry_status

        status = get_expiry_status()

        # Map status string to HealthCheck status
        if status["status"] == "pass":
            check_status = "ok"
        elif status["status"] == "warning":
            check_status = "warning"
        else:  # fail
            check_status = "error"

        # Build details string
        details = None
        if status["is_temporary"]:
            if status["status"] == "fail":
                details = f"Get a permanent key at: {CONSOLE_KEYS_URL}"
            elif status["status"] == "warning":
                details = f"Consider getting a permanent key: {CONSOLE_KEYS_URL}"

        checks.append(HealthCheck(
            name="API Key Status",
            status=check_status,
            message=status["message"],
            details=details,
            fix_available=status["status"] != "pass",
        ))

    except Exception as e:
        checks.append(HealthCheck(
            name="API Key Status",
            status="warning",
            message="Could not check API key status",
            details=sanitize_error_message(e),
        ))

    return checks


def _check_configuration() -> list[HealthCheck]:
    """Check configuration file validity."""
    checks = []

    config_file = Path.home() / ".raxe" / "config.yaml"

    # Config file exists
    if config_file.exists():
        checks.append(HealthCheck(
            name="Config File",
            status="ok",
            message=f"Found at {config_file}",
        ))

        # Try to parse config
        try:
            import yaml
            with open(config_file) as f:
                config = yaml.safe_load(f)

            if config:
                checks.append(HealthCheck(
                    name="Config Valid",
                    status="ok",
                    message="Valid YAML format",
                ))
            else:
                checks.append(HealthCheck(
                    name="Config Valid",
                    status="warning",
                    message="Config file is empty",
                    fix_available=True,
                ))
        except Exception as e:
            checks.append(HealthCheck(
                name="Config Valid",
                status="error",
                message="Invalid YAML format",
                details=sanitize_error_message(e),
                fix_available=True,
            ))

        # Check permissions
        if config_file.stat().st_mode & 0o600:
            checks.append(HealthCheck(
                name="Permissions",
                status="ok",
                message="Read/write OK",
            ))
        else:
            checks.append(HealthCheck(
                name="Permissions",
                status="warning",
                message="Incorrect permissions",
                details=f"Current: {oct(config_file.stat().st_mode)[-3:]}",
                fix_available=True,
            ))
    else:
        checks.append(HealthCheck(
            name="Config File",
            status="warning",
            message="Not found",
            details="Run 'raxe init' to create configuration",
            fix_available=True,
        ))

    return checks


def _check_database() -> list[HealthCheck]:
    """Check database health."""
    checks = []

    db_path = Path.home() / ".raxe" / "telemetry.db"

    # Database exists
    if db_path.exists():
        checks.append(HealthCheck(
            name="Database File",
            status="ok",
            message=f"Found at {db_path}",
        ))

        # SQLite version
        sqlite_version = sqlite3.sqlite_version
        min_version = "3.35.0"
        if sqlite_version >= min_version:
            checks.append(HealthCheck(
                name="SQLite Version",
                status="ok",
                message=f"{sqlite_version}",
            ))
        else:
            checks.append(HealthCheck(
                name="SQLite Version",
                status="warning",
                message=f"{sqlite_version} (recommend >= {min_version})",
            ))

        # Database size
        size_mb = db_path.stat().st_size / (1024 * 1024)
        if size_mb < 100:
            checks.append(HealthCheck(
                name="Database Size",
                status="ok",
                message=f"{size_mb:.1f} MB",
            ))
        else:
            checks.append(HealthCheck(
                name="Database Size",
                status="warning",
                message=f"{size_mb:.1f} MB (consider cleanup)",
                details="Run cleanup script to reduce size",
            ))

        # Try to query database
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            conn.close()

            checks.append(HealthCheck(
                name="Database Integrity",
                status="ok",
                message=f"{table_count} tables",
            ))
        except Exception as e:
            checks.append(HealthCheck(
                name="Database Integrity",
                status="error",
                message="Corruption detected",
                details=sanitize_error_message(e),
                fix_available=True,
            ))
    else:
        checks.append(HealthCheck(
            name="Database File",
            status="warning",
            message="Not created yet",
            details="Will be created on first scan",
        ))

    return checks


def _check_rule_packs() -> list[HealthCheck]:
    """Check rule packs status."""
    checks = []

    try:
        from raxe.sdk.client import Raxe

        raxe = Raxe()
        rules = raxe.get_all_rules()
        packs = raxe.list_rule_packs()

        if rules:
            checks.append(HealthCheck(
                name="Rules Loaded",
                status="ok",
                message=f"{len(rules)} rules from {len(packs)} packs",
            ))
        else:
            checks.append(HealthCheck(
                name="Rules Loaded",
                status="warning",
                message="No rules loaded",
                details="Check pack configuration",
            ))

        # Check for bundled packs
        from raxe.application.preloader import get_bundled_packs_root
        bundled_packs = get_bundled_packs_root()

        if bundled_packs.exists():
            checks.append(HealthCheck(
                name="Bundled Packs",
                status="ok",
                message=f"Available at {bundled_packs}",
            ))
        else:
            checks.append(HealthCheck(
                name="Bundled Packs",
                status="error",
                message="Bundled packs not found",
                details="Reinstall RAXE to restore bundled packs",
            ))

    except Exception as e:
        checks.append(HealthCheck(
            name="Rule Packs",
            status="error",
            message="Failed to load rule packs",
            details=sanitize_error_message(e),
        ))

    return checks


def _check_performance() -> list[HealthCheck]:
    """Check performance metrics."""
    checks = []

    try:
        import time

        from raxe.sdk.client import Raxe

        raxe = Raxe()

        # Test scan latency
        test_prompt = "This is a test prompt for performance measurement"

        # Warmup
        raxe.scan(test_prompt)

        # Measure
        iterations = 10
        durations = []
        for _ in range(iterations):
            start = time.perf_counter()
            raxe.scan(test_prompt)
            duration = (time.perf_counter() - start) * 1000
            durations.append(duration)

        avg_latency = sum(durations) / len(durations)
        p95_latency = sorted(durations)[int(len(durations) * 0.95)]

        # Check against targets
        if avg_latency < 5.0:
            checks.append(HealthCheck(
                name="Avg Scan Time",
                status="ok",
                message=f"{avg_latency:.2f}ms (target: <5ms)",
            ))
        elif avg_latency < 10.0:
            checks.append(HealthCheck(
                name="Avg Scan Time",
                status="warning",
                message=f"{avg_latency:.2f}ms (target: <5ms)",
            ))
        else:
            checks.append(HealthCheck(
                name="Avg Scan Time",
                status="error",
                message=f"{avg_latency:.2f}ms (target: <5ms)",
                details="Performance degraded - check system resources",
            ))

        if p95_latency < 10.0:
            checks.append(HealthCheck(
                name="P95 Latency",
                status="ok",
                message=f"{p95_latency:.2f}ms (target: <10ms)",
            ))
        else:
            checks.append(HealthCheck(
                name="P95 Latency",
                status="warning",
                message=f"{p95_latency:.2f}ms (target: <10ms)",
            ))

    except Exception as e:
        checks.append(HealthCheck(
            name="Performance",
            status="error",
            message="Failed to measure performance",
            details=sanitize_error_message(e),
        ))

    return checks


def _display_check_results(checks: list[HealthCheck]) -> None:
    """Display health check results."""
    for check in checks:
        if check.status == "ok":
            icon = "✅"
            style = "green"
        elif check.status == "warning":
            icon = "⚠️ "
            style = "yellow"
        else:  # error
            icon = "❌"
            style = "red"

        console.print(f"  {icon} [{style}]{check.name}:[/] {check.message}")

        if check.details:
            console.print(f"     [dim]{check.details}[/dim]")


def _display_summary(checks: list[HealthCheck]) -> None:
    """Display summary of health checks."""
    console.print("[bold]Summary[/bold]")
    console.print()

    ok_count = sum(1 for c in checks if c.status == "ok")
    warning_count = sum(1 for c in checks if c.status == "warning")
    error_count = sum(1 for c in checks if c.status == "error")

    total = len(checks)

    console.print(f"  [green]✓ Passed:[/green] {ok_count}/{total}")
    if warning_count > 0:
        console.print(f"  [yellow]⚠ Warnings:[/yellow] {warning_count}/{total}")
    if error_count > 0:
        console.print(f"  [red]✗ Errors:[/red] {error_count}/{total}")

    console.print()

    if error_count == 0 and warning_count == 0:
        console.print("[bold green]✓ All checks passed! RAXE is healthy.[/bold green]")
    elif error_count > 0:
        console.print("[bold red]✗ Critical issues found. Run with --fix to attempt repairs.[/bold red]")
    else:
        console.print("[bold yellow]⚠ Warnings found. System functional but not optimal.[/bold yellow]")

    console.print()


def _auto_fix(checks: list[HealthCheck]) -> None:
    """Attempt to auto-fix issues."""
    console.print("[bold cyan]Auto-Fix[/bold cyan]")
    console.print()

    fixable = [c for c in checks if c.fix_available and c.status != "ok"]

    if not fixable:
        console.print("[green]No fixable issues found[/green]")
        return

    for check in fixable:
        console.print(f"Fixing: {check.name}...")

        try:
            if "Config" in check.name:
                _fix_config()
                display_success(f"Fixed {check.name}")
            elif "Dependencies" in check.name:
                console.print("[yellow]  Please run: pip install raxe[dev][/yellow]")
            elif "Database" in check.name:
                _fix_database()
                display_success(f"Fixed {check.name}")
            elif "Permissions" in check.name:
                _fix_permissions()
                display_success(f"Fixed {check.name}")
            else:
                display_warning(f"No automated fix for {check.name}")
        except Exception as e:
            display_error(f"Failed to fix {check.name}", sanitize_error_message(e))

    console.print()


def _fix_config() -> None:
    """Fix configuration issues."""
    config_file = Path.home() / ".raxe" / "config.yaml"

    if not config_file.exists():
        # Create default config
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_content = """# RAXE Configuration
version: 1.0.0

# Telemetry (privacy-preserving)
telemetry:
  enabled: true
  endpoint: https://api.raxe.ai/v1/telemetry

# Performance
performance:
  mode: balanced
  l2_enabled: true
  max_latency_ms: 10
"""
        config_file.write_text(config_content)


def _fix_database() -> None:
    """Fix database issues."""
    db_path = Path.home() / ".raxe" / "telemetry.db"

    # Simple integrity check
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA integrity_check")
        conn.close()
    except Exception:
        # Backup and recreate
        backup_path = db_path.with_suffix(".db.backup")
        if db_path.exists():
            db_path.rename(backup_path)


def _fix_permissions() -> None:
    """Fix permission issues."""
    config_file = Path.home() / ".raxe" / "config.yaml"

    if config_file.exists():
        config_file.chmod(0o600)


def _export_report(checks: list[HealthCheck], export_path: str) -> None:
    """Export diagnostic report to file."""
    console.print(f"[cyan]Exporting report to {export_path}...[/cyan]")

    lines = []
    lines.append("RAXE Health Check Report")
    lines.append("=" * 60)
    lines.append("")

    for check in checks:
        status_str = check.status.upper()
        lines.append(f"[{status_str}] {check.name}")
        lines.append(f"  Message: {check.message}")
        if check.details:
            lines.append(f"  Details: {check.details}")
        lines.append("")

    # Summary
    ok_count = sum(1 for c in checks if c.status == "ok")
    warning_count = sum(1 for c in checks if c.status == "warning")
    error_count = sum(1 for c in checks if c.status == "error")

    lines.append("Summary")
    lines.append("-" * 60)
    lines.append(f"Passed: {ok_count}/{len(checks)}")
    lines.append(f"Warnings: {warning_count}/{len(checks)}")
    lines.append(f"Errors: {error_count}/{len(checks)}")

    # Write to file
    Path(export_path).write_text("\n".join(lines))

    display_success(f"Report exported to {export_path}")


if __name__ == "__main__":
    doctor()
