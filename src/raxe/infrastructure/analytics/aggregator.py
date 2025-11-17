"""
Data aggregator for analytics.

Aggregates local scan history into analytics-ready format with:
- Daily and hourly rollups
- Detection pattern analysis
- Performance trend tracking
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import and_, case, create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from raxe.infrastructure.database.models import Base, TelemetryEvent
from raxe.utils.validators import validate_date_range, validate_positive_integer

logger = logging.getLogger(__name__)


@dataclass
class DailyRollup:
    """Daily aggregated statistics."""
    date: date
    total_scans: int
    total_threats: int
    avg_duration_ms: float
    max_duration_ms: float
    unique_users: int
    detection_rate: float


@dataclass
class HourlyPattern:
    """Hourly usage pattern."""
    hour: int
    scan_count: int
    threat_count: int
    avg_duration_ms: float


@dataclass
class DetectionBreakdown:
    """Detection breakdown by category/severity."""
    severity: str
    count: int
    percentage: float


class DataAggregator:
    """
    Data aggregation for analytics.

    Provides aggregated views of telemetry data for efficient analytics queries.
    """

    def __init__(self, db_path: Path | None = None):
        """
        Initialize data aggregator.

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

        logger.info(f"Data aggregator initialized with database: {self.db_path}")

    def _get_session(self) -> Session:
        """Create a new database session."""
        return self.SessionLocal()

    def get_daily_rollup(
        self,
        start_date: date,
        end_date: date,
        *,
        session: Session | None = None
    ) -> list[DailyRollup]:
        """
        Get daily aggregated statistics using SQL aggregation.

        Performance optimization: Uses database GROUP BY instead of
        loading all events into memory.

        Args:
            start_date: Start date
            end_date: End date (inclusive)
            session: Optional database session

        Returns:
            List of DailyRollup objects, one per day

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

            # OPTIMIZED: Use SQL aggregation instead of loading all rows
            daily_stats = session.query(
                func.date(TelemetryEvent.timestamp).label('event_date'),
                func.count(TelemetryEvent.id).label('total_scans'),
                func.sum(
                    case((TelemetryEvent.detection_count > 0, 1), else_=0)
                ).label('total_threats'),
                func.avg(TelemetryEvent.total_latency_ms).label('avg_duration'),
                func.max(TelemetryEvent.total_latency_ms).label('max_duration'),
                func.count(func.distinct(TelemetryEvent.customer_id)).label('unique_users')
            ).filter(
                and_(
                    TelemetryEvent.timestamp >= start_dt,
                    TelemetryEvent.timestamp <= end_dt
                )
            ).group_by(
                func.date(TelemetryEvent.timestamp)
            ).all()

            # Convert to dictionary for easy lookup
            stats_by_date = {}
            for row in daily_stats:
                event_date = row.event_date
                total_scans = row.total_scans or 0
                total_threats = row.total_threats or 0
                detection_rate = (total_threats / total_scans * 100) if total_scans > 0 else 0.0

                stats_by_date[event_date] = DailyRollup(
                    date=event_date,
                    total_scans=total_scans,
                    total_threats=total_threats,
                    avg_duration_ms=round(float(row.avg_duration or 0), 2),
                    max_duration_ms=round(float(row.max_duration or 0), 2),
                    unique_users=row.unique_users or 0,
                    detection_rate=round(detection_rate, 2)
                )

            # Create rollups for all dates in range (including days with no activity)
            rollups = []
            current_date = start_date
            while current_date <= end_date:
                if current_date in stats_by_date:
                    rollups.append(stats_by_date[current_date])
                else:
                    # No activity on this day
                    rollups.append(DailyRollup(
                        date=current_date,
                        total_scans=0,
                        total_threats=0,
                        avg_duration_ms=0.0,
                        max_duration_ms=0.0,
                        unique_users=0,
                        detection_rate=0.0
                    ))

                current_date += timedelta(days=1)

            return rollups

        finally:
            if close_session:
                session.close()

    def get_hourly_patterns(
        self,
        days: int = 30,
        *,
        session: Session | None = None
    ) -> list[HourlyPattern]:
        """
        Get hourly usage patterns.

        Analyzes when users scan most frequently by aggregating
        scan activity by hour of day.

        Args:
            days: Number of days to look back
            session: Optional database session

        Returns:
            List of HourlyPattern objects (24 hours)

        Raises:
            ValidationError: If days parameter is invalid
        """
        close_session = session is None
        if session is None:
            session = self._get_session()

        try:
            # Validate days parameter (security: prevent DoS)
            validate_positive_integer(days, "days")
            if days > 730:  # Max 2 years
                from raxe.utils.validators import ValidationError
                raise ValidationError(f"days parameter too large: {days} (maximum: 730)")

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            # Get events in time window
            events = session.query(TelemetryEvent).filter(
                TelemetryEvent.timestamp >= cutoff
            ).all()

            # Group by hour
            hourly_data: dict[int, list[TelemetryEvent]] = {h: [] for h in range(24)}
            for event in events:
                hour = event.timestamp.hour
                hourly_data[hour].append(event)

            # Create patterns
            patterns = []
            for hour in range(24):
                hour_events = hourly_data[hour]
                scan_count = len(hour_events)
                threat_count = sum(1 for e in hour_events if e.detection_count > 0)
                avg_duration = (
                    sum(e.total_latency_ms for e in hour_events) / scan_count
                    if scan_count > 0
                    else 0.0
                )

                patterns.append(HourlyPattern(
                    hour=hour,
                    scan_count=scan_count,
                    threat_count=threat_count,
                    avg_duration_ms=round(avg_duration, 2)
                ))

            return patterns

        finally:
            if close_session:
                session.close()

    def get_detection_breakdown(
        self,
        days: int = 30,
        *,
        session: Session | None = None
    ) -> list[DetectionBreakdown]:
        """
        Get detection breakdown by severity.

        Args:
            days: Number of days to look back
            session: Optional database session

        Returns:
            List of DetectionBreakdown objects
        """
        close_session = session is None
        if session is None:
            session = self._get_session()

        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            # Get total detections
            total_detections = session.query(func.count(TelemetryEvent.id)).filter(
                and_(
                    TelemetryEvent.timestamp >= cutoff,
                    TelemetryEvent.detection_count > 0
                )
            ).scalar() or 0

            if total_detections == 0:
                return []

            # Count by severity
            breakdowns = []
            for severity in ["critical", "high", "medium", "low", "info"]:
                count = session.query(func.count(TelemetryEvent.id)).filter(
                    and_(
                        TelemetryEvent.timestamp >= cutoff,
                        TelemetryEvent.highest_severity == severity
                    )
                ).scalar() or 0

                if count > 0:
                    percentage = (count / total_detections * 100)
                    breakdowns.append(DetectionBreakdown(
                        severity=severity,
                        count=count,
                        percentage=round(percentage, 2)
                    ))

            # Sort by count descending
            breakdowns.sort(key=lambda x: x.count, reverse=True)

            return breakdowns

        finally:
            if close_session:
                session.close()

    def get_performance_trends(
        self,
        days: int = 30,
        *,
        session: Session | None = None
    ) -> dict[str, Any]:
        """
        Get performance trends over time.

        Args:
            days: Number of days to look back
            session: Optional database session

        Returns:
            Dictionary with performance trend data
        """
        close_session = session is None
        if session is None:
            session = self._get_session()

        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            # Get events
            events = session.query(TelemetryEvent).filter(
                TelemetryEvent.timestamp >= cutoff
            ).order_by(TelemetryEvent.timestamp).all()

            if not events:
                return {
                    "avg_latency_ms": 0.0,
                    "min_latency_ms": 0.0,
                    "max_latency_ms": 0.0,
                    "p50_latency_ms": 0.0,
                    "p95_latency_ms": 0.0,
                    "p99_latency_ms": 0.0,
                    "trend": "stable",
                    "sample_size": 0
                }

            # Calculate percentiles
            latencies = sorted([e.total_latency_ms for e in events])
            total_count = len(latencies)

            avg_latency = sum(latencies) / total_count
            min_latency = latencies[0]
            max_latency = latencies[-1]

            p50_index = int(total_count * 0.50)
            p95_index = int(total_count * 0.95)
            p99_index = int(total_count * 0.99)

            p50_latency = latencies[p50_index] if p50_index < total_count else latencies[-1]
            p95_latency = latencies[p95_index] if p95_index < total_count else latencies[-1]
            p99_latency = latencies[p99_index] if p99_index < total_count else latencies[-1]

            # Calculate trend (compare first half vs second half)
            midpoint = total_count // 2
            first_half_avg = sum(latencies[:midpoint]) / midpoint if midpoint > 0 else 0
            second_half_avg = sum(latencies[midpoint:]) / (total_count - midpoint) if total_count > midpoint else 0

            if second_half_avg > first_half_avg * 1.1:
                trend = "degrading"
            elif second_half_avg < first_half_avg * 0.9:
                trend = "improving"
            else:
                trend = "stable"

            return {
                "avg_latency_ms": round(avg_latency, 2),
                "min_latency_ms": round(min_latency, 2),
                "max_latency_ms": round(max_latency, 2),
                "p50_latency_ms": round(p50_latency, 2),
                "p95_latency_ms": round(p95_latency, 2),
                "p99_latency_ms": round(p99_latency, 2),
                "trend": trend,
                "sample_size": total_count
            }

        finally:
            if close_session:
                session.close()

    def get_l1_vs_l2_breakdown(
        self,
        days: int = 30,
        *,
        session: Session | None = None
    ) -> dict[str, Any]:
        """
        Get L1 vs L2 detection breakdown.

        Args:
            days: Number of days to look back
            session: Optional database session

        Returns:
            Dictionary with L1/L2 statistics
        """
        close_session = session is None
        if session is None:
            session = self._get_session()

        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            # Get all events
            total_scans = session.query(func.count(TelemetryEvent.id)).filter(
                TelemetryEvent.timestamp >= cutoff
            ).scalar() or 0

            if total_scans == 0:
                return {
                    "total_scans": 0,
                    "l1_only": 0,
                    "l2_used": 0,
                    "l2_usage_rate": 0.0,
                    "avg_l1_ms": 0.0,
                    "avg_l2_ms": 0.0
                }

            # Count L2 usage (where l2_inference_ms is not null and > 0)
            l2_scans = session.query(func.count(TelemetryEvent.id)).filter(
                and_(
                    TelemetryEvent.timestamp >= cutoff,
                    TelemetryEvent.l2_inference_ms.isnot(None),
                    TelemetryEvent.l2_inference_ms > 0
                )
            ).scalar() or 0

            l1_only = total_scans - l2_scans

            # Average latencies
            avg_l1 = session.query(func.avg(TelemetryEvent.l1_inference_ms)).filter(
                TelemetryEvent.timestamp >= cutoff
            ).scalar() or 0.0

            avg_l2 = session.query(func.avg(TelemetryEvent.l2_inference_ms)).filter(
                and_(
                    TelemetryEvent.timestamp >= cutoff,
                    TelemetryEvent.l2_inference_ms.isnot(None),
                    TelemetryEvent.l2_inference_ms > 0
                )
            ).scalar() or 0.0

            return {
                "total_scans": total_scans,
                "l1_only": l1_only,
                "l2_used": l2_scans,
                "l2_usage_rate": round((l2_scans / total_scans * 100) if total_scans > 0 else 0.0, 2),
                "avg_l1_ms": round(avg_l1, 2),
                "avg_l2_ms": round(avg_l2, 2)
            }

        finally:
            if close_session:
                session.close()

    def close(self) -> None:
        """Close database connection."""
        self.engine.dispose()
        logger.info("Data aggregator closed")
