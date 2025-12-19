"""
RAXE CLI - Command-line interface.

Uses the unified Raxe client internally - no duplicate logic.
"""
import json
import sys
from pathlib import Path

import click

from raxe import __version__
from raxe.cli.auth import auth, auth_link
from raxe.cli.config import config
from raxe.cli.doctor import doctor
from raxe.cli.event import event
from raxe.cli.error_handler import handle_cli_error
from raxe.cli.exit_codes import (
    EXIT_CONFIG_ERROR,
    EXIT_INVALID_INPUT,
    EXIT_SCAN_ERROR,
    EXIT_THREAT_DETECTED,
)
from raxe.cli.expiry_warning import check_and_display_expiry_warning
from raxe.cli.export import export
from raxe.cli.history import history
from raxe.cli.models import models
from raxe.cli.output import console, display_error, display_scan_result, display_success
from raxe.cli.privacy import privacy_command
from raxe.cli.profiler import profile_command
from raxe.cli.repl import repl
from raxe.cli.rules import rules
from raxe.cli.stats import stats
from raxe.cli.suppress import suppress
from raxe.cli.telemetry import telemetry
from raxe.cli.test import test
from raxe.cli.tune import tune
from raxe.cli.validate import validate_rule_command
from raxe.sdk.client import Raxe


# Note: Telemetry flush is now handled by the unified helper:
# from raxe.infrastructure.telemetry.flush_helper import ensure_telemetry_flushed


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="RAXE CLI", message="%(prog)s %(version)s")
@click.option(
    "--no-color",
    is_flag=True,
    help="Disable colored output",
    envvar="RAXE_NO_COLOR",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Show detailed logs (enables console logging)",
    envvar="RAXE_VERBOSE",
)
@click.option(
    "--quiet",
    is_flag=True,
    help="Suppress all visual output (for CI/CD)",
    envvar="RAXE_QUIET",
)
@click.pass_context
def cli(ctx, no_color: bool, verbose: bool, quiet: bool):
    """RAXE - AI Security for LLMs • Privacy-First Threat Detection"""
    # Flush any stale telemetry from previous sessions (non-blocking background thread)
    # This recovers events that were queued but not flushed due to crashes or improper exit
    try:
        from raxe.infrastructure.telemetry.flush_helper import flush_stale_telemetry_async
        flush_stale_telemetry_async()
    except Exception:
        pass  # Never block CLI startup

    # Ensure ctx.obj exists for sub-commands
    ctx.ensure_object(dict)
    ctx.obj["no_color"] = no_color or quiet  # Quiet implies no color
    ctx.obj["verbose"] = verbose and not quiet  # Quiet overrides verbose
    ctx.obj["quiet"] = quiet

    # Show welcome banner if no command provided (unless quiet)
    if ctx.invoked_subcommand is None:
        if not quiet:
            # Check if this is a first run
            from raxe.cli.setup_wizard import check_first_run, display_first_run_message

            if check_first_run():
                display_first_run_message(console)
            else:
                from raxe.cli.branding import print_help_menu
                print_help_menu(console)
        ctx.exit()

    # Track command usage (record the invoked command name)
    if ctx.invoked_subcommand:
        try:
            from raxe.infrastructure.tracking.usage import UsageTracker
            tracker = UsageTracker()
            tracker.record_command(ctx.invoked_subcommand)
        except Exception:
            # Don't fail if tracking fails
            pass

    # Enable console logging if verbose flag set
    if verbose:
        import os
        os.environ["RAXE_ENABLE_CONSOLE_LOGGING"] = "true"

        # Reconfigure logging to enable console output
        from raxe.utils.logging import setup_logging
        setup_logging(enable_console_logging=True)


@cli.command()
@click.option(
    "--api-key",
    help="RAXE API key (optional, for cloud features)",
    envvar="RAXE_API_KEY",
)
@click.option(
    "--telemetry/--no-telemetry",
    default=True,
    help="Enable privacy-preserving telemetry (default: enabled)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing configuration",
)
@handle_cli_error
def init(api_key: str | None, telemetry: bool, force: bool):
    """Initialize RAXE configuration with interactive setup."""
    from rich.panel import Panel
    from rich.text import Text

    from raxe.cli.branding import print_info, print_logo, print_success

    config_dir = Path.home() / ".raxe"
    config_file = config_dir / "config.yaml"

    # Show compact logo
    print_logo(console, compact=True)
    console.print()
    console.print("🔧 [bold cyan]RAXE Initialization[/bold cyan]")
    console.print()

    # Check if already initialized
    if config_file.exists() and not force:
        print_success(console, f"RAXE already initialized at {config_file}")
        print_info(console, "Use --force to overwrite existing configuration")
        return

    # Create config directory
    config_dir.mkdir(parents=True, exist_ok=True)

    # Show configuration summary
    summary = Text()
    summary.append("Configuration Summary:\n\n", style="bold cyan")
    summary.append("  📂 Location: ", style="white")
    summary.append(f"{config_file}\n", style="cyan")
    summary.append("  🔑 API Key: ", style="white")
    summary.append(f"{api_key if api_key else 'Not configured (optional)'}\n", style="yellow" if not api_key else "green")
    summary.append("  📊 Telemetry: ", style="white")
    summary.append(f"{'Enabled' if telemetry else 'Disabled'}\n", style="green" if telemetry else "yellow")
    summary.append("  ⚡ Performance: ", style="white")
    summary.append("Balanced mode with L2 detection\n", style="cyan")

    console.print(Panel(summary, border_style="cyan", padding=(1, 2)))
    console.print()

    # Generate config
    config_content = f"""# RAXE Configuration
version: 1.0.0

# API Key (optional - for cloud features)
{"api_key: " + api_key if api_key else "# api_key: raxe_test_customer123_abc456"}

# Telemetry (privacy-preserving, only hashes sent)
telemetry:
  enabled: {str(telemetry).lower()}
  endpoint: https://api.beta.raxe.ai/v1/telemetry

# Performance
performance:
  mode: balanced  # fast, balanced, accurate
  l2_enabled: true
  max_latency_ms: 10

# Pack precedence (custom > community > core)
packs:
  precedence:
    - custom
    - community
    - core

# Policy source
policies:
  source: local_file  # local_file, api, inline
  path: .raxe/policies.yaml
"""

    config_file.write_text(config_content)

    print_success(console, "RAXE initialized successfully!")
    console.print()

    # Next steps panel
    next_steps = Text()
    next_steps.append("Quick Start:\n\n", style="bold cyan")
    next_steps.append("  1️⃣  ", style="white")
    next_steps.append('raxe scan "your text here"\n', style="cyan")
    next_steps.append("     Scan text for security threats\n\n", style="dim")
    next_steps.append("  2️⃣  ", style="white")
    next_steps.append('raxe test\n', style="cyan")
    next_steps.append("     Test your configuration\n\n", style="dim")
    next_steps.append("  3️⃣  ", style="white")
    next_steps.append('raxe stats\n', style="cyan")
    next_steps.append("     View statistics & achievements\n\n", style="dim")
    next_steps.append("  📚  ", style="white")
    next_steps.append('https://docs.raxe.ai\n', style="cyan underline")
    next_steps.append("     Read the documentation", style="dim")

    console.print(Panel(next_steps, title="[bold cyan]Next Steps[/bold cyan]", border_style="cyan", padding=(1, 2)))
    console.print()


@cli.command()
@handle_cli_error
def setup():
    """Interactive setup wizard for first-time users.

    Provides a friendly, guided setup experience that walks you through:
      - API key configuration (or temp key auto-generation)
      - Detection settings (L2 ML detection, telemetry)
      - Shell completion installation
      - Configuration file creation
      - Test scan verification

    \b
    Examples:
      raxe setup
    """
    from raxe.cli.setup_wizard import run_setup_wizard

    success = run_setup_wizard(console)

    if not success:
        sys.exit(1)


def parse_suppress_pattern(pattern: str) -> tuple[str, str]:
    """Parse suppress pattern with optional action override.

    Formats:
        pi-001 -> (pi-001, SUPPRESS)
        pi-001:FLAG -> (pi-001, FLAG)
        pi-001:LOG -> (pi-001, LOG)
        jb-* -> (jb-*, SUPPRESS)
        jb-*:FLAG -> (jb-*, FLAG)

    Args:
        pattern: Pattern string, optionally with :ACTION suffix

    Returns:
        Tuple of (rule_pattern, action)

    Raises:
        click.BadParameter: If action is invalid
    """
    if ":" in pattern:
        parts = pattern.rsplit(":", 1)
        rule_pattern = parts[0]
        action = parts[1].upper()
        if action not in ("SUPPRESS", "FLAG", "LOG"):
            raise click.BadParameter(
                f"Invalid action '{action}'. Valid actions: SUPPRESS, FLAG, LOG"
            )
        return rule_pattern, action
    return pattern, "SUPPRESS"


@cli.command()
@click.argument("text", required=False)
@click.option(
    "--stdin",
    is_flag=True,
    help="Read text from stdin instead of argument",
)
@click.option(
    "--format",
    type=click.Choice(["text", "json", "yaml", "table"]),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--ci",
    is_flag=True,
    help="CI/CD mode: JSON output, no banner, exit code 1 on threats",
    envvar="RAXE_CI",
)
@click.option(
    "--profile",
    is_flag=True,
    help="Enable performance profiling",
)
@click.option(
    "--l1-only",
    is_flag=True,
    help="Use L1 (regex) detection only",
)
@click.option(
    "--l2-only",
    is_flag=True,
    help="Use L2 (ML) detection only",
)
@click.option(
    "--mode",
    type=click.Choice(["fast", "balanced", "thorough"]),
    default="balanced",
    help="Performance mode (default: balanced)",
)
@click.option(
    "--confidence",
    type=float,
    help="Minimum confidence threshold (0.0-1.0)",
)
@click.option(
    "--explain",
    is_flag=True,
    help="Show detailed explanation of detections",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Test scan without saving to database",
)
@click.option(
    "--suppress",
    "suppress_patterns",
    multiple=True,
    help="Suppress rule(s) for this scan. Supports wildcards and action override (e.g., pi-001, jb-*, pi-001:FLAG)",
)
@click.pass_context
def scan(
    ctx,
    text: str | None,
    stdin: bool,
    format: str,
    ci: bool,
    profile: bool,
    l1_only: bool,
    l2_only: bool,
    mode: str,
    confidence: float | None,
    explain: bool,
    dry_run: bool,
    suppress_patterns: tuple[str, ...],
):
    """
    Scan text for security threats.

    \b
    Examples:
      raxe scan "Ignore all previous instructions"
      echo "test" | raxe scan --stdin
      raxe scan "prompt" --format json
      raxe scan "text" --l1-only --mode fast
      raxe scan "text" --confidence 0.8 --explain
      raxe scan "text" --ci  # CI/CD mode (JSON, exit 1 on threats)
      raxe --quiet scan "text"  # Same as --ci

    \b
    Suppression Examples:
      raxe scan "text" --suppress pi-001                  # Suppress single rule
      raxe scan "text" --suppress pi-001 --suppress jb-*  # Multiple suppressions
      raxe scan "text" --suppress "pi-001:FLAG"           # Flag instead of suppress

    \b
    Exit Codes (for CI/CD integration):
      0  Success - scan completed, no threats detected
      1  Threat detected (with --ci or --quiet mode)
      2  Invalid input - no text provided or bad arguments
      3  Configuration error - RAXE not initialized
      4  Scan error - execution failed
    """
    # Check if CI or quiet mode is enabled
    # --ci flag is an explicit alias for CI/CD mode (same as --quiet)
    quiet = ctx.obj.get("quiet", False) or ci
    verbose = ctx.obj.get("verbose", False) and not ci  # CI mode overrides verbose
    no_color = ctx.obj.get("no_color", False) or ci  # CI mode implies no color

    # Auto-enable quiet mode for JSON/YAML formats to prevent progress contamination
    if format in ("json", "yaml"):
        quiet = True

    # Override format to JSON if quiet mode
    if quiet and format == "text":
        format = "json"

    # Show compact logo (for visual consistency)
    from raxe.cli.branding import print_logo
    if format == "text" and not quiet:  # Only show for text output when not quiet
        print_logo(console, compact=True)
        console.print()
        # Check and display API key expiry warning if applicable
        check_and_display_expiry_warning(console)

    # Get text from argument or stdin
    if stdin:
        text = sys.stdin.read()
    elif not text:
        display_error("No text provided", "Provide text as argument or use --stdin")
        sys.exit(EXIT_INVALID_INPUT)

    # Setup progress indicator
    from raxe.cli.progress import create_progress_indicator
    from raxe.cli.progress_context import detect_progress_mode

    progress_mode = detect_progress_mode(
        quiet=quiet,
        verbose=verbose,
        no_color=no_color
    )

    progress = create_progress_indicator(progress_mode)

    # Create Raxe client (uses config if available)
    try:
        raxe = Raxe(progress_callback=progress)
    except Exception as e:
        display_error("Failed to initialize RAXE", str(e))
        console.print("Try running: [cyan]raxe init[/cyan]")
        sys.exit(EXIT_CONFIG_ERROR)

    # Add CLI-specified suppressions (temporary, for this scan only)
    cli_suppressions: list[tuple[str, str]] = []  # (pattern, action) tuples
    if suppress_patterns:
        from raxe.domain.suppression import Suppression, SuppressionAction, SuppressionValidationError

        for pattern_str in suppress_patterns:
            try:
                rule_pattern, action_str = parse_suppress_pattern(pattern_str)
                action = SuppressionAction(action_str)

                # Add to suppression manager (temporary, runtime only)
                raxe.suppression_manager.add_suppression(
                    pattern=rule_pattern,
                    reason="CLI --suppress flag",
                    action=action,
                    created_by="cli",
                    log_to_audit=False,  # Don't log temporary suppressions
                )
                cli_suppressions.append((rule_pattern, action_str))
            except SuppressionValidationError as e:
                display_error(
                    f"Invalid suppression pattern: {pattern_str}",
                    f"{e}\n\nValid pattern examples:\n"
                    "  pi-001         - Suppress specific rule\n"
                    "  pi-*           - Suppress all prompt injection rules\n"
                    "  jb-*:FLAG      - Flag jailbreak rules for review\n"
                )
                sys.exit(EXIT_INVALID_INPUT)
            except click.BadParameter as e:
                display_error(f"Invalid suppression pattern: {pattern_str}", str(e))
                sys.exit(EXIT_INVALID_INPUT)

    # Scan using unified client
    # Wire all CLI flags to scan parameters
    try:
        if profile:
            # Import profiler here to avoid circular dependency
            try:
                from raxe.monitoring.profiler import PerformanceProfiler

                profiler = PerformanceProfiler()
                prof_result = profiler.profile_scan(text, iterations=1)
                result = raxe.scan(
                    text,
                    l1_enabled=not l2_only,
                    l2_enabled=not l1_only,
                    mode=mode,
                    confidence_threshold=confidence if confidence else 0.5,
                    explain=explain,
                    dry_run=dry_run,
                )

                # Show scan result first
                if format == "text":
                    no_color = ctx.obj.get("no_color", False)
                    display_scan_result(result, no_color=no_color, explain=explain)

                    # Then show profile
                    click.echo()
                    click.secho("=" * 60, fg="cyan")
                    click.secho("Performance Profile", fg="cyan", bold=True)
                    click.secho("=" * 60, fg="cyan")
                    click.echo(prof_result.stats_report)
                else:
                    # For JSON/YAML, just show result (profile would clutter output)
                    result = raxe.scan(
                        text,
                        l1_enabled=not l2_only,
                        l2_enabled=not l1_only,
                        mode=mode,
                        confidence_threshold=confidence if confidence else 0.5,
                        explain=explain,
                        dry_run=dry_run,
                    )
            except ImportError:
                console.print("[yellow]Warning: Profiling not available[/yellow]")
                result = raxe.scan(
                    text,
                    l1_enabled=not l2_only,
                    l2_enabled=not l1_only,
                    mode=mode,
                    confidence_threshold=confidence if confidence else 0.5,
                    explain=explain,
                    dry_run=dry_run,
                )
        else:
            result = raxe.scan(
                text,
                l1_enabled=not l2_only,
                l2_enabled=not l1_only,
                mode=mode,
                confidence_threshold=confidence if confidence else 0.5,
                explain=explain,
                dry_run=dry_run,
            )
    except Exception as e:
        display_error("Scan execution failed", str(e))
        sys.exit(EXIT_SCAN_ERROR)

    # Output based on format
    if format == "json" and not profile:
        # Collect L1 detections
        l1_detections = []
        for d in result.scan_result.l1_result.detections:
            detection_dict = {
                "rule_id": d.rule_id,
                "severity": d.severity.value,
                "confidence": d.confidence,
                "layer": "L1",
                "message": getattr(d, "message", ""),
            }
            # Include flag status if flagged
            if getattr(d, "is_flagged", False):
                detection_dict["is_flagged"] = True
                if getattr(d, "suppression_reason", None):
                    detection_dict["flag_reason"] = d.suppression_reason
            l1_detections.append(detection_dict)

        # Collect L2 predictions
        l2_detections = []
        if result.scan_result.l2_result and result.scan_result.l2_result.has_predictions:
            for p in result.scan_result.l2_result.predictions:
                # Map confidence to severity
                if p.confidence >= 0.8:
                    severity = "high"
                elif p.confidence >= 0.6:
                    severity = "medium"
                else:
                    severity = "low"

                # Extract family/subfamily from bundle metadata if available
                family = p.metadata.get("family")
                sub_family = p.metadata.get("sub_family")
                scores = p.metadata.get("scores", {})
                why_it_hit = p.metadata.get("why_it_hit", [])
                recommended_action = p.metadata.get("recommended_action", [])

                detection = {
                    "rule_id": f"L2-{p.threat_type.value}",
                    "severity": severity,
                    "confidence": p.confidence,
                    "layer": "L2",
                    "message": p.explanation or f"{p.threat_type.value} detected",
                }

                # Add ML model metadata fields if available
                if family:
                    detection["family"] = family
                if sub_family:
                    detection["sub_family"] = sub_family
                if scores:
                    detection["scores"] = scores
                if why_it_hit:
                    detection["why_it_hit"] = why_it_hit
                if recommended_action:
                    detection["recommended_action"] = recommended_action

                l2_detections.append(detection)

        output = {
            "has_detections": result.scan_result.has_threats,
            "detections": l1_detections + l2_detections,
            "duration_ms": result.duration_ms,
            "l1_count": len(l1_detections),
            "l2_count": len(l2_detections),
        }
        click.echo(json.dumps(output, indent=2))

    elif format == "yaml" and not profile:
        try:
            import yaml

            # Collect L1 detections
            l1_detections = []
            for d in result.scan_result.l1_result.detections:
                detection_dict = {
                    "rule_id": d.rule_id,
                    "severity": d.severity.value,
                    "confidence": d.confidence,
                    "layer": "L1",
                    "message": getattr(d, "message", ""),
                }
                # Include flag status if flagged
                if getattr(d, "is_flagged", False):
                    detection_dict["is_flagged"] = True
                    if getattr(d, "suppression_reason", None):
                        detection_dict["flag_reason"] = d.suppression_reason
                l1_detections.append(detection_dict)

            # Collect L2 predictions
            l2_detections = []
            if result.scan_result.l2_result and result.scan_result.l2_result.has_predictions:
                for p in result.scan_result.l2_result.predictions:
                    # Map confidence to severity
                    if p.confidence >= 0.8:
                        severity = "high"
                    elif p.confidence >= 0.6:
                        severity = "medium"
                    else:
                        severity = "low"

                    l2_detections.append({
                        "rule_id": f"L2-{p.threat_type.value}",
                        "severity": severity,
                        "confidence": p.confidence,
                        "layer": "L2",
                        "message": p.explanation or f"{p.threat_type.value} detected",
                    })

            output = {
                "has_detections": result.scan_result.has_threats,
                "detections": l1_detections + l2_detections,
                "duration_ms": result.duration_ms,
                "l1_count": len(l1_detections),
                "l2_count": len(l2_detections),
            }
            click.echo(yaml.dump(output))
        except ImportError:
            display_error("PyYAML not installed", "Use --format json instead")
            sys.exit(EXIT_CONFIG_ERROR)

    elif format == "text" and not profile:
        # Use rich output
        no_color = ctx.obj.get("no_color", False)
        display_scan_result(result, no_color=no_color, explain=explain)

    # Show dry-run feedback after displaying result (unless quiet)
    if dry_run and not quiet:
        console.print()
        console.print("[yellow]  Dry run mode: Results not saved to database[/yellow]")
        console.print()

    # Auto-flush telemetry at end of scan using unified helper
    # This ends the session and flushes all queued events
    try:
        from raxe.infrastructure.telemetry.flush_helper import ensure_telemetry_flushed

        ensure_telemetry_flushed(timeout_seconds=2.0, end_session=True)
    except Exception:
        pass  # Never let telemetry affect scan completion

    # Exit with appropriate code for CI/CD (quiet mode)
    if quiet and result.scan_result.has_threats:
        sys.exit(EXIT_THREAT_DETECTED)


@cli.command("batch")
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json", "csv"]),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--output",
    type=click.Path(),
    help="Output file for results (default: stdout)",
)
@click.option(
    "--fail-fast",
    is_flag=True,
    help="Stop on first critical threat",
)
@handle_cli_error
def batch_scan(file: str, output_format: str, output: str | None, fail_fast: bool) -> None:
    """
    Batch scan prompts from a file.

    Reads prompts from a file (one per line) and scans each.

    \b
    Examples:
      raxe batch prompts.txt
      raxe batch prompts.txt --format json --output results.json
      raxe batch prompts.txt --fail-fast
    """
    import csv as csv_module
    from pathlib import Path

    from raxe.cli.branding import print_logo

    # Show compact logo for text output
    if output_format == "text":
        print_logo(console, compact=True)
        console.print()
        # Check and display API key expiry warning if applicable
        check_and_display_expiry_warning(console)

    try:
        raxe = Raxe()
    except Exception as e:
        display_error("Failed to initialize RAXE", str(e))
        console.print("Try running: [cyan]raxe init[/cyan]")
        sys.exit(EXIT_CONFIG_ERROR)

    # Read prompts from file
    # Supports both plain text (one prompt per line) and JSON format
    # JSON format: {"id": "...", "prompt": "...", ...} - extracts "prompt" field
    import json as json_module

    def extract_prompt(line: str) -> str:
        """Extract prompt from line, handling JSON if present."""
        line = line.strip()
        if not line:
            return ""
        # Try to parse as JSON and extract "prompt" field
        if line.startswith("{"):
            try:
                data = json_module.loads(line)
                if isinstance(data, dict) and "prompt" in data:
                    return str(data["prompt"])
            except json_module.JSONDecodeError:
                pass  # Not valid JSON, use line as-is
        return line

    try:
        with open(file) as f:
            prompts = [extract_prompt(line) for line in f]
            prompts = [p for p in prompts if p]  # Filter empty
    except Exception as e:
        display_error("Failed to read input file", str(e))
        sys.exit(EXIT_INVALID_INPUT)

    if not prompts:
        console.print("[yellow]No prompts found in file[/yellow]")
        return

    console.print(f"[cyan]Batch scanning {len(prompts)} prompts...[/cyan]")
    console.print()

    # Scan all prompts
    results = []
    threats_found = 0
    critical_found = False

    from raxe.cli.output import create_progress_bar

    with create_progress_bar("Scanning...") as progress:
        task = progress.add_task("Processing...", total=len(prompts))

        for i, prompt in enumerate(prompts):
            try:
                result = raxe.scan(prompt)
                results.append({
                    "line": i + 1,
                    "prompt": prompt[:50] + "..." if len(prompt) > 50 else prompt,
                    "has_threats": result.scan_result.has_threats,
                    "detection_count": len(result.scan_result.l1_result.detections),
                    "highest_severity": result.scan_result.combined_severity.value if result.scan_result.has_threats else "none",
                    "duration_ms": result.duration_ms,
                    "detections": [
                        {
                            "rule_id": d.rule_id,
                            "severity": d.severity.value,
                            "confidence": d.confidence,
                        }
                        for d in result.scan_result.l1_result.detections
                    ],
                })

                if result.scan_result.has_threats:
                    threats_found += 1
                    if result.scan_result.combined_severity.value == "critical":
                        critical_found = True
                        if fail_fast:
                            console.print()
                            console.print(f"[red bold]Critical threat found at line {i+1}. Stopping.[/red bold]")
                            break

                progress.update(task, completed=i + 1)

            except Exception as e:
                console.print()
                display_error(f"Error scanning line {i+1}", str(e))
                if fail_fast:
                    break

    console.print()

    # Output results
    if output_format == "json":
        import json
        output_data = {
            "total_scanned": len(results),
            "threats_found": threats_found,
            "results": results,
        }

        if output:
            Path(output).write_text(json.dumps(output_data, indent=2))
            display_success(f"Results written to {output}")
        else:
            console.print(json.dumps(output_data, indent=2))

    elif output_format == "csv":
        if not output:
            display_error("CSV format requires --output option", "Specify output file with --output")
            sys.exit(EXIT_INVALID_INPUT)

        with open(output, "w", newline="") as f:
            writer = csv_module.DictWriter(
                f,
                fieldnames=["line", "prompt", "has_threats", "detection_count", "highest_severity", "duration_ms"]
            )
            writer.writeheader()
            for result in results:
                writer.writerow({
                    "line": result["line"],
                    "prompt": result["prompt"],
                    "has_threats": result["has_threats"],
                    "detection_count": result["detection_count"],
                    "highest_severity": result["highest_severity"],
                    "duration_ms": result["duration_ms"],
                })

        display_success(f"Results written to {output}")

    else:  # text format
        # Display summary
        from rich.table import Table

        table = Table(title="Batch Scan Results", show_header=True, header_style="bold cyan")
        table.add_column("Line", justify="right", style="cyan", no_wrap=True)
        table.add_column("Prompt", style="white")
        table.add_column("Status", style="bold", no_wrap=True)
        table.add_column("Detections", justify="right", no_wrap=True)
        table.add_column("Time", justify="right", no_wrap=True)

        for result in results:
            if result["has_threats"]:
                status = "[red]THREAT[/red]"
            else:
                status = "[green]SAFE[/green]"

            table.add_row(
                str(result["line"]),
                result["prompt"],
                status,
                str(result["detection_count"]),
                f"{result['duration_ms']:.1f}ms",
            )

        console.print(table)
        console.print()

        # Summary
        console.print("[bold]Summary[/bold]")
        console.print(f"  Total scanned: {len(results)}")
        console.print(f"  Threats found: {threats_found}")
        console.print(f"  Clean scans: {len(results) - threats_found}")

        if critical_found:
            console.print("  [red bold]Critical threats detected![/red bold]")

        console.print()

    # Auto-flush telemetry at end of batch scan
    # Use generous timeout and batches for batch operations (many events)
    # Each HTTP batch takes ~0.5-1s, so 1000 prompts needs ~40s+ for full flush
    try:
        from raxe.infrastructure.telemetry.flush_helper import ensure_telemetry_flushed

        # Calculate appropriate timeout based on number of prompts
        # ~0.05s per prompt accounts for HTTP latency, capped at 120s
        timeout = min(5.0 + len(prompts) * 0.05, 120.0)
        # Allow 2x batches to handle both critical and standard queues
        # Each queue might have up to len(prompts) events
        max_batches = max(20, (len(prompts) // 50 + 1) * 2)

        ensure_telemetry_flushed(
            timeout_seconds=timeout,
            max_batches=max_batches,
            end_session=True,
        )
    except Exception:
        pass  # Never let telemetry affect batch completion


@cli.group()
def pack():
    """Manage rule packs."""
    pass


@pack.command("list")
def pack_list():
    """List installed rule packs."""
    raxe = Raxe()

    click.echo("Installed packs:")
    click.echo()

    # Get packs from registry
    stats = raxe.stats
    click.echo(f"  Rules loaded: {stats['rules_loaded']}")
    click.echo(f"  Packs loaded: {stats['packs_loaded']}")
    click.echo()
    click.echo("Use 'raxe pack info <pack-id>' for details")


@pack.command("info")
@click.argument("pack_id")
def pack_info(pack_id: str):
    """Show information about a specific pack."""
    click.echo(f"Pack: {pack_id}")
    click.echo("  (Full pack info coming in next sprint)")


@cli.command()
@handle_cli_error
def plugins():
    """List installed plugins.

    Shows all discovered plugins with their status (loaded or failed).
    """
    from raxe.plugins import PluginLoader

    loader = PluginLoader()
    discovered = loader.discover_plugins()

    if not discovered:
        console.print("[yellow]No plugins found[/yellow]")
        console.print()
        console.print(f"Install plugins to: {loader.plugin_paths}")
        console.print("See: https://docs.raxe.ai/plugins for more info")
        return

    # Create table
    from rich.table import Table

    table = Table(title="Installed Plugins")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Path", style="blue")
    table.add_column("Status", style="green")

    for plugin_info in discovered:
        # Determine status
        if plugin_info.name in loader.loaded_plugins:
            status = "[green]✓ Loaded[/green]"
        elif plugin_info.name in loader.failed_plugins:
            error = loader.failed_plugins[plugin_info.name]
            status = f"[red]✗ Failed: {error}[/red]"
        else:
            status = "[yellow]○ Not Enabled[/yellow]"

        table.add_row(
            plugin_info.name,
            str(plugin_info.path),
            status
        )

    console.print(table)
    console.print()
    console.print(f"Total: {len(discovered)} plugins discovered")
    console.print(f"Loaded: {len(loader.loaded_plugins)}")
    console.print(f"Failed: {len(loader.failed_plugins)}")
    console.print()
    console.print("Enable plugins in ~/.raxe/config.yaml under plugins.enabled")


# Note: profile_cmd removed - use 'raxe profile' command instead
# Note: metrics_server removed - functionality consolidated into monitoring module


@cli.command("completion")
@click.argument(
    "shell",
    type=click.Choice(["bash", "zsh", "fish", "powershell"]),
)
def completion(shell: str):
    """
    Generate shell completion script.

    \b
    Installation:
      # Bash
      raxe completion bash > /etc/bash_completion.d/raxe

      # Zsh
      raxe completion zsh > ~/.zsh/completions/_raxe

      # Fish
      raxe completion fish > ~/.config/fish/completions/raxe.fish

      # PowerShell
      raxe completion powershell >> $PROFILE
    """
    if shell == "bash":
        script = """
# RAXE bash completion
_raxe_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="init setup scan batch test stats export repl rules doctor pack plugins privacy profile suppress telemetry tune validate-rule auth completion --help --version"

    COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
    return 0
}
complete -F _raxe_completion raxe
"""
    elif shell == "zsh":
        script = """
#compdef raxe
_raxe() {
    local -a commands
    commands=(
        'init:Initialize RAXE configuration'
        'setup:Interactive setup wizard'
        'scan:Scan text for threats'
        'batch:Batch scan prompts from file'
        'test:Test configuration and connectivity'
        'stats:Show local statistics'
        'export:Export scan history'
        'repl:Interactive shell'
        'rules:Manage and inspect detection rules'
        'doctor:Run system health checks'
        'pack:Manage rule packs'
        'plugins:List installed plugins'
        'privacy:Show privacy guarantees'
        'profile:Profile scan performance'
        'suppress:Manage false positive suppressions'
        'telemetry:Manage telemetry settings'
        'tune:Tune detection parameters'
        'validate-rule:Validate a rule file'
        'auth:Manage authentication and API keys'
        'completion:Generate shell completion'
    )
    _describe 'command' commands
}
_raxe
"""
    elif shell == "fish":
        script = """
# RAXE fish completion
complete -c raxe -f -a "init setup scan batch test stats export repl rules doctor pack plugins privacy profile suppress telemetry tune validate-rule auth completion"
complete -c raxe -f -a "init" -d "Initialize RAXE configuration"
complete -c raxe -f -a "setup" -d "Interactive setup wizard"
complete -c raxe -f -a "scan" -d "Scan text for threats"
complete -c raxe -f -a "batch" -d "Batch scan prompts from file"
complete -c raxe -f -a "test" -d "Test configuration"
complete -c raxe -f -a "stats" -d "Show statistics"
complete -c raxe -f -a "export" -d "Export scan history"
complete -c raxe -f -a "repl" -d "Interactive shell"
complete -c raxe -f -a "rules" -d "Manage detection rules"
complete -c raxe -f -a "doctor" -d "Run health checks"
complete -c raxe -f -a "pack" -d "Manage rule packs"
complete -c raxe -f -a "plugins" -d "List installed plugins"
complete -c raxe -f -a "privacy" -d "Show privacy guarantees"
complete -c raxe -f -a "profile" -d "Profile scan performance"
complete -c raxe -f -a "suppress" -d "Manage suppressions"
complete -c raxe -f -a "telemetry" -d "Manage telemetry settings"
complete -c raxe -f -a "tune" -d "Tune detection parameters"
complete -c raxe -f -a "validate-rule" -d "Validate a rule file"
complete -c raxe -f -a "auth" -d "Manage authentication and API keys"
"""
    elif shell == "powershell":
        script = """
# RAXE PowerShell completion
Register-ArgumentCompleter -Native -CommandName raxe -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    $commands = @('init', 'setup', 'scan', 'batch', 'test', 'stats', 'export', 'repl', 'rules', 'doctor', 'pack', 'plugins', 'privacy', 'profile', 'suppress', 'telemetry', 'tune', 'validate-rule', 'auth', 'completion')
    $commands | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {
        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
    }
}
"""
    click.echo(script)


# Register new commands
cli.add_command(auth)
cli.add_command(test)
cli.add_command(stats)
cli.add_command(export)
cli.add_command(repl)
cli.add_command(rules)
cli.add_command(doctor)
cli.add_command(models)
cli.add_command(profile_command)
cli.add_command(privacy_command)
cli.add_command(suppress)
cli.add_command(tune)
cli.add_command(validate_rule_command)
cli.add_command(config)
cli.add_command(event)
cli.add_command(history)
cli.add_command(telemetry)

# Top-level alias for 'raxe link ABC123' (same as 'raxe auth link ABC123')
cli.add_command(auth_link, name="link")


if __name__ == "__main__":
    cli()
