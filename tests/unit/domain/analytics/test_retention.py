"""Unit tests for retention calculation functions.

Tests pure domain logic - no mocks needed, no I/O.
"""
from datetime import date

import pytest

from raxe.domain.analytics.models import RetentionMetrics
from raxe.domain.analytics.retention import (
    calculate_cohort_retention,
    calculate_retention,
    calculate_retention_rate,
)


class TestCalculateRetention:
    """Test suite for calculate_retention function."""

    def test_no_scans_returns_all_false(self):
        """User with no scans should have no retention."""
        result = calculate_retention(
            installation_id="user1",
            install_date=date(2025, 1, 1),
            scan_dates=[],
        )

        assert result.installation_id == "user1"
        assert result.install_date == date(2025, 1, 1)
        assert result.day1_retained is False
        assert result.day7_retained is False
        assert result.day30_retained is False
        assert result.total_scans == 0
        assert result.last_scan_date is None

    def test_day1_retention_exact_day(self):
        """Scan on day 1 (install_date + 1) should count as retained."""
        install_date = date(2025, 1, 1)
        scan_dates = [date(2025, 1, 2)]  # Day 1

        result = calculate_retention("user1", install_date, scan_dates)

        assert result.day1_retained is True
        assert result.total_scans == 1
        assert result.last_scan_date == date(2025, 1, 2)

    def test_day1_retention_not_on_day1(self):
        """Scan not on day 1 should not count as day 1 retention."""
        install_date = date(2025, 1, 1)
        scan_dates = [date(2025, 1, 3)]  # Day 2, not day 1

        result = calculate_retention("user1", install_date, scan_dates)

        assert result.day1_retained is False

    def test_day7_retention_day_6(self):
        """Scan on day 6 should count as day 7 retention."""
        install_date = date(2025, 1, 1)
        scan_dates = [date(2025, 1, 7)]  # Day 6

        result = calculate_retention("user1", install_date, scan_dates)

        assert result.day7_retained is True

    def test_day7_retention_day_7(self):
        """Scan on day 7 should count as day 7 retention."""
        install_date = date(2025, 1, 1)
        scan_dates = [date(2025, 1, 8)]  # Day 7

        result = calculate_retention("user1", install_date, scan_dates)

        assert result.day7_retained is True

    def test_day7_retention_day_8(self):
        """Scan on day 8 should count as day 7 retention."""
        install_date = date(2025, 1, 1)
        scan_dates = [date(2025, 1, 9)]  # Day 8

        result = calculate_retention("user1", install_date, scan_dates)

        assert result.day7_retained is True

    def test_day7_retention_not_in_window(self):
        """Scan outside day 6-8 window should not count."""
        install_date = date(2025, 1, 1)
        scan_dates = [date(2025, 1, 5)]  # Day 4, too early

        result = calculate_retention("user1", install_date, scan_dates)

        assert result.day7_retained is False

    def test_day30_retention_day_29(self):
        """Scan on day 29 should count as day 30 retention."""
        install_date = date(2025, 1, 1)
        scan_dates = [date(2025, 1, 30)]  # Day 29

        result = calculate_retention("user1", install_date, scan_dates)

        assert result.day30_retained is True

    def test_day30_retention_day_30(self):
        """Scan on day 30 should count as day 30 retention."""
        install_date = date(2025, 1, 1)
        scan_dates = [date(2025, 1, 31)]  # Day 30

        result = calculate_retention("user1", install_date, scan_dates)

        assert result.day30_retained is True

    def test_day30_retention_day_31(self):
        """Scan on day 31 should count as day 30 retention."""
        install_date = date(2025, 1, 1)
        scan_dates = [date(2025, 2, 1)]  # Day 31

        result = calculate_retention("user1", install_date, scan_dates)

        assert result.day30_retained is True

    def test_all_retention_windows(self):
        """User who scans on all retention days."""
        install_date = date(2025, 1, 1)
        scan_dates = [
            date(2025, 1, 2),   # Day 1
            date(2025, 1, 8),   # Day 7
            date(2025, 1, 31),  # Day 30
        ]

        result = calculate_retention("user1", install_date, scan_dates)

        assert result.day1_retained is True
        assert result.day7_retained is True
        assert result.day30_retained is True
        assert result.total_scans == 3
        assert result.last_scan_date == date(2025, 1, 31)

    def test_duplicate_scan_dates(self):
        """Duplicate scan dates should be counted."""
        install_date = date(2025, 1, 1)
        scan_dates = [
            date(2025, 1, 2),
            date(2025, 1, 2),  # Duplicate
            date(2025, 1, 2),  # Duplicate
        ]

        result = calculate_retention("user1", install_date, scan_dates)

        assert result.total_scans == 3  # Duplicates counted
        assert result.day1_retained is True

    def test_last_scan_date_is_max(self):
        """last_scan_date should be the most recent scan."""
        install_date = date(2025, 1, 1)
        scan_dates = [
            date(2025, 1, 5),
            date(2025, 1, 15),  # Most recent
            date(2025, 1, 10),
        ]

        result = calculate_retention("user1", install_date, scan_dates)

        assert result.last_scan_date == date(2025, 1, 15)


class TestCalculateCohortRetention:
    """Test suite for calculate_cohort_retention function."""

    def test_empty_cohort(self):
        """Empty cohort returns empty dict."""
        result = calculate_cohort_retention({})
        assert result == {}

    def test_single_user_cohort(self):
        """Cohort with one user."""
        cohort = {
            "user1": (date(2025, 1, 1), [date(2025, 1, 2)])
        }

        result = calculate_cohort_retention(cohort)

        assert len(result) == 1
        assert "user1" in result
        assert result["user1"].day1_retained is True

    def test_multiple_user_cohort(self):
        """Cohort with multiple users."""
        cohort = {
            "user1": (date(2025, 1, 1), [date(2025, 1, 2)]),
            "user2": (date(2025, 1, 1), [date(2025, 1, 8)]),
            "user3": (date(2025, 1, 1), []),
        }

        result = calculate_cohort_retention(cohort)

        assert len(result) == 3
        assert result["user1"].day1_retained is True
        assert result["user2"].day7_retained is True
        assert result["user3"].total_scans == 0


class TestCalculateRetentionRate:
    """Test suite for calculate_retention_rate function."""

    def test_empty_list_returns_zero(self):
        """Empty metrics list returns 0%."""
        result = calculate_retention_rate([], "day1")
        assert result == 0.0

    def test_all_retained_returns_100(self):
        """All users retained returns 100%."""
        metrics = [
            RetentionMetrics("u1", date(2025, 1, 1), True, True, True, 10, None),
            RetentionMetrics("u2", date(2025, 1, 1), True, True, True, 5, None),
        ]

        result = calculate_retention_rate(metrics, "day1")
        assert result == 100.0

    def test_none_retained_returns_zero(self):
        """No users retained returns 0%."""
        metrics = [
            RetentionMetrics("u1", date(2025, 1, 1), False, False, False, 0, None),
            RetentionMetrics("u2", date(2025, 1, 1), False, False, False, 0, None),
        ]

        result = calculate_retention_rate(metrics, "day1")
        assert result == 0.0

    def test_partial_retention(self):
        """Some users retained calculates correct percentage."""
        metrics = [
            RetentionMetrics("u1", date(2025, 1, 1), True, False, False, 1, None),
            RetentionMetrics("u2", date(2025, 1, 1), False, False, False, 0, None),
            RetentionMetrics("u3", date(2025, 1, 1), True, False, False, 1, None),
        ]

        result = calculate_retention_rate(metrics, "day1")
        assert result == pytest.approx(66.66666666666666)

    def test_day7_retention_rate(self):
        """Calculate day 7 retention rate."""
        metrics = [
            RetentionMetrics("u1", date(2025, 1, 1), True, True, False, 10, None),
            RetentionMetrics("u2", date(2025, 1, 1), True, False, False, 5, None),
            RetentionMetrics("u3", date(2025, 1, 1), True, True, False, 8, None),
            RetentionMetrics("u4", date(2025, 1, 1), False, False, False, 1, None),
        ]

        result = calculate_retention_rate(metrics, "day7")
        assert result == 50.0  # 2 out of 4

    def test_day30_retention_rate(self):
        """Calculate day 30 retention rate."""
        metrics = [
            RetentionMetrics("u1", date(2025, 1, 1), True, True, True, 30, None),
            RetentionMetrics("u2", date(2025, 1, 1), True, True, False, 15, None),
        ]

        result = calculate_retention_rate(metrics, "day30")
        assert result == 50.0  # 1 out of 2

    def test_invalid_window_raises_error(self):
        """Invalid window parameter raises ValueError."""
        metrics = [
            RetentionMetrics("u1", date(2025, 1, 1), True, True, True, 10, None),
        ]

        with pytest.raises(ValueError, match="Invalid window"):
            calculate_retention_rate(metrics, "day99")
