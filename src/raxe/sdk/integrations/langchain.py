"""LangChain integration for RAXE scanning.

Provides a callback handler that automatically scans prompts and responses
in LangChain applications without modifying existing code.

This integration works with:
    - LLMs, Chat Models
    - Chains (Sequential, Conversational, etc.)
    - Agents and Tools
    - Memory systems

Usage:
    from langchain.llms import OpenAI
    from raxe.sdk.integrations import RaxeCallbackHandler

    # Add callback to automatically scan all LLM interactions
    llm = OpenAI(callbacks=[RaxeCallbackHandler()])

    # All prompts and responses automatically scanned
    result = llm("What is the capital of France?")
"""
import logging
from typing import Any

from raxe.sdk.client import Raxe
from raxe.sdk.exceptions import SecurityException

logger = logging.getLogger(__name__)


class RaxeCallbackHandler:
    """LangChain callback handler for automatic RAXE scanning.

    This callback handler intercepts LangChain events and scans:
        1. All prompts before sending to LLM (on_llm_start)
        2. All LLM responses (on_llm_end)
        3. Tool inputs and outputs (on_tool_start, on_tool_end)
        4. Agent actions (on_agent_action)

    The handler supports both blocking and monitoring modes:
        - Blocking mode: Raises SecurityException on threat detection
        - Monitoring mode: Logs threats but allows execution

    Attributes:
        raxe: Raxe client instance for scanning
        block_on_prompt_threats: Block execution if prompt threat detected
        block_on_response_threats: Block execution if response threat detected
        scan_tools: Whether to scan tool inputs/outputs
        scan_agent_actions: Whether to scan agent actions

    Example:
        >>> from langchain.llms import OpenAI
        >>> from raxe.sdk.integrations import RaxeCallbackHandler
        >>>
        >>> # Blocking mode (default)
        >>> handler = RaxeCallbackHandler()
        >>> llm = OpenAI(callbacks=[handler])
        >>>
        >>> # Monitoring mode
        >>> handler = RaxeCallbackHandler(block_on_prompt_threats=False)
        >>> llm = OpenAI(callbacks=[handler])
        >>>
        >>> # Custom Raxe client
        >>> raxe = Raxe(telemetry=False)
        >>> handler = RaxeCallbackHandler(raxe_client=raxe)
    """

    def __init__(
        self,
        raxe_client: Raxe | None = None,
        *,
        block_on_prompt_threats: bool = True,
        block_on_response_threats: bool = False,
        scan_tools: bool = True,
        scan_agent_actions: bool = True,
    ):
        """Initialize RAXE callback handler.

        Args:
            raxe_client: Optional Raxe instance (creates default if None)
            block_on_prompt_threats: Block on prompt threats (default: True)
            block_on_response_threats: Block on response threats (default: False)
            scan_tools: Scan tool inputs/outputs (default: True)
            scan_agent_actions: Scan agent actions (default: True)

        Example:
            # Default configuration (blocking on prompts)
            handler = RaxeCallbackHandler()

            # Monitoring mode only
            handler = RaxeCallbackHandler(
                block_on_prompt_threats=False,
                block_on_response_threats=False
            )

            # Scan only LLM interactions, skip tools
            handler = RaxeCallbackHandler(scan_tools=False)
        """
        self.raxe = raxe_client or Raxe()
        self.block_on_prompt_threats = block_on_prompt_threats
        self.block_on_response_threats = block_on_response_threats
        self.scan_tools = scan_tools
        self.scan_agent_actions = scan_agent_actions

        logger.debug(
            f"RaxeCallbackHandler initialized: "
            f"block_prompts={block_on_prompt_threats}, "
            f"block_responses={block_on_response_threats}, "
            f"scan_tools={scan_tools}"
        )

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Scan prompts before LLM execution.

        Args:
            serialized: LLM serialization info
            prompts: List of prompts to send to LLM
            **kwargs: Additional callback arguments

        Raises:
            SecurityException: If threat detected and blocking enabled
        """
        for idx, prompt in enumerate(prompts):
            if not prompt:
                continue

            try:
                result = self.raxe.scan(
                    prompt,
                    block_on_threat=self.block_on_prompt_threats,
                )

                if result.has_threats:
                    logger.warning(
                        f"Threat detected in LangChain prompt {idx + 1}/{len(prompts)}: "
                        f"{result.severity} severity "
                        f"(block={self.block_on_prompt_threats})"
                    )

            except SecurityException:
                # Re-raise to stop LangChain execution
                logger.error(
                    f"Blocked LangChain prompt {idx + 1}/{len(prompts)} "
                    f"due to security threat"
                )
                raise

    def on_llm_end(
        self,
        response: Any,
        **kwargs: Any,
    ) -> None:
        """Scan LLM responses after execution.

        Args:
            response: LLM response object
            **kwargs: Additional callback arguments

        Raises:
            SecurityException: If threat detected and blocking enabled
        """
        # Extract text from LangChain response
        texts = self._extract_response_texts(response)

        for idx, text in enumerate(texts):
            if not text:
                continue

            try:
                result = self.raxe.scan(
                    text,
                    block_on_threat=self.block_on_response_threats,
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

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Scan tool inputs before execution.

        Args:
            serialized: Tool serialization info
            input_str: Tool input string
            **kwargs: Additional callback arguments

        Raises:
            SecurityException: If threat detected and blocking enabled
        """
        if not self.scan_tools or not input_str:
            return

        try:
            result = self.raxe.scan(
                input_str,
                block_on_threat=self.block_on_prompt_threats,
            )

            if result.has_threats:
                tool_name = serialized.get("name", "unknown")
                logger.warning(
                    f"Threat detected in tool '{tool_name}' input: "
                    f"{result.severity} severity"
                )

        except SecurityException:
            logger.error("Blocked tool execution due to security threat")
            raise

    def on_tool_end(
        self,
        output: str,
        **kwargs: Any,
    ) -> None:
        """Scan tool outputs after execution.

        Args:
            output: Tool output string
            **kwargs: Additional callback arguments

        Raises:
            SecurityException: If threat detected and blocking enabled
        """
        if not self.scan_tools or not output:
            return

        try:
            result = self.raxe.scan(
                output,
                block_on_threat=self.block_on_response_threats,
            )

            if result.has_threats:
                logger.warning(
                    f"Threat detected in tool output: {result.severity} severity"
                )

        except SecurityException:
            logger.error("Blocked tool output due to security threat")
            raise

    def on_agent_action(
        self,
        action: Any,
        **kwargs: Any,
    ) -> None:
        """Scan agent actions before execution.

        Args:
            action: Agent action object
            **kwargs: Additional callback arguments

        Raises:
            SecurityException: If threat detected and blocking enabled
        """
        if not self.scan_agent_actions:
            return

        # Extract action input
        action_input = None
        if hasattr(action, "tool_input"):
            action_input = str(action.tool_input)
        elif isinstance(action, dict) and "tool_input" in action:
            action_input = str(action["tool_input"])

        if not action_input:
            return

        try:
            result = self.raxe.scan(
                action_input,
                block_on_threat=self.block_on_prompt_threats,
            )

            if result.has_threats:
                tool_name = getattr(action, "tool", "unknown")
                logger.warning(
                    f"Threat detected in agent action '{tool_name}': "
                    f"{result.severity} severity"
                )

        except SecurityException:
            logger.error("Blocked agent action due to security threat")
            raise

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        _inputs: dict[str, Any],  # Required by LangChain protocol, unused
        **kwargs: Any,
    ) -> None:
        """Hook for chain start (optional scanning of inputs).

        Args:
            serialized: Chain serialization info
            _inputs: Chain input dictionary (unused - rely on on_llm_start)
            **kwargs: Additional callback arguments
        """
        # Optional: Scan chain inputs
        # For now, rely on on_llm_start for prompt scanning
        pass

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Hook for chain end (optional scanning of outputs).

        Args:
            outputs: Chain output dictionary
            **kwargs: Additional callback arguments
        """
        # Optional: Scan chain outputs
        # For now, rely on on_llm_end for response scanning
        pass

    def on_llm_error(
        self,
        error: Exception | KeyboardInterrupt,
        **kwargs: Any,
    ) -> None:
        """Hook for LLM errors.

        Args:
            error: Exception that occurred
            **kwargs: Additional callback arguments
        """
        # Don't interfere with error handling
        pass

    def on_tool_error(
        self,
        error: Exception | KeyboardInterrupt,
        **kwargs: Any,
    ) -> None:
        """Hook for tool errors.

        Args:
            error: Exception that occurred
            **kwargs: Additional callback arguments
        """
        # Don't interfere with error handling
        pass

    def on_chain_error(
        self,
        error: Exception | KeyboardInterrupt,
        **kwargs: Any,
    ) -> None:
        """Hook for chain errors.

        Args:
            error: Exception that occurred
            **kwargs: Additional callback arguments
        """
        # Don't interfere with error handling
        pass

    def _extract_response_texts(self, response: Any) -> list[str]:
        """Extract text strings from LangChain response object.

        Args:
            response: LLM response object (format varies by LangChain version)

        Returns:
            List of text strings to scan
        """
        texts: list[str] = []

        # Handle LLMResult object
        if hasattr(response, "generations"):
            for generation_list in response.generations:
                for generation in generation_list:
                    if hasattr(generation, "text"):
                        texts.append(generation.text)
                    elif isinstance(generation, dict) and "text" in generation:
                        texts.append(generation["text"])

        # Handle ChatResult object
        elif hasattr(response, "content"):
            texts.append(response.content)

        # Handle dict response
        elif isinstance(response, dict):
            if "text" in response:
                texts.append(response["text"])
            elif "content" in response:
                texts.append(response["content"])

        # Handle string response
        elif isinstance(response, str):
            texts.append(response)

        return [text for text in texts if text]

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
