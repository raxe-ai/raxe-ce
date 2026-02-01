"""Manual tests for pre-release verification.

These tests require manual execution and are NOT run by pytest automatically.
Run them in an isolated environment before releases.

Usage:
    # Create isolated test environment
    mkdir -p /tmp/raxe-manual-test && cd /tmp/raxe-manual-test
    python -m venv venv && source venv/bin/activate
    pip install -e /path/to/raxe-ce

    # Run manual tests
    python /path/to/raxe-ce/tests/manual/test_openclaw_integration.py
"""
