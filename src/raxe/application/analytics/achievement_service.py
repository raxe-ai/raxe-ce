"""Achievement tracking and evaluation service.

Manages all achievement types and tracks user progress.

CRITICAL: This is application layer - orchestrates but doesn't calculate.
All calculations delegated to domain layer, all I/O to repository.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from raxe.domain.analytics import (
    ACHIEVEMENTS,
    Achievement,
    calculate_user_achievements,
    check_achievement_unlocked,
    find_next_achievements,
    get_achievement_by_id,
)

from .repositories import AnalyticsRepository

logger = logging.getLogger(__name__)


class AchievementService:
    """Service for comprehensive achievement tracking.

    This service orchestrates:
    1. Data loading from repository (infrastructure)
    2. Achievement evaluation (domain pure functions)
    3. Achievement saving and notification

    CRITICAL: This service does NOT perform calculations itself.
    All business logic is delegated to domain layer functions.
    """

    def __init__(self, repository: AnalyticsRepository):
        """Initialize achievement service.

        Args:
            repository: Repository for data access (dependency injection)
        """
        self.repository = repository
        self._streak_service = None  # Can be set externally to avoid circular import

    def set_streak_service(self, streak_service):
        """Set the streak service for streak-based achievements.

        Args:
            streak_service: StreakService instance
        """
        self._streak_service = streak_service

    def evaluate_user_achievements(
        self,
        installation_id: str
    ) -> list[Achievement]:
        """Evaluate all potential achievements for a user.

        This checks which achievements the user has earned and saves any
        new achievements to the repository.

        Args:
            installation_id: User's installation identifier

        Returns:
            List of newly earned achievements

        Example:
            >>> service = AchievementService(repo)
            >>> new_achievements = service.evaluate_user_achievements("abc123")
            >>> for ach in new_achievements:
            ...     print(f"Unlocked: {ach.name} (+{ach.points} points)")
        """
        try:
            # Step 1: Gather user activity data (I/O)
            activity = self.repository.get_user_activity(installation_id)

            if not activity:
                logger.info(
                    f"No activity for achievement evaluation: {installation_id}"
                )
                return []

            # Step 2: Get streak info if streak service available
            from datetime import date

            from raxe.domain.analytics import StreakMetrics


            if self._streak_service:
                streak_metrics = self._streak_service.get_user_streak(installation_id)
            else:
                # Fallback to zero streaks if service not available
                streak_metrics = StreakMetrics(
                    installation_id=installation_id,
                    current_streak=0,
                    longest_streak=0,
                    total_scan_days=len(activity.scan_dates),
                    last_scan_date=date.today()
                )

            # Step 3: Calculate all unlocked achievements using domain (pure logic)
            user_achievements = calculate_user_achievements(
                installation_id=installation_id,
                scan_count=activity.total_scans,
                streak_metrics=streak_metrics
            )

            # Step 4: Get existing achievements from repository (I/O)
            existing = self.repository.get_achievements(installation_id)
            existing_ids = {a['achievement_id'] for a in existing}

            # Step 5: Filter to only new achievements
            new_achievement_ids = [
                ach_id for ach_id in user_achievements.unlocked_achievements
                if ach_id not in existing_ids
            ]

            new_achievements = []
            for ach_id in new_achievement_ids:
                achievement = get_achievement_by_id(ach_id)
                if achievement:
                    new_achievements.append(achievement)

            # Step 6: Save new achievements to repository (I/O)
            for achievement in new_achievements:
                self.repository.save_achievement(
                    installation_id=installation_id,
                    achievement_id=achievement.id,
                    earned_at=datetime.now(timezone.utc),
                    metadata={
                        'name': achievement.name,
                        'description': achievement.description,
                        'points': achievement.points,
                        'unlock_condition': achievement.unlock_condition,
                        'scan_count': activity.total_scans,
                        'streak_count': streak_metrics.longest_streak
                    }
                )

                logger.info(
                    f"Achievement unlocked: {installation_id} -> "
                    f"{achievement.name} (+{achievement.points} points)"
                )

            return new_achievements

        except Exception as e:
            logger.error(
                f"Failed to evaluate achievements for {installation_id}: {e}"
            )
            raise

    def get_user_achievement_summary(
        self,
        installation_id: str
    ) -> dict[str, Any]:
        """Get complete achievement summary for a user.

        Args:
            installation_id: User's installation identifier

        Returns:
            Dictionary with unlocked achievements, points, and next goals

        Example:
            >>> service = AchievementService(repo)
            >>> summary = service.get_user_achievement_summary("abc123")
            >>> print(f"Total points: {summary['total_points']}")
            >>> print(f"Unlocked: {summary['unlocked_count']}/{summary['total_count']}")
        """
        try:
            # Step 1: Get user activity and calculate current state
            activity = self.repository.get_user_activity(installation_id)

            if not activity:
                return {
                    "installation_id": installation_id,
                    "total_points": 0,
                    "unlocked_count": 0,
                    "total_count": len(ACHIEVEMENTS),
                    "unlocked_achievements": [],
                    "next_achievements": []
                }

            # Step 2: Get streak metrics
            from datetime import date

            from raxe.domain.analytics import StreakMetrics


            if self._streak_service:
                streak_metrics = self._streak_service.get_user_streak(installation_id)
            else:
                streak_metrics = StreakMetrics(
                    installation_id=installation_id,
                    current_streak=0,
                    longest_streak=0,
                    total_scan_days=len(activity.scan_dates),
                    last_scan_date=date.today()
                )

            # Step 3: Calculate user achievements using domain (pure logic)
            user_achievements = calculate_user_achievements(
                installation_id=installation_id,
                scan_count=activity.total_scans,
                streak_metrics=streak_metrics
            )

            # Step 4: Find next achievements to unlock (pure logic)
            next_achievements = find_next_achievements(
                user_achievements,
                max_results=3
            )

            # Step 5: Build response
            result = {
                "installation_id": installation_id,
                "total_points": user_achievements.total_points,
                "unlocked_count": len(user_achievements.unlocked_achievements),
                "total_count": len(ACHIEVEMENTS),
                "unlocked_achievements": [
                    {
                        "id": ach_id,
                        "name": get_achievement_by_id(ach_id).name,
                        "points": get_achievement_by_id(ach_id).points
                    }
                    for ach_id in user_achievements.unlocked_achievements
                    if get_achievement_by_id(ach_id)
                ],
                "next_achievements": [
                    {
                        "id": ach.id,
                        "name": ach.name,
                        "description": ach.description,
                        "points": ach.points,
                        "progress_needed": progress
                    }
                    for ach, progress in next_achievements
                ]
            }

            logger.info(
                f"Achievement summary for {installation_id}: "
                f"{result['unlocked_count']}/{result['total_count']} unlocked, "
                f"{result['total_points']} points"
            )

            return result

        except Exception as e:
            logger.error(
                f"Failed to get achievement summary for {installation_id}: {e}"
            )
            raise

    def get_recent_unlocks(
        self
    ) -> list[dict[str, Any]]:
        """Get recently unlocked achievements across all users.

        Returns:
            List of recent achievement unlocks with user and timestamp

        Example:
            >>> service = AchievementService(repo)
            >>> recent = service.get_recent_unlocks()
            >>> for unlock in recent[:5]:
            ...     print(f"{unlock['achievement_name']} - {unlock['earned_at']}")
        """
        try:
            # Note: This is a simplified implementation.
            # For production, we'd want a dedicated query method in repository
            # that can efficiently get recent unlocks across all users.

            # For now, we'll return an empty list as this would require
            # iterating through all users which is inefficient.
            # This should be implemented as a repository method with proper indexing.

            logger.warning(
                "get_recent_unlocks is not yet implemented - "
                "requires repository method with proper indexing"
            )

            return []

        except Exception as e:
            logger.error(f"Failed to get recent unlocks: {e}")
            raise

    def get_achievement_leaderboard(
        self
    ) -> list[dict[str, Any]]:
        """Get top users by achievement points.

        Returns:
            List of top users sorted by achievement points

        Example:
            >>> service = AchievementService(repo)
            >>> leaderboard = service.get_achievement_leaderboard()
            >>> for rank, user in enumerate(leaderboard, 1):
            ...     print(f"{rank}. {user['installation_id']}: {user['points']} pts")
        """
        try:
            # Note: This is a simplified implementation.
            # For production with millions of users, we'd want to cache
            # achievement points or use materialized views.

            # For now, we'll return an empty list as this would require
            # calculating achievements for all users which is inefficient.
            # This should be implemented with proper caching/indexing.

            logger.warning(
                "get_achievement_leaderboard is not yet implemented - "
                "requires caching or materialized views for efficiency"
            )

            return []

        except Exception as e:
            logger.error(f"Failed to get achievement leaderboard: {e}")
            raise

    def get_achievement_progress(
        self,
        installation_id: str,
        achievement_id: str
    ) -> dict[str, Any]:
        """Get user's progress toward a specific achievement.

        Args:
            installation_id: User's installation identifier
            achievement_id: Achievement to check progress for

        Returns:
            Dictionary with achievement details and progress

        Raises:
            ValueError: If achievement_id is invalid

        Example:
            >>> service = AchievementService(repo)
            >>> progress = service.get_achievement_progress("abc123", "power_user")
            >>> print(f"Progress: {progress['current']}/{progress['required']}")
            >>> print(f"Unlocked: {progress['unlocked']}")
        """
        try:
            # Step 1: Validate achievement exists
            achievement = get_achievement_by_id(achievement_id)
            if not achievement:
                raise ValueError(f"Invalid achievement_id: {achievement_id}")

            # Step 2: Get user activity
            activity = self.repository.get_user_activity(installation_id)

            if not activity:
                return {
                    "achievement_id": achievement_id,
                    "achievement_name": achievement.name,
                    "unlocked": False,
                    "current": 0,
                    "required": self._extract_threshold(achievement.unlock_condition),
                    "progress_percentage": 0.0
                }

            # Step 3: Get streak metrics
            from datetime import date

            from raxe.domain.analytics import StreakMetrics


            if self._streak_service:
                streak_metrics = self._streak_service.get_user_streak(installation_id)
            else:
                streak_metrics = StreakMetrics(
                    installation_id=installation_id,
                    current_streak=0,
                    longest_streak=0,
                    total_scan_days=len(activity.scan_dates),
                    last_scan_date=date.today()
                )

            # Step 4: Check if achievement is unlocked (pure logic)
            is_unlocked = check_achievement_unlocked(
                achievement,
                scan_count=activity.total_scans,
                streak_count=streak_metrics.longest_streak
            )

            # Step 5: Calculate progress
            required = self._extract_threshold(achievement.unlock_condition)

            if "scan_count" in achievement.unlock_condition:
                current = activity.total_scans
            elif "streak_count" in achievement.unlock_condition:
                current = streak_metrics.longest_streak
            else:
                current = 0

            progress_percentage = min((current / required * 100), 100.0) if required > 0 else 0.0

            result = {
                "achievement_id": achievement_id,
                "achievement_name": achievement.name,
                "description": achievement.description,
                "points": achievement.points,
                "unlocked": is_unlocked,
                "current": current,
                "required": required,
                "progress_percentage": round(progress_percentage, 1)
            }

            logger.info(
                f"Achievement progress for {installation_id}/{achievement_id}: "
                f"{current}/{required} ({progress_percentage:.1f}%)"
            )

            return result

        except Exception as e:
            logger.error(
                f"Failed to get achievement progress for {installation_id}/{achievement_id}: {e}"
            )
            raise

    def _extract_threshold(self, unlock_condition: str) -> int:
        """Extract numeric threshold from unlock condition string.

        Args:
            unlock_condition: Condition string (e.g., "scan_count >= 100")

        Returns:
            Numeric threshold value
        """
        try:
            if ">=" in unlock_condition:
                return int(unlock_condition.split(">=")[1].strip())
            return 0
        except (ValueError, IndexError):
            return 0
