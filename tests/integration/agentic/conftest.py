"""Fixtures for agentic integration tests.

Provides conditional skipping and framework detection.
"""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for framework requirements."""
    config.addinivalue_line(
        "markers",
        "requires_langchain: test requires LangChain to be installed",
    )
    config.addinivalue_line(
        "markers",
        "requires_crewai: test requires CrewAI to be installed",
    )
    config.addinivalue_line(
        "markers",
        "requires_autogen: test requires AutoGen to be installed",
    )
    config.addinivalue_line(
        "markers",
        "requires_llamaindex: test requires LlamaIndex to be installed",
    )
    config.addinivalue_line(
        "markers",
        "requires_mcp: test requires MCP SDK to be installed",
    )


@pytest.fixture(scope="session")
def langchain_available() -> bool:
    """Check if LangChain is installed."""
    try:
        import langchain

        return True
    except ImportError:
        return False


@pytest.fixture(scope="session")
def langchain_version() -> str | None:
    """Get installed LangChain version."""
    try:
        import langchain

        return langchain.__version__
    except ImportError:
        return None


@pytest.fixture(scope="session")
def crewai_available() -> bool:
    """Check if CrewAI is installed."""
    try:
        import crewai

        return True
    except ImportError:
        return False


@pytest.fixture(scope="session")
def crewai_version() -> str | None:
    """Get installed CrewAI version."""
    try:
        import crewai

        return crewai.__version__
    except ImportError:
        return None


@pytest.fixture(scope="session")
def autogen_available() -> bool:
    """Check if AutoGen is installed."""
    try:
        import autogen

        return True
    except ImportError:
        return False


@pytest.fixture(scope="session")
def autogen_version() -> str | None:
    """Get installed AutoGen version."""
    try:
        import autogen

        return autogen.__version__
    except ImportError:
        return None


@pytest.fixture(scope="session")
def llamaindex_available() -> bool:
    """Check if LlamaIndex is installed."""
    try:
        import llama_index

        return True
    except ImportError:
        return False


@pytest.fixture(scope="session")
def llamaindex_version() -> str | None:
    """Get installed LlamaIndex version."""
    try:
        import llama_index

        return llama_index.__version__
    except ImportError:
        return None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip tests based on framework availability."""
    for item in items:
        if "requires_langchain" in item.keywords:
            try:
                import langchain  # noqa: F401
            except ImportError:
                item.add_marker(pytest.mark.skip(reason="LangChain not installed"))

        if "requires_crewai" in item.keywords:
            try:
                import crewai  # noqa: F401
            except ImportError:
                item.add_marker(pytest.mark.skip(reason="CrewAI not installed"))

        if "requires_autogen" in item.keywords:
            try:
                import autogen  # noqa: F401
            except ImportError:
                item.add_marker(pytest.mark.skip(reason="AutoGen not installed"))

        if "requires_llamaindex" in item.keywords:
            try:
                import llama_index  # noqa: F401
            except ImportError:
                item.add_marker(pytest.mark.skip(reason="LlamaIndex not installed"))

        if "requires_mcp" in item.keywords:
            try:
                import mcp  # noqa: F401
            except ImportError:
                item.add_marker(pytest.mark.skip(reason="MCP SDK not installed"))
