"""AutoGen (pyautogen) integration for RAXE scanning.

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

Requirements:
    - pyautogen >= 0.2.0 or autogen-agentchat ~= 0.2

Usage:
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

Notes on AutoGen Versions:
    - AutoGen 0.2.x: Use `register_hook` for message interception
    - AutoGen 0.4.x: Has different API, may need migration
    - AG2 (fork): Compatible with 0.2.x API

    This integration targets pyautogen 0.2+ / autogen-agentchat ~= 0.2
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from raxe.sdk.agent_scanner import (
    AgentScannerConfig,
    AgentScanResult,
    MessageType,
    ScanContext,
    ScanType,
    create_agent_scanner,
)
from raxe.sdk.exceptions import SecurityException

if TYPE_CHECKING:
    from raxe.sdk.client import Raxe

logger = logging.getLogger(__name__)


# Type alias for AutoGen message format
AutoGenMessage = dict[str, Any]


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
        raxe: "Raxe",
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
        """Register RAXE scanning hooks with an AutoGen agent.

        This method registers message processing hooks with the agent
        to enable automatic scanning of all messages.

        Hooks registered:
        - process_message_before_send: Scan outgoing messages
        - process_last_received_message: Scan incoming messages

        Args:
            agent: AutoGen ConversableAgent or subclass

        Raises:
            TypeError: If agent is not a ConversableAgent
            ValueError: If agent has no name attribute

        Example:
            assistant = AssistantAgent("assistant", llm_config=config)
            guard.register(assistant)
        """
        # Validate agent type
        if not self._is_conversable_agent(agent):
            raise TypeError(
                f"Expected ConversableAgent, got {type(agent).__name__}. "
                "Ensure you're using autogen.ConversableAgent or a subclass."
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
        """Check if object is an AutoGen ConversableAgent.

        We check by duck typing to avoid hard dependency on autogen.

        Args:
            agent: Object to check

        Returns:
            True if agent appears to be a ConversableAgent
        """
        # Check for required ConversableAgent methods
        required_attrs = [
            "register_hook",
            "send",
            "receive",
            "generate_reply",
        ]

        return all(hasattr(agent, attr) for attr in required_attrs)

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

        AutoGen messages can be:
        - String: Direct text content
        - Dict with "content": Standard message format
        - Dict with "function_call": Function call message
        - List of content blocks: Multi-modal message

        Args:
            message: AutoGen message in any format

        Returns:
            Extracted text content, or None if no text found
        """
        if message is None:
            return None

        # String message
        if isinstance(message, str):
            return message

        # Dict message
        if isinstance(message, dict):
            # Standard content field
            content = message.get("content")
            if isinstance(content, str):
                return content

            # List of content blocks (multi-modal)
            if isinstance(content, list):
                texts = []
                for block in content:
                    if isinstance(block, str):
                        texts.append(block)
                    elif isinstance(block, dict) and "text" in block:
                        texts.append(block["text"])
                return " ".join(texts) if texts else None

            # Function call
            function_call = message.get("function_call")
            if function_call and isinstance(function_call, dict):
                # Return function name and arguments
                func_name = function_call.get("name", "")
                func_args = function_call.get("arguments", "")
                return f"{func_name}: {func_args}"

            # Tool calls
            tool_calls = message.get("tool_calls")
            if tool_calls and isinstance(tool_calls, list):
                texts = []
                for call in tool_calls:
                    if isinstance(call, dict):
                        func = call.get("function", {})
                        name = func.get("name", "")
                        args = func.get("arguments", "")
                        texts.append(f"{name}: {args}")
                return " | ".join(texts) if texts else None

        return None

    def _is_function_call(self, message: AutoGenMessage | str) -> bool:
        """Check if message is a function/tool call.

        Args:
            message: Message to check

        Returns:
            True if message contains function/tool call
        """
        if not isinstance(message, dict):
            return False

        return "function_call" in message or "tool_calls" in message

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

    def __repr__(self) -> str:
        """String representation of guard."""
        return (
            f"RaxeConversationGuard("
            f"on_threat={self.config.on_threat!r}, "
            f"agents={len(self._registered_agents)})"
        )


# Re-export for convenience
__all__ = [
    "RaxeConversationGuard",
    "AgentScannerConfig",
    "ScanMode",
    "MessageType",
    "ScanContext",
]
