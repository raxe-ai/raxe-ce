"""Async wrappers for LLM clients.

This module provides async versions of LLM client wrappers that automatically
scan prompts and responses using AsyncRaxe.

Available wrappers:
- AsyncRaxeOpenAI: Async OpenAI client wrapper

Example usage:
    from raxe.async_sdk.wrappers import AsyncRaxeOpenAI

    # Async OpenAI with automatic scanning
    async with AsyncRaxeOpenAI() as client:
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )
"""
from raxe.async_sdk.wrappers.openai import AsyncRaxeOpenAI

__all__ = [
    "AsyncRaxeOpenAI",
]
