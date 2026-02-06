"""CLI commands for MCP (Model Context Protocol) server and gateway.

Commands:
- raxe mcp serve [--transport stdio] [--log-level debug|info|warn|error] [--quiet]
- raxe mcp gateway --upstream <command> [--config <file>] [--on-threat log|block]
- raxe mcp audit <config-file>
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import click
from rich.table import Table

from raxe.cli.exit_codes import EXIT_CONFIG_ERROR, EXIT_INVALID_INPUT, EXIT_SCAN_ERROR
from raxe.cli.output import console


def _check_mcp_available() -> tuple[bool, str | None]:
    """Check if MCP SDK is available.

    Returns:
        Tuple of (is_available, error_message)
    """
    try:
        import mcp  # noqa: F401
        from mcp.server import Server  # noqa: F401
        from mcp.server.stdio import stdio_server  # noqa: F401

        return True, None
    except ImportError as e:
        return False, f"ImportError: {e}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


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
    """MCP (Model Context Protocol) server and security gateway commands.

    RAXE provides two MCP integration modes:

    \b
    1. MCP Server (raxe mcp serve)
       RAXE exposes threat detection as MCP tools that AI assistants
       can call directly.

    \b
    2. MCP Security Gateway (raxe mcp gateway)
       RAXE acts as a transparent proxy between MCP clients and servers,
       scanning ALL traffic for threats. Protects any MCP server.
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
    be called by AI assistants like Claude Desktop and Cursor.

    \b
    Examples:
        raxe mcp serve                    # Start with default options
        raxe mcp serve --log-level debug  # Enable debug logging
        raxe mcp serve --quiet            # Suppress banner

    \b
    Claude Desktop Configuration (~/.config/claude/claude_desktop_config.json):
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
    mcp_available, mcp_error = _check_mcp_available()
    if not mcp_available:
        console.print("[red]Error:[/red] MCP SDK is not available")
        console.print()
        if mcp_error:
            console.print(f"[dim]Details: {mcp_error}[/dim]")
            console.print()
        console.print("Install with: [cyan]pip install raxe[mcp][/cyan]")
        console.print("  or: [cyan]pip install mcp[/cyan]")
        sys.exit(EXIT_CONFIG_ERROR)

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
        exit_code = EXIT_SCAN_ERROR
    finally:
        # Always flush telemetry on exit
        try:
            from raxe.infrastructure.telemetry.flush_helper import ensure_telemetry_flushed

            ensure_telemetry_flushed(timeout_seconds=2.0)
        except Exception:  # noqa: S110
            pass

    sys.exit(exit_code)


@mcp.command("gateway")
@click.option(
    "--upstream",
    "-u",
    multiple=True,
    help="Upstream MCP server command (can specify multiple)",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to gateway config file (mcp-security.yaml)",
)
@click.option(
    "--on-threat",
    type=click.Choice(["log", "block", "warn"]),
    default="log",
    help="Action on threat detection (default: log)",
)
@click.option(
    "--severity-threshold",
    type=click.Choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
    default="HIGH",
    help="Minimum severity to trigger action (default: HIGH)",
)
@click.option(
    "--no-l2",
    is_flag=True,
    help="Disable L2 ML detection for faster scanning",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def gateway(
    upstream: tuple[str, ...],
    config: str | None,
    on_threat: str,
    severity_threshold: str,
    no_l2: bool,
    verbose: bool,
) -> None:
    """Start the MCP Security Gateway.

    The gateway acts as a transparent proxy between MCP clients (like Claude
    Desktop) and MCP servers. It intercepts and scans ALL traffic for threats.

    \b
    Examples:
        # Protect a filesystem server
        raxe mcp gateway -u "npx @modelcontextprotocol/server-filesystem /tmp"

        # Block on high severity threats
        raxe mcp gateway -u "npx @modelcontextprotocol/server-git" --on-threat block

        # Use config file
        raxe mcp gateway --config mcp-security.yaml

    \b
    Config file format (mcp-security.yaml):
        gateway:
          listen: stdio
          default_policy:
            on_threat: log
            severity_threshold: HIGH

        upstreams:
          - name: filesystem
            command: npx
            args: ["@modelcontextprotocol/server-filesystem", "/tmp"]
            scan_tool_calls: true
            scan_tool_responses: true

    \b
    Claude Desktop Configuration:
        {
          "mcpServers": {
            "raxe-gateway": {
              "command": "raxe",
              "args": ["mcp", "gateway", "-u", "npx @modelcontextprotocol/server-filesystem /tmp"]
            }
          }
        }
    """
    # Check MCP availability
    mcp_available, mcp_error = _check_mcp_available()
    if not mcp_available:
        console.print("[red]Error:[/red] MCP SDK is not available")
        console.print()
        if mcp_error:
            console.print(f"[dim]Details: {mcp_error}[/dim]")
            console.print()
        console.print("Install with: [cyan]pip install raxe[mcp][/cyan]")
        sys.exit(EXIT_CONFIG_ERROR)

    from raxe.mcp.config import GatewayConfig, UpstreamConfig
    from raxe.mcp.gateway import RaxeMCPGateway

    # Load config
    if config:
        gateway_config = GatewayConfig.load(config)
    else:
        gateway_config = GatewayConfig()

    # Apply CLI overrides
    gateway_config.default_policy.on_threat = on_threat  # type: ignore[assignment]
    gateway_config.default_policy.severity_threshold = severity_threshold  # type: ignore[assignment]
    gateway_config.l2_enabled = not no_l2
    gateway_config.verbose = verbose

    # Add upstream from CLI
    for upstream_cmd in upstream:
        parts = upstream_cmd.split()
        if parts:
            upstream_config = UpstreamConfig(
                name=parts[0],
                command=parts[0],
                args=parts[1:] if len(parts) > 1 else [],
            )
            gateway_config.upstreams.append(upstream_config)

    if not gateway_config.upstreams:
        console.print("[red]Error:[/red] No upstream servers configured")
        console.print()
        console.print("Specify upstream with: [cyan]--upstream 'command args'[/cyan]")
        console.print("  or provide: [cyan]--config mcp-security.yaml[/cyan]")
        sys.exit(EXIT_INVALID_INPUT)

    # Show startup info
    console.print("[bold cyan]RAXE MCP Security Gateway[/bold cyan]")
    console.print(f"  On threat: {on_threat}")
    console.print(f"  Severity threshold: {severity_threshold}")
    console.print(f"  L2 ML detection: {'Disabled' if no_l2 else 'Enabled'}")
    console.print()
    console.print("[bold]Protected upstreams:[/bold]")
    for up in gateway_config.upstreams:
        console.print(f"  - {up.name}")
    console.print()
    console.print("[dim]Press Ctrl+C to shutdown[/dim]")
    console.print()

    # Run gateway
    gw = RaxeMCPGateway(gateway_config)

    try:
        asyncio.run(gw.run())
    except KeyboardInterrupt:
        console.print()
        console.print("[dim]Gateway stopped[/dim]")

        # Show stats
        stats = gw.get_stats()
        if stats["requests_forwarded"] > 0 or stats["requests_blocked"] > 0:
            console.print()
            console.print("[bold]Session Statistics:[/bold]")
            console.print(f"  Requests forwarded: {stats['requests_forwarded']}")
            console.print(f"  Requests blocked: {stats['requests_blocked']}")
            console.print(f"  Threats detected: {stats['threats_detected']}")
            console.print(f"  Total scan time: {stats['total_scan_time_ms']:.1f}ms")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(EXIT_SCAN_ERROR)
    finally:
        try:
            from raxe.infrastructure.telemetry.flush_helper import ensure_telemetry_flushed

            ensure_telemetry_flushed(timeout_seconds=2.0)
        except Exception:  # noqa: S110
            pass


@mcp.command("audit")
@click.argument("config_file", type=click.Path(exists=True))
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output results as JSON",
)
def audit(config_file: str, json_output: bool) -> None:
    """Audit an MCP configuration file for security issues.

    Analyzes Claude Desktop or custom MCP configuration files and
    reports potential security concerns.

    \b
    Examples:
        raxe mcp audit ~/.config/claude/claude_desktop_config.json
        raxe mcp audit mcp-security.yaml --json
    """
    config_path = Path(config_file)

    # Load config file
    try:
        with open(config_path) as f:
            if config_path.suffix in (".yaml", ".yml"):
                import yaml

                config_data = yaml.safe_load(f)
            else:
                config_data = json.load(f)
    except Exception as e:
        console.print(f"[red]Error loading config:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    # Audit the configuration
    issues = _audit_mcp_config(config_data)

    if json_output:
        console.print(json.dumps({"issues": issues, "total": len(issues)}, indent=2))
    else:
        _display_audit_results(config_path, issues)


def _audit_mcp_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Audit an MCP configuration for security issues.

    Args:
        config: Parsed configuration dictionary

    Returns:
        List of issue dictionaries
    """
    issues: list[dict[str, Any]] = []

    # Check for mcpServers (Claude Desktop format)
    mcp_servers = config.get("mcpServers", {})
    if not mcp_servers:
        # Try upstreams (RAXE format)
        mcp_servers = {
            u.get("name", f"upstream_{i}"): u for i, u in enumerate(config.get("upstreams", []))
        }

    for name, server_config in mcp_servers.items():
        # Check for dangerous commands
        command = server_config.get("command", "")
        args = server_config.get("args", [])

        # Check for filesystem access
        if "filesystem" in command.lower() or any("filesystem" in str(a).lower() for a in args):
            # Check if path is sensitive
            path_args = [a for a in args if isinstance(a, str) and a.startswith("/")]
            for path in path_args:
                if path in ("/", "/home", "/Users", "/etc", "/root"):
                    issues.append(
                        {
                            "server": name,
                            "severity": "HIGH",
                            "type": "sensitive_path",
                            "message": f"Filesystem server has access to sensitive path: {path}",
                            "recommendation": "Restrict to specific directories",
                        }
                    )
                elif path.startswith("/tmp") or path.startswith("/var/tmp"):  # noqa: S108
                    issues.append(
                        {
                            "server": name,
                            "severity": "LOW",
                            "type": "temp_path",
                            "message": f"Filesystem server has access to temp directory: {path}",
                            "recommendation": "Consider if temp access is necessary",
                        }
                    )

        # Check for shell/exec capabilities
        if any(keyword in command.lower() for keyword in ["shell", "exec", "bash", "sh", "cmd"]):
            issues.append(
                {
                    "server": name,
                    "severity": "CRITICAL",
                    "type": "shell_access",
                    "message": "Server has shell execution capabilities",
                    "recommendation": "Use RAXE gateway to monitor tool calls",
                }
            )

        # Check for database access
        if any(
            keyword in command.lower() for keyword in ["postgres", "mysql", "sqlite", "database"]
        ):
            issues.append(
                {
                    "server": name,
                    "severity": "HIGH",
                    "type": "database_access",
                    "message": "Server has database access capabilities",
                    "recommendation": "Ensure read-only access and use RAXE gateway",
                }
            )

        # Check for environment variables with secrets
        env = server_config.get("env", {})
        for env_key in env:
            if any(
                keyword in env_key.upper()
                for keyword in ["KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL"]
            ):
                issues.append(
                    {
                        "server": name,
                        "severity": "MEDIUM",
                        "type": "env_secrets",
                        "message": f"Environment variable may contain secrets: {env_key}",
                        "recommendation": "Review if this credential is necessary",
                    }
                )

        # Check if not using RAXE gateway
        if "raxe" not in command.lower():
            issues.append(
                {
                    "server": name,
                    "severity": "INFO",
                    "type": "no_raxe_protection",
                    "message": "Server is not protected by RAXE gateway",
                    "recommendation": "Consider using: raxe mcp gateway --upstream '<command>'",
                }
            )

    return issues


def _display_audit_results(config_path: Path, issues: list[dict[str, Any]]) -> None:
    """Display audit results in a formatted table.

    Args:
        config_path: Path to audited config file
        issues: List of issues found
    """
    console.print(f"[bold]MCP Configuration Audit: {config_path}[/bold]")
    console.print()

    if not issues:
        console.print("[green]No issues found![/green]")
        return

    # Group by severity
    severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]

    table = Table(show_header=True, header_style="bold")
    table.add_column("Severity")
    table.add_column("Server")
    table.add_column("Issue")
    table.add_column("Recommendation")

    for severity in severity_order:
        severity_issues = [i for i in issues if i["severity"] == severity]
        for issue in severity_issues:
            severity_style = {
                "CRITICAL": "[red bold]",
                "HIGH": "[red]",
                "MEDIUM": "[yellow]",
                "LOW": "[blue]",
                "INFO": "[dim]",
            }.get(severity, "")

            table.add_row(
                f"{severity_style}{severity}[/]",
                issue["server"],
                issue["message"],
                issue.get("recommendation", ""),
            )

    console.print(table)
    console.print()

    # Summary
    critical_count = sum(1 for i in issues if i["severity"] == "CRITICAL")
    high_count = sum(1 for i in issues if i["severity"] == "HIGH")

    if critical_count > 0:
        msg = f"Found {critical_count} CRITICAL issues that require immediate attention!"
        console.print(f"[red bold]{msg}[/red bold]")
    elif high_count > 0:
        console.print(f"[red]Found {high_count} HIGH severity issues.[/red]")
    else:
        console.print(f"[yellow]Found {len(issues)} issues to review.[/yellow]")


@mcp.command("generate-config")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="mcp-security.yaml",
    help="Output file path (default: mcp-security.yaml)",
)
def generate_config(output: str) -> None:
    """Generate a sample MCP gateway configuration file.

    Creates a template configuration file that can be customized
    for your MCP server setup.

    \b
    Example:
        raxe mcp generate-config
        raxe mcp generate-config -o my-config.yaml
    """
    sample_config = """# RAXE MCP Security Gateway Configuration
# Generated by: raxe mcp generate-config

# Gateway settings
gateway:
  # Transport: stdio (for Claude Desktop) or http
  listen: stdio

  # HTTP settings (if listen: http)
  # host: 127.0.0.1
  # port: 8080

  # Default policy for all upstreams
  default_policy:
    # Action on threat: log, block, or warn
    on_threat: log
    # Minimum severity to trigger action: LOW, MEDIUM, HIGH, CRITICAL
    severity_threshold: HIGH
    # Rate limit (requests per minute, 0 = unlimited)
    rate_limit_rpm: 60

  # Enable telemetry (privacy-preserving)
  telemetry_enabled: true

  # Enable L2 ML detection (more accurate but slower)
  l2_enabled: true

# Upstream MCP servers to protect
upstreams:
  # Example: Filesystem server
  - name: filesystem
    command: npx
    args:
      - "@modelcontextprotocol/server-filesystem"
      - "/path/to/safe/directory"
    # Scan settings
    scan_tool_calls: true
    scan_tool_responses: true
    scan_resources: true
    # Optional: override policy for this upstream
    # policy:
    #   on_threat: block
    #   severity_threshold: MEDIUM

  # Example: Git server
  # - name: git
  #   command: npx
  #   args:
  #     - "@modelcontextprotocol/server-git"
  #   scan_tool_calls: true
  #   scan_tool_responses: true

  # Example: Custom server with environment variables
  # - name: custom
  #   command: /path/to/server
  #   args: []
  #   env:
  #     API_KEY: "your-key"
"""

    output_path = Path(output)
    output_path.write_text(sample_config)
    console.print(f"[green]Generated config file:[/green] {output_path}")
    console.print()
    console.print("Edit the file and run:")
    console.print(f"  [cyan]raxe mcp gateway --config {output}[/cyan]")


# Export the group
__all__ = ["mcp"]
