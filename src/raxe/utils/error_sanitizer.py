"""
Error message sanitization for security.

Removes sensitive information from error messages before displaying
to users, preventing information disclosure vulnerabilities.
"""

import re
from pathlib import Path


def sanitize_error_message(error: Exception) -> str:
    """
    Remove sensitive information from error messages.

    Sanitizes:
    - File paths (replaced with <path>)
    - API keys (replaced with <api_key>)
    - Database connection strings (replaced with <db>)
    - Internal variable names/values (replaced with <internal>)

    Args:
        error: Exception to sanitize

    Returns:
        Sanitized error message string

    Examples:
        >>> err = Exception("/Users/alice/secret.txt not found")
        >>> sanitize_error_message(err)
        '<path> not found'

        >>> err = Exception("API key rxk_abc123 invalid")
        >>> sanitize_error_message(err)
        'API key <api_key> invalid'
    """
    message = str(error)

    # Remove Unix-style file paths
    message = re.sub(r'/Users/[^/\s]+/[^\s]*', '<path>', message)
    message = re.sub(r'/home/[^/\s]+/[^\s]*', '<path>', message)
    message = re.sub(r'/var/[^\s]*', '<path>', message)
    # nosec B108 - This is regex pattern matching, not temp file usage
    message = re.sub(r'/tmp/[^\s]*', '<path>', message)

    # Remove Windows-style file paths
    message = re.sub(r'C:\\Users\\[^\\]+\\[^\s]*', '<path>', message)
    message = re.sub(r'[A-Z]:\\[^\s]+', '<path>', message)

    # Remove API keys (rxk_ prefix)
    message = re.sub(r'rxk_[a-zA-Z0-9_]+', '<api_key>', message)

    # Remove database connection strings
    message = re.sub(r'sqlite:///[^\s]+', 'sqlite:///<db>', message)
    message = re.sub(r'postgresql://[^\s]+', 'postgresql://<connection>', message)
    message = re.sub(r'mysql://[^\s]+', 'mysql://<connection>', message)

    # Remove environment variable values
    message = re.sub(r'RAXE_[A-Z_]+=\S+', 'RAXE_<var>=<value>', message)

    # Remove internal variable assignments
    message = re.sub(r'_[a-z_]+\s*=\s*[^\s,;]+', '<internal>', message)

    # Remove UUIDs
    message = re.sub(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        '<id>',
        message
    )

    # Remove IP addresses
    message = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<ip>', message)

    # Remove Python file paths with line numbers
    message = re.sub(r'File "[^"]+\.py", line \d+', 'File "<file>", line <n>', message)

    return message


def sanitize_path(path: Path) -> str:
    """
    Sanitize a file path for display.

    Replaces user home directory with ~ for privacy.

    Args:
        path: Path to sanitize

    Returns:
        Sanitized path string

    Examples:
        >>> from pathlib import Path
        >>> sanitize_path(Path.home() / ".raxe" / "config.yaml")
        '~/.raxe/config.yaml'
    """
    try:
        # Try to make relative to home directory
        home = Path.home()
        if path.is_relative_to(home):
            relative = path.relative_to(home)
            return f"~/{relative}"
    except (ValueError, AttributeError):
        pass

    # If not under home, just show the filename
    return path.name


def safe_error_display(error: Exception, *, show_traceback: bool = False) -> str:
    """
    Create a safe error message for display to users.

    Args:
        error: Exception to display
        show_traceback: Whether to include traceback (default: False)

    Returns:
        Safe error message string
    """
    # Get sanitized message
    sanitized = sanitize_error_message(error)

    # Build display message
    error_type = type(error).__name__
    display_msg = f"{error_type}: {sanitized}"

    if show_traceback:
        import traceback
        tb = traceback.format_exc()
        # Sanitize traceback too
        sanitized_tb = sanitize_error_message(Exception(tb))
        display_msg += f"\n\n{sanitized_tb}"

    return display_msg
