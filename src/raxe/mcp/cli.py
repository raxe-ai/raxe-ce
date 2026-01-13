"""
RAXE MCP Server CLI Entry Point.

This module provides the raxe-mcp command for running the MCP server.
Requires: pip install raxe[mcp]
"""

from __future__ import annotations

import sys


def main() -> int:
    """
    Main entry point for raxe-mcp command.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    # Check for MCP availability before importing heavy modules
    try:
        import mcp  # noqa: F401
    except ImportError:
        return 1

    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(
        prog="raxe-mcp",
        description="RAXE MCP Server - AI Security for LLM Assistants",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind for SSE transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to bind for SSE transport (default: 8765)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )

    args = parser.parse_args()

    if args.version:
        return 0

    # Import server after confirming dependencies are available
    try:
        from raxe.mcp.server import run_server

        return run_server(
            transport=args.transport,
            host=args.host,
            port=args.port,
            verbose=args.verbose,
        )
    except KeyboardInterrupt:
        return 0
    except Exception:
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
