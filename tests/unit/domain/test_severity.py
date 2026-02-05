"""Unit tests for severity utility functions."""

from __future__ import annotations

from raxe.domain.severity import (
    SEVERITY_ORDER,
    compare_severity,
    get_highest_severity,
    get_severity_value,
    is_severity_at_least,
)


class TestSeverityOrder:
    """Tests for SEVERITY_ORDER constant."""

    def test_severity_order_values(self):
        """Test that severity values are correctly ordered."""
        assert SEVERITY_ORDER["NONE"] == 0
        assert SEVERITY_ORDER["LOW"] == 1
        assert SEVERITY_ORDER["MEDIUM"] == 2
        assert SEVERITY_ORDER["HIGH"] == 3
        assert SEVERITY_ORDER["CRITICAL"] == 4

    def test_severity_order_is_increasing(self):
        """Test that severity values increase."""
        severities = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
        for i in range(len(severities) - 1):
            assert SEVERITY_ORDER[severities[i]] < SEVERITY_ORDER[severities[i + 1]]


class TestGetSeverityValue:
    """Tests for get_severity_value function."""

    def test_known_severities(self):
        """Test known severity values."""
        assert get_severity_value("CRITICAL") == 4
        assert get_severity_value("HIGH") == 3
        assert get_severity_value("MEDIUM") == 2
        assert get_severity_value("LOW") == 1
        assert get_severity_value("NONE") == 0

    def test_case_insensitive(self):
        """Test case insensitivity."""
        assert get_severity_value("critical") == 4
        assert get_severity_value("Critical") == 4
        assert get_severity_value("CRITICAL") == 4
        assert get_severity_value("high") == 3
        assert get_severity_value("High") == 3

    def test_none_returns_zero(self):
        """Test that None returns 0."""
        assert get_severity_value(None) == 0

    def test_unknown_returns_zero(self):
        """Test that unknown severity returns 0."""
        assert get_severity_value("UNKNOWN") == 0
        assert get_severity_value("invalid") == 0


class TestCompareSeverity:
    """Tests for compare_severity function."""

    def test_greater_than(self):
        """Test greater than comparison."""
        assert compare_severity("HIGH", "MEDIUM") == 1
        assert compare_severity("CRITICAL", "LOW") == 1

    def test_less_than(self):
        """Test less than comparison."""
        assert compare_severity("LOW", "HIGH") == -1
        assert compare_severity("MEDIUM", "CRITICAL") == -1

    def test_equal(self):
        """Test equal comparison."""
        assert compare_severity("HIGH", "HIGH") == 0
        assert compare_severity("CRITICAL", "CRITICAL") == 0

    def test_none_handling(self):
        """Test handling of None values."""
        assert compare_severity(None, "HIGH") == -1
        assert compare_severity("HIGH", None) == 1
        assert compare_severity(None, None) == 0


class TestIsSeverityAtLeast:
    """Tests for is_severity_at_least function."""

    def test_meets_threshold(self):
        """Test when severity meets threshold."""
        assert is_severity_at_least("HIGH", "HIGH") is True
        assert is_severity_at_least("CRITICAL", "HIGH") is True
        assert is_severity_at_least("CRITICAL", "MEDIUM") is True

    def test_below_threshold(self):
        """Test when severity is below threshold."""
        assert is_severity_at_least("MEDIUM", "HIGH") is False
        assert is_severity_at_least("LOW", "HIGH") is False
        assert is_severity_at_least("NONE", "LOW") is False

    def test_none_handling(self):
        """Test handling of None severity."""
        assert is_severity_at_least(None, "HIGH") is False
        assert is_severity_at_least(None, "NONE") is True


class TestGetHighestSeverity:
    """Tests for get_highest_severity function."""

    def test_finds_highest(self):
        """Test finding highest severity."""
        assert get_highest_severity(["LOW", "HIGH", "MEDIUM"]) == "HIGH"
        assert get_highest_severity(["CRITICAL", "LOW"]) == "CRITICAL"
        assert get_highest_severity(["MEDIUM"]) == "MEDIUM"

    def test_empty_list(self):
        """Test empty list returns None."""
        assert get_highest_severity([]) is None

    def test_with_none_values(self):
        """Test handling of None values in list."""
        assert get_highest_severity([None, "HIGH", None]) == "HIGH"
        assert get_highest_severity([None, None]) is None

    def test_case_normalization(self):
        """Test that result is uppercase."""
        assert get_highest_severity(["low", "high"]) == "HIGH"
