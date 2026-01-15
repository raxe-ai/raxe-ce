"""Unit tests for achievement calculation functions.

Tests pure domain logic - no mocks needed, no I/O.
"""

from datetime import date

from raxe.domain.analytics.achievements import (
    ACHIEVEMENTS,
    calculate_user_achievements,
    check_achievement_unlocked,
    find_next_achievements,
    get_achievement_by_id,
    get_leaderboard_points,
)
from raxe.domain.analytics.models import (
    Achievement,
    StreakMetrics,
    UserAchievements,
)


class TestAchievements:
    """Test suite for ACHIEVEMENTS constant."""

    def test_achievements_list_not_empty(self):
        """ACHIEVEMENTS list should not be empty."""
        assert len(ACHIEVEMENTS) > 0

    def test_all_achievements_have_unique_ids(self):
        """All achievement IDs should be unique."""
        ids = [ach.id for ach in ACHIEVEMENTS]
        assert len(ids) == len(set(ids))

    def test_all_achievements_have_positive_points(self):
        """All achievements should have positive points."""
        for ach in ACHIEVEMENTS:
            assert ach.points > 0

    def test_achievements_have_unlock_conditions(self):
        """All achievements should have unlock conditions."""
        for ach in ACHIEVEMENTS:
            assert ach.unlock_condition
            assert (
                "scan_count >=" in ach.unlock_condition or "streak_count >=" in ach.unlock_condition
            )


class TestGetAchievementById:
    """Test suite for get_achievement_by_id function."""

    def test_get_existing_achievement(self):
        """Get achievement that exists."""
        ach = get_achievement_by_id("first_scan")
        assert ach is not None
        assert ach.id == "first_scan"

    def test_get_nonexistent_achievement(self):
        """Get achievement that doesn't exist returns None."""
        ach = get_achievement_by_id("nonexistent")
        assert ach is None

    def test_get_power_user_achievement(self):
        """Get power_user achievement."""
        ach = get_achievement_by_id("power_user")
        assert ach is not None
        assert ach.name == "Power User"
        assert "100 scans" in ach.description


class TestCheckAchievementUnlocked:
    """Test suite for check_achievement_unlocked function."""

    def test_scan_count_achievement_unlocked(self):
        """Achievement unlocked when scan count threshold met."""
        ach = Achievement("test", "Test", "Test", 10, "scan_count >= 5")
        result = check_achievement_unlocked(ach, scan_count=10, streak_count=0)
        assert result is True

    def test_scan_count_achievement_not_unlocked(self):
        """Achievement not unlocked when scan count below threshold."""
        ach = Achievement("test", "Test", "Test", 10, "scan_count >= 5")
        result = check_achievement_unlocked(ach, scan_count=3, streak_count=0)
        assert result is False

    def test_scan_count_achievement_exactly_at_threshold(self):
        """Achievement unlocked when scan count exactly at threshold."""
        ach = Achievement("test", "Test", "Test", 10, "scan_count >= 5")
        result = check_achievement_unlocked(ach, scan_count=5, streak_count=0)
        assert result is True

    def test_streak_count_achievement_unlocked(self):
        """Achievement unlocked when streak count threshold met."""
        ach = Achievement("test", "Test", "Test", 50, "streak_count >= 7")
        result = check_achievement_unlocked(ach, scan_count=0, streak_count=10)
        assert result is True

    def test_streak_count_achievement_not_unlocked(self):
        """Achievement not unlocked when streak count below threshold."""
        ach = Achievement("test", "Test", "Test", 50, "streak_count >= 7")
        result = check_achievement_unlocked(ach, scan_count=0, streak_count=5)
        assert result is False

    def test_unknown_condition_returns_false(self):
        """Unknown condition type returns False."""
        ach = Achievement("test", "Test", "Test", 10, "unknown_metric >= 5")
        result = check_achievement_unlocked(ach, scan_count=10, streak_count=10)
        assert result is False


class TestCalculateUserAchievements:
    """Test suite for calculate_user_achievements function."""

    def test_no_scans_no_achievements(self):
        """User with no scans has no achievements."""
        streaks = StreakMetrics("u1", 0, 0, 0, date(2025, 1, 15))
        result = calculate_user_achievements("u1", scan_count=0, streak_metrics=streaks)

        assert result.installation_id == "u1"
        assert result.unlocked_achievements == []
        assert result.total_points == 0
        assert result.scan_count == 0
        assert result.streak_count == 0

    def test_first_scan_achievement(self):
        """User with 1 scan unlocks first_scan."""
        streaks = StreakMetrics("u1", 1, 1, 1, date(2025, 1, 15))
        result = calculate_user_achievements("u1", scan_count=1, streak_metrics=streaks)

        assert "first_scan" in result.unlocked_achievements
        assert result.total_points >= 10  # first_scan is 10 points

    def test_power_user_achievement(self):
        """User with 100 scans unlocks power_user."""
        streaks = StreakMetrics("u1", 0, 0, 50, date(2025, 1, 15))
        result = calculate_user_achievements("u1", scan_count=100, streak_metrics=streaks)

        assert "first_scan" in result.unlocked_achievements
        assert "getting_started" in result.unlocked_achievements
        assert "power_user" in result.unlocked_achievements
        assert result.total_points >= 135  # 10 + 25 + 100

    def test_streak_achievement(self):
        """User with 7-day streak unlocks streak_7."""
        streaks = StreakMetrics("u1", 7, 7, 7, date(2025, 1, 15))
        result = calculate_user_achievements("u1", scan_count=7, streak_metrics=streaks)

        assert "streak_3" in result.unlocked_achievements
        assert "streak_7" in result.unlocked_achievements

    def test_multiple_achievements(self):
        """User with high stats unlocks multiple achievements."""
        streaks = StreakMetrics("u1", 30, 30, 100, date(2025, 1, 15))
        result = calculate_user_achievements("u1", scan_count=100, streak_metrics=streaks)

        # Should have scan-based achievements
        assert "first_scan" in result.unlocked_achievements
        assert "power_user" in result.unlocked_achievements

        # Should have streak-based achievements
        assert "streak_7" in result.unlocked_achievements
        assert "streak_30" in result.unlocked_achievements

        # Points should be sum of all unlocked
        assert result.total_points > 0

    def test_achievement_points_calculated_correctly(self):
        """Total points is sum of unlocked achievement points."""
        streaks = StreakMetrics("u1", 0, 0, 1, date(2025, 1, 15))
        result = calculate_user_achievements("u1", scan_count=1, streak_metrics=streaks)

        # Only first_scan (10 points)
        assert result.total_points == 10

    def test_scan_and_streak_count_stored(self):
        """User achievements store scan and streak counts."""
        streaks = StreakMetrics("u1", 7, 10, 15, date(2025, 1, 15))
        result = calculate_user_achievements("u1", scan_count=50, streak_metrics=streaks)

        assert result.scan_count == 50
        assert result.streak_count == 10  # Uses longest_streak


class TestFindNextAchievements:
    """Test suite for find_next_achievements function."""

    def test_no_achievements_returns_all_as_next(self):
        """User with no achievements sees all as next."""
        current = UserAchievements("u1", [], 0, 0, 0)
        next_achs = find_next_achievements(current, max_results=3)

        assert len(next_achs) <= 3
        assert all(isinstance(ach, Achievement) for ach, _ in next_achs)
        assert all(isinstance(progress, int) for _, progress in next_achs)

    def test_finds_closest_achievements(self):
        """Finds achievements closest to unlocking."""
        current = UserAchievements("u1", ["first_scan"], 10, 10, 0)
        next_achs = find_next_achievements(current, max_results=3)

        # getting_started (10 scans) should be first (0 scans needed)
        assert next_achs[0][0].id == "getting_started"
        assert next_achs[0][1] == 0  # Already have 10 scans

    def test_excludes_unlocked_achievements(self):
        """Already unlocked achievements not in results."""
        current = UserAchievements("u1", ["first_scan", "power_user"], 135, 100, 0)
        next_achs = find_next_achievements(current, max_results=10)

        # Should not include first_scan or power_user
        next_ids = [ach.id for ach, _ in next_achs]
        assert "first_scan" not in next_ids
        assert "power_user" not in next_ids

    def test_max_results_limit(self):
        """Respects max_results parameter."""
        current = UserAchievements("u1", [], 0, 0, 0)
        next_achs = find_next_achievements(current, max_results=2)

        assert len(next_achs) <= 2

    def test_sorted_by_progress_needed(self):
        """Results sorted by progress needed (ascending)."""
        current = UserAchievements("u1", [], 0, 5, 2)
        next_achs = find_next_achievements(current, max_results=5)

        # Progress needed should be ascending
        progress_values = [progress for _, progress in next_achs]
        assert progress_values == sorted(progress_values)

    def test_progress_needed_calculation(self):
        """Progress needed is calculated correctly."""
        current = UserAchievements("u1", [], 0, 5, 0)
        next_achs = find_next_achievements(current, max_results=10)

        # Find getting_started (needs 10 scans)
        getting_started = next(
            (ach, prog) for ach, prog in next_achs if ach.id == "getting_started"
        )
        assert getting_started is not None
        assert getting_started[1] == 5  # Need 5 more scans


class TestGetLeaderboardPoints:
    """Test suite for get_leaderboard_points function."""

    def test_empty_leaderboard(self):
        """Empty user data returns empty leaderboard."""
        result = get_leaderboard_points({})
        assert result == []

    def test_single_user_leaderboard(self):
        """Single user leaderboard."""
        achievements = {
            "user1": UserAchievements("user1", ["first_scan"], 10, 1, 0),
        }
        result = get_leaderboard_points(achievements)

        assert len(result) == 1
        assert result[0][0] == "user1"
        assert result[0][1] == 10

    def test_sorted_by_points_descending(self):
        """Leaderboard sorted by points (highest first)."""
        achievements = {
            "user1": UserAchievements("user1", [], 10, 0, 0),
            "user2": UserAchievements("user2", [], 200, 0, 0),
            "user3": UserAchievements("user3", [], 50, 0, 0),
        }
        result = get_leaderboard_points(achievements)

        assert len(result) == 3
        assert result[0][0] == "user2"  # Highest points
        assert result[1][0] == "user3"
        assert result[2][0] == "user1"  # Lowest points

    def test_tied_points(self):
        """Users with same points."""
        achievements = {
            "user1": UserAchievements("user1", [], 100, 0, 0),
            "user2": UserAchievements("user2", [], 100, 0, 0),
        }
        result = get_leaderboard_points(achievements)

        assert len(result) == 2
        # Both have same points
        assert result[0][1] == 100
        assert result[1][1] == 100

    def test_zero_points_users_included(self):
        """Users with 0 points are included."""
        achievements = {
            "user1": UserAchievements("user1", [], 100, 0, 0),
            "user2": UserAchievements("user2", [], 0, 0, 0),
        }
        result = get_leaderboard_points(achievements)

        assert len(result) == 2
        assert result[1][0] == "user2"
        assert result[1][1] == 0
