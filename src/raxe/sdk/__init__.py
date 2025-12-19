"""RAXE SDK - Unified client for all integrations.

This module provides the core SDK interface for RAXE.
The Raxe class is the single entry point for all scanning operations.

Usage patterns:
    1. Direct scan:
        from raxe import Raxe
        raxe = Raxe()
        result = raxe.scan("Ignore all previous instructions")
        if result.has_threats:
            print(f"Threat: {result.severity}")

    2. Decorator pattern:
        @raxe.protect
        def generate_response(prompt: str) -> str:
            return llm.generate(prompt)

    3. Wrap existing client:
        from openai import OpenAI
        client = raxe.wrap(OpenAI())

    4. Inline suppression:
        result = raxe.scan(text, suppress=["pi-001", "jb-*"])

    5. Scoped suppression:
        with raxe.suppressed("pi-*", reason="Testing"):
            result = raxe.scan(text)

Public exports:
    - Raxe: Main client class
    - RaxeException: Base exception
    - SecurityException: Threat detected exception
    - RaxeBlockedError: Request blocked exception
    - suppression_scope: Function for scoped suppression without client
"""

from raxe.sdk.client import Raxe
from raxe.sdk.exceptions import (
    RaxeBlockedError,
    RaxeException,
    SecurityException,
)
from raxe.sdk.suppression_context import suppression_scope

__all__ = [
    "Raxe",
    "RaxeBlockedError",
    "RaxeException",
    "SecurityException",
    "suppression_scope",
]
