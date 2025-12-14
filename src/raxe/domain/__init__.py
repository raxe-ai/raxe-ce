"""
Domain Layer - Pure Business Logic

CRITICAL RULE: This layer must contain ZERO I/O operations.

The domain layer is the heart of RAXE's threat detection logic.
All code here must be:
    ✅ Pure functions (input → output, no side effects)
    ✅ Stateless transformations and validations
    ✅ Rule matching and threat scoring
    ❌ NO database calls
    ❌ NO network requests
    ❌ NO file system access
    ❌ NO logging (pass results to application layer)

Why? This makes domain logic:
    - Blazingly fast to test (no mocks needed)
    - Easy to reason about (pure functions)
    - Portable across environments
    - Reusable in other language SDKs

Modules (to be implemented):
    - threat_detector.py: Core detection logic
    - rule_engine.py: Rule matching algorithms
    - models.py: Value objects and domain entities
    - severity.py: Severity scoring logic
    - validators.py: Input validation
"""

__all__ = []
