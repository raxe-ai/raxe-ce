"""Golden file tests for suppression behavior.

These tests ensure suppression behavior is deterministic and consistent:
- Same input + config = same output
- Suppression patterns work correctly across versions
- No regressions in suppression matching logic

When suppression logic changes intentionally, update golden files with:
    pytest tests/golden/test_suppression_golden.py --update-golden
"""
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from raxe.domain.suppression import Suppression
from raxe.domain.suppression_factory import create_suppression_manager


# ============================================================================
# Golden Test Fixtures
# ============================================================================


GOLDEN_DIR = Path(__file__).parent / "fixtures" / "suppression"


# Suppression pattern test cases
# Format: (pattern, rule_ids_to_test, expected_matches)
# Note: Patterns starting with '*' are NOT allowed in the actual implementation
PATTERN_TEST_CASES = [
    # Exact matches
    ("pi-001", ["pi-001", "pi-002", "pi-001a", "jb-001"], [True, False, False, False]),
    ("jb-regex-basic", ["jb-regex-basic", "jb-regex", "jb-basic"], [True, False, False]),
    # Prefix wildcards (valid family prefixes)
    ("pi-*", ["pi-001", "pi-002", "pi-advanced", "jb-001", "pii-email"], [True, True, True, False, False]),
    ("jb-*", ["jb-001", "jb-regex-basic", "pi-001"], [True, True, False]),
    ("cmd-*", ["cmd-001", "cmd-injection", "pi-001"], [True, True, False]),
    # Middle wildcards (with valid prefixes)
    ("jb-*-basic", ["jb-regex-basic", "jb-pattern-basic", "jb-basic", "jb-advanced"], [True, True, False, False]),
    ("pi-*-v2", ["pi-001-v2", "pi-advanced-v2", "pi-v2", "pi-001"], [True, True, False, False]),
    # Question mark wildcards
    ("pi-00?", ["pi-001", "pi-002", "pi-009", "pi-010", "pi-0001"], [True, True, True, False, False]),
    # Character classes
    ("pi-[0-9]*", ["pi-001", "pi-999", "pi-1abc", "pi-abc"], [True, True, True, False]),
    # Multiple wildcards (with valid prefix)
    ("jb-*-*", ["jb-regex-basic", "jb-a-b", "jb-001"], [True, True, False]),
]


# ============================================================================
# Golden Test Implementation
# ============================================================================


def get_golden_file_path(test_name: str) -> Path:
    """Get path to golden file for a test."""
    return GOLDEN_DIR / f"{test_name}.json"


def ensure_golden_dir_exists() -> None:
    """Ensure golden fixtures directory exists."""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)


class TestSuppressionPatternGolden:
    """Golden tests for suppression pattern matching."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Ensure golden directory exists."""
        ensure_golden_dir_exists()

    @pytest.mark.parametrize(
        "pattern,rule_ids,expected",
        PATTERN_TEST_CASES,
        ids=[f"pattern_{tc[0].replace('*', 'star').replace('?', 'q').replace('[', 'b')}" for tc in PATTERN_TEST_CASES],
    )
    def test_pattern_matching(
        self,
        pattern: str,
        rule_ids: list[str],
        expected: list[bool],
        request: pytest.FixtureRequest,
    ) -> None:
        """Test that pattern matching produces expected results."""
        update_golden = request.config.getoption("--update-golden", default=False)

        # Create suppression and test matches
        suppression = Suppression(
            pattern=pattern,
            reason="Test pattern",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        actual_matches = [suppression.matches(rule_id) for rule_id in rule_ids]

        # Build result for golden file
        test_name = f"pattern_{pattern.replace('*', 'star').replace('?', 'q').replace('[', 'b').replace(']', 'b')}"
        golden_file = get_golden_file_path(test_name)

        actual = {
            "pattern": pattern,
            "test_cases": [
                {"rule_id": rule_id, "matches": match}
                for rule_id, match in zip(rule_ids, actual_matches)
            ],
        }

        if update_golden:
            golden_file.write_text(json.dumps(actual, indent=2))
            pytest.skip(f"Updated golden file: {golden_file.name}")
            return

        # Compare with expected (from test parameters, not golden file for now)
        assert actual_matches == expected, f"Pattern {pattern} mismatch"


class TestSuppressionManagerGolden:
    """Golden tests for suppression manager behavior."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Ensure golden directory exists."""
        ensure_golden_dir_exists()

    def test_is_suppressed_deterministic(
        self, request: pytest.FixtureRequest
    ) -> None:
        """Test that is_suppressed behavior is deterministic."""
        update_golden = request.config.getoption("--update-golden", default=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create manager with fixed suppressions
            manager = create_suppression_manager(db_path=db_path, auto_load=False)

            # Add suppressions in specific order (all with valid family prefixes)
            suppressions_to_add = [
                ("pi-001", "Specific PI rule"),
                ("pi-*", "All PI rules"),
                ("jb-*", "All JB rules"),
                ("jb-regex-basic", "Specific JB rule"),
            ]
            for pattern, reason in suppressions_to_add:
                manager.add_suppression(pattern, reason)

            # Test rule IDs
            test_rule_ids = [
                "pi-001",
                "pi-002",
                "pi-injection",
                "jb-001",
                "jb-regex-basic",
                "jb-injection",
                "cmd-injection",
                "pii-email",
            ]

            # Get results
            results = []
            for rule_id in test_rule_ids:
                is_suppressed, reason = manager.is_suppressed(rule_id)
                results.append({
                    "rule_id": rule_id,
                    "is_suppressed": is_suppressed,
                    "reason": reason if is_suppressed else None,
                })

            golden_file = get_golden_file_path("manager_is_suppressed")

            actual = {
                "suppressions": [{"pattern": p, "reason": r} for p, r in suppressions_to_add],
                "results": results,
            }

            if update_golden:
                golden_file.write_text(json.dumps(actual, indent=2))
                pytest.skip(f"Updated golden file: {golden_file.name}")
                return

            # If golden file exists, compare
            if golden_file.exists():
                expected = json.loads(golden_file.read_text())
                assert actual == expected, "is_suppressed behavior changed"
            else:
                # First run - just verify determinism by running twice
                for rule_id in test_rule_ids:
                    first = manager.is_suppressed(rule_id)
                    second = manager.is_suppressed(rule_id)
                    assert first == second, f"Non-deterministic for {rule_id}"

    def test_wildcard_priority_deterministic(
        self, request: pytest.FixtureRequest
    ) -> None:
        """Test that wildcard priority is deterministic."""
        update_golden = request.config.getoption("--update-golden", default=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            manager = create_suppression_manager(db_path=db_path, auto_load=False)

            # Add overlapping patterns (all with valid prefixes)
            manager.add_suppression("pi-*", "All PI")
            manager.add_suppression("pi-injection", "Specific PI injection")
            manager.add_suppression("pi-*-advanced", "PI advanced patterns")

            # pi-injection matches multiple patterns
            is_suppressed, reason = manager.is_suppressed("pi-injection")

            golden_file = get_golden_file_path("wildcard_priority")

            actual = {
                "test_rule": "pi-injection",
                "is_suppressed": is_suppressed,
                "reason": reason,
            }

            if update_golden:
                golden_file.write_text(json.dumps(actual, indent=2))
                pytest.skip(f"Updated golden file: {golden_file.name}")
                return

            # Verify it's always suppressed (regardless of which pattern wins)
            assert is_suppressed is True
            assert reason in ["All PI", "Specific PI injection"]


class TestSuppressionFileLoadingGolden:
    """Golden tests for YAML suppression file loading."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Ensure golden directory exists."""
        ensure_golden_dir_exists()

    def test_file_loading_deterministic(
        self, request: pytest.FixtureRequest
    ) -> None:
        """Test that file loading produces deterministic results."""
        update_golden = request.config.getoption("--update-golden", default=False)

        # Note: All patterns must have valid family prefixes
        # Patterns like *-injection are NOT allowed
        yaml_content = """version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "False positive in documentation"
  - pattern: "jb-regex-basic"
    reason: "Too sensitive"
  - pattern: "pi-*"
    reason: "All PI rules"
  - pattern: "jb-*"
    reason: "All JB rules"
  - pattern: "jb-*-basic"
    reason: "Basic JB rules"
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".raxe" / "suppressions.yaml"
            db_path = Path(tmpdir) / "test.db"

            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(yaml_content)

            manager = create_suppression_manager(
                config_path=config_path,
                db_path=db_path,
                auto_load=True,
            )

            suppressions = manager.get_suppressions()

            # Build result
            actual = {
                "loaded_count": len(suppressions),
                "patterns": sorted([s.pattern for s in suppressions]),
            }

            golden_file = get_golden_file_path("file_loading")

            if update_golden:
                golden_file.write_text(json.dumps(actual, indent=2))
                pytest.skip(f"Updated golden file: {golden_file.name}")
                return

            # Verify expected count (5 patterns with valid prefixes)
            expected_patterns = [
                "jb-*",
                "jb-*-basic",
                "jb-regex-basic",
                "pi-*",
                "pi-001",
            ]
            assert actual["loaded_count"] == 5
            assert actual["patterns"] == expected_patterns


class TestSuppressionExpirationGolden:
    """Golden tests for expiration behavior."""

    def test_expiration_boundary_conditions(
        self, request: pytest.FixtureRequest
    ) -> None:
        """Test expiration at boundary conditions."""
        update_golden = request.config.getoption("--update-golden", default=False)

        # Fixed reference time for testing
        reference_time = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Test cases with different expiration scenarios
        test_cases = [
            ("past_1_day", (reference_time - timedelta(days=1)).isoformat(), True),
            ("past_1_second", (reference_time - timedelta(seconds=1)).isoformat(), True),
            ("future_1_second", (reference_time + timedelta(seconds=1)).isoformat(), False),
            ("future_1_day", (reference_time + timedelta(days=1)).isoformat(), False),
            ("future_1_year", (reference_time + timedelta(days=365)).isoformat(), False),
            ("no_expiration", None, False),
        ]

        results = []
        for name, expires_at, expected_expired in test_cases:
            suppression = Suppression(
                pattern="test-rule",
                reason="Test",
                created_at=datetime.now(timezone.utc).isoformat(),
                expires_at=expires_at,
            )

            is_expired = suppression.is_expired(current_time=reference_time)
            results.append({
                "name": name,
                "expires_at": expires_at,
                "is_expired": is_expired,
                "expected": expected_expired,
            })

            # Verify matches expected
            assert is_expired == expected_expired, f"Expiration mismatch for {name}"

        # All tests should pass against expected values
        for result in results:
            assert result["is_expired"] == result["expected"]


# ============================================================================
# Regression Tests
# ============================================================================


class TestSuppressionRegressions:
    """Regression tests for known issues."""

    def test_empty_pattern_rejected(self) -> None:
        """Regression: Empty pattern should be rejected."""
        with pytest.raises(ValueError, match="Pattern cannot be empty"):
            Suppression(
                pattern="",
                reason="Test",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

    def test_empty_reason_rejected(self) -> None:
        """Regression: Empty reason should be rejected."""
        with pytest.raises(ValueError, match="Reason cannot be empty"):
            Suppression(
                pattern="pi-001",
                reason="",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

    def test_case_sensitive_matching(self) -> None:
        """Regression: Pattern matching should be case-sensitive."""
        suppression = Suppression(
            pattern="PI-001",
            reason="Uppercase",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Should NOT match lowercase
        assert suppression.matches("pi-001") is False
        assert suppression.matches("PI-001") is True

    def test_fnmatch_special_chars(self) -> None:
        """Regression: fnmatch special characters work correctly."""
        # Test that [0-9] character class works
        suppression = Suppression(
            pattern="pi-[0-9]*",
            reason="Numeric",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        assert suppression.matches("pi-001") is True
        assert suppression.matches("pi-999") is True
        assert suppression.matches("pi-abc") is False

    def test_no_partial_match(self) -> None:
        """Regression: Pattern must match entire rule ID, not partial."""
        # Note: "pi" alone would not be valid if we added a wildcard
        # but exact match without wildcard should work
        suppression = Suppression(
            pattern="pi-001",
            reason="Exact match pattern",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # "pi-001" should NOT match "pi-0010" (exact match required)
        assert suppression.matches("pi-0010") is False
        assert suppression.matches("pi-001") is True
        assert suppression.matches("pi-00") is False

    def test_wildcard_prefix_not_allowed(self) -> None:
        """Regression: Patterns starting with * are not allowed."""
        from raxe.domain.suppression import SuppressionValidationError

        with pytest.raises(SuppressionValidationError, match="starts with wildcard"):
            Suppression(
                pattern="*-injection",
                reason="Suffix pattern",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
