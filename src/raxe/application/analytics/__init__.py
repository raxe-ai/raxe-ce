"""Application layer for analytics services.

This package contains orchestration services that coordinate
between pure domain logic (calculations) and infrastructure (I/O).

Services:
    - RetentionService: User retention calculations
    - StreakService: Activity streak tracking
    - StatisticsService: DAU/WAU/MAU and usage stats
    - AchievementService: Achievement evaluation and tracking

All services delegate calculations to domain layer and
data access to repository implementations.
"""

from .achievement_service import AchievementService
from .repositories import AnalyticsRepository, ScanEvent, UserActivity
from .retention_service import RetentionService
from .statistics_service import StatisticsService
from .streak_service import StreakService

__all__ = [
    "AchievementService",
    "AnalyticsRepository",
    "RetentionService",
    "ScanEvent",
    "StatisticsService",
    "StreakService",
    "UserActivity",
]
