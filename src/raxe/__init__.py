"""
RAXE CE - AI Safety Telemetry & Guardrails (Community Edition)

RAXE is a developer-first safety observability layer for LLM applications.
Think of it as the instrument panel for your AI - providing real-time visibility,
threat detection, and guardrails before AGI arrives.

Quick Start:
    >>> import raxe
    >>> raxe.init()  # Auto-configure
    >>> # Your LLM calls are now protected

Core Philosophy:
    - Privacy-first: Hash PII, never log prompts
    - Local-first: Scanning happens on your machine
    - Developer-friendly: <60 seconds to first detection
    - AGI safety: Visibility before governance

Architecture:
    This package follows Clean/Hexagonal architecture:
    - domain/: Pure business logic (NO I/O)
    - application/: Use cases and orchestration
    - infrastructure/: I/O implementations (DB, API, etc.)
    - cli/: Command-line interface
    - sdk/: Python SDK for integration
    - utils/: Shared utilities
"""

__version__ = "0.1.0"
__author__ = "RAXE Team"
__license__ = "MIT"

# Public API will be exported here once implemented
__all__ = [
    "__version__",
]
