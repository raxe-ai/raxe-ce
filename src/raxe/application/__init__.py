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

Modules (to be implemented):
    - scan_prompt.py: Scan a single prompt/response
    - batch_scan.py: Batch scanning workflows
    - telemetry.py: Telemetry management
    - upgrade_flow.py: Upgrade to paid tiers
"""

__all__ = []
