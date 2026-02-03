"""CLI commands for MCP (Model Context Protocol) server.

Commands:
- raxe mcp serve [--transport stdio] [--log-level debug|info|warn|error] [--quiet]
"""

import sys

import click
from rich.console import Console

console = Console()


def _check_mcp_available() -> bool:
    """Check if MCP SDK is available."""
    try:
        import mcp  # noqa: F401

        return True
    except ImportError:
        return False


def run_server(
    transport: str = "stdio",
    verbose: bool = False,
    quiet: bool = False,
) -> int:
    """Run the MCP server.

    Wrapper around raxe.mcp.server.run_server.

    Args:
        transport: Transport protocol ("stdio")
        verbose: Enable verbose logging
        quiet: Suppress output

    Returns:
        Exit code (0 for success)
    """
    from raxe.mcp.server import run_server as _run_server

    return _run_server(transport=transport, verbose=verbose)


@click.group()
def mcp() -> None:
    """MCP (Model Context Protocol) server commands.

    Start an MCP server to expose RAXE threat detection capabilities
    to AI assistants like Claude Desktop and OpenClaw.
    """
    pass


@mcp.command("serve")
@click.option(
    "--transport",
    type=click.Choice(["stdio"]),
    default="stdio",
    help="Transport protocol (default: stdio)",
)
@click.option(
    "--log-level",
    type=click.Choice(["debug", "info", "warn", "error"]),
    default="info",
    help="Log level (default: info)",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress startup banner and non-error output",
)
def serve(transport: str, log_level: str, quiet: bool) -> None:
    """Start the MCP server for AI assistant integration.

    The MCP server exposes RAXE threat detection as tools that can
    be called by AI assistants like Claude Desktop and OpenClaw.

    \b
    Examples:
        raxe mcp serve                    # Start with default options
        raxe mcp serve --log-level debug  # Enable debug logging
        raxe mcp serve --quiet            # Suppress banner

    \b
    Claude Desktop Configuration (~/.config/claude-desktop/claude_desktop_config.json):
        {
          "mcpServers": {
            "raxe-security": {
              "command": "raxe",
              "args": ["mcp", "serve"]
            }
          }
        }
    """
    # Check MCP availability first
    if not _check_mcp_available():
        console.print("[red]Error:[/red] MCP SDK is not installed")
        console.print()
        console.print("Install with: [cyan]pip install raxe[mcp][/cyan]")
        console.print("  or: [cyan]pip install mcp[/cyan]")
        sys.exit(1)

    verbose = log_level == "debug"

    if not quiet:
        console.print("[bold cyan]RAXE MCP Server[/bold cyan]")
        console.print(f"  Transport: {transport}")
        console.print(f"  Log level: {log_level}")
        console.print()
        console.print("[dim]Press Ctrl+C to shutdown[/dim]")
        console.print()

    exit_code = 0
    try:
        exit_code = run_server(transport=transport, verbose=verbose, quiet=quiet)
    except KeyboardInterrupt:
        if not quiet:
            console.print()
            console.print("[dim]Shutdown complete[/dim]")
        exit_code = 0
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        exit_code = 1
    finally:
        # Always flush telemetry on exit
        try:
            from raxe.infrastructure.telemetry.flush_helper import ensure_telemetry_flushed

            ensure_telemetry_flushed(timeout_seconds=2.0)
        except Exception:  # noqa: S110
            pass

    sys.exit(exit_code)


# Export the group
__all__ = ["mcp"]
