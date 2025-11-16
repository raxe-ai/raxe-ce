"""
Pytest configuration and shared fixtures.

This module provides:
- Custom pytest command-line options (--update-golden)
- Shared fixtures for all tests
- Test configuration settings
"""
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command-line options to pytest.

    Args:
        parser: pytest command-line parser
    """
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help=(
            "Update golden file expected outputs instead of comparing. "
            "Use this when detection logic changes intentionally. "
            "Example: pytest tests/golden/ --update-golden"
        ),
    )


@pytest.fixture
def update_golden(request: pytest.FixtureRequest) -> bool:
    """Fixture to check if --update-golden flag was provided.

    Args:
        request: pytest fixture request

    Returns:
        True if --update-golden was provided, False otherwise

    Example:
        def test_something(update_golden):
            if update_golden:
                # Update reference data
                write_golden_file(data)
            else:
                # Normal test comparison
                assert data == expected
    """
    return request.config.getoption("--update-golden", default=False)


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers and settings.

    Args:
        config: pytest configuration object
    """
    # Register custom markers
    config.addinivalue_line(
        "markers",
        "golden: golden file regression tests (can use --update-golden)",
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers",
        "integration: integration tests (deselect with '-m \"not integration\"')",
    )
    config.addinivalue_line(
        "markers",
        "performance: performance benchmark tests (deselect with '-m \"not performance\"')",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Modify test collection to add automatic markers.

    Args:
        config: pytest configuration object
        items: list of collected test items
    """
    # Auto-mark tests based on their location
    for item in items:
        # Add markers based on test file path
        if "tests/integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.slow)

        if "tests/performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)

        if "tests/golden" in str(item.fspath):
            item.add_marker(pytest.mark.golden)
