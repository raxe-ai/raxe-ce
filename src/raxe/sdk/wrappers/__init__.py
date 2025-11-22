"""LLM Client Wrappers.

Drop-in replacements for popular LLM clients that add RAXE scanning.

This module provides wrappers for:
    - OpenAI client wrapper (RaxeOpenAI)
    - Anthropic client wrapper (RaxeAnthropic)
    - Google Vertex AI wrapper (RaxeVertexAI)
    - wrap_client() helper for runtime wrapping

Integrations are available via raxe.sdk.integrations:
    - LangChain callback handler (RaxeCallbackHandler)
    - Hugging Face pipeline wrapper (RaxePipeline)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe
    from raxe.sdk.wrappers.anthropic import RaxeAnthropic
    from raxe.sdk.wrappers.openai import RaxeOpenAI
    from raxe.sdk.wrappers.vertexai import RaxeVertexAI

__all__ = [
    "RaxeAnthropic",
    "RaxeOpenAI",
    "RaxeVertexAI",
    "wrap_client",
]

# Availability flags
_OPENAI_AVAILABLE = False
_ANTHROPIC_AVAILABLE = False
_VERTEXAI_AVAILABLE = False

# Lazy imports to avoid requiring all dependencies
RaxeOpenAI = None
RaxeAnthropic = None
RaxeVertexAI = None


def __getattr__(name: str):
    """Lazy import wrappers to avoid requiring all dependencies.

    Args:
        name: Name of the wrapper to import

    Returns:
        The requested wrapper class

    Raises:
        ImportError: If the wrapper's dependencies are not installed
        AttributeError: If the wrapper name is not recognized
    """
    global RaxeOpenAI, RaxeAnthropic, RaxeVertexAI
    global _OPENAI_AVAILABLE, _ANTHROPIC_AVAILABLE, _VERTEXAI_AVAILABLE

    if name == "RaxeOpenAI":
        if RaxeOpenAI is None:
            try:
                from raxe.sdk.wrappers.openai import RaxeOpenAI as _RaxeOpenAI
                RaxeOpenAI = _RaxeOpenAI
                _OPENAI_AVAILABLE = True
            except ImportError as e:
                raise ImportError(
                    "OpenAI wrapper requires openai package. "
                    "Install with: pip install openai"
                ) from e
        return RaxeOpenAI

    elif name == "RaxeAnthropic":
        if RaxeAnthropic is None:
            try:
                from raxe.sdk.wrappers.anthropic import RaxeAnthropic as _RaxeAnthropic
                RaxeAnthropic = _RaxeAnthropic
                _ANTHROPIC_AVAILABLE = True
            except ImportError as e:
                raise ImportError(
                    "Anthropic wrapper requires anthropic package. "
                    "Install with: pip install anthropic"
                ) from e
        return RaxeAnthropic

    elif name == "RaxeVertexAI":
        if RaxeVertexAI is None:
            try:
                from raxe.sdk.wrappers.vertexai import RaxeVertexAI as _RaxeVertexAI
                RaxeVertexAI = _RaxeVertexAI
                _VERTEXAI_AVAILABLE = True
            except ImportError as e:
                raise ImportError(
                    "Vertex AI wrapper requires google-cloud-aiplatform package. "
                    "Install with: pip install google-cloud-aiplatform"
                ) from e
        return RaxeVertexAI

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def wrap_client(raxe_client: Raxe, client: Any) -> Any:
    """Wrap an LLM client with RAXE scanning.

    This helper function wraps an existing LLM client instance
    with RAXE scanning capabilities. It detects the client type
    and returns the appropriate wrapper.

    Args:
        raxe_client: Raxe instance to use for scanning
        client: LLM client to wrap (OpenAI, Anthropic, etc.)

    Returns:
        Wrapped client with automatic scanning

    Raises:
        ImportError: If required wrapper package not installed
        NotImplementedError: If client type not supported

    Usage:
        >>> from raxe import Raxe
        >>> from openai import OpenAI
        >>> raxe = Raxe()
        >>> client = raxe.wrap(OpenAI(api_key="sk-..."))
        >>> # All calls automatically scanned

    Supported Clients:
        - openai.OpenAI -> RaxeOpenAI
        - anthropic.Anthropic -> RaxeAnthropic
        - More coming soon...
    """
    client_type = type(client).__name__

    if client_type == "OpenAI":
        # Wrap OpenAI client - import directly from submodule to avoid lazy loading issues
        from raxe.sdk.wrappers.openai import RaxeOpenAI

        # Create wrapped version with same config
        wrapped = RaxeOpenAI(raxe=raxe_client)

        # Copy API key from original if available
        if hasattr(client, "api_key"):
            wrapped._openai_client.api_key = client.api_key

        return wrapped

    elif client_type == "Anthropic":
        # Wrap Anthropic client - import directly from submodule to avoid lazy loading issues
        from raxe.sdk.wrappers.anthropic import RaxeAnthropic

        # Create wrapped version with same config
        wrapped = RaxeAnthropic(raxe=raxe_client)

        # Copy API key from original if available
        if hasattr(client, "api_key"):
            wrapped._anthropic_client.api_key = client.api_key

        return wrapped

    else:
        raise NotImplementedError(
            f"Wrapper for {client_type} not implemented yet. "
            f"Supported: OpenAI, Anthropic"
        )
