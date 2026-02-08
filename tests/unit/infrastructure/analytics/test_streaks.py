"""
Unit tests for streak tracker and achievements.

Tests the gamification system including:
- Streak tracking
- Achievement unlocking
- Points calculation
- Progress tracking
"""

import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from raxe.infrastructure.analytics.streaks import (
    ACHIEVEMENTS,
    Achievement,
    AchievementType,
    StreakData,
    StreakTracker,
)


@pytest.fixture
def temp_data_file():
    """Create a temporary achievements file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        data_path = Path(f.name)

    yield data_path

    # Cleanup
    if data_path.exists():
        data_path.unlink()


@pytest.fixture
def streak_tracker(temp_data_file):
    """Create streak tracker with temporary data file."""
    return StreakTracker(data_path=temp_data_file)


class TestStreakData:
    """Test suite for StreakData dataclass."""

    def test_streak_data_creation(self):
        """Test creating StreakData object."""
        data = StreakData(
            current_streak=5,
            longest_streak=10,
            last_scan_date=datetime.now(timezone.utc).date(),
            total_scan_days=20,
        )

        assert data.current_streak == 5
        assert data.longest_streak == 10
        assert data.total_scan_days == 20

    def test_streak_data_to_dict(self):
        """Test converting StreakData to dictionary."""
        data = StreakData(
            current_streak=5, longest_streak=10, last_scan_date=datetime.now(timezone.utc).date()
        )

        result = data.to_dict()
        assert result["current_streak"] == 5
        assert result["longest_streak"] == 10
        assert "last_scan_date" in result

    def test_streak_data_from_dict(self):
        """Test creating StreakData from dictionary."""
        dict_data = {
            "current_streak": 5,
            "longest_streak": 10,
            "last_scan_date": "2025-11-16",
            "total_scan_days": 20,
        }

        data = StreakData.from_dict(dict_data)
        assert data.current_streak == 5
        assert data.longest_streak == 10
        assert data.total_scan_days == 20


class TestAchievement:
    """Test suite for Achievement dataclass."""

    def test_achievement_creation(self):
        """Test creating Achievement object."""
        achievement = Achievement(
            id="test_achievement",
            name="Test Achievement",
            description="A test achievement",
            icon="🏆",
            points=100,
        )

        assert achievement.id == "test_achievement"
        assert achievement.name == "Test Achievement"
        assert achievement.points == 100
        assert achievement.unlocked_at is None

    def test_achievement_to_dict(self):
        """Test converting Achievement to dictionary."""
        achievement = Achievement(
            id="test",
            name="Test",
            description="Test achievement",
            icon="🏆",
            points=100,
            unlocked_at=datetime.now(timezone.utc),
        )

        result = achievement.to_dict()
        assert result["id"] == "test"
        assert result["points"] == 100
        assert result["unlocked"] is True
        assert "unlocked_at" in result

    def test_achievement_from_dict(self):
        """Test creating Achievement from dictionary."""
        dict_data = {
            "id": "test",
            "name": "Test",
            "description": "Test achievement",
            "icon": "🏆",
            "points": 100,
            "unlocked_at": datetime.now(timezone.utc).isoformat(),
        }

        achievement = Achievement.from_dict(dict_data)
        assert achievement.id == "test"
        assert achievement.points == 100
        assert achievement.unlocked_at is not None


class TestStreakTracker:
    """Test suite for StreakTracker."""

    def test_tracker_initialization(self, temp_data_file):
        """Test tracker initializes correctly."""
        tracker = StreakTracker(data_path=temp_data_file)

        assert tracker.data_path == temp_data_file
        assert tracker.streak_data.current_streak == 0
        assert tracker.total_points == 0
        assert len(tracker.achievements) > 0

    def test_first_scan_records_streak(self, streak_tracker):
        """Test recording first scan."""
        streak_tracker.record_scan()

        assert streak_tracker.streak_data.current_streak == 1
        assert streak_tracker.streak_data.longest_streak == 1
        assert streak_tracker.streak_data.total_scan_days == 1

    def test_consecutive_scans_build_streak(self, streak_tracker):
        """Test consecutive scans build streak."""
        today = datetime.now(timezone.utc).date()

        # Record scans for 5 consecutive days
        for i in range(5):
            scan_date = today - timedelta(days=4 - i)
            streak_tracker.record_scan(scan_date)

        assert streak_tracker.streak_data.current_streak == 5
        assert streak_tracker.streak_data.longest_streak == 5
        assert streak_tracker.streak_data.total_scan_days == 5

    def test_missed_day_breaks_streak(self, streak_tracker):
        """Test missing a day breaks the streak."""
        today = datetime.now(timezone.utc).date()

        # Build a 5-day streak
        for i in range(5):
            scan_date = today - timedelta(days=10 - i)
            streak_tracker.record_scan(scan_date)

        assert streak_tracker.streak_data.current_streak == 5
        assert streak_tracker.streak_data.longest_streak == 5

        # Skip 2 days, then scan again
        streak_tracker.record_scan(today - timedelta(days=3))

        assert streak_tracker.streak_data.current_streak == 1
        assert streak_tracker.streak_data.longest_streak == 5  # Longest streak unchanged

    def test_same_day_scans_dont_increase_streak(self, streak_tracker):
        """Test multiple scans on same day don't increase streak."""
        today = datetime.now(timezone.utc).date()

        streak_tracker.record_scan(today)
        assert streak_tracker.streak_data.current_streak == 1

        # Scan again same day
        streak_tracker.record_scan(today)
        assert streak_tracker.streak_data.current_streak == 1
        assert streak_tracker.streak_data.total_scan_days == 1

    def test_streak_7_achievement_unlocks(self, streak_tracker):
        """Test 7-day streak achievement unlocks."""
        today = datetime.now(timezone.utc).date()

        # Build a 7-day streak
        for i in range(7):
            scan_date = today - timedelta(days=6 - i)
            streak_tracker.record_scan(scan_date)

        # Check achievement is unlocked
        achievement = streak_tracker.achievements[AchievementType.STREAK_7.value]
        assert achievement.unlocked_at is not None

    def test_streak_30_achievement_unlocks(self, streak_tracker):
        """Test 30-day streak achievement unlocks."""
        today = datetime.now(timezone.utc).date()

        # Build a 30-day streak
        for i in range(30):
            scan_date = today - timedelta(days=29 - i)
            streak_tracker.record_scan(scan_date)

        # Check achievement is unlocked
        achievement = streak_tracker.achievements[AchievementType.STREAK_30.value]
        assert achievement.unlocked_at is not None

    def test_first_scan_achievement(self, streak_tracker):
        """Test first scan achievement unlocks."""
        streak_tracker.check_achievements(total_scans=1)

        achievement = streak_tracker.achievements[AchievementType.FIRST_SCAN.value]
        assert achievement.unlocked_at is not None
        assert streak_tracker.total_points >= achievement.points

    def test_scan_milestone_achievements(self, streak_tracker):
        """Test scan milestone achievements unlock."""
        # 100 scans
        streak_tracker.check_achievements(total_scans=100)
        achievement = streak_tracker.achievements[AchievementType.SCANS_100.value]
        assert achievement.unlocked_at is not None

        # 1000 scans
        streak_tracker.check_achievements(total_scans=1000)
        achievement = streak_tracker.achievements[AchievementType.SCANS_1000.value]
        assert achievement.unlocked_at is not None

    def test_threat_detection_achievements(self, streak_tracker):
        """Test threat detection achievements unlock."""
        # First threat
        streak_tracker.check_achievements(threats_detected=1)
        achievement = streak_tracker.achievements[AchievementType.FIRST_THREAT.value]
        assert achievement.unlocked_at is not None

        # 10 threats
        streak_tracker.check_achievements(threats_detected=10)
        achievement = streak_tracker.achievements[AchievementType.THREATS_10.value]
        assert achievement.unlocked_at is not None

        # 100 threats
        streak_tracker.check_achievements(threats_detected=100)
        achievement = streak_tracker.achievements[AchievementType.THREATS_100.value]
        assert achievement.unlocked_at is not None

    def test_speed_demon_achievement(self, streak_tracker):
        """Test speed demon achievement unlocks."""
        # Avg scan time < 5ms with at least 10 scans
        streak_tracker.check_achievements(total_scans=10, avg_scan_time_ms=4.5)

        achievement = streak_tracker.achievements[AchievementType.SPEED_DEMON.value]
        assert achievement.unlocked_at is not None

    def test_guardian_achievement(self, streak_tracker):
        """Test guardian achievement unlocks."""
        streak_tracker.check_achievements(threats_blocked=10)

        achievement = streak_tracker.achievements[AchievementType.GUARDIAN.value]
        assert achievement.unlocked_at is not None

    def test_achievement_only_unlocks_once(self, streak_tracker):
        """Test achievement can only be unlocked once."""
        # Unlock first scan
        streak_tracker.check_achievements(total_scans=1)
        initial_points = streak_tracker.total_points

        # Try to unlock again
        streak_tracker.check_achievements(total_scans=1)
        assert streak_tracker.total_points == initial_points

    def test_get_unlocked_achievements(self, streak_tracker):
        """Test getting unlocked achievements."""
        assert len(streak_tracker.get_unlocked_achievements()) == 0

        # Unlock some achievements
        streak_tracker.check_achievements(total_scans=1)
        streak_tracker.check_achievements(threats_detected=1)

        unlocked = streak_tracker.get_unlocked_achievements()
        assert len(unlocked) == 2

    def test_get_locked_achievements(self, streak_tracker):
        """Test getting locked achievements."""
        total_achievements = len(streak_tracker.achievements)
        locked = streak_tracker.get_locked_achievements()

        assert len(locked) == total_achievements

        # Unlock one
        streak_tracker.check_achievements(total_scans=1)
        locked = streak_tracker.get_locked_achievements()
        assert len(locked) == total_achievements - 1

    def test_get_progress_summary(self, streak_tracker):
        """Test getting progress summary."""
        progress = streak_tracker.get_progress_summary()

        assert "total_achievements" in progress
        assert "unlocked" in progress
        assert "locked" in progress
        assert "completion_percentage" in progress
        assert "total_points" in progress
        assert progress["unlocked"] == 0
        assert progress["total_points"] == 0

        # Unlock some achievements
        streak_tracker.check_achievements(total_scans=100)

        progress = streak_tracker.get_progress_summary()
        assert progress["unlocked"] > 0
        assert progress["total_points"] > 0

    def test_get_streak_info(self, streak_tracker):
        """Test getting streak information."""
        streak_info = streak_tracker.get_streak_info()

        assert "current_streak" in streak_info
        assert "longest_streak" in streak_info
        assert "total_scan_days" in streak_info
        assert "is_active" in streak_info

        assert streak_info["current_streak"] == 0
        assert not streak_info["is_active"]

        # Record a scan
        streak_tracker.record_scan()

        streak_info = streak_tracker.get_streak_info()
        assert streak_info["current_streak"] == 1
        assert streak_info["is_active"]

    def test_data_persistence(self, temp_data_file):
        """Test data persists across instances."""
        # Create tracker and unlock achievements
        tracker1 = StreakTracker(data_path=temp_data_file)
        tracker1.check_achievements(total_scans=100, threats_detected=10)
        tracker1.record_scan()

        initial_points = tracker1.total_points
        initial_streak = tracker1.streak_data.current_streak

        # Create new instance
        tracker2 = StreakTracker(data_path=temp_data_file)

        # Data should be loaded
        assert tracker2.total_points == initial_points
        assert tracker2.streak_data.current_streak == initial_streak
        assert len(tracker2.get_unlocked_achievements()) > 0

    def test_streak_active_check(self, streak_tracker):
        """Test streak active status check."""
        # No scans yet
        assert not streak_tracker._is_streak_active()

        # Scan today
        streak_tracker.record_scan(datetime.now(timezone.utc).date())
        assert streak_tracker._is_streak_active()

        # Scan yesterday
        tracker2 = StreakTracker()
        tracker2.record_scan(datetime.now(timezone.utc).date() - timedelta(days=1))
        assert tracker2._is_streak_active()

        # Scan 2 days ago (streak broken)
        tracker3 = StreakTracker()
        tracker3.record_scan(datetime.now(timezone.utc).date() - timedelta(days=2))
        assert not tracker3._is_streak_active()


class TestAchievementCatalog:
    """Test suite for achievement catalog."""

    def test_all_achievements_defined(self):
        """Test all achievement types are in catalog."""
        for achievement_type in AchievementType:
            assert achievement_type.value in ACHIEVEMENTS

    def test_achievement_data_complete(self):
        """Test all achievements have required fields."""
        for achievement_id, achievement in ACHIEVEMENTS.items():
            assert achievement.id == achievement_id
            assert len(achievement.name) > 0
            assert len(achievement.description) > 0
            assert len(achievement.icon) > 0
            assert achievement.points > 0

    def test_achievement_points_reasonable(self):
        """Test achievement points are in reasonable range."""
        for achievement in ACHIEVEMENTS.values():
            assert 0 < achievement.points <= 1000
