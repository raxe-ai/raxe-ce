# RAXE CE - Complete Architecture Map

## 1. Overall Project Structure

```
raxe-ce/
├── src/raxe/
│   ├── __init__.py                    # PUBLIC API: Raxe, Detection, ScanResult, Severity
│   │
│   ├── cli/                           # Command-line interface (Click-based)
│   │   ├── main.py                    # CLI entry point with all commands
│   │   ├── output.py                  # Rich formatting for terminal output
│   │   ├── config.py, doctor.py, rules.py, stats.py, etc.
│   │   └── branding.py                # Logo and styling
│   │
│   ├── sdk/                           # Python SDK (PRIMARY USER INTERFACE)
│   │   ├── client.py                  # Raxe() - Main client (single entry point for all)
│   │   ├── decorator.py               # @raxe.protect decorator pattern
│   │   ├── wrappers/                  # LLM client wrappers (OpenAI, Anthropic, VertexAI)
│   │   ├── integrations/              # Framework integrations (LangChain, HuggingFace)
│   │   └── exceptions.py              # RaxeException, SecurityException, RaxeBlockedError
│   │
│   ├── domain/                        # Pure business logic (NO I/O allowed)
│   │   ├── models.py                  # Core domain objects (Severity, BlockAction, ScanPolicy)
│   │   ├── engine/
│   │   │   ├── executor.py            # RuleExecutor - matches rules against text
│   │   │   ├── matcher.py             # PatternMatcher - regex matching
│   │   │   └── Detection, ScanResult   # Immutable value objects
│   │   ├── rules/
│   │   │   ├── models.py              # Rule, Pattern, Severity, RuleFamily
│   │   │   ├── custom.py              # Custom rule loading
│   │   │   └── schema.py              # Rule YAML validation
│   │   ├── ml/
│   │   │   ├── protocol.py            # L2Detector protocol
│   │   │   ├── stub_detector.py       # No-op detector for testing
│   │   │   ├── production_detector.py # ML model wrapper
│   │   │   └── enhanced_detector.py   # Optimized version
│   │   ├── policies/
│   │   │   └── models.py              # ScanPolicy
│   │   ├── packs/
│   │   │   └── models.py              # Pack metadata
│   │   ├── analytics/                 # Gamification (achievements, streaks, retention)
│   │   └── telemetry/
│   │       └── event_creator.py       # Privacy-preserving event creation
│   │
│   ├── application/                   # Use cases and orchestration
│   │   ├── scan_pipeline.py           # ScanPipeline - complete scan workflow
│   │   ├── preloader.py               # One-time startup optimization
│   │   ├── scan_merger.py             # Merge L1+L2 results
│   │   ├── apply_policy.py            # Policy evaluation
│   │   ├── telemetry_manager.py       # Telemetry orchestration
│   │   ├── lazy_l2.py                 # Lazy ML detector loading
│   │   └── analytics/                 # Statistics services
│   │
│   ├── infrastructure/                # I/O implementations (database, API, files)
│   │   ├── config/
│   │   │   ├── scan_config.py         # ScanConfig - YAML loading
│   │   │   └── toml_config.py         # TOML config support
│   │   ├── database/
│   │   │   ├── connection.py          # SQLite connection pool
│   │   │   ├── models.py              # ORM models
│   │   │   └── scan_history.py        # Scan history persistence
│   │   ├── packs/
│   │   │   ├── registry.py            # PackRegistry - loads all packs
│   │   │   ├── loader.py              # Pack file loading
│   │   │   └── yaml_loader.py         # YAML rule parsing
│   │   ├── rules/
│   │   │   ├── yaml_loader.py         # Load rules from YAML
│   │   │   ├── custom_loader.py       # Load custom rules
│   │   │   └── versioning.py          # Rule version management
│   │   ├── policies/
│   │   │   ├── yaml_loader.py         # Load policies from YAML
│   │   │   ├── api_client.py          # Cloud policy sync
│   │   │   └── validator.py           # Policy validation
│   │   ├── telemetry/
│   │   │   ├── config.py              # TelemetryConfig
│   │   │   ├── sender.py              # Async telemetry sending
│   │   │   ├── queue.py               # Event queue
│   │   │   ├── hook.py                # TelemetryHook
│   │   │   └── dual_sender.py         # Batching + async
│   │   ├── tracking/
│   │   │   └── usage.py               # UsageTracker - install.json, usage.json
│   │   ├── analytics/
│   │   │   ├── engine.py              # Analytics computation
│   │   │   ├── repository.py          # Query analytics
│   │   │   ├── streaks.py             # Streak tracking
│   │   │   ├── views.py               # Aggregated views
│   │   │   └── aggregator.py          # Result aggregation
│   │   ├── security/
│   │   │   ├── auth.py                # Authentication
│   │   │   ├── signatures.py          # API signature verification
│   │   │   └── policy_validator.py    # Policy signature checking
│   │   ├── schemas/
│   │   │   ├── validator.py           # Runtime validation
│   │   │   └── middleware.py          # Validation middleware
│   │   └── cloud/                     # Cloud integration
│   │
│   ├── plugins/                       # Plugin architecture
│   │   ├── protocol.py                # RaxePlugin, DetectorPlugin, ActionPlugin, TransformPlugin
│   │   ├── manager.py                 # PluginManager - lifecycle and execution
│   │   ├── loader.py                  # PluginLoader - discovery and loading
│   │   └── custom_rules.py            # Custom rules plugin support
│   │
│   ├── packs/                         # Bundled rule packs
│   │   └── core/
│   │       ├── prompt_injection/      # Prompt injection rules
│   │       ├── jailbreak/             # Jailbreak patterns
│   │       ├── pii/                   # PII detection
│   │       └── ...
│   │
│   ├── utils/                         # Utilities
│   │   ├── logging.py                 # Structured logging (structlog)
│   │   ├── error_sanitizer.py         # Error message sanitization
│   │   ├── validators.py              # Input validation
│   │   ├── profiler.py                # Performance profiling
│   │   └── performance.py             # Performance config
│   │
│   ├── monitoring/                    # Runtime monitoring
│   │   ├── metrics.py                 # Prometheus metrics
│   │   ├── profiler.py                # Performance profiling
│   │   └── server.py                  # Metrics HTTP server
│   │
│   ├── async_sdk/                     # Async versions (for async/await usage)
│   │   ├── client.py                  # AsyncRaxe client
│   │   └── wrappers/                  # Async wrappers
│   │
│   └── application/
│       └── ab_testing.py              # A/B testing framework
│
└── examples/                           # Usage examples
    ├── basic_scan.py                  # Simplest usage
    ├── decorator_usage.py             # @raxe.protect examples
    ├── layer_control_usage.py         # L1/L2 control
    ├── async_usage.py                 # Async/await patterns
    ├── plugins/                       # Plugin examples
    │   ├── custom_detector/           # Custom regex detector
    │   ├── slack_notifier/            # Action plugin (send alerts)
    │   ├── file_logger/               # Log to file plugin
    │   └── webhook/                   # Webhook plugin
    ├── langchain_integration/         # LangChain integration
    ├── fastapi_integration/           # FastAPI integration
    ├── flask_integration/             # Flask integration
    ├── django_integration/            # Django integration
    └── ...
```

---

## 2. The Unified Scanning System: How Data Flows

### Entry Point: Single Raxe Client
All operations eventually call `Raxe.scan()` - the ONLY scanning method:

```
┌─ CLI Commands                           ┌─ SDK Direct Usage
│  $ raxe scan "text"     ─────────────>  │  raxe = Raxe()
│                                         │  result = raxe.scan(text)
│
├─ Decorators                            ├─ LLM Wrappers
│  @raxe.protect          ─────────────>  │  client = raxe.wrap(OpenAI())
│  def func(prompt):                     │  response = client.chat.create(...)
│
└─ Framework Integrations                └─ ALL PATHS
   LangChain, HuggingFace ──────────────>     │
                                              ↓
                                    Raxe.scan(text) {
                                       1. Validate input
                                       2. Run pipeline
                                       3. Track usage
                                       4. Return result
                                    }
```

### Complete Scan Pipeline Flow

```
Text Input
    │
    ├─ → PreloadStats (one-time at init)
    │     ├─ Load config
    │     ├─ Load rule packs
    │     ├─ Compile regex patterns
    │     └─ Warm up L2 detector
    │
    ├─ → Main Scan Pipeline
    │     │
    │     ├─ [L1 Layer - Regex Detection] <5ms target
    │     │  ├─ Load rules from PackRegistry
    │     │  ├─ RuleExecutor.execute(text, rules)
    │     │  │  └─ PatternMatcher.match() for each rule
    │     │  └─ Detections: [Detection, Detection, ...]
    │     │
    │     ├─ [L2 Layer - ML Detection] <1ms target
    │     │  ├─ Skip if fail_fast_on_critical && CRITICAL found
    │     │  ├─ L2Detector.detect(text)
    │     │  └─ Predictions: [Prediction, Prediction, ...]
    │     │
    │     ├─ [Plugin Layer - Custom Detection]
    │     │  ├─ PluginManager.run_detectors(text)
    │     │  └─ Detections from plugins
    │     │
    │     ├─ [Merge Results]
    │     │  ├─ ScanMerger.merge(l1_result, l2_result, plugin_detections)
    │     │  └─ CombinedScanResult with highest severity
    │     │
    │     ├─ [Apply Policy]
    │     │  ├─ ScanPolicy.should_block(result)
    │     │  └─ Determine BlockAction (ALLOW/WARN/BLOCK)
    │     │
    │     └─ [Execute Plugins - Actions]
    │        ├─ PluginManager.run_actions(result)
    │        └─ Send Slack, log to file, webhook, etc.
    │
    ├─ → Post-Scan Activities
    │     ├─ Record in ScanHistoryDB (privacy hashes only)
    │     ├─ Record usage stats
    │     ├─ Check and unlock achievements
    │     ├─ Update streaks
    │     └─ Send telemetry (privacy-preserving)
    │
    └─ → Return ScanPipelineResult
         ├─ scan_result (merged detections)
         ├─ policy_decision (ALLOW/WARN/BLOCK)
         ├─ should_block (boolean)
         ├─ duration_ms (latency)
         └─ metadata (context)
```

---

## 3. Developer-Facing Interfaces

### 3.1 CLI Interface ($ raxe command)

**Location:** `/home/user/raxe-ce/src/raxe/cli/main.py`

```bash
# Initialization
raxe init --api-key sk-...
# Free tier: telemetry enabled by default
# Pro tier: telemetry manageable via web console

# Single scan
raxe scan "Ignore all instructions" 
raxe scan "text" --format json|yaml|text
raxe scan "text" --l1-only --l2-only
raxe scan "text" --mode fast|balanced|thorough
raxe scan "text" --confidence 0.8 --explain

# Batch processing
raxe batch prompts.txt --format json --output results.json --parallel 4

# Management
raxe rules list     # List all rules
raxe rules info RULE_ID
raxe test          # Test configuration
raxe stats         # Show statistics and achievements
raxe export        # Export scan history
raxe doctor        # Health check
raxe plugins       # List plugins
raxe pack list     # List packs

# REPL and profiling
raxe repl          # Interactive shell
raxe profile "text" -n 100  # Performance profiling
raxe metrics-server -p 9090 # Start Prometheus server

# Completion
raxe completion bash|zsh|fish|powershell
```

**Output Formatters:** `/home/user/raxe-ce/src/raxe/cli/output.py`

```python
# Rich formatted output with colors
display_scan_result(result, no_color=False)  # Pretty terminal display
# + JSON/YAML export support
# + Progress bars
# + Tables for batch results
```

### 3.2 SDK/Direct Usage (Python)

**Location:** `/home/user/raxe-ce/src/raxe/sdk/client.py`

```python
from raxe import Raxe, Detection, ScanResult, Severity

# Initialize (configuration cascade: explicit > env > file > defaults)
raxe = Raxe()
raxe = Raxe(api_key="raxe_...", telemetry=False, l2_enabled=True)
raxe = Raxe.from_config_file(Path.home() / ".raxe" / "config.yaml")

# Core scanning methods
result = raxe.scan(text)                           # Balanced mode
result = raxe.scan_fast(text)                      # L1 only, <3ms
result = raxe.scan_thorough(text)                  # All layers, <100ms
result = raxe.scan_high_confidence(text, 0.8)    # High confidence only

# Advanced parameters
result = raxe.scan(
    text,
    mode="fast|balanced|thorough",
    l1_enabled=True,
    l2_enabled=True,
    confidence_threshold=0.5,
    explain=True,
    block_on_threat=False,
    customer_id="customer123",
    context={"user_id": "user1", "session": "sess1"}
)

# Check results
if result.has_threats:
    print(f"Severity: {result.severity}")  # "critical", "high", "medium", "low"
    print(f"Detections: {result.total_detections}")
    for detection in result.scan_result.l1_result.detections:
        print(f"  {detection.rule_id}: {detection.message}")

# Blocking on threat
try:
    raxe.scan(text, block_on_threat=True)
except SecurityException as e:
    print(f"Blocked: {e.result.severity}")
```

### 3.3 Decorator Pattern

**Location:** `/home/user/raxe-ce/src/raxe/sdk/decorator.py`

```python
from raxe import Raxe

raxe = Raxe()

# Basic - blocks by default
@raxe.protect
def generate(prompt: str) -> str:
    return llm.generate(prompt)

# Async function protection
@raxe.protect
async def async_generate(prompt: str) -> str:
    return await llm.generate_async(prompt)

# Customized
@raxe.protect(block=False)                    # Monitoring mode
def monitor_function(prompt: str) -> str:
    return process(prompt)

@raxe.protect(on_threat=lambda r: log.warn(r))  # Custom callback
def custom_handler(prompt: str) -> str:
    return process(prompt)

@raxe.protect(allow_severity=["LOW"])         # Allow low severity
def permissive(prompt: str) -> str:
    return process(prompt)

# Extracted from function arguments
@raxe.protect
def func1(prompt: str): ...              # First string arg

@raxe.protect
def func2(text: str): ...                # Common param names

@raxe.protect
def func3(content: str): ...

@raxe.protect
def func4(messages: list[dict]): ...     # OpenAI style - messages[-1]["content"]
```

### 3.4 LLM Client Wrappers

**Location:** `/home/user/raxe-ce/src/raxe/sdk/wrappers/`

```python
# OpenAI
from raxe import RaxeOpenAI

client = RaxeOpenAI(api_key="sk-...")
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)  # Scanned automatically

# Anthropic
from raxe import RaxeAnthropic

client = RaxeAnthropic(api_key="sk-...")
response = client.messages.create(
    model="claude-3",
    messages=[{"role": "user", "content": "Hello"}]
)  # Scanned automatically

# Runtime wrapping
from openai import OpenAI

raxe = Raxe()
original = OpenAI(api_key="sk-...")
client = raxe.wrap(original)  # Wraps with scanning
```

### 3.5 Framework Integrations

**Location:** `/home/user/raxe-ce/src/raxe/sdk/integrations/`

```python
# LangChain
from raxe.sdk.integrations import RaxeCallbackHandler

callback = RaxeCallbackHandler(raxe=raxe)
chain.invoke(input, config={"callbacks": [callback]})

# HuggingFace
from raxe.sdk.integrations import RaxePipeline

pipe = RaxePipeline(
    model="mistral",
    raxe=raxe,
    device="cuda"
)
result = pipe("Your prompt here")
```

---

## 4. Domain Layer - Pure Business Logic

**No I/O operations allowed in domain layer.**

### Core Domain Models

**Location:** `/home/user/raxe-ce/src/raxe/domain/models.py`

```python
# Enums
class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class BlockAction(Enum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    BLOCK = "BLOCK"
    CHALLENGE = "CHALLENGE"

# Value Objects
@dataclass(frozen=True)
class ScanRequest:
    text: str
    context: dict[str, str] | None = None
    rule_filters: list[str] | None = None

@dataclass(frozen=True)
class ScanPolicy:
    block_on_critical: bool = True
    block_on_high: bool = False
    allow_on_low_confidence: bool = True
    confidence_threshold: float = 0.7
    
    def should_block(self, result: ScanResult) -> bool:
        # Policy logic - no I/O
        ...

# Detection Result
@dataclass(frozen=True)
class Detection:
    rule_id: str
    severity: Severity
    confidence: float  # 0.0-1.0
    matches: list[Match]
    detected_at: str  # ISO timestamp
    message: str
    explanation: str | None = None
    detection_layer: str = "L1"  # L1, L2, or PLUGIN

@dataclass(frozen=True)
class ScanResult:
    detections: list[Detection]
    scanned_at: str
    text_length: int
    rules_checked: int
    scan_duration_ms: float
    
    @property
    def has_detections(self) -> bool: ...
    @property
    def highest_severity(self) -> Severity | None: ...
```

### Rule Engine

**Location:** `/home/user/raxe-ce/src/raxe/domain/engine/executor.py`

```python
class RuleExecutor:
    """Stateless rule executor - pure function on steroids."""
    
    def execute(
        self,
        text: str,
        rules: list[Rule],
        timeout_seconds: float = 5.0
    ) -> ScanResult:
        """Execute rules against text - side effect free."""
        # 1. Compile patterns (cached)
        # 2. Match each rule
        # 3. Aggregate detections
        # 4. Return ScanResult
        
        # Performance target: <5ms for typical prompts
        ...

class PatternMatcher:
    """Low-level regex pattern matching with timeout protection."""
    
    def match(
        self,
        pattern: RePattern[str],
        text: str,
        timeout_seconds: float = 5.0
    ) -> list[Match]:
        """Find all matches with timeout."""
        ...
```

### Rule Models

**Location:** `/home/user/raxe-ce/src/raxe/domain/rules/models.py`

```python
class RuleFamily(Enum):
    PI = "PI"           # Prompt Injection
    JB = "JB"           # Jailbreak
    PII = "PII"         # PII/Data Leak
    CMD = "CMD"         # Command Injection
    ENC = "ENC"         # Encoding/Obfuscation
    RAG = "RAG"         # RAG-specific
    HC = "HC"           # Harmful Content
    SEC = "SEC"         # Security
    QUAL = "QUAL"       # Quality
    CUSTOM = "CUSTOM"   # User-defined

@dataclass(frozen=True)
class Pattern:
    """A single regex pattern."""
    pattern: str
    flags: list[str] = field(default_factory=list)
    timeout: float = 5.0
    
    def compile(self) -> RePattern[str]:
        """Compile pattern with flags - pure operation."""
        ...

@dataclass(frozen=True)
class Rule:
    """A complete threat detection rule."""
    id: str                         # "pi-001"
    version: str                    # "1.0.0"
    family: RuleFamily              # PI, JB, etc.
    severity: Severity              # Critical, High, etc.
    patterns: list[Pattern]         # Multiple regex patterns
    message: str                    # Human-readable message
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.9         # Default confidence
```

---

## 5. Application Layer - Orchestration

**Location:** `/home/user/raxe-ce/src/raxe/application/`

### Scan Pipeline Orchestrator

**Location:** `/home/user/raxe-ce/src/raxe/application/scan_pipeline.py`

```python
class ScanPipeline:
    """Complete scan workflow orchestrator."""
    
    def scan(
        self,
        text: str,
        customer_id: str | None = None,
        context: dict | None = None,
        l1_enabled: bool = True,
        l2_enabled: bool = True,
        mode: str = "balanced",
        confidence_threshold: float = 0.5,
        explain: bool = False,
    ) -> ScanPipelineResult:
        """Main orchestration method."""
        
        # 1. L1 Rule-based detection
        l1_result = self.rule_executor.execute(text, rules)
        
        # 2. Check fail-fast optimization
        if self.config.fail_fast_on_critical:
            if l1_result.highest_severity == Severity.CRITICAL:
                if l1_result.detections[0].confidence >= min_confidence_for_skip:
                    l2_enabled = False  # Skip L2 when certain
        
        # 3. L2 ML detection
        l2_result = None
        if l2_enabled and self.l2_detector:
            l2_result = self.l2_detector.detect(text, context)
        
        # 4. Merge results
        merged = self.scan_merger.merge(l1_result, l2_result, plugin_detections)
        
        # 5. Apply policy
        policy_decision = self.policy.get_action(merged)
        
        # 6. Execute plugins
        self.plugin_manager.run_actions(result)
        
        # 7. Return complete result
        return ScanPipelineResult(...)

@dataclass(frozen=True)
class ScanPipelineResult:
    scan_result: CombinedScanResult
    policy_decision: BlockAction
    should_block: bool
    duration_ms: float
    text_hash: str                   # SHA256 (privacy-preserving)
    metadata: dict[str, object]
    l1_detections: int = 0
    l2_detections: int = 0
    plugin_detections: int = 0
```

### Pipeline Preloader

**Location:** `/home/user/raxe-ce/src/raxe/application/preloader.py`

```python
def preload_pipeline(config: ScanConfig) -> tuple[ScanPipeline, PreloadStats]:
    """One-time startup optimization."""
    
    # 1. Load config
    # 2. Load all rule packs
    # 3. Compile regex patterns
    # 4. Warm up L2 detector
    # 5. Initialize plugin manager
    # 6. Return optimized pipeline + stats
    
    # Performance: ~100-200ms one-time cost
    # Benefit: -5-10ms per scan thereafter
```

---

## 6. Infrastructure Layer - I/O Implementations

### Configuration

**Location:** `/home/user/raxe-ce/src/raxe/infrastructure/config/`

```python
class ScanConfig:
    """Complete configuration hierarchy."""
    
    packs_root: Path = ~/.raxe/packs
    enable_l2: bool = True
    use_production_l2: bool = True
    l2_confidence_threshold: float = 0.5
    fail_fast_on_critical: bool = True
    
    policy: ScanPolicy                 # Policy config
    performance: PerformanceConfig     # Perf tuning
    telemetry: TelemetryConfig        # Telemetry settings
    api_key: str | None
    customer_id: str | None
    
    @classmethod
    def from_file(cls, path: Path) -> "ScanConfig":
        """Load from ~/.raxe/config.yaml"""
        ...
    
    @classmethod
    def from_env(cls) -> "ScanConfig":
        """Load from environment variables"""
        ...
```

### Pack Registry

**Location:** `/home/user/raxe-ce/src/raxe/infrastructure/packs/registry.py`

```python
class PackRegistry:
    """Loads and indexes all rule packs."""
    
    def __init__(self, config: RegistryConfig):
        # Loads bundled core packs
        # Loads custom packs from ~/.raxe/packs/custom/
        # Loads community packs from ~/.raxe/packs/community/
        # Resolves pack precedence: custom > community > core
        
    def get_all_rules(self) -> list[Rule]:
        """All rules from all packs."""
        
    def list_packs(self) -> list[str]:
        """Installed pack names."""
```

### Scan History Database

**Location:** `/home/user/raxe-ce/src/raxe/infrastructure/database/scan_history.py`

```python
class ScanHistoryDB:
    """SQLite-based scan history persistence."""
    
    def record_scan(
        self,
        prompt: str,
        detections: list[Detection],
        l1_duration_ms: float,
        l2_duration_ms: float | None = None,
        version: str = "1.0.0"
    ) -> None:
        """Record scan with privacy: text_hash instead of actual text."""
        # Stores: timestamp, text_hash, detection_count, severity, duration
        # NO actual prompts stored
```

### Telemetry System

**Location:** `/home/user/raxe-ce/src/raxe/infrastructure/telemetry/`

```python
class TelemetryManager:
    """Privacy-preserving event tracking."""
    
    def send_event(
        self,
        event_type: str,
        data: dict[str, Any]
    ) -> None:
        """Queue event for async sending."""
        # Never sends: prompts, responses, secrets
        # Sends: aggregated stats, hashes, latencies
```

---

## 7. Plugin Architecture

**Location:** `/home/user/raxe-ce/src/raxe/plugins/`

### Plugin Types

```python
class RaxePlugin(Protocol):
    """Base plugin with lifecycle hooks."""
    
    @property
    def metadata(self) -> PluginMetadata: ...
    
    def on_init(self, config: dict[str, Any]) -> None:
        """Called once at plugin load."""
        
    def on_scan_start(self, text: str, context: dict | None = None) -> str | None:
        """Pre-scan hook - can transform input."""
        
    def on_scan_complete(self, result: ScanPipelineResult) -> None:
        """Post-scan hook - read-only."""
        
    def on_threat_detected(self, result: ScanPipelineResult) -> None:
        """Called only if threats found."""
        
    def on_shutdown(self) -> None:
        """Cleanup on shutdown."""

class DetectorPlugin(RaxePlugin):
    """Custom threat detector."""
    
    def detect(
        self,
        text: str,
        context: dict[str, Any] | None = None
    ) -> list[Detection]:
        """Return detections from custom logic."""

class ActionPlugin(RaxePlugin):
    """Post-scan action executor."""
    
    def should_execute(self, result: ScanPipelineResult) -> bool:
        """Check if action should run."""
        
    def execute(self, result: ScanPipelineResult) -> None:
        """Execute action (send Slack, log, etc.)."""

class TransformPlugin(RaxePlugin):
    """Input/output transformer."""
    
    def transform_input(self, text: str, context: dict | None = None) -> str:
        """Pre-scan transformation."""
        
    def transform_output(self, result: ScanPipelineResult) -> ScanPipelineResult:
        """Post-scan transformation."""
```

### Plugin Lifecycle & Manager

```python
class PluginManager:
    """Manages plugin execution with error isolation."""
    
    def initialize(
        self,
        enabled_plugins: list[str],
        plugin_configs: dict[str, dict[str, Any]]
    ) -> None:
        """Load and categorize plugins."""
        
    def execute_hook(self, hook_name: str, *args, **kwargs) -> list[Any]:
        """Execute hook on all plugins in priority order."""
        # Error isolation: one plugin failure doesn't crash others
        # Timeout enforcement: 5 seconds default
        # Metrics tracking: success rate, duration, errors
        
    def run_detectors(self, text: str) -> list[Detection]:
        """Run all detector plugins."""
        
    def run_actions(self, result: ScanPipelineResult) -> None:
        """Run action plugins."""
        
    def shutdown(self) -> None:
        """Graceful shutdown in reverse order."""

@dataclass
class PluginMetadata:
    name: str                   # "slack_notifier"
    version: str                # "1.0.0"
    author: str                 # Plugin author
    description: str            # Description
    priority: PluginPriority    # CRITICAL, HIGH, NORMAL, LOW
    requires: tuple[str, ...]   # ["raxe>=1.0.0"]
    tags: tuple[str, ...]       # ["action", "notification"]
```

### Plugin Examples

See `/home/user/raxe-ce/examples/plugins/`:

1. **custom_detector/plugin.py** - Custom regex patterns
   ```python
   class CustomRegexDetector(DetectorPlugin):
       def detect(self, text: str, context=None) -> list[Detection]:
           # User-defined patterns loaded from config.toml
   ```

2. **slack_notifier/plugin.py** - Send alerts to Slack
   ```python
   class SlackNotifierPlugin(ActionPlugin):
       def should_execute(self, result) -> bool:
           return result.has_threats and result.severity in ["HIGH", "CRITICAL"]
       
       def execute(self, result) -> None:
           # Send formatted message to Slack webhook
   ```

3. **file_logger/plugin.py** - Log to file
4. **webhook/plugin.py** - Send to webhook

---

## 8. Output & Formatting Mechanisms

**Location:** `/home/user/raxe-ce/src/raxe/cli/output.py`

### Display Formatters

```python
console = Console()  # Rich terminal console

SEVERITY_COLORS = {
    Severity.CRITICAL: "red bold",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "blue",
}

SEVERITY_ICONS = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🔵",
}

# Beautiful terminal output
display_scan_result(result, no_color=False)
# Outputs:
#   🔴 THREAT DETECTED
#   ┌─────────────────────────────────────────┐
#   │ Rule        │ Severity │ Confidence │ Message
#   │ pi-001      │ CRITICAL │    0.95    │ Prompt injection detected
#   │ jb-005      │   HIGH   │    0.82    │ Jailbreak attempt
#   └─────────────────────────────────────────┘
#   Summary: 2 detections • Severity: CRITICAL • Scan time: 4.23ms

# Export formats
- JSON: `{"has_detections": true, "detections": [...], ...}`
- YAML: YAML formatted output
- Text: Rich terminal output
- CSV: For batch operations
```

---

## 9. Logging System

**Location:** `/home/user/raxe-ce/src/raxe/utils/logging.py`

### Structured Logging with Privacy

```python
from raxe.utils.logging import get_logger

logger = get_logger(__name__)

# Structured logging (no PII allowed)
logger.info(
    "scan_completed",
    prompt_hash="sha256:abc123...",  # Hash, not actual prompt
    detection_count=3,
    severity="high",
    duration_ms=4.2,
    l1_enabled=True,
    l2_enabled=True
)

# Auto-redaction processor
# Redacts keys: prompt, response, api_key, password, token, secret
# Redacts long alphanumeric strings (likely API keys)

# Multiple handlers:
# - Console: Colored, human-readable (dev mode)
# - File: JSON structured logs, rotated (10MB, keep 5)

# Environment variables
RAXE_LOG_LEVEL = "INFO"
RAXE_ENABLE_FILE_LOGGING = "true"
RAXE_ENABLE_CONSOLE_LOGGING = "false"  # Off by default in CLI
```

---

## 10. Configuration Systems

### Config Files

```yaml
# ~/.raxe/config.yaml
version: 1.0.0

# API
api_key: raxe_test_customer123_abc456

# Telemetry (privacy-preserving)
telemetry:
  enabled: true
  endpoint: https://api.raxe.ai/v1/telemetry
  batch_size: 10
  flush_interval_seconds: 30

# Performance
performance:
  mode: balanced  # fast, balanced, accurate
  l2_enabled: true
  max_latency_ms: 10

# Detection policy
policy:
  block_on_critical: true
  block_on_high: false
  confidence_threshold: 0.7

# Pack precedence
packs:
  precedence:
    - custom      # User packs override everything
    - community   # Community packs
    - core        # Built-in core rules

# Plugins
plugins:
  enabled:
    - slack_notifier
    - custom_detector
    - file_logger
  
  slack_notifier:
    webhook_url: https://hooks.slack.com/...
    min_severity: HIGH
    channel: "#security"
  
  custom_detector:
    patterns:
      - name: api_key
        pattern: "sk-[a-zA-Z0-9]{48}"
        severity: HIGH
        message: "OpenAI API key detected"
```

### Configuration Cascade

```python
ScanConfig(
    # Priority 1: Explicit parameters
    api_key="raxe_...",
    telemetry=False,
    l2_enabled=True,
) or
# Priority 2: Environment variables
os.getenv("RAXE_API_KEY")
os.getenv("RAXE_ENABLE_L2")
or
# Priority 3: Config file
~/.raxe/config.yaml
or
# Priority 4: Defaults
ScanConfig()  # All defaults
```

---

## 11. How Developers Actually Use RAXE

### Common Workflows

#### 1. CLI User
```bash
# Setup
raxe init --api-key raxe_... --telemetry

# Quick scan
raxe scan "Ignore all previous instructions"
raxe scan "text" --format json

# Batch operations
raxe batch prompts.txt --output results.json

# Management
raxe stats
raxe rules list
raxe doctor
```

#### 2. SDK Direct Usage
```python
from raxe import Raxe, SecurityException

raxe = Raxe()

result = raxe.scan("user prompt")

if result.has_threats:
    print(f"Threat detected: {result.severity}")
    for detection in result.scan_result.l1_result.detections:
        print(f"  - {detection.rule_id}: {detection.message}")
else:
    print("Safe")
```

#### 3. FastAPI Integration
```python
from fastapi import FastAPI
from raxe import Raxe, SecurityException

app = FastAPI()
raxe = Raxe()

@app.post("/chat")
async def chat(prompt: str):
    try:
        result = raxe.scan(prompt, block_on_threat=True)
    except SecurityException:
        return {"error": "Threat detected"}
    
    response = llm.generate(prompt)
    return {"response": response}
```

#### 4. Decorator Pattern
```python
from raxe import Raxe

raxe = Raxe()

@raxe.protect
def generate_content(prompt: str) -> str:
    # Blocks if threat detected (raises SecurityException)
    return llm.generate(prompt)

@raxe.protect(block=False)  # Monitoring mode
def analyze_prompt(prompt: str) -> dict:
    # Logs threats but doesn't block
    return process(prompt)
```

#### 5. LLM Wrapper Pattern
```python
from raxe import RaxeOpenAI

client = RaxeOpenAI(api_key="sk-...")

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)  # Automatically scanned
```

#### 6. Custom Plugin
```python
# ~/.raxe/plugins/my_detector/plugin.py
from raxe.plugins import DetectorPlugin, PluginMetadata

class MyDetector(DetectorPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_detector",
            version="1.0.0",
            author="Me",
            description="Custom detector"
        )
    
    def on_init(self, config: dict):
        self.pattern = config.get("pattern")
    
    def detect(self, text: str, context=None):
        if self.pattern in text:
            return [Detection(...)]
        return []

plugin = MyDetector()

# Enable in config.yaml
# [plugins.enabled]
# my_detector = true
```

---

## 12. Key Data Flows & Sequences

### Scan Request Flow
```
User Input → Raxe.scan() → Pipeline.scan()
    ├─ L1: RuleExecutor.execute() → Detections
    ├─ L2: L2Detector.detect() → Predictions
    ├─ PLUGIN: PluginManager.run_detectors() → Detections
    ├─ MERGE: ScanMerger.merge() → CombinedScanResult
    ├─ POLICY: ScanPolicy.should_block() → BlockAction
    ├─ PLUGINS: PluginManager.run_actions()
    ├─ TRACK: UsageTracker + ScanHistoryDB
    ├─ TELEMETRY: TelemetryManager
    └─ Return: ScanPipelineResult
```

### Plugin Execution Order
```
On Scan Start:
  1. on_scan_start() [ALL plugins, priority order]
  2. transform_input() [ALL plugins, chain results]

During Scan:
  3. run_detectors() [DetectorPlugin.detect()]

On Scan Complete:
  4. on_scan_complete() [ALL plugins, read-only]

If Threats Found:
  5. on_threat_detected() [ALL plugins]

On Actions:
  6. run_actions() [ActionPlugin.execute() if should_execute()]

On Shutdown:
  7. on_shutdown() [ALL plugins, reverse order]
```

### Configuration Loading
```
Raxe.__init__()
    ├─ Explicit parameters provided?
    │   └─ Use those
    ├─ ScanConfig.from_file(config_path)?
    │   └─ Parse ~/.raxe/config.yaml
    ├─ Environment variables?
    │   └─ RAXE_* variables
    └─ Defaults
        └─ ScanConfig() defaults

Then apply specific overrides:
    ├─ api_key override
    ├─ telemetry override
    ├─ l2_enabled override
    └─ Other kwargs
```

---

## 13. Performance Optimization Strategies

### Startup Optimization (Preloader)
```
Preload Pipeline (100-200ms one-time)
├─ Load all rule packs
├─ Compile regex patterns (cached)
├─ Warm up L2 detector
└─ Initialize plugin manager

Result: Per-scan latency -5-10ms
```

### Scan-Time Optimization
```
Fail-Fast on CRITICAL
├─ IF l1_result has CRITICAL AND confidence >= threshold
│   └─ SKIP L2 detection (save 1ms)

Lazy L2 Loading
├─ Only load ML model if l2_enabled=True
└─ First call: +100ms, subsequent: <1ms

Layer Control
├─ mode="fast" → L1 only (<3ms)
├─ mode="balanced" → L1+L2 (<10ms)
├─ mode="thorough" → L1+L2+plugins (<100ms)

Confidence Filtering
├─ Set confidence_threshold to reduce false positives
└─ Higher threshold = fewer detections to process
```

---

## 14. Integration Points Summary

| Integration | Location | Use Case |
|---|---|---|
| **CLI** | `src/raxe/cli/main.py` | Command-line tool |
| **SDK Direct** | `src/raxe/sdk/client.py` | Python code |
| **Decorator** | `src/raxe/sdk/decorator.py` | Function protection |
| **Wrapper** | `src/raxe/sdk/wrappers/` | LLM clients |
| **LangChain** | `src/raxe/sdk/integrations/langchain.py` | LangChain callback |
| **HuggingFace** | `src/raxe/sdk/integrations/huggingface.py` | HF pipelines |
| **Plugins** | `src/raxe/plugins/` | Custom logic |
| **FastAPI** | `examples/fastapi_integration/` | Web framework |
| **Flask** | `examples/flask_integration/` | Web framework |
| **Django** | `examples/django_integration/` | Web framework |
| **Async** | `src/raxe/async_sdk/` | Async/await patterns |

