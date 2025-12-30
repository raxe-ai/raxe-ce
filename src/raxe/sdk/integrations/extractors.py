"""Unified text extraction utilities for RAXE integrations.

This module provides common text extraction functions used across all
framework integrations (LangChain, AutoGen, CrewAI, LlamaIndex, etc.).

The extractors handle various message formats:
- Plain strings
- Objects with .content attribute
- Dicts with "content" or "text" keys
- Multi-modal content lists
- Function/tool call messages
"""

from __future__ import annotations

from typing import Any


def extract_text_from_message(message: Any) -> str | None:
    """Extract text content from a chat message.

    Handles common message formats across frameworks:
    - Plain string
    - Object with .content attribute (ChatMessage, HumanMessage, etc.)
    - Dict with "content" key
    - Multi-modal content lists

    Args:
        message: Message in any supported format

    Returns:
        Extracted text or None if no text found
    """
    if message is None:
        return None

    if isinstance(message, str):
        return message

    # Handle objects with .content attribute
    if hasattr(message, "content"):
        return extract_text_from_content(message.content)

    # Handle dict messages
    if isinstance(message, dict):
        content = message.get("content")
        if content is not None:
            return extract_text_from_content(content)
        # Fallback to "text" key
        text = message.get("text")
        if isinstance(text, str):
            return text

    return None


def extract_text_from_content(content: Any) -> str | None:
    """Extract text from a content field.

    Handles:
    - Plain string
    - List of content blocks (multi-modal)
    - Nested content objects

    Args:
        content: Content value (string, list, or object)

    Returns:
        Extracted text or None
    """
    if content is None:
        return None

    if isinstance(content, str):
        return content

    # Handle list of content blocks (multi-modal messages)
    if isinstance(content, list):
        return extract_text_from_content_list(content)

    # Handle objects with text attribute
    if hasattr(content, "text"):
        return str(content.text)

    return None


def extract_text_from_content_list(content_list: list[Any]) -> str | None:
    """Extract text from a list of content blocks.

    Common in multi-modal messages where content is a list of
    text blocks, image blocks, etc.

    Args:
        content_list: List of content blocks

    Returns:
        Combined text from all text blocks, or None if empty
    """
    if not content_list:
        return None

    texts: list[str] = []
    for block in content_list:
        if isinstance(block, str):
            texts.append(block)
        elif isinstance(block, dict):
            # Common format: {"type": "text", "text": "..."}
            text = block.get("text")
            if isinstance(text, str):
                texts.append(text)
        elif hasattr(block, "text"):
            # Object with text attribute
            texts.append(str(block.text))

    return " ".join(texts) if texts else None


def extract_text_from_dict(
    d: dict[str, Any],
    keys: tuple[str, ...] = ("content", "text", "message"),
) -> str | None:
    """Extract text from a dict using fallback keys.

    Args:
        d: Dictionary to extract from
        keys: Keys to try in order

    Returns:
        First non-None string value found, or None
    """
    for key in keys:
        value = d.get(key)
        if isinstance(value, str):
            return value
        if value is not None:
            # Try to extract from nested content
            extracted = extract_text_from_content(value)
            if extracted:
                return extracted
    return None


def extract_text_from_response(response: Any) -> str | None:
    """Extract text from an LLM response object.

    Handles various response formats:
    - Plain string
    - Object with .text attribute
    - Object with .content attribute
    - Object with .generations (LangChain)
    - Object with .message (LangChain generation)

    Args:
        response: LLM response object

    Returns:
        Extracted text or None
    """
    if response is None:
        return None

    if isinstance(response, str):
        return response

    # Direct text attribute
    if hasattr(response, "text"):
        return str(response.text)

    # Content attribute (common in chat responses)
    if hasattr(response, "content"):
        return extract_text_from_content(response.content)

    # LangChain generations format
    if hasattr(response, "generations"):
        texts: list[str] = []
        for gen_list in response.generations:
            for gen in gen_list:
                if hasattr(gen, "text"):
                    texts.append(gen.text)
                elif hasattr(gen, "message"):
                    msg_text = extract_text_from_message(gen.message)
                    if msg_text:
                        texts.append(msg_text)
        return "\n".join(texts) if texts else None

    # Fallback to string conversion
    return str(response) if response else None


def extract_texts_from_value(value: Any) -> list[str]:
    """Extract all text strings from a value.

    Useful for extracting multiple texts from complex structures.

    Args:
        value: Value to extract texts from

    Returns:
        List of extracted text strings (may be empty)
    """
    if value is None:
        return []

    if isinstance(value, str):
        return [value] if value else []

    if isinstance(value, list):
        texts: list[str] = []
        for item in value:
            texts.extend(extract_texts_from_value(item))
        return texts

    if isinstance(value, dict):
        # Try common text keys
        for key in ("content", "text", "message", "output"):
            if key in value:
                texts = extract_texts_from_value(value[key])
                if texts:
                    return texts
        return []

    # Object with content or text
    if hasattr(value, "content"):
        return extract_texts_from_value(value.content)
    if hasattr(value, "text"):
        return [str(value.text)]

    return []


def is_function_call(message: Any) -> bool:
    """Check if a message is a function/tool call.

    Args:
        message: Message to check

    Returns:
        True if message appears to be a function call
    """
    if isinstance(message, dict):
        # OpenAI/AutoGen format
        if "function_call" in message or "tool_calls" in message:
            return True
        # Role-based detection
        if message.get("role") in ("function", "tool"):
            return True

    # Object-based detection
    if hasattr(message, "function_call") and message.function_call:
        return True
    if hasattr(message, "tool_calls") and message.tool_calls:
        return True

    return False


def extract_function_call_text(message: Any) -> str | None:
    """Extract scannable text from a function/tool call.

    Combines function name and arguments for security scanning.

    Args:
        message: Function call message

    Returns:
        Combined function name and arguments text, or None
    """
    parts: list[str] = []

    if isinstance(message, dict):
        # OpenAI function_call format
        fc = message.get("function_call")
        if isinstance(fc, dict):
            if "name" in fc:
                parts.append(f"function: {fc['name']}")
            if "arguments" in fc:
                parts.append(f"args: {fc['arguments']}")

        # OpenAI tool_calls format
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for tc in tool_calls:
                if isinstance(tc, dict):
                    func = tc.get("function", {})
                    if isinstance(func, dict):
                        if "name" in func:
                            parts.append(f"function: {func['name']}")
                        if "arguments" in func:
                            parts.append(f"args: {func['arguments']}")

    # Object-based function call
    if hasattr(message, "function_call") and message.function_call:
        fc = message.function_call
        if hasattr(fc, "name"):
            parts.append(f"function: {fc.name}")
        if hasattr(fc, "arguments"):
            parts.append(f"args: {fc.arguments}")

    if hasattr(message, "tool_calls") and message.tool_calls:
        for tc in message.tool_calls:
            if hasattr(tc, "function"):
                func = tc.function
                if hasattr(func, "name"):
                    parts.append(f"function: {func.name}")
                if hasattr(func, "arguments"):
                    parts.append(f"args: {func.arguments}")

    return " | ".join(parts) if parts else None


def extract_agent_name(obj: Any, fallback: str = "unknown") -> str:
    """Extract agent name from various object types.

    Args:
        obj: Object that may contain agent info
        fallback: Default name if extraction fails

    Returns:
        Agent name or fallback
    """
    # Direct agent attribute
    if hasattr(obj, "agent"):
        agent = obj.agent
        if isinstance(agent, str):
            return agent
        if hasattr(agent, "name"):
            return str(agent.name)
        if hasattr(agent, "role"):
            return str(agent.role)

    # Direct name attribute
    if hasattr(obj, "name"):
        return str(obj.name)

    # Role attribute (common in chat)
    if hasattr(obj, "role"):
        return str(obj.role)

    # Dict with agent info
    if isinstance(obj, dict):
        if "agent" in obj:
            agent = obj["agent"]
            if isinstance(agent, str):
                return agent
            if isinstance(agent, dict):
                return agent.get("name", fallback)
        return obj.get("name", obj.get("role", fallback))

    return fallback


__all__ = [
    "extract_agent_name",
    "extract_function_call_text",
    "extract_text_from_content",
    "extract_text_from_content_list",
    "extract_text_from_dict",
    "extract_text_from_message",
    "extract_text_from_response",
    "extract_texts_from_value",
    "is_function_call",
]
