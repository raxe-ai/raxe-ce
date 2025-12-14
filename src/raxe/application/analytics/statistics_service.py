"""Usage statistics service.

Calculates DAU, WAU, MAU and other aggregate statistics.

CRITICAL: This is application layer - orchestrates but doesn't calculate.
All calculations delegated to domain layer, all I/O to repository.
"""

import logging
from datetime import date, timedelta
from typing import Any

from raxe.domain.analytics import (
    calculate_dau,
    calculate_growth_rate,
    calculate_mau,
    calculate_stickiness,
    calculate_usage_statistics,
    calculate_wau,
)

from .repositories import AnalyticsRepository

logger = logging.getLogger(__name__)


class StatisticsService:
    """Service for calculating usage statistics.

    This service orchestrates:
    1. Data loading from repository (infrastructure)
    2. Statistics calculation (domain pure functions)
    3. Result formatting and caching

    CRITICAL: This service does NOT perform calculations itself.
    All business logic is delegated to domain layer functions.
    """

    def __init__(self, repository: AnalyticsRepository):
        """Initialize statistics service.

        Args:
            repository: Repository for data access (dependency injection)
        """
        self.repository = repository

    def calculate_active_users(
        self,
        target_date: date | None = None
    ) -> dict[str, Any]:
        """Calculate DAU, WAU, and MAU for a given date.

        Args:
            target_date: Date to calculate for (default: today)

        Returns:
            Dictionary with 'dau', 'wau', 'mau', and 'stickiness' metrics

        Example:
            >>> service = StatisticsService(repo)
            >>> metrics = service.calculate_active_users()
            >>> print(f"DAU: {metrics['dau']}, MAU: {metrics['mau']}")
            >>> print(f"Stickiness: {metrics['stickiness']:.1f}%")
        """
        if target_date is None:
            target_date = date.today()

        try:
            # Step 1: Get user activity data from repository (I/O)
            # We need scan dates for all users to calculate DAU/WAU/MAU

            # Get users active in the last 30 days (for MAU calculation)
            user_ids = self.repository.get_active_users(
                target_date=target_date,
                window_days=30
            )

            if not user_ids:
                logger.info(f"No active users found for {target_date}")
                return {
                    "target_date": target_date.isoformat(),
                    "dau": 0,
                    "wau": 0,
                    "mau": 0,
                    "stickiness": 0.0
                }

            # Step 2: Build scan_dates_by_user map for domain functions
            scan_dates_by_user = {}
            for user_id in user_ids:
                activity = self.repository.get_user_activity(
                    user_id,
                    start_date=target_date - timedelta(days=30),
                    end_date=target_date
                )
                if activity and activity.scan_dates:
                    scan_dates_by_user[user_id] = activity.scan_dates

            # Step 3: Calculate metrics using domain functions (pure logic)
            dau = calculate_dau(scan_dates_by_user, target_date)
            wau = calculate_wau(scan_dates_by_user, target_date)
            mau = calculate_mau(scan_dates_by_user, target_date)
            stickiness = calculate_stickiness(dau, mau)

            result = {
                "target_date": target_date.isoformat(),
                "dau": dau,
                "wau": wau,
                "mau": mau,
                "stickiness": round(stickiness, 2)
            }

            logger.info(
                f"Active users for {target_date}: "
                f"DAU={dau}, WAU={wau}, MAU={mau}, "
                f"stickiness={stickiness:.1f}%"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to calculate active users: {e}")
            raise

    def calculate_usage_stats(
        self,
        start_date: date,
        end_date: date
    ) -> dict[str, Any]:
        """Calculate usage statistics for a time period.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period

        Returns:
            Dictionary with usage metrics and statistics

        Example:
            >>> service = StatisticsService(repo)
            >>> stats = service.calculate_usage_stats(
            ...     start_date=date(2025, 1, 1),
            ...     end_date=date(2025, 1, 31)
            ... )
            >>> print(f"Total scans: {stats['total_scans']}")
            >>> print(f"Average scans per user: {stats['avg_scans_per_user']:.1f}")
        """
        try:
            # Step 1: Get all scan events in period (I/O)
            events = self.repository.get_scan_events(
                start_date=start_date,
                end_date=end_date
            )

            if not events:
                logger.info(
                    f"No events found for usage stats {start_date} to {end_date}"
                )
                return {
                    "period_start": start_date.isoformat(),
                    "period_end": end_date.isoformat(),
                    "total_scans": 0,
                    "unique_users": 0,
                    "avg_scans_per_user": 0.0,
                    "threats_detected": 0,
                    "detection_rate": 0.0,
                    "dau": 0,
                    "wau": 0,
                    "mau": 0
                }

            # Step 2: Build scan_dates_by_user for domain functions
            scan_dates_by_user = {}
            threat_count = 0

            for event in events:
                user_id = event.installation_id
                event_date = event.timestamp.date()

                if user_id not in scan_dates_by_user:
                    scan_dates_by_user[user_id] = []
                scan_dates_by_user[user_id].append(event_date)

                if event.has_threats:
                    threat_count += 1

            # Step 3: Calculate statistics using domain functions (pure logic)
            usage_stats = calculate_usage_statistics(
                scan_dates_by_user=scan_dates_by_user,
                period_start=start_date,
                period_end=end_date
            )

            total_scans = usage_stats.total_scans
            detection_rate = (
                (threat_count / total_scans * 100)
                if total_scans > 0
                else 0.0
            )

            result = {
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "total_scans": total_scans,
                "unique_users": len(scan_dates_by_user),
                "avg_scans_per_user": round(usage_stats.avg_scans_per_user, 2),
                "threats_detected": threat_count,
                "detection_rate": round(detection_rate, 2),
                "dau": usage_stats.dau,
                "wau": usage_stats.wau,
                "mau": usage_stats.mau
            }

            logger.info(
                f"Usage stats for {start_date} to {end_date}: "
                f"scans={total_scans}, users={result['unique_users']}, "
                f"avg={usage_stats.avg_scans_per_user:.1f}"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to calculate usage stats: {e}")
            raise

    def calculate_growth_metrics(
        self,
        current_period_end: date,
        *,
        period_days: int = 30
    ) -> dict[str, Any]:
        """Calculate growth metrics comparing two time periods.

        Args:
            current_period_end: End date of current period
            period_days: Length of each period in days (default: 30)

        Returns:
            Dictionary with growth metrics and comparison

        Example:
            >>> service = StatisticsService(repo)
            >>> growth = service.calculate_growth_metrics(date.today())
            >>> print(f"MAU growth: {growth['mau_growth_rate']:.1f}%")
            >>> print(f"Scan growth: {growth['scan_growth_rate']:.1f}%")
        """
        try:
            # Calculate current period stats
            current_start = current_period_end - timedelta(days=period_days - 1)
            current_stats = self.calculate_usage_stats(
                current_start,
                current_period_end
            )

            # Calculate previous period stats
            previous_end = current_start - timedelta(days=1)
            previous_start = previous_end - timedelta(days=period_days - 1)
            previous_stats = self.calculate_usage_stats(
                previous_start,
                previous_end
            )

            # Calculate growth rates using domain functions (pure logic)
            mau_growth = calculate_growth_rate(
                current_stats["mau"],
                previous_stats["mau"]
            )

            scan_growth = calculate_growth_rate(
                current_stats["total_scans"],
                previous_stats["total_scans"]
            )

            user_growth = calculate_growth_rate(
                current_stats["unique_users"],
                previous_stats["unique_users"]
            )

            result = {
                "current_period": {
                    "start": current_start.isoformat(),
                    "end": current_period_end.isoformat(),
                    "mau": current_stats["mau"],
                    "total_scans": current_stats["total_scans"],
                    "unique_users": current_stats["unique_users"]
                },
                "previous_period": {
                    "start": previous_start.isoformat(),
                    "end": previous_end.isoformat(),
                    "mau": previous_stats["mau"],
                    "total_scans": previous_stats["total_scans"],
                    "unique_users": previous_stats["unique_users"]
                },
                "growth": {
                    "mau_growth_rate": round(mau_growth, 2),
                    "scan_growth_rate": round(scan_growth, 2),
                    "user_growth_rate": round(user_growth, 2)
                }
            }

            logger.info(
                f"Growth metrics: MAU={mau_growth:.1f}%, "
                f"scans={scan_growth:.1f}%, users={user_growth:.1f}%"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to calculate growth metrics: {e}")
            raise

    def calculate_user_percentiles(
        self,
        metric: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None
    ) -> dict[str, Any]:
        """Calculate percentiles for a user metric.

        Args:
            metric: Metric to calculate percentiles for ("scans", "threats")
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Dictionary with percentile values (p50, p75, p95, p99)

        Raises:
            ValueError: If metric is not supported

        Example:
            >>> service = StatisticsService(repo)
            >>> percentiles = service.calculate_user_percentiles("scans")
            >>> print(f"Median scans: {percentiles['p50']}")
            >>> print(f"P95 scans: {percentiles['p95']}")
        """
        if metric not in ("scans", "threats"):
            raise ValueError(
                f"Invalid metric: {metric}. Must be 'scans' or 'threats'"
            )

        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        try:
            # Get all users and their activity
            events = self.repository.get_scan_events(
                start_date=start_date,
                end_date=end_date
            )

            if not events:
                logger.info("No events for percentile calculation")
                return {
                    "metric": metric,
                    "p50": 0,
                    "p75": 0,
                    "p95": 0,
                    "p99": 0
                }

            # Count metric per user
            user_counts = {}
            for event in events:
                user_id = event.installation_id
                if user_id not in user_counts:
                    user_counts[user_id] = {"scans": 0, "threats": 0}

                user_counts[user_id]["scans"] += 1
                if event.has_threats:
                    user_counts[user_id]["threats"] += 1

            # Extract values and sort
            values = sorted([
                counts[metric] for counts in user_counts.values()
            ])

            if not values:
                return {
                    "metric": metric,
                    "p50": 0,
                    "p75": 0,
                    "p95": 0,
                    "p99": 0
                }

            # Calculate percentiles
            def percentile(sorted_values: list, p: float) -> int:
                """Calculate percentile from sorted values."""
                if not sorted_values:
                    return 0
                idx = int(len(sorted_values) * p)
                idx = min(idx, len(sorted_values) - 1)
                return sorted_values[idx]

            result = {
                "metric": metric,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_users": len(values),
                "p50": percentile(values, 0.50),
                "p75": percentile(values, 0.75),
                "p95": percentile(values, 0.95),
                "p99": percentile(values, 0.99)
            }

            logger.info(
                f"Percentiles for {metric}: "
                f"p50={result['p50']}, p95={result['p95']}, p99={result['p99']}"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to calculate percentiles: {e}")
            raise
