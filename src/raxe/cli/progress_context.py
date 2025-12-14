"""Terminal context detection for progress indicators.

Detects the appropriate progress display mode based on:
- TTY availability
- Environment variables (NO_COLOR, TERM, etc.)
- CLI flags (--quiet, --no-color)
"""

import os
import sys


def detect_progress_mode(
    quiet: bool = False,
    verbose: bool = False,
    no_color: bool = False,
) -> str:
    """Detect appropriate progress mode based on terminal context.

    Args:
        quiet: --quiet flag set
        verbose: --verbose flag set
        no_color: --no-color flag set

    Returns:
        Progress mode: "interactive", "simple", or "quiet"

    Priority:
        1. Explicit --quiet flag → quiet
        2. Non-TTY environment → simple
        3. Dumb terminal → simple
        4. NO_COLOR environment → simple
        5. Default → interactive
    """

    # Priority 1: Explicit quiet flag
    if quiet or os.getenv("RAXE_QUIET"):
        return "quiet"

    # Priority 2: Check if stdout is a TTY
    if not sys.stdout.isatty():
        return "simple"  # CI/CD, pipe, redirect

    # Priority 3: Check for dumb terminal
    term = os.getenv("TERM", "")
    if term in ("dumb", ""):
        return "simple"

    # Priority 4: Check for NO_COLOR or --no-color
    if no_color or os.getenv("NO_COLOR") or os.getenv("RAXE_NO_COLOR"):
        return "simple"

    # Priority 5: Check for explicit simple mode
    if os.getenv("RAXE_SIMPLE_PROGRESS"):
        return "simple"

    # Default: Full interactive progress
    return "interactive"


def supports_unicode() -> bool:
    """Check if terminal supports Unicode icons.

    Returns:
        True if Unicode supported, False for ASCII fallback
    """
    # Check for ASCII-only mode
    if os.getenv("RAXE_ASCII_ONLY"):
        return False

    # Check encoding
    encoding = sys.stdout.encoding or ""
    if "utf" in encoding.lower():
        return True

    # Windows CMD often doesn't support Unicode
    if sys.platform == "win32" and os.getenv("TERM") != "xterm":
        return False

    return True


def supports_animation() -> bool:
    """Check if terminal supports animations.

    Returns:
        True if animations supported, False for static icons
    """
    # Check for explicit no-animation flag
    if os.getenv("RAXE_NO_ANIMATION"):
        return False

    # Check for accessibility mode
    if os.getenv("RAXE_ACCESSIBLE_MODE"):
        return False

    # Non-TTY doesn't support animation
    if not sys.stdout.isatty():
        return False

    return True
