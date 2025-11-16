# Analytics Quickstart Guide

Quick reference for using RAXE CE analytics and gamification features.

## CLI Commands

### View Your Statistics

```bash
# Show your personal stats
raxe stats

# Output as JSON
raxe stats --format json

# Export to file
raxe stats --export my_stats.json
```

### Global Platform Statistics

```bash
# View community-wide stats
raxe stats --global

# Export global stats
raxe stats --global --format json > global.json
```

### Retention Analysis

```bash
# See your cohort's retention rates
raxe stats --retention
```

## Python SDK Usage

### Get User Statistics

```python
from raxe.infrastructure.analytics.engine import AnalyticsEngine

# Initialize engine
engine = AnalyticsEngine()

# Get your stats
stats = engine.get_user_stats("your_installation_id")

print(f"Total scans: {stats.total_scans}")
print(f"Threats detected: {stats.threats_detected}")
print(f"Current streak: {stats.current_streak} days")
print(f"Average scan time: {stats.avg_scan_time_ms}ms")

# Cleanup
engine.close()
```

### Track Achievements

```python
from raxe.infrastructure.analytics.streaks import StreakTracker

# Initialize tracker
tracker = StreakTracker()

# Record a scan (updates streaks)
newly_unlocked = tracker.record_scan()

# Check for milestone achievements
newly_unlocked.extend(tracker.check_achievements(
    total_scans=100,
    threats_detected=10,
    avg_scan_time_ms=4.5,
    threats_blocked=5
))

# Notify user of new achievements
for achievement in newly_unlocked:
    print(f"🎉 {achievement.icon} {achievement.name}!")
    print(f"   {achievement.description}")
    print(f"   +{achievement.points} points")

# View progress
progress = tracker.get_progress_summary()
print(f"Unlocked: {progress['unlocked']}/{progress['total_achievements']}")
print(f"Total points: {progress['total_points']}")
```

### Calculate Retention

```python
from datetime import date, timedelta
from raxe.infrastructure.analytics.engine import AnalyticsEngine

engine = AnalyticsEngine()

# Calculate retention for cohort from 30 days ago
cohort_date = date.today() - timedelta(days=30)
retention = engine.calculate_retention(cohort_date)

print(f"Cohort size: {retention['cohort_size']}")
print(f"Day 1 retention: {retention['day_1']}%")
print(f"Day 7 retention: {retention['day_7']}%")
print(f"Day 30 retention: {retention['day_30']}%")

engine.close()
```

### Aggregate Data

```python
from datetime import date, timedelta
from raxe.infrastructure.analytics.aggregator import DataAggregator

agg = DataAggregator()

# Get daily rollup for last 7 days
start_date = date.today() - timedelta(days=6)
end_date = date.today()
rollups = agg.get_daily_rollup(start_date, end_date)

for rollup in rollups:
    print(f"{rollup.date}: {rollup.total_scans} scans, "
          f"{rollup.total_threats} threats ({rollup.detection_rate:.1f}%)")

# Get hourly patterns
patterns = agg.get_hourly_patterns(days=30)
for pattern in patterns:
    if pattern.scan_count > 0:
        print(f"Hour {pattern.hour:02d}: {pattern.scan_count} scans")

# Get detection breakdown
breakdown = agg.get_detection_breakdown(days=30)
for item in breakdown:
    print(f"{item.severity}: {item.count} ({item.percentage:.1f}%)")

agg.close()
```

### Generate Reports

```python
from datetime import date, timedelta
from raxe.infrastructure.analytics.engine import AnalyticsEngine

engine = AnalyticsEngine()

# Generate monthly report
start = date.today() - timedelta(days=30)
end = date.today()
report = engine.generate_report(start, end)

print(f"Report for {report['period']['start_date']} to {report['period']['end_date']}")
print(f"Total scans: {report['overview']['total_scans']}")
print(f"Unique users: {report['overview']['unique_users']}")
print(f"Threats detected: {report['overview']['threats_detected']}")
print(f"Detection rate: {report['overview']['detection_rate']}%")
print(f"Avg latency: {report['performance']['avg_total_latency_ms']:.2f}ms")

engine.close()
```

## Achievements Reference

### Scan-Based Achievements

| Achievement | Requirement | Points |
|-------------|-------------|--------|
| 🔍 First Scan | Complete 1 scan | 10 |
| 💯 Century Scanner | Complete 100 scans | 100 |
| 🌟 Scan Master | Complete 1,000 scans | 500 |

### Streak Achievements

| Achievement | Requirement | Points |
|-------------|-------------|--------|
| 🔥 Week Warrior | 7-day streak | 50 |
| ⚡ Monthly Master | 30-day streak | 200 |

### Threat Detection Achievements

| Achievement | Requirement | Points |
|-------------|-------------|--------|
| 🛡️ Threat Hunter | Detect 1 threat | 25 |
| 🎯 Security Guardian | Detect 10 threats | 75 |
| 👑 Elite Defender | Detect 100 threats | 300 |
| 🛡️ Guardian | Block 10 threats | 100 |

### Performance Achievements

| Achievement | Requirement | Points |
|-------------|-------------|--------|
| ⚡ Speed Demon | Avg scan time < 5ms (min 10 scans) | 150 |

## Database Views

### Query Daily Stats

```python
from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///~/.raxe/telemetry.db")

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT * FROM daily_stats
        WHERE date >= date('now', '-7 days')
        ORDER BY date DESC
    """))

    for row in result:
        print(f"{row.date}: {row.total_scans} scans, {row.detection_rate:.1f}% detection")
```

### Query Hourly Patterns

```python
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT * FROM hourly_patterns
        ORDER BY scan_count DESC
        LIMIT 5
    """))

    print("Top 5 busiest hours:")
    for row in result:
        print(f"Hour {row.hour:02d}: {row.scan_count} scans")
```

### Query Detection Breakdown

```python
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT * FROM detection_breakdown
        ORDER BY count DESC
    """))

    for row in result:
        print(f"{row.severity}: {row.count} ({row.percentage:.1f}%)")
```

## Environment Variables

```bash
# Disable achievements tracking
export RAXE_ACHIEVEMENTS_ENABLED=false

# Custom achievements file location
export RAXE_ACHIEVEMENTS_FILE=~/.config/raxe/achievements.json

# Custom analytics database
export RAXE_ANALYTICS_DB=~/.config/raxe/analytics.db
```

## Common Patterns

### Daily Achievement Check

```python
from raxe.infrastructure.analytics.engine import AnalyticsEngine
from raxe.infrastructure.analytics.streaks import StreakTracker

def check_daily_achievements(installation_id: str):
    """Check and unlock achievements after each scan."""
    engine = AnalyticsEngine()
    tracker = StreakTracker()

    # Get current stats
    stats = engine.get_user_stats(installation_id)

    # Record scan (updates streaks)
    newly_unlocked = tracker.record_scan()

    # Check for milestone achievements
    newly_unlocked.extend(tracker.check_achievements(
        total_scans=stats.total_scans,
        threats_detected=stats.threats_detected,
        avg_scan_time_ms=stats.avg_scan_time_ms
    ))

    # Notify user
    for achievement in newly_unlocked:
        print(f"🎉 Achievement unlocked: {achievement.icon} {achievement.name}")

    engine.close()
    return newly_unlocked
```

### Weekly Report

```python
from datetime import date, timedelta
from raxe.infrastructure.analytics.engine import AnalyticsEngine
from raxe.infrastructure.analytics.aggregator import DataAggregator

def generate_weekly_report(installation_id: str):
    """Generate weekly activity report."""
    engine = AnalyticsEngine()
    agg = DataAggregator()

    # Get date range
    end_date = date.today()
    start_date = end_date - timedelta(days=6)

    # Get user stats
    stats = engine.get_user_stats(installation_id)

    # Get daily breakdown
    rollups = agg.get_daily_rollup(start_date, end_date)
    total_week_scans = sum(r.total_scans for r in rollups)
    total_week_threats = sum(r.total_threats for r in rollups)

    print(f"📊 Weekly Report ({start_date} to {end_date})")
    print(f"\nTotal scans this week: {total_week_scans}")
    print(f"Threats detected: {total_week_threats}")
    print(f"Current streak: {stats.current_streak} days")
    print(f"Average scan time: {stats.avg_scan_time_ms:.1f}ms")

    print("\nDaily breakdown:")
    for rollup in rollups:
        if rollup.total_scans > 0:
            print(f"  {rollup.date}: {rollup.total_scans} scans, "
                  f"{rollup.total_threats} threats")

    engine.close()
    agg.close()
```

## Troubleshooting

### Reset Achievements

```python
from pathlib import Path

# Remove achievements file to reset
achievements_file = Path.home() / ".raxe" / "achievements.json"
if achievements_file.exists():
    achievements_file.unlink()
    print("Achievements reset")
```

### Rebuild Analytics Views

```python
from raxe.infrastructure.analytics.views import create_analytics_views
from sqlalchemy import create_engine

engine = create_engine("sqlite:///~/.raxe/telemetry.db")
create_analytics_views(engine)
print("Analytics views recreated")
```

### Check Database Size

```python
from pathlib import Path

db_path = Path.home() / ".raxe" / "telemetry.db"
size_mb = db_path.stat().st_size / (1024 * 1024)
print(f"Database size: {size_mb:.2f} MB")
```

## Best Practices

1. **Close engines/aggregators** when done to free resources:
   ```python
   engine = AnalyticsEngine()
   try:
       stats = engine.get_user_stats(id)
   finally:
       engine.close()
   ```

2. **Use context managers** for database operations:
   ```python
   with engine.connect() as conn:
       result = conn.execute(query)
   ```

3. **Cache analytics results** for frequently accessed data:
   ```python
   from functools import lru_cache

   @lru_cache(maxsize=128)
   def get_cached_stats(installation_id: str):
       engine = AnalyticsEngine()
       stats = engine.get_user_stats(installation_id)
       engine.close()
       return stats
   ```

4. **Batch achievement checks** instead of checking after every scan:
   ```python
   # Check achievements once per day instead of per scan
   if should_check_daily_achievements():
       check_daily_achievements(installation_id)
   ```

## Support

For issues or questions:
- GitHub Issues: https://github.com/raxe-ai/raxe-ce/issues
- Documentation: https://docs.raxe.ai
- Community: https://community.raxe.ai
