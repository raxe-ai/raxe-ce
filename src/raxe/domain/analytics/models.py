"""Pure analytics domain models - no I/O.

This module contains immutable value objects for analytics.
All models are frozen dataclasses to ensure immutability.

CRITICAL: This is domain layer - NO I/O operations allowed.
"""
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class RetentionMetrics:
    """Immutable retention metrics for a user.

    Tracks user retention across different time windows:
    - Day 1: Did user scan within 24 hours of install?
    - Day 7: Did user scan between day 6-8?
    - Day 30: Did user scan between day 29-31?

    Args:
        installation_id: Unique identifier for this installation
        install_date: Date when user installed RAXE
        day1_retained: True if user scanned on day 1
        day7_retained: True if user scanned around day 7
        day30_retained: True if user scanned around day 30
        total_scans: Total number of scans performed
        last_scan_date: Most recent scan date, if any
    """
    installation_id: str
    install_date: date
    day1_retained: bool
    day7_retained: bool
    day30_retained: bool
    total_scans: int
    last_scan_date: date | None = None


@dataclass(frozen=True)
class StreakMetrics:
    """Immutable streak metrics for a user.

    Tracks user engagement streaks (consecutive days with scans).

    Args:
        installation_id: Unique identifier for this installation
        current_streak: Current consecutive day streak (0 if broken)
        longest_streak: Longest consecutive day streak ever achieved
        total_scan_days: Total unique days with at least one scan
        last_scan_date: Most recent scan date
    """
    installation_id: str
    current_streak: int
    longest_streak: int
    total_scan_days: int
    last_scan_date: date


@dataclass(frozen=True)
class UsageStatistics:
    """Immutable usage statistics for a time period.

    Aggregated metrics for understanding user engagement.

    Args:
        period_start: Start of the measurement period
        period_end: End of the measurement period
        dau: Daily Active Users (users who scanned on period_end)
        wau: Weekly Active Users (users who scanned in last 7 days)
        mau: Monthly Active Users (users who scanned in last 30 days)
        total_scans: Total scans performed in period
        avg_scans_per_user: Average scans per active user
    """
    period_start: date
    period_end: date
    dau: int
    wau: int
    mau: int
    total_scans: int
    avg_scans_per_user: float


@dataclass(frozen=True)
class Achievement:
    """Immutable achievement definition.

    Represents a gamification achievement users can unlock.

    Args:
        id: Unique achievement identifier (e.g., "first_scan")
        name: Display name (e.g., "First Scan")
        description: User-facing description
        points: Points awarded for unlocking
        unlock_condition: Machine-readable condition (e.g., "scan_count >= 100")
    """
    id: str
    name: str
    description: str
    points: int
    unlock_condition: str


@dataclass(frozen=True)
class UserAchievements:
    """Immutable user achievement progress.

    Tracks which achievements a user has unlocked and their total points.

    Args:
        installation_id: Unique identifier for this installation
        unlocked_achievements: List of achievement IDs the user has unlocked
        total_points: Sum of points from all unlocked achievements
        scan_count: Total scans (cached for achievement checking)
        streak_count: Longest streak (cached for achievement checking)
    """
    installation_id: str
    unlocked_achievements: list[str] = field(default_factory=list)
    total_points: int = 0
    scan_count: int = 0
    streak_count: int = 0
