"""Async OpenAI client wrapper with automatic RAXE scanning.

Drop-in async replacement for openai.AsyncOpenAI that scans all prompts and responses.

This wrapper allows users to replace:
    from openai import AsyncOpenAI
    client = AsyncOpenAI()

With:
    from raxe.async_sdk import AsyncRaxeOpenAI
    client = AsyncRaxeOpenAI()  # All calls automatically scanned

The wrapper intercepts chat.completions.create calls, scans user messages
before sending to OpenAI, and optionally scans responses.
"""
import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from raxe.async_sdk.client import AsyncRaxe

logger = logging.getLogger(__name__)


class AsyncRaxeOpenAI:
    """Drop-in async replacement for openai.AsyncOpenAI with automatic scanning.

    This wrapper wraps the AsyncOpenAI client and intercepts all
    chat.completions.create calls to scan prompts and responses.

    Usage:
        # Instead of:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key="sk-...")

        # Use:
        from raxe.async_sdk import AsyncRaxeOpenAI
        async with AsyncRaxeOpenAI(api_key="sk-...") as client:
            response = await client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hello"}]
            )

    Attributes:
        raxe: AsyncRaxe client instance for scanning
        raxe_block_on_threat: Whether to block requests on threat detection
        raxe_scan_responses: Whether to scan OpenAI responses
    """

    def __init__(
        self,
        *args: Any,
        raxe: Optional["AsyncRaxe"] = None,
        raxe_block_on_threat: bool = True,
        raxe_scan_responses: bool = True,
        raxe_cache_size: int = 1000,
        **kwargs: Any
    ):
        """Initialize AsyncRaxeOpenAI client.

        Args:
            *args: Passed to AsyncOpenAI.__init__
            raxe: Optional AsyncRaxe client (creates default if not provided)
            raxe_block_on_threat: Block requests on threat detection
            raxe_scan_responses: Also scan OpenAI responses
            raxe_cache_size: Cache size for AsyncRaxe (default: 1000)
            **kwargs: Passed to AsyncOpenAI.__init__

        Example:
            # With default AsyncRaxe client
            async with AsyncRaxeOpenAI(api_key="sk-...") as client:
                response = await client.chat.completions.create(...)

            # With custom AsyncRaxe client
            from raxe.async_sdk import AsyncRaxe
            raxe = AsyncRaxe(telemetry=False)
            client = AsyncRaxeOpenAI(api_key="sk-...", raxe=raxe)

            # Disable blocking (just monitor)
            client = AsyncRaxeOpenAI(
                api_key="sk-...",
                raxe_block_on_threat=False
            )
        """
        # Try to import AsyncOpenAI
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai package is required for AsyncRaxeOpenAI. "
                "Install with: pip install openai"
            ) from None

        # Initialize AsyncOpenAI client
        self._openai_client = AsyncOpenAI(*args, **kwargs)

        # Create or use provided AsyncRaxe client
        if raxe is None:
            from raxe.async_sdk.client import AsyncRaxe
            raxe = AsyncRaxe(cache_size=raxe_cache_size)

        self.raxe = raxe
        self.raxe_block_on_threat = raxe_block_on_threat
        self.raxe_scan_responses = raxe_scan_responses

        # Wrap the chat completions resource
        self._wrap_chat_completions()

        logger.debug(
            f"AsyncRaxeOpenAI initialized: block={raxe_block_on_threat}, "
            f"scan_responses={raxe_scan_responses}"
        )

    def _wrap_chat_completions(self) -> None:
        """Wrap chat.completions.create method with scanning."""
        # Get original create method
        original_create = self._openai_client.chat.completions.create

        async def wrapped_create(*args: Any, **kwargs: Any) -> Any:
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
                            await self._scan_message(content)
                elif hasattr(message, "role") and hasattr(message, "content"):
                    # Handle object-style messages
                    if message.role == "user":
                        await self._scan_message(message.content)

            # Call original AsyncOpenAI
            response = await original_create(*args, **kwargs)

            # Optionally scan response
            if self.raxe_scan_responses and hasattr(response, "choices"):
                await self._scan_response(response)

            return response

        # Replace the method
        self._openai_client.chat.completions.create = wrapped_create  # type: ignore

    async def _scan_message(self, content: str) -> None:
        """Scan a user message for threats.

        Args:
            content: Message content to scan

        Raises:
            RaxeBlockedError: If threat detected and blocking enabled
        """
        # Use AsyncRaxe.scan() - single entry point
        result = await self.raxe.scan(
            content,
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

    async def _scan_response(self, response: Any) -> None:
        """Scan OpenAI response for threats.

        Args:
            response: OpenAI response object
        """
        try:
            for choice in response.choices:
                if hasattr(choice, "message") and hasattr(choice.message, "content"):
                    content = choice.message.content
                    if content:
                        # Scan but don't block on responses
                        # (just monitor for policy violations)
                        result = await self.raxe.scan(content, block_on_threat=False)
                        if result.has_threats:
                            logger.info(
                                f"Threat detected in OpenAI response: {result.severity}"
                            )
        except Exception as e:
            # Don't fail on response scanning
            logger.error(f"Failed to scan response: {e}")

    def __getattr__(self, name: str) -> Any:
        """Proxy all other attributes to the AsyncOpenAI client.

        This makes AsyncRaxeOpenAI a true drop-in replacement by forwarding
        all attributes and methods we don't explicitly override.

        Args:
            name: Attribute name

        Returns:
            Attribute from underlying AsyncOpenAI client
        """
        return getattr(self._openai_client, name)

    async def __aenter__(self) -> "AsyncRaxeOpenAI":
        """Enter async context manager.

        Returns:
            Self for use in async with statement
        """
        await self._openai_client.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager and cleanup.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
        """
        await self._openai_client.__aexit__(exc_type, exc_val, exc_tb)
        await self.raxe.close()

    def __repr__(self) -> str:
        """String representation of AsyncRaxeOpenAI client.

        Returns:
            Human-readable string
        """
        return (
            f"AsyncRaxeOpenAI(block_on_threat={self.raxe_block_on_threat}, "
            f"scan_responses={self.raxe_scan_responses})"
        )
