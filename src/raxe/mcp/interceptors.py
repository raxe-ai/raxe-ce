"""MCP Message Interceptors.

Interceptors handle scanning of different MCP message types:
- Tool calls (arguments and parameters)
- Tool responses (output content)
- Resources (content provided to LLM)
- Prompts (template content)
- Sampling requests (system prompts)

Each interceptor extracts text content from MCP messages and scans
it using the RAXE AgentScanner.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from raxe.domain.severity import get_severity_value

if TYPE_CHECKING:
    from raxe.sdk.agent_scanner import AgentScanner, AgentScanResult


@dataclass
class InterceptionResult:
    """Result of intercepting and scanning an MCP message.

    Attributes:
        should_block: Whether the message should be blocked
        scan_result: The scan result from AgentScanner (if scanned)
        modified_message: Modified message (if any transformation applied)
        reason: Human-readable reason for blocking (if blocked)
        texts_scanned_count: Number of text segments scanned (privacy-safe)
    """

    should_block: bool = False
    scan_result: AgentScanResult | None = None
    modified_message: dict[str, Any] | None = None
    reason: str | None = None
    texts_scanned_count: int = 0


class BaseInterceptor(ABC):
    """Base class for MCP message interceptors.

    Interceptors are responsible for:
    1. Extracting text content from specific MCP message types
    2. Scanning the extracted content
    3. Deciding whether to allow, modify, or block the message
    """

    def __init__(self, scanner: AgentScanner) -> None:
        """Initialize interceptor with scanner.

        Args:
            scanner: AgentScanner instance for threat detection
        """
        self._scanner = scanner

    @abstractmethod
    def can_handle(self, method: str) -> bool:
        """Check if this interceptor can handle the given method.

        Args:
            method: MCP method name (e.g., "tools/call")

        Returns:
            True if this interceptor handles this method
        """
        ...

    @abstractmethod
    def intercept(
        self,
        method: str,
        params: dict[str, Any] | None,
        is_response: bool = False,
    ) -> InterceptionResult:
        """Intercept and scan an MCP message.

        Args:
            method: MCP method name
            params: Message parameters/result
            is_response: True if this is a response message

        Returns:
            InterceptionResult with scan outcome
        """
        ...

    def _extract_text_content(self, obj: Any) -> list[str]:
        """Recursively extract text content from any object.

        Args:
            obj: Any object (dict, list, str, etc.)

        Returns:
            List of text strings found
        """
        texts: list[str] = []

        if obj is None:
            return texts

        if isinstance(obj, str):
            stripped = obj.strip()
            if stripped:  # Skip empty strings and whitespace-only
                texts.append(stripped)
        elif isinstance(obj, dict):
            # Check for common text fields
            for key in ("text", "content", "value", "message", "prompt", "query"):
                if key in obj and isinstance(obj[key], str):
                    stripped = obj[key].strip()
                    if stripped:
                        texts.append(stripped)

            # Recurse into all values (skip known text fields to avoid duplicates)
            text_keys = {"text", "content", "value", "message", "prompt", "query"}
            for key, value in obj.items():
                if key not in text_keys:
                    texts.extend(self._extract_text_content(value))
        elif isinstance(obj, list):
            for item in obj:
                texts.extend(self._extract_text_content(item))

        return texts

    def _scan_texts(self, texts: list[str]) -> InterceptionResult:
        """Scan multiple texts and aggregate results.

        Args:
            texts: List of texts to scan

        Returns:
            InterceptionResult with aggregated scan outcome
        """
        if not texts:
            return InterceptionResult()

        should_block = False
        aggregated_result: AgentScanResult | None = None

        for text in texts:
            result = self._scanner.scan_prompt(text)

            if result.should_block:
                should_block = True

            if aggregated_result is None:
                aggregated_result = result
            elif result.has_threats:
                # Keep the most severe result using canonical severity ordering
                if aggregated_result.severity is None or (
                    result.severity
                    and get_severity_value(result.severity)
                    > get_severity_value(aggregated_result.severity)
                ):
                    aggregated_result = result

        reason = None
        if should_block and aggregated_result:
            reason = f"Threat detected: {aggregated_result.severity} severity"
            if aggregated_result.rule_ids:
                reason += f" (rules: {', '.join(aggregated_result.rule_ids[:3])})"

        return InterceptionResult(
            should_block=should_block,
            scan_result=aggregated_result,
            reason=reason,
            texts_scanned_count=len(texts),
        )


class ToolCallInterceptor(BaseInterceptor):
    """Intercept and scan MCP tool call arguments.

    Scans:
    - Tool arguments (the parameters passed to tools)
    - Can detect command injection, prompt injection, data exfiltration
    """

    def can_handle(self, method: str) -> bool:
        return method == "tools/call"

    def intercept(
        self,
        method: str,
        params: dict[str, Any] | None,
        is_response: bool = False,
    ) -> InterceptionResult:
        if is_response or params is None:
            return InterceptionResult()

        # Extract tool arguments
        arguments = params.get("arguments", {})
        texts = self._extract_text_content(arguments)

        # Also check tool name for suspicious patterns
        tool_name = params.get("name", "")
        if tool_name:
            texts.append(f"Tool call: {tool_name}")

        return self._scan_texts(texts)


class ToolResponseInterceptor(BaseInterceptor):
    """Intercept and scan MCP tool call responses.

    Scans:
    - Tool output content
    - Can detect data exfiltration, indirect prompt injection
    """

    def can_handle(self, method: str) -> bool:
        return method == "tools/call"

    def intercept(
        self,
        method: str,
        params: dict[str, Any] | None,
        is_response: bool = False,
    ) -> InterceptionResult:
        if not is_response or params is None:
            return InterceptionResult()

        # Extract content from tool response
        content = params.get("content", [])
        texts = self._extract_text_content(content)

        return self._scan_texts(texts)


class ResourceInterceptor(BaseInterceptor):
    """Intercept and scan MCP resource content.

    Scans:
    - Resource content before providing to LLM
    - Can detect hidden instructions, injection payloads
    """

    def can_handle(self, method: str) -> bool:
        return method in ("resources/read", "resources/list")

    def intercept(
        self,
        method: str,
        params: dict[str, Any] | None,
        is_response: bool = False,
    ) -> InterceptionResult:
        if not is_response or params is None:
            return InterceptionResult()

        # Extract content from resource response
        contents = params.get("contents", [])
        texts = self._extract_text_content(contents)

        return self._scan_texts(texts)


class PromptInterceptor(BaseInterceptor):
    """Intercept and scan MCP prompt templates.

    Scans:
    - Prompt template content
    - Can detect injection payloads in templates
    """

    def can_handle(self, method: str) -> bool:
        return method in ("prompts/get", "prompts/list")

    def intercept(
        self,
        method: str,
        params: dict[str, Any] | None,
        is_response: bool = False,
    ) -> InterceptionResult:
        if not is_response or params is None:
            return InterceptionResult()

        # Extract messages from prompt response
        messages = params.get("messages", [])
        texts = self._extract_text_content(messages)

        # Also check description
        description = params.get("description", "")
        if description:
            texts.append(description)

        return self._scan_texts(texts)


class SamplingInterceptor(BaseInterceptor):
    """Intercept and scan MCP sampling requests.

    Scans:
    - System prompts in sampling requests
    - Messages being sent to LLM
    - Can detect prompt manipulation
    """

    def can_handle(self, method: str) -> bool:
        return method == "sampling/createMessage"

    def intercept(
        self,
        method: str,
        params: dict[str, Any] | None,
        is_response: bool = False,
    ) -> InterceptionResult:
        if is_response or params is None:
            return InterceptionResult()

        texts: list[str] = []

        # Extract system prompt
        system_prompt = params.get("systemPrompt", "")
        if system_prompt:
            texts.append(system_prompt)

        # Extract messages
        messages = params.get("messages", [])
        texts.extend(self._extract_text_content(messages))

        return self._scan_texts(texts)


class InterceptorChain:
    """Chain of interceptors for processing MCP messages.

    Manages multiple interceptors and routes messages to appropriate ones.
    """

    def __init__(self, scanner: AgentScanner) -> None:
        """Initialize interceptor chain with scanner.

        Args:
            scanner: AgentScanner instance for threat detection
        """
        self._scanner = scanner
        self._interceptors: list[BaseInterceptor] = [
            ToolCallInterceptor(scanner),
            ToolResponseInterceptor(scanner),
            ResourceInterceptor(scanner),
            PromptInterceptor(scanner),
            SamplingInterceptor(scanner),
        ]

    def intercept(
        self,
        method: str,
        params: dict[str, Any] | None,
        is_response: bool = False,
    ) -> InterceptionResult:
        """Route message to appropriate interceptor.

        Args:
            method: MCP method name
            params: Message parameters
            is_response: True if this is a response message

        Returns:
            InterceptionResult from the handling interceptor
        """
        for interceptor in self._interceptors:
            if interceptor.can_handle(method):
                return interceptor.intercept(method, params, is_response)

        # No interceptor matched - allow by default
        return InterceptionResult()

    def intercept_request(
        self,
        message: dict[str, Any],
    ) -> InterceptionResult:
        """Intercept a JSON-RPC request message.

        Args:
            message: Full JSON-RPC request

        Returns:
            InterceptionResult
        """
        method = message.get("method", "")
        params = message.get("params")

        return self.intercept(method, params, is_response=False)

    def intercept_response(
        self,
        request: dict[str, Any],
        response: dict[str, Any],
    ) -> InterceptionResult:
        """Intercept a JSON-RPC response message.

        Args:
            request: Original request message
            response: Response message

        Returns:
            InterceptionResult
        """
        method = request.get("method", "")
        result = response.get("result")

        return self.intercept(method, result, is_response=True)
