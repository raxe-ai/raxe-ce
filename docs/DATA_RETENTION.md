# Data Retention Policy & Configuration

## Overview

RAXE stores scan history, analytics, and usage data locally in SQLite database. This document explains what data is stored, for how long, and how to configure retention policies.

## What Data is Stored

### Scan History

**Location**: `~/.raxe/raxe.db` (table: `scans`)

**Data Stored**:
- Prompt hash (SHA-256) - **NOT the actual prompt text**
- Timestamp
- Threat detected (boolean)
- Severity level
- Rule IDs matched
- Scan duration
- L1/L2 status

**Example**:
```sql
sqlite3 ~/.raxe/raxe.db "SELECT * FROM scans LIMIT 1;"
```

**Privacy**: Only SHA-256 hashes are stored, never the raw prompt text.

### Analytics & Statistics

**Location**: `~/.raxe/raxe.db` (tables: `analytics`, `achievements`)

**Data Stored**:
- Total scans count
- Threats detected count
- Daily streak
- Achievement unlocks
- Performance metrics (avg scan time)

### Telemetry Queue

**Location**: `~/.raxe/raxe.db` (table: `telemetry_queue`)

**Data Stored** (if telemetry enabled):
- Anonymized scan metadata
- Environment info (Python version, OS)
- Performance metrics
- Pending transmission status

**Privacy**: Prompts are hashed before storage, never raw text.

## Default Retention Periods

**Current Implementation**: ⚠️ **No automatic expiration** (unlimited storage)

**Recommended Retention**:
| Data Type | Recommended Retention | Rationale |
|-----------|----------------------|-----------|
| Scan history | 30 days | Security audit trail |
| Analytics/stats | 90 days | Trend analysis |
| Telemetry queue | 7 days | Retry window |
| Logs (if file logging) | 7 days | Troubleshooting |
| Cache | Session/TTL | Performance |

## Configuring Retention

### Option 1: Manual Cleanup

```bash
# Export scan history before deletion
raxe export --format json --output scans_backup.json

# Delete database to clear all data
rm ~/.raxe/raxe.db

# Reinitialize
raxe init
```

### Option 2: SQL-Based Cleanup

```bash
# Delete scans older than 30 days
sqlite3 ~/.raxe/raxe.db \
  "DELETE FROM scans WHERE timestamp < datetime('now', '-30 days');"

# Delete old telemetry queue entries
sqlite3 ~/.raxe/raxe.db \
  "DELETE FROM telemetry_queue WHERE created_at < datetime('now', '-7 days');"

# Vacuum database to reclaim space
sqlite3 ~/.raxe/raxe.db "VACUUM;"
```

### Option 3: Python Script

Create `~/.raxe/cleanup.py`:

```python
#!/usr/bin/env python3
"""Cleanup old RAXE data based on retention policy."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
RETENTION_DAYS = {
    "scans": 30,
    "telemetry_queue": 7,
    "analytics": 90,
}

db_path = Path.home() / ".raxe" / "raxe.db"

def cleanup_old_data():
    """Remove data older than retention period."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for table, days in RETENTION_DAYS.items():
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            cursor.execute(
                f"DELETE FROM {table} WHERE timestamp < ?",
                (cutoff_date,)
            )
            deleted = cursor.rowcount
            print(f"Deleted {deleted} rows from {table} (older than {days} days)")
        except sqlite3.Error as e:
            print(f"Error cleaning {table}: {e}")

    # Vacuum to reclaim space
    cursor.execute("VACUUM")
    conn.commit()
    conn.close()
    print("Cleanup complete!")

if __name__ == "__main__":
    cleanup_old_data()
```

Run with cron:

```bash
# Add to crontab (daily at 2 AM)
crontab -e

# Add this line:
0 2 * * * python3 ~/.raxe/cleanup.py >> ~/.raxe/cleanup.log 2>&1
```

### Option 4: Configuration File (Future)

**Planned Feature** (not yet implemented):

```yaml
# ~/.raxe/config.yaml
database:
  retention:
    scans: 30  # days
    analytics: 90
    telemetry_queue: 7
    auto_vacuum: true
```

## Database Size Management

### Check Current Size

```bash
# Database file size
du -h ~/.raxe/raxe.db

# Row counts by table
sqlite3 ~/.raxe/raxe.db <<EOF
SELECT 'scans' as table_name, COUNT(*) as row_count FROM scans
UNION ALL
SELECT 'analytics', COUNT(*) FROM analytics
UNION ALL
SELECT 'telemetry_queue', COUNT(*) FROM telemetry_queue;
EOF
```

### Expected Growth

**Typical Sizes**:
- Empty database: ~50 KB
- 1,000 scans: ~200 KB
- 10,000 scans: ~2 MB
- 100,000 scans: ~20 MB

**Growth Rate**:
- ~200 bytes per scan record
- ~100 bytes per analytics entry

### Storage Limits

```bash
# Set filesystem quota (if supported)
# Example: limit ~/.raxe directory to 100MB
setquota -u $USER 100M 100M 0 0 /home

# Monitor disk usage
df -h ~/.raxe/
```

## Privacy & Compliance

### GDPR Right to Deletion

Delete all personal data:

```bash
# Export data first (optional)
raxe export --format json --output my_data.json

# Delete all local data
rm -rf ~/.raxe/

# Reinitialize (fresh start)
raxe init --no-telemetry
```

### Data Portability

Export all scan history:

```bash
# Export as JSON
raxe export --format json --output scans.json

# Export as CSV
raxe export --format csv --output scans.csv

# Direct SQL export
sqlite3 ~/.raxe/raxe.db ".dump" > backup.sql
```

### Disable Data Collection

```yaml
# ~/.raxe/config.yaml
telemetry:
  enabled: false  # Disable cloud telemetry

analytics:
  enabled: false  # Disable local analytics

database:
  enabled: false  # Disable scan history (future)
```

Or via environment variable:

```bash
export RAXE_TELEMETRY_ENABLED=false
raxe scan "test"
```

## Backup & Restore

### Backup Database

```bash
# Simple copy
cp ~/.raxe/raxe.db ~/.raxe/raxe.db.backup

# SQL dump
sqlite3 ~/.raxe/raxe.db ".backup ~/.raxe/backup.db"

# With timestamp
cp ~/.raxe/raxe.db ~/.raxe/raxe.db.$(date +%Y%m%d_%H%M%S)
```

### Restore Database

```bash
# From backup
cp ~/.raxe/raxe.db.backup ~/.raxe/raxe.db

# From SQL dump
sqlite3 ~/.raxe/raxe.db < backup.sql
```

### Automated Backups

```bash
#!/bin/bash
# ~/.raxe/backup.sh

BACKUP_DIR="$HOME/.raxe/backups"
mkdir -p "$BACKUP_DIR"

# Keep last 7 days
find "$BACKUP_DIR" -name "raxe.db.*" -mtime +7 -delete

# Create new backup
cp "$HOME/.raxe/raxe.db" "$BACKUP_DIR/raxe.db.$(date +%Y%m%d)"
```

## Audit Trail

### Query Scan History

```sql
-- Recent threats
SELECT
    datetime(timestamp, 'unixepoch') as scan_time,
    severity,
    rules_matched
FROM scans
WHERE has_threat = 1
ORDER BY timestamp DESC
LIMIT 10;

-- Scan volume by day
SELECT
    date(timestamp, 'unixepoch') as scan_date,
    COUNT(*) as scan_count,
    SUM(has_threat) as threat_count
FROM scans
GROUP BY scan_date
ORDER BY scan_date DESC
LIMIT 30;

-- Most triggered rules
SELECT
    rule_id,
    COUNT(*) as trigger_count
FROM (
    SELECT json_each.value as rule_id
    FROM scans, json_each(rules_matched)
    WHERE has_threat = 1
)
GROUP BY rule_id
ORDER BY trigger_count DESC
LIMIT 10;
```

### Export Audit Report

```bash
# Generate monthly report
sqlite3 ~/.raxe/raxe.db <<EOF > audit_report_$(date +%Y%m).txt
.mode column
.headers on

SELECT
    strftime('%Y-%m', timestamp, 'unixepoch') as month,
    COUNT(*) as total_scans,
    SUM(has_threat) as threats_detected,
    ROUND(AVG(scan_duration_ms), 2) as avg_duration_ms
FROM scans
WHERE timestamp >= strftime('%s', 'now', 'start of month', '-1 month')
GROUP BY month;
EOF
```

## Database Encryption

**Current Status**: ❌ **Not Implemented**

**Recommendation**: For sensitive environments, use SQLCipher:

```bash
# Install SQLCipher
pip install sqlcipher3

# Encrypt existing database
sqlcipher ~/.raxe/raxe.db
> PRAGMA key = 'your-encryption-key';
> ATTACH DATABASE 'encrypted.db' AS encrypted KEY 'your-encryption-key';
> SELECT sqlcipher_export('encrypted');
> DETACH DATABASE encrypted;
```

**Future**: Native encryption support planned for v1.5+

## Troubleshooting

### Database Corruption

```bash
# Check integrity
sqlite3 ~/.raxe/raxe.db "PRAGMA integrity_check;"

# Recover from corruption
sqlite3 ~/.raxe/raxe.db ".recover" | sqlite3 recovered.db

# Replace corrupted database
mv ~/.raxe/raxe.db ~/.raxe/raxe.db.corrupted
mv recovered.db ~/.raxe/raxe.db
```

### Disk Space Issues

```bash
# Check database size
du -h ~/.raxe/raxe.db

# Vacuum to reclaim space
sqlite3 ~/.raxe/raxe.db "VACUUM;"

# Delete old records
sqlite3 ~/.raxe/raxe.db \
  "DELETE FROM scans WHERE timestamp < datetime('now', '-7 days');"
```

## Best Practices

1. **Regular Cleanup**: Run cleanup script weekly or monthly
2. **Export Before Deletion**: Always export data before mass deletion
3. **Monitor Size**: Check database size regularly
4. **Backup Important Data**: Backup before major operations
5. **Test Retention**: Verify retention policy with test data
6. **Document Policy**: Share retention policy with team
7. **Compliance**: Ensure retention meets regulatory requirements

## Compliance Checklist

- [ ] Documented retention periods
- [ ] Automated cleanup process
- [ ] Data export capability
- [ ] Right to deletion honored
- [ ] Minimal data collection
- [ ] Encrypted storage (optional, recommended)
- [ ] Audit trail maintained
- [ ] Regular backups

## See Also

- [Privacy Guide](privacy.md)
- [Security Policy](SECURITY.md)
- [Threat Model - Data Retention](THREAT_MODELING.md#data-retention)
- [GDPR Compliance](SECURITY.md#compliance)
