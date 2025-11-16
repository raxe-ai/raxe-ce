"""Retention analytics service.

Orchestrates retention calculation by combining domain logic with data access.

CRITICAL: This is application layer - orchestrates but doesn't calculate.
All calculations delegated to domain layer, all I/O to repository.
"""

import logging
from datetime import date, timedelta
from typing import Any

from raxe.domain.analytics import (
    RetentionMetrics,
    calculate_cohort_retention,
    calculate_retention,
    calculate_retention_rate,
)

from .repositories import AnalyticsRepository

logger = logging.getLogger(__name__)


class RetentionService:
    """Service for calculating user retention metrics.

    This service orchestrates:
    1. Data loading from repository (infrastructure)
    2. Retention calculation (domain pure functions)
    3. Result formatting and logging

    CRITICAL: This service does NOT perform calculations itself.
    All business logic is delegated to domain layer functions.
    """

    def __init__(self, repository: AnalyticsRepository):
        """Initialize retention service.

        Args:
            repository: Repository for data access (dependency injection)
        """
        self.repository = repository

    def calculate_user_retention(
        self,
        installation_id: str
    ) -> RetentionMetrics:
        """Calculate retention for a specific user.

        Args:
            installation_id: User's installation identifier

        Returns:
            RetentionMetrics with day 1/7/30 retention calculated

        Example:
            >>> service = RetentionService(repo)
            >>> metrics = service.calculate_user_retention("abc123")
            >>> print(f"Day 1 retention: {metrics.day1_retained}")
        """
        try:
            # Step 1: Load user activity from repository (I/O)
            activity = self.repository.get_user_activity(installation_id)

            if not activity:
                logger.info(f"No activity found for user {installation_id}")
                # Return empty metrics
                return RetentionMetrics(
                    installation_id=installation_id,
                    install_date=date.today(),
                    day1_retained=False,
                    day7_retained=False,
                    day30_retained=False,
                    total_scans=0,
                    last_scan_date=None
                )

            # Step 2: Calculate retention using domain function (pure logic)
            metrics = calculate_retention(
                installation_id=installation_id,
                install_date=activity.first_seen.date(),
                scan_dates=activity.scan_dates
            )

            logger.info(
                f"Calculated retention for {installation_id}: "
                f"day1={metrics.day1_retained}, day7={metrics.day7_retained}, "
                f"day30={metrics.day30_retained}"
            )

            return metrics

        except Exception as e:
            logger.error(f"Failed to calculate retention for {installation_id}: {e}")
            raise

    def calculate_cohort_retention_metrics(
        self,
        cohort_date: date,
        *,
        days_to_check: list[int] | None = None
    ) -> dict[str, Any]:
        """Calculate retention for installation cohort.

        Args:
            cohort_date: Date when users first installed
            days_to_check: Days after install to check (default: [1, 7, 30])

        Returns:
            Dictionary with cohort metrics and individual user retention

        Example:
            >>> service = RetentionService(repo)
            >>> results = service.calculate_cohort_retention_metrics(date(2025, 1, 1))
            >>> print(f"Cohort size: {results['cohort_size']}")
            >>> print(f"Day 1 rate: {results['day1_retention_rate']}%")
        """
        if days_to_check is None:
            days_to_check = [1, 7, 30]

        try:
            # Step 1: Load cohort users from database (I/O)
            cohort_user_ids = self.repository.get_cohort_users(cohort_date)

            if not cohort_user_ids:
                logger.info(f"No users found for cohort {cohort_date}")
                return {
                    "cohort_date": cohort_date.isoformat(),
                    "cohort_size": 0,
                    "day1_retention_rate": 0.0,
                    "day7_retention_rate": 0.0,
                    "day30_retention_rate": 0.0,
                    "users": {}
                }

            # Step 2: Build cohort data structure for domain function
            cohort_data = {}
            for user_id in cohort_user_ids:
                activity = self.repository.get_user_activity(user_id)
                if activity:
                    cohort_data[user_id] = (
                        activity.first_seen.date(),
                        activity.scan_dates
                    )

            # Step 3: Calculate retention using domain function (pure logic)
            retention_by_user = calculate_cohort_retention(cohort_data)

            # Step 4: Calculate aggregate retention rates (pure logic)
            metrics_list = list(retention_by_user.values())
            day1_rate = calculate_retention_rate(metrics_list, "day1")
            day7_rate = calculate_retention_rate(metrics_list, "day7")
            day30_rate = calculate_retention_rate(metrics_list, "day30")

            result = {
                "cohort_date": cohort_date.isoformat(),
                "cohort_size": len(cohort_user_ids),
                "day1_retention_rate": round(day1_rate, 2),
                "day7_retention_rate": round(day7_rate, 2),
                "day30_retention_rate": round(day30_rate, 2),
                "users": {
                    user_id: {
                        "day1_retained": m.day1_retained,
                        "day7_retained": m.day7_retained,
                        "day30_retained": m.day30_retained,
                        "total_scans": m.total_scans
                    }
                    for user_id, m in retention_by_user.items()
                }
            }

            logger.info(
                f"Calculated cohort retention for {cohort_date}: "
                f"size={result['cohort_size']}, "
                f"day1={result['day1_retention_rate']}%, "
                f"day7={result['day7_retention_rate']}%"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to calculate cohort retention: {e}")
            raise

    def calculate_rolling_retention(
        self,
        end_date: date,
        window_days: int = 30
    ) -> dict[str, Any]:
        """Calculate rolling retention over a time window.

        Rolling retention = % of users active in window who return.

        Args:
            end_date: End date for the calculation window
            window_days: Number of days in the window (default: 30)

        Returns:
            Dictionary with rolling retention metrics

        Example:
            >>> service = RetentionService(repo)
            >>> metrics = service.calculate_rolling_retention(date.today(), 30)
            >>> print(f"Retention rate: {metrics['retention_rate']}%")
        """
        start_date = end_date - timedelta(days=window_days)

        try:
            # Step 1: Get all scan events in window (I/O)
            events = self.repository.get_scan_events(
                start_date=start_date,
                end_date=end_date
            )

            if not events:
                logger.info(
                    f"No events found for rolling retention {start_date} to {end_date}"
                )
                return {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "total_users": 0,
                    "returning_users": 0,
                    "retention_rate": 0.0
                }

            # Step 2: Group events by user to determine activity patterns
            user_activity = {}
            for event in events:
                user_id = event.installation_id
                if user_id not in user_activity:
                    user_activity[user_id] = []
                user_activity[user_id].append(event.timestamp.date())

            # Step 3: Calculate retention (users active on 2+ different days)
            total_users = len(user_activity)
            returning_users = sum(
                1 for dates in user_activity.values()
                if len(set(dates)) >= 2  # Active on at least 2 different days
            )

            retention_rate = (
                (returning_users / total_users * 100)
                if total_users > 0
                else 0.0
            )

            result = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_users": total_users,
                "returning_users": returning_users,
                "retention_rate": round(retention_rate, 2)
            }

            logger.info(
                f"Calculated rolling retention {start_date} to {end_date}: "
                f"total={total_users}, returning={returning_users}, "
                f"rate={retention_rate:.1f}%"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to calculate rolling retention: {e}")
            raise
