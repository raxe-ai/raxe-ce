"""
Shared fixtures for integration tests.

Provides common test infrastructure including:
- Temporary database paths
- Test telemetry orchestrators
- Test pipelines with telemetry enabled
- Mock components for isolated testing
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
    from raxe.infrastructure.telemetry.dual_queue import DualQueue


@pytest.fixture
def telemetry_db(tmp_path: Path) -> Path:
    """Create a temporary telemetry database path.

    Args:
        tmp_path: pytest temporary path fixture

    Returns:
        Path to temporary SQLite database file.

    Example:
        def test_something(telemetry_db):
            queue = DualQueue(db_path=telemetry_db)
    """
    db_path = tmp_path / "telemetry.db"
    return db_path


@pytest.fixture
def test_queue(telemetry_db: Path) -> Generator[DualQueue, None, None]:
    """Create a test DualQueue with temporary database.

    The queue is properly closed after the test completes.

    Args:
        telemetry_db: Path to temporary database

    Yields:
        Configured DualQueue instance.

    Example:
        def test_queue_operations(test_queue):
            event = create_scan_event(...)
            test_queue.enqueue(event)
    """
    from raxe.infrastructure.telemetry.dual_queue import DualQueue

    queue = DualQueue(db_path=telemetry_db)
    try:
        yield queue
    finally:
        queue.close()


@pytest.fixture
def test_orchestrator(telemetry_db: Path) -> Generator[TelemetryOrchestrator, None, None]:
    """Create a test TelemetryOrchestrator with temporary database.

    The orchestrator is properly started and stopped, ensuring clean
    state for each test.

    Args:
        telemetry_db: Path to temporary database

    Yields:
        Configured and started TelemetryOrchestrator instance.

    Example:
        def test_tracking(test_orchestrator):
            test_orchestrator.track_scan(
                scan_result={"threat_detected": True},
                prompt_hash="abc123",
                duration_ms=5.0,
            )
    """
    from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
    from raxe.infrastructure.config.yaml_config import TelemetryConfig

    # Create config with telemetry enabled
    config = TelemetryConfig(enabled=True)

    # Create orchestrator with temp database
    orchestrator = TelemetryOrchestrator(config=config, db_path=telemetry_db)
    orchestrator.start()

    try:
        yield orchestrator
    finally:
        orchestrator.stop(graceful=False)


@pytest.fixture
def disabled_orchestrator(telemetry_db: Path) -> Generator[TelemetryOrchestrator, None, None]:
    """Create a test TelemetryOrchestrator with telemetry disabled.

    Used to verify that no events are tracked when telemetry is disabled.

    Args:
        telemetry_db: Path to temporary database

    Yields:
        TelemetryOrchestrator with telemetry disabled.

    Example:
        def test_no_tracking_when_disabled(disabled_orchestrator):
            disabled_orchestrator.track_scan(...)
            # Should not create any events
    """
    from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
    from raxe.infrastructure.config.yaml_config import TelemetryConfig

    # Create config with telemetry disabled
    config = TelemetryConfig(enabled=False)

    # Create orchestrator with temp database
    orchestrator = TelemetryOrchestrator(config=config, db_path=telemetry_db)

    try:
        yield orchestrator
    finally:
        orchestrator.stop(graceful=False)


@pytest.fixture
def mock_scan_result() -> dict[str, Any]:
    """Create a mock scan result for testing.

    Returns:
        Dictionary with scan result structure.
    """
    return {
        "threat_detected": True,
        "detection_count": 2,
        "highest_severity": "HIGH",
        "rule_ids": ["pi-001", "pi-002"],
        "families": ["PI"],
        "l1_hit": True,
        "l2_hit": False,
        "l2_enabled": True,
        "prompt_length": 50,
        "action_taken": "warn",
    }


@pytest.fixture
def clean_scan_result() -> dict[str, Any]:
    """Create a clean scan result with no threats.

    Returns:
        Dictionary with clean scan result structure.
    """
    return {
        "threat_detected": False,
        "detection_count": 0,
        "highest_severity": None,
        "rule_ids": [],
        "families": [],
        "l1_hit": False,
        "l2_hit": False,
        "l2_enabled": True,
        "prompt_length": 50,
        "action_taken": "allow",
    }


@pytest.fixture
def sample_prompt_hash() -> str:
    """Create a sample prompt hash for testing.

    Returns:
        64-character SHA-256 hash string.
    """
    import hashlib

    return hashlib.sha256(b"test prompt").hexdigest()


@pytest.fixture
def isolated_raxe_home(tmp_path: Path) -> Generator[Path, None, None]:
    """Create an isolated RAXE home directory for testing.

    This fixture sets up a complete isolated environment for RAXE,
    preventing interference with any real configuration or data.

    Args:
        tmp_path: pytest temporary path fixture

    Yields:
        Path to the isolated .raxe directory.
    """
    import os

    raxe_home = tmp_path / ".raxe"
    raxe_home.mkdir(parents=True, exist_ok=True)

    # Save original environment
    original_home = os.environ.get("RAXE_HOME")

    # Set isolated home
    os.environ["RAXE_HOME"] = str(raxe_home)

    try:
        yield raxe_home
    finally:
        # Restore original environment
        if original_home is not None:
            os.environ["RAXE_HOME"] = original_home
        else:
            os.environ.pop("RAXE_HOME", None)
