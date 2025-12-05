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
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

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
        raxe_block_on_threat: bool = True,
        raxe_scan_responses: bool = True,
        **kwargs
    ):
        """Initialize RaxeAnthropic client.

        Args:
            *args: Passed to Anthropic.__init__
            raxe: Optional Raxe client (creates default if not provided)
            raxe_block_on_threat: Block requests on threat detection
            raxe_scan_responses: Also scan Claude responses
            **kwargs: Passed to Anthropic.__init__

        Example:
            # With default Raxe client
            client = RaxeAnthropic(api_key="sk-ant-...")

            # With custom Raxe client
            raxe = Raxe(telemetry=False)
            client = RaxeAnthropic(api_key="sk-ant-...", raxe=raxe)

            # Disable blocking (just monitor)
            client = RaxeAnthropic(
                api_key="sk-ant-...",
                raxe_block_on_threat=False
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
            RaxeBlockedError: If threat detected and blocking enabled
        """
        # Extract text from content (may be string or list of blocks)
        text = self._extract_text_from_content(content)

        if not text:
            return

        # Use Raxe.scan() - single entry point
        result = self.raxe.scan(
            text,
            block_on_threat=self.raxe_block_on_threat
        )

        # If we get here and blocking is enabled but not raised,
        # it means no threat was detected or scan() didn't raise
        # Just log for monitoring
        if result.has_threats:
            logger.warning(
                f"Threat detected in user message: {result.severity} "
                f"(block={self.raxe_block_on_threat})"
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
                            # Scan but don't block on responses
                            # (just monitor for policy violations)
                            result = self.raxe.scan(text, block_on_threat=False)
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
                result = self.raxe.scan(accumulated_text, block_on_threat=False)
                if result.has_threats:
                    logger.info(
                        f"Threat detected in Claude streaming response: {result.severity}"
                    )
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
