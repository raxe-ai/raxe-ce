# RAXE CE - Quick Reference Guide

## Single Entry Point Architecture
All interfaces → `Raxe.scan()` (ONLY scanning method)

```
CLI, SDK, Decorators, Wrappers, Integrations
    ↓
Raxe.scan(text, **options)
    ↓
ScanPipeline orchestration
    ↓
ScanPipelineResult
```

---

## Developer Interfaces (5 Ways to Use RAXE)

### 1. CLI (`raxe` command)
```bash
raxe scan "text" --format json --mode fast
raxe batch prompts.txt --output results.json
raxe stats
```
**File:** `src/raxe/cli/main.py`

### 2. SDK Direct Usage
```python
from raxe import Raxe

raxe = Raxe()
result = raxe.scan(text)
if result.has_threats:
    print(f"Severity: {result.severity}")
```
**File:** `src/raxe/sdk/client.py`

### 3. Decorator Pattern
```python
@raxe.protect
def generate(prompt: str) -> str:
    return llm.generate(prompt)  # Raises SecurityException on threat
```
**File:** `src/raxe/sdk/decorator.py`

### 4. LLM Client Wrappers
```python
from raxe import RaxeOpenAI

client = RaxeOpenAI(api_key="sk-...")
response = client.chat.completions.create(...)  # Auto-scanned
```
**File:** `src/raxe/sdk/wrappers/`

### 5. Plugins
```python
class MyDetector(DetectorPlugin):
    def detect(self, text, context=None) -> list[Detection]:
        # Custom detection logic
        return detections

plugin = MyDetector()
```
**File:** `src/raxe/plugins/` + `examples/plugins/`

---

## Scan Pipeline Layers

```
Input Text
    ↓
[L1 Layer] RuleExecutor.execute() → Regex patterns → <5ms
    ↓
[L2 Layer] L2Detector.detect() → ML model → <1ms (optional)
    ↓
[Plugin Layer] PluginManager.run_detectors() → Custom logic
    ↓
[Merge] ScanMerger → CombinedScanResult
    ↓
[Policy] ScanPolicy.should_block() → BlockAction (ALLOW/WARN/BLOCK)
    ↓
[Actions] PluginManager.run_actions() → Send Slack, log, etc.
    ↓
[Track] Record in database + telemetry
    ↓
Return ScanPipelineResult
```

---

## Core Domain Models

**Enums:**
- `Severity`: CRITICAL, HIGH, MEDIUM, LOW, INFO
- `BlockAction`: ALLOW, WARN, BLOCK, CHALLENGE
- `RuleFamily`: PI (Prompt Injection), JB (Jailbreak), PII, CMD, ENC, RAG, HC, SEC, QUAL, CUSTOM

**Key Objects:**
- `Detection`: rule_id, severity, confidence, message, explanation
- `ScanResult`: detections[], scanned_at, text_length, scan_duration_ms
- `ScanPolicy`: block_on_critical, confidence_threshold, etc.
- `Rule`: id, version, family, severity, patterns[]
- `ScanPipelineResult`: scan_result, policy_decision, should_block, duration_ms

---

## Configuration Cascade

```
1. Explicit parameters → Raxe(api_key="...", telemetry=False)
2. Environment variables → RAXE_API_KEY, RAXE_ENABLE_L2
3. Config file → ~/.raxe/config.yaml
4. Defaults → ScanConfig()
```

---

## Plugin Lifecycle

```
1. on_init(config) → Load configuration
2. on_scan_start(text) → Pre-scan, can transform input
3. [L1/L2/Plugin detection]
4. on_scan_complete(result) → Post-scan notification
5. on_threat_detected(result) → If threats found
6. [Actions] execute() → Send alerts, log, etc.
7. on_shutdown() → Cleanup
```

---

## Performance Targets

| Layer | Target | Notes |
|-------|--------|-------|
| **L1** | <5ms | Regex-based detection |
| **L2** | <1ms | ML detection |
| **Overhead** | <4ms | Merging, policy, tracking |
| **Total P95** | <10ms | End-to-end latency |
| **Startup** | 100-200ms | One-time initialization cost |

---

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `src/raxe/cli/` | Command-line interface |
| `src/raxe/sdk/` | Python SDK (client, decorator, wrappers) |
| `src/raxe/domain/` | Pure business logic (engine, rules, models) |
| `src/raxe/application/` | Orchestration (pipeline, preloader) |
| `src/raxe/infrastructure/` | I/O (config, database, packs, telemetry) |
| `src/raxe/plugins/` | Plugin system (manager, loader, protocol) |
| `src/raxe/utils/` | Utilities (logging, validators, profiler) |
| `examples/` | Usage examples and integrations |

---

## Common Code Patterns

### Basic Scan
```python
from raxe import Raxe
raxe = Raxe()
result = raxe.scan("user input")
```

### With Blocking
```python
try:
    raxe.scan(text, block_on_threat=True)
except SecurityException as e:
    print(f"Blocked: {e.result.severity}")
```

### Performance Variants
```python
raxe.scan_fast(text)                    # L1 only, <3ms
raxe.scan_thorough(text)                # All layers, <100ms
raxe.scan_high_confidence(text, 0.8)   # High confidence only
```

### With Custom Config
```python
result = raxe.scan(
    text,
    mode="fast|balanced|thorough",
    l1_enabled=True,
    l2_enabled=True,
    confidence_threshold=0.5,
    explain=True,
    customer_id="customer123"
)
```

### Check Results
```python
if result.has_threats:
    print(f"Severity: {result.severity}")
    print(f"Detections: {result.total_detections}")
    print(f"Action: {result.policy_decision.value}")
    print(f"Should Block: {result.should_block}")
```

### Access Detections
```python
# L1 detections (regex-based)
for detection in result.scan_result.l1_result.detections:
    print(f"{detection.rule_id}: {detection.message}")

# L2 predictions (ML-based)
if result.scan_result.l2_result:
    for prediction in result.scan_result.l2_result.predictions:
        print(f"{prediction.threat_type}: {prediction.explanation}")
```

---

## Class Hierarchy

```
Domain Layer (Pure Logic):
  ├── ScanResult
  ├── Detection
  ├── Rule
  ├── Pattern
  ├── Severity (Enum)
  ├── BlockAction (Enum)
  └── RuleExecutor

Application Layer (Orchestration):
  ├── ScanPipeline
  ├── ScanMerger
  └── PreloadStats

Infrastructure Layer (I/O):
  ├── ScanConfig
  ├── PackRegistry
  ├── ScanHistoryDB
  └── TelemetryManager

SDK Layer (User Interface):
  ├── Raxe (client)
  ├── Decorator (protect)
  ├── Wrappers (RaxeOpenAI, RaxeAnthropic)
  └── Integrations (LangChain, HuggingFace)

Plugin System:
  ├── PluginManager
  ├── PluginLoader
  ├── RaxePlugin (Protocol)
  ├── DetectorPlugin (Protocol)
  ├── ActionPlugin (Protocol)
  └── TransformPlugin (Protocol)
```

---

## Output Formatting

**Formats:**
- Text: Rich colored terminal output
- JSON: Machine-readable structured data
- YAML: Human-readable data format
- CSV: Spreadsheet format for batch results

**Rich Output Features:**
- Colored severity indicators (🔴🟠🟡🔵)
- Formatted tables for detections
- Progress bars for batch operations
- Styled panels and panels

---

## Logging & Privacy

**Logging System:**
- Structured logging with PII redaction
- Console handler (dev) + File handler (production)
- Auto-redact: prompts, responses, API keys, secrets
- Session tracking for log correlation
- Environment-based configuration

**Privacy:**
- NO actual prompts stored in database (only hashes)
- NO secrets transmitted in telemetry
- Text hashes: SHA256 for privacy-preserving tracking
- Privacy-first telemetry batching

---

## File Structure Overview

```
Total modules: 60+
Total LOC: ~20,000
Entry point: src/raxe/__init__.py → Raxe class
CLI entry: src/raxe/cli/main.py → cli() function
Config: ~/.raxe/config.yaml (user config)
Database: ~/.raxe/scan_history.db (SQLite)
Plugins: ~/.raxe/plugins/ (custom plugins)
Packs: ~/.raxe/packs/ (rule packs)
Logs: ~/.raxe/logs/raxe.log (structured logs)
```

---

## Quick Debug Checklist

- [ ] Check `raxe doctor` for health status
- [ ] Verify config: `raxe init --force`
- [ ] Test scan: `raxe scan "test" --format json`
- [ ] List rules: `raxe rules list`
- [ ] Check logs: `~/.raxe/logs/raxe.log`
- [ ] Enable verbose: `raxe scan "text" --verbose`
- [ ] Check plugins: `raxe plugins`
- [ ] Validate config: `python -c "from raxe import Raxe; Raxe().validate_configuration()"`

