"""Dashboard data provider - fetches and caches data from scan history."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from raxe.infrastructure.database.scan_history import ScanHistoryDB, ScanRecord


@dataclass
class AlertItem:
    """Single alert item for display in the dashboard.

    Attributes:
        scan_id: Database scan ID
        timestamp: When the scan occurred
        severity: Highest severity level
        rule_ids: List of rule IDs that triggered
        detection_count: Total number of detections
        prompt_preview: First N characters of prompt (for context)
        prompt_hash: SHA256 hash of prompt
        event_id: Portal event ID (if available)
        l1_detections: Number of L1 detections
        l2_detections: Number of L2 detections
        confidence: Highest confidence score
        descriptions: Human-readable detection descriptions
    """

    scan_id: int
    timestamp: datetime
    severity: str
    rule_ids: list[str]
    detection_count: int
    prompt_preview: str
    prompt_hash: str
    event_id: str | None = None
    l1_detections: int = 0
    l2_detections: int = 0
    confidence: float = 0.0
    descriptions: list[str] = field(default_factory=list)
    prompt_text: str | None = None  # Full prompt (for detail view)


@dataclass
class DashboardData:
    """Aggregated data for dashboard rendering.

    This is the main data structure passed to views and widgets.
    """

    # Summary statistics (today)
    total_scans_today: int = 0
    total_threats_today: int = 0
    threats_by_severity: dict[str, int] = field(
        default_factory=lambda: {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "INFO": 0,
        }
    )

    # Recent alerts (for alert feed)
    recent_alerts: list[AlertItem] = field(default_factory=list)

    # Trends (for sparklines) - last 24 hours, hourly buckets
    hourly_scans: list[int] = field(default_factory=lambda: [0] * 24)
    hourly_threats: list[int] = field(default_factory=lambda: [0] * 24)

    # Performance metrics
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    l1_avg_ms: float = 0.0
    l2_avg_ms: float = 0.0

    # System status
    rules_loaded: int = 0
    ml_model_loaded: bool = True
    last_scan_time: datetime | None = None

    # Metadata
    data_range_days: int = 30
    last_refresh: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DashboardDataProvider:
    """Provides data for the dashboard with caching.

    Queries the scan history database and aggregates data for
    dashboard display. Implements caching to minimize database
    queries during rapid refresh cycles.
    """

    MAX_ALERTS_CACHED = 100
    MAX_SCANS_QUERIED = 500
    PREVIEW_LENGTH = 50

    def __init__(
        self,
        db: ScanHistoryDB | None = None,
        history_days: int = 30,
        cache_ttl_seconds: float = 1.0,
    ):
        """Initialize the data provider.

        Args:
            db: ScanHistoryDB instance (creates new one if None)
            history_days: Number of days of history to consider
            cache_ttl_seconds: Cache time-to-live in seconds
        """
        if db is None:
            from raxe.infrastructure.database.scan_history import ScanHistoryDB

            db = ScanHistoryDB()

        self.db = db
        self.history_days = history_days
        self.cache_ttl_seconds = cache_ttl_seconds

        self._cache: DashboardData | None = None
        self._cache_time: datetime | None = None
        self._last_seen_scan_id: int | None = None

    def get_data(self, force_refresh: bool = False) -> DashboardData:
        """Get dashboard data, using cache if fresh.

        Args:
            force_refresh: If True, bypass cache

        Returns:
            DashboardData with current statistics
        """
        now = datetime.now(timezone.utc)

        # Check cache validity
        cache_valid = (
            not force_refresh
            and self._cache is not None
            and self._cache_time is not None
            and (now - self._cache_time).total_seconds() < self.cache_ttl_seconds
        )

        if cache_valid:
            return self._cache  # type: ignore

        # Fetch fresh data
        self._cache = self._fetch_data()
        self._cache_time = now

        return self._cache

    def force_refresh(self) -> DashboardData:
        """Force a cache refresh.

        Returns:
            Fresh DashboardData
        """
        return self.get_data(force_refresh=True)

    def get_alert_details(self, scan_id: int) -> AlertItem | None:
        """Get full details for a specific alert.

        Args:
            scan_id: Database scan ID

        Returns:
            AlertItem with full details including prompt text
        """
        scan = self.db.get_scan(scan_id)
        if scan is None:
            return None

        detections = self.db.get_detections(scan_id)

        return AlertItem(
            scan_id=scan.id or 0,
            timestamp=scan.timestamp,
            severity=scan.highest_severity or "UNKNOWN",
            rule_ids=[d.rule_id for d in detections],
            detection_count=scan.threats_found,
            prompt_preview=self._safe_preview(scan.prompt_text),
            prompt_hash=scan.prompt_hash,
            event_id=scan.event_id,
            l1_detections=scan.l1_detections,
            l2_detections=scan.l2_detections,
            confidence=max((d.confidence for d in detections), default=0.0),
            descriptions=[d.description or "" for d in detections if d.description],
            prompt_text=scan.prompt_text,
        )

    def _fetch_data(self) -> DashboardData:
        """Fetch fresh data from the database.

        Returns:
            New DashboardData instance
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Get recent scans
        scans = self.db.list_scans(limit=self.MAX_SCANS_QUERIED)

        # Calculate today's stats
        today_scans = [s for s in scans if s.timestamp >= today_start]
        total_scans_today = len(today_scans)
        total_threats_today = sum(s.threats_found for s in today_scans)

        # Threats by severity
        threats_by_severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        for scan in today_scans:
            if scan.highest_severity:
                sev = scan.highest_severity.upper()
                if sev in threats_by_severity:
                    threats_by_severity[sev] += 1

        # Build recent alerts (threats only)
        recent_alerts: list[AlertItem] = []
        for scan in scans:
            if scan.threats_found > 0 and len(recent_alerts) < self.MAX_ALERTS_CACHED:
                detections = self.db.get_detections(scan.id or 0)
                recent_alerts.append(
                    AlertItem(
                        scan_id=scan.id or 0,
                        timestamp=scan.timestamp,
                        severity=scan.highest_severity or "UNKNOWN",
                        rule_ids=[d.rule_id for d in detections],
                        detection_count=scan.threats_found,
                        prompt_preview=self._safe_preview(scan.prompt_text),
                        prompt_hash=scan.prompt_hash,
                        event_id=scan.event_id,
                        l1_detections=scan.l1_detections,
                        l2_detections=scan.l2_detections,
                        confidence=max((d.confidence for d in detections), default=0.0),
                        descriptions=[d.description or "" for d in detections if d.description],
                    )
                )

        # Calculate hourly trends (last 24 hours)
        hourly_scans, hourly_threats = self._calculate_hourly_trends(scans, now)

        # Get performance stats
        stats = self.db.get_statistics(days=1)

        # Calculate P95 approximation (1.5x average is rough estimate)
        avg_total = stats.get("avg_total_duration_ms") or 0.0
        p95_approx = avg_total * 1.5 if avg_total > 0 else 0.0

        # Last scan time
        last_scan_time = scans[0].timestamp if scans else None

        # Update tracking
        if scans:
            self._last_seen_scan_id = scans[0].id

        return DashboardData(
            total_scans_today=total_scans_today,
            total_threats_today=total_threats_today,
            threats_by_severity=threats_by_severity,
            recent_alerts=recent_alerts,
            hourly_scans=hourly_scans,
            hourly_threats=hourly_threats,
            avg_latency_ms=avg_total,
            p95_latency_ms=p95_approx,
            l1_avg_ms=stats.get("avg_l1_duration_ms") or 0.0,
            l2_avg_ms=stats.get("avg_l2_duration_ms") or 0.0,
            rules_loaded=0,  # Will be set by orchestrator
            ml_model_loaded=True,
            last_scan_time=last_scan_time,
            data_range_days=self.history_days,
            last_refresh=datetime.now(timezone.utc),
        )

    def _calculate_hourly_trends(
        self, scans: list[ScanRecord], now: datetime
    ) -> tuple[list[int], list[int]]:
        """Calculate hourly scan and threat counts for last 24 hours.

        Args:
            scans: List of ScanRecord objects
            now: Current timestamp

        Returns:
            Tuple of (hourly_scans, hourly_threats) lists
        """
        hourly_scans = [0] * 24
        hourly_threats = [0] * 24

        cutoff = now - timedelta(hours=24)

        for scan in scans:
            if scan.timestamp < cutoff:
                continue

            # Calculate hours ago (0 = current hour, 23 = 23 hours ago)
            hours_ago = int((now - scan.timestamp).total_seconds() / 3600)
            if 0 <= hours_ago < 24:
                # Index 23 = oldest, index 0 = newest
                bucket = 23 - hours_ago
                hourly_scans[bucket] += 1
                if scan.threats_found > 0:
                    hourly_threats[bucket] += 1

        return hourly_scans, hourly_threats

    def _safe_preview(self, prompt_text: str | None, max_len: int | None = None) -> str:
        """Generate safe preview of prompt text.

        Args:
            prompt_text: Full prompt text (may be None)
            max_len: Maximum preview length (default: PREVIEW_LENGTH)

        Returns:
            Truncated preview string
        """
        if max_len is None:
            max_len = self.PREVIEW_LENGTH

        if not prompt_text:
            return "[No preview]"

        # Clean up whitespace
        preview = " ".join(prompt_text.split())

        if len(preview) > max_len:
            return preview[: max_len - 3] + "..."

        return preview

    def has_new_alerts(self) -> bool:
        """Check if there are new alerts since last refresh.

        Returns:
            True if new alerts exist
        """
        if self._last_seen_scan_id is None:
            return False

        scans = self.db.list_scans(limit=5)
        for scan in scans:
            if scan.id and scan.id > self._last_seen_scan_id and scan.threats_found > 0:
                return True

        return False
