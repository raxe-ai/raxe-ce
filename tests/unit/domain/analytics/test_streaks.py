"""Unit tests for streak calculation functions.

Tests pure domain logic - no mocks needed, no I/O.
"""

from datetime import date, timedelta

from raxe.domain.analytics.models import StreakMetrics
from raxe.domain.analytics.streaks import (
    calculate_streaks,
    compare_streaks,
)


class TestCalculateStreaks:
    """Test suite for calculate_streaks function."""

    def test_no_scans_returns_zero_streaks(self):
        """User with no scans has zero streaks."""
        result = calculate_streaks(
            installation_id="user1", scan_dates=[], reference_date=date(2025, 1, 15)
        )

        assert result.installation_id == "user1"
        assert result.current_streak == 0
        assert result.longest_streak == 0
        assert result.total_scan_days == 0

    def test_single_scan_today(self):
        """Single scan today creates 1-day streak."""
        today = date(2025, 1, 15)
        result = calculate_streaks(
            installation_id="user1", scan_dates=[today], reference_date=today
        )

        assert result.current_streak == 1
        assert result.longest_streak == 1
        assert result.total_scan_days == 1
        assert result.last_scan_date == today

    def test_single_scan_yesterday(self):
        """Single scan yesterday creates 1-day streak."""
        today = date(2025, 1, 15)
        yesterday = date(2025, 1, 14)
        result = calculate_streaks(
            installation_id="user1", scan_dates=[yesterday], reference_date=today
        )

        assert result.current_streak == 1
        assert result.longest_streak == 1

    def test_single_scan_two_days_ago_breaks_streak(self):
        """Scan from 2 days ago means no current streak."""
        today = date(2025, 1, 15)
        two_days_ago = date(2025, 1, 13)
        result = calculate_streaks(
            installation_id="user1", scan_dates=[two_days_ago], reference_date=today
        )

        assert result.current_streak == 0
        assert result.longest_streak == 1  # Historical streak of 1

    def test_consecutive_days_current_streak(self):
        """Consecutive days through today creates current streak."""
        today = date(2025, 1, 15)
        scan_dates = [
            date(2025, 1, 13),
            date(2025, 1, 14),
            date(2025, 1, 15),
        ]
        result = calculate_streaks(
            installation_id="user1", scan_dates=scan_dates, reference_date=today
        )

        assert result.current_streak == 3
        assert result.longest_streak == 3
        assert result.total_scan_days == 3

    def test_gap_in_middle_breaks_current_streak(self):
        """Gap in scan history breaks the current streak."""
        today = date(2025, 1, 15)
        scan_dates = [
            date(2025, 1, 10),
            date(2025, 1, 11),
            # Gap here
            date(2025, 1, 14),
            date(2025, 1, 15),
        ]
        result = calculate_streaks(
            installation_id="user1", scan_dates=scan_dates, reference_date=today
        )

        assert result.current_streak == 2
        assert result.longest_streak == 2
        assert result.total_scan_days == 4

    def test_longest_streak_in_past(self):
        """Longest streak can be in the past."""
        today = date(2025, 1, 15)
        scan_dates = [
            date(2025, 1, 1),
            date(2025, 1, 2),
            date(2025, 1, 3),
            date(2025, 1, 4),  # 4-day streak in past
            # Gap
            date(2025, 1, 14),
            date(2025, 1, 15),  # 2-day current streak
        ]
        result = calculate_streaks(
            installation_id="user1", scan_dates=scan_dates, reference_date=today
        )

        assert result.current_streak == 2
        assert result.longest_streak == 4  # Historical max
        assert result.total_scan_days == 6

    def test_duplicate_dates_deduplicated(self):
        """Duplicate scan dates should be deduplicated."""
        today = date(2025, 1, 15)
        scan_dates = [
            date(2025, 1, 13),
            date(2025, 1, 13),  # Duplicate
            date(2025, 1, 14),
            date(2025, 1, 14),  # Duplicate
            date(2025, 1, 15),
        ]
        result = calculate_streaks(
            installation_id="user1", scan_dates=scan_dates, reference_date=today
        )

        assert result.current_streak == 3
        assert result.total_scan_days == 3  # Deduplicated

    def test_unsorted_dates_handled(self):
        """Unsorted scan dates should be handled correctly."""
        today = date(2025, 1, 15)
        scan_dates = [
            date(2025, 1, 15),
            date(2025, 1, 13),
            date(2025, 1, 14),  # Out of order
        ]
        result = calculate_streaks(
            installation_id="user1", scan_dates=scan_dates, reference_date=today
        )

        assert result.current_streak == 3
        assert result.longest_streak == 3

    def test_long_streak(self):
        """Test with a long streak."""
        today = date(2025, 2, 15)
        # Create 30-day streak
        scan_dates = [today - timedelta(days=i) for i in range(30)]

        result = calculate_streaks(
            installation_id="user1", scan_dates=scan_dates, reference_date=today
        )

        assert result.current_streak == 30
        assert result.longest_streak == 30
        assert result.total_scan_days == 30

    def test_multiple_streaks_finds_longest(self):
        """Multiple streaks should find the longest."""
        today = date(2025, 1, 31)
        scan_dates = [
            # First streak: 3 days
            date(2025, 1, 1),
            date(2025, 1, 2),
            date(2025, 1, 3),
            # Gap
            # Second streak: 5 days (longest)
            date(2025, 1, 10),
            date(2025, 1, 11),
            date(2025, 1, 12),
            date(2025, 1, 13),
            date(2025, 1, 14),
            # Gap
            # Third streak: 2 days (current)
            date(2025, 1, 30),
            date(2025, 1, 31),
        ]
        result = calculate_streaks(
            installation_id="user1", scan_dates=scan_dates, reference_date=today
        )

        assert result.current_streak == 2
        assert result.longest_streak == 5
        assert result.total_scan_days == 10

    def test_current_streak_equals_longest_when_ongoing(self):
        """Current streak can equal longest streak."""
        today = date(2025, 1, 15)
        scan_dates = [
            date(2025, 1, 13),
            date(2025, 1, 14),
            date(2025, 1, 15),
        ]
        result = calculate_streaks(
            installation_id="user1", scan_dates=scan_dates, reference_date=today
        )

        assert result.current_streak == 3
        assert result.longest_streak == 3

    def test_scan_only_on_install_day(self):
        """Scan only on install day (not today/yesterday)."""
        today = date(2025, 1, 15)
        scan_dates = [date(2025, 1, 1)]  # 14 days ago

        result = calculate_streaks(
            installation_id="user1", scan_dates=scan_dates, reference_date=today
        )

        assert result.current_streak == 0  # Too old
        assert result.longest_streak == 1  # Historical


class TestCompareStreaks:
    """Test suite for compare_streaks function."""

    def test_no_change(self):
        """Identical metrics return zero deltas."""
        streak1 = StreakMetrics("u1", 5, 10, 100, date(2025, 1, 15))
        streak2 = StreakMetrics("u1", 5, 10, 100, date(2025, 1, 15))

        deltas = compare_streaks(streak1, streak2)

        assert deltas["current_streak"] == 0
        assert deltas["longest_streak"] == 0
        assert deltas["total_scan_days"] == 0

    def test_current_streak_increased(self):
        """Current streak increased."""
        current = StreakMetrics("u1", 7, 10, 100, date(2025, 1, 15))
        previous = StreakMetrics("u1", 5, 10, 95, date(2025, 1, 14))

        deltas = compare_streaks(current, previous)

        assert deltas["current_streak"] == 2
        assert deltas["total_scan_days"] == 5

    def test_longest_streak_increased(self):
        """Longest streak increased."""
        current = StreakMetrics("u1", 11, 11, 100, date(2025, 1, 15))
        previous = StreakMetrics("u1", 10, 10, 99, date(2025, 1, 14))

        deltas = compare_streaks(current, previous)

        assert deltas["longest_streak"] == 1
        assert deltas["current_streak"] == 1

    def test_streak_broken(self):
        """Streak was broken."""
        current = StreakMetrics("u1", 0, 10, 100, date(2025, 1, 15))
        previous = StreakMetrics("u1", 10, 10, 99, date(2025, 1, 10))

        deltas = compare_streaks(current, previous)

        assert deltas["current_streak"] == -10  # Streak broken
        assert deltas["longest_streak"] == 0  # Max didn't change

    def test_negative_changes(self):
        """Deltas can be negative (shouldn't happen in practice)."""
        current = StreakMetrics("u1", 3, 8, 95, date(2025, 1, 15))
        previous = StreakMetrics("u1", 5, 10, 100, date(2025, 1, 14))

        deltas = compare_streaks(current, previous)

        assert deltas["current_streak"] < 0
        assert deltas["longest_streak"] < 0
        assert deltas["total_scan_days"] < 0
