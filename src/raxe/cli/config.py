"""CLI commands for configuration management."""
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from raxe.infrastructure.config.yaml_config import RaxeConfig, create_default_config
from raxe.utils.logging import get_logger

logger = get_logger(__name__)
console = Console()


@click.group()
def config() -> None:
    """Manage RAXE configuration."""
    pass


@config.command()
@click.option(
    "--path",
    type=click.Path(exists=True, path_type=Path),
    help="Config file path (default: ~/.raxe/config.yaml)",
)
def show(path: Path | None) -> None:
    """Display current configuration."""
    try:
        config_obj = RaxeConfig.load(config_path=path)

        # Create table
        table = Table(title="RAXE Configuration", show_header=True, header_style="bold cyan")
        table.add_column("Section", style="bold")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")

        # Add core settings
        table.add_row("core", "environment", config_obj.core.environment)
        table.add_row("core", "version", config_obj.core.version)
        table.add_row("core", "api_key", "***" if config_obj.core.api_key else "(not set)")

        # Add detection settings
        table.add_row("detection", "l1_enabled", str(config_obj.detection.l1_enabled))
        table.add_row("detection", "l2_enabled", str(config_obj.detection.l2_enabled))
        table.add_row("detection", "mode", config_obj.detection.mode)
        table.add_row(
            "detection",
            "confidence_threshold",
            str(config_obj.detection.confidence_threshold),
        )

        # Add telemetry settings
        table.add_row("telemetry", "enabled", str(config_obj.telemetry.enabled))
        table.add_row("telemetry", "batch_size", str(config_obj.telemetry.batch_size))
        table.add_row("telemetry", "flush_interval", str(config_obj.telemetry.flush_interval))

        # Add performance settings
        table.add_row(
            "performance",
            "max_queue_size",
            str(config_obj.performance.max_queue_size),
        )
        table.add_row(
            "performance",
            "scan_timeout",
            str(config_obj.performance.scan_timeout),
        )

        # Add logging settings
        table.add_row("logging", "level", config_obj.logging.level)
        table.add_row("logging", "directory", config_obj.logging.directory)

        console.print(table)

        logger.info("config_show_completed")

    except Exception as e:
        console.print(f"[red]Error loading config:[/red] {e}")
        logger.error("config_show_failed", error=str(e))
        raise click.Abort() from e


@config.command()
@click.argument("key")
@click.argument("value")
@click.option(
    "--path",
    type=click.Path(path_type=Path),
    help="Config file path (default: ~/.raxe/config.yaml)",
)
def set_value(key: str, value: str, path: Path | None) -> None:
    """Set a configuration value.

    KEY should be in format: section.key (e.g., detection.mode)
    VALUE is the new value to set
    """
    try:
        # Load config
        if path is None:
            path = Path.home() / ".raxe" / "config.yaml"

        if path.exists():
            config_obj = RaxeConfig.from_file(path)
        else:
            config_obj = RaxeConfig()

        # Update value
        config_obj.update(key, value)

        # Validate
        errors = config_obj.validate()
        if errors:
            console.print("[red]Validation errors:[/red]")
            for error in errors:
                console.print(f"  - {error}")
            raise click.Abort()

        # Save
        config_obj.save(path)

        console.print(f"[green]✓[/green] Set {key} = {value}")
        logger.info("config_set_completed", key=key)

    except ValueError as e:
        console.print(f"[red]Invalid key:[/red] {e}")
        logger.error("config_set_failed", key=key, error=str(e))
        raise click.Abort() from e
    except Exception as e:
        console.print(f"[red]Error updating config:[/red] {e}")
        logger.error("config_set_failed", key=key, error=str(e))
        raise click.Abort() from e


@config.command()
@click.option(
    "--path",
    type=click.Path(path_type=Path),
    help="Config file path (default: ~/.raxe/config.yaml)",
)
@click.confirmation_option(prompt="Reset configuration to defaults?")
def reset(path: Path | None) -> None:
    """Reset configuration to defaults."""
    try:
        if path is None:
            path = Path.home() / ".raxe" / "config.yaml"

        # Create default config
        create_default_config(path)

        console.print("[green]✓[/green] Configuration reset to defaults")
        console.print(f"Config file: {path}")

        logger.info("config_reset_completed")

    except Exception as e:
        console.print(f"[red]Error resetting config:[/red] {e}")
        logger.error("config_reset_failed", error=str(e))
        raise click.Abort() from e


@config.command()
@click.option(
    "--path",
    type=click.Path(exists=True, path_type=Path),
    help="Config file path (default: ~/.raxe/config.yaml)",
)
def validate(path: Path | None) -> None:
    """Validate configuration file."""
    try:
        config_obj = RaxeConfig.load(config_path=path)

        errors = config_obj.validate()

        if errors:
            console.print("[red]Validation failed:[/red]")
            for error in errors:
                console.print(f"  ✗ {error}")
            raise click.Abort()
        else:
            console.print("[green]✓ Configuration is valid[/green]")

        logger.info("config_validate_completed")

    except Exception as e:
        console.print(f"[red]Error validating config:[/red] {e}")
        logger.error("config_validate_failed", error=str(e))
        raise click.Abort() from e


@config.command()
@click.option(
    "--path",
    type=click.Path(exists=True, path_type=Path),
    help="Config file path (default: ~/.raxe/config.yaml)",
)
def edit(path: Path | None) -> None:
    """Open configuration file in editor."""
    import os
    import subprocess

    try:
        if path is None:
            path = Path.home() / ".raxe" / "config.yaml"

        # Create if doesn't exist
        if not path.exists():
            create_default_config(path)

        # Get editor
        editor = os.environ.get("EDITOR", "vi")

        # Open in editor
        subprocess.run([editor, str(path)])

        logger.info("config_edit_completed")

    except Exception as e:
        console.print(f"[red]Error opening editor:[/red] {e}")
        logger.error("config_edit_failed", error=str(e))
        raise click.Abort() from e
