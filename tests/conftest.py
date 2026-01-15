"""
Pytest configuration and shared fixtures.

This module provides:
- Custom pytest command-line options (--update-golden)
- Shared fixtures for all tests
- Test configuration settings
- Suppression system fixtures
"""

import tempfile
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from raxe.domain.suppression import Suppression, SuppressionManager


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
    # Telemetry-specific markers
    config.addinivalue_line(
        "markers",
        "telemetry: telemetry-related tests",
    )
    config.addinivalue_line(
        "markers",
        "privacy: privacy validation tests (CRITICAL - must always pass)",
    )
    config.addinivalue_line(
        "markers",
        "schema: JSON schema validation tests",
    )
    config.addinivalue_line(
        "markers",
        "suppression: suppression system tests",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Modify test collection to add automatic markers.

    Args:
        config: pytest configuration object
        items: list of collected test items
    """
    # Auto-mark tests based on their location
    for item in items:
        item_path = str(item.fspath)

        # Add markers based on test file path
        if "tests/integration" in item_path:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.slow)

        if "tests/performance" in item_path:
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)

        if "tests/golden" in item_path:
            item.add_marker(pytest.mark.golden)

        # Auto-mark telemetry tests
        if "/telemetry/" in item_path:
            item.add_marker(pytest.mark.telemetry)

        # Auto-mark privacy tests (tests containing 'privacy' in name)
        if "privacy" in item.name.lower() or "test_privacy" in item_path:
            item.add_marker(pytest.mark.privacy)

        # Auto-mark schema tests
        if "schema" in item.name.lower() or "test_schema" in item_path:
            item.add_marker(pytest.mark.schema)

        # Auto-mark suppression tests
        if "suppression" in item.name.lower() or "test_suppression" in item_path:
            item.add_marker(pytest.mark.suppression)


# ============================================================================
# Suppression System Fixtures
# ============================================================================


class InMemorySuppressionRepository:
    """In-memory implementation of SuppressionRepository for testing.

    This is NOT a mock - it's a real implementation that stores data
    in memory instead of a database. This allows pure domain layer testing
    without any I/O operations.

    Usage:
        @pytest.fixture
        def manager(in_memory_repo):
            return SuppressionManager(repository=in_memory_repo, auto_load=True)
    """

    def __init__(self, initial_suppressions: list[Suppression] | None = None) -> None:
        """Initialize with optional initial suppressions.

        Args:
            initial_suppressions: List of suppressions to pre-populate
        """
        self._suppressions: dict[str, Suppression] = {}
        self._audit_log: list[dict[str, Any]] = []

        if initial_suppressions:
            for s in initial_suppressions:
                self._suppressions[s.pattern] = s

    def load_suppressions(self) -> list[Suppression]:
        """Load all suppressions from memory.

        Returns:
            List of Suppression objects
        """
        return list(self._suppressions.values())

    def save_suppression(self, suppression: Suppression) -> None:
        """Save a suppression to memory.

        Args:
            suppression: Suppression to save
        """
        self._suppressions[suppression.pattern] = suppression

    def remove_suppression(self, pattern: str) -> bool:
        """Remove a suppression from memory.

        Args:
            pattern: Pattern to remove

        Returns:
            True if removed, False if not found
        """
        if pattern in self._suppressions:
            del self._suppressions[pattern]
            return True
        return False

    def save_all_suppressions(self, suppressions: list[Suppression]) -> None:
        """Replace all suppressions in memory.

        Args:
            suppressions: List of suppressions to save
        """
        self._suppressions = {s.pattern: s for s in suppressions}

    def log_audit(self, entry: Any) -> None:
        """Log an audit entry to memory.

        Args:
            entry: AuditEntry to log
        """
        self._audit_log.append(
            {
                "pattern": entry.pattern,
                "reason": entry.reason,
                "action": entry.action,
                "created_at": entry.created_at,
                "scan_id": entry.scan_id,
                "rule_id": entry.rule_id,
                "created_by": entry.created_by,
                "metadata": entry.metadata,
            }
        )

    def get_audit_log(
        self,
        limit: int = 100,
        pattern: str | None = None,
        action: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get audit log entries from memory.

        Args:
            limit: Maximum entries to return
            pattern: Filter by pattern (optional)
            action: Filter by action (optional)

        Returns:
            List of audit log entries as dictionaries
        """
        results = self._audit_log

        if pattern:
            results = [e for e in results if e["pattern"] == pattern]
        if action:
            results = [e for e in results if e["action"] == action]

        return results[:limit]


@pytest.fixture
def in_memory_suppression_repo() -> InMemorySuppressionRepository:
    """Create a fresh in-memory suppression repository for each test.

    Returns:
        InMemorySuppressionRepository instance

    Example:
        def test_suppression(in_memory_suppression_repo):
            manager = SuppressionManager(
                repository=in_memory_suppression_repo,
                auto_load=True
            )
            manager.add_suppression("pi-001", "Test")
    """
    return InMemorySuppressionRepository()


@pytest.fixture
def suppression_manager(
    in_memory_suppression_repo: InMemorySuppressionRepository,
) -> SuppressionManager:
    """Create a suppression manager with in-memory repository.

    This fixture provides a ready-to-use SuppressionManager for testing
    suppression logic without any file or database I/O.

    Returns:
        SuppressionManager instance

    Example:
        def test_is_suppressed(suppression_manager):
            suppression_manager.add_suppression("pi-001", "Test")
            assert suppression_manager.is_suppressed("pi-001")[0] is True
    """
    return SuppressionManager(repository=in_memory_suppression_repo, auto_load=True)


@pytest.fixture
def temp_raxe_config_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for RAXE configuration.

    This fixture creates a temporary directory that can be used for
    suppression YAML files and SQLite databases in integration tests.

    Yields:
        Path to temporary directory

    Example:
        def test_file_loading(temp_raxe_config_dir):
            config_path = temp_raxe_config_dir / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(sample_suppressions_yaml_content)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_suppressions_yaml_content() -> str:
    """Provide sample .raxe/suppressions.yaml file content for testing.

    Returns:
        Sample YAML suppressions content as string

    Example:
        def test_loading(temp_raxe_config_dir, sample_suppressions_yaml_content):
            config_path = temp_raxe_config_dir / ".raxe" / "suppressions.yaml"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(sample_suppressions_yaml_content)
    """
    # Note: Patterns must have valid family prefixes (pi, jb, cmd, etc.)
    # Patterns like *-injection are NOT allowed (must start with family prefix)
    return """version: "1.0"

# Test configuration
suppressions:
  # Specific rules
  - pattern: "pi-001"
    reason: "False positive in documentation"
  - pattern: "jb-regex-basic"
    reason: "Too sensitive for this project"

  # Wildcard patterns (with valid family prefixes)
  - pattern: "pi-*"
    reason: "All prompt injection rules"
  - pattern: "jb-*"
    reason: "All jailbreak rules"

  # More specific patterns
  - pattern: "jb-*-basic"
    reason: "All basic jailbreak rules"
"""


@pytest.fixture
def sample_suppressions() -> list[Suppression]:
    """Provide sample Suppression objects for testing.

    Returns:
        List of sample Suppression objects

    Example:
        def test_matching(sample_suppressions):
            for supp in sample_suppressions:
                assert supp.pattern is not None
    """
    # Note: All patterns must have valid family prefixes
    now = datetime.now(timezone.utc).isoformat()
    return [
        Suppression(
            pattern="pi-001",
            reason="False positive in documentation",
            created_at=now,
            created_by="test",
        ),
        Suppression(
            pattern="jb-regex-basic",
            reason="Too sensitive",
            created_at=now,
            created_by="test",
        ),
        Suppression(
            pattern="pi-*",
            reason="All PI rules",
            created_at=now,
            created_by="test",
        ),
        Suppression(
            pattern="jb-*",
            reason="All JB rules",
            created_at=now,
            created_by="test",
        ),
    ]


@pytest.fixture
def mock_suppression_manager(
    sample_suppressions: list[Suppression],
) -> SuppressionManager:
    """Create a pre-populated suppression manager for testing.

    This fixture provides a SuppressionManager pre-loaded with common
    test patterns including exact matches and wildcards.

    Returns:
        SuppressionManager with sample suppressions

    Example:
        def test_wildcard_matching(mock_suppression_manager):
            is_suppressed, _ = mock_suppression_manager.is_suppressed("pi-002")
            assert is_suppressed is True  # Matches pi-*
    """
    repo = InMemorySuppressionRepository(initial_suppressions=sample_suppressions)
    return SuppressionManager(repository=repo, auto_load=True)
