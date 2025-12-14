"""Pure streak calculation functions - no I/O.

This module contains pure functions for calculating user engagement streaks.
All functions are stateless and perform no I/O operations.

CRITICAL: This is domain layer - NO database, network, or file operations.
"""
from datetime import date, timedelta

from .models import StreakMetrics


def calculate_streaks(
    installation_id: str,
    scan_dates: list[date],
    *,
    reference_date: date | None = None,
) -> StreakMetrics:
    """Calculate streak metrics for a user.

    Pure function - takes sorted scan dates, returns streak metrics.

    A "streak" is consecutive days with at least one scan. Current streak
    only counts if the last scan was today or yesterday.

    Args:
        installation_id: Unique user identifier
        scan_dates: List of dates user performed scans (will be sorted/deduped)
        reference_date: Date to use as "today" (defaults to date.today(), for testing)

    Returns:
        StreakMetrics with current and longest streaks

    Example:
        >>> metrics = calculate_streaks(
        ...     installation_id="abc123",
        ...     scan_dates=[
        ...         date(2025, 1, 1),
        ...         date(2025, 1, 2),
        ...         date(2025, 1, 3),
        ...         date(2025, 1, 5),  # Gap here
        ...         date(2025, 1, 6),
        ...     ],
        ...     reference_date=date(2025, 1, 6)
        ... )
        >>> metrics.longest_streak
        3
        >>> metrics.current_streak
        2
    """
    if reference_date is None:
        reference_date = date.today()

    if not scan_dates:
        return StreakMetrics(
            installation_id=installation_id,
            current_streak=0,
            longest_streak=0,
            total_scan_days=0,
            last_scan_date=reference_date,
        )

    # Sort and deduplicate scan dates
    unique_dates = sorted(set(scan_dates))

    # Calculate current streak (from reference_date backwards)
    current_streak = _calculate_current_streak(unique_dates, reference_date)

    # Calculate longest streak (historical)
    longest_streak = _calculate_longest_streak(unique_dates)

    # Longest streak is at least as long as current streak
    longest_streak = max(longest_streak, current_streak)

    return StreakMetrics(
        installation_id=installation_id,
        current_streak=current_streak,
        longest_streak=longest_streak,
        total_scan_days=len(unique_dates),
        last_scan_date=unique_dates[-1],
    )


def _calculate_current_streak(unique_dates: list[date], reference_date: date) -> int:
    """Calculate current streak from reference_date backwards.

    A current streak only counts if the last scan was today or yesterday
    relative to reference_date.

    Args:
        unique_dates: Sorted list of unique scan dates
        reference_date: Date to use as "today"

    Returns:
        Current consecutive day streak (0 if broken)
    """
    yesterday = reference_date - timedelta(days=1)

    # Current streak only exists if last scan was today or yesterday
    if unique_dates[-1] not in (reference_date, yesterday):
        return 0

    current_streak = 1

    # Walk backwards counting consecutive days
    for i in range(len(unique_dates) - 2, -1, -1):
        expected_prev_date = unique_dates[i + 1] - timedelta(days=1)
        if unique_dates[i] == expected_prev_date:
            current_streak += 1
        else:
            break

    return current_streak


def _calculate_longest_streak(unique_dates: list[date]) -> int:
    """Calculate longest historical streak.

    Args:
        unique_dates: Sorted list of unique scan dates

    Returns:
        Longest consecutive day streak ever achieved
    """
    if not unique_dates:
        return 0

    longest_streak = 1
    current_run = 1

    for i in range(1, len(unique_dates)):
        days_diff = (unique_dates[i] - unique_dates[i - 1]).days

        if days_diff == 1:
            # Consecutive day - extend current run
            current_run += 1
            longest_streak = max(longest_streak, current_run)
        else:
            # Gap - reset current run
            current_run = 1

    return longest_streak


def compare_streaks(
    current: StreakMetrics,
    previous: StreakMetrics,
) -> dict[str, int]:
    """Compare two streak metrics to show change.

    Pure function - calculates deltas between metrics.

    Args:
        current: Current streak metrics
        previous: Previous streak metrics

    Returns:
        Dictionary with delta values for each metric

    Example:
        >>> current = StreakMetrics("u1", 5, 10, 100, date(2025, 1, 6))
        >>> previous = StreakMetrics("u1", 3, 8, 95, date(2025, 1, 5))
        >>> deltas = compare_streaks(current, previous)
        >>> deltas["current_streak"]
        2
        >>> deltas["longest_streak"]
        2
    """
    return {
        "current_streak": current.current_streak - previous.current_streak,
        "longest_streak": current.longest_streak - previous.longest_streak,
        "total_scan_days": current.total_scan_days - previous.total_scan_days,
    }
