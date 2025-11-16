"""
Optimized aggregation query methods for Phase 3B performance optimization.

These methods replace inefficient implementations in aggregator.py that load
all events into memory. Use SQL GROUP BY and aggregation functions instead.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from raxe.infrastructure.database.models import TelemetryEvent

from .aggregator import DataAggregator, DetectionBreakdown


class OptimizedAggregator(DataAggregator):
    """
    Performance-optimized version of DataAggregator.

    All query methods use SQL aggregation instead of loading rows into memory.
    """

    def get_detection_breakdown(
        self,
        days: int = 30,
        *,
        session: Session | None = None
    ) -> list[DetectionBreakdown]:
        """
        Get detection breakdown by severity using SQL aggregation.

        Performance optimization: Single GROUP BY query instead of
        multiple COUNT queries per severity.

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

            # OPTIMIZED: Single GROUP BY query instead of N queries
            severity_stats = session.query(
                TelemetryEvent.highest_severity,
                func.count(TelemetryEvent.id).label('count')
            ).filter(
                and_(
                    TelemetryEvent.timestamp >= cutoff,
                    TelemetryEvent.detection_count > 0,
                    TelemetryEvent.highest_severity.isnot(None)
                )
            ).group_by(
                TelemetryEvent.highest_severity
            ).all()

            if not severity_stats:
                return []

            # Calculate total and percentages
            total_detections = sum(row.count for row in severity_stats)

            breakdowns = []
            for row in severity_stats:
                percentage = (row.count / total_detections * 100) if total_detections > 0 else 0.0
                breakdowns.append(DetectionBreakdown(
                    severity=row.highest_severity,
                    count=row.count,
                    percentage=round(percentage, 2)
                ))

            # Sort by count descending
            breakdowns.sort(key=lambda x: x.count, reverse=True)

            return breakdowns

        finally:
            if close_session:
                session.close()

    def get_daily_scan_counts(
        self,
        start_date: datetime,
        end_date: datetime,
        *,
        session: Session | None = None
    ) -> dict[str, int]:
        """
        Get scan counts per day using database aggregation.

        Performance optimization: Much faster than loading all events.

        Args:
            start_date: Start date
            end_date: End date
            session: Optional database session

        Returns:
            Dictionary mapping date strings to scan counts
        """
        close_session = session is None
        if session is None:
            session = self._get_session()

        try:
            result = session.query(
                func.date(TelemetryEvent.timestamp).label('scan_date'),
                func.count(TelemetryEvent.id).label('scan_count'),
            ).filter(
                and_(
                    TelemetryEvent.timestamp >= start_date,
                    TelemetryEvent.timestamp <= end_date
                )
            ).group_by(
                func.date(TelemetryEvent.timestamp)
            ).all()

            return {str(row.scan_date): row.scan_count for row in result}

        finally:
            if close_session:
                session.close()

    def get_all_active_users_paginated(
        self,
        start_date: datetime,
        end_date: datetime,
        page_size: int = 1000,
        *,
        session: Session | None = None
    ) -> list[list[str]]:
        """
        Get all active users in paginated batches.

        Performance optimization: Yields batches of user IDs to avoid memory issues.

        Args:
            start_date: Start date
            end_date: End date
            page_size: Number of users per batch
            session: Optional database session

        Returns:
            List of user ID batches
        """
        close_session = session is None
        if session is None:
            session = self._get_session()

        try:
            all_batches = []
            offset = 0

            while True:
                batch = session.query(
                    func.distinct(TelemetryEvent.customer_id)
                ).filter(
                    and_(
                        TelemetryEvent.timestamp >= start_date,
                        TelemetryEvent.timestamp <= end_date
                    )
                ).limit(page_size).offset(offset).all()

                if not batch:
                    break

                user_ids = [row[0] for row in batch]
                all_batches.append(user_ids)

                offset += page_size

            return all_batches

        finally:
            if close_session:
                session.close()
