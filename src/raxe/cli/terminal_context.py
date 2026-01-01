"""Terminal context detection for interactive features.

Provides utilities for detecting whether the CLI is running in an
interactive environment (terminal with user) or non-interactive
(CI/CD, scripts, pipes).

Used by:
- setup_wizard.py: Skip interactive prompts in CI
- repl.py: Refuse to start in non-interactive mode
- Any future commands requiring user input

Exit Codes:
    EXIT_CONFIG_ERROR (3) is used when setup cannot proceed due to
    non-interactive environment, guiding users to alternatives.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class TerminalMode(Enum):
    """Terminal execution mode."""

    INTERACTIVE = "interactive"  # Real terminal with user
    CI = "ci"  # CI/CD environment
    PIPE = "pipe"  # Piped input/output
    SCRIPT = "script"  # Non-TTY, non-CI (cron, systemd, etc.)


# Environment variables that indicate CI/CD environment
# Order matters for detection - check specific first, generic last
_CI_ENV_VARS: tuple[str, ...] = (
    # GitHub Actions
    "GITHUB_ACTIONS",
    "GITHUB_WORKFLOW",
    # GitLab CI
    "GITLAB_CI",
    # Jenkins
    "JENKINS_URL",
    "BUILD_ID",
    # CircleCI
    "CIRCLECI",
    # Travis CI
    "TRAVIS",
    # Azure Pipelines
    "TF_BUILD",
    "AZURE_PIPELINES",
    # Bitbucket Pipelines
    "BITBUCKET_BUILD_NUMBER",
    # AWS CodeBuild
    "CODEBUILD_BUILD_ID",
    # Google Cloud Build
    "CLOUD_BUILD",
    # Buildkite
    "BUILDKITE",
    # TeamCity
    "TEAMCITY_VERSION",
    # Drone CI
    "DRONE",
    # Semaphore
    "SEMAPHORE",
    # Vercel/Netlify/Render/Railway
    "VERCEL",
    "NETLIFY",
    "RENDER",
    "RAILWAY_ENVIRONMENT",
    # Generic CI indicators (checked last)
    "CI",
    "CONTINUOUS_INTEGRATION",
    # RAXE-specific override
    "RAXE_NON_INTERACTIVE",
)

# Mapping of env vars to human-readable CI service names
_CI_SERVICE_NAMES: dict[str, str] = {
    "GITHUB_ACTIONS": "GitHub Actions",
    "GITLAB_CI": "GitLab CI",
    "JENKINS_URL": "Jenkins",
    "CIRCLECI": "CircleCI",
    "TRAVIS": "Travis CI",
    "TF_BUILD": "Azure Pipelines",
    "BITBUCKET_BUILD_NUMBER": "Bitbucket Pipelines",
    "CODEBUILD_BUILD_ID": "AWS CodeBuild",
    "CLOUD_BUILD": "Google Cloud Build",
    "BUILDKITE": "Buildkite",
    "TEAMCITY_VERSION": "TeamCity",
    "DRONE": "Drone CI",
    "SEMAPHORE": "Semaphore",
    "VERCEL": "Vercel",
    "NETLIFY": "Netlify",
    "RENDER": "Render",
    "RAILWAY_ENVIRONMENT": "Railway",
}


@dataclass(frozen=True)
class TerminalContext:
    """Information about the terminal context.

    Attributes:
        mode: The detected terminal mode
        is_interactive: True if user can provide input
        detected_ci: Name of detected CI service (if any)
        has_tty: Whether stdin/stdout are TTYs
    """

    mode: TerminalMode
    is_interactive: bool
    detected_ci: str | None
    has_tty: bool

    @property
    def is_ci(self) -> bool:
        """Check if running in a CI/CD environment."""
        return self.mode == TerminalMode.CI

    @property
    def can_prompt(self) -> bool:
        """Check if we can prompt for user input."""
        return self.is_interactive and self.has_tty


def detect_ci_service() -> str | None:
    """Detect which CI service is running.

    Returns:
        CI service name if detected, None otherwise
    """
    # Check specific CI services first
    for env_var, name in _CI_SERVICE_NAMES.items():
        if os.environ.get(env_var):
            return name

    # Check generic CI detection
    if os.environ.get("CI") or os.environ.get("CONTINUOUS_INTEGRATION"):
        return "Unknown CI"

    return None


def _check_tty() -> bool:
    """Check if stdin and stdout are TTYs.

    Returns:
        True if both stdin and stdout are TTYs
    """
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        # Handle edge cases where stdin/stdout may be closed
        return False


def _is_dumb_terminal() -> bool:
    """Check for dumb or missing terminal.

    Returns:
        True if terminal is dumb or TERM is not set
    """
    term = os.environ.get("TERM", "")
    return term in ("", "dumb", "unknown")


def detect_terminal_context() -> TerminalContext:
    """Detect the current terminal context.

    Returns:
        TerminalContext with detection results

    Detection priority:
        1. RAXE_NON_INTERACTIVE env var (explicit override)
        2. CI environment variables
        3. TTY detection (stdin/stdout)
        4. TERM environment check
    """
    has_tty = _check_tty()
    detected_ci = detect_ci_service()

    # Priority 1: Explicit non-interactive override
    if os.environ.get("RAXE_NON_INTERACTIVE"):
        return TerminalContext(
            mode=TerminalMode.SCRIPT,
            is_interactive=False,
            detected_ci=detected_ci,
            has_tty=has_tty,
        )

    # Priority 2: CI environment
    if detected_ci or any(os.environ.get(v) for v in _CI_ENV_VARS):
        return TerminalContext(
            mode=TerminalMode.CI,
            is_interactive=False,
            detected_ci=detected_ci or "Unknown CI",
            has_tty=has_tty,
        )

    # Priority 3: TTY check
    if not has_tty:
        return TerminalContext(
            mode=TerminalMode.PIPE,
            is_interactive=False,
            detected_ci=None,
            has_tty=False,
        )

    # Priority 4: Dumb terminal check
    if _is_dumb_terminal():
        return TerminalContext(
            mode=TerminalMode.SCRIPT,
            is_interactive=False,
            detected_ci=None,
            has_tty=has_tty,
        )

    # Default: Interactive terminal
    return TerminalContext(
        mode=TerminalMode.INTERACTIVE,
        is_interactive=True,
        detected_ci=None,
        has_tty=True,
    )


def is_interactive() -> bool:
    """Quick check for interactive mode.

    Returns:
        True if running in an interactive terminal

    This is a convenience wrapper around detect_terminal_context()
    for simple boolean checks.
    """
    return get_terminal_context().is_interactive


# Module-level cache for performance
_cached_context: TerminalContext | None = None


def get_terminal_context() -> TerminalContext:
    """Get cached terminal context.

    The terminal context is detected once and cached for the
    lifetime of the process.

    Returns:
        Cached TerminalContext
    """
    global _cached_context
    if _cached_context is None:
        _cached_context = detect_terminal_context()
    return _cached_context


def clear_context_cache() -> None:
    """Clear the cached terminal context.

    Used primarily for testing to reset detection state.
    """
    global _cached_context
    _cached_context = None


__all__ = [
    "TerminalContext",
    "TerminalMode",
    "clear_context_cache",
    "detect_ci_service",
    "detect_terminal_context",
    "get_terminal_context",
    "is_interactive",
]
