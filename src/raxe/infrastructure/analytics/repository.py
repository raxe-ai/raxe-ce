"""Concrete repository implementation for analytics data access.

This is the infrastructure layer implementation of the repository interface.
Handles all database I/O for analytics using SQLite.

CRITICAL: This is infrastructure layer - ALL I/O operations happen here.
No business logic - just data access.
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import and_, create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from raxe.application.analytics.repositories import AnalyticsRepository, ScanEvent, UserActivity
from raxe.infrastructure.database.models import Base, TelemetryEvent

logger = logging.getLogger(__name__)


class SQLiteAnalyticsRepository(AnalyticsRepository):
    """SQLite implementation of analytics repository.

    Handles all database I/O for analytics data using SQLAlchemy.
    Optimized queries using database aggregation instead of loading
    all data into memory.

    CRITICAL: This is infrastructure - no business logic, only I/O.
    """

    def __init__(self, db_path: Path | None = None):
        """Initialize SQLite repository.

        Args:
            db_path: Path to SQLite database (defaults to ~/.raxe/telemetry.db)
        """
        if db_path is None:
            db_path = Path.home() / ".raxe" / "telemetry.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create database engine
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            connect_args={"check_same_thread": False}
        )

        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)

        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine)

        logger.info(f"SQLite analytics repository initialized: {db_path}")

    def _get_session(self) -> Session:
        """Create a new database session.

        Returns:
            SQLAlchemy session
        """
        return self.SessionLocal()

    def get_scan_events(
        self,
        start_date: date,
        end_date: date,
        installation_id: str | None = None
    ) -> list[ScanEvent]:
        """Get scan events within date range.

        Uses database filtering to only load relevant events.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            installation_id: Optional filter for specific user

        Returns:
            List of ScanEvent objects matching criteria
        """
        session = self._get_session()
        try:
            # Convert dates to datetime with timezone
            start_dt = datetime.combine(
                start_date,
                datetime.min.time()
            ).replace(tzinfo=timezone.utc)
            end_dt = datetime.combine(
                end_date,
                datetime.max.time()
            ).replace(tzinfo=timezone.utc)

            # Build query with filters
            query = session.query(TelemetryEvent).filter(
                and_(
                    TelemetryEvent.timestamp >= start_dt,
                    TelemetryEvent.timestamp <= end_dt,
                    TelemetryEvent.event_type == "scan_completed"
                )
            )

            if installation_id:
                query = query.filter(TelemetryEvent.customer_id == installation_id)

            # Execute query and convert to DTOs
            events = []
            for row in query.all():
                # Parse event data JSON
                if row.event_data:
                    try:
                        json.loads(row.event_data)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse event_data for event {row.id}")

                events.append(ScanEvent(
                    installation_id=row.customer_id,
                    timestamp=row.timestamp,
                    event_type=row.event_type,
                    has_threats=row.detection_count > 0,
                    severity=row.highest_severity,
                    scan_duration_ms=row.total_latency_ms
                ))

            logger.debug(
                f"Loaded {len(events)} scan events for period "
                f"{start_date} to {end_date}"
            )

            return events

        finally:
            session.close()

    def get_user_activity(
        self,
        installation_id: str,
        start_date: date | None = None,
        end_date: date | None = None
    ) -> UserActivity | None:
        """Get user activity summary.

        Uses database aggregation for performance.

        Args:
            installation_id: User's installation identifier
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            UserActivity object or None if user not found
        """
        session = self._get_session()
        try:
            # Build query with optional date filters
            query = session.query(TelemetryEvent).filter(
                TelemetryEvent.customer_id == installation_id
            )

            if start_date:
                start_dt = datetime.combine(
                    start_date,
                    datetime.min.time()
                ).replace(tzinfo=timezone.utc)
                query = query.filter(TelemetryEvent.timestamp >= start_dt)

            if end_date:
                end_dt = datetime.combine(
                    end_date,
                    datetime.max.time()
                ).replace(tzinfo=timezone.utc)
                query = query.filter(TelemetryEvent.timestamp <= end_dt)

            events = query.all()

            if not events:
                return None

            # Aggregate activity data
            first_seen = min(e.timestamp for e in events)
            last_seen = max(e.timestamp for e in events)

            # Get unique scan dates (for streak calculation)
            scan_dates = list({
                e.timestamp.date()
                for e in events
                if e.event_type == "scan_completed"
            })

            # Count scans and threats
            total_scans = sum(
                1 for e in events
                if e.event_type == "scan_completed"
            )

            total_threats = sum(
                1 for e in events
                if e.event_type == "scan_completed" and e.detection_count > 0
            )

            return UserActivity(
                installation_id=installation_id,
                first_seen=first_seen,
                last_seen=last_seen,
                total_scans=total_scans,
                total_threats=total_threats,
                scan_dates=sorted(scan_dates)
            )

        finally:
            session.close()

    def get_cohort_users(self, cohort_date: date) -> list[str]:
        """Get list of users who joined on specific date.

        A user "joined" on the date of their first event.

        Args:
            cohort_date: Date to find new installations

        Returns:
            List of installation IDs who first appeared on cohort_date
        """
        session = self._get_session()
        try:
            start_dt = datetime.combine(
                cohort_date,
                datetime.min.time()
            ).replace(tzinfo=timezone.utc)
            end_dt = start_dt + timedelta(days=1)

            # Find users whose first event was on cohort_date
            # Using subquery to find first timestamp per user
            subquery = session.query(
                TelemetryEvent.customer_id,
                func.min(TelemetryEvent.timestamp).label('first_seen')
            ).group_by(TelemetryEvent.customer_id).subquery()

            cohort_users = session.query(subquery.c.customer_id).filter(
                and_(
                    subquery.c.first_seen >= start_dt,
                    subquery.c.first_seen < end_dt
                )
            ).all()

            user_ids = [user[0] for user in cohort_users]

            logger.debug(
                f"Found {len(user_ids)} users in cohort {cohort_date}"
            )

            return user_ids

        finally:
            session.close()

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
        session = self._get_session()
        try:
            # Calculate window boundaries
            end_dt = datetime.combine(
                target_date,
                datetime.max.time()
            ).replace(tzinfo=timezone.utc)
            start_dt = end_dt - timedelta(days=window_days - 1)
            start_dt = start_dt.replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            # Query for distinct users in window
            active_users = session.query(
                TelemetryEvent.customer_id
            ).filter(
                and_(
                    TelemetryEvent.timestamp >= start_dt,
                    TelemetryEvent.timestamp <= end_dt,
                    TelemetryEvent.event_type == "scan_completed"
                )
            ).distinct().all()

            user_ids = [user[0] for user in active_users]

            logger.debug(
                f"Found {len(user_ids)} active users in window "
                f"{window_days} days ending {target_date}"
            )

            return user_ids

        finally:
            session.close()

    def save_achievement(
        self,
        installation_id: str,
        achievement_id: str,
        earned_at: datetime,
        metadata: dict[str, Any]
    ) -> None:
        """Save achievement earned by user.

        Currently stores in local JSON file. Can be migrated to
        database table later if needed.

        Args:
            installation_id: User who earned the achievement
            achievement_id: Unique achievement identifier
            earned_at: Timestamp when achievement was earned
            metadata: Additional achievement data (name, points, etc.)
        """
        # Store in local JSON file for now
        achievements_dir = Path.home() / ".raxe" / "achievements"
        achievements_dir.mkdir(parents=True, exist_ok=True)

        user_file = achievements_dir / f"{installation_id}.json"

        # Load existing achievements
        achievements = []
        if user_file.exists():
            try:
                with open(user_file) as f:
                    achievements = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(
                    f"Failed to load existing achievements for {installation_id}: {e}"
                )

        # Add new achievement
        achievements.append({
            'achievement_id': achievement_id,
            'earned_at': earned_at.isoformat(),
            **metadata
        })

        # Save back
        try:
            with open(user_file, 'w') as f:
                json.dump(achievements, f, indent=2)

            logger.debug(
                f"Saved achievement {achievement_id} for {installation_id}"
            )

        except OSError as e:
            logger.error(
                f"Failed to save achievement for {installation_id}: {e}"
            )
            raise

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
        achievements_dir = Path.home() / ".raxe" / "achievements"
        user_file = achievements_dir / f"{installation_id}.json"

        if not user_file.exists():
            return []

        try:
            with open(user_file) as f:
                achievements = json.load(f)

            logger.debug(
                f"Loaded {len(achievements)} achievements for {installation_id}"
            )

            return achievements

        except (OSError, json.JSONDecodeError) as e:
            logger.warning(
                f"Failed to load achievements for {installation_id}: {e}"
            )
            return []

    def close(self) -> None:
        """Close database connection.

        Disposes of the SQLAlchemy engine connection pool.
        """
        self.engine.dispose()
        logger.info("SQLite analytics repository closed")
