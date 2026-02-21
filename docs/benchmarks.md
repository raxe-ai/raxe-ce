# RAXE Performance Benchmarks

## Overview

RAXE uses a two-layer detection architecture:

- **L1 (Rule-Based)**: 515+ compiled regex rules. No external dependencies. Sub-millisecond to low-single-digit millisecond latency.
- **L2 (ML-Based)**: Gemma-based ONNX classifier for semantic threat detection. Included with `pip install raxe`.

All benchmarks measure **scan latency only** (excludes one-time initialization).

## Methodology

- **Timing**: `time.perf_counter()` (monotonic, nanosecond resolution)
- **Iterations**: 100 timed iterations per test (configurable via `--iterations`)
- **Warmup**: 5 iterations discarded before measurement (configurable via `--warmup`)
- **Percentiles**: P50 (median), P95, P99 computed from sorted latency array
- **Dry run**: Benchmarks use `dry_run=True` to exclude telemetry and history overhead
- **Memory**: RSS via `resource.getrusage()` (peak resident set size)

## Running Benchmarks

```bash
# Full benchmark suite (L1 + L2 if available)
python scripts/run_benchmarks.py

# L1 only (skips ML model loading)
python scripts/run_benchmarks.py --l1-only

# More iterations for stable results
python scripts/run_benchmarks.py --iterations 500

# JSON output only
python scripts/run_benchmarks.py --output json

# Save JSON to file
python scripts/run_benchmarks.py --json-file results.json

# All options
python scripts/run_benchmarks.py --iterations 500 --warmup 10 --output both --json-file results.json
```

## Input Sizes Tested

| Label | Characters | Description |
|-------|-----------|-------------|
| `tiny_10` | ~10 | Single short sentence |
| `short_100` | ~100 | Typical user prompt |
| `medium_500` | ~500 | Detailed question |
| `long_1000` | ~1000 | Multi-paragraph prompt |
| `xlarge_5000` | ~5000 | Very long input |
| `threat` | ~62 | Known prompt injection |

## Sample Results

Results below are from a single run and will vary by hardware.
Run `python scripts/run_benchmarks.py` to get numbers for your environment.

### L1 Rule-Based Detection

| Input Size | P50 (ms) | P95 (ms) | P99 (ms) |
|-----------|----------|----------|----------|
| tiny_10   | _run benchmark_ | _run benchmark_ | _run benchmark_ |
| short_100 | _run benchmark_ | _run benchmark_ | _run benchmark_ |
| medium_500| _run benchmark_ | _run benchmark_ | _run benchmark_ |
| long_1000 | _run benchmark_ | _run benchmark_ | _run benchmark_ |
| xlarge_5000| _run benchmark_ | _run benchmark_ | _run benchmark_ |
| threat    | _run benchmark_ | _run benchmark_ | _run benchmark_ |

### L1 + L2 Combined Detection

| Input Size | P50 (ms) | P95 (ms) | P99 (ms) |
|-----------|----------|----------|----------|
| tiny_10   | _run benchmark_ | _run benchmark_ | _run benchmark_ |
| short_100 | _run benchmark_ | _run benchmark_ | _run benchmark_ |
| medium_500| _run benchmark_ | _run benchmark_ | _run benchmark_ |
| long_1000 | _run benchmark_ | _run benchmark_ | _run benchmark_ |
| xlarge_5000| _run benchmark_ | _run benchmark_ | _run benchmark_ |
| threat    | _run benchmark_ | _run benchmark_ | _run benchmark_ |

### Memory Footprint

| Measurement | RSS (MB) |
|-------------|----------|
| Before init (Python baseline) | _run benchmark_ |
| After L1-only init | _run benchmark_ |
| After L1+L2 init | _run benchmark_ |

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| L1 P95 | < 5 ms | Rules-only, typical input |
| L1+L2 P95 | < 10 ms | Combined, with stub L2 |
| L1+L2 P95 (full ML) | < 50 ms | With ONNX model loaded |
| Init time | < 500 ms | One-time startup cost |
| Throughput | > 1000 scans/sec | L1-only sustained |

## CI Integration

The `benchmark.yml` GitHub Actions workflow runs benchmarks on every push
and PR. Results are tracked at the
[performance dashboard](https://raxe-ai.github.io/raxe-ce/dev/bench).

Performance regressions > 20% trigger a PR comment alert.

## Interpreting Results

- **P50** (median): Typical latency most users experience.
- **P95**: Latency at the 95th percentile. Use this for SLA targets.
- **P99**: Tail latency. High P99 relative to P95 indicates occasional spikes.
- **Stdev**: Standard deviation. Low stdev means consistent performance.

Factors that affect results:
- CPU speed and architecture (Apple Silicon vs x86)
- System load during benchmark
- Python version (3.11+ has faster regex)
- Number of rules loaded (more rules = higher L1 latency)
- L2 model type (stub vs ONNX vs sentence-transformers)
