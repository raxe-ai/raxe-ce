"""Repository interfaces for analytics data access.

These are abstract interfaces that define contracts for data access.
Concrete implementations live in infrastructure layer.

CRITICAL: This defines the boundary between application and infrastructure.
Domain layer never imports this - only application layer uses repositories.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass
class ScanEvent:
    """Scan event data for analytics.

    This is a data transfer object (DTO) that represents a scan event
    without coupling to infrastructure database models.

    Args:
        installation_id: User's installation identifier
        timestamp: When the scan occurred
        event_type: Type of event (e.g., "scan_completed")
        has_threats: Whether threats were detected
        severity: Highest severity level detected (optional)
        scan_duration_ms: Duration of scan in milliseconds (optional)
    """
    installation_id: str
    timestamp: datetime
    event_type: str
    has_threats: bool
    severity: str | None = None
    scan_duration_ms: float | None = None


@dataclass
class UserActivity:
    """User activity data for analytics.

    Aggregated user activity information needed for analytics calculations.

    Args:
        installation_id: User's installation identifier
        first_seen: First scan timestamp
        last_seen: Most recent scan timestamp
        total_scans: Total number of scans performed
        total_threats: Total number of threats detected
        scan_dates: List of unique dates with scan activity
    """
    installation_id: str
    first_seen: datetime
    last_seen: datetime
    total_scans: int
    total_threats: int
    scan_dates: list[date]


class AnalyticsRepository(ABC):
    """Abstract repository for analytics data access.

    This interface defines the contract for all analytics data operations.
    Concrete implementations (SQLite, Postgres, etc.) must implement all methods.

    CRITICAL: This is the application/infrastructure boundary.
    All I/O operations must go through repository implementations.
    """

    @abstractmethod
    def get_scan_events(
        self,
        start_date: date,
        end_date: date,
        installation_id: str | None = None
    ) -> list[ScanEvent]:
        """Get scan events within date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            installation_id: Optional filter for specific user

        Returns:
            List of ScanEvent objects matching criteria
        """
        pass

    @abstractmethod
    def get_user_activity(
        self,
        installation_id: str,
        start_date: date | None = None,
        end_date: date | None = None
    ) -> UserActivity | None:
        """Get user activity summary.

        Args:
            installation_id: User's installation identifier
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            UserActivity object or None if user not found
        """
        pass

    @abstractmethod
    def get_cohort_users(
        self,
        cohort_date: date
    ) -> list[str]:
        """Get list of users who joined on specific date.

        Args:
            cohort_date: Date to find new installations

        Returns:
            List of installation IDs who first appeared on cohort_date
        """
        pass

    @abstractmethod
    def get_active_users(
        self,
        target_date: date,
        window_days: int = 1
    ) -> list[str]:
        """Get active users within window of target date.

        Args:
            target_date: Reference date for activity check
            window_days: Number of days before target_date to include

        Returns:
            List of installation IDs active in the window
        """
        pass

    @abstractmethod
    def save_achievement(
        self,
        installation_id: str,
        achievement_id: str,
        earned_at: datetime,
        metadata: dict[str, Any]
    ) -> None:
        """Save achievement earned by user.

        Args:
            installation_id: User who earned the achievement
            achievement_id: Unique achievement identifier
            earned_at: Timestamp when achievement was earned
            metadata: Additional achievement data (name, points, etc.)
        """
        pass

    @abstractmethod
    def get_achievements(
        self,
        installation_id: str
    ) -> list[dict[str, Any]]:
        """Get all achievements for user.

        Args:
            installation_id: User to query

        Returns:
            List of achievement dictionaries with metadata
        """
        pass
