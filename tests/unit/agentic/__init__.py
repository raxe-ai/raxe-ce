"""Unit tests for agentic integrations.

This package contains unit tests for:
- AgentScanner core component
- MCP Server handler and tools
- LangChain integration (callback handler, LCEL)
- CrewAI integration (hooks, decorators)
- AutoGen integration (agent wrappers)
- LlamaIndex integration (query engine, retriever)

All tests in this package must be PURE:
- No network calls
- No database access
- No file I/O (except fixtures)
- Use mocks for external dependencies

Coverage target: >95% for domain layer, >90% for integrations.
"""
