"""LangChain integration for RAXE scanning.

Provides a callback handler that automatically scans prompts and responses
in LangChain applications without modifying existing code.

This integration supports:
    - LangChain 0.1.x, 0.2.x, 0.3.x
    - LLMs, Chat Models
    - Chains (Sequential, Conversational, etc.)
    - Agents and Tools (with validation)
    - Memory systems

Key Features:
    - AgentScanner composition for unified scanning
    - Tool validation with allowlist/blocklist
    - Trace-aware scanning with correlation IDs
    - Version-compatible callback implementation
    - Default: log-only (non-blocking)

Usage:
    from langchain.llms import OpenAI
    from raxe.sdk.integrations import RaxeCallbackHandler

    # Basic usage (log-only mode)
    llm = OpenAI(callbacks=[RaxeCallbackHandler()])

    # With tool restrictions
    from raxe.sdk.agent_scanner import ToolPolicy

    handler = RaxeCallbackHandler(
        tool_policy=ToolPolicy.block_tools("shell", "file_write")
    )

    # Blocking mode for prompts
    handler = RaxeCallbackHandler(block_on_prompt_threats=True)
"""
from __future__ import annotations

import logging
import sys
import uuid
from typing import TYPE_CHECKING, Any

from raxe.sdk.agent_scanner import (
    AgentScanner,
    AgentScanResult,
    ScanConfig,
    ScanType,
    ToolPolicy,
)
from raxe.sdk.client import Raxe
from raxe.sdk.exceptions import SecurityException

if TYPE_CHECKING:
    from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)


# ============================================================================
# LangChain Version Detection
# ============================================================================

def _detect_langchain_version() -> tuple[int, int, int]:
    """Detect installed LangChain version.

    Returns:
        Tuple of (major, minor, patch) version numbers.
        Returns (0, 0, 0) if LangChain is not installed.
    """
    try:
        import langchain

        version_str = getattr(langchain, "__version__", "0.0.0")
        parts = version_str.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2].split("-")[0].split("a")[0].split("b")[0]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except ImportError:
        return (0, 0, 0)
    except (ValueError, IndexError):
        return (0, 0, 0)


def _get_langchain_version_info() -> dict[str, Any]:
    """Get detailed LangChain version information.

    Returns:
        Dictionary with version details for debugging.
    """
    version = _detect_langchain_version()
    return {
        "version": f"{version[0]}.{version[1]}.{version[2]}",
        "major": version[0],
        "minor": version[1],
        "patch": version[2],
        "has_langchain_core": _has_langchain_core(),
        "has_run_manager": _has_run_manager(),
    }


def _has_langchain_core() -> bool:
    """Check if langchain-core is available (0.1+)."""
    try:
        import langchain_core  # noqa: F401
        return True
    except ImportError:
        return False


def _has_run_manager() -> bool:
    """Check if run manager is available for async support."""
    try:
        from langchain_core.callbacks.manager import RunManager  # noqa: F401
        return True
    except ImportError:
        return False


# ============================================================================
# Base Callback Handler (Version Agnostic)
# ============================================================================

class RaxeCallbackHandler:
    """LangChain callback handler for automatic RAXE scanning.

    This callback handler uses AgentScanner composition to intercept
    LangChain events and scan for security threats.

    Scans are performed on:
        1. All prompts before sending to LLM (on_llm_start)
        2. All LLM responses (on_llm_end)
        3. Tool inputs with validation (on_tool_start)
        4. Tool outputs (on_tool_end)
        5. Agent actions (on_agent_action)

    The handler supports both blocking and monitoring modes:
        - Blocking mode: Raises SecurityException on threat detection
        - Monitoring mode (default): Logs threats but allows execution

    Attributes:
        scanner: AgentScanner instance for scanning operations
        block_on_prompt_threats: Block execution if prompt threat detected
        block_on_response_threats: Block execution if response threat detected
        scan_tools: Whether to scan tool inputs/outputs
        scan_agent_actions: Whether to scan agent actions
        trace_id: Current trace ID for correlation

    Example:
        >>> from langchain.llms import OpenAI
        >>> from raxe.sdk.integrations import RaxeCallbackHandler
        >>>
        >>> # Monitoring mode (default)
        >>> handler = RaxeCallbackHandler()
        >>> llm = OpenAI(callbacks=[handler])
        >>>
        >>> # Blocking mode
        >>> handler = RaxeCallbackHandler(block_on_prompt_threats=True)
        >>> llm = OpenAI(callbacks=[handler])
        >>>
        >>> # With tool restrictions
        >>> from raxe.sdk.agent_scanner import ToolPolicy
        >>> handler = RaxeCallbackHandler(
        ...     tool_policy=ToolPolicy.block_tools("shell", "file_write")
        ... )
    """

    # Class-level version info (computed once)
    _langchain_version: tuple[int, int, int] | None = None

    def __init__(
        self,
        raxe_client: Raxe | None = None,
        *,
        scanner: AgentScanner | None = None,
        tool_policy: ToolPolicy | None = None,
        block_on_prompt_threats: bool = False,  # Changed: default log-only
        block_on_response_threats: bool = False,
        scan_tools: bool = True,
        scan_agent_actions: bool = True,
        on_threat: Any | None = None,
    ) -> None:
        """Initialize RAXE callback handler.

        Args:
            raxe_client: Optional Raxe instance (creates default if None)
            scanner: Optional AgentScanner instance (creates default if None)
            tool_policy: Policy for tool validation (default: no restrictions)
            block_on_prompt_threats: Block on prompt threats (default: False)
            block_on_response_threats: Block on response threats (default: False)
            scan_tools: Scan tool inputs/outputs (default: True)
            scan_agent_actions: Scan agent actions (default: True)
            on_threat: Optional callback for threat notifications

        Example:
            # Default configuration (log-only)
            handler = RaxeCallbackHandler()

            # Blocking mode for prompts
            handler = RaxeCallbackHandler(block_on_prompt_threats=True)

            # With tool restrictions
            handler = RaxeCallbackHandler(
                tool_policy=ToolPolicy.block_tools("shell", "file_write")
            )

            # Custom Raxe client
            raxe = Raxe(telemetry=False)
            handler = RaxeCallbackHandler(raxe_client=raxe)
        """
        # Store configuration
        self.block_on_prompt_threats = block_on_prompt_threats
        self.block_on_response_threats = block_on_response_threats
        self.scan_tools = scan_tools
        self.scan_agent_actions = scan_agent_actions

        # Create or use provided scanner (composition pattern)
        if scanner is not None:
            self.scanner = scanner
        else:
            # Build scan configs from parameters
            scan_configs = {
                ScanType.PROMPT: ScanConfig(
                    enabled=True,
                    block_on_threat=block_on_prompt_threats,
                ),
                ScanType.RESPONSE: ScanConfig(
                    enabled=True,
                    block_on_threat=block_on_response_threats,
                ),
                ScanType.TOOL_CALL: ScanConfig(
                    enabled=scan_tools,
                    block_on_threat=block_on_prompt_threats,  # Use prompt policy
                ),
                ScanType.TOOL_RESULT: ScanConfig(
                    enabled=scan_tools,
                    block_on_threat=block_on_response_threats,  # Use response policy
                ),
                ScanType.AGENT_ACTION: ScanConfig(
                    enabled=scan_agent_actions,
                    block_on_threat=block_on_prompt_threats,  # Use prompt policy
                ),
            }

            self.scanner = AgentScanner(
                raxe_client=raxe_client,
                tool_policy=tool_policy,
                scan_configs=scan_configs,
                on_threat=on_threat,
            )

        # Store raxe reference for backwards compatibility
        self.raxe = self.scanner.raxe

        # Trace management
        self.trace_id: str | None = None

        # Detect LangChain version (once per class)
        if RaxeCallbackHandler._langchain_version is None:
            RaxeCallbackHandler._langchain_version = _detect_langchain_version()

        logger.debug(
            "RaxeCallbackHandler initialized",
            extra={
                "block_prompts": block_on_prompt_threats,
                "block_responses": block_on_response_threats,
                "scan_tools": scan_tools,
                "langchain_version": f"{self._langchain_version[0]}.{self._langchain_version[1]}.{self._langchain_version[2]}",
            },
        )

    # ========================================================================
    # LLM Callbacks
    # ========================================================================

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Scan prompts before LLM execution.

        Args:
            serialized: LLM serialization info
            prompts: List of prompts to send to LLM
            run_id: LangChain run ID (0.1+)
            parent_run_id: Parent run ID for nested runs
            tags: Optional tags for the run
            metadata: Optional metadata for the run
            **kwargs: Additional callback arguments

        Raises:
            SecurityException: If threat detected and blocking enabled
        """
        # Start trace if not already started
        if self.trace_id is None and run_id:
            self.trace_id = str(run_id)
            self.scanner.start_trace(self.trace_id)

        llm_name = serialized.get("name", serialized.get("id", ["unknown"])[-1] if isinstance(serialized.get("id"), list) else "unknown")

        for idx, prompt in enumerate(prompts):
            if not prompt or not prompt.strip():
                continue

            try:
                result = self.scanner.scan_prompt(
                    prompt,
                    metadata={
                        "llm_name": llm_name,
                        "prompt_index": idx,
                        "total_prompts": len(prompts),
                        **(metadata or {}),
                    },
                )

                if result.has_threats:
                    logger.warning(
                        f"Threat detected in LangChain prompt {idx + 1}/{len(prompts)}: "
                        f"{result.severity} severity "
                        f"(block={self.block_on_prompt_threats})"
                    )

            except SecurityException:
                logger.error(
                    f"Blocked LangChain prompt {idx + 1}/{len(prompts)} "
                    f"due to security threat"
                )
                raise

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Scan LLM responses after execution.

        Args:
            response: LLM response object
            run_id: LangChain run ID (0.1+)
            parent_run_id: Parent run ID for nested runs
            tags: Optional tags for the run
            **kwargs: Additional callback arguments

        Raises:
            SecurityException: If threat detected and blocking enabled
        """
        texts = self._extract_response_texts(response)

        for idx, text in enumerate(texts):
            if not text or not text.strip():
                continue

            try:
                result = self.scanner.scan_response(
                    text,
                    metadata={
                        "response_index": idx,
                        "total_responses": len(texts),
                    },
                )

                if result.has_threats:
                    logger.warning(
                        f"Threat detected in LangChain response {idx + 1}/{len(texts)}: "
                        f"{result.severity} severity "
                        f"(block={self.block_on_response_threats})"
                    )

            except SecurityException:
                logger.error(
                    f"Blocked LangChain response {idx + 1}/{len(texts)} "
                    f"due to security threat"
                )
                raise

    def on_llm_new_token(
        self,
        token: str,
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """Handle streaming token (no scanning, just observe).

        Streaming tokens are too small to scan meaningfully.
        Full response scanning happens in on_llm_end.

        Args:
            token: The new token
            run_id: LangChain run ID
            parent_run_id: Parent run ID
            **kwargs: Additional arguments
        """
        pass  # Streaming tokens are not scanned individually

    def on_llm_error(
        self,
        error: Exception | KeyboardInterrupt,
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """Handle LLM errors.

        Args:
            error: Exception that occurred
            run_id: LangChain run ID
            parent_run_id: Parent run ID
            **kwargs: Additional callback arguments
        """
        pass  # Don't interfere with error handling

    # ========================================================================
    # Chat Model Callbacks (LangChain 0.1+)
    # ========================================================================

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Scan chat messages before sending to model.

        This callback is for chat models (GPT-4, Claude, etc.).

        Args:
            serialized: Model serialization info
            messages: List of message lists (batched)
            run_id: LangChain run ID
            parent_run_id: Parent run ID
            tags: Optional tags
            metadata: Optional metadata
            **kwargs: Additional arguments

        Raises:
            SecurityException: If threat detected and blocking enabled
        """
        # Start trace if not already started
        if self.trace_id is None and run_id:
            self.trace_id = str(run_id)
            self.scanner.start_trace(self.trace_id)

        model_name = serialized.get("name", "unknown")

        # Extract text from messages
        for batch_idx, message_list in enumerate(messages):
            for msg_idx, message in enumerate(message_list):
                # Handle different message formats
                content = self._extract_message_content(message)
                if not content or not content.strip():
                    continue

                try:
                    result = self.scanner.scan_prompt(
                        content,
                        metadata={
                            "model_name": model_name,
                            "batch_index": batch_idx,
                            "message_index": msg_idx,
                            "message_type": self._get_message_type(message),
                            **(metadata or {}),
                        },
                    )

                    if result.has_threats:
                        logger.warning(
                            f"Threat detected in chat message: "
                            f"{result.severity} severity "
                            f"(block={self.block_on_prompt_threats})"
                        )

                except SecurityException:
                    logger.error("Blocked chat message due to security threat")
                    raise

    # ========================================================================
    # Tool Callbacks
    # ========================================================================

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Validate and scan tool inputs before execution.

        This method:
        1. Validates tool against policy (allowlist/blocklist)
        2. Scans tool input for threats

        Args:
            serialized: Tool serialization info
            input_str: Tool input string
            run_id: LangChain run ID
            parent_run_id: Parent run ID
            tags: Optional tags
            metadata: Optional metadata
            **kwargs: Additional callback arguments

        Raises:
            SecurityException: If threat detected and blocking enabled
            ValueError: If tool is not allowed by policy
        """
        if not self.scan_tools:
            return

        tool_name = serialized.get("name", "unknown")

        try:
            result = self.scanner.scan_tool_call(
                tool_name=tool_name,
                tool_args=input_str,
                metadata=metadata,
            )

            if result.policy_violation:
                logger.error(
                    f"Tool policy violation: '{tool_name}' - {result.message}"
                )
                if result.should_block:
                    raise ValueError(result.message)

            if result.has_threats:
                logger.warning(
                    f"Threat detected in tool '{tool_name}' input: "
                    f"{result.severity} severity"
                )

        except SecurityException:
            logger.error(f"Blocked tool '{tool_name}' execution due to security threat")
            raise

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Scan tool outputs after execution.

        Args:
            output: Tool output string
            run_id: LangChain run ID
            parent_run_id: Parent run ID
            tags: Optional tags
            **kwargs: Additional callback arguments

        Raises:
            SecurityException: If threat detected and blocking enabled
        """
        if not self.scan_tools or not output:
            return

        try:
            result = self.scanner.scan_tool_result(
                tool_name="unknown",  # Tool name not available in on_tool_end
                result=output,
            )

            if result.has_threats:
                logger.warning(
                    f"Threat detected in tool output: {result.severity} severity"
                )

        except SecurityException:
            logger.error("Blocked tool output due to security threat")
            raise

    def on_tool_error(
        self,
        error: Exception | KeyboardInterrupt,
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """Handle tool errors.

        Args:
            error: Exception that occurred
            run_id: LangChain run ID
            parent_run_id: Parent run ID
            **kwargs: Additional callback arguments
        """
        pass  # Don't interfere with error handling

    # ========================================================================
    # Agent Callbacks
    # ========================================================================

    def on_agent_action(
        self,
        action: Any,
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Scan agent actions before execution.

        Args:
            action: Agent action object
            run_id: LangChain run ID
            parent_run_id: Parent run ID
            tags: Optional tags
            **kwargs: Additional callback arguments

        Raises:
            SecurityException: If threat detected and blocking enabled
        """
        if not self.scan_agent_actions:
            return

        # Extract action details
        tool_name = None
        action_input = None

        if hasattr(action, "tool"):
            tool_name = str(action.tool)
        elif isinstance(action, dict) and "tool" in action:
            tool_name = str(action["tool"])

        if hasattr(action, "tool_input"):
            action_input = action.tool_input
        elif isinstance(action, dict) and "tool_input" in action:
            action_input = action["tool_input"]

        if action_input is None:
            return

        try:
            result = self.scanner.scan_agent_action(
                action_type="tool_call" if tool_name else "action",
                action_input=action_input,
                tool_name=tool_name,
            )

            if result.has_threats:
                logger.warning(
                    f"Threat detected in agent action '{tool_name or 'unknown'}': "
                    f"{result.severity} severity"
                )

        except SecurityException:
            logger.error("Blocked agent action due to security threat")
            raise

    def on_agent_finish(
        self,
        finish: Any,
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Handle agent finish (end of agent run).

        Args:
            finish: Agent finish object
            run_id: LangChain run ID
            parent_run_id: Parent run ID
            tags: Optional tags
            **kwargs: Additional callback arguments
        """
        # End trace when agent finishes
        if run_id and str(run_id) == self.trace_id:
            self.scanner.end_trace()
            self.trace_id = None

    # ========================================================================
    # Chain Callbacks
    # ========================================================================

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Handle chain start.

        Currently does not perform scanning. Use on_llm_start for prompt scanning.

        Args:
            serialized: Chain serialization info
            inputs: Chain input dictionary
            run_id: LangChain run ID
            parent_run_id: Parent run ID
            tags: Optional tags
            metadata: Optional metadata
            **kwargs: Additional callback arguments
        """
        # Start trace for top-level chain
        if parent_run_id is None and run_id:
            self.trace_id = str(run_id)
            self.scanner.start_trace(self.trace_id)

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Handle chain end.

        Currently does not perform scanning. Use on_llm_end for response scanning.

        Args:
            outputs: Chain output dictionary
            run_id: LangChain run ID
            parent_run_id: Parent run ID
            tags: Optional tags
            **kwargs: Additional callback arguments
        """
        # End trace for top-level chain
        if parent_run_id is None and run_id and str(run_id) == self.trace_id:
            self.scanner.end_trace()
            self.trace_id = None

    def on_chain_error(
        self,
        error: Exception | KeyboardInterrupt,
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """Handle chain errors.

        Args:
            error: Exception that occurred
            run_id: LangChain run ID
            parent_run_id: Parent run ID
            **kwargs: Additional callback arguments
        """
        # End trace on error
        if run_id and str(run_id) == self.trace_id:
            self.scanner.end_trace()
            self.trace_id = None

    # ========================================================================
    # Retriever Callbacks (LangChain 0.1+)
    # ========================================================================

    def on_retriever_start(
        self,
        serialized: dict[str, Any],
        query: str,
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Scan retriever queries.

        Args:
            serialized: Retriever serialization info
            query: Query string
            run_id: LangChain run ID
            parent_run_id: Parent run ID
            tags: Optional tags
            metadata: Optional metadata
            **kwargs: Additional arguments
        """
        if not query or not query.strip():
            return

        try:
            result = self.scanner.scan_prompt(
                query,
                metadata={
                    "source": "retriever",
                    **(metadata or {}),
                },
            )

            if result.has_threats:
                logger.warning(
                    f"Threat detected in retriever query: {result.severity} severity"
                )

        except SecurityException:
            logger.error("Blocked retriever query due to security threat")
            raise

    def on_retriever_end(
        self,
        documents: list[Any],
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Handle retriever results.

        Currently does not scan retrieved documents. Consider adding
        document scanning for high-security environments.

        Args:
            documents: Retrieved documents
            run_id: LangChain run ID
            parent_run_id: Parent run ID
            tags: Optional tags
            **kwargs: Additional arguments
        """
        pass  # Retrieved documents not scanned by default

    def on_retriever_error(
        self,
        error: Exception | KeyboardInterrupt,
        *,
        run_id: Any | None = None,
        parent_run_id: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """Handle retriever errors.

        Args:
            error: Exception that occurred
            run_id: LangChain run ID
            parent_run_id: Parent run ID
            **kwargs: Additional arguments
        """
        pass  # Don't interfere with error handling

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _extract_response_texts(self, response: Any) -> list[str]:
        """Extract text strings from LangChain response object.

        Handles various response formats across LangChain versions.

        Args:
            response: LLM response object (format varies by LangChain version)

        Returns:
            List of text strings to scan
        """
        texts: list[str] = []

        # Handle LLMResult object (generations attribute)
        if hasattr(response, "generations"):
            for generation_list in response.generations:
                for generation in generation_list:
                    if hasattr(generation, "text"):
                        texts.append(generation.text)
                    elif hasattr(generation, "message"):
                        # ChatGeneration has message instead of text
                        content = self._extract_message_content(generation.message)
                        if content:
                            texts.append(content)
                    elif isinstance(generation, dict) and "text" in generation:
                        texts.append(generation["text"])

        # Handle ChatResult/AIMessage object (content attribute)
        elif hasattr(response, "content"):
            if isinstance(response.content, str):
                texts.append(response.content)
            elif isinstance(response.content, list):
                # Handle structured content (text + tool calls)
                for item in response.content:
                    if isinstance(item, str):
                        texts.append(item)
                    elif isinstance(item, dict) and "text" in item:
                        texts.append(item["text"])

        # Handle dict response
        elif isinstance(response, dict):
            if "text" in response:
                texts.append(response["text"])
            elif "content" in response:
                texts.append(response["content"])
            elif "output" in response:
                texts.append(response["output"])

        # Handle string response
        elif isinstance(response, str):
            texts.append(response)

        return [text for text in texts if text and text.strip()]

    def _extract_message_content(self, message: Any) -> str | None:
        """Extract text content from a chat message.

        Args:
            message: Chat message object

        Returns:
            Text content or None
        """
        # Handle BaseMessage subclasses
        if hasattr(message, "content"):
            content = message.content
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Structured content
                text_parts = []
                for item in content:
                    if isinstance(item, str):
                        text_parts.append(item)
                    elif isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                return " ".join(text_parts) if text_parts else None

        # Handle dict format
        elif isinstance(message, dict):
            if "content" in message:
                return message["content"]
            elif "text" in message:
                return message["text"]

        # Handle tuple format (role, content)
        elif isinstance(message, tuple) and len(message) >= 2:
            return str(message[1])

        return None

    def _get_message_type(self, message: Any) -> str:
        """Get the type of a chat message.

        Args:
            message: Chat message object

        Returns:
            Message type string
        """
        # Get type from class name
        if hasattr(message, "__class__"):
            class_name = message.__class__.__name__
            if "Human" in class_name or "User" in class_name:
                return "human"
            elif "AI" in class_name or "Assistant" in class_name:
                return "ai"
            elif "System" in class_name:
                return "system"
            elif "Tool" in class_name:
                return "tool"

        # Get type from attribute
        if hasattr(message, "type"):
            return str(message.type)

        # Get type from dict
        if isinstance(message, dict) and "role" in message:
            return message["role"]

        return "unknown"

    def __repr__(self) -> str:
        """String representation of callback handler.

        Returns:
            Human-readable string
        """
        return (
            f"RaxeCallbackHandler("
            f"block_prompts={self.block_on_prompt_threats}, "
            f"block_responses={self.block_on_response_threats}, "
            f"scan_tools={self.scan_tools})"
        )


# ============================================================================
# Convenience Functions
# ============================================================================

def create_callback_handler(
    *,
    block_prompts: bool = False,
    block_responses: bool = False,
    tool_policy: ToolPolicy | None = None,
    on_threat: Any | None = None,
) -> RaxeCallbackHandler:
    """Create a RAXE callback handler with common configuration.

    Args:
        block_prompts: Block on prompt threats (default: False)
        block_responses: Block on response threats (default: False)
        tool_policy: Policy for tool validation
        on_threat: Optional callback for threat notifications

    Returns:
        Configured RaxeCallbackHandler

    Example:
        # Monitoring mode (log only)
        handler = create_callback_handler()

        # Blocking mode for prompts
        handler = create_callback_handler(block_prompts=True)

        # With tool restrictions
        handler = create_callback_handler(
            tool_policy=ToolPolicy.block_tools("shell")
        )
    """
    return RaxeCallbackHandler(
        block_on_prompt_threats=block_prompts,
        block_on_response_threats=block_responses,
        tool_policy=tool_policy,
        on_threat=on_threat,
    )


def get_langchain_version() -> str:
    """Get the installed LangChain version string.

    Returns:
        Version string (e.g., "0.2.5") or "not installed"
    """
    version = _detect_langchain_version()
    if version == (0, 0, 0):
        return "not installed"
    return f"{version[0]}.{version[1]}.{version[2]}"
