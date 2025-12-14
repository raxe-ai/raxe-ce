"""
CLI error handler decorator for consistent, user-friendly error handling.

Provides a decorator that wraps CLI commands to catch exceptions and display
helpful error messages with codes and remediation hints.

Example output:
    ERROR [CFG-001]
    Configuration file not found

    Details: ~/.raxe/config.yaml does not exist

    Suggested Fix:
      Run: raxe init

    Learn More: https://docs.raxe.ai/errors/CFG-001
"""

import functools
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

import click

from raxe.cli.exit_codes import (
    EXIT_AUTH_ERROR,
    EXIT_CONFIG_ERROR,
    EXIT_INVALID_INPUT,
    EXIT_SCAN_ERROR,
    EXIT_SUCCESS,
    EXIT_THREAT_DETECTED,
)
from raxe.cli.output import console
from raxe.infrastructure.telemetry.credential_store import CredentialExpiredError
from raxe.sdk.exceptions import (
    ConfigurationError,
    DatabaseError,
    ErrorCategory,
    ErrorCode,
    InfrastructureError,
    RaxeBlockedError,
    RaxeException,
    RuleError,
    SecurityException,
    ValidationError,
    credential_expired_error,
)
from raxe.utils.error_sanitizer import sanitize_error_message

F = TypeVar("F", bound=Callable[..., Any])


@dataclass(frozen=True)
class ErrorHelp:
    """Help text for a specific error type.

    Attributes:
        title: Short title for the error (displayed after error code)
        suggested_fix: Command or action to fix the issue
        learn_more_suffix: Suffix for the documentation URL
    """

    title: str
    suggested_fix: str
    learn_more_suffix: str


# Mapping of ErrorCode to help text with actionable steps
ERROR_HELP_MAP: dict[ErrorCode, ErrorHelp] = {
    # Configuration errors (CFG-001 to CFG-099)
    ErrorCode.CFG_NOT_FOUND: ErrorHelp(
        title="Configuration file not found",
        suggested_fix="Run: raxe init",
        learn_more_suffix="CFG-001",
    ),
    ErrorCode.CFG_INVALID_FORMAT: ErrorHelp(
        title="Invalid configuration format",
        suggested_fix="Run: raxe config validate",
        learn_more_suffix="CFG-002",
    ),
    ErrorCode.CFG_MISSING_REQUIRED: ErrorHelp(
        title="Missing required configuration",
        suggested_fix="Run: raxe config show  # to see current config",
        learn_more_suffix="CFG-003",
    ),
    ErrorCode.CFG_INVALID_VALUE: ErrorHelp(
        title="Invalid configuration value",
        suggested_fix="Check your ~/.raxe/config.yaml file",
        learn_more_suffix="CFG-004",
    ),
    ErrorCode.CFG_PERMISSION_DENIED: ErrorHelp(
        title="Permission denied accessing configuration",
        suggested_fix="Check file permissions on ~/.raxe/",
        learn_more_suffix="CFG-005",
    ),
    ErrorCode.CFG_INITIALIZATION_FAILED: ErrorHelp(
        title="Configuration initialization failed",
        suggested_fix="Run: raxe doctor  # to diagnose issues",
        learn_more_suffix="CFG-006",
    ),
    # Rule errors (RULE-100 to RULE-199)
    ErrorCode.RULE_NOT_FOUND: ErrorHelp(
        title="Detection rule not found",
        suggested_fix="Run: raxe rules list  # to see available rules",
        learn_more_suffix="RULE-100",
    ),
    ErrorCode.RULE_INVALID_SYNTAX: ErrorHelp(
        title="Invalid rule syntax",
        suggested_fix="Run: raxe validate-rule <path>  # to validate",
        learn_more_suffix="RULE-101",
    ),
    ErrorCode.RULE_INVALID_PATTERN: ErrorHelp(
        title="Invalid regex pattern in rule",
        suggested_fix="Test your regex at regex101.com",
        learn_more_suffix="RULE-102",
    ),
    ErrorCode.RULE_LOAD_FAILED: ErrorHelp(
        title="Failed to load detection rules",
        suggested_fix="Run: raxe doctor  # to check rule loading",
        learn_more_suffix="RULE-103",
    ),
    ErrorCode.RULE_PACK_NOT_FOUND: ErrorHelp(
        title="Rule pack not found",
        suggested_fix="Run: raxe pack list  # to see installed packs",
        learn_more_suffix="RULE-104",
    ),
    ErrorCode.RULE_PACK_INVALID: ErrorHelp(
        title="Invalid rule pack format",
        suggested_fix="Check pack structure and manifest.yaml",
        learn_more_suffix="RULE-105",
    ),
    ErrorCode.RULE_VERSION_MISMATCH: ErrorHelp(
        title="Rule version mismatch",
        suggested_fix="Update RAXE or rule pack to compatible version",
        learn_more_suffix="RULE-106",
    ),
    ErrorCode.RULE_DUPLICATE_ID: ErrorHelp(
        title="Duplicate rule ID detected",
        suggested_fix="Ensure all rule IDs are unique across packs",
        learn_more_suffix="RULE-107",
    ),
    # Security errors (SEC-200 to SEC-299)
    ErrorCode.SEC_THREAT_DETECTED: ErrorHelp(
        title="Security threat detected",
        suggested_fix="Run: raxe scan <text> --explain  # for details",
        learn_more_suffix="SEC-200",
    ),
    ErrorCode.SEC_BLOCKED_BY_POLICY: ErrorHelp(
        title="Request blocked by security policy",
        suggested_fix="Review policy or add suppression rule",
        learn_more_suffix="SEC-201",
    ),
    ErrorCode.SEC_CRITICAL_THREAT: ErrorHelp(
        title="Critical security threat detected",
        suggested_fix="Investigate immediately - potential attack",
        learn_more_suffix="SEC-202",
    ),
    ErrorCode.SEC_SIGNATURE_INVALID: ErrorHelp(
        title="Invalid rule pack signature",
        suggested_fix="Verify rule pack integrity and source",
        learn_more_suffix="SEC-203",
    ),
    ErrorCode.SEC_AUTH_FAILED: ErrorHelp(
        title="Authentication failed",
        suggested_fix="Get a permanent key at the console or run: raxe auth login",
        learn_more_suffix="SEC-204",
    ),
    ErrorCode.SEC_CREDENTIAL_EXPIRED: ErrorHelp(
        title="API key has expired",
        suggested_fix="Get a permanent key at the console or run: raxe auth login",
        learn_more_suffix="SEC-206",
    ),
    ErrorCode.SEC_PERMISSION_DENIED: ErrorHelp(
        title="Permission denied",
        suggested_fix="Contact administrator for access",
        learn_more_suffix="SEC-205",
    ),
    # Database errors (DB-300 to DB-399)
    ErrorCode.DB_CONNECTION_FAILED: ErrorHelp(
        title="Database connection failed",
        suggested_fix="Run: raxe doctor  # to diagnose database issues",
        learn_more_suffix="DB-300",
    ),
    ErrorCode.DB_QUERY_FAILED: ErrorHelp(
        title="Database query failed",
        suggested_fix="Run: raxe doctor  # to check database health",
        learn_more_suffix="DB-301",
    ),
    ErrorCode.DB_MIGRATION_FAILED: ErrorHelp(
        title="Database migration failed",
        suggested_fix="Backup data and run: raxe init --force",
        learn_more_suffix="DB-302",
    ),
    ErrorCode.DB_INTEGRITY_ERROR: ErrorHelp(
        title="Database integrity error",
        suggested_fix="Database may be corrupted - restore from backup",
        learn_more_suffix="DB-303",
    ),
    ErrorCode.DB_NOT_INITIALIZED: ErrorHelp(
        title="Database not initialized",
        suggested_fix="Run: raxe init",
        learn_more_suffix="DB-304",
    ),
    ErrorCode.DB_LOCK_TIMEOUT: ErrorHelp(
        title="Database lock timeout",
        suggested_fix="Close other RAXE instances and retry",
        learn_more_suffix="DB-305",
    ),
    # Validation errors (VAL-400 to VAL-499)
    ErrorCode.VAL_EMPTY_INPUT: ErrorHelp(
        title="Empty input provided",
        suggested_fix="Provide non-empty text to scan",
        learn_more_suffix="VAL-400",
    ),
    ErrorCode.VAL_INPUT_TOO_LONG: ErrorHelp(
        title="Input exceeds maximum length",
        suggested_fix="Split input into smaller chunks",
        learn_more_suffix="VAL-401",
    ),
    ErrorCode.VAL_INVALID_FORMAT: ErrorHelp(
        title="Invalid input format",
        suggested_fix="Check input format requirements",
        learn_more_suffix="VAL-402",
    ),
    ErrorCode.VAL_MISSING_FIELD: ErrorHelp(
        title="Required field missing",
        suggested_fix="Provide all required fields",
        learn_more_suffix="VAL-403",
    ),
    ErrorCode.VAL_TYPE_MISMATCH: ErrorHelp(
        title="Type mismatch",
        suggested_fix="Check data types match expected format",
        learn_more_suffix="VAL-404",
    ),
    ErrorCode.VAL_OUT_OF_RANGE: ErrorHelp(
        title="Value out of allowed range",
        suggested_fix="Use value within allowed range",
        learn_more_suffix="VAL-405",
    ),
    ErrorCode.VAL_INVALID_REGEX: ErrorHelp(
        title="Invalid regular expression",
        suggested_fix="Fix regex syntax - test at regex101.com",
        learn_more_suffix="VAL-406",
    ),
    ErrorCode.VAL_POLICY_INVALID: ErrorHelp(
        title="Invalid policy configuration",
        suggested_fix="Check policy file format and syntax",
        learn_more_suffix="VAL-407",
    ),
    # Infrastructure errors (INFRA-500 to INFRA-599)
    ErrorCode.INFRA_NETWORK_ERROR: ErrorHelp(
        title="Network error",
        suggested_fix="Check network connectivity",
        learn_more_suffix="INFRA-500",
    ),
    ErrorCode.INFRA_TIMEOUT: ErrorHelp(
        title="Operation timed out",
        suggested_fix="Retry or increase timeout setting",
        learn_more_suffix="INFRA-501",
    ),
    ErrorCode.INFRA_SERVICE_UNAVAILABLE: ErrorHelp(
        title="Service unavailable",
        suggested_fix="Service may be down - retry later",
        learn_more_suffix="INFRA-502",
    ),
    ErrorCode.INFRA_RATE_LIMITED: ErrorHelp(
        title="Rate limit exceeded",
        suggested_fix="Wait and retry with backoff.\n  Get a permanent key for higher limits via: raxe auth login",
        learn_more_suffix="INFRA-503",
    ),
    ErrorCode.INFRA_DISK_FULL: ErrorHelp(
        title="Disk space exhausted",
        suggested_fix="Free up disk space",
        learn_more_suffix="INFRA-504",
    ),
    ErrorCode.INFRA_MODEL_LOAD_FAILED: ErrorHelp(
        title="Failed to load ML model",
        suggested_fix="Run: pip install raxe[ml]  # to install ML dependencies",
        learn_more_suffix="INFRA-505",
    ),
    ErrorCode.INFRA_CIRCUIT_BREAKER_OPEN: ErrorHelp(
        title="Circuit breaker is open",
        suggested_fix="Service recovering - retry in a few minutes",
        learn_more_suffix="INFRA-506",
    ),
}


# Mapping of exception types to exit codes
EXCEPTION_EXIT_CODES: dict[type[Exception], int] = {
    ConfigurationError: EXIT_CONFIG_ERROR,
    ValidationError: EXIT_INVALID_INPUT,
    RuleError: EXIT_CONFIG_ERROR,
    DatabaseError: EXIT_SCAN_ERROR,
    InfrastructureError: EXIT_SCAN_ERROR,
    SecurityException: EXIT_THREAT_DETECTED,
    RaxeBlockedError: EXIT_THREAT_DETECTED,
}


# Mapping of error categories to exit codes (fallback)
CATEGORY_EXIT_CODES: dict[ErrorCategory, int] = {
    ErrorCategory.CFG: EXIT_CONFIG_ERROR,
    ErrorCategory.VAL: EXIT_INVALID_INPUT,
    ErrorCategory.RULE: EXIT_CONFIG_ERROR,
    ErrorCategory.DB: EXIT_SCAN_ERROR,
    ErrorCategory.INFRA: EXIT_SCAN_ERROR,
    ErrorCategory.SEC: EXIT_THREAT_DETECTED,
}


# Base URL for error documentation
DOCS_BASE_URL = "https://docs.raxe.ai/errors"


def _get_exit_code(exc: Exception) -> int:
    """Determine the appropriate exit code for an exception.

    Args:
        exc: The exception to get exit code for

    Returns:
        Appropriate exit code for the exception type
    """
    # First try exact type match
    for exc_type, exit_code in EXCEPTION_EXIT_CODES.items():
        if type(exc) is exc_type:
            return exit_code

    # Then try isinstance for inheritance
    for exc_type, exit_code in EXCEPTION_EXIT_CODES.items():
        if isinstance(exc, exc_type):
            return exit_code

    # If it's a RaxeException with an error code, use category
    if isinstance(exc, RaxeException) and exc.code is not None:
        category = exc.code.category
        if category in CATEGORY_EXIT_CODES:
            return CATEGORY_EXIT_CODES[category]

    # Default to scan error
    return EXIT_SCAN_ERROR


def _format_error_display(
    error_code: str | None,
    title: str,
    details: str | None,
    suggested_fix: str | None,
    learn_more_url: str | None,
) -> None:
    """Format and display error with rich formatting.

    Args:
        error_code: Error code string (e.g., "CFG-001")
        title: Error title/message
        details: Optional error details
        suggested_fix: Optional suggested fix command
        learn_more_url: Optional documentation URL
    """
    from rich.panel import Panel
    from rich.text import Text

    # Build error header
    error_text = Text()
    error_text.append("ERROR", style="red bold")
    if error_code:
        error_text.append(f" [{error_code}]", style="red")

    console.print(Panel(error_text, border_style="red", width=80, padding=(0, 1)))
    console.print()

    # Title/message
    console.print(f"[white]{title}[/white]")

    # Details (if provided)
    if details:
        console.print()
        console.print("[dim]Details:[/dim]")
        console.print(f"[dim]  {details}[/dim]")

    # Suggested fix (if provided)
    if suggested_fix:
        console.print()
        console.print("[yellow bold]Suggested Fix:[/yellow bold]")
        console.print(f"[cyan]  {suggested_fix}[/cyan]")

    # Learn more URL (if provided)
    if learn_more_url:
        console.print()
        console.print(f"[blue]Learn More:[/blue] [blue underline]{learn_more_url}[/blue underline]")

    console.print()


def _handle_raxe_exception(exc: RaxeException) -> int:
    """Handle a RaxeException with proper error display.

    Args:
        exc: The RaxeException to handle

    Returns:
        Exit code to use
    """
    # Get error code and details
    error_code = exc.code.value if exc.code else None
    error_help = ERROR_HELP_MAP.get(exc.code) if exc.code else None

    # Determine title
    if error_help:
        title = error_help.title
    elif exc.error:
        title = exc.error.message
    else:
        title = str(exc)

    # Sanitize any sensitive information from details
    details = None
    if exc.error and exc.error.details:
        # Format details as key=value pairs, sanitized
        detail_parts = []
        for key, value in exc.error.details.items():
            sanitized_value = sanitize_error_message(Exception(str(value)))
            detail_parts.append(f"{key}={sanitized_value}")
        details = ", ".join(detail_parts)

    # Determine suggested fix
    suggested_fix = None
    if error_help:
        suggested_fix = error_help.suggested_fix
    elif exc.remediation:
        suggested_fix = exc.remediation

    # Determine learn more URL
    learn_more_url = None
    if error_help:
        learn_more_url = f"{DOCS_BASE_URL}/{error_help.learn_more_suffix}"
    elif exc.doc_url:
        learn_more_url = exc.doc_url

    # Display formatted error
    _format_error_display(
        error_code=error_code,
        title=title,
        details=details,
        suggested_fix=suggested_fix,
        learn_more_url=learn_more_url,
    )

    return _get_exit_code(exc)


def _handle_click_exception(exc: click.ClickException) -> int:
    """Handle Click exceptions (UsageError, BadParameter, etc.).

    Args:
        exc: The Click exception to handle

    Returns:
        Exit code to use
    """
    # For Click exceptions, use the built-in formatting
    # but wrap in our error display style
    _format_error_display(
        error_code=None,
        title=exc.format_message(),
        details=None,
        suggested_fix="Run: raxe --help  # for usage information",
        learn_more_url=f"{DOCS_BASE_URL}/cli-usage",
    )
    return EXIT_INVALID_INPUT


def _handle_unexpected_exception(exc: Exception) -> int:
    """Handle unexpected exceptions with sanitized output.

    Args:
        exc: The unexpected exception to handle

    Returns:
        Exit code to use
    """
    # Sanitize the error message to remove sensitive info
    sanitized_message = sanitize_error_message(exc)

    _format_error_display(
        error_code=None,
        title="An unexpected error occurred",
        details=sanitized_message,
        suggested_fix="Run: raxe doctor  # to diagnose issues",
        learn_more_url=f"{DOCS_BASE_URL}/troubleshooting",
    )

    return EXIT_SCAN_ERROR


def _handle_credential_expired_exception(exc: CredentialExpiredError) -> int:
    """Handle CredentialExpiredError with prominent error display.

    Args:
        exc: The CredentialExpiredError to handle

    Returns:
        Exit code EXIT_AUTH_ERROR (5)
    """
    # Create a RaxeError from the CredentialExpiredError
    raxe_error = credential_expired_error(
        days_expired=exc.days_expired,
        console_url=exc.console_url,
    )

    # Build details string
    details = None
    if exc.days_expired > 0:
        details = f"Key expired {exc.days_expired} day(s) ago"

    _format_error_display(
        error_code=ErrorCode.SEC_CREDENTIAL_EXPIRED.value,
        title=raxe_error.message,
        details=details,
        suggested_fix=raxe_error.remediation,
        learn_more_url=f"{DOCS_BASE_URL}/SEC-206",
    )

    return EXIT_AUTH_ERROR


def handle_cli_error(func: F) -> F:
    """Decorator that provides consistent error handling for CLI commands.

    Catches exceptions and displays user-friendly error messages with:
    - Error code (if available)
    - Human-readable message
    - Details (sanitized to remove sensitive information)
    - Suggested fix with actionable command
    - Link to documentation

    Usage:
        @cli.command()
        @handle_cli_error
        def my_command():
            # Command implementation that may raise exceptions
            pass

    Args:
        func: The CLI command function to wrap

    Returns:
        Wrapped function with error handling
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except CredentialExpiredError as exc:
            # Handle expired credentials with prominent error
            exit_code = _handle_credential_expired_exception(exc)
            sys.exit(exit_code)
        except RaxeException as exc:
            exit_code = _handle_raxe_exception(exc)
            sys.exit(exit_code)
        except click.ClickException as exc:
            exit_code = _handle_click_exception(exc)
            sys.exit(exit_code)
        except KeyboardInterrupt:
            console.print()
            console.print("[yellow]Operation cancelled by user[/yellow]")
            console.print()
            sys.exit(EXIT_SUCCESS)
        except Exception as exc:
            exit_code = _handle_unexpected_exception(exc)
            sys.exit(exit_code)

    return wrapper  # type: ignore[return-value]


def handle_cli_error_quiet(func: F) -> F:
    """Decorator variant for quiet mode (JSON output, minimal display).

    Similar to handle_cli_error but outputs errors as JSON for CI/CD integration.

    Usage:
        @cli.command()
        @handle_cli_error_quiet
        def my_command():
            # Command implementation
            pass

    Args:
        func: The CLI command function to wrap

    Returns:
        Wrapped function with quiet error handling
    """
    import json

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except CredentialExpiredError as exc:
            # Output credential expired error as JSON
            error_output = {
                "error": True,
                "code": ErrorCode.SEC_CREDENTIAL_EXPIRED.value,
                "message": str(exc),
                "remediation": f"Get a permanent key at: {exc.console_url} or run: raxe auth login",
                "days_expired": exc.days_expired,
            }
            click.echo(json.dumps(error_output, indent=2))
            sys.exit(EXIT_AUTH_ERROR)
        except RaxeException as exc:
            # Output error as JSON
            error_output = {
                "error": True,
                "code": exc.code.value if exc.code else None,
                "message": str(exc),
                "remediation": exc.remediation,
            }
            click.echo(json.dumps(error_output, indent=2))
            sys.exit(_get_exit_code(exc))
        except click.ClickException as exc:
            error_output = {
                "error": True,
                "code": None,
                "message": exc.format_message(),
                "remediation": "Check command usage with --help",
            }
            click.echo(json.dumps(error_output, indent=2))
            sys.exit(EXIT_INVALID_INPUT)
        except KeyboardInterrupt:
            error_output = {
                "error": True,
                "code": None,
                "message": "Operation cancelled",
                "remediation": None,
            }
            click.echo(json.dumps(error_output, indent=2))
            sys.exit(EXIT_SUCCESS)
        except Exception as exc:
            sanitized_message = sanitize_error_message(exc)
            error_output = {
                "error": True,
                "code": None,
                "message": sanitized_message,
                "remediation": "Run raxe doctor to diagnose issues",
            }
            click.echo(json.dumps(error_output, indent=2))
            sys.exit(EXIT_SCAN_ERROR)

    return wrapper  # type: ignore[return-value]


__all__ = [
    "CATEGORY_EXIT_CODES",
    "DOCS_BASE_URL",
    "ERROR_HELP_MAP",
    "EXCEPTION_EXIT_CODES",
    "ErrorHelp",
    "handle_cli_error",
    "handle_cli_error_quiet",
]
