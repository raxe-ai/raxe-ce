"""LLM Framework Integrations.

Framework-specific integrations for RAXE scanning:
    - LangChain callback handler (RaxeCallbackHandler)
    - Hugging Face pipeline wrapper (RaxePipeline)

These integrations provide framework-native ways to add RAXE scanning
to existing applications without changing code structure.
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from raxe.sdk.integrations.huggingface import RaxePipeline
    from raxe.sdk.integrations.langchain import RaxeCallbackHandler

__all__ = ["RaxeCallbackHandler", "RaxePipeline"]


def __getattr__(name: str):
    """Lazy import integrations to avoid requiring all dependencies.

    Args:
        name: Name of the integration to import

    Returns:
        The requested integration class

    Raises:
        ImportError: If the integration's dependencies are not installed
        AttributeError: If the integration name is not recognized
    """
    if name == "RaxeCallbackHandler":
        try:
            from raxe.sdk.integrations.langchain import RaxeCallbackHandler
            return RaxeCallbackHandler
        except ImportError as e:
            raise ImportError(
                "LangChain integration requires langchain package. "
                "Install with: pip install langchain"
            ) from e

    elif name == "RaxePipeline":
        try:
            from raxe.sdk.integrations.huggingface import RaxePipeline
            return RaxePipeline
        except ImportError as e:
            raise ImportError(
                "Hugging Face integration requires transformers package. "
                "Install with: pip install transformers"
            ) from e

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
