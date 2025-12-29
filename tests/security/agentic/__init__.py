"""Security tests for agentic features.

Tests security properties including:
- Injection attack detection (SQL, shell, path traversal)
- Protocol fuzzing (malformed inputs)
- Privacy preservation (no PII in logs/telemetry)
- Multi-step jailbreak detection

These tests are CRITICAL and must always pass.
"""
