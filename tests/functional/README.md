# RAXE Functional Test Suite

## Overview
Comprehensive functional tests for RAXE Community Edition release validation.
These tests validate the complete system functionality including recent optimizations.

## Test Organization

```
tests/functional/
├── README.md                      # This file
├── run_all_tests.py              # Main test runner with performance tracking
├── conftest.py                   # Shared test fixtures and utilities
├── test_data/                    # Test data fixtures
│   ├── safe_prompts.json         # Known safe prompts
│   ├── threat_prompts.json       # Known threat prompts
│   └── edge_cases.json          # Edge case test data
├── cli/                          # CLI functional tests
│   ├── test_basic_scanning.py   # Core scan functionality
│   ├── test_progress_indicators.py # TTY/non-TTY progress
│   ├── test_output_formats.py   # JSON/text/verbose output
│   ├── test_error_handling.py   # Invalid inputs, exit codes
│   └── test_configuration.py    # CLI config options
├── sdk/                          # SDK functional tests
│   ├── test_initialization.py   # Init stats, timing
│   ├── test_multiple_scans.py   # No re-init verification
│   ├── test_thread_safety.py    # Concurrent operations
│   ├── test_memory_management.py # Memory leak detection
│   └── test_telemetry.py        # Telemetry validation
├── decorator/                    # Decorator functional tests
│   ├── test_protection.py       # Threat blocking
│   ├── test_transparency.py     # No function impact
│   ├── test_error_resilience.py # Graceful degradation
│   └── test_concurrency.py      # Thread-safe decoration
├── l2_detection/                 # L2 model tests
│   ├── test_model_loading.py    # ONNX/bundle/stub fallback
│   ├── test_eager_loading.py    # No timeout verification
│   ├── test_detection_accuracy.py # Threat detection quality
│   └── test_performance.py      # <150ms inference
├── integration/                  # Cross-component tests
│   ├── test_user_journeys.py    # End-to-end scenarios
│   ├── test_backward_compat.py  # LazyL2Detector support
│   └── test_failure_recovery.py # Resilience testing
└── performance/                  # Performance benchmarks
    ├── test_initialization_time.py # <500ms init
    ├── test_scan_latency.py      # <10ms p95
    └── test_memory_usage.py      # Memory profiling
```

## Test Execution

```bash
# Run all functional tests
pytest tests/functional/ -v

# Run with performance tracking
python tests/functional/run_all_tests.py

# Run specific suite
pytest tests/functional/cli/ -v

# Run with coverage
pytest tests/functional/ --cov=raxe --cov-report=html

# Run in parallel (faster)
pytest tests/functional/ -n auto
```

## Performance Benchmarks

| Component | Target | Threshold |
|-----------|--------|-----------|
| Init Time | <500ms | FAIL >1s |
| Scan P95 | <10ms | FAIL >20ms |
| L2 Inference | <150ms | FAIL >300ms |
| Memory/scan | <1MB | FAIL >5MB |
| CLI overhead | <50ms | FAIL >100ms |

## Release Validation Checklist

### Pre-Release Tests
- [ ] All functional tests pass (100%)
- [ ] Performance benchmarks met
- [ ] No memory leaks detected
- [ ] Thread safety validated
- [ ] Backward compatibility confirmed

### Test Coverage Requirements
- [ ] Overall: >80%
- [ ] Domain layer: >95%
- [ ] Critical paths: 100%
- [ ] Error paths: >90%

### Critical User Journeys
1. First-time developer experience
2. CI/CD pipeline integration
3. Production API protection
4. Security team threat hunting

## Test Data Specifications

### Safe Prompts (test_data/safe_prompts.json)
- Normal user queries
- Technical questions
- Code generation requests
- Documentation queries

### Threat Prompts (test_data/threat_prompts.json)
- Jailbreak attempts
- Prompt injection
- Data exfiltration
- System manipulation

### Edge Cases (test_data/edge_cases.json)
- Empty/null inputs
- Unicode/emoji
- Very long prompts (>10KB)
- Malformed JSON
- Special characters