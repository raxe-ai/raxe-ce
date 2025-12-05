"""Unit tests for usage statistics functions.

Tests pure domain logic - no mocks needed, no I/O.
"""
from datetime import date

from raxe.domain.analytics.statistics import (
    calculate_dau,
    calculate_growth_rate,
    calculate_mau,
    calculate_stickiness,
    calculate_usage_statistics,
    calculate_wau,
)


class TestCalculateDAU:
    """Test suite for calculate_dau function."""

    def test_no_users_returns_zero(self):
        """Empty user data returns 0 DAU."""
        result = calculate_dau({}, date(2025, 1, 15))
        assert result == 0

    def test_no_scans_on_target_date(self):
        """No scans on target date returns 0 DAU."""
        data = {
            "user1": [date(2025, 1, 14)],  # Day before
            "user2": [date(2025, 1, 16)],  # Day after
        }
        result = calculate_dau(data, date(2025, 1, 15))
        assert result == 0

    def test_single_user_on_target_date(self):
        """Single user scanned on target date."""
        data = {
            "user1": [date(2025, 1, 15)],
            "user2": [date(2025, 1, 14)],
        }
        result = calculate_dau(data, date(2025, 1, 15))
        assert result == 1

    def test_multiple_users_on_target_date(self):
        """Multiple users scanned on target date."""
        target = date(2025, 1, 15)
        data = {
            "user1": [target, date(2025, 1, 14)],
            "user2": [target],
            "user3": [target, date(2025, 1, 16)],
            "user4": [date(2025, 1, 14)],  # Not on target
        }
        result = calculate_dau(data, target)
        assert result == 3

    def test_user_with_multiple_scans_same_day_counted_once(self):
        """User with multiple scans on same day counted once."""
        target = date(2025, 1, 15)
        data = {
            "user1": [target, target, target],  # 3 scans same day
            "user2": [target],
        }
        result = calculate_dau(data, target)
        assert result == 2  # Still 2 unique users


class TestCalculateWAU:
    """Test suite for calculate_wau function."""

    def test_no_users_returns_zero(self):
        """Empty user data returns 0 WAU."""
        result = calculate_wau({}, date(2025, 1, 15))
        assert result == 0

    def test_no_scans_in_week(self):
        """No scans in week returns 0 WAU."""
        week_end = date(2025, 1, 15)
        data = {
            "user1": [date(2025, 1, 8)],  # 7 days before window
            "user2": [date(2025, 1, 1)],  # 14 days before window
        }
        result = calculate_wau(data, week_end)
        assert result == 0

    def test_scan_on_week_end(self):
        """Scan on week_end counts."""
        week_end = date(2025, 1, 15)
        data = {
            "user1": [week_end],
        }
        result = calculate_wau(data, week_end)
        assert result == 1

    def test_scan_on_week_start(self):
        """Scan on week_start (week_end - 6 days) counts."""
        week_end = date(2025, 1, 15)
        week_start = date(2025, 1, 9)  # 6 days before
        data = {
            "user1": [week_start],
        }
        result = calculate_wau(data, week_end)
        assert result == 1

    def test_scan_before_week_start_excluded(self):
        """Scan before week_start excluded."""
        week_end = date(2025, 1, 15)
        too_early = date(2025, 1, 8)  # 7 days before
        data = {
            "user1": [too_early],
        }
        result = calculate_wau(data, week_end)
        assert result == 0

    def test_multiple_users_in_week(self):
        """Multiple users with scans in week."""
        week_end = date(2025, 1, 15)
        data = {
            "user1": [date(2025, 1, 15)],  # Last day
            "user2": [date(2025, 1, 10)],  # Middle of week
            "user3": [date(2025, 1, 9)],   # First day
            "user4": [date(2025, 1, 8)],   # Outside window
        }
        result = calculate_wau(data, week_end)
        assert result == 3

    def test_user_scanned_multiple_days_counted_once(self):
        """User who scanned multiple days counted once."""
        week_end = date(2025, 1, 15)
        data = {
            "user1": [
                date(2025, 1, 9),
                date(2025, 1, 10),
                date(2025, 1, 15),
            ],
        }
        result = calculate_wau(data, week_end)
        assert result == 1  # One unique user


class TestCalculateMAU:
    """Test suite for calculate_mau function."""

    def test_no_users_returns_zero(self):
        """Empty user data returns 0 MAU."""
        result = calculate_mau({}, date(2025, 1, 31))
        assert result == 0

    def test_no_scans_in_month(self):
        """No scans in month returns 0 MAU."""
        month_end = date(2025, 1, 31)
        data = {
            "user1": [date(2025, 1, 1)],  # 30 days before window
            "user2": [date(2024, 12, 31)],  # Previous year
        }
        result = calculate_mau(data, month_end)
        assert result == 0

    def test_scan_on_month_end(self):
        """Scan on month_end counts."""
        month_end = date(2025, 1, 31)
        data = {
            "user1": [month_end],
        }
        result = calculate_mau(data, month_end)
        assert result == 1

    def test_scan_on_month_start(self):
        """Scan on month_start (month_end - 29 days) counts."""
        month_end = date(2025, 1, 31)
        month_start = date(2025, 1, 2)  # 29 days before
        data = {
            "user1": [month_start],
        }
        result = calculate_mau(data, month_end)
        assert result == 1

    def test_scan_before_month_start_excluded(self):
        """Scan before month_start excluded."""
        month_end = date(2025, 1, 31)
        too_early = date(2025, 1, 1)  # 30 days before
        data = {
            "user1": [too_early],
        }
        result = calculate_mau(data, month_end)
        assert result == 0

    def test_multiple_users_in_month(self):
        """Multiple users with scans in month."""
        month_end = date(2025, 1, 31)
        data = {
            "user1": [date(2025, 1, 31)],  # Last day
            "user2": [date(2025, 1, 15)],  # Middle
            "user3": [date(2025, 1, 2)],   # First day
            "user4": [date(2025, 1, 1)],   # Outside window
        }
        result = calculate_mau(data, month_end)
        assert result == 3

    def test_thirty_day_window(self):
        """MAU uses 30-day window (not calendar month)."""
        month_end = date(2025, 2, 15)
        # 30 days before is Jan 16
        data = {
            "user1": [date(2025, 1, 16)],  # Exactly 30 days (outside)
            "user2": [date(2025, 1, 17)],  # 29 days (inside)
        }
        result = calculate_mau(data, month_end)
        assert result == 1  # Only user2 in window


class TestCalculateUsageStatistics:
    """Test suite for calculate_usage_statistics function."""

    def test_empty_data_returns_zeros(self):
        """Empty data returns all zeros."""
        result = calculate_usage_statistics(
            {},
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
        )

        assert result.dau == 0
        assert result.wau == 0
        assert result.mau == 0
        assert result.total_scans == 0
        assert result.avg_scans_per_user == 0.0

    def test_filters_scans_to_period(self):
        """Only scans within period are counted."""
        data = {
            "user1": [
                date(2024, 12, 31),  # Before period
                date(2025, 1, 15),   # In period
                date(2025, 2, 1),    # After period
            ],
        }
        result = calculate_usage_statistics(
            data,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
        )

        assert result.total_scans == 1  # Only middle scan

    def test_calculates_all_metrics(self):
        """Calculates DAU, WAU, MAU correctly."""
        period_end = date(2025, 1, 31)
        data = {
            "user1": [period_end],
            "user2": [date(2025, 1, 25)],  # In WAU window
            "user3": [date(2025, 1, 15)],  # In MAU window only
        }
        result = calculate_usage_statistics(
            data,
            period_start=date(2025, 1, 1),
            period_end=period_end,
        )

        assert result.dau == 1   # user1
        assert result.wau == 2   # user1, user2
        assert result.mau == 3   # all users

    def test_calculates_total_scans(self):
        """Total scans is sum of all scans in period."""
        data = {
            "user1": [date(2025, 1, 15), date(2025, 1, 16)],
            "user2": [date(2025, 1, 15)],
        }
        result = calculate_usage_statistics(
            data,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
        )

        assert result.total_scans == 3

    def test_calculates_avg_scans_per_user(self):
        """Average scans per user is total / active users."""
        data = {
            "user1": [date(2025, 1, 15), date(2025, 1, 16)],  # 2 scans
            "user2": [date(2025, 1, 15)],  # 1 scan
            "user3": [],  # No scans, not active
        }
        result = calculate_usage_statistics(
            data,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
        )

        assert result.avg_scans_per_user == 1.5  # 3 scans / 2 active users

    def test_period_dates_in_result(self):
        """Period start/end dates are in result."""
        result = calculate_usage_statistics(
            {},
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
        )

        assert result.period_start == date(2025, 1, 1)
        assert result.period_end == date(2025, 1, 31)


class TestCalculateStickiness:
    """Test suite for calculate_stickiness function."""

    def test_zero_mau_returns_zero(self):
        """Zero MAU returns 0% stickiness."""
        result = calculate_stickiness(dau=0, mau=0)
        assert result == 0.0

    def test_dau_equals_mau_is_100_percent(self):
        """DAU == MAU returns 100% stickiness."""
        result = calculate_stickiness(dau=100, mau=100)
        assert result == 100.0

    def test_half_daily_users(self):
        """50% of monthly users are daily."""
        result = calculate_stickiness(dau=50, mau=100)
        assert result == 50.0

    def test_quarter_daily_users(self):
        """25% of monthly users are daily."""
        result = calculate_stickiness(dau=25, mau=100)
        assert result == 25.0


class TestCalculateGrowthRate:
    """Test suite for calculate_growth_rate function."""

    def test_zero_previous_zero_current_returns_zero(self):
        """0 to 0 users is 0% growth."""
        result = calculate_growth_rate(current_mau=0, previous_mau=0)
        assert result == 0.0

    def test_zero_previous_nonzero_current_returns_100(self):
        """0 to N users is 100% growth."""
        result = calculate_growth_rate(current_mau=100, previous_mau=0)
        assert result == 100.0

    def test_positive_growth(self):
        """Growth from 100 to 120 is 20%."""
        result = calculate_growth_rate(current_mau=120, previous_mau=100)
        assert result == 20.0

    def test_negative_growth(self):
        """Decline from 100 to 80 is -20%."""
        result = calculate_growth_rate(current_mau=80, previous_mau=100)
        assert result == -20.0

    def test_no_growth(self):
        """Same MAU is 0% growth."""
        result = calculate_growth_rate(current_mau=100, previous_mau=100)
        assert result == 0.0

    def test_large_growth(self):
        """100 to 300 is 200% growth."""
        result = calculate_growth_rate(current_mau=300, previous_mau=100)
        assert result == 200.0
