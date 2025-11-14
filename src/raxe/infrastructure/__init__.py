"""
Infrastructure Layer - I/O Implementations

This layer handles ALL external I/O operations:
    - Database access (SQLite)
    - Network calls (Cloud API)
    - File system operations (Config files)
    - External services

The infrastructure layer implements interfaces defined by the domain
and application layers, keeping those layers pure and testable.

Subdirectories:
    - database/: SQLite queue, migrations, models
    - cloud/: RAXE cloud API client, telemetry sender
    - config/: Configuration file I/O, environment variables

Key Patterns:
    - Repository pattern for data access
    - Adapter pattern for external services
    - Circuit breaker for resilience
    - Retry logic with exponential backoff
"""

__all__ = []
