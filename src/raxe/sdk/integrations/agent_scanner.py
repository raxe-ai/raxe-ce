"""DEPRECATED: Import from raxe.sdk.agent_scanner instead.

This module is a compatibility shim that re-exports types from the canonical
location at raxe.sdk.agent_scanner. It will be removed in v0.5.0.

Migration:
    # Old (deprecated)
    from raxe.sdk.integrations.agent_scanner import AgentScanner, ScanMode

    # New (recommended)
    from raxe.sdk.agent_scanner import AgentScanner, ScanMode
"""
from __future__ import annotations

import warnings

# Emit deprecation warning on import
warnings.warn(
    "raxe.sdk.integrations.agent_scanner is deprecated. "
    "Import from raxe.sdk.agent_scanner instead. "
    "This module will be removed in v0.5.0.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export all types from canonical module
from raxe.sdk.agent_scanner import (
    AgentScanner,
    AgentScannerConfig,
    AgentScanResult,
    MessageType,
    ScanConfig,
    ScanContext,
    ScanMode,
    ScanType,
    ThreatAction,
    ThreatDetectedError,
    ToolBlockedError,
    ToolPolicy,
    ToolValidationConfig,
    ToolValidationMode,
    ToolValidationResponse,
    ToolValidationResult,
    create_agent_scanner,
)

# All public symbols
__all__ = [
    # Core classes
    "AgentScanner",
    "AgentScannerConfig",
    "AgentScanResult",
    "ScanConfig",
    "ScanContext",
    # Enums
    "MessageType",
    "ScanMode",
    "ScanType",
    "ThreatAction",
    "ToolValidationMode",
    "ToolValidationResult",
    # Tool-related
    "ToolPolicy",
    "ToolValidationConfig",
    "ToolValidationResponse",
    # Exceptions
    "ThreatDetectedError",
    "ToolBlockedError",
    # Factory
    "create_agent_scanner",
]
