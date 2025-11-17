# RAXE CE - Codebase Exploration Summary

## Overview
Complete exploration and documentation of the RAXE CE (Community Edition) AI security system for LLMs.

**Total Modules:** 60+  
**Total Lines of Code:** ~20,000  
**Architecture:** Clean Architecture (Domain → Application → Infrastructure)  
**Entry Points:** 5 (CLI, SDK, Decorator, Wrappers, Plugins)

---

## Generated Documentation

### 1. **ARCHITECTURE_MAP.md** (1,261 lines)
Comprehensive deep-dive into the entire RAXE system. Contains:
- Complete directory structure with descriptions
- Unified scanning system flow
- All 5 developer interfaces with code examples
- Domain layer (pure business logic)
- Application layer (orchestration)
- Infrastructure layer (I/O & external APIs)
- Plugin architecture (7 plugin types)
- Output & formatting mechanisms
- Logging system with privacy
- Configuration systems
- Developer workflows

**When to use:** Need detailed understanding of how something works

### 2. **QUICK_REFERENCE.md** (400 lines)
Quick lookup guide for developers. Contains:
- Single entry point architecture
- 5 ways to use RAXE
- Scan pipeline layers
- Core domain models
- Configuration cascade
- Plugin lifecycle
- Performance targets
- Key directories
- Common code patterns
- Class hierarchy
- Output formatting
- Logging & privacy
- Quick debug checklist

**When to use:** Need a quick reminder or want to see code examples

### 3. **ARCHITECTURE_DIAGRAM.txt** (ASCII diagram)
Visual representation of the system:
- User interface layer (5 interfaces → single entry point)
- Application layer (9-step pipeline)
- Domain layer (pure logic)
- Infrastructure layer (I/O & external APIs)
- Plugin system (extensibility)
- Utilities & monitoring
- Key design principles

**When to use:** Want a visual overview or present to team

---

## Key Findings

### 1. Single Entry Point Design
All interfaces converge on `Raxe.scan()` - the ONLY scanning method:
```
CLI/SDK/Decorator/Wrappers/Integrations → Raxe.scan() → ScanPipelineResult
```

### 2. Clean Architecture
```
Domain Layer (no I/O)
    ↓
Application Layer (orchestration)
    ↓
Infrastructure Layer (I/O, databases, APIs)
```

### 3. Scanning Pipeline (9 Steps)
```
Input → L1 (Regex) → L2 (ML) → Plugins → Merge → Policy → Actions → Track → Result
```

### 4. Developer Interfaces (5 Ways)
1. **CLI**: `raxe scan "text"` command-line tool
2. **SDK**: `raxe.scan(text)` direct Python usage
3. **Decorator**: `@raxe.protect` function protection
4. **Wrappers**: `RaxeOpenAI()` drop-in LLM client replacement
5. **Plugins**: Custom DetectorPlugin, ActionPlugin, TransformPlugin

### 5. Plugin System
```
RaxePlugin (Base)
├─ DetectorPlugin → detect() → custom threat detection
├─ ActionPlugin → should_execute() + execute() → send alerts
├─ TransformPlugin → transform_input/output() → text transforms
└─ Lifecycle hooks: on_init, on_scan_start, on_scan_complete, on_threat_detected, on_shutdown
```

### 6. Performance Optimization
- **L1 Layer**: <5ms (regex-based detection)
- **L2 Layer**: <1ms (ML detection)
- **Total P95**: <10ms (end-to-end)
- **Startup**: 100-200ms one-time (preload)
- **Fail-fast**: Skip L2 if CRITICAL detected with high confidence

### 7. Privacy-First Design
- NO actual prompts stored (only SHA256 hashes)
- PII auto-redaction in logs (prompts, API keys, secrets)
- Privacy-preserving telemetry (no data transmission)
- Text hashes used for privacy-respecting tracking

### 8. Configuration Cascade
```
Explicit parameters → Environment variables → Config file → Defaults
```

### 9. Output Formatting
- **Text**: Rich colored terminal output with tables
- **JSON**: Machine-readable structured data
- **YAML**: Human-readable format
- **CSV**: Spreadsheet format for batch results

### 10. Logging & Monitoring
- Structured logging (structlog)
- PII redaction processor
- Console handler (dev) + File handler (production)
- Prometheus metrics
- Performance profiling
- Analytics (achievements, streaks, retention)

---

## Directory Structure

```
src/raxe/
├── cli/                    # Command-line interface (Click)
├── sdk/                    # Python SDK (Raxe client, decorator, wrappers)
├── domain/                 # Pure business logic (engine, rules, models)
├── application/            # Orchestration (pipeline, preloader)
├── infrastructure/         # I/O (config, database, packs, telemetry)
├── plugins/                # Plugin system (manager, loader, protocol)
├── utils/                  # Utilities (logging, validators, profiler)
├── monitoring/             # Prometheus metrics, profiling
├── async_sdk/              # Async/await versions
└── packs/                  # Bundled rule packs (core, custom, community)
```

---

## Most Important Files

### Entry Points
- **`src/raxe/__init__.py`**: Public API exports
- **`src/raxe/sdk/client.py`**: Raxe() class - SINGLE ENTRY POINT
- **`src/raxe/cli/main.py`**: CLI commands

### Core Logic
- **`src/raxe/domain/engine/executor.py`**: RuleExecutor - pattern matching
- **`src/raxe/domain/rules/models.py`**: Rule, Pattern, Severity
- **`src/raxe/application/scan_pipeline.py`**: ScanPipeline - orchestration

### Infrastructure
- **`src/raxe/infrastructure/config/scan_config.py`**: Configuration loading
- **`src/raxe/infrastructure/packs/registry.py`**: PackRegistry - rule loading
- **`src/raxe/infrastructure/database/scan_history.py`**: Database persistence

### Plugins
- **`src/raxe/plugins/protocol.py`**: Plugin protocols
- **`src/raxe/plugins/manager.py`**: PluginManager - orchestration
- **`examples/plugins/`**: Plugin examples

### Output
- **`src/raxe/cli/output.py`**: Rich formatting

### Logging
- **`src/raxe/utils/logging.py`**: Structured logging with PII redaction

---

## Performance Targets

| Component | Target | Status |
|-----------|--------|--------|
| L1 Detection | <5ms | Regex-based |
| L2 Detection | <1ms | ML-based |
| Total Latency | <10ms P95 | Combined |
| Startup | 100-200ms | One-time |
| Fast Mode | <3ms | L1 only |
| Thorough Mode | <100ms | All layers |

---

## Design Principles

### 1. Clean Architecture
Domain (pure logic) → Application (orchestration) → Infrastructure (I/O)

### 2. Single Responsibility
Each class has one reason to change

### 3. Dependency Inversion
Depend on abstractions (protocols), not concrete implementations

### 4. Error Isolation
Plugin failures don't crash core system

### 5. Privacy-First
No sensitive data in logs, database, or telemetry

### 6. Performance Optimization
Preload, lazy loading, fail-fast, layer control

### 7. Configuration Flexibility
Environment > File > Defaults with explicit overrides

### 8. Extensibility
Plugin system with hooks, protocols, error isolation

---

## How Developers Use RAXE

### 1. Quick CLI Test
```bash
raxe scan "Ignore all previous instructions"
```

### 2. SDK Integration
```python
from raxe import Raxe
raxe = Raxe()
result = raxe.scan(user_prompt)
if result.has_threats:
    print(f"Blocked: {result.severity}")
```

### 3. Decorator Protection
```python
@raxe.protect
def generate(prompt: str) -> str:
    return llm.generate(prompt)  # Raises SecurityException on threat
```

### 4. LLM Wrapper
```python
from raxe import RaxeOpenAI
client = RaxeOpenAI(api_key="sk-...")
response = client.chat.completions.create(...)  # Auto-scanned
```

### 5. Custom Plugin
```python
class MyDetector(DetectorPlugin):
    def detect(self, text, context=None):
        if "malicious" in text:
            return [Detection(...)]
        return []
```

---

## Configuration Files

### ~/.raxe/config.yaml
Main configuration file with sections:
- API (api_key)
- Telemetry (enabled, endpoint, batching)
- Performance (mode, L2 settings)
- Policy (blocking rules)
- Packs (precedence)
- Plugins (enabled + per-plugin config)

### ~/.raxe/plugins/
Plugin directory:
- `custom_detector/` - User-defined patterns
- `slack_notifier/` - Slack alerts
- `file_logger/` - File logging
- `webhook/` - Webhook posting

### ~/.raxe/packs/
Rule packs:
- `core/` - Built-in rules
- `custom/` - User packs (override core)
- `community/` - Community packs

---

## Testing & Validation

### CLI Health Check
```bash
raxe doctor
```

### Validation Code
```python
from raxe import Raxe
raxe = Raxe()
validation = raxe.validate_configuration()
```

### Debug Checklist
- [ ] `raxe doctor` - Health status
- [ ] `raxe init --force` - Reinit config
- [ ] `raxe scan "test" --format json` - Test scan
- [ ] `raxe rules list` - List rules
- [ ] `~/.raxe/logs/raxe.log` - Check logs
- [ ] `raxe scan "text" --verbose` - Enable verbose
- [ ] `raxe plugins` - List plugins

---

## Next Steps

### For Understanding the Code
1. Read QUICK_REFERENCE.md for overview
2. Read ARCHITECTURE_MAP.md for deep dive
3. Look at examples/ for usage patterns
4. Study tests/ for behavior validation

### For Extending the System
1. Create custom DetectorPlugin in ~/.raxe/plugins/
2. Define plugin metadata and config
3. Implement detect() method
4. Enable in config.yaml

### For Integration
1. Use Raxe() class directly in your app
2. Or use @raxe.protect decorator
3. Or use RaxeOpenAI wrapper
4. Or integrate with LangChain/HuggingFace

---

## Key Takeaways

1. **Single Entry Point**: All paths lead to `Raxe.scan()`
2. **Clean Architecture**: Domain → Application → Infrastructure
3. **Privacy-First**: No prompts stored, PII redacted, no secrets transmitted
4. **Performant**: <10ms P95, optimized preloading
5. **Extensible**: Rich plugin system with error isolation
6. **Developer-Friendly**: 5 interfaces for different use cases
7. **Well-Documented**: Code is self-documenting with clear abstractions
8. **Configuration-Driven**: Environment > File > Defaults

---

## Files in This Exploration

- **ARCHITECTURE_MAP.md** - 1,261 lines, comprehensive guide
- **QUICK_REFERENCE.md** - 400 lines, quick lookup
- **ARCHITECTURE_DIAGRAM.txt** - ASCII visual representation
- **CODEBASE_EXPLORATION_SUMMARY.md** - This file (overview)

**Total Documentation**: 2,000+ lines of detailed guides and references

---

*Exploration completed: November 16, 2024*  
*RAXE Version: 0.0.2*  
*Python: 3.10+*  
*Architecture: Clean Architecture (Domain → Application → Infrastructure)*
