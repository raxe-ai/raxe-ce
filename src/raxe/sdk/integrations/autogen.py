"""AutoGen integration for RAXE scanning.

Provides RaxeConversationGuard for automatic security scanning of
multi-agent conversations in AutoGen applications.

This integration works with:
    - ConversableAgent and its subclasses
    - AssistantAgent, UserProxyAgent
    - GroupChat conversations
    - Function/tool calls
    - Agent-to-agent message flows

Key Features:
    - Hook-based message interception (no code changes to agents)
    - Configurable blocking modes (log-only, block-on-threat, etc.)
    - Multi-agent conversation awareness
    - Function call scanning
    - Privacy-preserving logging

Supported Versions:
    - pyautogen 0.2.x / autogen-agentchat 0.2.x (hook-based API)
    - autogen-agentchat 0.4.x+ (async message-based API)
    - AG2 (fork): Compatible with 0.2.x API

Usage (v0.2.x - hook-based):
    from autogen import AssistantAgent, UserProxyAgent
    from raxe import Raxe
    from raxe.sdk.integrations import RaxeConversationGuard

    # Create agents
    assistant = AssistantAgent("assistant", llm_config=llm_config)
    user = UserProxyAgent("user")

    # Create RAXE guard
    raxe = Raxe()
    guard = RaxeConversationGuard(raxe)

    # Register with agents (one-liner per agent)
    guard.register(assistant)
    guard.register(user)

    # Conversations are now automatically scanned
    user.initiate_chat(assistant, message="Hello!")

Usage (v0.4.x+ - wrapper-based):
    from autogen_agentchat.agents import AssistantAgent
    from raxe import Raxe
    from raxe.sdk.integrations import RaxeConversationGuard

    # Create RAXE guard
    raxe = Raxe()
    guard = RaxeConversationGuard(raxe)

    # Create agent with RAXE wrapper
    assistant = AssistantAgent("assistant", model_client=client)
    protected_assistant = guard.wrap_agent(assistant)

    # Use protected agent in your workflow
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from raxe.sdk.agent_scanner import (
    AgentScannerConfig,
    AgentScanResult,
    MessageType,
    ScanContext,
    create_agent_scanner,
)
from raxe.sdk.exceptions import SecurityException
from raxe.sdk.integrations.extractors import (
    extract_function_call_text,
    extract_text_from_message,
    is_function_call,
)

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe

logger = logging.getLogger(__name__)


# Type alias for AutoGen message format
AutoGenMessage = dict[str, Any]


# ============================================================================
# AutoGen Version Detection
# ============================================================================

def _detect_autogen_version() -> tuple[int, int, int]:
    """Detect installed AutoGen version.

    Checks for autogen-agentchat (new package) first, then pyautogen.

    Returns:
        Tuple of (major, minor, patch) version numbers.
        Returns (0, 0, 0) if AutoGen is not installed.
    """
    # Try new package name first (v0.4+)
    try:
        import autogen_agentchat
        version_str = getattr(autogen_agentchat, "__version__", "0.0.0")
        parts = version_str.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2].split("-")[0].split("a")[0].split("b")[0]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except ImportError:
        pass

    # Try legacy package name (v0.2.x)
    try:
        import autogen
        version_str = getattr(autogen, "__version__", "0.0.0")
        parts = version_str.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2].split("-")[0].split("a")[0].split("b")[0]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except ImportError:
        pass

    # Try pyautogen (alternative package name)
    try:
        import pyautogen
        version_str = getattr(pyautogen, "__version__", "0.0.0")
        parts = version_str.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2].split("-")[0].split("a")[0].split("b")[0]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except ImportError:
        pass

    return (0, 0, 0)


def _is_v04_or_later() -> bool:
    """Check if AutoGen v0.4+ (new async API) is installed.

    Returns:
        True if using v0.4+ with async message API.
    """
    version = _detect_autogen_version()
    return version >= (0, 4, 0)


def _has_register_hook(agent: Any) -> bool:
    """Check if agent has register_hook method (v0.2.x API).

    Args:
        agent: AutoGen agent to check

    Returns:
        True if agent supports hook-based registration
    """
    return hasattr(agent, "register_hook") and callable(agent.register_hook)


def _is_async_agent(agent: Any) -> bool:
    """Check if agent uses async message API (v0.4+ API).

    Args:
        agent: AutoGen agent to check

    Returns:
        True if agent supports async message API
    """
    return hasattr(agent, "on_messages") or hasattr(agent, "on_messages_stream")


class RaxeConversationGuard:
    """RAXE security guard for AutoGen multi-agent conversations.

    Registers hooks with AutoGen agents to intercept and scan messages
    for security threats. Supports multiple agents and conversation flows.

    The guard uses AutoGen's hook system to intercept messages at key points:
    - process_message_before_send: Scan outgoing messages before sending
    - process_all_messages_before_reply: Scan conversation history before reply
    - process_last_received_message: Scan incoming messages

    Attributes:
        raxe: Raxe client instance for scanning
        config: Scanner configuration
        registered_agents: Set of registered agent names

    Example:
        # Basic usage with default config (log-only mode)
        from autogen import AssistantAgent, UserProxyAgent
        from raxe import Raxe
        from raxe.sdk.integrations.autogen import RaxeConversationGuard

        raxe = Raxe()
        guard = RaxeConversationGuard(raxe)

        assistant = AssistantAgent("assistant", llm_config=config)
        user = UserProxyAgent("user")

        guard.register(assistant)
        guard.register(user)

        # All messages are now scanned
        user.initiate_chat(assistant, message="Hello!")

    Example with blocking:
        # Block on HIGH or CRITICAL threats
        from raxe.sdk.integrations.autogen import RaxeConversationGuard
        from raxe.sdk.agent_scanner import AgentScannerConfig

        config = AgentScannerConfig(
            on_threat="block",
            block_severity_threshold="HIGH",
        )
        guard = RaxeConversationGuard(raxe, config=config)

        # Messages with HIGH/CRITICAL threats will be blocked
    """

    def __init__(
        self,
        raxe: Raxe,
        config: AgentScannerConfig | None = None,
    ) -> None:
        """Initialize the conversation guard.

        Args:
            raxe: Raxe client instance for scanning
            config: Optional scanner configuration. Defaults to log-only mode.

        Example:
            # Default (log-only)
            guard = RaxeConversationGuard(raxe)

            # Blocking mode for high severity threats
            config = AgentScannerConfig(
                on_threat="block",
                block_severity_threshold="HIGH",
                scan_tool_calls=True,
            )
            guard = RaxeConversationGuard(raxe, config=config)
        """
        # Default to log-only mode for safety
        if config is None:
            config = AgentScannerConfig(on_threat="log")

        self._config = config  # Store for property access
        self._scanner = create_agent_scanner(raxe, config)
        self._registered_agents: set[str] = set()

        logger.info(
            "RaxeConversationGuard initialized",
            extra={
                "on_threat": config.on_threat,
                "scan_prompts": config.scan_prompts,
                "scan_tool_calls": config.scan_tool_calls,
            },
        )

    @property
    def config(self) -> AgentScannerConfig:
        """Get the scanner configuration."""
        return self._config

    @property
    def registered_agents(self) -> set[str]:
        """Get set of registered agent names."""
        return self._registered_agents.copy()

    def register(self, agent: Any) -> None:
        """Register RAXE scanning hooks with an AutoGen agent (v0.2.x).

        This method registers message processing hooks with the agent
        to enable automatic scanning of all messages.

        For AutoGen v0.4+, use wrap_agent() instead.

        Hooks registered:
        - process_message_before_send: Scan outgoing messages
        - process_last_received_message: Scan incoming messages

        Args:
            agent: AutoGen ConversableAgent or subclass (v0.2.x)

        Raises:
            TypeError: If agent is not a v0.2.x ConversableAgent
            ValueError: If agent has no name attribute

        Example:
            assistant = AssistantAgent("assistant", llm_config=config)
            guard.register(assistant)
        """
        # Check if this is a v0.4+ async agent
        if _is_async_agent(agent):
            raise TypeError(
                f"Agent {type(agent).__name__} uses AutoGen v0.4+ API. "
                "Use guard.wrap_agent(agent) instead of guard.register(agent)."
            )

        # Validate agent type for v0.2.x
        if not self._is_conversable_agent(agent):
            raise TypeError(
                f"Expected ConversableAgent with register_hook method, got {type(agent).__name__}. "
                "For v0.2.x: use autogen.ConversableAgent or subclass. "
                "For v0.4+: use guard.wrap_agent(agent) instead."
            )

        # Get agent name
        agent_name = getattr(agent, "name", None)
        if agent_name is None:
            raise ValueError("Agent must have a 'name' attribute")

        # Skip if already registered
        if agent_name in self._registered_agents:
            logger.debug(
                "Agent already registered",
                extra={"agent": agent_name},
            )
            return

        # Register hooks
        self._register_hooks(agent)

        # Track registration
        self._registered_agents.add(agent_name)

        logger.info(
            "Agent registered with RAXE guard",
            extra={"agent": agent_name},
        )

    def register_all(self, *agents: Any) -> None:
        """Register multiple agents at once.

        Convenience method for registering several agents.

        Args:
            *agents: AutoGen agents to register

        Example:
            assistant = AssistantAgent("assistant", llm_config=config)
            user = UserProxyAgent("user")
            critic = AssistantAgent("critic", llm_config=config)

            guard.register_all(assistant, user, critic)
        """
        for agent in agents:
            self.register(agent)

    def unregister(self, agent: Any) -> None:
        """Unregister an agent from RAXE scanning.

        Note: This only removes tracking. AutoGen doesn't provide
        a way to unregister hooks, so the hooks will remain active
        but won't affect operation.

        Args:
            agent: Agent to unregister
        """
        agent_name = getattr(agent, "name", None)
        if agent_name and agent_name in self._registered_agents:
            self._registered_agents.discard(agent_name)
            logger.info(
                "Agent unregistered from RAXE guard",
                extra={"agent": agent_name},
            )

    def _is_conversable_agent(self, agent: Any) -> bool:
        """Check if object is an AutoGen ConversableAgent (v0.2.x).

        We check by duck typing to avoid hard dependency on autogen.

        Args:
            agent: Object to check

        Returns:
            True if agent appears to be a v0.2.x ConversableAgent
        """
        # Check for required v0.2.x ConversableAgent methods
        return _has_register_hook(agent) and hasattr(agent, "name")

    def _register_hooks(self, agent: Any) -> None:
        """Register RAXE scanning hooks with an agent.

        Args:
            agent: AutoGen agent to register hooks with
        """
        agent_name = getattr(agent, "name", "unknown")

        # Create hook closures that capture agent context
        def process_message_before_send_hook(
            sender: Any,
            message: AutoGenMessage | str,
            recipient: Any,
            silent: bool,
        ) -> AutoGenMessage | str:
            """Hook to scan messages before sending."""
            return self._scan_outgoing_message(
                message=message,
                sender_name=agent_name,
                recipient_name=getattr(recipient, "name", None),
            )

        def process_last_received_message_hook(
            messages: list[AutoGenMessage],
        ) -> list[AutoGenMessage]:
            """Hook to scan the last received message."""
            return self._scan_last_received(
                messages=messages,
                receiver_name=agent_name,
            )

        # Register the hooks
        try:
            agent.register_hook(
                "process_message_before_send",
                process_message_before_send_hook,
            )
            logger.debug(
                "Registered process_message_before_send hook",
                extra={"agent": agent_name},
            )
        except Exception as e:
            logger.warning(
                "Failed to register process_message_before_send hook",
                extra={"agent": agent_name, "error": str(e)},
            )

        try:
            agent.register_hook(
                "process_last_received_message",
                process_last_received_message_hook,
            )
            logger.debug(
                "Registered process_last_received_message hook",
                extra={"agent": agent_name},
            )
        except Exception as e:
            logger.warning(
                "Failed to register process_last_received_message hook",
                extra={"agent": agent_name, "error": str(e)},
            )

    def _raise_security_exception(self, result: AgentScanResult) -> None:
        """Raise SecurityException from an AgentScanResult.

        Handles both cases where pipeline_result is available or not.

        Args:
            result: AgentScanResult with threat details

        Raises:
            SecurityException: Always raises with appropriate error info
        """
        from raxe.sdk.exceptions import security_threat_detected_error

        if result.pipeline_result is not None:
            raise SecurityException(result.pipeline_result)

        # Create exception from AgentScanResult data
        error = security_threat_detected_error(
            severity=str(result.severity or "UNKNOWN"),
            detection_count=result.detection_count,
        )
        # Create a simple exception with the error info
        message = (
            f"Security threat detected: {result.severity} "
            f"({result.detection_count} detection(s))"
        )
        exc = SecurityException.__new__(SecurityException)
        exc.result = None  # No pipeline result available
        exc.error = error
        Exception.__init__(exc, message)
        raise exc

    def _scan_outgoing_message(
        self,
        message: AutoGenMessage | str,
        sender_name: str,
        recipient_name: str | None,
    ) -> AutoGenMessage | str:
        """Scan an outgoing message before it's sent.

        Args:
            message: Message to scan (string or dict)
            sender_name: Name of sending agent
            recipient_name: Name of receiving agent

        Returns:
            Original message if allowed, raises SecurityException if blocked
        """
        # Extract text content from message
        text = self._extract_message_text(message)
        if not text:
            return message

        # Determine message type
        if self._is_function_call(message):
            message_type = MessageType.FUNCTION_CALL
        elif recipient_name is None:
            message_type = MessageType.AGENT_RESPONSE
        else:
            message_type = MessageType.AGENT_TO_AGENT

        # Create context
        context = ScanContext(
            message_type=message_type,
            sender_name=sender_name,
            receiver_name=recipient_name,
        )

        # Scan the message
        result = self._scanner.scan_message(text, context=context)

        # Handle blocking
        if result.should_block:
            self._raise_security_exception(result)

        return message

    def _scan_last_received(
        self,
        messages: list[AutoGenMessage],
        receiver_name: str,
    ) -> list[AutoGenMessage]:
        """Scan the last received message in conversation.

        This hook is called before generating a reply.

        Args:
            messages: List of messages in conversation
            receiver_name: Name of agent receiving messages

        Returns:
            Original messages if allowed, raises SecurityException if blocked
        """
        if not messages:
            return messages

        # Get the last message
        last_message = messages[-1]
        text = self._extract_message_text(last_message)

        if not text:
            return messages

        # Determine sender and message type
        sender_name = last_message.get("name") if isinstance(last_message, dict) else None
        role = last_message.get("role") if isinstance(last_message, dict) else None

        if role == "user":
            message_type = MessageType.HUMAN_INPUT
        elif role == "function":
            message_type = MessageType.FUNCTION_RESULT
        else:
            message_type = MessageType.AGENT_TO_AGENT

        # Create context
        context = ScanContext(
            message_type=message_type,
            sender_name=sender_name,
            receiver_name=receiver_name,
            message_index=len(messages) - 1,
        )

        # Scan the message
        result = self._scanner.scan_message(text, context=context)

        # Handle blocking
        if result.should_block:
            self._raise_security_exception(result)

        return messages

    def _extract_message_text(self, message: AutoGenMessage | str) -> str | None:
        """Extract text content from an AutoGen message.

        Uses unified extractor from raxe.sdk.integrations.extractors.
        Falls back to function call extraction if no content found.

        Args:
            message: AutoGen message in any format

        Returns:
            Extracted text content, or None if no text found
        """
        # First try standard message extraction
        text = extract_text_from_message(message)
        if text:
            return text

        # For function calls, extract the call details
        if is_function_call(message):
            return extract_function_call_text(message)

        return None

    def _is_function_call(self, message: AutoGenMessage | str) -> bool:
        """Check if message is a function/tool call.

        Uses unified extractor from raxe.sdk.integrations.extractors.

        Args:
            message: Message to check

        Returns:
            True if message contains function/tool call
        """
        return is_function_call(message)

    def scan_manual(
        self,
        text: str,
        *,
        message_type: MessageType = MessageType.AGENT_TO_AGENT,
        sender_name: str | None = None,
        receiver_name: str | None = None,
    ) -> AgentScanResult:
        """Manually scan text outside of hook flow.

        Use this for scanning text that isn't captured by hooks,
        such as user input before passing to agents.

        Args:
            text: Text to scan
            message_type: Type of message
            sender_name: Optional sender name
            receiver_name: Optional receiver name

        Returns:
            AgentScanResult with scan details

        Example:
            # Scan user input before starting chat
            result = guard.scan_manual(
                user_input,
                message_type=MessageType.HUMAN_INPUT,
                sender_name="human"
            )
            if result.should_block:
                print("Cannot proceed - security threat detected")
        """
        context = ScanContext(
            message_type=message_type,
            sender_name=sender_name,
            receiver_name=receiver_name,
        )

        return self._scanner.scan_message(text, context=context)

    # =========================================================================
    # AutoGen v0.4+ Support (Wrapper-based)
    # =========================================================================

    def wrap_agent(self, agent: Any) -> Any:
        """Wrap an AutoGen v0.4+ agent with RAXE scanning.

        This method creates a wrapper around an AutoGen v0.4+ agent that
        scans all messages before they are processed by the agent.

        For AutoGen v0.2.x, use register() instead.

        Args:
            agent: AutoGen v0.4+ agent (must have on_messages method)

        Returns:
            Wrapped agent with RAXE scanning enabled

        Raises:
            TypeError: If agent doesn't support v0.4+ API

        Example:
            from autogen_agentchat.agents import AssistantAgent
            from raxe import Raxe
            from raxe.sdk.integrations import RaxeConversationGuard

            guard = RaxeConversationGuard(Raxe())
            assistant = AssistantAgent("assistant", model_client=client)
            protected = guard.wrap_agent(assistant)

            # Use protected agent - messages will be scanned
        """
        # Check if this is a v0.2.x agent
        if self._is_conversable_agent(agent):
            raise TypeError(
                f"Agent {type(agent).__name__} uses AutoGen v0.2.x API. "
                "Use guard.register(agent) instead of guard.wrap_agent(agent)."
            )

        # Check if agent has v0.4+ API
        if not _is_async_agent(agent):
            raise TypeError(
                f"Agent {type(agent).__name__} doesn't have on_messages method. "
                "Ensure you're using AutoGen v0.4+ agents."
            )

        # Get agent name for tracking
        agent_name = getattr(agent, "name", type(agent).__name__)

        # Track registration
        self._registered_agents.add(agent_name)

        logger.info(
            "Agent wrapped with RAXE guard (v0.4+ API)",
            extra={"agent": agent_name},
        )

        # Return a wrapper that scans messages
        return _RaxeAgentWrapper(agent, self, agent_name)

    def __repr__(self) -> str:
        """String representation of guard."""
        return (
            f"RaxeConversationGuard("
            f"on_threat={self.config.on_threat!r}, "
            f"agents={len(self._registered_agents)})"
        )


# ============================================================================
# AutoGen v0.4+ Agent Wrapper
# ============================================================================

class _RaxeAgentWrapper:
    """Wrapper for AutoGen v0.4+ agents that adds RAXE scanning.

    This wrapper intercepts the on_messages and on_messages_stream methods
    to scan all incoming messages before they are processed by the agent.

    The wrapper uses composition to delegate all other attributes and methods
    to the wrapped agent.
    """

    def __init__(
        self,
        agent: Any,
        guard: RaxeConversationGuard,
        agent_name: str,
    ) -> None:
        """Initialize agent wrapper.

        Args:
            agent: The AutoGen v0.4+ agent to wrap
            guard: The RaxeConversationGuard instance
            agent_name: Name of the agent for logging
        """
        self._agent = agent
        self._guard = guard
        self._agent_name = agent_name

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to wrapped agent."""
        return getattr(self._agent, name)

    async def on_messages(
        self,
        messages: list[Any],
        cancellation_token: Any = None,
    ) -> Any:
        """Process messages with RAXE scanning (v0.4+ API).

        Scans all messages before passing to the wrapped agent.

        Args:
            messages: List of ChatMessage objects
            cancellation_token: Optional cancellation token

        Returns:
            Response from the wrapped agent
        """
        # Scan each message
        for msg in messages:
            self._scan_message(msg)

        # Delegate to wrapped agent
        return await self._agent.on_messages(messages, cancellation_token)

    async def on_messages_stream(
        self,
        messages: list[Any],
        cancellation_token: Any = None,
    ) -> Any:
        """Process messages with streaming and RAXE scanning (v0.4+ API).

        Scans all messages before passing to the wrapped agent.

        Args:
            messages: List of ChatMessage objects
            cancellation_token: Optional cancellation token

        Yields:
            Streaming responses from the wrapped agent
        """
        # Scan each message
        for msg in messages:
            self._scan_message(msg)

        # Delegate to wrapped agent
        async for response in self._agent.on_messages_stream(messages, cancellation_token):
            yield response

    def _scan_message(self, message: Any) -> None:
        """Scan a single message for threats.

        Args:
            message: ChatMessage object or dict

        Raises:
            SecurityException: If threat detected and blocking is enabled
        """
        # Extract text from message
        text = self._extract_message_text(message)
        if not text:
            return

        # Determine message type
        source = getattr(message, "source", None)
        if source == "user":
            message_type = MessageType.HUMAN_INPUT
        else:
            message_type = MessageType.AGENT_TO_AGENT

        # Create context
        context = ScanContext(
            message_type=message_type,
            sender_name=source,
            receiver_name=self._agent_name,
        )

        # Perform scan
        result = self._guard._scanner.scan_message(text, context=context)

        # Handle blocking
        if result.should_block:
            logger.warning(
                "Message blocked by RAXE guard (v0.4+)",
                extra={
                    "agent": self._agent_name,
                    "severity": result.severity,
                    "prompt_hash": result.prompt_hash,
                },
            )
            self._guard._raise_security_exception(result)

    def _extract_message_text(self, message: Any) -> str | None:
        """Extract text from a v0.4+ ChatMessage.

        Uses unified extractor from raxe.sdk.integrations.extractors.

        Args:
            message: ChatMessage object or dict

        Returns:
            Extracted text or None
        """
        return extract_text_from_message(message)

    def __repr__(self) -> str:
        """String representation."""
        return f"RaxeAgentWrapper({self._agent_name})"


# Re-export for convenience
__all__ = [
    "AgentScannerConfig",
    "MessageType",
    "RaxeConversationGuard",
    "ScanContext",
]
