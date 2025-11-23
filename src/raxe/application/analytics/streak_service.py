"""Streak tracking service.

Manages user activity streaks and related achievements.

CRITICAL: This is application layer - orchestrates but doesn't calculate.
All calculations delegated to domain layer, all I/O to repository.
"""

import logging
from datetime import date
from typing import Any

from raxe.domain.analytics import StreakMetrics, calculate_streaks, compare_streaks

from .repositories import AnalyticsRepository

logger = logging.getLogger(__name__)


class StreakService:
    """Service for tracking and managing user activity streaks.

    This service orchestrates:
    1. Data loading from repository (infrastructure)
    2. Streak calculation (domain pure functions)
    3. Achievement checking and saving

    CRITICAL: This service does NOT perform calculations itself.
    All business logic is delegated to domain layer functions.
    """

    def __init__(self, repository: AnalyticsRepository):
        """Initialize streak service.

        Args:
            repository: Repository for data access (dependency injection)
        """
        self.repository = repository

    def get_user_streak(
        self,
        installation_id: str,
        *,
        as_of_date: date | None = None
    ) -> StreakMetrics:
        """Get current and longest streak for a user.

        Args:
            installation_id: User's installation identifier
            as_of_date: Calculate streak as of this date (default: today)

        Returns:
            StreakMetrics with current and longest streaks

        Example:
            >>> service = StreakService(repo)
            >>> metrics = service.get_user_streak("abc123")
            >>> print(f"Current streak: {metrics.current_streak} days")
            >>> print(f"Longest streak: {metrics.longest_streak} days")
        """
        if as_of_date is None:
            as_of_date = date.today()

        try:
            # Step 1: Load user activity from repository (I/O)
            activity = self.repository.get_user_activity(
                installation_id=installation_id,
                end_date=as_of_date
            )

            if not activity:
                logger.info(f"No activity found for user {installation_id}")
                return StreakMetrics(
                    installation_id=installation_id,
                    current_streak=0,
                    longest_streak=0,
                    total_scan_days=0,
                    last_scan_date=as_of_date
                )

            # Step 2: Calculate streak using domain function (pure logic)
            streak_metrics = calculate_streaks(
                installation_id=installation_id,
                scan_dates=activity.scan_dates,
                reference_date=as_of_date
            )

            logger.info(
                f"Calculated streak for {installation_id}: "
                f"current={streak_metrics.current_streak}, "
                f"longest={streak_metrics.longest_streak}, "
                f"total_days={streak_metrics.total_scan_days}"
            )

            return streak_metrics

        except Exception as e:
            logger.error(f"Failed to calculate streak for {installation_id}: {e}")
            raise

    def get_active_streak_users(
        self,
        *,
        min_streak: int = 1,
        reference_date: date | None = None
    ) -> list[dict[str, Any]]:
        """Get users who currently have an active streak.

        Args:
            min_streak: Minimum streak length to include (default: 1)
            reference_date: Date to check streaks as of (default: today)

        Returns:
            List of dictionaries with user streak information

        Example:
            >>> service = StreakService(repo)
            >>> active_users = service.get_active_streak_users(min_streak=7)
            >>> for user in active_users:
            ...     print(f"{user['installation_id']}: {user['current_streak']} days")
        """
        if reference_date is None:
            reference_date = date.today()

        try:
            # Step 1: Get all active users in the last 2 days (I/O)
            # (to find users who might have an active streak)
            active_user_ids = self.repository.get_active_users(
                target_date=reference_date,
                window_days=2
            )

            if not active_user_ids:
                logger.info("No active users found for streak check")
                return []

            # Step 2: Calculate streaks for all active users
            active_streaks = []
            for user_id in active_user_ids:
                streak_metrics = self.get_user_streak(
                    user_id,
                    as_of_date=reference_date
                )

                # Filter by minimum streak length
                if streak_metrics.current_streak >= min_streak:
                    active_streaks.append({
                        "installation_id": user_id,
                        "current_streak": streak_metrics.current_streak,
                        "longest_streak": streak_metrics.longest_streak,
                        "total_scan_days": streak_metrics.total_scan_days,
                        "last_scan_date": streak_metrics.last_scan_date.isoformat()
                    })

            # Sort by streak length (descending)
            active_streaks.sort(
                key=lambda x: x["current_streak"],
                reverse=True
            )

            logger.info(
                f"Found {len(active_streaks)} users with active streaks >= {min_streak}"
            )

            return active_streaks

        except Exception as e:
            logger.error(f"Failed to get active streak users: {e}")
            raise

    def get_streak_leaderboard(
        self,
        *,
        limit: int = 10,
        metric: str = "current_streak"
    ) -> list[dict[str, Any]]:
        """Get top users by streak length.

        Args:
            limit: Maximum number of users to return (default: 10)
            metric: Which metric to rank by: "current_streak" or "longest_streak"

        Returns:
            List of top users sorted by streak metric

        Raises:
            ValueError: If metric is not "current_streak" or "longest_streak"

        Example:
            >>> service = StreakService(repo)
            >>> leaderboard = service.get_streak_leaderboard(limit=5)
            >>> for rank, user in enumerate(leaderboard, 1):
            ...     print(f"{rank}. {user['installation_id']}: {user['current_streak']}")
        """
        if metric not in ("current_streak", "longest_streak"):
            raise ValueError(
                f"Invalid metric: {metric}. "
                f"Must be 'current_streak' or 'longest_streak'"
            )

        try:
            # Get all active users and calculate their streaks
            # Note: This is a simplified implementation. For production with
            # millions of users, we'd want to cache streak metrics or use
            # materialized views.
            all_streaks = self.get_active_streak_users(min_streak=1)

            # Sort by requested metric
            all_streaks.sort(
                key=lambda x: x[metric],
                reverse=True
            )

            # Return top N
            leaderboard = all_streaks[:limit]

            logger.info(
                f"Generated streak leaderboard: {len(leaderboard)} users "
                f"ranked by {metric}"
            )

            return leaderboard

        except Exception as e:
            logger.error(f"Failed to generate streak leaderboard: {e}")
            raise

    def compare_user_streaks(
        self,
        installation_id: str,
        previous_date: date,
        current_date: date | None = None
    ) -> dict[str, int]:
        """Compare user's streaks between two dates.

        Args:
            installation_id: User's installation identifier
            previous_date: Earlier date for comparison
            current_date: Later date for comparison (default: today)

        Returns:
            Dictionary with delta values for streak metrics

        Example:
            >>> service = StreakService(repo)
            >>> deltas = service.compare_user_streaks(
            ...     "abc123",
            ...     previous_date=date(2025, 1, 1),
            ...     current_date=date(2025, 1, 10)
            ... )
            >>> print(f"Streak grew by: {deltas['current_streak']} days")
        """
        if current_date is None:
            current_date = date.today()

        try:
            # Calculate streaks for both dates
            previous_metrics = self.get_user_streak(
                installation_id,
                as_of_date=previous_date
            )

            current_metrics = self.get_user_streak(
                installation_id,
                as_of_date=current_date
            )

            # Use domain function to calculate deltas (pure logic)
            deltas = compare_streaks(current_metrics, previous_metrics)

            logger.info(
                f"Compared streaks for {installation_id}: "
                f"current_delta={deltas['current_streak']}, "
                f"longest_delta={deltas['longest_streak']}"
            )

            return deltas

        except Exception as e:
            logger.error(
                f"Failed to compare streaks for {installation_id}: {e}"
            )
            raise
