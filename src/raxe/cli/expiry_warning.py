"""Proactive API key expiry warning utility.

Provides proactive warnings for users with temporary API keys that are
approaching expiration. This module checks credential expiry and returns
appropriate warning messages for display in the CLI.

Warning Thresholds:
- Days 8-14: No warning (plenty of time remaining)
- Days 4-7: Yellow warning banner (early warning)
- Days 2-3: Orange warning banner (urgent)
- Day 1: Red warning "Expires TODAY" (critical)
- Day 0 or past: Handled by CredentialExpiredError

Example usage:
    from raxe.cli.expiry_warning import get_expiry_warning, display_expiry_warning

    warning_msg, color = get_expiry_warning()
    if warning_msg:
        display_expiry_warning(warning_msg, color)
"""

from __future__ import annotations

import logging
from typing import Literal

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

logger = logging.getLogger(__name__)

# Warning thresholds (days remaining)
WARNING_THRESHOLD_YELLOW = 7  # Show yellow warning when <= 7 days remaining
WARNING_THRESHOLD_ORANGE = 3  # Show orange/urgent warning when <= 3 days remaining
WARNING_THRESHOLD_RED = 1  # Show red warning when <= 1 day remaining (expires today)


# Console URL for getting permanent keys - resolved from centralized endpoints
def _get_console_keys_url() -> str:
    """Get console keys URL from centralized endpoints."""
    from raxe.infrastructure.config.endpoints import get_console_url

    return f"{get_console_url()}/keys"


# Exported constant for backward compatibility
CONSOLE_KEYS_URL = "https://console.raxe.ai/keys"


def get_expiry_warning() -> tuple[str | None, Literal["yellow", "orange", "red", ""]]:
    """Check API key expiry and return warning message if applicable.

    This function checks if the current API key is a temporary key and
    calculates the days until expiry. Based on the days remaining, it
    returns an appropriate warning message.

    Returns:
        A tuple of (warning_message, color) where:
        - warning_message: The warning text to display, or None if no warning needed
        - color: "yellow" (early), "orange" (urgent), "red" (critical), "" (no warning)

    Warning Thresholds:
        - Days > 7: No warning (plenty of time)
        - Days 4-7: Yellow warning banner (early warning)
        - Days 2-3: Orange warning banner (urgent)
        - Day 1 (expires today): Red warning (critical)
        - Day 0 or expired: Handled by CredentialExpiredError (not here)

    Example:
        >>> warning, color = get_expiry_warning()
        >>> if warning:
        ...     print(f"[{color}]{warning}[/{color}]")
    """
    try:
        from raxe.infrastructure.telemetry.credential_store import CredentialStore

        store = CredentialStore()
        credentials = store.load()

        if credentials is None:
            # No credentials stored
            logger.debug("No credentials found, skipping expiry check")
            return None, ""

        if not credentials.is_temporary():
            # Permanent keys don't expire
            logger.debug("Permanent key detected, skipping expiry check")
            return None, ""

        # Calculate days until expiry
        days_remaining = credentials.days_until_expiry()

        if days_remaining is None:
            # No expiry date set (shouldn't happen for temp keys)
            logger.debug("No expiry date found for temporary key")
            return None, ""

        # Check if already expired (handled by CredentialExpiredError elsewhere)
        if days_remaining <= 0:
            # Already expired - let CredentialExpiredError handle this
            logger.debug("Key already expired, CredentialExpiredError should handle")
            return None, ""

        # Determine warning level based on days remaining
        if days_remaining <= WARNING_THRESHOLD_RED:
            # Expires today - red warning (critical)
            message = "Your API key expires TODAY"
            return message, "red"

        if days_remaining <= WARNING_THRESHOLD_ORANGE:
            # Days 2-3 - orange warning (urgent)
            if days_remaining == 2:
                message = "Your API key expires tomorrow"
            else:
                message = f"Your API key expires in {days_remaining} days"
            return message, "orange"

        if days_remaining <= WARNING_THRESHOLD_YELLOW:
            # Days 4-7 - yellow warning (early warning)
            message = f"Your API key expires in {days_remaining} days"
            return message, "yellow"

        # Plenty of time remaining - no warning
        logger.debug(f"Key has {days_remaining} days remaining, no warning needed")
        return None, ""

    except Exception as e:
        # Don't fail the CLI if expiry check fails
        logger.debug(f"Failed to check key expiry: {e}")
        return None, ""


def display_expiry_warning(
    console: Console,
    warning_message: str,
    color: Literal["yellow", "orange", "red"],
) -> None:
    """Display expiry warning banner in the CLI.

    Creates a visually distinct warning panel that draws user attention
    to their approaching key expiry.

    Args:
        console: Rich Console instance for output
        warning_message: The warning message to display
        color: "yellow" (early), "orange" (urgent), or "red" (critical)

    Example output:
        +-------------------------------------------------------------+
        |  Your API key expires in 3 days                             |
        |                                                             |
        |  Get a permanent key: raxe auth login                       |
        |  Or visit: https://console.raxe.ai/keys                     |
        +-------------------------------------------------------------+
    """
    # Choose icon and style based on severity
    if color == "red":
        icon = "!!"
        border_style = "red bold"
    elif color == "orange":
        icon = "!!"
        border_style = "dark_orange bold"
    else:
        icon = "!!"
        border_style = "yellow"

    # Build warning content
    content = Text()
    content.append(f"{icon}  ", style=f"{color} bold")
    content.append(warning_message, style=f"{color} bold")
    content.append("\n\n", style="")
    content.append("Get a permanent key: ", style="white")
    content.append("raxe auth login", style="cyan")
    content.append("\nOr visit: ", style="white")
    content.append(_get_console_keys_url(), style="blue underline")

    console.print(
        Panel(
            content,
            border_style=border_style,
            width=65,
            padding=(0, 2),
        )
    )
    console.print()


def check_and_display_expiry_warning(console: Console) -> bool:
    """Convenience function to check and display expiry warning if needed.

    Combines get_expiry_warning() and display_expiry_warning() into a single
    call for easy integration into CLI commands.

    Args:
        console: Rich Console instance for output

    Returns:
        True if a warning was displayed, False otherwise

    Example:
        >>> from rich.console import Console
        >>> from raxe.cli.expiry_warning import check_and_display_expiry_warning
        >>> console = Console()
        >>> if check_and_display_expiry_warning(console):
        ...     print("Warning was shown")
    """
    warning_message, color = get_expiry_warning()

    if warning_message and color:
        display_expiry_warning(console, warning_message, color)
        return True

    return False


def get_expiry_status() -> dict[str, int | str | bool | None]:
    """Get detailed expiry status for use in doctor command.

    Returns a dictionary with expiry status information suitable for
    the doctor health check command.

    Returns:
        Dictionary with keys:
        - is_temporary: bool - True if using a temporary key
        - days_remaining: int | None - Days until expiry (None if not temp)
        - status: str - "pass", "warning", or "fail"
        - message: str - Human-readable status message

    Example:
        >>> status = get_expiry_status()
        >>> print(f"Status: {status['status']}, Message: {status['message']}")
    """
    try:
        from raxe.infrastructure.telemetry.credential_store import CredentialStore

        store = CredentialStore()
        credentials = store.load()

        if credentials is None:
            return {
                "is_temporary": False,
                "days_remaining": None,
                "status": "warning",
                "message": "No API key configured",
            }

        if not credentials.is_temporary():
            return {
                "is_temporary": False,
                "days_remaining": None,
                "status": "pass",
                "message": f"Permanent key ({credentials.key_type})",
            }

        # Temporary key - check expiry
        days_remaining = credentials.days_until_expiry()

        if days_remaining is None:
            return {
                "is_temporary": True,
                "days_remaining": None,
                "status": "warning",
                "message": "Temporary key (expiry unknown)",
            }

        if days_remaining <= 0:
            return {
                "is_temporary": True,
                "days_remaining": 0,
                "status": "fail",
                "message": "Temporary key EXPIRED",
            }

        if days_remaining <= WARNING_THRESHOLD_RED:
            return {
                "is_temporary": True,
                "days_remaining": days_remaining,
                "status": "fail",
                "message": "Temporary key expires TODAY",
            }

        if days_remaining <= WARNING_THRESHOLD_ORANGE:
            # Days 2-3 - urgent warning
            return {
                "is_temporary": True,
                "days_remaining": days_remaining,
                "status": "fail",
                "message": f"Temporary key expires in {days_remaining} days (URGENT)",
            }

        if days_remaining <= WARNING_THRESHOLD_YELLOW:
            # Days 4-7 - early warning
            return {
                "is_temporary": True,
                "days_remaining": days_remaining,
                "status": "warning",
                "message": f"Temporary key ({days_remaining} days remaining)",
            }

        return {
            "is_temporary": True,
            "days_remaining": days_remaining,
            "status": "pass",
            "message": f"Temporary key ({days_remaining} days remaining)",
        }

    except Exception as e:
        logger.debug(f"Failed to get expiry status: {e}")
        return {
            "is_temporary": False,
            "days_remaining": None,
            "status": "warning",
            "message": "Could not check key status",
        }


def display_temp_key_first_run_notice(console: Console) -> None:
    """Display a one-time notice when a temporary key is first used.

    This notice appears ONCE per installation to inform users about:
    - They are using a 14-day temporary key
    - The exact expiration date
    - How to get a permanent key

    Args:
        console: Rich Console instance for output

    Example output:
        +-------------------------------------------------------------+
        |  Welcome to RAXE!                                           |
        |                                                             |
        |  You're using a temporary API key for evaluation.           |
        |                                                             |
        |  Expires: January 15, 2025 (14 days)                        |
        |                                                             |
        |  Get a permanent key anytime:                               |
        |    raxe auth                                                |
        |                                                             |
        |  Your scans and history will be preserved when you upgrade. |
        +-------------------------------------------------------------+
    """
    try:
        from raxe.infrastructure.telemetry.credential_store import CredentialStore

        store = CredentialStore()
        credentials = store.load()

        if credentials is None or not credentials.is_temporary():
            return

        # Calculate expiry date string
        expiry_str = "14 days"
        if credentials.expires_at:
            try:
                from datetime import datetime

                expiry_dt = datetime.fromisoformat(credentials.expires_at.replace("Z", "+00:00"))
                expiry_str = expiry_dt.strftime("%B %d, %Y")
                days_remaining = credentials.days_until_expiry()
                if days_remaining is not None:
                    expiry_str = f"{expiry_str} ({days_remaining} days)"
            except (ValueError, TypeError):
                pass

        # Build notice content
        content = Text()
        content.append("Welcome to RAXE!\n\n", style="bold cyan")
        content.append("You're using a ", style="white")
        content.append("temporary API key", style="yellow bold")
        content.append(" for evaluation.\n\n", style="white")
        content.append("Expires: ", style="white")
        content.append(expiry_str, style="cyan bold")
        content.append("\n\n", style="")
        content.append("Get a permanent key anytime:\n", style="white")
        content.append("  raxe auth\n\n", style="cyan")
        content.append(
            "Your scans and history will be preserved when you upgrade.",
            style="dim",
        )

        console.print(
            Panel(
                content,
                border_style="cyan",
                width=65,
                padding=(0, 2),
            )
        )
        console.print()

    except Exception as e:
        # Don't fail the CLI if notice display fails
        logger.debug(f"Failed to display first-run notice: {e}")


def check_and_display_first_run_notice(console: Console) -> bool:
    """Check if first-run notice should be shown and display it.

    This function checks if:
    1. The user has a temporary key
    2. The first-run notice hasn't been shown yet

    If both conditions are met, it displays the notice and marks it as shown.

    Args:
        console: Rich Console instance for output

    Returns:
        True if the notice was displayed, False otherwise
    """
    try:
        from raxe.infrastructure.telemetry.credential_store import CredentialStore

        store = CredentialStore()
        credentials = store.load()

        if credentials is None:
            return False

        if not credentials.is_temporary():
            return False

        if credentials.temp_key_notice_shown:
            return False

        # Display the notice
        display_temp_key_first_run_notice(console)

        # Mark as shown and save
        from dataclasses import replace

        updated_credentials = replace(credentials, temp_key_notice_shown=True)
        store.save(updated_credentials)

        return True

    except Exception as e:
        # Don't fail the CLI if notice check fails
        logger.debug(f"Failed to check first-run notice: {e}")
        return False


__all__ = [
    "CONSOLE_KEYS_URL",
    "WARNING_THRESHOLD_ORANGE",
    "WARNING_THRESHOLD_RED",
    "WARNING_THRESHOLD_YELLOW",
    "_get_console_keys_url",
    "check_and_display_expiry_warning",
    "check_and_display_first_run_notice",
    "display_expiry_warning",
    "display_temp_key_first_run_notice",
    "get_expiry_status",
    "get_expiry_warning",
]
