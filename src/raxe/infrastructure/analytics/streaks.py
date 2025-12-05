"""
Streak tracking and gamification system.

Tracks user engagement through streaks and unlockable achievements.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AchievementType(Enum):
    """Achievement types."""
    FIRST_SCAN = "first_scan"
    STREAK_7 = "streak_7"
    STREAK_30 = "streak_30"
    SCANS_100 = "scans_100"
    SCANS_1000 = "scans_1000"
    FIRST_THREAT = "first_threat"
    THREATS_10 = "threats_10"
    THREATS_100 = "threats_100"
    SPEED_DEMON = "speed_demon"  # Avg scan time < 5ms
    GUARDIAN = "guardian"  # Blocked 10 threats


@dataclass
class Achievement:
    """Achievement definition."""
    id: str
    name: str
    description: str
    icon: str
    points: int
    unlocked_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "points": self.points,
            "unlocked_at": self.unlocked_at.isoformat() if self.unlocked_at else None,
            "unlocked": self.unlocked_at is not None
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Achievement":
        """Create from dictionary."""
        unlocked_at = None
        if data.get("unlocked_at"):
            unlocked_at = datetime.fromisoformat(data["unlocked_at"])

        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            icon=data["icon"],
            points=data["points"],
            unlocked_at=unlocked_at
        )


# Achievement catalog
ACHIEVEMENTS: dict[str, Achievement] = {
    AchievementType.FIRST_SCAN.value: Achievement(
        id=AchievementType.FIRST_SCAN.value,
        name="First Scan",
        description="Completed your first security scan",
        icon="🔍",
        points=10
    ),
    AchievementType.STREAK_7.value: Achievement(
        id=AchievementType.STREAK_7.value,
        name="Week Warrior",
        description="Maintained a 7-day scan streak",
        icon="🔥",
        points=50
    ),
    AchievementType.STREAK_30.value: Achievement(
        id=AchievementType.STREAK_30.value,
        name="Monthly Master",
        description="Maintained a 30-day scan streak",
        icon="⚡",
        points=200
    ),
    AchievementType.SCANS_100.value: Achievement(
        id=AchievementType.SCANS_100.value,
        name="Century Scanner",
        description="Completed 100 scans",
        icon="💯",
        points=100
    ),
    AchievementType.SCANS_1000.value: Achievement(
        id=AchievementType.SCANS_1000.value,
        name="Scan Master",
        description="Completed 1,000 scans",
        icon="🌟",
        points=500
    ),
    AchievementType.FIRST_THREAT.value: Achievement(
        id=AchievementType.FIRST_THREAT.value,
        name="Threat Hunter",
        description="Detected your first security threat",
        icon="🛡️",
        points=25
    ),
    AchievementType.THREATS_10.value: Achievement(
        id=AchievementType.THREATS_10.value,
        name="Security Guardian",
        description="Detected 10 security threats",
        icon="🎯",
        points=75
    ),
    AchievementType.THREATS_100.value: Achievement(
        id=AchievementType.THREATS_100.value,
        name="Elite Defender",
        description="Detected 100 security threats",
        icon="👑",
        points=300
    ),
    AchievementType.SPEED_DEMON.value: Achievement(
        id=AchievementType.SPEED_DEMON.value,
        name="Speed Demon",
        description="Achieved average scan time under 5ms",
        icon="⚡",
        points=150
    ),
    AchievementType.GUARDIAN.value: Achievement(
        id=AchievementType.GUARDIAN.value,
        name="Guardian",
        description="Blocked 10 security threats",
        icon="🛡️",
        points=100
    ),
}


@dataclass
class StreakData:
    """Streak tracking data."""
    current_streak: int = 0
    longest_streak: int = 0
    last_scan_date: date | None = None
    total_scan_days: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "current_streak": self.current_streak,
            "longest_streak": self.longest_streak,
            "last_scan_date": self.last_scan_date.isoformat() if self.last_scan_date else None,
            "total_scan_days": self.total_scan_days
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StreakData":
        """Create from dictionary."""
        last_scan_date = None
        if data.get("last_scan_date"):
            last_scan_date = date.fromisoformat(data["last_scan_date"])

        return cls(
            current_streak=data.get("current_streak", 0),
            longest_streak=data.get("longest_streak", 0),
            last_scan_date=last_scan_date,
            total_scan_days=data.get("total_scan_days", 0)
        )


class StreakTracker:
    """
    Tracks user engagement streaks and achievements.

    Stores streak data and achievements in ~/.raxe/achievements.json
    """

    def __init__(self, data_path: Path | None = None):
        """
        Initialize streak tracker.

        Args:
            data_path: Path to achievements data file (defaults to ~/.raxe/achievements.json)
        """
        if data_path is None:
            data_path = Path.home() / ".raxe" / "achievements.json"

        self.data_path = data_path
        # Create parent directory with restricted permissions (owner read/write/execute only)
        self.data_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Load existing data
        self.streak_data = StreakData()
        self.achievements: dict[str, Achievement] = {
            k: Achievement(**asdict(v)) for k, v in ACHIEVEMENTS.items()
        }
        self.total_points = 0

        self._load()

        logger.info(f"Streak tracker initialized with data file: {self.data_path}")

    def _load(self) -> None:
        """Load streak and achievement data from file."""
        if not self.data_path.exists():
            logger.info("No existing achievements file, starting fresh")
            return

        try:
            with open(self.data_path) as f:
                data = json.load(f)

            # Load streak data
            if "streak_data" in data:
                self.streak_data = StreakData.from_dict(data["streak_data"])

            # Load achievements
            if "achievements" in data:
                for achievement_data in data["achievements"]:
                    achievement_id = achievement_data["id"]
                    if achievement_id in self.achievements:
                        self.achievements[achievement_id] = Achievement.from_dict(achievement_data)

            # Load total points
            self.total_points = data.get("total_points", 0)

            logger.info(
                f"Loaded streak data: current={self.streak_data.current_streak}, "
                f"longest={self.streak_data.longest_streak}, points={self.total_points}"
            )

        except Exception as e:
            logger.error(f"Failed to load achievements data: {e}")

    def _save(self) -> None:
        """Save streak and achievement data to file with secure permissions."""
        try:
            data = {
                "streak_data": self.streak_data.to_dict(),
                "achievements": [a.to_dict() for a in self.achievements.values()],
                "total_points": self.total_points,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }

            # Write file with secure permissions (owner read/write only)
            with open(self.data_path, 'w') as f:
                json.dump(data, f, indent=2)

            # Set restrictive permissions on the file (owner read/write only - 0o600)
            os.chmod(self.data_path, 0o600)

            logger.debug(f"Saved achievements data to {self.data_path}")

        except Exception as e:
            logger.error(f"Failed to save achievements data: {e}")

    def record_scan(self, scan_date: date | None = None) -> list[Achievement]:
        """
        Record a scan and update streaks.

        Args:
            scan_date: Date of scan (defaults to today)

        Returns:
            List of newly unlocked achievements
        """
        if scan_date is None:
            scan_date = datetime.now(timezone.utc).date()

        newly_unlocked: list[Achievement] = []

        # Update streak
        if self.streak_data.last_scan_date is None:
            # First scan ever
            self.streak_data.current_streak = 1
            self.streak_data.longest_streak = 1
            self.streak_data.total_scan_days = 1
        elif scan_date == self.streak_data.last_scan_date:
            # Same day, no change to streak
            pass
        elif scan_date == self.streak_data.last_scan_date + timedelta(days=1):
            # Consecutive day
            self.streak_data.current_streak += 1
            self.streak_data.longest_streak = max(
                self.streak_data.longest_streak,
                self.streak_data.current_streak
            )
            self.streak_data.total_scan_days += 1
        else:
            # Streak broken
            self.streak_data.current_streak = 1
            self.streak_data.total_scan_days += 1

        self.streak_data.last_scan_date = scan_date

        # Check for streak achievements
        if self.streak_data.current_streak >= 7:
            newly_unlocked.extend(self._unlock_achievement(AchievementType.STREAK_7.value))

        if self.streak_data.current_streak >= 30:
            newly_unlocked.extend(self._unlock_achievement(AchievementType.STREAK_30.value))

        self._save()

        return newly_unlocked

    def check_achievements(
        self,
        *,
        total_scans: int = 0,
        threats_detected: int = 0,
        avg_scan_time_ms: float = 0.0,
        threats_blocked: int = 0
    ) -> list[Achievement]:
        """
        Check and unlock achievements based on stats.

        Args:
            total_scans: Total number of scans
            threats_detected: Total threats detected
            avg_scan_time_ms: Average scan time in milliseconds
            threats_blocked: Total threats blocked

        Returns:
            List of newly unlocked achievements
        """
        newly_unlocked: list[Achievement] = []

        # First scan
        if total_scans >= 1:
            newly_unlocked.extend(self._unlock_achievement(AchievementType.FIRST_SCAN.value))

        # Scan milestones
        if total_scans >= 100:
            newly_unlocked.extend(self._unlock_achievement(AchievementType.SCANS_100.value))

        if total_scans >= 1000:
            newly_unlocked.extend(self._unlock_achievement(AchievementType.SCANS_1000.value))

        # Threat detection
        if threats_detected >= 1:
            newly_unlocked.extend(self._unlock_achievement(AchievementType.FIRST_THREAT.value))

        if threats_detected >= 10:
            newly_unlocked.extend(self._unlock_achievement(AchievementType.THREATS_10.value))

        if threats_detected >= 100:
            newly_unlocked.extend(self._unlock_achievement(AchievementType.THREATS_100.value))

        # Performance
        if total_scans >= 10 and avg_scan_time_ms < 5.0:
            newly_unlocked.extend(self._unlock_achievement(AchievementType.SPEED_DEMON.value))

        # Threat blocking
        if threats_blocked >= 10:
            newly_unlocked.extend(self._unlock_achievement(AchievementType.GUARDIAN.value))

        if newly_unlocked:
            self._save()

        return newly_unlocked

    def _unlock_achievement(self, achievement_id: str) -> list[Achievement]:
        """
        Unlock an achievement if not already unlocked.

        Args:
            achievement_id: Achievement identifier

        Returns:
            List containing the achievement if newly unlocked, empty list otherwise
        """
        if achievement_id not in self.achievements:
            logger.warning(f"Unknown achievement: {achievement_id}")
            return []

        achievement = self.achievements[achievement_id]

        if achievement.unlocked_at is not None:
            # Already unlocked
            return []

        # Unlock achievement
        achievement.unlocked_at = datetime.now(timezone.utc)
        self.total_points += achievement.points

        logger.info(
            f"Achievement unlocked: {achievement.name} (+{achievement.points} points)"
        )

        return [achievement]

    def get_unlocked_achievements(self) -> list[Achievement]:
        """
        Get all unlocked achievements.

        Returns:
            List of unlocked achievements
        """
        return [a for a in self.achievements.values() if a.unlocked_at is not None]

    def get_locked_achievements(self) -> list[Achievement]:
        """
        Get all locked achievements.

        Returns:
            List of locked achievements
        """
        return [a for a in self.achievements.values() if a.unlocked_at is None]

    def get_progress_summary(self) -> dict[str, Any]:
        """
        Get achievement progress summary.

        Returns:
            Dictionary with progress information
        """
        total_achievements = len(self.achievements)
        unlocked_count = len(self.get_unlocked_achievements())

        return {
            "total_achievements": total_achievements,
            "unlocked": unlocked_count,
            "locked": total_achievements - unlocked_count,
            "completion_percentage": round((unlocked_count / total_achievements * 100) if total_achievements > 0 else 0.0, 2),
            "total_points": self.total_points,
            "current_streak": self.streak_data.current_streak,
            "longest_streak": self.streak_data.longest_streak
        }

    def get_streak_info(self) -> dict[str, Any]:
        """
        Get streak information.

        Returns:
            Dictionary with streak data
        """
        return {
            "current_streak": self.streak_data.current_streak,
            "longest_streak": self.streak_data.longest_streak,
            "last_scan_date": self.streak_data.last_scan_date.isoformat() if self.streak_data.last_scan_date else None,
            "total_scan_days": self.streak_data.total_scan_days,
            "is_active": self._is_streak_active()
        }

    def _is_streak_active(self) -> bool:
        """
        Check if current streak is still active.

        Returns:
            True if streak is active (scanned today or yesterday)
        """
        if self.streak_data.last_scan_date is None:
            return False

        today = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)

        return self.streak_data.last_scan_date in (today, yesterday)
