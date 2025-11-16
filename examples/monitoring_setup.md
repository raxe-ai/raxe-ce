# RAXE Monitoring Setup Guide

## Overview

This guide shows how to set up comprehensive monitoring for RAXE CE using Prometheus and Grafana. Monitor performance, detect anomalies, and optimize your RAXE deployment.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Prometheus Setup](#prometheus-setup)
3. [Grafana Dashboards](#grafana-dashboards)
4. [Alert Rules](#alert-rules)
5. [Example Queries](#example-queries)

---

## Quick Start

### Start RAXE Metrics Server

```bash
# Start metrics server on port 9090
raxe metrics-server --port 9090

# Metrics available at:
# http://localhost:9090/metrics
```

### Test Metrics Endpoint

```bash
# View raw metrics
curl http://localhost:9090/metrics

# Example output:
# raxe_scans_total{action="allowed",severity="none"} 42.0
# raxe_scan_duration_seconds_bucket{layer="regex",le="0.005"} 38.0
# raxe_detections_total{category="PI",rule_id="pi-001",severity="critical"} 5.0
```

---

## Prometheus Setup

### 1. Install Prometheus

#### macOS (Homebrew)
```bash
brew install prometheus
```

#### Ubuntu/Debian
```bash
sudo apt-get install prometheus
```

#### Docker
```bash
docker pull prom/prometheus
```

### 2. Configure Prometheus

Create `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  # RAXE metrics
  - job_name: 'raxe'
    static_configs:
      - targets: ['localhost:9090']
        labels:
          app: 'raxe-ce'
          environment: 'production'

  # Optional: System metrics
  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']
```

### 3. Start Prometheus

```bash
# Local
prometheus --config.file=prometheus.yml

# Docker
docker run -d \
  -p 9091:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus

# Access UI at http://localhost:9091
```

### 4. Verify Scraping

```bash
# Check targets
curl http://localhost:9091/api/v1/targets

# Should show raxe target as UP
```

---

## Grafana Dashboards

### 1. Install Grafana

#### macOS (Homebrew)
```bash
brew install grafana
brew services start grafana
```

#### Ubuntu/Debian
```bash
sudo apt-get install grafana
sudo systemctl start grafana-server
```

#### Docker
```bash
docker run -d \
  -p 3000:3000 \
  --name=grafana \
  grafana/grafana
```

Access at: http://localhost:3000 (default login: admin/admin)

### 2. Add Prometheus Data Source

1. Go to Configuration → Data Sources
2. Click "Add data source"
3. Select "Prometheus"
4. Set URL to `http://localhost:9091`
5. Click "Save & Test"

### 3. Import RAXE Dashboard

#### Option A: Import Dashboard JSON

Save this as `raxe_dashboard.json`:

```json
{
  "dashboard": {
    "title": "RAXE CE Performance",
    "tags": ["raxe", "security", "llm"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Scan Throughput",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(raxe_scans_total[1m])",
            "legendFormat": "{{severity}} - {{action}}"
          }
        ],
        "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8}
      },
      {
        "id": 2,
        "title": "P95 Scan Latency",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(raxe_scan_duration_seconds_bucket[5m]))",
            "legendFormat": "{{layer}}"
          }
        ],
        "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8}
      },
      {
        "id": 3,
        "title": "Detection Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(raxe_detections_total[1m])",
            "legendFormat": "{{severity}} - {{category}}"
          }
        ],
        "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8}
      },
      {
        "id": 4,
        "title": "Queue Depth",
        "type": "graph",
        "targets": [
          {
            "expr": "raxe_queue_depth",
            "legendFormat": "{{priority}}"
          }
        ],
        "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8}
      }
    ]
  }
}
```

Import:
1. Dashboards → Import
2. Upload JSON file or paste JSON
3. Select Prometheus data source
4. Click "Import"

#### Option B: Create Dashboard Manually

**Panel 1: Scan Throughput**
- Query: `rate(raxe_scans_total[1m])`
- Visualization: Time series
- Legend: `{{severity}} - {{action}}`

**Panel 2: P95 Latency**
- Query: `histogram_quantile(0.95, rate(raxe_scan_duration_seconds_bucket[5m]))`
- Visualization: Time series
- Unit: seconds (s)

**Panel 3: Detection Rate**
- Query: `rate(raxe_detections_total[1m])`
- Visualization: Time series
- Legend: `{{severity}} - {{category}}`

**Panel 4: Queue Depth**
- Query: `raxe_queue_depth`
- Visualization: Time series
- Legend: `{{priority}}`

---

## Alert Rules

### 1. Create Alert Rules

Create `alerts.yml`:

```yaml
groups:
  - name: raxe_alerts
    interval: 30s
    rules:
      # High latency alert
      - alert: RaxeHighLatency
        expr: histogram_quantile(0.95, rate(raxe_scan_duration_seconds_bucket[5m])) > 0.025
        for: 5m
        labels:
          severity: warning
          component: raxe
        annotations:
          summary: "RAXE P95 latency is high"
          description: "P95 scan latency is {{ $value }}s (threshold: 25ms)"

      # Very high latency alert
      - alert: RaxeCriticalLatency
        expr: histogram_quantile(0.95, rate(raxe_scan_duration_seconds_bucket[5m])) > 0.050
        for: 2m
        labels:
          severity: critical
          component: raxe
        annotations:
          summary: "RAXE P95 latency is critical"
          description: "P95 scan latency is {{ $value }}s (threshold: 50ms)"

      # High error rate
      - alert: RaxeHighErrorRate
        expr: rate(raxe_errors_total[5m]) > 0.01
        for: 2m
        labels:
          severity: warning
          component: raxe
        annotations:
          summary: "RAXE error rate is high"
          description: "Error rate is {{ $value }} errors/sec"

      # Queue backing up
      - alert: RaxeQueueBackup
        expr: raxe_queue_depth{priority="high"} > 1000
        for: 5m
        labels:
          severity: warning
          component: raxe
        annotations:
          summary: "RAXE telemetry queue is backing up"
          description: "Queue depth is {{ $value }} items"

      # Many detections (possible attack)
      - alert: RaxeHighDetectionRate
        expr: rate(raxe_detections_total{severity="critical"}[5m]) > 1
        for: 1m
        labels:
          severity: warning
          component: raxe
        annotations:
          summary: "High rate of CRITICAL detections"
          description: "Detecting {{ $value }} critical threats/sec (possible attack)"

      # Low throughput (possible degradation)
      - alert: RaxeLowThroughput
        expr: rate(raxe_scans_total[5m]) < 0.1
        for: 10m
        labels:
          severity: info
          component: raxe
        annotations:
          summary: "RAXE throughput is low"
          description: "Only {{ $value }} scans/sec (possible degradation)"
```

### 2. Configure Alertmanager

Create `alertmanager.yml`:

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'component']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'

  routes:
    - match:
        severity: critical
      receiver: 'critical'
      continue: true

receivers:
  - name: 'default'
    slack_configs:
      - api_url: 'YOUR_SLACK_WEBHOOK'
        channel: '#alerts'
        title: 'RAXE Alert'

  - name: 'critical'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_KEY'
    slack_configs:
      - api_url: 'YOUR_SLACK_WEBHOOK'
        channel: '#critical-alerts'
        title: 'RAXE CRITICAL Alert'
```

### 3. Start Alertmanager

```bash
# Update prometheus.yml to include alerts
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']

rule_files:
  - "alerts.yml"

# Restart Prometheus
prometheus --config.file=prometheus.yml

# Start Alertmanager
alertmanager --config.file=alertmanager.yml
```

---

## Example Queries

### Performance Queries

#### Scan Latency by Percentile
```promql
# P50 (median)
histogram_quantile(0.50, rate(raxe_scan_duration_seconds_bucket[5m]))

# P95
histogram_quantile(0.95, rate(raxe_scan_duration_seconds_bucket[5m]))

# P99
histogram_quantile(0.99, rate(raxe_scan_duration_seconds_bucket[5m]))
```

#### Throughput
```promql
# Overall scan rate
rate(raxe_scans_total[1m])

# By severity
sum by(severity) (rate(raxe_scans_total[1m]))

# By action (blocked vs allowed)
sum by(action) (rate(raxe_scans_total[1m]))
```

#### Component Breakdown
```promql
# L1 (regex) average duration
rate(raxe_scan_duration_seconds_sum{layer="regex"}[5m]) /
rate(raxe_scan_duration_seconds_count{layer="regex"}[5m])

# L2 (ML) average duration
rate(raxe_scan_duration_seconds_sum{layer="ml"}[5m]) /
rate(raxe_scan_duration_seconds_count{layer="ml"}[5m])
```

### Detection Queries

#### Detection Rate by Severity
```promql
sum by(severity) (rate(raxe_detections_total[5m]))
```

#### Most Triggered Rules
```promql
topk(10, rate(raxe_rule_matches_total[1h]))
```

#### Detection Rate by Category
```promql
sum by(category) (rate(raxe_detections_total[5m]))
```

#### False Positive Rate
```promql
rate(raxe_false_positives_total[1h])
```

### Queue Queries

#### Queue Depth Over Time
```promql
raxe_queue_depth
```

#### Queue Processing Rate
```promql
rate(raxe_queue_items_processed_total[5m])
```

#### Queue Processing Success Rate
```promql
rate(raxe_queue_items_processed_total{status="success"}[5m]) /
rate(raxe_queue_items_processed_total[5m])
```

### Error Queries

#### Error Rate
```promql
rate(raxe_errors_total[5m])
```

#### Errors by Type
```promql
sum by(error_type) (rate(raxe_errors_total[5m]))
```

---

## Production Monitoring Checklist

- [ ] Prometheus scraping RAXE metrics
- [ ] Grafana dashboard configured
- [ ] Alert rules defined
- [ ] Alertmanager configured
- [ ] Notifications tested
- [ ] Runbook created for alerts
- [ ] Metrics retention configured
- [ ] Backup of Prometheus data
- [ ] Access control configured
- [ ] SSL/TLS for endpoints

---

## Docker Compose Setup

Complete stack with Prometheus + Grafana + RAXE:

```yaml
# docker-compose.yml
version: '3.8'

services:
  # RAXE application
  raxe:
    build: .
    ports:
      - "8000:8000"  # Application
      - "9090:9090"  # Metrics
    command: |
      sh -c "
        raxe metrics-server --port 9090 &
        python -m raxe.server
      "

  # Prometheus
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9091:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./alerts.yml:/etc/prometheus/alerts.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  # Grafana
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false

  # Alertmanager
  alertmanager:
    image: prom/alertmanager:latest
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml

volumes:
  prometheus_data:
  grafana_data:
```

Start the stack:
```bash
docker-compose up -d
```

---

## Additional Resources

- [Performance Tuning Guide](../docs/performance/tuning_guide.md)
- [Benchmarking Guide](../docs/performance/benchmarking.md)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)

**Last Updated**: 2025-11-15
**Version**: 1.0.0
