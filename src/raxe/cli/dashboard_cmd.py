"""Dashboard command - real-time security monitoring dashboard."""

from __future__ import annotations

import click

from raxe.cli.output import console, display_error


@click.command()
@click.option(
    "--refresh",
    "-r",
    default=2.0,
    type=float,
    help="Refresh interval in seconds (default: 2)",
)
@click.option(
    "--theme",
    type=click.Choice(["raxe", "matrix", "cyber"]),
    default="raxe",
    help="Color theme (default: raxe)",
)
@click.option(
    "--animations",
    is_flag=True,
    help="Enable RGB chroma border animations (off by default for performance)",
)
@click.option(
    "--no-logo",
    is_flag=True,
    help="Hide the RAXE ASCII logo",
)
@click.pass_context
def dashboard(
    ctx: click.Context,
    refresh: float,
    theme: str,
    animations: bool,
    no_logo: bool,
) -> None:
    """Real-time security monitoring dashboard.

    Launch an interactive terminal dashboard showing:

    \b
    - Live threat detection feed
    - Severity breakdown
    - 24-hour trend sparklines
    - Performance metrics
    - System health status

    Navigate with arrow keys, press Enter to expand alerts.
    Press Q to quit.

    \b
    Examples:
        raxe dashboard              # Launch with default settings
        raxe dashboard --refresh 1  # Faster refresh rate
        raxe dashboard --theme matrix  # Green Matrix style
    """
    try:
        from raxe.cli.dashboard import DashboardConfig, DashboardOrchestrator

        # Build config
        config = DashboardConfig(
            refresh_interval_seconds=refresh,
            theme=theme,
            enable_animations=animations,  # Off by default, use --animations to enable
            show_logo=not no_logo,
        )

        # Create and start orchestrator
        orchestrator = DashboardOrchestrator(config=config, console=console)
        orchestrator.start()

    except KeyboardInterrupt:
        # Clean exit on Ctrl+C
        pass
    except ImportError as e:
        display_error(f"Dashboard dependencies not available: {e}")
        ctx.exit(1)
    except Exception as e:
        display_error(f"Dashboard error: {e}")
        ctx.exit(1)


@click.command()
@click.pass_context
def monitor(ctx: click.Context) -> None:
    """Alias for 'raxe dashboard'.

    Launch the real-time security monitoring dashboard.
    """
    # Invoke dashboard with default options
    ctx.invoke(dashboard)
