"""CLI command for starting the RAXE JSON-RPC server.

This command starts a JSON-RPC server that can be used for integration
with AI platforms like OpenClaw. The server communicates via stdio
using line-delimited JSON.

Usage:
    raxe serve                     # Start with defaults
    raxe serve --quiet             # No startup banner
    raxe serve --log-level debug   # Enable debug logging

Example JSON-RPC request:
    {"jsonrpc":"2.0","id":"1","method":"version","params":{}}
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import click

from raxe import __version__
from raxe.cli.error_handler import handle_cli_error

if TYPE_CHECKING:
    pass


def _print_banner() -> None:
    """Print startup banner to stderr.

    Banner goes to stderr to keep stdout clean for JSON-RPC communication.
    """
    # Print to stderr so stdout remains clean for JSON-RPC
    banner = f"""RAXE JSON-RPC Server v{__version__}
Mode: jsonrpc (stdio)
Ready to accept requests...
"""
    sys.stderr.write(banner)
    sys.stderr.flush()


@click.command()
@click.option(
    "--mode",
    type=click.Choice(["jsonrpc"]),
    default="jsonrpc",
    help="Server mode (default: jsonrpc)",
)
@click.option(
    "--log-level",
    type=click.Choice(["debug", "info", "warning", "error"]),
    default="info",
    help="Logging level (default: info)",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress startup banner",
)
@handle_cli_error
def serve(
    mode: str,
    log_level: str,
    quiet: bool,
) -> None:
    """Start RAXE JSON-RPC server for integration with AI platforms like OpenClaw.

    The server reads JSON-RPC requests from stdin and writes responses to stdout.
    Each request/response is a single line of JSON.

    \\b
    Available Methods:
      scan           - Scan text for security threats
      scan_fast      - Fast scan using L1 only
      scan_tool_call - Validate a tool call before execution
      scan_batch     - Batch scan multiple prompts
      version        - Get server version information
      health         - Check server health
      stats          - Get server statistics

    \\b
    Examples:
      # Start server
      raxe serve

      # Test with echo
      echo '{"jsonrpc":"2.0","id":"1","method":"version","params":{}}' | raxe serve

      # Quiet mode (no banner)
      raxe serve --quiet

    \\b
    Exit Codes:
      0  Normal shutdown (EOF, SIGINT, or SIGTERM)
      1  Server error
    """
    import logging

    from raxe.application.jsonrpc.dispatcher import JsonRpcDispatcher
    from raxe.application.jsonrpc.handlers import register_handlers
    from raxe.infrastructure.jsonrpc.server import JsonRpcServer
    from raxe.infrastructure.jsonrpc.transports.stdio import StdioTransport
    from raxe.sdk.client import Raxe

    # Configure logging level
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,  # Log to stderr to keep stdout for JSON-RPC
    )
    logger = logging.getLogger("raxe.jsonrpc")

    # Print banner unless quiet mode
    if not quiet:
        _print_banner()

    try:
        # Initialize Raxe client
        logger.info("Initializing Raxe client...")
        raxe = Raxe()
        logger.info(f"Raxe client initialized: {raxe.stats['rules_loaded']} rules loaded")

        # Register handlers
        logger.info("Registering JSON-RPC handlers...")
        register_handlers(raxe)
        logger.info("Handlers registered")

        # Create transport (stdio)
        transport = StdioTransport()

        # Create dispatcher
        dispatcher = JsonRpcDispatcher()

        # Create and start server
        logger.info("Starting JSON-RPC server...")
        server = JsonRpcServer(transport=transport, dispatcher=dispatcher)

        # Start server (blocks until stopped)
        server.start()

        logger.info("Server stopped normally")

    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        if not quiet:
            sys.stderr.write("\nShutting down...\n")
            sys.stderr.flush()
        logger.info("Server stopped by user")

    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


# Export for registration
__all__ = ["serve"]
