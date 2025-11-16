"""Pure analytics domain layer - no I/O operations.

This package contains all business logic for analytics calculations.
All functions are pure - they take data and return data without side effects.

CRITICAL: This is domain layer - NO database, network, or file operations allowed.

Public API:
    Models:
        - RetentionMetrics
        - StreakMetrics
        - UsageStatistics
        - Achievement
        - UserAchievements

    Functions:
        - calculate_retention()
        - calculate_cohort_retention()
        - calculate_streaks()
        - calculate_dau()
        - calculate_wau()
        - calculate_mau()
        - calculate_usage_statistics()
        - calculate_user_achievements()
        - ACHIEVEMENTS (const list)
"""

# Models
# Achievement functions
from .achievements import (
    ACHIEVEMENTS,
    calculate_user_achievements,
    check_achievement_unlocked,
    find_next_achievements,
    get_achievement_by_id,
    get_leaderboard_points,
)
from .models import (
    Achievement,
    RetentionMetrics,
    StreakMetrics,
    UsageStatistics,
    UserAchievements,
)

# Retention functions
from .retention import (
    calculate_cohort_retention,
    calculate_retention,
    calculate_retention_rate,
)

# Statistics functions
from .statistics import (
    calculate_dau,
    calculate_growth_rate,
    calculate_mau,
    calculate_stickiness,
    calculate_usage_statistics,
    calculate_wau,
)

# Streak functions
from .streaks import (
    calculate_streaks,
    compare_streaks,
)

__all__ = [
    # Achievements
    "ACHIEVEMENTS",
    "Achievement",
    # Models
    "RetentionMetrics",
    "StreakMetrics",
    "UsageStatistics",
    "UserAchievements",
    "calculate_cohort_retention",
    # Statistics
    "calculate_dau",
    "calculate_growth_rate",
    "calculate_mau",
    # Retention
    "calculate_retention",
    "calculate_retention_rate",
    "calculate_stickiness",
    # Streaks
    "calculate_streaks",
    "calculate_usage_statistics",
    "calculate_user_achievements",
    "calculate_wau",
    "check_achievement_unlocked",
    "compare_streaks",
    "find_next_achievements",
    "get_achievement_by_id",
    "get_leaderboard_points",
]
