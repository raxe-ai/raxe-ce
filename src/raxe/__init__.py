"""RAXE - AI Security for LLMs

Privacy-first threat detection for LLM applications.

RAXE provides developer-friendly, privacy-first AI security with:
- Local-first scanning (PII never leaves your machine)
- <10ms scan latency (P95)
- Community-driven threat detection
- Drop-in LLM client wrappers

Quick Start:
    >>> from raxe import Raxe
    >>> raxe = Raxe()
    >>> result = raxe.scan("Ignore all previous instructions")
    >>> if result.has_threats:
    ...     print(f"Threat: {result.severity}")

Decorator Pattern:
    >>> @raxe.protect
    ... def generate(prompt: str) -> str:
    ...     return llm.generate(prompt)

Wrapper Pattern:
    >>> from openai import OpenAI
    >>> client = raxe.wrap(OpenAI())
    >>> # All calls automatically scanned

Architecture:
    This package follows Clean Architecture:
    - domain/: Pure business logic (NO I/O)
    - application/: Use cases and orchestration
    - infrastructure/: I/O implementations (DB, API, packs)
    - sdk/: Python SDK (this is the entry point)
    - cli/: Command-line interface

For more information: https://docs.raxe.ai
"""

__version__ = "1.0.0"
__author__ = "RAXE Team"
__license__ = "MIT"

# Core client (PRIMARY EXPORT)
# Common types
from raxe.domain.engine.executor import Detection, ScanResult
from raxe.domain.rules.models import Severity
from raxe.sdk.client import Raxe

# Exceptions
from raxe.sdk.exceptions import (
    RaxeBlockedError,
    RaxeException,
    SecurityException,
)

__all__ = [
    "Detection",
    # Core
    "Raxe",
    "RaxeBlockedError",
    # Exceptions
    "RaxeException",
    # Types
    "ScanResult",
    "SecurityException",
    "Severity",
    # Metadata
    "__version__",
]

# CLI entry point
from raxe.cli.main import cli  # noqa: F401 - Used by setuptools entry point

# Wrappers (optional, requires openai)
try:
    from raxe.sdk.wrappers.openai import RaxeOpenAI  # noqa: F401 - Conditionally exported
    __all__.append("RaxeOpenAI")
except ImportError:
    # OpenAI not installed, skip wrapper
    pass

__all__.append("cli")
