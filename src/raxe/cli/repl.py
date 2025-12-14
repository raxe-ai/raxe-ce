"""
RAXE REPL - Interactive shell for RAXE commands.
"""

from pathlib import Path

import click
from rich.table import Table

from raxe.cli.output import console, display_error, display_scan_result, display_stats
from raxe.sdk.client import Raxe, ScanPipelineResult

# Optional dependencies for REPL functionality
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.history import FileHistory
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False


@click.command()
def repl() -> None:
    """
    Launch interactive REPL mode.

    Start an interactive shell for RAXE commands with:
      - Command history (saved between sessions)
      - Tab completion
      - Multi-line input support
      - Scan history tracking

    \b
    Available commands:
      scan <text>       - Scan text for threats
      history           - Show scan history
      show <id>         - Show scan details
      rules [list|<id>] - List or show rules
      stats             - Show statistics
      config            - Show configuration
      clear             - Clear screen
      help              - Show help
      exit              - Exit REPL

    \b
    Examples:
      raxe repl
    """
    # Check if prompt_toolkit is available
    if not PROMPT_TOOLKIT_AVAILABLE:
        console.print(
            "[red]Error:[/red] prompt-toolkit is required for REPL mode.\n"
            "Install it with: [cyan]pip install raxe[repl][/cyan]"
        )
        raise click.Abort()

    from raxe.cli.branding import print_logo

    # Show compact logo
    print_logo(console, compact=True)
    console.print()

    console.print("[bold cyan]RAXE Interactive Shell[/bold cyan]")
    console.print("Type 'help' for commands, 'exit' to quit")
    console.print()

    # Setup autocomplete
    completer = WordCompleter(
        ["scan", "history", "show", "rules", "stats", "config", "clear", "help", "exit", "quit"],
        ignore_case=True,
    )

    # Setup history file
    history_file = Path.home() / ".raxe" / "repl_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    session: PromptSession = PromptSession(
        history=FileHistory(str(history_file)),
        completer=completer,
    )

    # Initialize Raxe client
    try:
        raxe = Raxe()
    except Exception as e:
        display_error("Failed to initialize RAXE", str(e))
        console.print("Run 'raxe init' to set up configuration")
        return

    # Track scan history for this session
    scan_history: list[tuple[str, ScanPipelineResult]] = []

    # REPL loop
    while True:
        try:
            # Get input
            text = session.prompt("raxe> ")

            # Skip empty input
            if not text.strip():
                continue

            # Parse command
            parts = text.strip().split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            # Execute command
            if command in ["exit", "quit"]:
                break
            elif command == "help":
                _display_help()
            elif command == "scan":
                if not args:
                    console.print("[yellow]Usage: scan <text>[/yellow]")
                else:
                    result = _handle_scan(raxe, args)
                    if result:
                        scan_history.append((args, result))
            elif command == "history":
                _handle_history(scan_history)
            elif command == "show":
                _handle_show(scan_history, args)
            elif command == "rules":
                _handle_rules(raxe, args)
            elif command == "stats":
                _handle_stats(raxe)
            elif command == "config":
                _handle_config()
            elif command == "clear":
                console.clear()
                console.print("[bold cyan]RAXE Interactive Shell[/bold cyan]")
                console.print("Type 'help' for commands, 'exit' to quit")
                console.print()
            else:
                console.print(f"[red]Unknown command: {command}[/red]")
                console.print("Type 'help' for available commands")

            console.print()

        except KeyboardInterrupt:
            console.print()
            continue
        except EOFError:
            break
        except Exception as e:
            display_error("Command failed", str(e))
            console.print()

    # Auto-flush telemetry at end of REPL session
    # This ensures all scan events from the session are sent before exit
    try:
        from raxe.infrastructure.telemetry.flush_helper import ensure_telemetry_flushed

        ensure_telemetry_flushed(
            timeout_seconds=5.0,  # Allow more time for REPL sessions
            end_session=True,
        )
    except Exception:
        pass  # Never let telemetry affect REPL exit

    console.print("[cyan]Goodbye![/cyan]")


def _display_help() -> None:
    """Display REPL help."""
    console.print("[bold]Available Commands:[/bold]")
    console.print()
    console.print("  [cyan]scan <text>[/cyan]       - Scan text for security threats")
    console.print("  [cyan]history[/cyan]           - Show scan history for this session")
    console.print("  [cyan]show <id>[/cyan]         - Show detailed results for scan #id")
    console.print("  [cyan]rules [list|<id>][/cyan] - List rules or show rule details")
    console.print("  [cyan]stats[/cyan]             - Show local statistics")
    console.print("  [cyan]config[/cyan]            - Show current configuration")
    console.print("  [cyan]clear[/cyan]             - Clear screen")
    console.print("  [cyan]help[/cyan]              - Show this help message")
    console.print("  [cyan]exit[/cyan] or [cyan]quit[/cyan]    - Exit REPL")
    console.print()
    console.print("[bold]Tips:[/bold]")
    console.print("  - Use Tab for command completion")
    console.print("  - Use Up/Down arrows for command history")
    console.print("  - Ctrl+C to cancel current input")
    console.print()


def _handle_scan(raxe: Raxe, text: str) -> ScanPipelineResult | None:
    """
    Handle scan command.

    Args:
        raxe: Raxe client instance
        text: Text to scan

    Returns:
        ScanPipelineResult if successful, None otherwise
    """
    try:
        result = raxe.scan(text)
        display_scan_result(result)
        return result
    except Exception as e:
        display_error("Scan failed", str(e))
        return None


def _handle_history(scan_history: list[tuple[str, ScanPipelineResult]]) -> None:
    """
    Handle history command.

    Args:
        scan_history: List of (prompt, result) tuples
    """
    if not scan_history:
        console.print("[yellow]No scan history in this session[/yellow]")
        return

    table = Table(title="Scan History", show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Prompt", style="white")
    table.add_column("Status", style="bold", no_wrap=True)
    table.add_column("Detections", justify="right", no_wrap=True)
    table.add_column("Time", justify="right", no_wrap=True)

    for i, (prompt, result) in enumerate(scan_history, 1):
        # Truncate long prompts
        display_prompt = prompt if len(prompt) <= 50 else prompt[:47] + "..."

        if result.scan_result.has_threats:
            status = "[red]THREAT[/red]"
        else:
            status = "[green]SAFE[/green]"

        detection_count = len(result.scan_result.l1_result.detections)

        table.add_row(
            str(i),
            display_prompt,
            status,
            str(detection_count),
            f"{result.duration_ms:.1f}ms",
        )

    console.print(table)
    console.print()
    console.print(f"[bold]Total:[/bold] {len(scan_history)} scans in this session")


def _handle_show(scan_history: list[tuple[str, ScanPipelineResult]], args: str) -> None:
    """
    Handle show command.

    Args:
        scan_history: List of (prompt, result) tuples
        args: Scan ID to show
    """
    if not args:
        console.print("[yellow]Usage: show <id>[/yellow]")
        console.print("Example: show 1")
        return

    try:
        scan_id = int(args)
    except ValueError:
        console.print(f"[red]Invalid scan ID: {args}[/red]")
        console.print("ID must be a number (e.g., 'show 1')")
        return

    if scan_id < 1 or scan_id > len(scan_history):
        console.print(f"[red]Scan #{scan_id} not found[/red]")
        console.print(f"Valid range: 1-{len(scan_history)}")
        return

    # Show detailed scan result
    prompt, result = scan_history[scan_id - 1]

    console.print(f"[bold]Scan #{scan_id}[/bold]")
    console.print()
    console.print("[bold]Prompt:[/bold]")
    console.print(f"  {prompt}")
    console.print()

    display_scan_result(result)


def _handle_rules(raxe: Raxe, args: str) -> None:
    """
    Handle rules command.

    Args:
        raxe: Raxe client instance
        args: Command arguments (list or rule_id)
    """
    try:
        all_rules = raxe.get_all_rules()
    except Exception as e:
        display_error("Failed to load rules", str(e))
        return

    if not all_rules:
        console.print("[yellow]No rules loaded[/yellow]")
        return

    # Default to list if no args
    if not args or args == "list":
        # Display rules list
        table = Table(title="Detection Rules", show_header=True, header_style="bold cyan")
        table.add_column("Rule ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="white")
        table.add_column("Severity", style="bold", no_wrap=True)

        for rule in sorted(all_rules, key=lambda r: r.rule_id)[:20]:  # Limit to 20
            severity_color = _get_severity_color(rule.severity.value)
            table.add_row(
                rule.rule_id,
                rule.name[:40] + "..." if len(rule.name) > 40 else rule.name,
                f"[{severity_color}]{rule.severity.value.upper()}[/]",
            )

        console.print(table)
        console.print()
        console.print(f"[dim]Showing 20/{len(all_rules)} rules. Use 'rules <rule_id>' for details.[/dim]")

    else:
        # Show specific rule
        rule_id = args
        rule = next((r for r in all_rules if r.rule_id == rule_id), None)

        if not rule:
            console.print(f"[red]Rule not found: {rule_id}[/red]")
            console.print("Use 'rules list' to see available rules")
            return

        # Display rule details
        console.print(f"[bold cyan]{rule.rule_id}@{rule.version}[/bold cyan] - {rule.name}")
        console.print()
        console.print(f"[bold]Description:[/bold] {rule.description}")
        console.print()
        console.print(f"[bold]Family:[/bold] {rule.family.value} / {rule.sub_family}")
        severity_color = _get_severity_color(rule.severity.value)
        console.print(f"[bold]Severity:[/bold] [{severity_color}]{rule.severity.value.upper()}[/]")
        console.print(f"[bold]Confidence:[/bold] {rule.confidence * 100:.1f}%")
        console.print()
        console.print(f"[bold]Patterns:[/bold] {len(rule.patterns)} regex patterns")


def _handle_stats(raxe: Raxe) -> None:
    """
    Handle stats command.

    Args:
        raxe: Raxe client instance
    """
    try:
        stats = raxe.stats
        display_stats(stats)
    except Exception as e:
        display_error("Failed to get statistics", str(e))


def _handle_config() -> None:
    """Handle config command."""
    config_file = Path.home() / ".raxe" / "config.yaml"

    if not config_file.exists():
        console.print("[yellow]No configuration file found[/yellow]")
        console.print(f"Run 'raxe init' to create: {config_file}")
        return

    console.print(f"[bold]Configuration:[/bold] {config_file}")
    console.print()

    # Read and display config
    try:
        config_content = config_file.read_text()
        console.print(config_content)
    except Exception as e:
        display_error("Failed to read configuration", str(e))


def _get_severity_color(severity: str) -> str:
    """Get rich color for severity level."""
    color_map = {
        "critical": "red bold",
        "high": "red",
        "medium": "yellow",
        "low": "blue",
        "info": "green",
    }
    return color_map.get(severity.lower(), "white")


if __name__ == "__main__":
    repl()
