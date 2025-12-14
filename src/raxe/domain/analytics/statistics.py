"""Pure usage statistics functions - no I/O.

This module contains pure functions for calculating usage statistics (DAU, WAU, MAU).
All functions are stateless and perform no I/O operations.

CRITICAL: This is domain layer - NO database, network, or file operations.
"""
from datetime import date, timedelta

from .models import UsageStatistics


def calculate_dau(
    scan_dates_by_user: dict[str, list[date]],
    target_date: date,
) -> int:
    """Calculate Daily Active Users for a specific date.

    Pure function - counts unique users who scanned on target date.

    Args:
        scan_dates_by_user: Map of user_id -> list of scan dates
        target_date: Date to calculate DAU for

    Returns:
        Number of unique users who scanned on target_date

    Example:
        >>> data = {
        ...     "user1": [date(2025, 1, 15), date(2025, 1, 16)],
        ...     "user2": [date(2025, 1, 15)],
        ...     "user3": [date(2025, 1, 14)],
        ... }
        >>> calculate_dau(data, date(2025, 1, 15))
        2
    """
    active_users = {
        user_id
        for user_id, dates in scan_dates_by_user.items()
        if target_date in dates
    }
    return len(active_users)


def calculate_wau(
    scan_dates_by_user: dict[str, list[date]],
    week_end: date,
) -> int:
    """Calculate Weekly Active Users for week ending on week_end.

    Pure function - counts unique users who scanned in last 7 days.

    Args:
        scan_dates_by_user: Map of user_id -> list of scan dates
        week_end: Last day of the week to calculate WAU for

    Returns:
        Number of unique users who scanned in the 7-day window

    Example:
        >>> data = {
        ...     "user1": [date(2025, 1, 10), date(2025, 1, 15)],
        ...     "user2": [date(2025, 1, 15)],
        ...     "user3": [date(2025, 1, 8)],  # Outside window
        ... }
        >>> calculate_wau(data, date(2025, 1, 15))
        2
    """
    week_start = week_end - timedelta(days=6)
    active_users = {
        user_id
        for user_id, dates in scan_dates_by_user.items()
        if any(week_start <= d <= week_end for d in dates)
    }
    return len(active_users)


def calculate_mau(
    scan_dates_by_user: dict[str, list[date]],
    month_end: date,
) -> int:
    """Calculate Monthly Active Users for month ending on month_end.

    Pure function - counts unique users who scanned in last 30 days.

    Args:
        scan_dates_by_user: Map of user_id -> list of scan dates
        month_end: Last day of the month to calculate MAU for

    Returns:
        Number of unique users who scanned in the 30-day window

    Example:
        >>> data = {
        ...     "user1": [date(2025, 1, 1), date(2025, 1, 31)],
        ...     "user2": [date(2025, 1, 31)],
        ...     "user3": [date(2024, 12, 31)],  # Outside window
        ... }
        >>> calculate_mau(data, date(2025, 1, 31))
        2
    """
    month_start = month_end - timedelta(days=29)
    active_users = {
        user_id
        for user_id, dates in scan_dates_by_user.items()
        if any(month_start <= d <= month_end for d in dates)
    }
    return len(active_users)


def calculate_usage_statistics(
    scan_dates_by_user: dict[str, list[date]],
    period_start: date,
    period_end: date,
) -> UsageStatistics:
    """Calculate comprehensive usage statistics for a period.

    Pure function - aggregates all usage metrics.

    Args:
        scan_dates_by_user: Map of user_id -> list of scan dates
        period_start: Start of the measurement period
        period_end: End of the measurement period

    Returns:
        UsageStatistics with DAU, WAU, MAU, and scan metrics

    Example:
        >>> data = {
        ...     "user1": [date(2025, 1, 15), date(2025, 1, 16)],
        ...     "user2": [date(2025, 1, 15)],
        ... }
        >>> stats = calculate_usage_statistics(data, date(2025, 1, 1), date(2025, 1, 16))
        >>> stats.total_scans
        3
        >>> stats.dau
        1
    """
    # Filter scans within period
    period_scans = {
        user_id: [d for d in dates if period_start <= d <= period_end]
        for user_id, dates in scan_dates_by_user.items()
    }

    total_scans = sum(len(dates) for dates in period_scans.values())
    active_users = len([dates for dates in period_scans.values() if dates])

    return UsageStatistics(
        period_start=period_start,
        period_end=period_end,
        dau=calculate_dau(scan_dates_by_user, period_end),
        wau=calculate_wau(scan_dates_by_user, period_end),
        mau=calculate_mau(scan_dates_by_user, period_end),
        total_scans=total_scans,
        avg_scans_per_user=total_scans / active_users if active_users > 0 else 0.0,
    )


def calculate_stickiness(dau: int, mau: int) -> float:
    """Calculate stickiness ratio (DAU/MAU).

    Pure function - calculates engagement ratio.

    Stickiness measures how many of your monthly users are active daily.
    Higher is better (max 100% if DAU == MAU).

    Args:
        dau: Daily Active Users
        mau: Monthly Active Users

    Returns:
        Stickiness ratio as percentage (0.0 to 100.0)

    Example:
        >>> calculate_stickiness(dau=50, mau=200)
        25.0
    """
    if mau == 0:
        return 0.0
    return (dau / mau) * 100.0


def calculate_growth_rate(
    current_mau: int,
    previous_mau: int,
) -> float:
    """Calculate month-over-month growth rate.

    Pure function - calculates percentage change.

    Args:
        current_mau: Current month's MAU
        previous_mau: Previous month's MAU

    Returns:
        Growth rate as percentage (can be negative)

    Example:
        >>> calculate_growth_rate(current_mau=120, previous_mau=100)
        20.0
        >>> calculate_growth_rate(current_mau=80, previous_mau=100)
        -20.0
    """
    if previous_mau == 0:
        return 0.0 if current_mau == 0 else 100.0

    return ((current_mau - previous_mau) / previous_mau) * 100.0
