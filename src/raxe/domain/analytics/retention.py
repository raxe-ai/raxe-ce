"""Pure retention calculation functions - no I/O.

This module contains pure functions for calculating user retention metrics.
All functions are stateless and perform no I/O operations.

CRITICAL: This is domain layer - NO database, network, or file operations.
"""
from datetime import date, timedelta

from .models import RetentionMetrics


def calculate_retention(
    installation_id: str,
    install_date: date,
    scan_dates: list[date],
) -> RetentionMetrics:
    """Calculate retention metrics for a single user.

    Pure function - takes data, returns data, no I/O.

    Retention windows:
    - Day 1: Scan occurred on install_date + 1 day
    - Day 7: Scan occurred on days 6, 7, or 8 after install
    - Day 30: Scan occurred on days 29, 30, or 31 after install

    Args:
        installation_id: Unique user identifier
        install_date: When user installed RAXE
        scan_dates: List of dates user performed scans (may contain duplicates)

    Returns:
        RetentionMetrics with day 1/7/30 retention calculated

    Example:
        >>> metrics = calculate_retention(
        ...     installation_id="abc123",
        ...     install_date=date(2025, 1, 1),
        ...     scan_dates=[date(2025, 1, 2), date(2025, 1, 8), date(2025, 1, 31)]
        ... )
        >>> metrics.day1_retained
        True
        >>> metrics.day7_retained
        True
        >>> metrics.day30_retained
        True
    """
    if not scan_dates:
        return RetentionMetrics(
            installation_id=installation_id,
            install_date=install_date,
            day1_retained=False,
            day7_retained=False,
            day30_retained=False,
            total_scans=0,
            last_scan_date=None,
        )

    # Convert to set for O(1) lookup
    scan_date_set = set(scan_dates)

    # Day 1 retention: scan on the day after install
    day1_date = install_date + timedelta(days=1)
    day1_retained = day1_date in scan_date_set

    # Day 7 retention: scan between day 6-8 (inclusive)
    day7_retained = any(
        (install_date + timedelta(days=d)) in scan_date_set
        for d in range(6, 9)
    )

    # Day 30 retention: scan between day 29-31 (inclusive)
    day30_retained = any(
        (install_date + timedelta(days=d)) in scan_date_set
        for d in range(29, 32)
    )

    return RetentionMetrics(
        installation_id=installation_id,
        install_date=install_date,
        day1_retained=day1_retained,
        day7_retained=day7_retained,
        day30_retained=day30_retained,
        total_scans=len(scan_dates),
        last_scan_date=max(scan_dates) if scan_dates else None,
    )


def calculate_cohort_retention(
    cohort: dict[str, tuple[date, list[date]]]
) -> dict[str, RetentionMetrics]:
    """Calculate retention for an entire cohort of users.

    Pure function - processes multiple users in batch.

    Args:
        cohort: Map of installation_id -> (install_date, scan_dates)

    Returns:
        Map of installation_id -> RetentionMetrics

    Example:
        >>> cohort = {
        ...     "user1": (date(2025, 1, 1), [date(2025, 1, 2)]),
        ...     "user2": (date(2025, 1, 1), [date(2025, 1, 8)]),
        ... }
        >>> results = calculate_cohort_retention(cohort)
        >>> results["user1"].day1_retained
        True
        >>> results["user2"].day7_retained
        True
    """
    return {
        installation_id: calculate_retention(
            installation_id=installation_id,
            install_date=install_date,
            scan_dates=scan_dates,
        )
        for installation_id, (install_date, scan_dates) in cohort.items()
    }


def calculate_retention_rate(
    retention_metrics: list[RetentionMetrics],
    window: str,
) -> float:
    """Calculate retention rate for a cohort.

    Pure function - aggregates retention metrics.

    Args:
        retention_metrics: List of RetentionMetrics for cohort members
        window: Which retention window to calculate ("day1", "day7", or "day30")

    Returns:
        Retention rate as a percentage (0.0 to 100.0)

    Raises:
        ValueError: If window is not one of "day1", "day7", "day30"

    Example:
        >>> metrics = [
        ...     RetentionMetrics("u1", date(2025, 1, 1), True, True, False, 10, None),
        ...     RetentionMetrics("u2", date(2025, 1, 1), True, False, False, 5, None),
        ...     RetentionMetrics("u3", date(2025, 1, 1), False, False, False, 1, None),
        ... ]
        >>> calculate_retention_rate(metrics, "day1")
        66.66666666666666
    """
    if not retention_metrics:
        return 0.0

    if window not in ("day1", "day7", "day30"):
        raise ValueError(f"Invalid window: {window}. Must be 'day1', 'day7', or 'day30'")

    # Map window to attribute
    attr_map = {
        "day1": "day1_retained",
        "day7": "day7_retained",
        "day30": "day30_retained",
    }

    retained_count = sum(
        1 for m in retention_metrics
        if getattr(m, attr_map[window])
    )

    return (retained_count / len(retention_metrics)) * 100.0
