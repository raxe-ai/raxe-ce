"""
Input validation utilities for security and data integrity.

Provides validation functions for common input types to prevent attacks
and ensure data quality.
"""

from datetime import datetime, timedelta, timezone


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


def validate_date_range(
    start_date: datetime,
    end_date: datetime,
    *,
    max_days: int = 730,  # 2 years default
    allow_future: bool = False,
) -> None:
    """
    Validate date range inputs to prevent attacks and data issues.

    Args:
        start_date: Start of date range
        end_date: End of date range
        max_days: Maximum allowed range in days (default: 730 = 2 years)
        allow_future: Whether to allow future dates (default: False)

    Raises:
        ValidationError: If date range is invalid

    Examples:
        >>> from datetime import datetime, timedelta, timezone
        >>> now = datetime.now(timezone.utc)
        >>> yesterday = now - timedelta(days=1)
        >>> validate_date_range(yesterday, now)  # OK
        >>> validate_date_range(now, yesterday)  # Raises ValidationError
    """
    # Type check
    if not isinstance(start_date, datetime):
        raise ValidationError(f"start_date must be datetime, got {type(start_date).__name__}")

    if not isinstance(end_date, datetime):
        raise ValidationError(f"end_date must be datetime, got {type(end_date).__name__}")

    # Logical order check
    if start_date > end_date:
        raise ValidationError(
            f"start_date ({start_date.isoformat()}) must be before "
            f"end_date ({end_date.isoformat()})"
        )

    # Range size check (DoS protection)
    range_delta = end_date - start_date
    max_range = timedelta(days=max_days)

    if range_delta > max_range:
        raise ValidationError(
            f"Date range too large: {range_delta.days} days "
            f"(maximum allowed: {max_days} days)"
        )

    # Future date check
    if not allow_future:
        now = datetime.now(timezone.utc)
        # Make naive if comparing with naive datetimes
        if start_date.tzinfo is None:
            now = now.replace(tzinfo=None)

        if start_date > now:
            raise ValidationError(
                f"start_date cannot be in the future: {start_date.isoformat()}"
            )
        # For end_date, allow same day (end_date might be 23:59:59.999999 of today)
        # Compare dates only, not full datetime
        end_date_date = end_date.date() if hasattr(end_date, 'date') else end_date
        now_date = now.date() if hasattr(now, 'date') else now
        if end_date_date > now_date:
            raise ValidationError(
                f"end_date cannot be in the future: {end_date.isoformat()}"
            )


def validate_positive_integer(value: int, name: str = "value") -> None:
    """
    Validate that a value is a positive integer.

    Args:
        value: Value to validate
        name: Name of the value (for error messages)

    Raises:
        ValidationError: If value is not a positive integer
    """
    if not isinstance(value, int):
        raise ValidationError(f"{name} must be an integer, got {type(value).__name__}")

    if value < 0:
        raise ValidationError(f"{name} must be positive, got {value}")


def validate_string_length(
    value: str,
    name: str = "value",
    *,
    min_length: int = 0,
    max_length: int | None = None,
) -> None:
    """
    Validate string length constraints.

    Args:
        value: String to validate
        name: Name of the value (for error messages)
        min_length: Minimum allowed length (default: 0)
        max_length: Maximum allowed length (default: None = no limit)

    Raises:
        ValidationError: If string length is invalid
    """
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string, got {type(value).__name__}")

    if len(value) < min_length:
        raise ValidationError(
            f"{name} must be at least {min_length} characters, got {len(value)}"
        )

    if max_length is not None and len(value) > max_length:
        raise ValidationError(
            f"{name} must be at most {max_length} characters, got {len(value)}"
        )


def validate_sql_identifier(identifier: str, name: str = "identifier") -> None:
    """
    Validate that a string is a safe SQL identifier.

    Only allows alphanumeric characters and underscores.

    Args:
        identifier: SQL identifier to validate
        name: Name of the identifier (for error messages)

    Raises:
        ValidationError: If identifier is invalid

    Examples:
        >>> validate_sql_identifier("table_name")  # OK
        >>> validate_sql_identifier("user; DROP TABLE users;")  # Raises ValidationError
    """
    if not isinstance(identifier, str):
        raise ValidationError(f"{name} must be a string, got {type(identifier).__name__}")

    if not identifier:
        raise ValidationError(f"{name} cannot be empty")

    # Only allow alphanumeric and underscores
    if not all(c.isalnum() or c == '_' for c in identifier):
        raise ValidationError(
            f"{name} can only contain alphanumeric characters and underscores, "
            f"got: {identifier}"
        )

    # Don't allow starting with a number
    if identifier[0].isdigit():
        raise ValidationError(f"{name} cannot start with a digit")
