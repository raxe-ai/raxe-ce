# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.2] - 2025-11-16

### Added
- **12 new security rules** for improved threat detection:
  - `jb-104@1.0.0`: Role-playing based jailbreak detection
  - `jb-105@1.0.0`: STAN/DAN/AIM named persona jailbreak detection
  - `pi-3027@1.0.0`: Instruction override synonym detection (forget, erase, discard)
  - `cmd-023@1.0.0`: Data exfiltration commands (curl/wget piped to bash)
  - `cmd-025@1.0.0`: Credential harvesting attempts
  - `cmd-026@1.0.0`: Template injection (SSTI) detection
  - `cmd-027@1.0.0`: Deserialization attack patterns
  - `pi-022@1.0.0`: Obfuscated prompt injection (l33t speak, homoglyphs)
  - `pi-023@1.0.0`: DAN/STAN/AIM jailbreak personas
  - `pi-024@1.0.0`: Base64/hex encoded injection attempts
  - `pi-025@1.0.0`: Multilingual prompt injection
  - `pi-027@1.0.0`: Polite/indirect instruction overrides
- **180+ comprehensive tests** covering edge cases, evasion techniques, and performance
  - `tests/integration/test_edge_cases.py` (40 tests)
  - `tests/integration/test_evasion_techniques.py` (50 tests)
  - `tests/integration/test_false_positives.py` (60 tests)
  - `tests/performance/test_detection_performance.py` (20 tests)
- **428 golden file test cases** for regression prevention across all 116 rules
- **Organized test data structure** with clear separation:
  - `tests/fixtures/` for curated test data (1,000 benign + 412 threats)
  - `tests/fixtures/README.md` documentation
- **Automated test utilities**:
  - `scripts/generate_comprehensive_golden_files.py` for golden file generation
  - `scripts/add_test_markers.py` for pytest marker management

### Changed
- **Improved detection rate** from 94.42% to 95.15% (+0.73%)
  - ENC family: 82.98% → 87.23% (+4.25%)
  - JB family: 89.09% → 90.91% (+1.82%)
- Enhanced `enc-044@1.0.0` pattern to catch uppercase hex encoding (e.g., `0xFF`)
- Enhanced `enc-069@1.0.0` to support both `powershell` and `pwsh` commands
- Total rules increased from 104 to **116 rules** across 7 families
  - CMD: 20 → 24 rules (+4)
  - PI: 21 → 26 rules (+5)
- Test suite expanded from ~1,200 to **1,383 tests** (+15% coverage)

### Fixed
- Bug in `tests/integration/test_detection_coverage.py` family coverage tests
- KeyError when accessing malicious sample fields (standardized to `"text"` key)
- **AsyncIO EOFError warnings** in telemetry logs (fixed `run_async_send` to use `asyncio.run()`)
- HTTP/2 dependency issue (disabled HTTP/2 in async telemetry sender)
- CLI version test expecting old version number (updated to 0.0.2)

### Performance
- **P50 latency**: 0.37ms (13x better than <5ms target)
- **P95 latency**: 0.49ms (20x better than <10ms target)
- **P99 latency**: 1.34ms (15x better than <20ms target)
- **Throughput**: ~1,200 scans/second (20% above >1,000 target)
- **Memory**: ~60MB peak (40% below <100MB target)
- **False positive rate**: 0.00% maintained

### Documentation
- Comprehensive QA reports in `CLAUDE_WORKING_FILES/REPORTS/`:
  - `qa_test_report.md` - Detailed test analysis
  - `qa_test_summary.md` - Executive summary
  - `qa_checklist.md` - Deployment checklist
  - `security_analysis_report.md` - Gap analysis and rule improvements
  - `test_data_organization_report.md` - Data structure documentation
  - `final_summary_qa_security.md` - Complete v0.0.2 summary

## [0.1.0] - TBD

Initial alpha release (in development)

### Planned Features
- CLI with `init`, `scan`, `config` commands
- Python SDK for integration
- L1 detection (rules-based)
- L2 detection (ML-based)
- Local SQLite queue
- Cloud telemetry (optional)
- OpenAI/Anthropic wrappers

---

## Version History

- **0.1.0** - Initial alpha (in development)

[Unreleased]: https://github.com/raxe-ai/raxe-ce/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/raxe-ai/raxe-ce/releases/tag/v0.1.0
