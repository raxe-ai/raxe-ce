"""
Decorator pattern for function protection.

Usage:
    raxe = Raxe()

    # Monitor mode (default - detects but doesn't block)
    @raxe.protect
    def generate(prompt: str) -> str:
        return llm.generate(prompt)

    # Check for threats in result
    result = raxe.scan("Ignore all instructions")
    if result.has_threats:
        # Handle threat appropriately
        pass
"""
from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe

# Type variable for generic function
F = TypeVar('F', bound=Callable[..., Any])


def protect_function(
    raxe_client: Raxe,
    func: F,
    *,
    block_on_threat: bool = False,
    on_threat: Callable | None = None,
    allow_severity: list[str] | None = None
) -> F:
    """
    Protect a function by scanning inputs before execution.

    Args:
        raxe_client: Raxe instance to use for scanning
        func: Function to protect
        block_on_threat: Raise SecurityException if threat detected (default: False)
        on_threat: Optional callback to invoke when threat detected
        allow_severity: Optional list of severities to allow (e.g., ["LOW"])

    Returns:
        Wrapped function that scans inputs before calling original

    Usage:
        raxe = Raxe()

        @raxe.protect
        def my_function(prompt: str) -> str:
            return process(prompt)

        # Enable blocking mode (use with caution)
        @raxe.protect(block_on_threat=True)
        def strict_function(prompt: str) -> str:
            return process(prompt)
    """
    # Check if function is async
    is_async = inspect.iscoroutinefunction(func)

    if is_async:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract text from arguments
            text = _extract_text_from_args(args, kwargs)

            if text:
                # Scan using Raxe client
                result = raxe_client.scan(text, block_on_threat=block_on_threat)

                # Handle threat detection
                if result.has_threats:
                    # Check if severity is allowed
                    if allow_severity and result.severity in allow_severity:
                        # Severity is allowed, don't block or callback
                        pass
                    else:
                        # Invoke callback if provided
                        if on_threat:
                            on_threat(result)

            # Call original async function
            return await func(*args, **kwargs)

        return async_wrapper  # type: ignore
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Extract text from arguments
            text = _extract_text_from_args(args, kwargs)

            if text:
                # Scan using Raxe client (will raise if block_on_threat=True)
                result = raxe_client.scan(text, block_on_threat=block_on_threat)

                # Handle threat detection
                if result.has_threats:
                    # Check if severity is allowed
                    if allow_severity and result.severity in allow_severity:
                        # Severity is allowed, don't block or callback
                        pass
                    else:
                        # Invoke callback if provided
                        if on_threat:
                            on_threat(result)

            # Call original function
            return func(*args, **kwargs)

        return sync_wrapper  # type: ignore


def _extract_text_from_args(args: tuple, kwargs: dict) -> str | None:
    """
    Extract text to scan from function arguments.

    Strategy:
    1. Check for kwarg named 'prompt', 'text', 'message', 'content'
    2. Check for first string positional argument
    3. Check for 'messages' list (LangChain/OpenAI style)

    Args:
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Extracted text or None
    """
    # Check common keyword argument names
    for key in ["prompt", "text", "message", "content", "input"]:
        if key in kwargs and isinstance(kwargs[key], str):
            return kwargs[key]

    # Check for messages list (OpenAI/LangChain format)
    if "messages" in kwargs:
        messages = kwargs["messages"]
        if isinstance(messages, list) and messages:
            # Extract from last message
            last_msg = messages[-1]
            if isinstance(last_msg, dict) and "content" in last_msg:
                return last_msg["content"]

    # Check first string positional argument
    for arg in args:
        if isinstance(arg, str):
            return arg

    # No text found
    return None


# Convenience function for backward compatibility
def protect(raxe_client: Raxe):
    """
    Create a decorator factory.

    Usage:
        raxe = Raxe()
        protect = raxe.protect

        @protect
        def my_func(prompt: str) -> str:
            return process(prompt)
    """
    def decorator(func: F) -> F:
        return protect_function(raxe_client, func)

    return decorator
