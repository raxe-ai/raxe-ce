"""Pure achievement calculation functions - no I/O.

This module contains pure functions for calculating user achievements.
All functions are stateless and perform no I/O operations.

CRITICAL: This is domain layer - NO database, network, or file operations.
"""

from .models import Achievement, StreakMetrics, UserAchievements

# Define all achievements (const data, not I/O)
ACHIEVEMENTS: list[Achievement] = [
    Achievement(
        id="first_scan",
        name="First Scan",
        description="Completed your first scan",
        points=10,
        unlock_condition="scan_count >= 1"
    ),
    Achievement(
        id="getting_started",
        name="Getting Started",
        description="Completed 10 scans",
        points=25,
        unlock_condition="scan_count >= 10"
    ),
    Achievement(
        id="power_user",
        name="Power User",
        description="Completed 100 scans",
        points=100,
        unlock_condition="scan_count >= 100"
    ),
    Achievement(
        id="super_user",
        name="Super User",
        description="Completed 1,000 scans",
        points=500,
        unlock_condition="scan_count >= 1000"
    ),
    Achievement(
        id="mega_user",
        name="Mega User",
        description="Completed 10,000 scans",
        points=2000,
        unlock_condition="scan_count >= 10000"
    ),
    Achievement(
        id="streak_3",
        name="Three Day Streak",
        description="3-day scan streak",
        points=20,
        unlock_condition="streak_count >= 3"
    ),
    Achievement(
        id="streak_7",
        name="Week Warrior",
        description="7-day scan streak",
        points=50,
        unlock_condition="streak_count >= 7"
    ),
    Achievement(
        id="streak_30",
        name="Monthly Master",
        description="30-day scan streak",
        points=200,
        unlock_condition="streak_count >= 30"
    ),
    Achievement(
        id="streak_100",
        name="Century Streak",
        description="100-day scan streak",
        points=1000,
        unlock_condition="streak_count >= 100"
    ),
    Achievement(
        id="streak_365",
        name="Year Legend",
        description="365-day scan streak",
        points=5000,
        unlock_condition="streak_count >= 365"
    ),
]


def get_achievement_by_id(achievement_id: str) -> Achievement | None:
    """Get achievement definition by ID.

    Pure function - looks up achievement in const data.

    Args:
        achievement_id: Unique achievement identifier

    Returns:
        Achievement object, or None if not found

    Example:
        >>> ach = get_achievement_by_id("first_scan")
        >>> ach.name
        'First Scan'
    """
    for achievement in ACHIEVEMENTS:
        if achievement.id == achievement_id:
            return achievement
    return None


def check_achievement_unlocked(
    achievement: Achievement,
    *,
    scan_count: int,
    streak_count: int,
) -> bool:
    """Check if achievement is unlocked based on user stats.

    Pure function - evaluates unlock conditions.

    Currently supports two condition types:
    - "scan_count >= N": User has N or more scans
    - "streak_count >= N": User has N or more day streak

    Args:
        achievement: Achievement to check
        scan_count: User's total scan count
        streak_count: User's longest streak count

    Returns:
        True if achievement is unlocked, False otherwise

    Example:
        >>> ach = Achievement("test", "Test", "Test", 10, "scan_count >= 5")
        >>> check_achievement_unlocked(ach, scan_count=10, streak_count=0)
        True
        >>> check_achievement_unlocked(ach, scan_count=3, streak_count=0)
        False
    """
    condition = achievement.unlock_condition

    # Parse condition and evaluate
    if "scan_count >=" in condition:
        threshold = int(condition.split(">=")[1].strip())
        return scan_count >= threshold
    elif "streak_count >=" in condition:
        threshold = int(condition.split(">=")[1].strip())
        return streak_count >= threshold

    # Unknown condition type - default to False
    return False


def calculate_user_achievements(
    installation_id: str,
    scan_count: int,
    streak_metrics: StreakMetrics,
) -> UserAchievements:
    """Calculate which achievements a user has unlocked.

    Pure function - evaluates all achievements against user stats.

    Args:
        installation_id: Unique user identifier
        scan_count: Total scans performed by user
        streak_metrics: User's streak metrics

    Returns:
        UserAchievements with unlocked achievements and total points

    Example:
        >>> from datetime import date
        >>> streaks = StreakMetrics("u1", 7, 7, 10, date(2025, 1, 15))
        >>> achievements = calculate_user_achievements("u1", 100, streaks)
        >>> "power_user" in achievements.unlocked_achievements
        True
        >>> "streak_7" in achievements.unlocked_achievements
        True
        >>> achievements.total_points > 0
        True
    """
    unlocked = [
        achievement.id
        for achievement in ACHIEVEMENTS
        if check_achievement_unlocked(
            achievement,
            scan_count=scan_count,
            streak_count=streak_metrics.longest_streak,
        )
    ]

    total_points = sum(
        ach.points
        for ach in ACHIEVEMENTS
        if ach.id in unlocked
    )

    return UserAchievements(
        installation_id=installation_id,
        unlocked_achievements=unlocked,
        total_points=total_points,
        scan_count=scan_count,
        streak_count=streak_metrics.longest_streak,
    )


def find_next_achievements(
    current_achievements: UserAchievements,
    *,
    max_results: int = 3,
) -> list[tuple[Achievement, int]]:
    """Find next achievements user can unlock.

    Pure function - identifies closest locked achievements.

    Args:
        current_achievements: User's current achievement state
        max_results: Maximum number of next achievements to return

    Returns:
        List of (achievement, progress_needed) tuples, sorted by closest first

    Example:
        >>> achievements = UserAchievements("u1", ["first_scan"], 10, 5, 2)
        >>> next_achs = find_next_achievements(achievements, max_results=2)
        >>> len(next_achs) <= 2
        True
    """
    unlocked_set = set(current_achievements.unlocked_achievements)
    locked_achievements = [
        ach for ach in ACHIEVEMENTS
        if ach.id not in unlocked_set
    ]

    # Calculate progress needed for each locked achievement
    achievements_with_progress = []
    for ach in locked_achievements:
        progress_needed = _calculate_progress_needed(
            ach,
            scan_count=current_achievements.scan_count,
            streak_count=current_achievements.streak_count,
        )
        achievements_with_progress.append((ach, progress_needed))

    # Sort by progress needed (closest first)
    achievements_with_progress.sort(key=lambda x: x[1])

    return achievements_with_progress[:max_results]


def _calculate_progress_needed(
    achievement: Achievement,
    *,
    scan_count: int,
    streak_count: int,
) -> int:
    """Calculate how much progress is needed to unlock achievement.

    Args:
        achievement: Achievement to check
        scan_count: User's current scan count
        streak_count: User's current streak count

    Returns:
        Number of scans/days needed (0 if already unlocked)
    """
    condition = achievement.unlock_condition

    if "scan_count >=" in condition:
        threshold = int(condition.split(">=")[1].strip())
        return max(0, threshold - scan_count)
    elif "streak_count >=" in condition:
        threshold = int(condition.split(">=")[1].strip())
        return max(0, threshold - streak_count)

    return 0


def get_leaderboard_points(
    user_achievements: dict[str, UserAchievements]
) -> list[tuple[str, int]]:
    """Generate leaderboard sorted by total points.

    Pure function - aggregates and sorts achievement data.

    Args:
        user_achievements: Map of installation_id -> UserAchievements

    Returns:
        List of (installation_id, total_points) tuples, sorted descending

    Example:
        >>> achievements = {
        ...     "user1": UserAchievements("user1", [], 100, 0, 0),
        ...     "user2": UserAchievements("user2", [], 200, 0, 0),
        ... }
        >>> leaderboard = get_leaderboard_points(achievements)
        >>> leaderboard[0][0]
        'user2'
    """
    leaderboard = [
        (installation_id, achievements.total_points)
        for installation_id, achievements in user_achievements.items()
    ]

    # Sort by points descending
    leaderboard.sort(key=lambda x: x[1], reverse=True)

    return leaderboard
