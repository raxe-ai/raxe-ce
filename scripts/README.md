# Development Scripts

Utility scripts for development and maintenance.

## Available Scripts

### `seed_data.py`
Generate test data for development and testing

```bash
python scripts/seed_data.py
```

Generates:
- Sample prompts (70% clean, 30% malicious)
- Detection events
- Test rules
- Performance test datasets

### `benchmark.py`
Run performance benchmarks

```bash
python scripts/benchmark.py
```

Validates:
- P95 scan latency <10ms
- Throughput >1000 scans/sec
- Memory usage <100MB for 10K events

## Future Scripts

- `migrate.py` - Database migration runner
- `update_rules.py` - Download latest community rules
- `analyze_coverage.py` - Detailed coverage analysis
- `profile.py` - Performance profiling tools
