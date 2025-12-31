"""LLM Framework Integrations.

Framework-specific integrations for RAXE scanning:
    - LangChain callback handler (RaxeCallbackHandler)
    - Hugging Face pipeline wrapper (RaxePipeline)
    - LlamaIndex callback handler (RaxeLlamaIndexCallback)
    - LlamaIndex query engine callback (RaxeQueryEngineCallback)
    - LlamaIndex agent callback (RaxeAgentCallback)
    - LlamaIndex span handler (RaxeSpanHandler)
    - AutoGen conversation guard (RaxeConversationGuard)
    - CrewAI crew guard (RaxeCrewGuard)
    - LiteLLM callback handler (RaxeLiteLLMCallback)
    - DSPy callback handler (RaxeDSPyCallback)
    - DSPy module guard (RaxeModuleGuard)
    - Base AgentScanner for multi-agent frameworks

These integrations provide framework-native ways to add RAXE scanning
to existing applications without changing code structure.

AutoGen Integration:
    from raxe import Raxe
    from raxe.sdk.integrations import RaxeConversationGuard

    raxe = Raxe()
    guard = RaxeConversationGuard(raxe)

    # Register with agents
    guard.register(assistant)
    guard.register(user_proxy)

CrewAI Integration:
    from crewai import Crew, Agent, Task
    from raxe import Raxe
    from raxe.sdk.integrations import RaxeCrewGuard

    guard = RaxeCrewGuard(Raxe())

    # Use callbacks with Crew
    crew = Crew(
        agents=[researcher, writer],
        tasks=[research_task, write_task],
        step_callback=guard.step_callback,
        task_callback=guard.task_callback,
    )
    result = crew.kickoff()

    # Or wrap entire crew
    protected_crew = guard.protect_crew(crew)
    result = protected_crew.kickoff()
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from raxe.sdk.integrations.agent_scanner import (
        AgentScanner,
        AgentScannerConfig,
        AgentScanResult,
        MessageType,
        ScanContext,
        ScanMode,
    )
    from raxe.sdk.integrations.autogen import RaxeConversationGuard
    from raxe.sdk.integrations.crewai import (
        CrewGuardConfig,
        CrewScanStats,
        RaxeCrewGuard,
        create_crew_guard,
    )
    from raxe.sdk.integrations.huggingface import RaxePipeline
    from raxe.sdk.integrations.langchain import RaxeCallbackHandler
    from raxe.sdk.integrations.llamaindex import (
        RaxeAgentCallback,
        RaxeLlamaIndexCallback,
        RaxeQueryEngineCallback,
        RaxeSpanHandler,
    )
    from raxe.sdk.integrations.portkey import (
        PortkeyGuardConfig,
        RaxePortkeyGuard,
        RaxePortkeyWebhook,
        create_portkey_guard,
        create_portkey_webhook,
    )
    from raxe.sdk.integrations.litellm import (
        LiteLLMConfig,
        RaxeLiteLLMCallback,
        create_litellm_handler,
    )
    from raxe.sdk.integrations.dspy import (
        DSPyConfig,
        RaxeDSPyCallback,
        RaxeModuleGuard,
        create_dspy_callback,
        create_module_guard,
    )

__all__ = [
    # LangChain
    "RaxeCallbackHandler",
    # Hugging Face
    "RaxePipeline",
    # LlamaIndex
    "RaxeLlamaIndexCallback",
    "RaxeQueryEngineCallback",
    "RaxeAgentCallback",
    "RaxeSpanHandler",
    # AutoGen
    "RaxeConversationGuard",
    # CrewAI
    "RaxeCrewGuard",
    "CrewGuardConfig",
    "CrewScanStats",
    "create_crew_guard",
    # Portkey
    "RaxePortkeyWebhook",
    "RaxePortkeyGuard",
    "PortkeyGuardConfig",
    "create_portkey_guard",
    "create_portkey_webhook",
    # LiteLLM
    "RaxeLiteLLMCallback",
    "LiteLLMConfig",
    "create_litellm_handler",
    # DSPy
    "RaxeDSPyCallback",
    "RaxeModuleGuard",
    "DSPyConfig",
    "create_dspy_callback",
    "create_module_guard",
    # Base agent scanner classes
    "AgentScanner",
    "AgentScannerConfig",
    "AgentScanResult",
    "MessageType",
    "ScanContext",
    "ScanMode",
]


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

    # LlamaIndex integrations
    elif name == "RaxeLlamaIndexCallback":
        try:
            from raxe.sdk.integrations.llamaindex import RaxeLlamaIndexCallback
            return RaxeLlamaIndexCallback
        except ImportError as e:
            raise ImportError(
                "LlamaIndex integration requires llama-index-core package. "
                "Install with: pip install llama-index-core"
            ) from e

    elif name == "RaxeQueryEngineCallback":
        try:
            from raxe.sdk.integrations.llamaindex import RaxeQueryEngineCallback
            return RaxeQueryEngineCallback
        except ImportError as e:
            raise ImportError(
                "LlamaIndex integration requires llama-index-core package. "
                "Install with: pip install llama-index-core"
            ) from e

    elif name == "RaxeAgentCallback":
        try:
            from raxe.sdk.integrations.llamaindex import RaxeAgentCallback
            return RaxeAgentCallback
        except ImportError as e:
            raise ImportError(
                "LlamaIndex integration requires llama-index-core package. "
                "Install with: pip install llama-index-core"
            ) from e

    elif name == "RaxeSpanHandler":
        try:
            from raxe.sdk.integrations.llamaindex import RaxeSpanHandler
            return RaxeSpanHandler
        except ImportError as e:
            raise ImportError(
                "LlamaIndex integration requires llama-index-core package. "
                "Install with: pip install llama-index-core"
            ) from e

    # AutoGen integration
    elif name == "RaxeConversationGuard":
        # AutoGen integration - no hard dependency on autogen
        # The guard uses duck typing to work with any ConversableAgent
        from raxe.sdk.integrations.autogen import RaxeConversationGuard
        return RaxeConversationGuard

    # CrewAI integration
    elif name in ("RaxeCrewGuard", "CrewGuardConfig", "CrewScanStats", "create_crew_guard"):
        # CrewAI integration - no hard dependency on crewai
        # The guard uses duck typing to work with Crew, Agent, Task
        from raxe.sdk.integrations import crewai
        return getattr(crewai, name)

    # Portkey integration
    elif name in (
        "RaxePortkeyWebhook",
        "RaxePortkeyGuard",
        "PortkeyGuardConfig",
        "create_portkey_guard",
        "create_portkey_webhook",
    ):
        # Portkey integration - no hard dependency on portkey-ai
        # Works with any OpenAI-compatible client
        from raxe.sdk.integrations import portkey
        return getattr(portkey, name)

    # LiteLLM integration
    elif name in (
        "RaxeLiteLLMCallback",
        "LiteLLMConfig",
        "create_litellm_handler",
    ):
        # LiteLLM integration - no hard dependency on litellm
        # The callback works with standard LiteLLM API
        from raxe.sdk.integrations import litellm
        return getattr(litellm, name)

    # DSPy integration
    elif name in (
        "RaxeDSPyCallback",
        "RaxeModuleGuard",
        "DSPyConfig",
        "create_dspy_callback",
        "create_module_guard",
    ):
        # DSPy integration - no hard dependency on dspy
        # Works with DSPy's callback system
        from raxe.sdk.integrations import dspy
        return getattr(dspy, name)

    # Base agent scanner classes (no external dependencies)
    elif name in (
        "AgentScanner",
        "AgentScannerConfig",
        "AgentScanResult",
        "MessageType",
        "ScanContext",
        "ScanMode",
    ):
        from raxe.sdk.integrations import agent_scanner
        return getattr(agent_scanner, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
