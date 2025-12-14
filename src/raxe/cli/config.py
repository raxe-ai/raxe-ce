"""CLI commands for configuration management."""
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from raxe.infrastructure.config.yaml_config import RaxeConfig, create_default_config
from raxe.utils.logging import get_logger

logger = get_logger(__name__)
console = Console()


def _send_key_upgrade_event(old_api_key: str | None, new_api_key: str) -> None:
    """Send a key_upgrade telemetry event when API key changes.

    This function handles detecting the key type change and sending
    the appropriate telemetry event with key IDs for server-side
    event linking.

    Args:
        old_api_key: The previous API key (may be None or empty).
        new_api_key: The new API key being set.
    """
    try:
        from raxe.domain.telemetry.events import create_key_upgrade_event
        from raxe.infrastructure.telemetry.credential_store import (
            CredentialStore,
            compute_key_id,
            validate_key_format,
        )

        # Skip if new key is empty or same as old
        if not new_api_key or new_api_key == old_api_key:
            return

        # Validate new key format
        try:
            new_key_type = validate_key_format(new_api_key)
        except Exception:
            # Invalid key format, skip telemetry
            return

        # Map key type to tier for telemetry
        # "temporary" -> "temp", "live"/"test" -> "community" (default tier)
        key_type_to_tier = {
            "temporary": "temp",
            "live": "community",
            "test": "community",
        }

        new_tier = key_type_to_tier.get(new_key_type, "community")

        # Compute key IDs
        new_key_id = compute_key_id(new_api_key)
        previous_key_id: str | None = None
        previous_tier: str | None = None
        days_on_previous: int | None = None

        # Try to get old key info from credential store
        if old_api_key:
            try:
                old_key_type = validate_key_format(old_api_key)
                previous_key_id = compute_key_id(old_api_key)
                previous_tier = key_type_to_tier.get(old_key_type, "temp")
            except Exception:
                pass
        else:
            # Check credential store for existing credentials
            store = CredentialStore()
            existing = store.load()
            if existing:
                previous_key_id = compute_key_id(existing.api_key)
                previous_tier = key_type_to_tier.get(existing.key_type, "temp")
                # Calculate days on previous
                try:
                    from datetime import datetime, timezone
                    created = datetime.fromisoformat(
                        existing.created_at.replace("Z", "+00:00")
                    )
                    now = datetime.now(timezone.utc)
                    days_on_previous = (now - created).days
                except Exception:
                    pass

        # Only send if this looks like an actual upgrade (not just setting same tier)
        if previous_tier and previous_tier == new_tier and previous_tier != "temp":
            # Same tier, not an upgrade - skip
            return

        # Create and send the event
        event = create_key_upgrade_event(
            previous_key_type=previous_tier or "temp",
            new_key_type=new_tier if new_tier != "temp" else "community",
            previous_key_id=previous_key_id,
            new_key_id=new_key_id,
            days_on_previous=days_on_previous,
            conversion_trigger="manual_upgrade",
        )

        # Try to send via telemetry sender
        try:
            from raxe.infrastructure.telemetry.sender import TelemetrySender
            sender = TelemetrySender()
            sender.send(event)
            logger.debug("key_upgrade_event_sent", new_key_id=new_key_id)
        except Exception as send_error:
            logger.debug(
                "key_upgrade_event_send_failed",
                error=str(send_error)
            )

    except Exception as e:
        # Don't fail the config update if telemetry fails
        logger.debug("key_upgrade_event_creation_failed", error=str(e))


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

        # Capture old API key before update (for telemetry)
        old_api_key: str | None = None
        if key == "core.api_key":
            old_api_key = config_obj.core.api_key

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

        # Send key_upgrade event if API key changed
        if key == "core.api_key":
            _send_key_upgrade_event(old_api_key, value)

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
