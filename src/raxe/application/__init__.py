"""
Application Layer - Use Cases & Orchestration

This layer coordinates between domain logic and infrastructure.
It defines the use cases and workflows of the RAXE system.

Responsibilities:
    - Orchestrate domain + infrastructure
    - Define use cases (scan prompt, batch scan, etc.)
    - Handle application-level errors
    - Coordinate telemetry and upgrades
    - Manage performance strategies

Pattern:
    def use_case(domain_service, repository, ...):
        # 1. Load data via infrastructure
        data = repository.load()

        # 2. Execute domain logic (pure)
        result = domain_service.process(data)

        # 3. Save via infrastructure
        repository.save(result)

        return result

Modules:
    - scan_pipeline.py: Main scanning pipeline
    - session_tracker.py: Session lifecycle and activation tracking
    - telemetry_orchestrator.py: Main telemetry coordination
    - telemetry_manager.py: Legacy telemetry management
"""

from .session_tracker import SessionTracker
from .telemetry_orchestrator import (
    TelemetryOrchestrator,
    get_orchestrator,
    reset_orchestrator,
)

__all__ = [
    # Session tracking
    "SessionTracker",
    # Telemetry orchestration
    "TelemetryOrchestrator",
    "get_orchestrator",
    "reset_orchestrator",
]
