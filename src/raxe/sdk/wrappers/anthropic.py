"""Anthropic client wrapper with automatic RAXE scanning.

Drop-in replacement for anthropic.Anthropic that scans all prompts and responses.

This wrapper allows users to replace:
    from anthropic import Anthropic
    client = Anthropic()

With:
    from raxe.sdk.wrappers import RaxeAnthropic
    client = RaxeAnthropic()  # All calls automatically scanned

The wrapper intercepts messages.create calls, scans user messages
before sending to Claude, and optionally scans responses.

Default behavior is LOG-ONLY (safe to add to production without breaking flows).
Enable blocking with `raxe_block_on_threat=True` for strict mode.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from raxe.sdk.agent_scanner import (
    AgentScannerConfig,
    create_agent_scanner,
)

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe

logger = logging.getLogger(__name__)


class RaxeAnthropic:
    """Drop-in replacement for anthropic.Anthropic with automatic scanning.

    This wrapper wraps the Anthropic client and intercepts all
    messages.create calls to scan prompts and responses.

    Usage:
        # Instead of:
        from anthropic import Anthropic
        client = Anthropic(api_key="sk-ant-...")

        # Use:
        from raxe.sdk.wrappers import RaxeAnthropic
        client = RaxeAnthropic(api_key="sk-ant-...")

        # All messages.create calls are automatically scanned
        response = client.messages.create(
            model="claude-3-opus-20240229",
            messages=[{"role": "user", "content": "Hello"}]
        )

    Attributes:
        raxe: Raxe client instance for scanning
        raxe_block_on_threat: Whether to block requests on threat detection
        raxe_scan_responses: Whether to scan Claude responses
    """

    def __init__(
        self,
        *args,
        raxe: Raxe | None = None,
        raxe_block_on_threat: bool = False,
        raxe_scan_responses: bool = True,
        **kwargs,
    ):
        """Initialize RaxeAnthropic client.

        Args:
            *args: Passed to Anthropic.__init__
            raxe: Optional Raxe client (creates default if not provided)
            raxe_block_on_threat: Block requests on threat detection.
                Default is False (log-only mode, safe for production).
            raxe_scan_responses: Also scan Claude responses
            **kwargs: Passed to Anthropic.__init__

        Example:
            # With default Raxe client (log-only mode)
            client = RaxeAnthropic(api_key="sk-ant-...")

            # With custom Raxe client
            raxe = Raxe(telemetry=False)
            client = RaxeAnthropic(api_key="sk-ant-...", raxe=raxe)

            # Enable blocking (strict mode)
            client = RaxeAnthropic(
                api_key="sk-ant-...",
                raxe_block_on_threat=True
            )

        Raises:
            ImportError: If anthropic package not installed
        """
        # Try to import Anthropic
        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise ImportError(
                "anthropic package is required for RaxeAnthropic. "
                "Install with: pip install anthropic"
            ) from e

        # Initialize parent Anthropic client
        self._anthropic_client = Anthropic(*args, **kwargs)

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
        self._scanner = create_agent_scanner(raxe, config, integration_type="anthropic")

        # Wrap the messages resource
        self._wrap_messages()

        logger.debug(
            f"RaxeAnthropic initialized: block={raxe_block_on_threat}, "
            f"scan_responses={raxe_scan_responses}"
        )

    def _wrap_messages(self):
        """Wrap messages.create method with scanning."""
        # Get original create method
        original_create = self._anthropic_client.messages.create

        def wrapped_create(*args, **kwargs):
            """Wrapped messages.create with RAXE scanning."""
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

            # Check if streaming is requested
            stream = kwargs.get("stream", False)

            # Call original Anthropic
            response = original_create(*args, **kwargs)

            # Handle streaming and non-streaming differently
            if stream:
                # For streaming, wrap the iterator
                return self._wrap_streaming_response(response)
            else:
                # For non-streaming, scan the complete response
                if self.raxe_scan_responses:
                    self._scan_response(response)
                return response

        # Replace the method
        self._anthropic_client.messages.create = wrapped_create

    def _scan_message(self, content: Any):
        """Scan a user message for threats.

        Args:
            content: Message content to scan (str or list of content blocks)

        Raises:
            ThreatDetectedError: If threat detected and blocking enabled
        """
        # Extract text from content (may be string or list of blocks)
        text = self._extract_text_from_content(content)

        if not text:
            return

        # Use AgentScanner for unified scanning with integration telemetry
        result = self._scanner.scan_prompt(text)

        # AgentScanner handles blocking if configured
        # Log for monitoring
        if result.has_threats:
            logger.warning(
                f"Threat detected in user message: {result.severity} (action={result.action_taken})"
            )

    def _scan_response(self, response: Any):
        """Scan Claude response for threats.

        Args:
            response: Anthropic response object
        """
        try:
            # Extract text from response content
            if hasattr(response, "content"):
                for content_block in response.content:
                    if hasattr(content_block, "text"):
                        text = content_block.text
                        if text:
                            # Scan response (AgentScanner handles blocking based on config)
                            result = self._scanner.scan_response(text)
                            if result.has_threats:
                                logger.info(
                                    f"Threat detected in Claude response: {result.severity}"
                                )
        except Exception as e:
            # Don't fail on response scanning
            logger.error(f"Failed to scan response: {e}")

    def _wrap_streaming_response(self, stream: Iterator) -> Iterator:
        """Wrap streaming response to scan chunks.

        Args:
            stream: Original streaming response iterator

        Yields:
            Response chunks with scanning
        """
        accumulated_text = ""

        for chunk in stream:
            # Accumulate text from chunks
            if hasattr(chunk, "delta") and hasattr(chunk.delta, "text"):
                accumulated_text += chunk.delta.text

            yield chunk

        # Scan accumulated text after stream completes
        if self.raxe_scan_responses and accumulated_text:
            try:
                result = self._scanner.scan_response(accumulated_text)
                if result.has_threats:
                    logger.info(f"Threat detected in Claude streaming response: {result.severity}")
            except Exception as e:
                logger.error(f"Failed to scan streaming response: {e}")

    def _extract_text_from_content(self, content: Any) -> str:
        """Extract text from Anthropic content format.

        Args:
            content: Content in various formats (str, list, etc.)

        Returns:
            Extracted text string
        """
        # Handle string content
        if isinstance(content, str):
            return content

        # Handle list of content blocks
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    texts.append(block["text"])
                elif hasattr(block, "text"):
                    texts.append(block.text)
            return " ".join(texts)

        # Handle single content block
        if isinstance(content, dict) and "text" in content:
            return content["text"]

        if hasattr(content, "text"):
            return content.text

        return ""

    def __getattr__(self, name):
        """Proxy all other attributes to the Anthropic client.

        This makes RaxeAnthropic a true drop-in replacement by forwarding
        all attributes and methods we don't explicitly override.

        Args:
            name: Attribute name

        Returns:
            Attribute from underlying Anthropic client
        """
        return getattr(self._anthropic_client, name)

    def __repr__(self) -> str:
        """String representation of RaxeAnthropic client.

        Returns:
            Human-readable string
        """
        return (
            f"RaxeAnthropic(block_on_threat={self.raxe_block_on_threat}, "
            f"scan_responses={self.raxe_scan_responses})"
        )
