# RAXE-CE Comprehensive Code Review - TODO

> **Generated:** 2025-12-20
> **Version:** 0.2.0
> **Review Type:** Multi-agent comprehensive analysis

## Summary

| Category | Critical | High | Medium | Low | Total |
|----------|----------|------|--------|-----|-------|
| Security | 0 | 2 | 4 | 3 | 9 |
| Performance | 0 | 1 | 6 | 15 | 22 |
| Architecture | 0 | 2 | 3 | 2 | 7 |
| Dead Code | 0 | 0 | 8 | 8 | 16 |
| Maintainability | 0 | 3 | 6 | 3 | 12 |
| ML/Detection | 0 | 1 | 5 | 6 | 12 |
| Platform/Scalability | 0 | 1 | 3 | 4 | 8 |
| Testing | 1 | 2 | 4 | 3 | 10 |
| **TOTAL** | **1** | **12** | **39** | **44** | **96** |

---

## Priority Legend

- **P0 (Critical):** Production blockers, security vulnerabilities, data loss risks
- **P1 (High):** Should fix before next release, significant impact
- **P2 (Medium):** Important improvements, schedule in next sprint
- **P3 (Low):** Nice to have, tech debt cleanup

---

## CRITICAL (P0)

### [T-001] Hash Length Test Failure - Test Bug
- **Category:** Testing
- **Location:** `tests/unit/infrastructure/test_telemetry_privacy.py:475`
- **Priority:** P0 | **Impact:** HIGH | **Effort:** LOW | **Complexity:** LOW
- **Description:** `test_no_pii_fields_in_complete_scan_event` expects hash length 64 but receives 71 (includes `sha256:` prefix)
- **Action:** Fix assertion to expect 71 chars or strip prefix before comparison
- **Owner:** TBD

---

## HIGH PRIORITY (P1)

### [S-001] Regex Timeout Not Enforced - ReDoS Risk
- **Category:** Security / Performance
- **Location:** `src/raxe/domain/engine/matcher.py:113-172`
- **Priority:** P1 | **Impact:** HIGH | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** `timeout_seconds` parameter is accepted but not enforced. Pathological regex patterns could cause ReDoS attacks.
- **Action:** Implement timeout using `regex` module or pre-validate all patterns against ReDoS
- **Owner:** TBD

### [S-002] Tarfile Extraction Without Path Validation
- **Category:** Security
- **Location:** `src/raxe/infrastructure/ml/model_downloader.py`
- **Priority:** P1 | **Impact:** HIGH | **Effort:** LOW | **Complexity:** LOW
- **Description:** `tarfile.extractall()` used without checking for path traversal attacks (CVE-2007-4559 pattern)
- **Action:** Add path validation to reject entries with `..` or absolute paths
- **Owner:** TBD

### [M-001] God Class - SDK Client 1579 Lines
- **Category:** Maintainability
- **Location:** `src/raxe/sdk/client.py` (1579 lines)
- **Priority:** P1 | **Impact:** HIGH | **Effort:** HIGH | **Complexity:** HIGH
- **Description:** `Raxe` class handles 40+ methods for scanning, config, suppression, telemetry, tracking, history, decorators, wrappers, and stats
- **Action:** Extract into separate service classes (ScanService, ConfigService, etc.) with Raxe as facade
- **Owner:** TBD

### [M-002] Excessive Function Length - scan() 418 Lines
- **Category:** Maintainability
- **Location:** `src/raxe/application/scan_pipeline.py:275-693`
- **Priority:** P1 | **Impact:** HIGH | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Single method with multiple responsibilities violating SRP
- **Action:** Extract private methods: `_execute_l1()`, `_execute_l2()`, `_apply_policy()`, `_apply_suppressions()`, `_record_telemetry()`
- **Owner:** TBD

### [M-003] Bare Exception Handler
- **Category:** Maintainability
- **Location:** `src/raxe/infrastructure/telemetry/sender.py:431`
- **Priority:** P1 | **Impact:** HIGH | **Effort:** LOW | **Complexity:** LOW
- **Description:** Bare `except:` catches SystemExit and KeyboardInterrupt, masking critical errors
- **Action:** Replace with specific exception types
- **Owner:** TBD

### [ML-001] Pattern Timeout Not Enforced
- **Category:** ML/Detection
- **Location:** `src/raxe/domain/engine/matcher.py:119-142`
- **Priority:** P1 | **Impact:** HIGH | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Same as S-001 - P95 latency target not guaranteed due to missing timeout
- **Action:** Use `regex` package with native timeout support
- **Owner:** TBD

### [PS-001] Unbounded Embedding Cache
- **Category:** Platform/Scalability
- **Location:** `src/raxe/domain/ml/embedding_cache.py`
- **Priority:** P1 | **Impact:** HIGH | **Effort:** LOW | **Complexity:** LOW
- **Description:** LRU cache has 1000 item limit but no memory limit. Large embeddings could cause OOM
- **Action:** Add memory-based eviction or reduce cache size
- **Owner:** TBD

### [T-002] Missing Integration Tests for Suppression System
- **Category:** Testing
- **Location:** `tests/integration/`
- **Priority:** P1 | **Impact:** HIGH | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** New suppression feature lacks comprehensive integration tests
- **Action:** Add integration tests for YAML config + SDK + CLI suppression flows
- **Owner:** TBD

### [T-003] Missing Edge Case Tests for Voting Engine
- **Category:** Testing
- **Location:** `tests/unit/domain/ml/voting/`
- **Priority:** P1 | **Impact:** HIGH | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Voting engine edge cases not tested (all abstain, tie-breakers, infinity ratios)
- **Action:** Add comprehensive edge case tests for voting logic
- **Owner:** TBD

### [A-001] Domain Layer Contains Logger Usage
- **Category:** Architecture
- **Location:** `src/raxe/domain/` (multiple files)
- **Priority:** P1 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Domain layer imports `raxe.utils.logging` which violates Clean Architecture (domain should be pure)
- **Action:** Remove logging from domain or inject logger as dependency
- **Owner:** TBD

### [A-002] Circular Import Risk in Suppression Factory
- **Category:** Architecture
- **Location:** `src/raxe/domain/suppression_factory.py`
- **Priority:** P1 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** Factory imports infrastructure layer (YAML repository) from domain layer
- **Action:** Move factory to application layer or use dependency injection
- **Owner:** TBD

---

## MEDIUM PRIORITY (P2)

### [S-003] API Key Logged at DEBUG Level
- **Category:** Security
- **Location:** `src/raxe/infrastructure/telemetry/credential_store.py`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** API key presence logged at debug level, could appear in debug logs
- **Action:** Remove or mask API key in logs
- **Owner:** TBD

### [S-004] YAML Load Without Schema Validation
- **Category:** Security
- **Location:** `src/raxe/infrastructure/rules/yaml_loader.py`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** `yaml.safe_load()` used but no schema validation after loading. Malformed rules could cause unexpected behavior
- **Action:** Add JSON Schema validation for rule YAML files
- **Owner:** TBD

### [P-001] Rule Pattern Cache Not Shared
- **Category:** Performance
- **Location:** `src/raxe/domain/engine/matcher.py:61-111`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** LOW
- **Description:** Pattern cache per-instance, not shared across scans. Same patterns compiled multiple times
- **Action:** Pre-compile patterns at registry load time
- **Owner:** TBD

### [P-002] L2 Model Cold Start Latency
- **Category:** Performance
- **Location:** `src/raxe/domain/ml/gemma_detector.py:73-215`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** First scan takes ~500ms due to model loading
- **Action:** Add warm_up() method for eager loading during startup
- **Owner:** TBD

### [P-003] Suppression Check Per Detection
- **Category:** Performance
- **Location:** `src/raxe/application/scan_pipeline.py:516-558`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Each detection checked against suppression manager individually
- **Action:** Batch load suppressions at scan start, check against in-memory set
- **Owner:** TBD

### [P-004] Pack Registry Deduplication on Every Scan
- **Category:** Performance
- **Location:** `src/raxe/infrastructure/packs/registry.py:222-259`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** `get_all_rules()` deduplicates 460 rules on every call
- **Action:** Cache deduplicated rule list, invalidate on pack reload
- **Owner:** TBD

### [P-005] Telemetry Orchestrator Lazy Init Per Scan
- **Category:** Performance
- **Location:** `src/raxe/application/scan_pipeline.py:331-339`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** `get_orchestrator()` and `ensure_installation()` called on every scan
- **Action:** Move initialization to pipeline `__init__()`
- **Owner:** TBD

### [P-006] All 5 Classifier Heads Run Always
- **Category:** Performance
- **Location:** `src/raxe/domain/ml/gemma_detector.py:425-534`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** HIGH
- **Description:** Voting engine runs all 5 heads even when early detection is sufficient
- **Action:** Implement conditional execution - skip low-priority heads on CRITICAL L1
- **Owner:** TBD

### [ML-002] REVIEW Decision Treated as Threat
- **Category:** ML/Detection
- **Location:** `src/raxe/domain/ml/gemma_detector.py:497`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** `is_threat = decision in (THREAT, REVIEW)` inflates threat counts for uncertain cases
- **Action:** Separate `is_threat` from `needs_review` - only THREAT should be true
- **Owner:** TBD

### [ML-003] Abstain Votes Not Contributing to Decision
- **Category:** ML/Detection
- **Location:** `src/raxe/domain/ml/voting/engine.py:196-202`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Abstaining heads reduce effective voter count, skewing ratio calculation
- **Action:** Consider partial credit for abstains or adjust min_threat_votes
- **Owner:** TBD

### [ML-004] Silent Rule Execution Failures
- **Category:** ML/Detection
- **Location:** `src/raxe/domain/engine/executor.py:327-331`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** Failed rules silently skipped with no visibility into which rules failed
- **Action:** Track failed rule IDs in ScanResult metadata
- **Owner:** TBD

### [ML-005] Severity Veto Override Too High
- **Category:** ML/Detection
- **Location:** `src/raxe/domain/ml/voting/engine.py:286-302`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** Need 3 of 4 non-severity heads to override severity=none, potentially missing valid threats
- **Action:** Consider reducing threshold to 2 for balanced preset
- **Owner:** TBD

### [D-001] Duplicate hash_text Functions
- **Category:** Dead Code
- **Location:** `src/raxe/domain/telemetry/event_creator.py:14`, `src/raxe/infrastructure/telemetry/hook.py:336`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** Identical function in two places, hook.py version never called
- **Action:** Remove hook.py:336 version, use event_creator.py
- **Owner:** TBD

### [D-002] OptimizedAggregator Never Used
- **Category:** Dead Code
- **Location:** `src/raxe/infrastructure/analytics/aggregator_optimized.py`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** Complete implementation exists but class never imported or instantiated
- **Action:** Either integrate or remove
- **Owner:** TBD

### [D-003] Empty Cloud Module
- **Category:** Dead Code
- **Location:** `src/raxe/infrastructure/cloud/`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** Directory with only empty `__init__.py`, no actual cloud code
- **Action:** Remove entire directory
- **Owner:** TBD

### [D-004] Unused validate_event_privacy Function
- **Category:** Dead Code
- **Location:** `src/raxe/domain/telemetry/event_creator.py:239`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** Exported in `__all__` but never called, superseded by ScanTelemetryBuilder
- **Action:** Remove function or document as public API
- **Owner:** TBD

### [D-005] Deprecated Analytics Engine Methods
- **Category:** Dead Code
- **Location:** `src/raxe/infrastructure/analytics/engine.py:138,342`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** Methods marked DEPRECATED but still present
- **Action:** Remove deprecated methods, use service layer
- **Owner:** TBD

### [D-006] Legacy create_scan_event Wrapper
- **Category:** Dead Code
- **Location:** `src/raxe/domain/telemetry/__init__.py:26`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** Legacy wrapper for backwards compatibility, only v2 used internally
- **Action:** Add deprecation warning, plan removal for v1.0
- **Owner:** TBD

### [D-007] Incomplete test CLI Command
- **Category:** Dead Code
- **Location:** `src/raxe/cli/test.py`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Stub command with "(Full cloud connectivity test coming soon)"
- **Action:** Complete implementation or remove
- **Owner:** TBD

### [D-008] Legacy Ensemble Logic Method
- **Category:** Dead Code
- **Location:** `src/raxe/domain/ml/gemma_detector.py:536`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** `_legacy_ensemble_logic` appears replaced by voting engine
- **Action:** Verify not used as fallback, then remove
- **Owner:** TBD

### [M-004] Duplicate Suppression Logic
- **Category:** Maintainability
- **Location:** `src/raxe/sdk/client.py:546-684`, `src/raxe/application/scan_pipeline.py:512-558`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Inline suppression logic duplicated in SDK and pipeline
- **Action:** Create `SuppressionProcessor` utility class
- **Owner:** TBD

### [M-005] Magic Numbers in Confidence Calculation
- **Category:** Maintainability
- **Location:** `src/raxe/domain/engine/executor.py:365-387`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** Unexplained constants: 3.0, 20.0, 0.4, 0.4, 0.2, 0.7, 0.3
- **Action:** Extract to named constants with documentation
- **Owner:** TBD

### [M-006] Inconsistent Error Handling Patterns
- **Category:** Maintainability
- **Location:** Multiple files
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Some use specific exceptions, others broad except, some silent
- **Action:** Define standard error handling pattern, use RaxeException hierarchy
- **Owner:** TBD

### [M-007] Timeout Parameter Not Implemented
- **Category:** Maintainability
- **Location:** `src/raxe/domain/engine/matcher.py:113-173`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** HIGH
- **Description:** Parameter accepted but ignored, API contract misleading
- **Action:** Implement or remove parameter with documentation
- **Owner:** TBD

### [M-008] ScanPipelineResult __bool__ Counterintuitive
- **Category:** Maintainability
- **Location:** `src/raxe/application/scan_pipeline.py:52-182`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** Result with threats is falsy, confusing semantics
- **Action:** Remove `__bool__`, use explicit `if not result.has_threats:`
- **Owner:** TBD

### [PS-002] Thread Safety in Telemetry Queue
- **Category:** Platform/Scalability
- **Location:** `src/raxe/infrastructure/telemetry/dual_queue.py`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Queue operations not fully thread-safe under high concurrency
- **Action:** Add proper locking for batch operations
- **Owner:** TBD

### [PS-003] Global Singleton Pattern Issues
- **Category:** Platform/Scalability
- **Location:** `src/raxe/application/telemetry_orchestrator.py`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Global `_orchestrator` instance breaks multi-process scenarios
- **Action:** Use contextvars or explicit dependency injection
- **Owner:** TBD

### [PS-004] Async/Sync Mixing in SDK
- **Category:** Platform/Scalability
- **Location:** `src/raxe/sdk/client.py`, `src/raxe/async_sdk/`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** HIGH | **Complexity:** HIGH
- **Description:** Separate sync and async clients with duplicated logic
- **Action:** Create common core, generate sync wrapper from async
- **Owner:** TBD

### [T-004] Flaky Tests Due to Timing
- **Category:** Testing
- **Location:** `tests/integration/`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Some integration tests have timing dependencies that cause intermittent failures
- **Action:** Add proper waits/retries or mock timing
- **Owner:** TBD

### [T-005] Missing Performance Benchmark Tests
- **Category:** Testing
- **Location:** `tests/performance/`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** P95 latency targets not validated in CI
- **Action:** Add benchmark tests with performance assertions
- **Owner:** TBD

### [T-006] Golden Tests Need Update Process
- **Category:** Testing
- **Location:** `tests/golden/`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** No documented process for updating golden files when rules change
- **Action:** Add script and documentation for golden file updates
- **Owner:** TBD

### [T-007] Missing Security Test Coverage
- **Category:** Testing
- **Location:** `tests/security/` (does not exist)
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** No dedicated security tests for input validation, injection prevention
- **Action:** Add security-focused test suite
- **Owner:** TBD

### [A-003] Layer Boundary Violations
- **Category:** Architecture
- **Location:** Multiple domain files
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Some domain files import from infrastructure (violates Clean Architecture)
- **Action:** Refactor to use dependency injection or move code to correct layer
- **Owner:** TBD

### [A-004] Missing Interface Definitions
- **Category:** Architecture
- **Location:** `src/raxe/domain/`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Some infrastructure dependencies in domain lack Protocol/ABC definitions
- **Action:** Add abstract interfaces for infrastructure dependencies
- **Owner:** TBD

### [C-001] Telemetry Enabled by Default Without Consent
- **Category:** Configuration
- **Location:** `src/raxe/infrastructure/telemetry/config.py`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** Telemetry is opt-out, not opt-in. Privacy-conscious users may be surprised
- **Action:** Add first-run consent prompt or make opt-in
- **Owner:** TBD

### [C-002] Environment Variables Not Documented
- **Category:** Configuration
- **Location:** `src/raxe/infrastructure/config/`
- **Priority:** P2 | **Impact:** MEDIUM | **Effort:** LOW | **Complexity:** LOW
- **Description:** RAXE_* env vars used but not documented comprehensively
- **Action:** Add env var reference documentation
- **Owner:** TBD

---

## LOW PRIORITY (P3)

### [P-007] EmbeddingCache Uses SHA256 for Keys
- **Category:** Performance
- **Location:** `src/raxe/domain/ml/embedding_cache.py:122-135`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** ~0.1ms overhead per lookup for SHA256 hash
- **Action:** Use Python `hash()` or xxhash for cache keys
- **Owner:** TBD

### [P-008] Severity Calculation Recalculated
- **Category:** Performance
- **Location:** `src/raxe/domain/engine/executor.py:188-209`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** `highest_severity` property recalculates on every call
- **Action:** Cache in `__post_init__`
- **Owner:** TBD

### [P-009] Datetime Generation Per Detection
- **Category:** Performance
- **Location:** `src/raxe/domain/engine/executor.py:288`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** `datetime.now().isoformat()` called for each detection
- **Action:** Capture once at scan start, reuse
- **Owner:** TBD

### [P-010] Context Extraction for Every Match
- **Category:** Performance
- **Location:** `src/raxe/domain/engine/matcher.py:147-167`
- **Priority:** P3 | **Impact:** LOW | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Context before/after extracted even if never displayed
- **Action:** Make context extraction lazy
- **Owner:** TBD

### [P-011] Text Hash Computed Every Scan
- **Category:** Performance
- **Location:** `src/raxe/application/scan_pipeline.py:874-886`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** SHA256 of full text computed on every scan for telemetry
- **Action:** Cache or use faster hash function
- **Owner:** TBD

### [P-012] YAML Rule Loading Not Streaming
- **Category:** Performance
- **Location:** `src/raxe/infrastructure/rules/yaml_loader.py:113-170`
- **Priority:** P3 | **Impact:** LOW | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** All rules loaded into list before processing
- **Action:** Implement streaming/iterator pattern
- **Owner:** TBD

### [ML-006] Embedding Cache Key Missing Model Version
- **Category:** ML/Detection
- **Location:** `src/raxe/domain/ml/gemma_detector.py:369-405`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Cache key is just text hash, stale after model update
- **Action:** Include model version in cache key
- **Owner:** TBD

### [ML-007] No L2 Warm-up Strategy
- **Category:** ML/Detection
- **Location:** `src/raxe/domain/ml/gemma_detector.py:73-214`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** First inference has high latency due to model loading
- **Action:** Add `warm_up()` method
- **Owner:** TBD

### [ML-008] Hard-Coded is_threat Fallback Threshold
- **Category:** ML/Detection
- **Location:** `src/raxe/domain/ml/protocol.py:145`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Fallback uses 0.35 threshold instead of configurable value
- **Action:** Reference L2Config threshold
- **Owner:** TBD

### [ML-009] Division by Zero Sentinel Value
- **Category:** ML/Detection
- **Location:** `src/raxe/domain/ml/voting/engine.py:205-227`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Infinity converted to magic number 999.0
- **Action:** Use explicit flag for "all THREAT votes" case
- **Owner:** TBD

### [ML-010] Duplicate Severity Mapping Logic
- **Category:** ML/Detection
- **Location:** `src/raxe/application/scan_merger.py:278-301`, `scan_pipeline.py:850-872`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Severity mapping with slightly different thresholds in two places
- **Action:** Centralize severity mapping
- **Owner:** TBD

### [ML-011] Technique Safe Labels Incomplete
- **Category:** ML/Detection
- **Location:** `src/raxe/domain/ml/voting/head_voters.py:256-258`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Only "none" marked as safe technique
- **Action:** Review vocabulary and add other benign labels
- **Owner:** TBD

### [D-009] Multiple TODO Comments Pending
- **Category:** Dead Code
- **Location:** Multiple files
- **Priority:** P3 | **Impact:** LOW | **Effort:** VARIES | **Complexity:** VARIES
- **Description:** TODOs for incomplete features scattered across codebase
- **Action:** Track and prioritize or remove stale TODOs
- **Owner:** TBD

### [D-010] privacy CLI Command Not Integrated
- **Category:** Dead Code
- **Location:** `src/raxe/cli/privacy.py`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Complete command but not in main CLI help
- **Action:** Register with main CLI or document usage
- **Owner:** TBD

### [D-011] Unused hash_identifier Function
- **Category:** Dead Code
- **Location:** `src/raxe/domain/telemetry/event_creator.py:46`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Only used internally, could be inlined
- **Action:** Inline or keep as utility (low priority)
- **Owner:** TBD

### [D-012] create_prompt_hash Wrapper Unnecessary
- **Category:** Dead Code
- **Location:** `src/raxe/domain/telemetry/events.py:1235`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Thin wrapper that just calls hash_text with sha256
- **Action:** Consider inlining
- **Owner:** TBD

### [D-013] Deprecated Model Status Enums
- **Category:** Dead Code
- **Location:** `src/raxe/domain/ml/manifest_schema.py:19`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** DEPRECATED enum value defined but not specially handled
- **Action:** Add handling or remove
- **Owner:** TBD

### [D-014] Legacy Raxeignore Check
- **Category:** Dead Code
- **Location:** `src/raxe/domain/suppression_factory.py:31`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Legacy .raxeignore check mentioned but not called
- **Action:** Complete legacy support or remove
- **Owner:** TBD

### [M-009] Missing Type Hints
- **Category:** Maintainability
- **Location:** `src/raxe/sdk/client.py:160`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Some parameters use `object` instead of proper types
- **Action:** Add proper Callable, PluginManager type hints
- **Owner:** TBD

### [M-010] Empty __init__ with Pass
- **Category:** Maintainability
- **Location:** `src/raxe/domain/rules/validator.py:100-101`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Init method with only pass statement
- **Action:** Remove or add comment explaining
- **Owner:** TBD

### [M-011] Inconsistent Naming Conventions
- **Category:** Maintainability
- **Location:** Multiple files
- **Priority:** P3 | **Impact:** LOW | **Effort:** MEDIUM | **Complexity:** LOW
- **Description:** Mixed naming patterns for methods, constants, tables
- **Action:** Standardize naming conventions
- **Owner:** TBD

### [PS-005] Path Handling Not Cross-Platform
- **Category:** Platform/Scalability
- **Location:** Multiple files
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Some places use `/` instead of `os.sep` or `pathlib`
- **Action:** Audit and fix path handling
- **Owner:** TBD

### [PS-006] Windows Path Separator Issues
- **Category:** Platform/Scalability
- **Location:** `src/raxe/infrastructure/config/`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Config paths may not work correctly on Windows
- **Action:** Use pathlib consistently
- **Owner:** TBD

### [PS-007] File Handle Leaks Possible
- **Category:** Platform/Scalability
- **Location:** Multiple files
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Some file operations don't use context managers
- **Action:** Audit and add proper with statements
- **Owner:** TBD

### [PS-008] No Connection Pooling for HTTP
- **Category:** Platform/Scalability
- **Location:** `src/raxe/infrastructure/telemetry/sender.py`
- **Priority:** P3 | **Impact:** LOW | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Each telemetry send may create new connection
- **Action:** Add connection pooling with requests.Session
- **Owner:** TBD

### [T-008] Test Coverage Gaps in CLI
- **Category:** Testing
- **Location:** `tests/unit/cli/`
- **Priority:** P3 | **Impact:** LOW | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Some CLI commands lack comprehensive tests
- **Action:** Add tests for remaining CLI commands
- **Owner:** TBD

### [T-009] Missing Mock Objects in Tests
- **Category:** Testing
- **Location:** `tests/`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Some tests use real I/O instead of mocks
- **Action:** Add proper mocking for I/O operations
- **Owner:** TBD

### [T-010] Test Fixtures Cleanup
- **Category:** Testing
- **Location:** `tests/conftest.py`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Some fixtures don't clean up temporary files
- **Action:** Add proper cleanup in fixtures
- **Owner:** TBD

### [A-005] Missing Boundary Interfaces
- **Category:** Architecture
- **Location:** `src/raxe/`
- **Priority:** P3 | **Impact:** LOW | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Some cross-layer dependencies lack explicit interfaces
- **Action:** Add Protocol definitions at layer boundaries
- **Owner:** TBD

### [A-006] Inconsistent Module Structure
- **Category:** Architecture
- **Location:** `src/raxe/infrastructure/`
- **Priority:** P3 | **Impact:** LOW | **Effort:** LOW | **Complexity:** LOW
- **Description:** Some infrastructure modules have inconsistent structure
- **Action:** Standardize module organization
- **Owner:** TBD

### [C-003] Config Validation Not Comprehensive
- **Category:** Configuration
- **Location:** `src/raxe/infrastructure/config/`
- **Priority:** P3 | **Impact:** LOW | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** Some config values not validated for type/range
- **Action:** Add comprehensive config validation
- **Owner:** TBD

### [C-004] Missing Config Migration Path
- **Category:** Configuration
- **Location:** `src/raxe/infrastructure/config/`
- **Priority:** P3 | **Impact:** LOW | **Effort:** MEDIUM | **Complexity:** MEDIUM
- **Description:** No migration strategy for config changes between versions
- **Action:** Add config version and migration support
- **Owner:** TBD

---

## Architecture Diagrams

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        RAXE-CE ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐
    │   CLI    │    │   SDK    │    │ AsyncSDK  │    │ Wrappers │
    │ (Click)  │    │ (Raxe)   │    │(AsyncRaxe)│    │(OpenAI,  │
    │          │    │          │    │           │    │Anthropic)│
    └────┬─────┘    └────┬─────┘    └─────┬─────┘    └────┬─────┘
         │               │                │               │
         └───────────────┴────────────────┴───────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   APPLICATION LAYER     │
                    ├─────────────────────────┤
                    │ • ScanPipeline          │
                    │ • ScanMerger            │
                    │ • ApplyPolicyUseCase    │
                    │ • TelemetryOrchestrator │
                    └────────────┬────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌────────▼────────┐    ┌────────▼────────┐    ┌────────▼────────┐
│  DOMAIN (L1)    │    │  DOMAIN (L2)    │    │ DOMAIN (POLICY) │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • RuleExecutor  │    │ • GemmaDetector │    │ • PolicyModels  │
│ • PatternMatcher│    │ • VotingEngine  │    │ • Suppression   │
│ • Rule Models   │    │ • L2Protocol    │    │ • Validation    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  INFRASTRUCTURE LAYER   │
                    ├─────────────────────────┤
                    │ • PackRegistry (rules)  │
                    │ • YAMLLoader            │
                    │ • TelemetrySender       │
                    │ • ScanHistoryDB         │
                    │ • ConfigLoader          │
                    └─────────────────────────┘
```

### Detection Pipeline Flow

```
                    INPUT TEXT
                         │
                         ▼
              ┌─────────────────────┐
              │    ScanPipeline     │
              │      .scan()        │
              └──────────┬──────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
         ▼                               ▼
┌─────────────────┐            ┌─────────────────┐
│   L1 ENGINE     │            │   L2 ENGINE     │
│ (Rule-based)    │            │ (ML-based)      │
├─────────────────┤            ├─────────────────┤
│ PackRegistry    │            │ GemmaL2Detector │
│ → 460+ rules    │            │ → Tokenizer     │
│ → 7 families    │            │ → Embeddings    │
│                 │            │ → 5 Classifiers │
│ RuleExecutor    │            │ → VotingEngine  │
│ → Pattern Match │            │                 │
│ → Confidence    │            │ Decision:       │
│                 │            │ SAFE/REVIEW/    │
│ Output:         │            │ THREAT          │
│ • detections[]  │            │                 │
│ • severity      │            │ Output:         │
└────────┬────────┘            │ • L2Result      │
         │                     │ • voting data   │
         │                     └────────┬────────┘
         │                              │
         └──────────────┬───────────────┘
                        │
                        ▼
              ┌─────────────────────┐
              │    ScanMerger       │
              │ Combines L1 + L2    │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   PolicyEvaluator   │
              │ → Apply policies    │
              │ → Determine action  │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ ScanPipelineResult  │
              │ • has_threats       │
              │ • should_block      │
              │ • severity          │
              └─────────────────────┘
```

### 5-Head Classifier Architecture

```
                    INPUT TEXT
                         │
                         ▼
              ┌─────────────────────┐
              │  Gemma2 Tokenizer   │
              │  (max 512 tokens)   │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Embedding Model    │
              │  (Matryoshka 256d)  │
              │  (ONNX Runtime)     │
              └──────────┬──────────┘
                         │
     ┌───────────────────┼───────────────────┐
     │       │       │       │       │       │
     ▼       ▼       ▼       ▼       ▼       ▼
┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
│ BINARY ││ FAMILY ││SEVERITY││TECHNIQUE│ HARM   │
│ HEAD   ││ HEAD   ││ HEAD   ││ HEAD   ││TYPES   │
├────────┤├────────┤├────────┤├────────┤├────────┤
│2 class ││9 class ││5 class ││22 class││10 label│
│threat/ ││benign, ││none,   ││none,   ││multi-  │
│safe    ││PI, JB, ││low,    ││instr-  ││label   │
│        ││CMD,etc ││medium, ││override││        │
│        ││        ││high,   ││,etc    ││        │
│        ││        ││critical││        ││        │
└────┬───┘└────┬───┘└────┬───┘└────┬───┘└────┬───┘
     │         │         │         │         │
     └─────────┴─────────┴─────────┴─────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │    VOTING ENGINE    │
              ├─────────────────────┤
              │ 1. Head Voters      │
              │    - threshold conf │
              │    - vote SAFE/     │
              │      ABSTAIN/THREAT │
              │                     │
              │ 2. Weighted Votes   │
              │    - binary: 2.0    │
              │    - family: 1.5    │
              │    - severity: 1.5  │
              │    - technique: 1.0 │
              │    - harm: 0.8      │
              │                     │
              │ 3. Decision Rules   │
              │    - high-conf rule │
              │    - severity veto  │
              │    - min votes      │
              │    - ratio thresh   │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   VotingResult      │
              │ • decision          │
              │ • confidence        │
              │ • per_head_votes    │
              │ • rule_triggered    │
              └─────────────────────┘
```

---

## Quick Wins (Effort: LOW, High Impact)

1. **[T-001]** Fix hash length test assertion
2. **[M-003]** Replace bare except with specific exceptions
3. **[D-003]** Remove empty cloud module directory
4. **[D-001]** Remove duplicate hash_text function
5. **[P-004]** Cache get_all_rules() result
6. **[P-005]** Move orchestrator init to pipeline __init__

## Recommended Sprint Planning

### Sprint 1 (Stability)
- Fix T-001 (test bug)
- Fix S-001 (regex timeout)
- Fix S-002 (tarfile security)
- Fix M-003 (bare except)

### Sprint 2 (Cleanup)
- Remove dead code (D-001 to D-008)
- Fix duplicate logic (M-004)
- Add missing tests (T-002, T-003)

### Sprint 3 (Performance)
- Implement P-001 to P-005 quick wins
- Add warm-up for L2 (ML-007)
- Cache improvements (P-007, P-008)

### Sprint 4 (Architecture)
- Refactor God class M-001
- Fix architecture violations (A-001, A-002)
- Improve error handling (M-006)

---

## Changelog

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-20 | Claude (multi-agent review) | Initial comprehensive review |

