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
import uuid
from typing import TYPE_CHECKING, Any

from raxe.sdk.agent_scanner import (
    AgentScanner,
    AgentScannerConfig,
    AgentScanResult,
    ScanType,
    ToolPolicy,
    create_agent_scanner,
)
from raxe.sdk.client import Raxe
from raxe.sdk.exceptions import SecurityException
from raxe.sdk.integrations.extractors import (
    extract_text_from_message,
    extract_text_from_response,
)

if TYPE_CHECKING:
    pass

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
    """Check if langchain-core is available."""
    try:
        import langchain_core  # noqa: F401

        return True
    except ImportError:
        return False


def _has_run_manager() -> bool:
    """Check if RunManager is available (0.1+)."""
    try:
        from langchain_core.callbacks.manager import RunManager  # noqa: F401

        return True
    except ImportError:
        return False


def _get_base_callback_handler_class():
    """Get BaseCallbackHandler class from langchain.

    This function is called at class instantiation time, not import time,
    ensuring proper inheritance even if langchain is installed later.

    Returns:
        BaseCallbackHandler class or object as fallback
    """
    try:
        from langchain_core.callbacks import BaseCallbackHandler

        return BaseCallbackHandler
    except ImportError:
        try:
            from langchain.callbacks.base import BaseCallbackHandler

            return BaseCallbackHandler
        except ImportError:
            return object


# ============================================================================
# Base Callback Handler Implementation
# ============================================================================


class _RaxeCallbackHandlerMixin:
    """Mixin containing RAXE callback handler logic.

    This mixin provides all the RAXE scanning functionality and is combined
    with the appropriate LangChain base class at runtime.
    """

    # Class-level version info (computed once)
    _langchain_version: tuple[int, int, int] | None = None

    def __init__(
        self,
        raxe_client: Raxe | None = None,
        *,
        scanner: AgentScanner | None = None,
        tool_policy: ToolPolicy | None = None,
        block_on_prompt_threats: bool = False,
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
        """
        # Store configuration
        self.block_on_prompt_threats = block_on_prompt_threats
        self.block_on_response_threats = block_on_response_threats
        self.scan_tools = scan_tools
        self.scan_agent_actions = scan_agent_actions
        self.on_threat = on_threat

        # Create or use provided Raxe client
        self._raxe = raxe_client or Raxe()

        # Create or use provided scanner with config
        if scanner is not None:
            self._scanner = scanner
        else:
            # Use AgentScannerConfig for proper initialization
            config = AgentScannerConfig(
                scan_prompts=True,
                scan_responses=True,
                scan_tool_calls=scan_tools,
                # Default to log-only mode for safety
                on_threat="block" if block_on_prompt_threats else "log",
            )
            self._scanner = create_agent_scanner(self._raxe, config, integration_type="langchain")

        # Trace ID for correlation (set on each chain/agent run)
        self.trace_id: str | None = None

        # Cache version info
        if _RaxeCallbackHandlerMixin._langchain_version is None:
            _RaxeCallbackHandlerMixin._langchain_version = _detect_langchain_version()

        logger.debug(
            "RaxeCallbackHandler initialized",
            extra={
                "langchain_version": self._langchain_version,
                "block_on_prompt_threats": block_on_prompt_threats,
                "block_on_response_threats": block_on_response_threats,
            },
        )

    # ========================================================================
    # LLM Callbacks - Core Scanning Points
    # ========================================================================

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Scan prompts before sending to LLM.

        This is the primary injection point for prompt scanning.
        Called before each LLM invocation with the prompts.
        """
        for prompt in prompts:
            result = self._scanner.scan(prompt, scan_type=ScanType.PROMPT)

            if result.has_threats:
                self._handle_threat(result, "prompt", prompt[:100])

                if self.block_on_prompt_threats:
                    raise SecurityException(result.pipeline_result)

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Scan LLM response for threats.

        Scans the generated response for potential data exfiltration,
        harmful content, or policy violations.
        """
        # Extract text from LLM response
        text = self._extract_llm_response_text(response)
        if not text:
            return

        result = self._scanner.scan(text, scan_type=ScanType.RESPONSE)

        if result.has_threats:
            self._handle_threat(result, "response", text[:100])

            if self.block_on_response_threats:
                raise SecurityException(result.pipeline_result)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Handle LLM errors."""
        logger.debug(
            "LLM error occurred",
            extra={"error": str(error), "trace_id": self.trace_id},
        )

    # ========================================================================
    # Chat Model Callbacks
    # ========================================================================

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Scan chat messages before sending to model.

        Handles ChatModel message format (list of messages).
        """
        for message_batch in messages:
            for message in message_batch:
                text = self._extract_message_text(message)
                if text:
                    result = self._scanner.scan(text, scan_type=ScanType.PROMPT)

                    if result.has_threats:
                        self._handle_threat(result, "chat_message", text[:100])

                        if self.block_on_prompt_threats:
                            raise SecurityException(result.pipeline_result)

    # ========================================================================
    # Tool Callbacks
    # ========================================================================

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Scan tool input before execution.

        Validates tool calls against policy and scans inputs.
        """
        if not self.scan_tools:
            return

        tool_name = serialized.get("name", "unknown")

        # Scan tool input
        result = self._scanner.scan_tool_call(
            tool_name=tool_name,
            tool_args=input_str,
        )

        if result.has_threats:
            self._handle_threat(result, f"tool:{tool_name}", input_str[:100])

            if self.block_on_prompt_threats:
                raise SecurityException(result.pipeline_result)

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Scan tool output."""
        if not self.scan_tools:
            return

        text = str(output) if output else ""
        if not text:
            return

        result = self._scanner.scan(text, scan_type=ScanType.TOOL_RESULT)

        if result.has_threats:
            self._handle_threat(result, "tool_output", text[:100])

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Handle tool errors."""
        logger.debug(
            "Tool error occurred",
            extra={"error": str(error), "trace_id": self.trace_id},
        )

    # ========================================================================
    # Agent Callbacks
    # ========================================================================

    def on_agent_action(
        self,
        action: Any,
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Scan agent action before execution."""
        if not self.scan_agent_actions:
            return

        # Extract action details
        tool_name = getattr(action, "tool", "unknown")
        tool_input = getattr(action, "tool_input", "")

        if isinstance(tool_input, dict):
            tool_input = str(tool_input)

        result = self._scanner.scan_tool_call(
            tool_name=tool_name,
            tool_args=tool_input,
        )

        if result.has_threats:
            self._handle_threat(result, f"agent_action:{tool_name}", tool_input[:100])

            if self.block_on_prompt_threats:
                raise SecurityException(result.pipeline_result)

    def on_agent_finish(
        self,
        finish: Any,
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Scan agent final output."""
        output = getattr(finish, "return_values", {})
        text = output.get("output", "") if isinstance(output, dict) else str(output)

        if text:
            result = self._scanner.scan(text, scan_type=ScanType.RESPONSE)

            if result.has_threats:
                self._handle_threat(result, "agent_finish", text[:100])

    # ========================================================================
    # Chain Callbacks
    # ========================================================================

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Track chain start for correlation."""
        # Set trace ID for correlation
        self.trace_id = str(run_id) if run_id else str(uuid.uuid4())

        logger.debug(
            "Chain started",
            extra={
                "chain_type": serialized.get("_type", "unknown"),
                "trace_id": self.trace_id,
            },
        )

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Track chain completion."""
        logger.debug(
            "Chain completed",
            extra={"trace_id": self.trace_id},
        )

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Handle chain errors."""
        logger.debug(
            "Chain error occurred",
            extra={"error": str(error), "trace_id": self.trace_id},
        )

    # ========================================================================
    # Retriever Callbacks (RAG)
    # ========================================================================

    def on_retriever_start(
        self,
        serialized: dict[str, Any],
        query: str,
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Scan retriever query."""
        result = self._scanner.scan(query, scan_type=ScanType.PROMPT)

        if result.has_threats:
            self._handle_threat(result, "retriever_query", query[:100])

            if self.block_on_prompt_threats:
                raise SecurityException(result.pipeline_result)

    def on_retriever_end(
        self,
        documents: list[Any],
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Scan retrieved documents for RAG poisoning attacks (ASI06)."""
        # Extract and scan document content for potential poisoning
        for i, doc in enumerate(documents):
            text = None
            if hasattr(doc, "page_content"):
                text = doc.page_content
            elif isinstance(doc, str):
                text = doc
            elif isinstance(doc, dict):
                text = doc.get("page_content") or doc.get("content") or doc.get("text")

            if text:
                result = self._scanner.scan_memory_read(
                    key=f"rag_doc_{i}",
                    value=text,
                    metadata={"document_index": i, "trace_id": self.trace_id},
                )
                if result.has_threats:
                    self._handle_threat(result, f"rag_document:{i}", text[:100])

    def on_retriever_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Handle retriever errors."""
        logger.debug(
            "Retriever error occurred",
            extra={"error": str(error), "trace_id": self.trace_id},
        )

    # ========================================================================
    # Text Callbacks
    # ========================================================================

    def on_text(
        self,
        text: str,
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Handle arbitrary text events."""
        pass  # Usually just logging, not security relevant

    # ========================================================================
    # Memory Scanning Methods (ASI06 - Memory Poisoning)
    # ========================================================================

    def scan_memory_before_save(
        self,
        memory_key: str,
        content: str,
    ) -> AgentScanResult:
        """Scan content before saving to LangChain memory.

        Call this method before ConversationBufferMemory.save_context()
        or similar memory operations to detect memory poisoning attempts.

        Args:
            memory_key: Key/identifier for the memory slot
            content: Content being saved to memory

        Returns:
            AgentScanResult with scan results

        Example:
            from langchain.memory import ConversationBufferMemory

            class SafeMemory(ConversationBufferMemory):
                def __init__(self, raxe_handler):
                    super().__init__()
                    self.raxe_handler = raxe_handler

                def save_context(self, inputs, outputs):
                    # Scan before saving
                    for key, value in outputs.items():
                        result = self.raxe_handler.scan_memory_before_save(key, str(value))
                        if result.has_threats:
                            raise ValueError(f"Memory poisoning detected: {result.severity}")
                    super().save_context(inputs, outputs)
        """
        return self._scanner.scan_memory_write(
            key=memory_key,
            value=content,
            metadata={"trace_id": self.trace_id},
        )

    def scan_memory_after_load(
        self,
        memory_key: str,
        content: str,
    ) -> AgentScanResult:
        """Scan content after loading from LangChain memory.

        Call this method after memory.load_memory_variables() to detect
        poisoned content that may have been previously injected.

        Args:
            memory_key: Key/identifier for the memory slot
            content: Content loaded from memory

        Returns:
            AgentScanResult with scan results
        """
        return self._scanner.scan_memory_read(
            key=memory_key,
            value=content,
            metadata={"trace_id": self.trace_id},
        )

    def validate_agent_goal_change(
        self,
        old_goal: str,
        new_goal: str,
    ) -> bool:
        """Validate a goal change in LangChain agents (ASI01).

        Call this when an agent's objective/goal changes to detect
        goal hijacking attacks.

        Args:
            old_goal: The agent's original goal
            new_goal: The proposed new goal

        Returns:
            True if the goal change is safe, False if suspicious

        Example:
            if not handler.validate_agent_goal_change(original_task, new_task):
                raise ValueError("Goal hijack detected!")
        """
        result = self._scanner.validate_goal_change(
            old_goal=old_goal,
            new_goal=new_goal,
            metadata={"trace_id": self.trace_id},
        )
        return not result.is_suspicious

    def validate_tool_chain(
        self,
        tool_sequence: list[tuple[str, dict]],
    ) -> bool:
        """Validate a sequence of tool calls for dangerous patterns (ASI02).

        Call this before executing a chain of tools to detect dangerous
        combinations like read+exfiltrate patterns.

        Args:
            tool_sequence: List of (tool_name, arguments) tuples

        Returns:
            True if the tool chain is safe, False if dangerous
        """
        result = self._scanner.validate_tool_chain(
            tool_sequence=tool_sequence,
            metadata={"trace_id": self.trace_id},
        )
        return not result.is_dangerous

    def scan_agent_handoff(
        self,
        sender_agent: str,
        receiver_agent: str,
        message: str,
    ) -> AgentScanResult:
        """Scan inter-agent communication for injection attacks (ASI07).

        Call this when agents communicate in multi-agent systems.

        Args:
            sender_agent: Name of the sending agent
            receiver_agent: Name of the receiving agent
            message: Message being transferred

        Returns:
            AgentScanResult with scan results
        """
        return self._scanner.scan_agent_handoff(
            sender=sender_agent,
            receiver=receiver_agent,
            message=message,
            metadata={"trace_id": self.trace_id},
        )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _handle_threat(
        self,
        result: AgentScanResult,
        context: str,
        text_preview: str,
    ) -> None:
        """Handle detected threat.

        Args:
            result: Scan result with threat details
            context: Context description (e.g., "prompt", "response")
            text_preview: Preview of scanned text for logging
        """
        logger.warning(
            "Security threat detected",
            extra={
                "context": context,
                "severity": str(result.severity),
                "detection_count": result.detection_count,
                "trace_id": self.trace_id,
                # Don't log actual text content for privacy
            },
        )

        # Call user-provided callback if set
        if self.on_threat:
            try:
                self.on_threat(result, context)
            except Exception as e:
                logger.error(f"Error in on_threat callback: {e}")

    def _extract_llm_response_text(self, response: Any) -> str | None:
        """Extract text from LLM response object.

        Uses unified extractor from raxe.sdk.integrations.extractors.
        """
        return extract_text_from_response(response)

    def _extract_message_text(self, message: Any) -> str | None:
        """Extract text from a chat message.

        Uses unified extractor from raxe.sdk.integrations.extractors.
        """
        return extract_text_from_message(message)

    # ========================================================================
    # Async Callback Methods
    # ========================================================================
    # LangChain supports async callbacks. These methods use the scanner's
    # async methods for non-blocking operation in async contexts.

    async def aon_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Async version of on_llm_start - scan prompts before LLM."""
        import asyncio

        for prompt in prompts:
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda p=prompt: self._scanner.scan(p, scan_type=ScanType.PROMPT)
            )

            if result.has_threats:
                self._handle_threat(result, "prompt", prompt[:100])

                if self.block_on_prompt_threats:
                    raise SecurityException(result.pipeline_result)

    async def aon_llm_end(
        self,
        response: Any,
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Async version of on_llm_end - scan LLM response."""
        import asyncio

        text = self._extract_llm_response_text(response)
        if not text:
            return

        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._scanner.scan(text, scan_type=ScanType.RESPONSE)
        )

        if result.has_threats:
            self._handle_threat(result, "response", text[:100])

            if self.block_on_response_threats:
                raise SecurityException(result.pipeline_result)

    async def aon_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Async version of on_chat_model_start - scan chat messages."""
        import asyncio

        for message_batch in messages:
            for message in message_batch:
                text = self._extract_message_text(message)
                if text:
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda t=text: self._scanner.scan(t, scan_type=ScanType.PROMPT)
                    )

                    if result.has_threats:
                        self._handle_threat(result, "chat_message", text[:100])

                        if self.block_on_prompt_threats:
                            raise SecurityException(result.pipeline_result)

    async def aon_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Async version of on_tool_start - scan tool input."""
        import asyncio

        if not self.scan_tools:
            return

        tool_name = serialized.get("name", "unknown")

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._scanner.scan_tool_call(tool_name=tool_name, tool_args=input_str),
        )

        if result.has_threats:
            self._handle_threat(result, f"tool:{tool_name}", input_str[:100])

            if self.block_on_prompt_threats:
                raise SecurityException(result.pipeline_result)

    async def aon_tool_end(
        self,
        output: Any,
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Async version of on_tool_end - scan tool output."""
        import asyncio

        if not self.scan_tools:
            return

        text = str(output) if output else ""
        if not text:
            return

        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._scanner.scan(text, scan_type=ScanType.TOOL_RESULT)
        )

        if result.has_threats:
            self._handle_threat(result, "tool_output", text[:100])

    async def aon_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Async version of on_chain_start - track chain start."""
        self.trace_id = str(run_id) if run_id else str(uuid.uuid4())

        logger.debug(
            "Chain started (async)",
            extra={
                "chain_type": serialized.get("_type", "unknown"),
                "trace_id": self.trace_id,
            },
        )

    async def aon_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Async version of on_chain_end - track chain completion."""
        logger.debug(
            "Chain completed (async)",
            extra={"trace_id": self.trace_id},
        )

    async def aon_retriever_start(
        self,
        serialized: dict[str, Any],
        query: str,
        *,
        run_id: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Async version of on_retriever_start - scan retriever query."""
        import asyncio

        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._scanner.scan(query, scan_type=ScanType.PROMPT)
        )

        if result.has_threats:
            self._handle_threat(result, "retriever_query", query[:100])

            if self.block_on_prompt_threats:
                raise SecurityException(result.pipeline_result)


# ============================================================================
# Factory Function for RaxeCallbackHandler
# ============================================================================

_RaxeCallbackHandlerClass: type | None = None


def _create_callback_handler_class() -> type:
    """Create RaxeCallbackHandler class with proper inheritance.

    This is called on first instantiation to ensure LangChain is available.
    """
    global _RaxeCallbackHandlerClass

    if _RaxeCallbackHandlerClass is not None:
        return _RaxeCallbackHandlerClass

    base_class = _get_base_callback_handler_class()

    # Create class dynamically with proper inheritance
    # Put mixin FIRST to ensure its methods take precedence
    if base_class is not object:
        bases = (_RaxeCallbackHandlerMixin, base_class)
    else:
        bases = (_RaxeCallbackHandlerMixin,)

    _RaxeCallbackHandlerClass = type(
        "RaxeCallbackHandler",
        bases,
        {
            "__doc__": _RaxeCallbackHandlerMixin.__doc__,
            "__module__": __name__,
        },
    )

    return _RaxeCallbackHandlerClass


class RaxeCallbackHandler:
    """LangChain callback handler for automatic RAXE scanning.

    This class dynamically inherits from LangChain's BaseCallbackHandler
    when instantiated, ensuring compatibility with LangChain's type checks.
    """

    def __new__(cls, *args, **kwargs):
        """Create instance of dynamically-generated handler class."""
        handler_class = _create_callback_handler_class()
        instance = object.__new__(handler_class)
        # Initialize the instance here since __init__ won't be called
        # on the returned instance (it's a different class)
        _RaxeCallbackHandlerMixin.__init__(instance, *args, **kwargs)
        return instance

    def __init__(
        self,
        raxe_client: Raxe | None = None,
        *,
        scanner: AgentScanner | None = None,
        tool_policy: ToolPolicy | None = None,
        block_on_prompt_threats: bool = False,
        block_on_response_threats: bool = False,
        scan_tools: bool = True,
        scan_agent_actions: bool = True,
        on_threat: Any | None = None,
    ) -> None:
        # This __init__ is never called when __new__ returns a different class
        # The initialization is done in __new__ above
        pass


# ============================================================================
# Convenience Functions
# ============================================================================


def create_callback_handler(
    raxe_client: Raxe | None = None,
    *,
    tool_policy: ToolPolicy | None = None,
    block_on_prompt_threats: bool = False,
    block_on_response_threats: bool = False,
    **kwargs: Any,
) -> RaxeCallbackHandler:
    """Factory function to create RaxeCallbackHandler.

    This is a convenience function that creates a RaxeCallbackHandler
    with the specified configuration.

    Args:
        raxe_client: Optional Raxe instance
        tool_policy: Policy for tool validation
        block_on_prompt_threats: Block on prompt threats
        block_on_response_threats: Block on response threats
        **kwargs: Additional arguments passed to handler

    Returns:
        Configured RaxeCallbackHandler instance
    """
    return RaxeCallbackHandler(
        raxe_client=raxe_client,
        tool_policy=tool_policy,
        block_on_prompt_threats=block_on_prompt_threats,
        block_on_response_threats=block_on_response_threats,
        **kwargs,
    )


def get_langchain_version() -> tuple[int, int, int]:
    """Get the installed LangChain version.

    Returns:
        Tuple of (major, minor, patch) version numbers.
    """
    return _detect_langchain_version()


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "RaxeCallbackHandler",
    "ToolPolicy",
    "create_callback_handler",
    "get_langchain_version",
]
