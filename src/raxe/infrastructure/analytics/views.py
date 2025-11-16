"""
Database views for analytics queries.

Provides SQL views for efficient analytics aggregations.
"""

from sqlalchemy import text
from sqlalchemy.engine import Engine

# SQL view definitions
DAILY_STATS_VIEW = """
CREATE VIEW IF NOT EXISTS daily_stats AS
SELECT
    DATE(timestamp) as date,
    COUNT(*) as total_scans,
    SUM(CASE WHEN detection_count > 0 THEN 1 ELSE 0 END) as total_threats,
    AVG(total_latency_ms) as avg_duration_ms,
    MAX(total_latency_ms) as max_duration_ms,
    COUNT(DISTINCT customer_id) as unique_users,
    CAST(SUM(CASE WHEN detection_count > 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as detection_rate
FROM telemetry_events
GROUP BY DATE(timestamp)
ORDER BY date DESC
"""

DETECTION_BREAKDOWN_VIEW = """
CREATE VIEW IF NOT EXISTS detection_breakdown AS
SELECT
    highest_severity as severity,
    COUNT(*) as count,
    CAST(COUNT(*) AS FLOAT) / (SELECT COUNT(*) FROM telemetry_events WHERE detection_count > 0) * 100 as percentage
FROM telemetry_events
WHERE detection_count > 0
GROUP BY highest_severity
ORDER BY count DESC
"""

HOURLY_PATTERNS_VIEW = """
CREATE VIEW IF NOT EXISTS hourly_patterns AS
SELECT
    CAST(strftime('%H', timestamp) AS INTEGER) as hour,
    COUNT(*) as scan_count,
    SUM(CASE WHEN detection_count > 0 THEN 1 ELSE 0 END) as threat_count,
    AVG(total_latency_ms) as avg_duration_ms
FROM telemetry_events
GROUP BY strftime('%H', timestamp)
ORDER BY hour
"""

PERFORMANCE_TRENDS_VIEW = """
CREATE VIEW IF NOT EXISTS performance_trends AS
SELECT
    DATE(timestamp) as date,
    AVG(total_latency_ms) as avg_latency_ms,
    AVG(l1_inference_ms) as avg_l1_ms,
    AVG(l2_inference_ms) as avg_l2_ms,
    MIN(total_latency_ms) as min_latency_ms,
    MAX(total_latency_ms) as max_latency_ms,
    COUNT(*) as sample_count
FROM telemetry_events
GROUP BY DATE(timestamp)
ORDER BY date DESC
"""

L1_L2_BREAKDOWN_VIEW = """
CREATE VIEW IF NOT EXISTS l1_l2_breakdown AS
SELECT
    DATE(timestamp) as date,
    COUNT(*) as total_scans,
    SUM(CASE WHEN l2_inference_ms IS NULL OR l2_inference_ms = 0 THEN 1 ELSE 0 END) as l1_only,
    SUM(CASE WHEN l2_inference_ms IS NOT NULL AND l2_inference_ms > 0 THEN 1 ELSE 0 END) as l2_used,
    AVG(l1_inference_ms) as avg_l1_ms,
    AVG(CASE WHEN l2_inference_ms > 0 THEN l2_inference_ms END) as avg_l2_ms
FROM telemetry_events
GROUP BY DATE(timestamp)
ORDER BY date DESC
"""

USER_ACTIVITY_VIEW = """
CREATE VIEW IF NOT EXISTS user_activity AS
SELECT
    customer_id,
    MIN(timestamp) as first_scan,
    MAX(timestamp) as last_scan,
    COUNT(*) as total_scans,
    SUM(CASE WHEN detection_count > 0 THEN 1 ELSE 0 END) as threats_detected,
    AVG(total_latency_ms) as avg_scan_time_ms,
    COUNT(DISTINCT DATE(timestamp)) as active_days
FROM telemetry_events
GROUP BY customer_id
"""

SEVERITY_TRENDS_VIEW = """
CREATE VIEW IF NOT EXISTS severity_trends AS
SELECT
    DATE(timestamp) as date,
    highest_severity as severity,
    COUNT(*) as count
FROM telemetry_events
WHERE detection_count > 0
GROUP BY DATE(timestamp), highest_severity
ORDER BY date DESC, count DESC
"""


def create_analytics_views(engine: Engine) -> None:
    """
    Create all analytics views in the database.

    Args:
        engine: SQLAlchemy engine instance

    Raises:
        Exception: If view creation fails
    """
    views = [
        ("daily_stats", DAILY_STATS_VIEW),
        ("detection_breakdown", DETECTION_BREAKDOWN_VIEW),
        ("hourly_patterns", HOURLY_PATTERNS_VIEW),
        ("performance_trends", PERFORMANCE_TRENDS_VIEW),
        ("l1_l2_breakdown", L1_L2_BREAKDOWN_VIEW),
        ("user_activity", USER_ACTIVITY_VIEW),
        ("severity_trends", SEVERITY_TRENDS_VIEW),
    ]

    with engine.begin() as conn:
        for _view_name, view_sql in views:
            try:
                conn.execute(text(view_sql))
                conn.execute(text("COMMIT"))
            except Exception as e:
                # View might already exist, that's ok
                if "already exists" not in str(e).lower():
                    raise


def drop_analytics_views(engine: Engine) -> None:
    """
    Drop all analytics views from the database.

    Args:
        engine: SQLAlchemy engine instance

    Raises:
        ValueError: If view name is invalid
    """
    # Whitelist of valid view names (security: prevent SQL injection)
    VALID_VIEWS = {
        "daily_stats",
        "detection_breakdown",
        "hourly_patterns",
        "performance_trends",
        "l1_l2_breakdown",
        "user_activity",
        "severity_trends",
    }

    views = [
        "daily_stats",
        "detection_breakdown",
        "hourly_patterns",
        "performance_trends",
        "l1_l2_breakdown",
        "user_activity",
        "severity_trends",
    ]

    with engine.begin() as conn:
        for view_name in views:
            # Validate view name against whitelist (security: SQL injection prevention)
            if view_name not in VALID_VIEWS:
                raise ValueError(f"Invalid view name: {view_name}")
            try:
                conn.execute(text(f"DROP VIEW IF EXISTS {view_name}"))
                conn.execute(text("COMMIT"))
            except Exception:
                # Silently ignore errors
                pass
