"""LlamaIndex integration for RAXE scanning.

Provides callback handlers and instrumentation for automatic RAXE scanning
in LlamaIndex applications. Supports both the legacy callback system and
the new instrumentation API (v0.10.20+).

This integration works with:
    - Query engines (VectorStoreIndex, etc.)
    - ReAct agents and function-calling agents
    - Tool execution
    - RAG pipelines (retrieval, synthesis)
    - LLM calls and embeddings

Usage (Callback Handler - v0.10+):
    from llama_index.core import VectorStoreIndex, Settings
    from llama_index.core.callbacks import CallbackManager
    from raxe.sdk.integrations import RaxeLlamaIndexCallback

    # Create callback handler
    raxe_callback = RaxeLlamaIndexCallback()

    # Add to callback manager
    callback_manager = CallbackManager([raxe_callback])
    Settings.callback_manager = callback_manager

    # All queries automatically scanned
    index = VectorStoreIndex.from_documents(documents)
    response = index.as_query_engine().query("What is AI?")

Usage (Instrumentation - v0.10.20+):
    from llama_index.core.instrumentation import get_dispatcher
    from raxe.sdk.integrations import RaxeSpanHandler

    # Create and register span handler
    span_handler = RaxeSpanHandler()
    root_dispatcher = get_dispatcher()
    root_dispatcher.add_span_handler(span_handler)

    # All operations automatically traced and scanned
    response = index.as_query_engine().query("What is AI?")
"""
from __future__ import annotations

import logging
from typing import Any

from raxe.sdk.client import Raxe
from raxe.sdk.exceptions import SecurityException
from raxe.sdk.integrations.extractors import (
    extract_text_from_message,
    extract_text_from_response,
    extract_texts_from_value,
)

logger = logging.getLogger(__name__)


# ============================================================================
# CBEventType Enum Values (from llama_index.core.callbacks.schema)
# ============================================================================
# These are the event types we care about for security scanning:
#
# QUERY       - Query start/end events
# LLM         - LLM call events (prompts and responses)
# EMBEDDING   - Embedding events
# RETRIEVE    - Retrieval events (RAG context)
# SYNTHESIZE  - Response synthesis events
# AGENT_STEP  - Agent step events
# FUNCTION_CALL - Function/tool call events
# CHUNKING    - Document chunking events
# TEMPLATING  - Template processing events
# RERANKING   - Reranking events
# ============================================================================


def _get_base_callback_handler():
    """Get BaseCallbackHandler class from llama_index."""
    try:
        from llama_index.core.callbacks.base import BaseCallbackHandler
        return BaseCallbackHandler
    except ImportError:
        # Return object as fallback if llama_index not installed
        return object


# Dynamically inherit from BaseCallbackHandler
_LlamaIndexBaseHandler = _get_base_callback_handler()


class RaxeLlamaIndexCallback(_LlamaIndexBaseHandler):
    """LlamaIndex callback handler for automatic RAXE scanning.

    This callback handler integrates with LlamaIndex's CallbackManager system
    to automatically scan prompts, queries, and responses for security threats.

    The handler intercepts events at key points in the LlamaIndex pipeline:
        1. QUERY events - Scan user queries before processing
        2. LLM events - Scan prompts before LLM calls
        3. RETRIEVE events - Monitor retrieved context (future)
        4. SYNTHESIZE events - Scan synthesized responses
        5. Agent events - Scan agent actions and tool inputs

    The handler supports both blocking and monitoring modes:
        - Blocking mode: Raises SecurityException on threat detection
        - Monitoring mode: Logs threats but allows execution

    Attributes:
        raxe: Raxe client instance for scanning
        block_on_query_threats: Block if query contains threats
        block_on_response_threats: Block if response contains threats
        scan_retrieved_context: Scan retrieved RAG context (future)
        scan_agent_actions: Scan agent tool inputs

    Example:
        >>> from llama_index.core import VectorStoreIndex, Settings
        >>> from llama_index.core.callbacks import CallbackManager
        >>> from raxe.sdk.integrations import RaxeLlamaIndexCallback
        >>>
        >>> # Blocking mode (default)
        >>> raxe_callback = RaxeLlamaIndexCallback()
        >>> Settings.callback_manager = CallbackManager([raxe_callback])
        >>>
        >>> # Monitoring mode
        >>> raxe_callback = RaxeLlamaIndexCallback(block_on_query_threats=False)
        >>>
        >>> # Custom Raxe client
        >>> raxe = Raxe(telemetry=False)
        >>> raxe_callback = RaxeLlamaIndexCallback(raxe_client=raxe)
    """

    def __init__(
        self,
        raxe_client: Raxe | None = None,
        *,
        block_on_query_threats: bool = False,
        block_on_response_threats: bool = False,
        scan_retrieved_context: bool = False,
        scan_agent_actions: bool = True,
    ) -> None:
        """Initialize RAXE callback handler for LlamaIndex.

        Args:
            raxe_client: Optional Raxe instance (creates default if None)
            block_on_query_threats: Block on query/prompt threats (default: False)
                NOTE: Default is False (log-only mode) per requirements
            block_on_response_threats: Block on response threats (default: False)
            scan_retrieved_context: Scan retrieved RAG context (default: False)
                NOTE: Placeholder for future RAG context validation
            scan_agent_actions: Scan agent tool inputs (default: True)

        Example:
            # Log-only mode (default)
            callback = RaxeLlamaIndexCallback()

            # Blocking mode for queries
            callback = RaxeLlamaIndexCallback(block_on_query_threats=True)

            # With custom Raxe client
            raxe = Raxe(api_key="raxe_...", telemetry=True)
            callback = RaxeLlamaIndexCallback(raxe_client=raxe)
        """
        # Initialize base class if it's a real LlamaIndex handler
        if _LlamaIndexBaseHandler is not object:
            # Pass empty ignore lists - we want to handle all events
            super().__init__(
                event_starts_to_ignore=[],
                event_ends_to_ignore=[],
            )
        self.raxe = raxe_client or Raxe()
        self.block_on_query_threats = block_on_query_threats
        self.block_on_response_threats = block_on_response_threats
        self.scan_retrieved_context = scan_retrieved_context
        self.scan_agent_actions = scan_agent_actions

        # Track active events for correlation
        self._active_events: dict[str, dict[str, Any]] = {}

        logger.debug(
            "RaxeLlamaIndexCallback initialized: "
            f"block_queries={block_on_query_threats}, "
            f"block_responses={block_on_response_threats}, "
            f"scan_agent_actions={scan_agent_actions}"
        )

    def on_event_start(
        self,
        event_type: Any,
        payload: dict[str, Any] | None = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        """Handle event start - scan inputs before processing.

        This method is called by LlamaIndex's CallbackManager when an event
        starts. We use it to scan queries, prompts, and agent inputs.

        Args:
            event_type: CBEventType enum value
            payload: Event payload with context data
            event_id: Unique event identifier
            parent_id: Parent event identifier
            **kwargs: Additional callback arguments

        Returns:
            Event ID for tracking

        Raises:
            SecurityException: If threat detected and blocking enabled
        """
        payload = payload or {}

        # Store event context for correlation
        self._active_events[event_id] = {
            "event_type": event_type,
            "parent_id": parent_id,
        }

        # Get event type name for comparison
        event_name = self._get_event_type_name(event_type)

        # Handle QUERY events - scan user query
        if event_name == "QUERY":
            query_str = payload.get("query_str") or payload.get("QUERY_STR", "")
            if query_str:
                self._scan_text(
                    text=query_str,
                    context="query",
                    block=self.block_on_query_threats,
                )

        # Handle LLM events - scan prompts
        elif event_name == "LLM":
            # Scan messages if present
            messages = payload.get("messages", [])
            for msg in messages:
                content = self._extract_message_content(msg)
                if content:
                    self._scan_text(
                        text=content,
                        context="llm_prompt",
                        block=self.block_on_query_threats,
                    )

            # Scan template if present
            template = payload.get("template", "")
            if template and "{" not in template:  # Skip templates with placeholders
                self._scan_text(
                    text=template,
                    context="llm_template",
                    block=self.block_on_query_threats,
                )

        # Handle AGENT_STEP events - scan agent inputs
        elif event_name == "AGENT_STEP" and self.scan_agent_actions:
            task_str = payload.get("task_str", "")
            if task_str:
                self._scan_text(
                    text=task_str,
                    context="agent_input",
                    block=self.block_on_query_threats,
                )

        # Handle FUNCTION_CALL events - scan tool inputs
        elif event_name == "FUNCTION_CALL" and self.scan_agent_actions:
            tool_input = payload.get("tool_input", "")
            if isinstance(tool_input, str) and tool_input:
                self._scan_text(
                    text=tool_input,
                    context="tool_input",
                    block=self.block_on_query_threats,
                )

        # Handle RETRIEVE events - future context validation
        elif event_name == "RETRIEVE" and self.scan_retrieved_context:
            # Placeholder for future retrieved context validation
            # This would scan the query before retrieval
            query_str = payload.get("query_str", "")
            if query_str:
                self._scan_text(
                    text=query_str,
                    context="retrieve_query",
                    block=self.block_on_query_threats,
                )

        return event_id

    def on_event_end(
        self,
        event_type: Any,
        payload: dict[str, Any] | None = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        """Handle event end - scan outputs after processing.

        This method is called by LlamaIndex's CallbackManager when an event
        ends. We use it to scan responses and synthesized content.

        Args:
            event_type: CBEventType enum value
            payload: Event payload with response data
            event_id: Event identifier
            **kwargs: Additional callback arguments

        Raises:
            SecurityException: If threat detected and blocking enabled
        """
        payload = payload or {}

        # Get event type name for comparison
        event_name = self._get_event_type_name(event_type)

        # Handle LLM events - scan responses
        if event_name == "LLM":
            response = payload.get("response", "")
            if response:
                response_text = self._extract_response_text(response)
                if response_text:
                    self._scan_text(
                        text=response_text,
                        context="llm_response",
                        block=self.block_on_response_threats,
                    )

        # Handle SYNTHESIZE events - scan synthesized responses
        elif event_name == "SYNTHESIZE":
            response = payload.get("response", "")
            if response:
                response_text = self._extract_response_text(response)
                if response_text:
                    self._scan_text(
                        text=response_text,
                        context="synthesized_response",
                        block=self.block_on_response_threats,
                    )

        # Handle QUERY events - scan final query response
        elif event_name == "QUERY":
            response = payload.get("response", "")
            if response:
                response_text = self._extract_response_text(response)
                if response_text:
                    self._scan_text(
                        text=response_text,
                        context="query_response",
                        block=self.block_on_response_threats,
                    )

        # Handle RETRIEVE events - future context validation
        elif event_name == "RETRIEVE" and self.scan_retrieved_context:
            # Placeholder for scanning retrieved nodes
            # This would scan the actual retrieved context for threats
            nodes = payload.get("nodes", [])
            for node in nodes:
                if hasattr(node, "text"):
                    self._scan_text(
                        text=node.text,
                        context="retrieved_context",
                        block=False,  # Never block on retrieved context
                    )

        # Handle FUNCTION_CALL events - scan tool outputs
        elif event_name == "FUNCTION_CALL" and self.scan_agent_actions:
            output = payload.get("output", "")
            if isinstance(output, str) and output:
                self._scan_text(
                    text=output,
                    context="tool_output",
                    block=self.block_on_response_threats,
                )

        # Cleanup event tracking
        self._active_events.pop(event_id, None)

    def start_trace(self, trace_id: str | None = None) -> None:
        """Called when a trace starts.

        Args:
            trace_id: Optional trace identifier
        """
        # Optional: Could track trace-level metadata
        pass

    def end_trace(
        self,
        trace_id: str | None = None,
        trace_map: dict[str, list[str]] | None = None,
    ) -> None:
        """Called when a trace ends.

        Args:
            trace_id: Optional trace identifier
            trace_map: Mapping of event IDs to child event IDs
        """
        # Cleanup any remaining event state
        self._active_events.clear()

    def _scan_text(
        self,
        text: str,
        context: str,
        block: bool,
    ) -> None:
        """Scan text for security threats.

        Args:
            text: Text to scan
            context: Context description for logging
            block: Whether to raise exception on threat

        Raises:
            SecurityException: If threat detected and block=True
        """
        if not text or not text.strip():
            return

        try:
            result = self.raxe.scan(
                text,
                block_on_threat=block,
            )

            if result.has_threats:
                logger.warning(
                    f"Threat detected in LlamaIndex {context}: "
                    f"{result.severity} severity (block={block})"
                )

        except SecurityException:
            logger.error(
                f"Blocked LlamaIndex {context} due to security threat"
            )
            raise

    def _get_event_type_name(self, event_type: Any) -> str:
        """Extract event type name from CBEventType enum.

        Args:
            event_type: CBEventType enum value or string

        Returns:
            Event type name as string
        """
        if isinstance(event_type, str):
            return event_type.upper()

        # Handle enum value
        if hasattr(event_type, "name"):
            return event_type.name.upper()
        if hasattr(event_type, "value"):
            return str(event_type.value).upper()

        return str(event_type).upper()

    def _extract_message_content(self, message: Any) -> str:
        """Extract text content from LlamaIndex message.

        Uses unified extractor from raxe.sdk.integrations.extractors.

        Args:
            message: ChatMessage or dict with content

        Returns:
            Extracted text content
        """
        return extract_text_from_message(message) or ""

    def _extract_response_text(self, response: Any) -> str:
        """Extract text from LlamaIndex response objects.

        Uses unified extractor with LlamaIndex-specific fallbacks.

        Args:
            response: Response object (various formats)

        Returns:
            Extracted response text
        """
        if isinstance(response, str):
            return response

        # Handle LlamaIndex Response object with response attribute
        if hasattr(response, "response"):
            return str(response.response)

        # Try unified extractor for other formats
        text = extract_text_from_response(response)
        if text:
            return text

        # Handle dict response (LlamaIndex-specific keys)
        if isinstance(response, dict):
            return response.get("response", "") or response.get("text", "")

        return ""

    def __repr__(self) -> str:
        """String representation of callback handler.

        Returns:
            Human-readable string
        """
        return (
            f"RaxeLlamaIndexCallback("
            f"block_queries={self.block_on_query_threats}, "
            f"block_responses={self.block_on_response_threats}, "
            f"scan_agent_actions={self.scan_agent_actions})"
        )


class RaxeSpanHandler:
    """LlamaIndex instrumentation span handler for RAXE scanning.

    This handler integrates with LlamaIndex's new instrumentation API
    (v0.10.20+) for more granular observability and scanning.

    The instrumentation API provides:
        - Structured spans with duration and context
        - Event-based tracking within spans
        - Parent-child relationships for tracing
        - OpenTelemetry compatibility

    Usage:
        >>> from llama_index.core.instrumentation import get_dispatcher
        >>> from raxe.sdk.integrations import RaxeSpanHandler
        >>>
        >>> span_handler = RaxeSpanHandler()
        >>> root_dispatcher = get_dispatcher()
        >>> root_dispatcher.add_span_handler(span_handler)

    Note:
        This is designed for LlamaIndex v0.10.20+ which introduced
        the instrumentation module. For earlier versions, use
        RaxeLlamaIndexCallback instead.
    """

    def __init__(
        self,
        raxe_client: Raxe | None = None,
        *,
        block_on_threats: bool = False,
        scan_llm_inputs: bool = True,
        scan_llm_outputs: bool = True,
    ) -> None:
        """Initialize RAXE span handler.

        Args:
            raxe_client: Optional Raxe instance (creates default if None)
            block_on_threats: Block on any threats (default: False)
            scan_llm_inputs: Scan LLM inputs (default: True)
            scan_llm_outputs: Scan LLM outputs (default: True)
        """
        self.raxe = raxe_client or Raxe()
        self.block_on_threats = block_on_threats
        self.scan_llm_inputs = scan_llm_inputs
        self.scan_llm_outputs = scan_llm_outputs

        logger.debug(
            "RaxeSpanHandler initialized: "
            f"block={block_on_threats}, "
            f"scan_inputs={scan_llm_inputs}, "
            f"scan_outputs={scan_llm_outputs}"
        )

    def span_enter(
        self,
        id_: str,
        bound_args: dict[str, Any],
        instance: Any | None = None,
        parent_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when entering a span.

        Args:
            id_: Span identifier
            bound_args: Arguments bound to the function
            instance: Instance the method is bound to
            parent_id: Parent span identifier
            **kwargs: Additional span data
        """
        if not self.scan_llm_inputs:
            return

        # Scan any string arguments
        for key, value in bound_args.items():
            if key in ("query", "prompt", "messages", "input"):
                self._scan_value(value, f"span_input_{key}")

    def span_exit(
        self,
        id_: str,
        bound_args: dict[str, Any],
        instance: Any | None = None,
        result: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when exiting a span.

        Args:
            id_: Span identifier
            bound_args: Arguments bound to the function
            instance: Instance the method is bound to
            result: Result of the function
            **kwargs: Additional span data
        """
        if not self.scan_llm_outputs:
            return

        if result is not None:
            self._scan_value(result, "span_output")

    def span_drop(
        self,
        id_: str,
        bound_args: dict[str, Any],
        instance: Any | None = None,
        err: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when a span is dropped (error occurred).

        Args:
            id_: Span identifier
            bound_args: Arguments bound to the function
            instance: Instance the method is bound to
            err: Exception that caused the drop
            **kwargs: Additional span data
        """
        # Don't interfere with error handling
        pass

    def _scan_value(self, value: Any, context: str) -> None:
        """Scan a value for security threats.

        Args:
            value: Value to scan (string, list, or object with text)
            context: Context description for logging
        """
        texts = self._extract_texts(value)

        for text in texts:
            if text and text.strip():
                try:
                    result = self.raxe.scan(
                        text,
                        block_on_threat=self.block_on_threats,
                    )

                    if result.has_threats:
                        logger.warning(
                            f"Threat detected in LlamaIndex {context}: "
                            f"{result.severity} severity"
                        )

                except SecurityException:
                    logger.error(
                        f"Blocked LlamaIndex {context} due to security threat"
                    )
                    raise

    def _extract_texts(self, value: Any) -> list[str]:
        """Extract text strings from various value types.

        Uses unified extractor from raxe.sdk.integrations.extractors.

        Args:
            value: Value to extract text from

        Returns:
            List of text strings
        """
        return extract_texts_from_value(value)

    def __repr__(self) -> str:
        """String representation of span handler."""
        return (
            f"RaxeSpanHandler("
            f"block={self.block_on_threats}, "
            f"scan_inputs={self.scan_llm_inputs}, "
            f"scan_outputs={self.scan_llm_outputs})"
        )


class RaxeQueryEngineCallback(RaxeLlamaIndexCallback):
    """Specialized callback handler for Query Engine use cases.

    This is a convenience subclass of RaxeLlamaIndexCallback that is
    optimized for query engine and RAG pipeline use cases.

    Key features:
        - Focused on QUERY, RETRIEVE, and SYNTHESIZE events
        - Simplified configuration for RAG pipelines
        - Default log-only mode for non-intrusive integration

    Example:
        >>> from llama_index.core import VectorStoreIndex, Settings
        >>> from llama_index.core.callbacks import CallbackManager
        >>> from raxe.sdk.integrations import RaxeQueryEngineCallback
        >>>
        >>> # Create and configure
        >>> callback = RaxeQueryEngineCallback()
        >>> Settings.callback_manager = CallbackManager([callback])
        >>>
        >>> # Query with automatic scanning
        >>> index = VectorStoreIndex.from_documents(documents)
        >>> engine = index.as_query_engine()
        >>> response = engine.query("What is the summary?")
    """

    def __init__(
        self,
        raxe_client: Raxe | None = None,
        *,
        block_on_threats: bool = False,
    ) -> None:
        """Initialize Query Engine callback.

        Args:
            raxe_client: Optional Raxe instance
            block_on_threats: Block on any threats (default: False)
        """
        super().__init__(
            raxe_client=raxe_client,
            block_on_query_threats=block_on_threats,
            block_on_response_threats=block_on_threats,
            scan_retrieved_context=False,  # Future feature
            scan_agent_actions=False,  # Not needed for query engines
        )


class RaxeAgentCallback(RaxeLlamaIndexCallback):
    """Specialized callback handler for Agent use cases.

    This is a convenience subclass of RaxeLlamaIndexCallback that is
    optimized for LlamaIndex agents (ReActAgent, FunctionCallingAgent, etc.).

    Key features:
        - Focused on AGENT_STEP and FUNCTION_CALL events
        - Scans tool inputs and outputs
        - Default log-only mode for non-intrusive integration

    Example:
        >>> from llama_index.core.agent import ReActAgent
        >>> from llama_index.core.callbacks import CallbackManager
        >>> from raxe.sdk.integrations import RaxeAgentCallback
        >>>
        >>> # Create and configure
        >>> callback = RaxeAgentCallback()
        >>> callback_manager = CallbackManager([callback])
        >>>
        >>> # Create agent with scanning
        >>> agent = ReActAgent.from_tools(
        ...     tools=[...],
        ...     callback_manager=callback_manager,
        ...     verbose=True,
        ... )
        >>> response = agent.chat("Calculate 2+2")
    """

    def __init__(
        self,
        raxe_client: Raxe | None = None,
        *,
        block_on_threats: bool = False,
        scan_tool_outputs: bool = True,
    ) -> None:
        """Initialize Agent callback.

        Args:
            raxe_client: Optional Raxe instance
            block_on_threats: Block on any threats (default: False)
            scan_tool_outputs: Scan tool output values (default: True)
        """
        super().__init__(
            raxe_client=raxe_client,
            block_on_query_threats=block_on_threats,
            block_on_response_threats=block_on_threats and scan_tool_outputs,
            scan_retrieved_context=False,
            scan_agent_actions=True,
        )
        self._scan_tool_outputs = scan_tool_outputs
