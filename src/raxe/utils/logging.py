"""Privacy-aware structured logging infrastructure.

This module provides structured logging with:
- PII redaction (prompts, API keys, secrets)
- Log rotation (10MB files, keep 5)
- Multiple handlers (console + file)
- Context injection (version, environment, session_id)
- Colored console output

Usage:
    from raxe.utils.logging import get_logger

    logger = get_logger(__name__)
    logger.info(
        "scan_completed",
        prompt_hash=hash_prompt(prompt),  # NOT actual prompt
        detection_count=3,
        duration_ms=15.2
    )
"""
import logging
import os
import sys
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog
from structlog.types import EventDict, WrappedLogger

# Session ID for tracking related log entries
SESSION_ID = str(uuid.uuid4())[:8]

# PII-sensitive keys to redact
PII_KEYS = {
    "prompt",
    "response",
    "api_key",
    "password",
    "token",
    "secret",
    "authorization",
    "bearer",
}


def redact_pii_processor(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Redact PII from log entries.

    Automatically redacts values for sensitive keys to prevent PII leakage.

    Args:
        logger: The wrapped logger instance
        method_name: The name of the method called (info, error, etc.)
        event_dict: The event dictionary to process

    Returns:
        Event dictionary with PII redacted
    """
    for key in list(event_dict.keys()):
        if key.lower() in PII_KEYS:
            event_dict[key] = "***REDACTED***"
        elif isinstance(event_dict[key], str):
            # Check if value looks like an API key (alphanumeric, long string)
            value = event_dict[key]
            if len(value) > 20 and value.replace("-", "").replace("_", "").isalnum():
                # Might be a secret, show only first/last 4 chars
                if key.lower() not in {"event", "message", "status"}:
                    event_dict[key] = f"{value[:4]}...{value[-4:]}"

    return event_dict


def add_app_context_processor(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add application context to all log entries.

    Adds:
    - session_id: Unique session identifier
    - version: RAXE version
    - environment: Current environment (development, production, test)

    Args:
        logger: The wrapped logger instance
        method_name: The name of the method called
        event_dict: The event dictionary to process

    Returns:
        Event dictionary with context added
    """
    from raxe import __version__

    event_dict["session_id"] = SESSION_ID
    event_dict["version"] = __version__
    event_dict["environment"] = os.getenv("RAXE_ENV", "production")

    return event_dict


def setup_logging(
    log_level: str = "INFO",
    log_dir: Path | None = None,
    enable_file_logging: bool = True,
    enable_console_logging: bool = True,
) -> None:
    """Setup structured logging infrastructure.

    Configures:
    - Console handler with colored output
    - File handler with JSON logs and rotation
    - PII redaction processor
    - Context injection processor

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (default: ~/.raxe/logs)
        enable_file_logging: Enable file logging
        enable_console_logging: Enable console logging
    """
    # Determine log directory
    if log_dir is None:
        log_dir = Path.home() / ".raxe" / "logs"

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Convert log level string to int
    log_level_int = getattr(logging, log_level.upper(), logging.INFO)

    # Configure processors
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        add_app_context_processor,
        redact_pii_processor,
    ]

    # Configure structlog
    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level_int)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler (colored, human-readable)
    if enable_console_logging:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level_int)

        # Console formatter (colored)
        console_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(
                colors=sys.stdout.isatty(),
                exception_formatter=structlog.dev.RichTracebackFormatter(),
            ),
            foreign_pre_chain=shared_processors,
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # File handler (JSON, rotated)
    if enable_file_logging:
        log_file = log_dir / "raxe.log"

        # Rotating file handler (10MB, keep 5 rotations)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level_int)

        # File formatter (JSON)
        file_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured BoundLogger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("scan_completed", duration_ms=15.2, threats=3)
    """
    return structlog.get_logger(name)


def configure_from_env() -> None:
    """Configure logging from environment variables.

    Environment variables:
        RAXE_LOG_LEVEL: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        RAXE_LOG_DIR: Log directory path
        RAXE_ENABLE_FILE_LOGGING: Enable file logging (true/false)
        RAXE_ENABLE_CONSOLE_LOGGING: Enable console logging (false by default for CLI)
    """
    log_level = os.getenv("RAXE_LOG_LEVEL", "INFO")
    log_dir_str = os.getenv("RAXE_LOG_DIR")
    log_dir = Path(log_dir_str) if log_dir_str else None

    enable_file = os.getenv("RAXE_ENABLE_FILE_LOGGING", "true").lower() == "true"
    # CHANGED: Console logging OFF by default for clean CLI output
    # Users can enable with RAXE_ENABLE_CONSOLE_LOGGING=true or --verbose flag
    enable_console = os.getenv("RAXE_ENABLE_CONSOLE_LOGGING", "false").lower() == "true"

    setup_logging(
        log_level=log_level,
        log_dir=log_dir,
        enable_file_logging=enable_file,
        enable_console_logging=enable_console,
    )


# Auto-configure on import if not already configured
if not structlog.is_configured():
    configure_from_env()
