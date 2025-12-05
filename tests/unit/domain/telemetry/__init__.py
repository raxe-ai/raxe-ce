"""
Domain layer telemetry unit tests.

These tests are PURE - no mocks, no I/O, no database.
They test only business logic and pure functions.

Coverage target: >95%

Test files:
    - test_event_factory.py: Event creation for all 11 types
    - test_priority_classifier.py: Priority calculation logic
    - test_privacy_validator.py: PII detection (CRITICAL)
    - test_hash_functions.py: Hashing utilities
"""
