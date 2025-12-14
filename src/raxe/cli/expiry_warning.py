"""Proactive API key expiry warning utility.

Provides proactive warnings for users with temporary API keys that are
approaching expiration. This module checks credential expiry and returns
appropriate warning messages for display in the CLI.

Warning Thresholds:
- Days 1-10: No warning (plenty of time remaining)
- Days 11-13: Yellow warning banner
- Day 14: Red warning "Expires TODAY"
- Day 15+: Already handled by CredentialExpiredError

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
WARNING_THRESHOLD_YELLOW = 4  # Show yellow warning when <= 4 days remaining
WARNING_THRESHOLD_RED = 1     # Show red warning when <= 1 day remaining

# Console URL for getting permanent keys - resolved from centralized endpoints
def _get_console_keys_url() -> str:
    """Get console keys URL from centralized endpoints."""
    from raxe.infrastructure.config.endpoints import get_console_url
    return f"{get_console_url()}/keys"


def get_expiry_warning() -> tuple[str | None, Literal["yellow", "red", ""]]:
    """Check API key expiry and return warning message if applicable.

    This function checks if the current API key is a temporary key and
    calculates the days until expiry. Based on the days remaining, it
    returns an appropriate warning message.

    Returns:
        A tuple of (warning_message, color) where:
        - warning_message: The warning text to display, or None if no warning needed
        - color: "yellow" for approaching expiry, "red" for expires today, "" if no warning

    Warning Thresholds:
        - Days > 4: No warning (plenty of time)
        - Days 2-4: Yellow warning banner
        - Day 1 (expires today): Red warning
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
        if days_remaining == 1:
            # Expires today - red warning
            message = "Your API key expires TODAY"
            return message, "red"

        if days_remaining <= WARNING_THRESHOLD_YELLOW:
            # Approaching expiry - yellow warning
            if days_remaining == 2:
                message = "Your API key expires tomorrow"
            else:
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
    color: Literal["yellow", "red"],
) -> None:
    """Display expiry warning banner in the CLI.

    Creates a visually distinct warning panel that draws user attention
    to their approaching key expiry.

    Args:
        console: Rich Console instance for output
        warning_message: The warning message to display
        color: Either "yellow" or "red" for warning severity

    Example output:
        +-------------------------------------------------------------+
        |  Your API key expires in 3 days                             |
        |                                                             |
        |  Get a permanent key: raxe auth login                       |
        |  Or visit: https://console.raxe.ai/keys                     |
        +-------------------------------------------------------------+
    """
    # Choose icon based on severity
    if color == "red":
        icon = "!!"
        border_style = "red bold"
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

    console.print(Panel(
        content,
        border_style=border_style,
        width=65,
        padding=(0, 2),
    ))
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
                "message": f"Temporary key expires TODAY",
            }

        if days_remaining <= 7:
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
            "message": f"Could not check key status",
        }


__all__ = [
    "get_expiry_warning",
    "display_expiry_warning",
    "check_and_display_expiry_warning",
    "get_expiry_status",
    "WARNING_THRESHOLD_YELLOW",
    "WARNING_THRESHOLD_RED",
    "_get_console_keys_url",
]
