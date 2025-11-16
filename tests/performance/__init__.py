"""Performance Tests - Benchmarks & SLO Validation

Performance requirements:
    - P95 scan latency: <10ms
    - Throughput: >1000 scans/sec
    - Memory: <100MB for 10K queued events

Run with: pytest tests/performance --benchmark-only
"""
