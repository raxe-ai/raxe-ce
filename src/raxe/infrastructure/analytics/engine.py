"""
Analytics engine for calculating metrics and retention.

This module provides analytics calculation for:
- Installation metrics
- Usage metrics
- Retention analysis
- Performance metrics
- Feature adoption
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import and_, case, create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from raxe.infrastructure.database.models import Base, TelemetryEvent
from raxe.utils.validators import validate_date_range

logger = logging.getLogger(__name__)


@dataclass
class InstallationMetrics:
    """Installation-related metrics."""
    total_installations: int = 0
    installations_by_os: dict[str, int] = field(default_factory=dict)
    installations_by_python: dict[str, int] = field(default_factory=dict)
    installations_by_source: dict[str, int] = field(default_factory=dict)
    geographic_distribution: dict[str, int] = field(default_factory=dict)


@dataclass
class UsageMetrics:
    """Usage-related metrics."""
    total_scans: int = 0
    scans_per_user_p50: float = 0.0
    scans_per_user_p95: float = 0.0
    scans_per_user_p99: float = 0.0
    threats_detected: int = 0
    detection_rate: float = 0.0
    avg_scans_per_day: float = 0.0


@dataclass
class RetentionMetrics:
    """Retention-related metrics."""
    dau: int = 0  # Daily Active Users
    wau: int = 0  # Weekly Active Users
    mau: int = 0  # Monthly Active Users
    day1_retention: float = 0.0
    day7_retention: float = 0.0
    day30_retention: float = 0.0


@dataclass
class PerformanceMetrics:
    """Performance-related metrics."""
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    avg_l1_latency_ms: float = 0.0
    avg_l2_latency_ms: float = 0.0
    avg_queue_depth: float = 0.0
    error_rate: float = 0.0


@dataclass
class UserStats:
    """Statistics for a specific user."""
    installation_id: str
    installation_date: datetime | None = None
    time_to_first_scan_seconds: float | None = None
    total_scans: int = 0
    threats_detected: int = 0
    detection_rate: float = 0.0
    last_scan: datetime | None = None
    current_streak: int = 0
    longest_streak: int = 0
    avg_scan_time_ms: float = 0.0
    l1_detections: int = 0
    l2_detections: int = 0


class AnalyticsEngine:
    """
    Analytics calculation engine.

    Calculates metrics from telemetry events stored in local SQLite database.
    All calculations happen locally - no cloud dependency.
    """

    def __init__(self, db_path: Path | None = None):
        """
        Initialize analytics engine.

        Args:
            db_path: Path to SQLite database (defaults to ~/.raxe/telemetry.db)
        """
        if db_path is None:
            db_path = Path.home() / ".raxe" / "telemetry.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create database connection
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,
            connect_args={"check_same_thread": False}
        )

        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)

        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine)

        logger.info(f"Analytics engine initialized with database: {self.db_path}")

    def _get_session(self) -> Session:
        """Create a new database session."""
        return self.SessionLocal()

    def calculate_retention(
        self,
        cohort_date: date,
        *,
        session: Session | None = None
    ) -> dict[str, Any]:
        """
        Calculate retention for installation cohort.

        DEPRECATED: This method delegates to RetentionService for Clean Architecture.
        Maintained for backward compatibility. Use RetentionService directly in new code.

        Args:
            cohort_date: Date of installation cohort
            session: Optional database session

        Returns:
            Dictionary with retention metrics for the cohort
        """
        # REFACTORED: Delegate to application service instead of containing business logic
        from raxe.application.analytics import RetentionService
        from raxe.infrastructure.analytics.repository import SQLiteAnalyticsRepository

        repository = SQLiteAnalyticsRepository(self.db_path)
        service = RetentionService(repository)

        result = service.calculate_cohort_retention_metrics(cohort_date)

        # Return in legacy format for backward compatibility
        return {
            "cohort_date": result["cohort_date"],
            "cohort_size": result["cohort_size"],
            "day_1": result["day1_retention_rate"],
            "day_7": result["day7_retention_rate"],
            "day_30": result["day30_retention_rate"]
        }

    def get_user_stats(
        self,
        installation_id: str,
        *,
        session: Session | None = None
    ) -> UserStats:
        """
        Get statistics for specific user using database aggregation.

        Performance optimization: Uses SQL aggregation instead of loading
        all events into memory. This is critical for users with millions of events.

        UPDATED: Now queries scan_history.db (primary) and falls back to telemetry.db
        if no scan history found. This ensures stats work after SDK integration.

        Args:
            installation_id: User's installation ID (customer_id)
            session: Optional database session

        Returns:
            UserStats object with user-specific metrics
        """
        # UPDATED: Query scan_history.db first (primary source after SDK integration)
        # NOTE: scan_history.db is NOT per-installation, it's global for this machine
        # So we ignore installation_id and just report all scans on this machine
        from raxe.infrastructure.database.scan_history import ScanHistoryDB
        from raxe.infrastructure.tracking.usage import UsageTracker

        try:
            # Try scan_history.db first (created by SDK scans)
            scan_history = ScanHistoryDB()
            usage_tracker = UsageTracker()

            # Get statistics from scan_history.db (all scans on this machine)
            stats = scan_history.get_statistics(days=365)  # Last year

            # Get installation info from usage tracker
            usage_stats = usage_tracker.get_usage_stats()
            install_info = usage_tracker.get_install_info()

            total_scans = stats.get('total_scans', 0)

            # IMPORTANT: Only use scan_history if we actually have data
            # In test environments, scan_history.db might be empty or non-existent
            if total_scans > 0:
                # We have scan history data - use it (global machine stats)
                scans_with_threats = stats.get('scans_with_threats', 0)
                detection_rate = stats.get('threat_rate', 0.0) * 100

                # Get L1/L2 breakdown from recent scans
                recent_scans = scan_history.list_scans(limit=100)
                l1_detections = sum(s.l1_detections for s in recent_scans)
                l2_detections = sum(s.l2_detections for s in recent_scans)

                # Get installation and first scan times
                installation_date = None
                time_to_first_scan = None
                if install_info:
                    installed_at_str = install_info.installed_at
                    if installed_at_str:
                        installation_date = datetime.fromisoformat(installed_at_str)

                # Get last scan time
                last_scan = None
                if usage_stats:
                    time_to_first_scan = usage_stats.time_to_first_scan_seconds
                    last_scan_str = usage_stats.last_scan_at
                    if last_scan_str:
                        last_scan = datetime.fromisoformat(last_scan_str)

                # Calculate streaks from scan history
                all_scans = scan_history.list_scans(limit=1000)
                scan_dates = [s.timestamp.date() for s in all_scans]
                current_streak, longest_streak = self._calculate_streaks_from_dates(scan_dates)

                # Handle None values for avg_total_duration_ms
                avg_duration = stats.get('avg_total_duration_ms') or 0.0

                result = UserStats(
                    installation_id=installation_id,
                    installation_date=installation_date,
                    time_to_first_scan_seconds=time_to_first_scan,
                    total_scans=total_scans,
                    threats_detected=scans_with_threats,
                    detection_rate=round(detection_rate, 2),
                    last_scan=last_scan,
                    current_streak=current_streak,
                    longest_streak=longest_streak,
                    avg_scan_time_ms=round(avg_duration, 2),
                    l1_detections=l1_detections,
                    l2_detections=l2_detections
                )
                return result
        except Exception as e:
            # Fall back to telemetry.db if scan_history.db has issues
            logger.debug(f"Scan history query failed, falling back to telemetry.db: {e}")

        # FALLBACK: Query telemetry.db (legacy behavior)
        close_session = session is None
        if session is None:
            session = self._get_session()

        try:
            # OPTIMIZED: Use database aggregation instead of loading all events
            stats = session.query(
                func.count(TelemetryEvent.id).label('total_scans'),
                func.sum(
                    case((TelemetryEvent.detection_count > 0, 1), else_=0)
                ).label('threats_detected'),
                func.avg(TelemetryEvent.total_latency_ms).label('avg_scan_time'),
                func.max(TelemetryEvent.timestamp).label('last_scan'),
                func.min(TelemetryEvent.timestamp).label('installation_date'),
                func.sum(
                    case(
                        (and_(TelemetryEvent.l2_inference_ms.isnot(None), TelemetryEvent.l2_inference_ms > 0), 1),
                        else_=0
                    )
                ).label('l2_detections'),
            ).filter(
                TelemetryEvent.customer_id == installation_id
            ).first()

            if not stats or stats.total_scans == 0:
                return UserStats(installation_id=installation_id)

            # Calculate derived metrics
            total_scans = stats.total_scans or 0
            threats_detected = stats.threats_detected or 0
            detection_rate = (threats_detected / total_scans * 100) if total_scans > 0 else 0.0
            l2_detections = stats.l2_detections or 0
            l1_detections = total_scans - l2_detections

            # Calculate time to first scan
            # Get the two earliest events for this calculation
            time_to_first_scan = None
            first_two_events = session.query(TelemetryEvent.timestamp).filter(
                TelemetryEvent.customer_id == installation_id
            ).order_by(TelemetryEvent.timestamp).limit(2).all()

            if len(first_two_events) == 2:
                time_to_first_scan = (first_two_events[1][0] - first_two_events[0][0]).total_seconds()

            # Calculate streaks (still needs scan dates, but we only query dates, not full events)
            scan_dates = session.query(
                func.date(TelemetryEvent.timestamp).label('scan_date')
            ).filter(
                TelemetryEvent.customer_id == installation_id
            ).distinct().order_by('scan_date').all()

            # Convert to date objects for streak calculation
            unique_dates = [d[0] for d in scan_dates]
            current_streak, longest_streak = self._calculate_streaks_from_dates(unique_dates)

            return UserStats(
                installation_id=installation_id,
                installation_date=stats.installation_date,
                time_to_first_scan_seconds=time_to_first_scan,
                total_scans=total_scans,
                threats_detected=threats_detected,
                detection_rate=round(detection_rate, 2),
                last_scan=stats.last_scan,
                current_streak=current_streak,
                longest_streak=longest_streak,
                avg_scan_time_ms=round(float(stats.avg_scan_time or 0), 2),
                l1_detections=l1_detections,
                l2_detections=l2_detections
            )

        finally:
            if close_session:
                session.close()

    def _calculate_streaks(self, events: list[TelemetryEvent]) -> tuple[int, int]:
        """
        Calculate current and longest streaks from events.

        DEPRECATED: Use _calculate_streaks_from_dates for better performance.
        This method is kept for backward compatibility.

        Args:
            events: List of telemetry events (must be sorted by timestamp)

        Returns:
            Tuple of (current_streak, longest_streak) in days
        """
        if not events:
            return 0, 0

        # Get unique days with scans
        scan_dates = set()
        for event in events:
            scan_date = event.timestamp.date()
            scan_dates.add(scan_date)

        sorted_dates = sorted(scan_dates)
        return self._calculate_streaks_from_dates(sorted_dates)

    def _calculate_streaks_from_dates(self, scan_dates: list) -> tuple[int, int]:
        """
        Calculate current and longest streaks from scan dates.

        Performance optimized version that works directly with dates
        instead of full event objects.

        Args:
            scan_dates: List of date objects (can be datetime.date or string dates)

        Returns:
            Tuple of (current_streak, longest_streak) in days
        """
        if not scan_dates:
            return 0, 0

        # Convert to date objects if needed
        if scan_dates and isinstance(scan_dates[0], str):
            from datetime import datetime as dt
            sorted_dates = sorted([dt.fromisoformat(d).date() for d in scan_dates])
        elif scan_dates and isinstance(scan_dates[0], datetime):
            sorted_dates = sorted([d.date() for d in scan_dates])
        else:
            sorted_dates = sorted(scan_dates)

        if not sorted_dates:
            return 0, 0

        # Calculate current streak
        current_streak = 1
        today = datetime.now(timezone.utc).date()

        if sorted_dates[-1] == today or sorted_dates[-1] == today - timedelta(days=1):
            # Active streak
            current_date = sorted_dates[-1]
            for i in range(len(sorted_dates) - 2, -1, -1):
                if sorted_dates[i] == current_date - timedelta(days=1):
                    current_streak += 1
                    current_date = sorted_dates[i]
                else:
                    break
        else:
            # Streak broken
            current_streak = 0

        # Calculate longest streak
        longest_streak = 1
        temp_streak = 1

        for i in range(1, len(sorted_dates)):
            if sorted_dates[i] == sorted_dates[i-1] + timedelta(days=1):
                temp_streak += 1
                longest_streak = max(longest_streak, temp_streak)
            else:
                temp_streak = 1

        return current_streak, longest_streak

    def get_global_stats(
        self,
        *,
        session: Session | None = None
    ) -> dict[str, Any]:
        """
        Get aggregate platform statistics.

        Args:
            session: Optional database session

        Returns:
            Dictionary with global platform metrics
        """
        close_session = session is None
        if session is None:
            session = self._get_session()

        try:
            now = datetime.now(timezone.utc)
            week_ago = now - timedelta(days=7)

            # Total users (unique customer IDs)
            total_users = session.query(TelemetryEvent.customer_id).distinct().count()

            # Active this week
            active_week = session.query(TelemetryEvent.customer_id).filter(
                TelemetryEvent.timestamp >= week_ago
            ).distinct().count()

            # Total scans
            total_scans = session.query(func.count(TelemetryEvent.id)).scalar() or 0

            # Total threats
            total_threats = session.query(func.count(TelemetryEvent.id)).filter(
                TelemetryEvent.detection_count > 0
            ).scalar() or 0

            detection_rate = (total_threats / total_scans * 100) if total_scans > 0 else 0.0

            # Critical threats
            critical_threats = session.query(func.count(TelemetryEvent.id)).filter(
                TelemetryEvent.highest_severity == "critical"
            ).scalar() or 0

            # Performance metrics
            avg_latency = session.query(func.avg(TelemetryEvent.total_latency_ms)).scalar() or 0.0

            # Get P95 latency (approximate using percentile)
            total_count = session.query(func.count(TelemetryEvent.id)).scalar() or 0
            p95_index = int(total_count * 0.95)

            p95_latency = 0.0
            if p95_index > 0:
                p95_event = session.query(TelemetryEvent.total_latency_ms).order_by(
                    TelemetryEvent.total_latency_ms
                ).offset(p95_index).first()
                if p95_event:
                    p95_latency = p95_event[0]

            # Top severity breakdown
            severity_counts = {}
            for severity in ["critical", "high", "medium", "low", "info"]:
                count = session.query(func.count(TelemetryEvent.id)).filter(
                    TelemetryEvent.highest_severity == severity
                ).scalar() or 0
                if count > 0:
                    severity_counts[severity] = count

            return {
                "community": {
                    "total_users": total_users,
                    "active_this_week": active_week,
                    "total_scans": total_scans
                },
                "threats": {
                    "total_detected": total_threats,
                    "detection_rate": round(detection_rate, 2),
                    "critical_threats": critical_threats,
                    "by_severity": severity_counts
                },
                "performance": {
                    "avg_scan_time_ms": round(avg_latency, 2),
                    "p95_latency_ms": round(p95_latency, 2)
                }
            }

        finally:
            if close_session:
                session.close()

    def generate_report(
        self,
        start_date: date,
        end_date: date,
        *,
        session: Session | None = None
    ) -> dict[str, Any]:
        """
        Generate analytics report for date range.

        Args:
            start_date: Report start date
            end_date: Report end date
            session: Optional database session

        Returns:
            Comprehensive analytics report

        Raises:
            ValidationError: If date range is invalid
        """
        close_session = session is None
        if session is None:
            session = self._get_session()

        try:
            start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

            # Validate date range (security: prevent DoS and invalid inputs)
            validate_date_range(start_dt, end_dt, max_days=730)

            # Get events in date range
            events = session.query(TelemetryEvent).filter(
                and_(
                    TelemetryEvent.timestamp >= start_dt,
                    TelemetryEvent.timestamp <= end_dt
                )
            ).all()

            # Calculate metrics
            total_scans = len(events)
            unique_users = len({e.customer_id for e in events})
            threats_detected = sum(1 for e in events if e.detection_count > 0)

            # Average metrics
            avg_latency = sum(e.total_latency_ms for e in events) / total_scans if total_scans > 0 else 0.0
            avg_l1 = sum(e.l1_inference_ms for e in events) / total_scans if total_scans > 0 else 0.0

            l2_events = [e for e in events if e.l2_inference_ms is not None]
            avg_l2 = sum(e.l2_inference_ms for e in l2_events) / len(l2_events) if l2_events else 0.0

            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": (end_date - start_date).days + 1
                },
                "overview": {
                    "total_scans": total_scans,
                    "unique_users": unique_users,
                    "threats_detected": threats_detected,
                    "detection_rate": round((threats_detected / total_scans * 100) if total_scans > 0 else 0.0, 2)
                },
                "performance": {
                    "avg_total_latency_ms": round(avg_latency, 2),
                    "avg_l1_latency_ms": round(avg_l1, 2),
                    "avg_l2_latency_ms": round(avg_l2, 2)
                },
                "scans_per_day": round(total_scans / ((end_date - start_date).days + 1), 2) if total_scans > 0 else 0.0
            }

        finally:
            if close_session:
                session.close()

    def get_user_events_paginated(
        self,
        installation_id: str,
        *,
        limit: int = 1000,
        offset: int = 0,
        session: Session | None = None
    ) -> list[TelemetryEvent]:
        """
        Get user events with pagination to avoid memory issues.

        Performance optimization: Fetch events in batches instead of
        loading millions of rows at once.

        Args:
            installation_id: User's installation ID
            limit: Maximum number of events to return
            offset: Number of events to skip
            session: Optional database session

        Returns:
            List of TelemetryEvent objects (up to limit)
        """
        close_session = session is None
        if session is None:
            session = self._get_session()

        try:
            return session.query(TelemetryEvent).filter(
                TelemetryEvent.customer_id == installation_id
            ).order_by(
                TelemetryEvent.timestamp.desc()
            ).limit(limit).offset(offset).all()

        finally:
            if close_session:
                session.close()

    def get_scan_dates_for_user(
        self,
        installation_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        *,
        session: Session | None = None
    ) -> list[date]:
        """
        Get unique scan dates for a user using database aggregation.

        Performance optimization: Much faster than loading all events
        into memory. Uses database DISTINCT to return only unique dates.

        Args:
            installation_id: User's installation ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            session: Optional database session

        Returns:
            List of unique scan dates
        """
        close_session = session is None
        if session is None:
            session = self._get_session()

        try:
            query = session.query(
                func.date(TelemetryEvent.timestamp).label('scan_date')
            ).filter(
                TelemetryEvent.customer_id == installation_id
            )

            if start_date:
                start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                query = query.filter(TelemetryEvent.timestamp >= start_dt)

            if end_date:
                end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
                query = query.filter(TelemetryEvent.timestamp <= end_dt)

            # Returns list of dates, not full event objects
            result = query.distinct().order_by('scan_date').all()
            return [row[0] for row in result]

        finally:
            if close_session:
                session.close()

    def calculate_retention_batch(
        self,
        installation_ids: list[str],
        cohort_date: date,
        *,
        session: Session | None = None
    ) -> dict[str, dict[str, Any]]:
        """
        Calculate retention for multiple users in one query.

        Performance optimization: Avoids N+1 query problem by batching
        all user retention calculations together.

        Args:
            installation_ids: List of installation IDs
            cohort_date: Cohort date to analyze
            session: Optional database session

        Returns:
            Dictionary mapping installation_id to retention metrics
        """
        close_session = session is None
        if session is None:
            session = self._get_session()

        try:
            results = {}

            # Batch query for all users
            cohort_start = datetime.combine(cohort_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            cohort_start + timedelta(days=1)

            # Get all events for these users in one query
            events = session.query(
                TelemetryEvent.customer_id,
                func.date(TelemetryEvent.timestamp).label('event_date')
            ).filter(
                TelemetryEvent.customer_id.in_(installation_ids)
            ).all()

            # Group by customer
            by_customer = {}
            for customer_id, event_date in events:
                if customer_id not in by_customer:
                    by_customer[customer_id] = set()
                by_customer[customer_id].add(event_date)

            # Calculate retention for each user
            for installation_id in installation_ids:
                user_dates = by_customer.get(installation_id, set())

                # Check activity on specific days
                day_1 = cohort_date + timedelta(days=1)
                day_7 = cohort_date + timedelta(days=7)
                day_30 = cohort_date + timedelta(days=30)

                results[installation_id] = {
                    "day_1": day_1 in user_dates,
                    "day_7": day_7 in user_dates,
                    "day_30": day_30 in user_dates,
                    "total_active_days": len(user_dates)
                }

            return results

        finally:
            if close_session:
                session.close()

    def close(self) -> None:
        """Close database connection."""
        self.engine.dispose()
        logger.info("Analytics engine closed")
