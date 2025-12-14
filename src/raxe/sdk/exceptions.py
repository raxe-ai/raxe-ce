"""RAXE SDK exceptions with structured error codes.

Custom exception hierarchy for RAXE SDK operations with structured error codes,
detailed messages, and actionable remediation hints.

All RAXE exceptions inherit from RaxeException for easy catching.

Error Code Format:
    {CATEGORY}-{NUMBER}

Categories:
    - CFG: Configuration errors (001-099)
    - RULE: Rule-related errors (100-199)
    - SEC: Security errors (200-299)
    - DB: Database errors (300-399)
    - VAL: Validation errors (400-499)
    - INFRA: Infrastructure errors (500-599)

Example:
    >>> try:
    ...     raxe.scan(prompt)
    ... except RaxeException as e:
    ...     print(f"Error {e.error.code}: {e.error.message}")
    ...     print(f"Fix: {e.error.remediation}")
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raxe.application.scan_pipeline import ScanPipelineResult


class ErrorCategory(str, Enum):
    """Categories for RAXE error codes."""

    CFG = "CFG"  # Configuration errors
    RULE = "RULE"  # Rule-related errors
    SEC = "SEC"  # Security errors
    DB = "DB"  # Database errors
    VAL = "VAL"  # Validation errors
    INFRA = "INFRA"  # Infrastructure errors


class ErrorCode(str, Enum):
    """Structured error codes for RAXE exceptions.

    Each error code follows the format: {CATEGORY}-{NUMBER}

    Error codes provide:
    - Consistent identification across logs and telemetry
    - Easy lookup in documentation
    - Programmatic error handling
    """

    # Configuration errors (CFG-001 to CFG-099)
    CFG_NOT_FOUND = "CFG-001"
    CFG_INVALID_FORMAT = "CFG-002"
    CFG_MISSING_REQUIRED = "CFG-003"
    CFG_INVALID_VALUE = "CFG-004"
    CFG_PERMISSION_DENIED = "CFG-005"
    CFG_INITIALIZATION_FAILED = "CFG-006"

    # Rule errors (RULE-100 to RULE-199)
    RULE_NOT_FOUND = "RULE-100"
    RULE_INVALID_SYNTAX = "RULE-101"
    RULE_INVALID_PATTERN = "RULE-102"
    RULE_LOAD_FAILED = "RULE-103"
    RULE_PACK_NOT_FOUND = "RULE-104"
    RULE_PACK_INVALID = "RULE-105"
    RULE_VERSION_MISMATCH = "RULE-106"
    RULE_DUPLICATE_ID = "RULE-107"

    # Security errors (SEC-200 to SEC-299)
    SEC_THREAT_DETECTED = "SEC-200"
    SEC_BLOCKED_BY_POLICY = "SEC-201"
    SEC_CRITICAL_THREAT = "SEC-202"
    SEC_SIGNATURE_INVALID = "SEC-203"
    SEC_AUTH_FAILED = "SEC-204"
    SEC_PERMISSION_DENIED = "SEC-205"
    SEC_CREDENTIAL_EXPIRED = "SEC-206"

    # Database errors (DB-300 to DB-399)
    DB_CONNECTION_FAILED = "DB-300"
    DB_QUERY_FAILED = "DB-301"
    DB_MIGRATION_FAILED = "DB-302"
    DB_INTEGRITY_ERROR = "DB-303"
    DB_NOT_INITIALIZED = "DB-304"
    DB_LOCK_TIMEOUT = "DB-305"

    # Validation errors (VAL-400 to VAL-499)
    VAL_EMPTY_INPUT = "VAL-400"
    VAL_INPUT_TOO_LONG = "VAL-401"
    VAL_INVALID_FORMAT = "VAL-402"
    VAL_MISSING_FIELD = "VAL-403"
    VAL_TYPE_MISMATCH = "VAL-404"
    VAL_OUT_OF_RANGE = "VAL-405"
    VAL_INVALID_REGEX = "VAL-406"
    VAL_POLICY_INVALID = "VAL-407"

    # Infrastructure errors (INFRA-500 to INFRA-599)
    INFRA_NETWORK_ERROR = "INFRA-500"
    INFRA_TIMEOUT = "INFRA-501"
    INFRA_SERVICE_UNAVAILABLE = "INFRA-502"
    INFRA_RATE_LIMITED = "INFRA-503"
    INFRA_DISK_FULL = "INFRA-504"
    INFRA_MODEL_LOAD_FAILED = "INFRA-505"
    INFRA_CIRCUIT_BREAKER_OPEN = "INFRA-506"

    @property
    def category(self) -> ErrorCategory:
        """Extract the category from the error code."""
        prefix = self.value.split("-")[0]
        return ErrorCategory(prefix)

    @property
    def number(self) -> int:
        """Extract the numeric part of the error code."""
        return int(self.value.split("-")[1])


# Base URL for error documentation
_DOCS_BASE_URL = "https://docs.raxe.ai/errors"


@dataclass(frozen=True)
class RaxeError:
    """Structured error information for RAXE exceptions.

    Provides comprehensive error details including:
    - Unique error code for identification
    - Human-readable message
    - Additional context details
    - Actionable remediation steps
    - Link to documentation

    Attributes:
        code: The ErrorCode enum value
        message: Human-readable error description
        details: Optional additional context as key-value pairs
        remediation: Suggested fix or next steps
        doc_url: Link to detailed documentation

    Example:
        >>> error = RaxeError(
        ...     code=ErrorCode.CFG_NOT_FOUND,
        ...     message="Configuration file not found",
        ...     details={"path": "/home/user/.raxe/config.yaml"},
        ...     remediation="Run 'raxe init' to create default configuration"
        ... )
        >>> print(error.doc_url)
        'https://docs.raxe.ai/errors/CFG-001'
    """

    code: ErrorCode
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    remediation: str = ""

    @property
    def doc_url(self) -> str:
        """Generate documentation URL for this error."""
        return f"{_DOCS_BASE_URL}/{self.code.value}"

    def __str__(self) -> str:
        """Format error as human-readable string."""
        parts = [f"[{self.code.value}] {self.message}"]
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            parts.append(f"Details: {detail_str}")
        if self.remediation:
            parts.append(f"Fix: {self.remediation}")
        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "code": self.code.value,
            "category": self.code.category.value,
            "message": self.message,
            "details": self.details,
            "remediation": self.remediation,
            "doc_url": self.doc_url,
        }


# ============================================================================
# Pre-defined error templates for common scenarios
# ============================================================================

def config_not_found_error(path: str) -> RaxeError:
    """Create error for missing configuration file."""
    return RaxeError(
        code=ErrorCode.CFG_NOT_FOUND,
        message=f"Configuration file not found: {path}",
        details={"path": path},
        remediation="Run 'raxe init' to create default configuration, "
        "or specify a valid config path with --config",
    )


def config_invalid_format_error(path: str, parse_error: str) -> RaxeError:
    """Create error for invalid configuration format."""
    return RaxeError(
        code=ErrorCode.CFG_INVALID_FORMAT,
        message=f"Invalid configuration format in {path}",
        details={"path": path, "parse_error": parse_error},
        remediation="Check YAML syntax and ensure the file is valid. "
        "Use 'raxe config validate' to check for errors.",
    )


def config_missing_required_error(field: str) -> RaxeError:
    """Create error for missing required configuration field."""
    return RaxeError(
        code=ErrorCode.CFG_MISSING_REQUIRED,
        message=f"Required configuration field missing: {field}",
        details={"field": field},
        remediation=f"Add the '{field}' field to your configuration file. "
        "See 'raxe config show' for current configuration.",
    )


def rule_not_found_error(rule_id: str) -> RaxeError:
    """Create error for missing rule."""
    return RaxeError(
        code=ErrorCode.RULE_NOT_FOUND,
        message=f"Rule not found: {rule_id}",
        details={"rule_id": rule_id},
        remediation="Check the rule ID spelling. Use 'raxe rules list' to see available rules.",
    )


def rule_invalid_pattern_error(rule_id: str, pattern: str, error: str) -> RaxeError:
    """Create error for invalid regex pattern in rule."""
    return RaxeError(
        code=ErrorCode.RULE_INVALID_PATTERN,
        message=f"Invalid regex pattern in rule {rule_id}",
        details={"rule_id": rule_id, "pattern_preview": pattern[:50] + "..." if len(pattern) > 50 else pattern, "error": error},
        remediation="Fix the regex pattern syntax. Test patterns at regex101.com before adding to rules.",
    )


def validation_empty_input_error(field: str = "prompt") -> RaxeError:
    """Create error for empty input."""
    return RaxeError(
        code=ErrorCode.VAL_EMPTY_INPUT,
        message=f"Empty {field} provided",
        details={"field": field},
        remediation=f"Provide a non-empty {field} for scanning.",
    )


def validation_input_too_long_error(
    field: str,
    length: int,
    max_length: int,
) -> RaxeError:
    """Create error for input exceeding maximum length."""
    return RaxeError(
        code=ErrorCode.VAL_INPUT_TOO_LONG,
        message=f"Input {field} exceeds maximum length",
        details={"field": field, "length": length, "max_length": max_length},
        remediation=f"Reduce {field} length to under {max_length} characters.",
    )


def database_connection_error(db_path: str, error: str) -> RaxeError:
    """Create error for database connection failure."""
    return RaxeError(
        code=ErrorCode.DB_CONNECTION_FAILED,
        message=f"Failed to connect to database: {db_path}",
        details={"db_path": db_path, "error": error},
        remediation="Check database path permissions and disk space. "
        "Run 'raxe doctor' to diagnose database issues.",
    )


def infrastructure_timeout_error(
    operation: str,
    timeout_seconds: float,
) -> RaxeError:
    """Create error for operation timeout."""
    return RaxeError(
        code=ErrorCode.INFRA_TIMEOUT,
        message=f"Operation timed out: {operation}",
        details={"operation": operation, "timeout_seconds": timeout_seconds},
        remediation="Try again or increase timeout. "
        "If persistent, check system resources with 'raxe doctor'.",
    )


def security_threat_detected_error(
    severity: str,
    detection_count: int,
) -> RaxeError:
    """Create error for detected security threat."""
    return RaxeError(
        code=ErrorCode.SEC_THREAT_DETECTED,
        message=f"Security threat detected: {severity} severity",
        details={"severity": severity, "detection_count": detection_count},
        remediation="Review the detected threat. If false positive, "
        "add a suppression rule or adjust policy thresholds.",
    )


def security_blocked_by_policy_error(
    policy_decision: str,
    severity: str,
) -> RaxeError:
    """Create error when request is blocked by policy."""
    return RaxeError(
        code=ErrorCode.SEC_BLOCKED_BY_POLICY,
        message=f"Request blocked by policy: {policy_decision}",
        details={"policy_decision": policy_decision, "severity": severity},
        remediation="Review policy configuration. Use 'raxe scan --explain' "
        "for detailed threat information.",
    )


def _get_default_console_keys_url() -> str:
    """Get default console keys URL from centralized endpoints."""
    from raxe.infrastructure.config.endpoints import get_console_url
    return f"{get_console_url()}/keys"


def credential_expired_error(
    days_expired: int,
    console_url: str | None = None,
) -> RaxeError:
    """Create error for expired API credentials.

    Args:
        days_expired: Number of days since the key expired.
        console_url: URL where users can get a new key (uses centralized endpoint if None).

    Returns:
        RaxeError with SEC-206 code and helpful remediation.
    """
    if console_url is None:
        console_url = _get_default_console_keys_url()

    if days_expired == 0:
        expiry_text = "today"
    elif days_expired == 1:
        expiry_text = "1 day ago"
    else:
        expiry_text = f"{days_expired} days ago"

    return RaxeError(
        code=ErrorCode.SEC_CREDENTIAL_EXPIRED,
        message=f"Your temporary API key expired {expiry_text}",
        details={"days_expired": days_expired, "console_url": console_url},
        remediation=f"Get a permanent key at: {console_url}\n"
        "Or run: raxe auth login",
    )


# ============================================================================
# Base Exception Classes
# ============================================================================

class RaxeException(Exception):
    """Base exception for all RAXE errors.

    Can be initialized with either a simple message (for backwards compatibility)
    or a structured RaxeError for rich error information.

    Attributes:
        error: Optional RaxeError with structured error details
        message: Human-readable error message

    Examples:
        # Legacy usage (backwards compatible)
        >>> raise RaxeException("Something went wrong")

        # Structured usage (preferred)
        >>> error = RaxeError(
        ...     code=ErrorCode.CFG_NOT_FOUND,
        ...     message="Config not found",
        ...     remediation="Run 'raxe init'"
        ... )
        >>> raise RaxeException(error)
    """

    def __init__(
        self,
        message_or_error: str | RaxeError,
        *,
        error: RaxeError | None = None,
    ) -> None:
        """Initialize RAXE exception.

        Args:
            message_or_error: Either a string message (legacy) or RaxeError (structured)
            error: Optional RaxeError (alternative to passing as first argument)
        """
        if isinstance(message_or_error, RaxeError):
            self.error = message_or_error
            self.message = str(message_or_error)
        elif error is not None:
            self.error = error
            self.message = message_or_error
        else:
            self.error = None
            self.message = message_or_error

        super().__init__(self.message)

    @property
    def code(self) -> ErrorCode | None:
        """Get error code if available."""
        return self.error.code if self.error else None

    @property
    def remediation(self) -> str | None:
        """Get remediation hint if available."""
        return self.error.remediation if self.error else None

    @property
    def doc_url(self) -> str | None:
        """Get documentation URL if available."""
        return self.error.doc_url if self.error else None

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        if self.error:
            return self.error.to_dict()
        return {
            "message": self.message,
            "code": None,
        }


# ============================================================================
# Configuration Exceptions
# ============================================================================

class ConfigurationError(RaxeException):
    """Raised when configuration is invalid or missing.

    This exception covers:
    - Missing configuration files
    - Invalid configuration format (YAML parse errors)
    - Missing required configuration fields
    - Invalid configuration values
    - Permission issues with config files

    Example:
        >>> raise ConfigurationError(config_not_found_error("/path/to/config"))
    """

    pass


# ============================================================================
# Validation Exceptions
# ============================================================================

class ValidationError(RaxeException):
    """Raised when input validation fails.

    This exception covers:
    - Empty input
    - Input exceeding length limits
    - Invalid format
    - Missing required fields
    - Type mismatches
    - Out of range values

    Example:
        >>> raise ValidationError(validation_empty_input_error("prompt"))
    """

    pass


# ============================================================================
# Rule Exceptions
# ============================================================================

class RuleError(RaxeException):
    """Raised when rule loading or processing fails.

    This exception covers:
    - Rule not found
    - Invalid rule syntax
    - Invalid regex patterns
    - Rule pack issues
    - Version mismatches

    Example:
        >>> raise RuleError(rule_not_found_error("pi-999"))
    """

    pass


# ============================================================================
# Database Exceptions
# ============================================================================

class DatabaseError(RaxeException):
    """Raised when database operations fail.

    This exception covers:
    - Connection failures
    - Query errors
    - Migration failures
    - Integrity constraint violations
    - Lock timeouts

    Example:
        >>> raise DatabaseError(database_connection_error("/path/to/db", "disk full"))
    """

    pass


# ============================================================================
# Infrastructure Exceptions
# ============================================================================

class InfrastructureError(RaxeException):
    """Raised when infrastructure operations fail.

    This exception covers:
    - Network errors
    - Timeouts
    - Service unavailability
    - Rate limiting
    - Disk space issues
    - Model loading failures
    - Circuit breaker activation

    Example:
        >>> raise InfrastructureError(infrastructure_timeout_error("cloud_sync", 30.0))
    """

    pass


# ============================================================================
# Security Exceptions (Backwards Compatible)
# ============================================================================

class SecurityException(RaxeException):
    """Raised when a security threat is detected and blocking is enabled.

    This exception is raised when:
    - A threat is detected during scanning
    - The policy dictates blocking (e.g., CRITICAL severity)
    - block_on_threat=True is specified

    Attributes:
        result: The ScanPipelineResult that triggered the exception
        error: Optional RaxeError with structured details

    Example:
        >>> # Standard usage with result
        >>> raise SecurityException(result)

        >>> # Usage with structured error
        >>> error = security_threat_detected_error("HIGH", 3)
        >>> raise SecurityException(result, error=error)
    """

    def __init__(
        self,
        result: "ScanPipelineResult",
        *,
        error: RaxeError | None = None,
    ) -> None:
        """Initialize security exception.

        Args:
            result: ScanPipelineResult containing threat details
            error: Optional structured error information
        """
        self.result = result

        # Create default structured error if not provided
        if error is None:
            error = security_threat_detected_error(
                severity=str(result.severity),
                detection_count=result.total_detections,
            )

        message = (
            f"Security threat detected: {result.severity} "
            f"({result.total_detections} detection(s))"
        )
        super().__init__(message, error=error)


class RaxeBlockedError(SecurityException):
    """Raised when a request is blocked by policy.

    This is a specialized SecurityException that indicates
    the request was explicitly blocked by policy evaluation.

    Attributes:
        result: The ScanPipelineResult with blocking decision
        error: RaxeError with SEC-201 code

    Example:
        >>> raise RaxeBlockedError(result)
    """

    def __init__(self, result: "ScanPipelineResult") -> None:
        """Initialize blocked error.

        Args:
            result: ScanPipelineResult with blocking decision
        """
        error = security_blocked_by_policy_error(
            policy_decision=str(result.policy_decision),
            severity=str(result.severity),
        )
        super().__init__(result, error=error)

        # Override message for backwards compatibility
        self.args = (
            f"Request blocked by policy: {result.policy_decision} "
            f"(Severity: {result.severity})",
        )


# ============================================================================
# Exception Mapping Utilities
# ============================================================================

def from_error_code(
    code: ErrorCode,
    message: str | None = None,
    details: dict[str, Any] | None = None,
    remediation: str | None = None,
) -> RaxeException:
    """Create appropriate exception from error code.

    Factory function that creates the correct exception type based on
    the error code category.

    Args:
        code: The ErrorCode to create exception for
        message: Optional custom message (uses default if not provided)
        details: Optional additional context
        remediation: Optional custom remediation (uses default if not provided)

    Returns:
        Appropriate RaxeException subclass based on error code category

    Example:
        >>> exc = from_error_code(
        ...     ErrorCode.CFG_NOT_FOUND,
        ...     message="Config missing",
        ...     details={"path": "/etc/raxe/config.yaml"}
        ... )
        >>> isinstance(exc, ConfigurationError)
        True
    """
    # Default messages for each error code
    default_messages: dict[ErrorCode, str] = {
        ErrorCode.CFG_NOT_FOUND: "Configuration file not found",
        ErrorCode.CFG_INVALID_FORMAT: "Invalid configuration format",
        ErrorCode.CFG_MISSING_REQUIRED: "Required configuration field missing",
        ErrorCode.CFG_INVALID_VALUE: "Invalid configuration value",
        ErrorCode.CFG_PERMISSION_DENIED: "Permission denied accessing configuration",
        ErrorCode.CFG_INITIALIZATION_FAILED: "Configuration initialization failed",
        ErrorCode.RULE_NOT_FOUND: "Detection rule not found",
        ErrorCode.RULE_INVALID_SYNTAX: "Invalid rule syntax",
        ErrorCode.RULE_INVALID_PATTERN: "Invalid regex pattern in rule",
        ErrorCode.RULE_LOAD_FAILED: "Failed to load detection rules",
        ErrorCode.RULE_PACK_NOT_FOUND: "Rule pack not found",
        ErrorCode.RULE_PACK_INVALID: "Invalid rule pack format",
        ErrorCode.RULE_VERSION_MISMATCH: "Rule version mismatch",
        ErrorCode.RULE_DUPLICATE_ID: "Duplicate rule ID detected",
        ErrorCode.SEC_THREAT_DETECTED: "Security threat detected",
        ErrorCode.SEC_BLOCKED_BY_POLICY: "Request blocked by security policy",
        ErrorCode.SEC_CRITICAL_THREAT: "Critical security threat detected",
        ErrorCode.SEC_SIGNATURE_INVALID: "Invalid signature",
        ErrorCode.SEC_AUTH_FAILED: "Authentication failed",
        ErrorCode.SEC_PERMISSION_DENIED: "Permission denied",
        ErrorCode.SEC_CREDENTIAL_EXPIRED: "API key has expired",
        ErrorCode.DB_CONNECTION_FAILED: "Database connection failed",
        ErrorCode.DB_QUERY_FAILED: "Database query failed",
        ErrorCode.DB_MIGRATION_FAILED: "Database migration failed",
        ErrorCode.DB_INTEGRITY_ERROR: "Database integrity error",
        ErrorCode.DB_NOT_INITIALIZED: "Database not initialized",
        ErrorCode.DB_LOCK_TIMEOUT: "Database lock timeout",
        ErrorCode.VAL_EMPTY_INPUT: "Empty input provided",
        ErrorCode.VAL_INPUT_TOO_LONG: "Input exceeds maximum length",
        ErrorCode.VAL_INVALID_FORMAT: "Invalid input format",
        ErrorCode.VAL_MISSING_FIELD: "Required field missing",
        ErrorCode.VAL_TYPE_MISMATCH: "Type mismatch",
        ErrorCode.VAL_OUT_OF_RANGE: "Value out of allowed range",
        ErrorCode.VAL_INVALID_REGEX: "Invalid regular expression",
        ErrorCode.VAL_POLICY_INVALID: "Invalid policy configuration",
        ErrorCode.INFRA_NETWORK_ERROR: "Network error",
        ErrorCode.INFRA_TIMEOUT: "Operation timed out",
        ErrorCode.INFRA_SERVICE_UNAVAILABLE: "Service unavailable",
        ErrorCode.INFRA_RATE_LIMITED: "Rate limit exceeded",
        ErrorCode.INFRA_DISK_FULL: "Disk space exhausted",
        ErrorCode.INFRA_MODEL_LOAD_FAILED: "Failed to load ML model",
        ErrorCode.INFRA_CIRCUIT_BREAKER_OPEN: "Circuit breaker is open",
    }

    # Default remediations for each error code
    default_remediations: dict[ErrorCode, str] = {
        ErrorCode.CFG_NOT_FOUND: "Run 'raxe init' to create default configuration",
        ErrorCode.CFG_INVALID_FORMAT: "Check YAML syntax with 'raxe config validate'",
        ErrorCode.CFG_MISSING_REQUIRED: "Add the missing field to configuration",
        ErrorCode.CFG_INVALID_VALUE: "Check documentation for valid values",
        ErrorCode.CFG_PERMISSION_DENIED: "Check file permissions on config directory",
        ErrorCode.CFG_INITIALIZATION_FAILED: "Run 'raxe doctor' to diagnose issues",
        ErrorCode.RULE_NOT_FOUND: "Use 'raxe rules list' to see available rules",
        ErrorCode.RULE_INVALID_SYNTAX: "Validate rule with 'raxe validate-rule'",
        ErrorCode.RULE_INVALID_PATTERN: "Test regex patterns at regex101.com",
        ErrorCode.RULE_LOAD_FAILED: "Check rule file permissions and format",
        ErrorCode.RULE_PACK_NOT_FOUND: "Install rule pack with 'raxe pack install'",
        ErrorCode.RULE_PACK_INVALID: "Validate pack structure and manifest",
        ErrorCode.RULE_VERSION_MISMATCH: "Update RAXE or rule pack to compatible version",
        ErrorCode.RULE_DUPLICATE_ID: "Ensure all rule IDs are unique",
        ErrorCode.SEC_THREAT_DETECTED: "Review detection with 'raxe scan --explain'",
        ErrorCode.SEC_BLOCKED_BY_POLICY: "Adjust policy or add suppression rule",
        ErrorCode.SEC_CRITICAL_THREAT: "Investigate immediately - potential attack",
        ErrorCode.SEC_SIGNATURE_INVALID: "Verify rule pack integrity",
        ErrorCode.SEC_AUTH_FAILED: "Get a permanent key at the console or run 'raxe auth login'",
        ErrorCode.SEC_PERMISSION_DENIED: "Contact administrator for access",
        ErrorCode.SEC_CREDENTIAL_EXPIRED: "Get a permanent key at the console or run 'raxe auth login'",
        ErrorCode.DB_CONNECTION_FAILED: "Check database path and permissions",
        ErrorCode.DB_QUERY_FAILED: "Run 'raxe doctor' to check database health",
        ErrorCode.DB_MIGRATION_FAILED: "Backup data and reinitialize database",
        ErrorCode.DB_INTEGRITY_ERROR: "Database may be corrupted - restore from backup",
        ErrorCode.DB_NOT_INITIALIZED: "Run 'raxe init' to initialize database",
        ErrorCode.DB_LOCK_TIMEOUT: "Close other RAXE instances and retry",
        ErrorCode.VAL_EMPTY_INPUT: "Provide non-empty input",
        ErrorCode.VAL_INPUT_TOO_LONG: "Reduce input length",
        ErrorCode.VAL_INVALID_FORMAT: "Check input format requirements",
        ErrorCode.VAL_MISSING_FIELD: "Provide all required fields",
        ErrorCode.VAL_TYPE_MISMATCH: "Check data types match expected format",
        ErrorCode.VAL_OUT_OF_RANGE: "Use value within allowed range",
        ErrorCode.VAL_INVALID_REGEX: "Fix regex syntax",
        ErrorCode.VAL_POLICY_INVALID: "Check policy configuration format",
        ErrorCode.INFRA_NETWORK_ERROR: "Check network connectivity",
        ErrorCode.INFRA_TIMEOUT: "Retry or increase timeout",
        ErrorCode.INFRA_SERVICE_UNAVAILABLE: "Service may be down - retry later",
        ErrorCode.INFRA_RATE_LIMITED: "Wait and retry with backoff. Get higher limits via 'raxe auth login'",
        ErrorCode.INFRA_DISK_FULL: "Free up disk space",
        ErrorCode.INFRA_MODEL_LOAD_FAILED: "Reinstall ML models with 'pip install raxe[ml]'",
        ErrorCode.INFRA_CIRCUIT_BREAKER_OPEN: "Service recovering - retry in a few minutes",
    }

    # Create the error
    error = RaxeError(
        code=code,
        message=message or default_messages.get(code, f"Error {code.value}"),
        details=details or {},
        remediation=remediation or default_remediations.get(code, ""),
    )

    # Map category to exception type
    exception_map: dict[ErrorCategory, type[RaxeException]] = {
        ErrorCategory.CFG: ConfigurationError,
        ErrorCategory.RULE: RuleError,
        ErrorCategory.SEC: RaxeException,  # Use base for SEC (SecurityException needs result)
        ErrorCategory.DB: DatabaseError,
        ErrorCategory.VAL: ValidationError,
        ErrorCategory.INFRA: InfrastructureError,
    }

    exception_class = exception_map.get(code.category, RaxeException)
    return exception_class(error)


# ============================================================================
# Re-exports for convenience
# ============================================================================

__all__ = [
    # Core classes
    "ErrorCategory",
    "ErrorCode",
    "RaxeError",
    # Base exception
    "RaxeException",
    # Domain exceptions
    "ConfigurationError",
    "ValidationError",
    "RuleError",
    "DatabaseError",
    "InfrastructureError",
    # Security exceptions (backwards compatible)
    "SecurityException",
    "RaxeBlockedError",
    # Error factories
    "config_not_found_error",
    "config_invalid_format_error",
    "config_missing_required_error",
    "rule_not_found_error",
    "rule_invalid_pattern_error",
    "validation_empty_input_error",
    "validation_input_too_long_error",
    "database_connection_error",
    "infrastructure_timeout_error",
    "security_threat_detected_error",
    "security_blocked_by_policy_error",
    "credential_expired_error",
    # Utilities
    "from_error_code",
]
