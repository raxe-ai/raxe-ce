<p align="center">
  <img src="https://github.com/raxe-ai/raxe-ce/blob/main/docs/assets/logo-square.png?raw=true" alt="RAXE" width="100"/>
</p>

# RAXE Architecture

## Overview

RAXE Community Edition is built on **Clean Architecture** principles with strict separation of concerns, ensuring maintainability, testability, and transparency. This document explains the system design, architectural decisions, and key components.

## Design Philosophy

RAXE is designed around three core principles:

1. **Privacy by Architecture** - Local-first design makes privacy violations impossible, not just improbable
2. **Transparency Through Code** - Open source architecture that can be audited and verified
3. **Domain Purity** - Core business logic isolated from I/O operations for testability and clarity

## Architecture Layers

RAXE follows **Hexagonal Architecture** (also known as Ports and Adapters) with four distinct layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLI / SDK Layer                              │
│  • Click commands (raxe scan, raxe rules, etc.)                 │
│  • Public Python SDK (Raxe class, decorators)                   │
│  • LLM client wrappers (RaxeOpenAI, RaxeAnthropic)              │
│  • Entry points for user interaction                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Application Layer                             │
│  • Use cases (scan_prompt, validate_rule, etc.)                 │
│  • Workflow orchestration                                       │
│  • Coordinates domain + infrastructure                          │
│  • Transaction boundaries                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              Domain Layer (PURE - NO I/O)                        │
│  • RuleExecutor (pure detection logic)                          │
│  • RuleExecutor (pattern matching)                              │
│  • ScanResult (value objects)                                   │
│  • Threat models and entities                                   │
│  • NO database, NO network, NO filesystem (except ML models)    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                            │
│  • SQLite persistence (ScanRepository)                          │
│  • HTTP client for telemetry                                    │
│  • File I/O for configuration                                   │
│  • YAML rule loading                                            │
│  • ML model loading (ONNX runtime)                              │
└─────────────────────────────────────────────────────────────────┘
```

## Domain Layer: The Heart of RAXE

The domain layer is **completely pure** - it contains zero I/O operations. This is a critical architectural constraint that ensures:

- **Testability**: No mocks needed, just pure function testing
- **Performance**: No I/O latency in core detection logic
- **Transparency**: Business logic is visible and auditable
- **Portability**: Domain logic works anywhere (cloud, edge, embedded)

### What's Allowed in Domain

✅ **Pure Functions**
```python
def detect_prompt_injection(prompt: str, rules: list[Rule]) -> list[Detection]:
    """Pure function - deterministic, no side effects"""
    detections = []
    for rule in rules:
        if rule.pattern.search(prompt):
            detections.append(Detection(rule_id=rule.id, ...))
    return detections
```

✅ **Value Objects**
```python
@dataclass(frozen=True)
class Detection:
    rule_id: str
    severity: Severity
    confidence: float
    matched_text: str
```

✅ **Business Logic**
```python
def calculate_combined_severity(detections: list[Detection]) -> Severity:
    """Pure business logic"""
    if not detections:
        return Severity.NONE
    # Weighted severity calculation
    max_severity = max(d.severity for d in detections)
    return max_severity
```

### What's Forbidden in Domain

❌ **Database Calls**
```python
# DON'T DO THIS IN DOMAIN
def detect_threats(prompt: str) -> list[Detection]:
    rules = load_rules_from_database()  # ❌ I/O in domain!
    ...
```

❌ **File I/O**
```python
# DON'T DO THIS IN DOMAIN
def load_config() -> Config:
    with open('config.yaml') as f:  # ❌ File I/O in domain!
        return yaml.load(f)
```

❌ **Network Requests**
```python
# DON'T DO THIS IN DOMAIN
def check_threat(prompt: str) -> bool:
    response = requests.post(api_url, json={...})  # ❌ Network I/O in domain!
    return response.json()
```

## Dual-Layer Detection System

RAXE uses a two-layer detection approach for comprehensive threat coverage:

### L1: Rule-Based Detection

Fast, precise pattern matching using curated YAML rules:

```
┌─────────────────┐
│  User Prompt    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  L1 Detector    │
│  • Regex rules  │
│  • Fast (<1ms)  │
│  • 460 rules    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  L1 Detections  │
│  • Rule matches │
│  • Severity     │
│  • Confidence   │
└─────────────────┘
```

**Characteristics:**
- **Speed**: < 1ms median latency
- **Precision**: 95%+ on known patterns
- **Coverage**: 7 threat families (PI, JB, PII, CMD, ENC, HC, RAG)
- **Transparency**: Every rule is auditable YAML

### L2: ML-Based Detection

Adaptive detection for obfuscated and novel attacks:

```
┌─────────────────┐
│  User Prompt    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Embeddings     │
│  (sentence-tf)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ONNX Model     │
│  • CPU-friendly │
│  • Quantized    │
│  • Fast (5-10ms)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  L2 Detections  │
│  • Anomaly score│
│  • Threat class │
└─────────────────┘
```

**Characteristics:**
- **Speed**: 5-10ms median latency
- **Recall**: 85%+ on novel/obfuscated attacks
- **Model**: Quantized ONNX for CPU efficiency
- **Fallback**: Gracefully degrades to L1 if model unavailable

### Combined Detection

```
┌──────────────┐     ┌──────────────┐
│ L1 Results   │     │ L2 Results   │
│ • Rule-based │     │ • ML-based   │
└──────┬───────┘     └──────┬───────┘
       │                    │
       └──────────┬─────────┘
                  │
                  ▼
         ┌────────────────┐
         │ Scoring Engine │
         │ • Hierarchical │
         │ • Weighted avg │
         └────────┬───────┘
                  │
                  ▼
         ┌────────────────┐
         │  Final Result  │
         │ • Combined     │
         │ • Severity     │
         │ • Detections   │
         └────────────────┘
```

## Privacy-First Architecture

RAXE's privacy guarantees are **architectural**, not just policy:

### Local-First Scanning

```
┌──────────────────────────────────────┐
│         User's Machine               │
│                                      │
│  ┌────────────┐                     │
│  │   Prompt   │                     │
│  └─────┬──────┘                     │
│        │                            │
│        ▼                            │
│  ┌────────────┐                     │
│  │ L1 Detector│ (Local)             │
│  └─────┬──────┘                     │
│        │                            │
│        ▼                            │
│  ┌────────────┐                     │
│  │ L2 Detector│ (Local ONNX)        │
│  └─────┬──────┘                     │
│        │                            │
│        ▼                            │
│  ┌────────────┐                     │
│  │   Result   │ ← All local!        │
│  └────────────┘                     │
│                                      │
└──────────────────────────────────────┘

       Optional Telemetry
              │
              ▼ (metadata + metrics)
┌──────────────────────────────────────┐
│         Cloud (Optional)             │
│  ┌────────────────────────┐          │
│  │  Telemetry Payload     │          │
│  │  • api_key (auth)      │          │
│  │  • prompt_hash (SHA256)│          │
│  │  • rule_id: "pi-001"   │          │
│  │  • severity: "HIGH"    │          │
│  │  • confidence: 0.95    │          │
│  │  • scan_duration_ms    │          │
│  │  • l2_metrics          │          │
│  │  NO raw prompts/text   │          │
│  └────────────────────────┘          │
└──────────────────────────────────────┘
```

### Privacy Guarantees

1. **No Prompt Transmission** - Raw prompts never leave device (verifiable in code)
2. **Hash for Uniqueness** - SHA-256 hash sent for deduplication (hard to reverse)
3. **API Key for Auth** - Identifies client for service access control
4. **Performance Metrics** - Scan durations and L2 metrics for optimization
5. **Optional Telemetry** - User controls everything, can disable completely
6. **No End-User PII** - No customer user IDs, IPs, or personal data
7. **Offline Capable** - Works 100% offline with zero degradation

## Data Flow

### Scan Flow (End-to-End)

```
1. User Input
   │
   ▼
2. CLI/SDK Layer
   raxe.scan("user prompt")
   │
   ▼
3. Application Layer
   scan_prompt_use_case()
   │
   ├─→ Load rules from infrastructure
   │   (RuleRepository.load_all())
   │
   ├─→ Pass to domain layer
   │   (detect_threats(prompt, rules))
   │
   ├─→ Domain returns detections
   │   (pure function, no I/O)
   │
   └─→ Save result to queue
       (ScanRepository.save())
   │
   ▼
4. Background Worker
   │
   ├─→ Batch scans from queue
   │
   ├─→ Extract detection metadata only
   │
   └─→ Send telemetry (if enabled)
       (TelemetryClient.send())
   │
   ▼
5. Return Result
   ScanResult with detections
```

### Configuration Loading

```
1. Application Start
   │
   ▼
2. Config Loader (Infrastructure)
   │
   ├─→ Check ~/.raxe/config.yaml
   │
   ├─→ Apply env var overrides
   │
   └─→ Validate schema
   │
   ▼
3. Rule Loader (Infrastructure)
   │
   ├─→ Load YAML rules from packs/
   │
   ├─→ Compile regex patterns
   │
   └─→ Cache in memory
   │
   ▼
4. Domain Layer Initialization
   │
   └─→ Receives rules as dependency
       (NO file I/O in domain)
```

## Key Design Decisions

### 1. Why Clean Architecture?

**Decision**: Separate domain logic from I/O operations

**Rationale**:
- **Testability**: Pure functions are trivial to test
- **Performance**: No I/O latency in hot path
- **Transparency**: Business logic is crystal clear
- **Portability**: Domain works anywhere

**Trade-off**: More boilerplate, but worth it for clarity

### 2. Why Dual-Layer Detection?

**Decision**: L1 (rules) + L2 (ML) instead of ML-only

**Rationale**:
- **Explainability**: Rule-based is transparent
- **Speed**: Regex is faster than ML inference
- **Coverage**: ML catches obfuscated patterns
- **Reliability**: Fallback if ML model unavailable

**Trade-off**: More complexity, but better UX

### 3. Why Local-First?

**Decision**: All scanning happens locally

**Rationale**:
- **Privacy**: No prompt transmission = no privacy risk
- **Latency**: Local = sub-millisecond response
- **Reliability**: No network dependency
- **Trust**: Users can verify behavior

**Trade-off**: Can't leverage cloud-scale ML (yet)

### 4. Why SQLite for Storage?

**Decision**: Embedded SQLite instead of remote DB

**Rationale**:
- **Zero Config**: No DB setup required
- **Privacy**: All data stays local
- **Portability**: Single file, easy backups
- **Performance**: Fast enough for local use

**Trade-off**: Not suitable for multi-user scenarios

### 5. Why YAML for Rules?

**Decision**: Human-readable YAML instead of code

**Rationale**:
- **Accessibility**: Non-programmers can contribute
- **Transparency**: Easy to audit and review
- **Versioning**: Git-friendly format
- **Validation**: Schema-validated before use

**Trade-off**: Slightly slower parsing (mitigated by caching)

## Extension Points

RAXE is designed to be extensible:

### 1. Custom Detectors (Plugin System)

```python
from raxe.plugins.protocol import DetectorPlugin

class MyCustomDetector(DetectorPlugin):
    """Custom detection logic"""

    def detect(self, prompt: str) -> list[Detection]:
        # Your custom logic here
        return detections

# Register plugin
raxe = Raxe(plugins=[MyCustomDetector()])
```

### 2. Custom Storage Backends

*(Planned feature - not yet implemented in v0.1.0)*

```python
from raxe.infrastructure.database.protocol import ScanRepository

class PostgresRepository(ScanRepository):
    """Custom storage implementation"""

    def save(self, scan: ScanResult) -> None:
        # Your storage logic
        pass

# Use custom repository
raxe = Raxe(scan_repository=PostgresRepository())
```

### 3. Custom Telemetry Backends

*(Planned feature - not yet implemented in v0.1.0)*

```python
from raxe.infrastructure.telemetry.protocol import TelemetryClient

class DatadogTelemetry(TelemetryClient):
    """Send metrics to Datadog"""

    def send(self, metrics: dict) -> None:
        # Your telemetry logic
        pass
```

## Performance Characteristics

### Latency Targets

| Operation | Target | Actual (P95) |
|-----------|--------|--------------|
| L1 Scan   | < 5ms  | 0.49ms (10x better) |
| L2 Scan   | < 10ms | 7.2ms (1.4x better) |
| Combined  | < 15ms | 8.1ms (1.8x better) |
| Rule Load | < 100ms | 45ms (2.2x better) |

### Throughput

- **Sequential**: ~120 scans/second
- **Batch Mode**: ~1,200 scans/second (10x improvement)
- **Memory**: ~60MB peak usage

### Optimizations

1. **Regex Compilation**: Rules compiled once at startup
2. **Batch Processing**: Amortize overhead across multiple scans
3. **ONNX Quantization**: 4x smaller models, 2x faster inference
4. **Pattern Caching**: Common patterns cached in memory
5. **Lazy Loading**: ML models loaded only when needed

## Security Considerations

### 1. Input Validation

All user input is validated at boundaries:

```python
def validate_prompt(prompt: str) -> None:
    if not isinstance(prompt, str):
        raise TypeError("Prompt must be string")
    if len(prompt) > 100_000:
        raise ValueError("Prompt too large")
```

### 2. ReDoS Protection

All regex patterns are validated for catastrophic backtracking:

```python
def validate_pattern(pattern: str) -> None:
    """Ensure pattern is ReDoS-safe"""
    # Check for exponential backtracking
    if has_nested_quantifiers(pattern):
        raise ValueError("Pattern may cause ReDoS")
```

### 3. Sandboxed ML Inference

ML models run in isolated ONNX runtime:

- No code execution (pure inference)
- Memory limits enforced
- Timeout protection

### 4. Secure Defaults

- Telemetry enabled by default (opt-out requires Pro+ tier)
- Block threats by default (fail-secure)
- HTTPS enforced for telemetry
- No sensitive data in logs

## Testing Strategy

### 1. Unit Tests (Domain Layer)

Pure function testing with no mocks:

```python
def test_detect_prompt_injection():
    rules = [create_pi_rule()]
    result = detect_prompt_injection("Ignore all instructions", rules)
    assert len(result) == 1
    assert result[0].severity == Severity.HIGH
```

### 2. Integration Tests (Application Layer)

Test workflows with real dependencies:

```python
def test_scan_workflow():
    raxe = Raxe()
    result = raxe.scan("test prompt")
    assert isinstance(result, ScanResult)
```

### 3. Golden File Tests

Prevent regressions with snapshot testing:

```python
@pytest.mark.parametrize("test_case", golden_files)
def test_golden(test_case):
    expected = load_golden(test_case)
    actual = scan_prompt(test_case.input)
    assert actual == expected
```

### 4. Property-Based Tests

Generate random inputs to find edge cases:

```python
@given(st.text())
def test_scan_never_crashes(prompt):
    result = raxe.scan(prompt)  # Should never raise
    assert isinstance(result, ScanResult)
```

## Future Architecture Considerations

### v0.2: Response Scanning

Add output scanning to detect unsafe LLM responses:

```
Prompt → L1/L2 → LLM → Response → L1/L2 → Safe Output
```

### v1.0: Policy-as-Code

Allow complex policy definitions:

```yaml
policy:
  name: "Corporate Policy"
  rules:
    - if: severity >= HIGH
      then: block
    - if: family == PII
      then: redact
    - if: confidence < 0.7
      then: warn
```

### v2.0: Distributed Architecture

Support multi-node deployments:

```
Edge Nodes (local scanning)
     ↓
Aggregation Layer (analytics)
     ↓
Central Dashboard (visualization)
```

## References

- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html) - Robert C. Martin
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/) - Alistair Cockburn
- [Domain-Driven Design](https://martinfowler.com/bliki/DomainDrivenDesign.html) - Eric Evans
- [OWASP LLM Top 10](https://owasp.org/www-project-top-ten/) - Security best practices

## Summary

RAXE's architecture is designed for:

- **Privacy**: Local-first design prevents data leakage
- **Performance**: Clean architecture enables sub-millisecond scans
- **Transparency**: Pure domain logic is auditable
- **Reliability**: Fail-safe defaults and graceful degradation
- **Extensibility**: Plugin system for custom logic

Every architectural decision prioritizes user trust through verifiable design, not just promises.
