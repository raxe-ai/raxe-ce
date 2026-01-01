"""Error catalog with detailed help information for all RAXE error codes.

Provides comprehensive metadata for each error code including:
- Description and common causes
- Remediation steps and examples
- Related error codes
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ErrorInfo:
    """Complete information about a RAXE error code.

    Used by:
    - CLI help command
    - Error display formatting
    - Documentation generation
    """

    code: str
    category: str
    title: str
    description: str
    causes: tuple[str, ...] = ()
    remediation: str = ""
    additional_steps: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    see_also: tuple[str, ...] = ()
    doc_url: str = field(default="")

    def __post_init__(self) -> None:
        """Auto-generate doc_url if not provided."""
        if not self.doc_url:
            object.__setattr__(
                self,
                "doc_url",
                f"https://docs.raxe.ai/errors/{self.code}",
            )


# Master catalog of all error codes with full metadata
ERROR_CATALOG: dict[str, ErrorInfo] = {
    # Configuration errors (CFG-001 to CFG-006)
    "CFG-001": ErrorInfo(
        code="CFG-001",
        category="CFG",
        title="Configuration Not Found",
        description=(
            "RAXE cannot find its configuration file at the expected location. "
            "This typically occurs on first run or when the config was deleted."
        ),
        causes=(
            "First time running RAXE",
            "Config file was deleted or moved",
            "Using --config with invalid path",
            "Permission denied on config directory",
        ),
        remediation="raxe init",
        additional_steps=(
            "Check if ~/.raxe/config.yaml exists",
            "Verify file permissions with: ls -la ~/.raxe/",
            "Create config directory manually: mkdir -p ~/.raxe",
        ),
        examples=(
            "raxe init                    # Create default config",
            "raxe init --force            # Overwrite existing",
            "raxe config show             # View current config",
        ),
        see_also=("CFG-002", "CFG-006"),
    ),
    "CFG-002": ErrorInfo(
        code="CFG-002",
        category="CFG",
        title="Invalid Configuration Format",
        description="Configuration file exists but contains invalid YAML syntax or structure.",
        causes=(
            "Malformed YAML syntax",
            "Missing required fields",
            "Wrong indentation",
            "Invalid field types",
        ),
        remediation="raxe config validate",
        additional_steps=(
            "Check YAML syntax with: cat ~/.raxe/config.yaml",
            "Recreate config with: raxe init --force",
            "See valid config example in documentation",
        ),
        see_also=("CFG-001", "CFG-004"),
    ),
    "CFG-003": ErrorInfo(
        code="CFG-003",
        category="CFG",
        title="Missing Required Configuration",
        description="A required configuration field is missing from the config file.",
        causes=(
            "Incomplete configuration",
            "Manually edited config missing fields",
            "Outdated config from older version",
        ),
        remediation="raxe init --force",
        see_also=("CFG-002",),
    ),
    "CFG-004": ErrorInfo(
        code="CFG-004",
        category="CFG",
        title="Invalid Configuration Value",
        description="A configuration value is invalid or out of acceptable range.",
        causes=(
            "Invalid API key format",
            "Unsupported log level",
            "Invalid file path",
        ),
        remediation="raxe config show",
        additional_steps=("Check config values", "Update with: raxe config set KEY VALUE"),
        see_also=("CFG-002",),
    ),
    "CFG-005": ErrorInfo(
        code="CFG-005",
        category="CFG",
        title="Permission Denied",
        description="Cannot read or write configuration file due to permission issues.",
        causes=(
            "Insufficient file permissions",
            "Running as different user",
            "Directory not accessible",
        ),
        remediation="chmod 600 ~/.raxe/config.yaml",
        additional_steps=("Check ownership: ls -la ~/.raxe/", "Fix permissions on directory"),
        see_also=("CFG-001",),
    ),
    "CFG-006": ErrorInfo(
        code="CFG-006",
        category="CFG",
        title="Initialization Failed",
        description="Failed to initialize RAXE configuration or required components.",
        causes=(
            "Disk full",
            "Permission denied",
            "Required dependencies missing",
        ),
        remediation="raxe doctor",
        additional_steps=("Check disk space: df -h", "Verify permissions"),
        see_also=("CFG-001", "INFRA-504"),
    ),
    # Rule errors (RULE-100 to RULE-107)
    "RULE-100": ErrorInfo(
        code="RULE-100",
        category="RULE",
        title="Rule Not Found",
        description="The specified detection rule does not exist.",
        causes=(
            "Typo in rule ID",
            "Rule was removed",
            "Rule pack not loaded",
        ),
        remediation="raxe rules list",
        examples=(
            "raxe rules list           # Show all rules",
            "raxe rules show pi-001    # View specific rule",
        ),
        see_also=("RULE-104",),
    ),
    "RULE-101": ErrorInfo(
        code="RULE-101",
        category="RULE",
        title="Invalid Rule Syntax",
        description="Rule file contains invalid YAML syntax.",
        causes=("Malformed YAML", "Invalid indentation", "Missing required fields"),
        remediation="raxe validate-rule <file>",
        see_also=("RULE-102",),
    ),
    "RULE-102": ErrorInfo(
        code="RULE-102",
        category="RULE",
        title="Invalid Pattern",
        description="Detection pattern in rule is invalid or malformed.",
        causes=("Invalid regex syntax", "Unsupported pattern type", "Empty pattern"),
        remediation="raxe validate-rule <file>",
        see_also=("RULE-101",),
    ),
    "RULE-103": ErrorInfo(
        code="RULE-103",
        category="RULE",
        title="Rule Load Failed",
        description="Failed to load detection rule from file.",
        causes=("File not readable", "Invalid format", "Circular dependency"),
        remediation="raxe doctor",
        see_also=("RULE-100", "RULE-101"),
    ),
    "RULE-104": ErrorInfo(
        code="RULE-104",
        category="RULE",
        title="Rule Pack Not Found",
        description="The specified rule pack does not exist.",
        causes=("Pack not installed", "Typo in pack name", "Pack was removed"),
        remediation="raxe pack list",
        see_also=("RULE-100",),
    ),
    "RULE-105": ErrorInfo(
        code="RULE-105",
        category="RULE",
        title="Invalid Rule Pack",
        description="Rule pack structure or manifest is invalid.",
        causes=("Missing manifest", "Invalid pack structure", "Corrupted pack"),
        remediation="raxe pack info <pack>",
        see_also=("RULE-104",),
    ),
    "RULE-106": ErrorInfo(
        code="RULE-106",
        category="RULE",
        title="Version Mismatch",
        description="Rule pack version is incompatible with current RAXE version.",
        causes=("Outdated pack", "RAXE needs update", "Breaking changes"),
        remediation="raxe pack update <pack>",
        see_also=("RULE-104",),
    ),
    "RULE-107": ErrorInfo(
        code="RULE-107",
        category="RULE",
        title="Duplicate Rule ID",
        description="Multiple rules with the same ID found.",
        causes=("Custom rule conflicts with core", "Duplicate in pack", "Overlapping packs"),
        remediation="raxe rules list --all",
        see_also=("RULE-100",),
    ),
    # Security errors (SEC-200 to SEC-206)
    "SEC-200": ErrorInfo(
        code="SEC-200",
        category="SEC",
        title="Threat Detected",
        description="Security threat was detected in the scanned content.",
        causes=("Prompt injection attempt", "Jailbreak pattern", "Sensitive data exposure"),
        remediation="raxe scan --explain <text>",
        examples=("raxe scan --explain 'text'   # See detection details",),
        see_also=("SEC-201", "SEC-202"),
    ),
    "SEC-201": ErrorInfo(
        code="SEC-201",
        category="SEC",
        title="Blocked by Policy",
        description="Request was blocked due to security policy configuration.",
        causes=("Block mode enabled", "Policy threshold exceeded", "Critical threat"),
        remediation="raxe config show",
        additional_steps=("Review policy: raxe policy show", "Adjust thresholds if needed"),
        see_also=("SEC-200",),
    ),
    "SEC-202": ErrorInfo(
        code="SEC-202",
        category="SEC",
        title="Critical Threat",
        description="Critical security threat detected requiring immediate attention.",
        causes=("High-confidence attack", "Multiple threat indicators", "Known attack pattern"),
        remediation="Review the flagged content",
        see_also=("SEC-200", "SEC-201"),
    ),
    "SEC-203": ErrorInfo(
        code="SEC-203",
        category="SEC",
        title="Invalid Signature",
        description="Cryptographic signature validation failed.",
        causes=("Tampered content", "Wrong key", "Corrupted data"),
        remediation="Verify data integrity",
        see_also=(),
    ),
    "SEC-204": ErrorInfo(
        code="SEC-204",
        category="SEC",
        title="Authentication Failed",
        description="API key authentication failed.",
        causes=("Invalid API key", "Key revoked", "Wrong key format"),
        remediation="raxe auth",
        additional_steps=("Check key: raxe auth status", "Get new key: raxe auth"),
        see_also=("SEC-206",),
    ),
    "SEC-205": ErrorInfo(
        code="SEC-205",
        category="SEC",
        title="Permission Denied",
        description="Operation not allowed for current authentication level.",
        causes=("Insufficient tier", "Feature not available", "Rate limit exceeded"),
        remediation="raxe auth status",
        see_also=("SEC-204",),
    ),
    "SEC-206": ErrorInfo(
        code="SEC-206",
        category="SEC",
        title="Credential Expired",
        description="API key or session has expired.",
        causes=("Temporary key expired", "Session timeout", "Key revoked"),
        remediation="raxe auth",
        see_also=("SEC-204",),
    ),
    # Database errors (DB-300 to DB-305)
    "DB-300": ErrorInfo(
        code="DB-300",
        category="DB",
        title="Connection Failed",
        description="Failed to connect to the local database.",
        causes=("Database file corrupted", "File locked", "Permission denied"),
        remediation="raxe doctor",
        see_also=("DB-304",),
    ),
    "DB-301": ErrorInfo(
        code="DB-301",
        category="DB",
        title="Query Failed",
        description="Database query execution failed.",
        causes=("Invalid query", "Database corrupted", "Schema mismatch"),
        remediation="raxe doctor",
        see_also=("DB-302",),
    ),
    "DB-302": ErrorInfo(
        code="DB-302",
        category="DB",
        title="Migration Failed",
        description="Database migration could not be applied.",
        causes=("Schema conflict", "Data corruption", "Version mismatch"),
        remediation="raxe doctor",
        additional_steps=("Backup data", "Check RAXE version"),
        see_also=("DB-301",),
    ),
    "DB-303": ErrorInfo(
        code="DB-303",
        category="DB",
        title="Integrity Error",
        description="Database integrity constraint violation.",
        causes=("Duplicate entry", "Foreign key violation", "Data corruption"),
        remediation="raxe doctor",
        see_also=("DB-301",),
    ),
    "DB-304": ErrorInfo(
        code="DB-304",
        category="DB",
        title="Not Initialized",
        description="Database has not been initialized.",
        causes=("First run", "Database deleted", "Failed initialization"),
        remediation="raxe init",
        see_also=("DB-300", "CFG-006"),
    ),
    "DB-305": ErrorInfo(
        code="DB-305",
        category="DB",
        title="Lock Timeout",
        description="Could not acquire database lock within timeout.",
        causes=("Another process using database", "Deadlock", "Stale lock"),
        remediation="Wait and retry",
        additional_steps=("Check for other RAXE processes", "Restart if needed"),
        see_also=("DB-300",),
    ),
    # Validation errors (VAL-400 to VAL-407)
    "VAL-400": ErrorInfo(
        code="VAL-400",
        category="VAL",
        title="Empty Input",
        description="Input text is empty or contains only whitespace.",
        causes=("Empty string provided", "Whitespace only", "None value"),
        remediation="Provide non-empty text",
        examples=('raxe scan "your text here"',),
        see_also=("VAL-401",),
    ),
    "VAL-401": ErrorInfo(
        code="VAL-401",
        category="VAL",
        title="Input Too Long",
        description="Input text exceeds maximum allowed length.",
        causes=("Text too long", "No size limit configured", "Large file"),
        remediation="Split into smaller chunks",
        see_also=("VAL-400",),
    ),
    "VAL-402": ErrorInfo(
        code="VAL-402",
        category="VAL",
        title="Invalid Format",
        description="Input is not in the expected format.",
        causes=("Wrong encoding", "Binary data", "Invalid JSON"),
        remediation="Check input format",
        see_also=("VAL-404",),
    ),
    "VAL-403": ErrorInfo(
        code="VAL-403",
        category="VAL",
        title="Missing Field",
        description="Required field is missing from input.",
        causes=("Incomplete request", "Missing parameter", "Empty field"),
        remediation="Provide all required fields",
        see_also=("VAL-400",),
    ),
    "VAL-404": ErrorInfo(
        code="VAL-404",
        category="VAL",
        title="Type Mismatch",
        description="Field value has wrong type.",
        causes=("String expected, got number", "Wrong data type", "Invalid casting"),
        remediation="Check field types",
        see_also=("VAL-402",),
    ),
    "VAL-405": ErrorInfo(
        code="VAL-405",
        category="VAL",
        title="Out of Range",
        description="Numeric value is outside acceptable range.",
        causes=("Value too high", "Value too low", "Invalid threshold"),
        remediation="Check acceptable range in docs",
        see_also=("VAL-404",),
    ),
    "VAL-406": ErrorInfo(
        code="VAL-406",
        category="VAL",
        title="Invalid Regex",
        description="Regular expression pattern is invalid.",
        causes=("Syntax error in regex", "Unsupported features", "Unclosed brackets"),
        remediation="Validate regex pattern",
        see_also=("RULE-102",),
    ),
    "VAL-407": ErrorInfo(
        code="VAL-407",
        category="VAL",
        title="Invalid Policy",
        description="Policy configuration is invalid.",
        causes=("Invalid action", "Unknown policy field", "Conflicting rules"),
        remediation="raxe policy validate",
        see_also=("SEC-201",),
    ),
    # Infrastructure errors (INFRA-500 to INFRA-506)
    "INFRA-500": ErrorInfo(
        code="INFRA-500",
        category="INFRA",
        title="Network Error",
        description="Network connection failed.",
        causes=("No internet connection", "DNS failure", "Firewall blocking"),
        remediation="Check network connection",
        additional_steps=("Test connectivity: curl https://api.raxe.ai", "Check firewall rules"),
        see_also=("INFRA-502",),
    ),
    "INFRA-501": ErrorInfo(
        code="INFRA-501",
        category="INFRA",
        title="Timeout",
        description="Operation timed out.",
        causes=("Slow network", "Server overloaded", "Large request"),
        remediation="Retry the operation",
        see_also=("INFRA-500",),
    ),
    "INFRA-502": ErrorInfo(
        code="INFRA-502",
        category="INFRA",
        title="Service Unavailable",
        description="RAXE service is temporarily unavailable.",
        causes=("Server maintenance", "Outage", "Regional issues"),
        remediation="Check status.raxe.ai",
        additional_steps=("Wait and retry", "Check status page"),
        see_also=("INFRA-500",),
    ),
    "INFRA-503": ErrorInfo(
        code="INFRA-503",
        category="INFRA",
        title="Rate Limited",
        description="Too many requests, rate limit exceeded.",
        causes=("High request volume", "Tier limit reached", "Burst traffic"),
        remediation="Slow down requests",
        additional_steps=("Check your tier limits: raxe auth status", "Upgrade for higher limits"),
        see_also=("SEC-205",),
    ),
    "INFRA-504": ErrorInfo(
        code="INFRA-504",
        category="INFRA",
        title="Disk Full",
        description="Insufficient disk space for operation.",
        causes=("Disk full", "Quota exceeded", "Log files too large"),
        remediation="Free up disk space",
        additional_steps=("Check space: df -h", "Clean logs: rm ~/.raxe/logs/*"),
        see_also=("CFG-006",),
    ),
    "INFRA-505": ErrorInfo(
        code="INFRA-505",
        category="INFRA",
        title="Model Load Failed",
        description="Failed to load ML model for L2 detection.",
        causes=("Model file missing", "Corrupted model", "Insufficient memory"),
        remediation="raxe doctor",
        additional_steps=("Check models: raxe models list", "Reinstall: pip install raxe[ml]"),
        see_also=("INFRA-504",),
    ),
    "INFRA-506": ErrorInfo(
        code="INFRA-506",
        category="INFRA",
        title="Circuit Breaker Open",
        description="Service circuit breaker is open due to repeated failures.",
        causes=("Too many failures", "Service degraded", "Dependency down"),
        remediation="Wait for circuit to reset",
        additional_steps=("Check service status", "Retry after cooldown"),
        see_also=("INFRA-502",),
    ),
}


def get_error_info(code: str) -> ErrorInfo | None:
    """Look up error info by code string.

    Args:
        code: Error code like "CFG-001" or "cfg-001" (case-insensitive)

    Returns:
        ErrorInfo if found, None otherwise
    """
    return ERROR_CATALOG.get(code.upper())


def list_error_codes() -> list[str]:
    """Return all error codes sorted by category and number."""
    return sorted(
        ERROR_CATALOG.keys(),
        key=lambda c: (c.split("-")[0], int(c.split("-")[1])),
    )


def list_by_category(category: str) -> list[ErrorInfo]:
    """Return all errors in a category.

    Args:
        category: Category prefix like "CFG", "RULE", etc.

    Returns:
        List of ErrorInfo objects in that category
    """
    category_upper = category.upper()
    return [info for info in ERROR_CATALOG.values() if info.category == category_upper]
