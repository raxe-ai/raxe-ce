"""Unit tests for RetentionService.

Tests service orchestration - NOT business logic (that's in domain layer).
Uses mock repositories to test I/O coordination.
"""

from datetime import date, datetime
from unittest.mock import Mock

import pytest

from raxe.application.analytics import RetentionService
from raxe.application.analytics.repositories import UserActivity


class TestRetentionService:
    """Test RetentionService orchestration."""

    def test_calculate_user_retention_with_activity(self):
        """Test user retention calculation with valid activity."""
        # Arrange
        mock_repo = Mock()
        mock_repo.get_user_activity.return_value = UserActivity(
            installation_id="user123",
            first_seen=datetime(2025, 1, 1),
            last_seen=datetime(2025, 1, 10),
            total_scans=50,
            total_threats=5,
            scan_dates=[
                date(2025, 1, 1),
                date(2025, 1, 2),  # Day 1
                date(2025, 1, 8),  # Day 7
                date(2025, 1, 10)
            ]
        )

        service = RetentionService(mock_repo)

        # Act
        metrics = service.calculate_user_retention("user123")

        # Assert
        assert metrics.installation_id == "user123"
        assert metrics.day1_retained is True  # Scanned on day 2
        assert metrics.day7_retained is True  # Scanned on day 8
        assert metrics.total_scans == 4
        mock_repo.get_user_activity.assert_called_once_with("user123")

    def test_calculate_user_retention_no_activity(self):
        """Test user retention with no activity returns empty metrics."""
        # Arrange
        mock_repo = Mock()
        mock_repo.get_user_activity.return_value = None

        service = RetentionService(mock_repo)

        # Act
        metrics = service.calculate_user_retention("user123")

        # Assert
        assert metrics.installation_id == "user123"
        assert metrics.day1_retained is False
        assert metrics.day7_retained is False
        assert metrics.day30_retained is False
        assert metrics.total_scans == 0

    def test_calculate_cohort_retention_metrics(self):
        """Test cohort retention calculation."""
        # Arrange
        mock_repo = Mock()
        cohort_date = date(2025, 1, 1)

        # Mock cohort users
        mock_repo.get_cohort_users.return_value = ["user1", "user2", "user3"]

        # Mock user activities
        def get_user_activity_side_effect(user_id):
            activities = {
                "user1": UserActivity(
                    installation_id=user_id,
                    first_seen=datetime(2025, 1, 1),
                    last_seen=datetime(2025, 1, 10),
                    total_scans=10,
                    total_threats=1,
                    scan_dates=[
                        date(2025, 1, 1),
                        date(2025, 1, 2),  # Day 1
                        date(2025, 1, 8),  # Day 7
                    ]
                ),
                "user2": UserActivity(
                    installation_id=user_id,
                    first_seen=datetime(2025, 1, 1),
                    last_seen=datetime(2025, 1, 2),
                    total_scans=2,
                    total_threats=0,
                    scan_dates=[date(2025, 1, 1), date(2025, 1, 2)]
                ),
                "user3": UserActivity(
                    installation_id=user_id,
                    first_seen=datetime(2025, 1, 1),
                    last_seen=datetime(2025, 1, 1),
                    total_scans=1,
                    total_threats=0,
                    scan_dates=[date(2025, 1, 1)]
                ),
            }
            return activities.get(user_id)

        mock_repo.get_user_activity.side_effect = get_user_activity_side_effect

        service = RetentionService(mock_repo)

        # Act
        result = service.calculate_cohort_retention_metrics(cohort_date)

        # Assert
        assert result["cohort_size"] == 3
        assert result["cohort_date"] == cohort_date.isoformat()
        assert 0 <= result["day1_retention_rate"] <= 100
        assert 0 <= result["day7_retention_rate"] <= 100
        assert result["day1_retention_rate"] > 0  # At least user1 and user2 returned

    def test_calculate_cohort_retention_empty_cohort(self):
        """Test cohort retention with no users."""
        # Arrange
        mock_repo = Mock()
        mock_repo.get_cohort_users.return_value = []

        service = RetentionService(mock_repo)

        # Act
        result = service.calculate_cohort_retention_metrics(date(2025, 1, 1))

        # Assert
        assert result["cohort_size"] == 0
        assert result["day1_retention_rate"] == 0.0
        assert result["day7_retention_rate"] == 0.0
        assert result["day30_retention_rate"] == 0.0

    def test_calculate_rolling_retention(self):
        """Test rolling retention calculation."""
        # Arrange
        from raxe.application.analytics.repositories import ScanEvent

        mock_repo = Mock()
        end_date = date(2025, 1, 31)

        # Mock scan events - users active on multiple days
        mock_repo.get_scan_events.return_value = [
            ScanEvent("user1", datetime(2025, 1, 1), "scan_completed", False),
            ScanEvent("user1", datetime(2025, 1, 5), "scan_completed", False),  # Returned
            ScanEvent("user2", datetime(2025, 1, 10), "scan_completed", True),
            ScanEvent("user2", datetime(2025, 1, 15), "scan_completed", False),  # Returned
            ScanEvent("user3", datetime(2025, 1, 20), "scan_completed", False),  # Only 1 day
        ]

        service = RetentionService(mock_repo)

        # Act
        result = service.calculate_rolling_retention(end_date, window_days=30)

        # Assert
        assert result["total_users"] == 3
        assert result["returning_users"] == 2  # user1 and user2 active on 2+ days
        assert result["retention_rate"] > 0

    def test_service_uses_dependency_injection(self):
        """Test service accepts repository via dependency injection."""
        # Arrange
        mock_repo = Mock()

        # Act
        service = RetentionService(mock_repo)

        # Assert
        assert service.repository is mock_repo

    def test_service_logs_on_error(self, caplog):
        """Test service logs errors properly."""
        # Arrange
        mock_repo = Mock()
        mock_repo.get_user_activity.side_effect = Exception("Database error")

        service = RetentionService(mock_repo)

        # Act & Assert
        with pytest.raises(Exception, match="Database error"):
            service.calculate_user_retention("user123")

        # Verify error was logged
        assert "Failed to calculate retention" in caplog.text
