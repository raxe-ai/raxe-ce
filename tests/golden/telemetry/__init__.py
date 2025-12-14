"""
Golden file tests for telemetry event schemas.

These tests prevent regressions in event structure by comparing
generated events against expected golden files.

Usage:
    # Run golden tests
    pytest tests/golden/telemetry/ -v

    # Update golden files after intentional changes
    pytest tests/golden/telemetry/ --update-golden
"""
