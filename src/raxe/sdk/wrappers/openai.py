"""OpenAI client wrapper with automatic RAXE scanning.

Drop-in replacement for openai.OpenAI that scans all prompts and responses.

This wrapper allows users to replace:
    from openai import OpenAI
    client = OpenAI()

With:
    from raxe import RaxeOpenAI
    client = RaxeOpenAI()  # All calls automatically scanned

The wrapper intercepts chat.completions.create calls, scans user messages
before sending to OpenAI, and optionally scans responses.

Default behavior is LOG-ONLY (safe to add to production without breaking flows).
Enable blocking with `raxe_block_on_threat=True` for strict mode.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from raxe.sdk.agent_scanner import (
    AgentScannerConfig,
    create_agent_scanner,
)

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe

# Try to import OpenAI at module level
try:
    from openai import OpenAI
except ImportError:
    # Create a dummy class if OpenAI is not installed
    class OpenAI:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "openai package is required for RaxeOpenAI. Install with: pip install openai"
            )


logger = logging.getLogger(__name__)


class RaxeOpenAI(OpenAI):
    """Drop-in replacement for openai.OpenAI with automatic scanning.

    This wrapper inherits from OpenAI client and intercepts all
    chat.completions.create calls to scan prompts and responses.

    Usage:
        # Instead of:
        from openai import OpenAI
        client = OpenAI(api_key="sk-...")

        # Use:
        from raxe import RaxeOpenAI
        client = RaxeOpenAI(api_key="sk-...")

        # All chat.completions.create calls are automatically scanned
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )

    Attributes:
        raxe: Raxe client instance for scanning
        raxe_block_on_threat: Whether to block requests on threat detection
        raxe_scan_responses: Whether to scan OpenAI responses
    """

    def __init__(
        self,
        *args,
        raxe: Raxe | None = None,
        raxe_block_on_threat: bool = False,
        raxe_scan_responses: bool = True,
        **kwargs,
    ):
        """Initialize RaxeOpenAI client.

        Args:
            *args: Passed to OpenAI.__init__
            raxe: Optional Raxe client (creates default if not provided)
            raxe_block_on_threat: Block requests on threat detection.
                Default is False (log-only mode, safe for production).
            raxe_scan_responses: Also scan OpenAI responses
            **kwargs: Passed to OpenAI.__init__

        Example:
            # With default Raxe client (log-only mode)
            client = RaxeOpenAI(api_key="sk-...")

            # With custom Raxe client
            raxe = Raxe(telemetry=False)
            client = RaxeOpenAI(api_key="sk-...", raxe=raxe)

            # Enable blocking (strict mode)
            client = RaxeOpenAI(
                api_key="sk-...",
                raxe_block_on_threat=True
            )
        """
        # Initialize parent OpenAI client
        super().__init__(*args, **kwargs)

        # Create or use provided Raxe client
        if raxe is None:
            from raxe.sdk.client import Raxe

            raxe = Raxe()

        self.raxe = raxe
        self.raxe_block_on_threat = raxe_block_on_threat
        self.raxe_scan_responses = raxe_scan_responses

        # Create AgentScanner for unified scanning
        config = AgentScannerConfig(
            scan_prompts=True,
            scan_responses=raxe_scan_responses,
            on_threat="block" if raxe_block_on_threat else "log",
        )
        self._scanner = create_agent_scanner(raxe, config, integration_type="openai")

        # Wrap the chat completions resource
        self._wrap_chat_completions()

        logger.debug(
            f"RaxeOpenAI initialized: block={raxe_block_on_threat}, "
            f"scan_responses={raxe_scan_responses}"
        )

    def _wrap_chat_completions(self):
        """Wrap chat.completions.create method with scanning."""
        # Get original create method
        original_create = super().chat.completions.create

        def wrapped_create(*args, **kwargs):
            """Wrapped chat.completions.create with RAXE scanning."""
            # Extract messages
            messages = kwargs.get("messages", [])

            # Scan each user message
            for message in messages:
                if isinstance(message, dict):
                    # Handle dict-style messages
                    if message.get("role") == "user":
                        content = message.get("content", "")
                        if content:
                            self._scan_message(content)
                elif hasattr(message, "role") and hasattr(message, "content"):
                    # Handle object-style messages
                    if message.role == "user":
                        self._scan_message(message.content)

            # Call original OpenAI
            response = original_create(*args, **kwargs)

            # Optionally scan response
            if self.raxe_scan_responses and hasattr(response, "choices"):
                self._scan_response(response)

            return response

        # Replace the method
        self.chat.completions.create = wrapped_create

    def _scan_message(self, content: str):
        """Scan a user message for threats.

        Args:
            content: Message content to scan

        Raises:
            ThreatDetectedError: If threat detected and blocking enabled
        """
        # Use AgentScanner for unified scanning with integration telemetry
        result = self._scanner.scan_prompt(content)

        # AgentScanner handles blocking if configured
        # Log for monitoring
        if result.has_threats:
            logger.warning(
                f"Threat detected in user message: {result.severity} (action={result.action_taken})"
            )

    def _scan_response(self, response: Any):
        """Scan OpenAI response for threats.

        Args:
            response: OpenAI response object
        """
        try:
            for choice in response.choices:
                if hasattr(choice, "message") and hasattr(choice.message, "content"):
                    content = choice.message.content
                    if content:
                        # Scan response (AgentScanner handles blocking based on config)
                        result = self._scanner.scan_response(content)
                        if result.has_threats:
                            logger.info(f"Threat detected in OpenAI response: {result.severity}")
        except Exception as e:
            # Don't fail on response scanning
            logger.error(f"Failed to scan response: {e}")

    def __repr__(self) -> str:
        """String representation of RaxeOpenAI client.

        Returns:
            Human-readable string
        """
        return (
            f"RaxeOpenAI(block_on_threat={self.raxe_block_on_threat}, "
            f"scan_responses={self.raxe_scan_responses})"
        )
