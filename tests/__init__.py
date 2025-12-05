"""
RAXE CE Test Suite

Coverage Requirements:
    - Overall: >80% (enforced in CI)
    - Domain layer: >95% (pure functions, no excuse)
    - Critical paths: 100% (auth, billing, data flow)

Test Organization:
    unit/           - Fast, isolated tests (>90% of tests)
        domain/     - Domain layer tests (pure, no mocks)
        application/- Use case tests (with mocks)
        infrastructure/ - Infrastructure tests (real SQLite)

    integration/    - Slow, integrated tests (full workflows)
    performance/    - Benchmark tests (not in CI by default)
    golden/         - Golden file regression tests

Run tests:
    pytest                          # All tests
    pytest tests/unit               # Fast tests only
    pytest --cov=raxe --cov-report=html  # With coverage
    pytest tests/performance --benchmark-only  # Benchmarks
"""
