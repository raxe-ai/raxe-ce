"""
SDK Layer - Python SDK for Integration

The public-facing SDK for developers to integrate RAXE into their apps.

Usage patterns:
    1. Wrap existing client:
        import openai
        from raxe import Raxe
        raxe = Raxe()
        client = raxe.wrap(openai.Client())

    2. Decorator pattern:
        @raxe.protect(block_on_threat=True)
        def generate_response(prompt):
            return llm.generate(prompt)

    3. Direct scan:
        result = raxe.scan(prompt="...")
        if result.has_threats():
            handle_threat(result)

Modules (to be implemented):
    - client.py: Main SDK client
    - decorators.py: @raxe.protect decorator
    - wrappers/: LLM client wrappers (OpenAI, Anthropic, etc.)
"""

__all__ = []
