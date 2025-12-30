# Changelog

All notable changes to RAXE Community Edition will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.4.0] - 2025-12-30

### Agentic Framework Integrations

This release adds first-class support for the most popular agentic AI frameworks, enabling automatic security scanning for multi-agent systems, RAG pipelines, and AI gateways.

#### Added

- **LangChain Integration** (`RaxeCallbackHandler`)
  - Automatic scanning of prompts and responses through LangChain callbacks
  - Support for chains, agents, and RAG pipelines
  - Tool policy enforcement with `ToolPolicy.block_tools()`
  - Blocking mode with `block_on_prompt_threats=True`

- **CrewAI Integration** (`RaxeCrewGuard`)
  - Step and task callbacks for multi-agent workflows
  - Automatic tool wrapping with `guard.wrap_tools()`
  - Configurable scan modes: `LOG_ONLY`, `BLOCK_ON_THREAT`, `BLOCK_ON_HIGH`, `BLOCK_ON_CRITICAL`
  - Agent thought and task output scanning

- **AutoGen Integration** (`RaxeConversationGuard`)
  - Hook-based interception for AutoGen conversations
  - Support for GroupChat and multi-agent scenarios
  - Agent registration with `guard.register(agent)`
  - Configurable via `AgentScannerConfig`

- **LlamaIndex Integration** (`RaxeLlamaIndexCallback`)
  - Callback and instrumentation API support
  - Specialized handlers: `RaxeQueryEngineCallback`, `RaxeAgentCallback`, `RaxeSpanHandler`
  - RAG pipeline protection
  - Support for LlamaIndex 0.10+ and 0.11+

- **Portkey Integration** (`RaxePortkeyWebhook`, `RaxePortkeyGuard`)
  - Webhook guardrail for Portkey AI Gateway
  - Client-side wrapper with `guard.wrap_client()`
  - Portkey-compatible verdict response format
  - Factory functions: `create_portkey_guard()`, `create_portkey_webhook()`

- **Core AgentScanner** (`raxe.sdk.agent_scanner`)
  - Unified scanning engine for all integrations
  - `ScanMode` enum: LOG_ONLY, BLOCK_ON_THREAT, BLOCK_ON_HIGH, BLOCK_ON_CRITICAL
  - `MessageType` enum: HUMAN_INPUT, AGENT_TO_AGENT, FUNCTION_CALL, FUNCTION_RESULT
  - `ScanContext` for rich context in scans
  - `ToolPolicy` for dangerous tool blocking

- **Convenience Imports**
  - All integrations available from `raxe.sdk.integrations`
  - Example: `from raxe.sdk.integrations import RaxeCallbackHandler, RaxeCrewGuard`

#### Changed

- Default behavior is now **log-only mode** (non-blocking) for all integrations
- Blocking must be explicitly enabled for safety

#### Documentation

- Full documentation at [docs.raxe.ai/integrations](https://docs.raxe.ai/integrations)
- LangChain: [docs.raxe.ai/integrations/langchain](https://docs.raxe.ai/integrations/langchain)
- CrewAI: [docs.raxe.ai/integrations/crewai](https://docs.raxe.ai/integrations/crewai)
- AutoGen: [docs.raxe.ai/integrations/autogen](https://docs.raxe.ai/integrations/autogen)
- LlamaIndex: [docs.raxe.ai/integrations/llamaindex](https://docs.raxe.ai/integrations/llamaindex)
- Portkey: [docs.raxe.ai/integrations/portkey](https://docs.raxe.ai/integrations/portkey)

---

## [0.3.1] - 2025-12-28

### Security & Documentation

#### Security

- Fixed ReDoS vulnerability in pattern matching
- Fixed tarball path traversal vulnerability

#### Changed

- Updated README with L1/L2 detection badges
- Synced `__version__` with package version

---

## [0.2.0] - 2025-12-20

### 🛡️ Suppression System v1.0

This release introduces a comprehensive suppression system for managing false positives in your AI security workflow.

#### Added

- **YAML-based suppression configuration** (`.raxe/suppressions.yaml`)
  - Structured schema with version control
  - Required reason field for audit compliance
  - Expiration date support for time-limited suppressions
  - Wildcard patterns with family prefix validation

- **Policy action overrides**
  - `SUPPRESS` - Remove detection from results (default)
  - `FLAG` - Keep detection but mark for human review
  - `LOG` - Keep detection for metrics/logging only

- **Inline SDK suppression**
  - `raxe.scan(text, suppress=["pi-001", "jb-*"])` parameter
  - `with raxe.suppressed("pi-*", reason="Testing")` context manager
  - Thread-safe scoped suppressions

- **CLI suppression commands**
  - `raxe scan --suppress pi-001` flag
  - `raxe suppress list/add/remove/audit/stats` subcommands
  - JSON/YAML export formats

- **Security hardening**
  - Pattern length limit (256 chars)
  - Reason length limit (500 chars)
  - Maximum suppressions limit (1000)
  - Fail-closed expiration handling

- **Detection flagging**
  - `Detection.is_flagged` field for FLAG action
  - `Detection.suppression_reason` field
  - Visual `[FLAG]` indicator in CLI output

#### Changed

- Configuration location moved to `.raxe/` directory
- Bare wildcard `*` patterns are now rejected (must use family prefix like `pi-*`)

#### Deprecated

- `.raxeignore` file format (still works, will be removed in v1.0.0)

#### Security

- No bare wildcards allowed (prevents accidental full suppression)
- Pattern validation requires valid family prefix
- Audit trail for all suppression operations

---

## [0.0.1] - 2025-12-04

**Open Beta Release**

RAXE Community Edition - Production-ready, privacy-first threat detection for LLM applications. Built on transparency, not hype.

### 🛡️ Core Features

#### Advanced Policy System
- **4 Policy Actions:** ALLOW (monitor), FLAG (warn), BLOCK (enforce), LOG (silent)
- **Flexible Targeting:** Rule IDs, families, severities, confidence thresholds
- **L2 Virtual Rules:** Policy targeting for ML detections (`l2-context-manipulation`, etc.)
- **Priority-Based Resolution:** Handle complex policy conflicts (0-1000 priority scale)
- **Security Limits:** Max 100 policies per customer, priority caps enforced
- **YAML Configuration:** Clean, readable policy definitions in `.raxe/policies.yaml`

#### Detection Engine
- **460+ curated detection rules** across 7 threat families:
  - **CMD (65 rules)** - Command injection, system commands, code execution
  - **ENC (70 rules)** - Encoding/obfuscation attacks, evasion techniques
  - **HC (65 rules)** - Harmful content, toxic output, policy violations
  - **JB (77 rules)** - Jailbreak attempts, persona manipulation, DAN attacks
  - **PI (59 rules)** - Prompt injection, instruction override, system prompt extraction
  - **PII (112 rules)** - PII detection, sensitive data leakage, credential exposure
  - **RAG (12 rules)** - RAG-specific attacks, context poisoning

- **Dual-layer detection system:**
  - **L1 (Rule-based):** Pattern matching with 95%+ precision on known threats
  - **L2 (ML-based):** CPU-friendly classifier for obfuscated and novel attacks
  - Combined detection rate: **95.15%** with <0.1% false positive rate

#### Privacy-First Telemetry
- **Privacy-preserving architecture** - All scanning happens locally
- **Rich L2 metadata sharing:**
  - ✅ Model metrics (confidence, scores, processing time, version)
  - ✅ Feature names (signal quality, classification)
  - ✅ Threat classifications (SAFE, ATTACK_LIKELY, FP_LIKELY)
  - ✅ API key, prompt hash (SHA-256), performance metrics
  - ❌ NEVER raw prompts, responses, matched text, or end-user identifiers
- **Telemetry enabled by default** - Opt-out available via config
- **Zero PII transmission** - Verifiable through open source code
- **Works 100% offline** - No cloud dependency required

#### Command-Line Interface
- `raxe init` - Initialize configuration with interactive setup
- `raxe scan` - Scan text for threats with detailed explanations
- `raxe batch` - Batch scan multiple prompts from files
- `raxe repl` - Interactive scanning mode
- `raxe stats` - Usage statistics and detection trends
- `raxe rules` - Browse and search detection rules
- `raxe doctor` - System health check and diagnostics
- `raxe export` - Export scan history (JSON/CSV)

#### Python SDK
- **Simple integration:** One-line wrapper for OpenAI, Anthropic, LangChain
- **Decorator pattern:** `@raxe.protect()` for function-level protection
- **Direct scanning:** `raxe.scan(text)` for custom integrations
- **Async support:** Non-blocking telemetry with async/await patterns

#### Configuration System
- **YAML-based configuration** (`~/.raxe/config.yaml`)
- Clean, readable format aligned with detection rules
- Environment variable overrides for all settings
- Validation with helpful error messages
- Default configuration for zero-config quick start

### 📊 Performance

Production-ready performance metrics:

- **P50 latency:** 0.37ms (13x better than 5ms target)
- **P95 latency:** 0.49ms (20x better than 10ms target)
- **P99 latency:** 1.34ms (15x better than 20ms target)
- **Throughput:** ~1,200 scans/second
- **Memory usage:** ~60MB peak
- **False positive rate:** <0.1%

Optimized for production workloads with:
- Circuit breaker for reliability
- Graceful degradation under load
- Configurable performance modes (fast/balanced/thorough)
- No catastrophic backtracking (all rules REDOS-safe)

### 🔒 Security Features

- **REDOS protection:** All 460+ regex patterns validated and optimized
- **Input validation:** Comprehensive sanitization and boundary checks
- **No code execution:** Pure pattern matching, no eval/exec
- **Sandboxed ML inference:** Isolated model execution
- **Secure defaults:** Fail-safe configuration out of the box

### 🧪 Testing & Quality

Comprehensive test suite ensuring reliability:

- **5,255+ tests** with comprehensive coverage:
  - Unit tests (4,800+)
  - Integration tests (400+)
  - Golden file tests (300+) for regression prevention
- **Test coverage:** 60%+ overall, >95% on core domain layer
- **Test data:** 1,000+ benign samples + 412 threat samples
- **CI/CD:** Automated testing on every commit

### 📚 Documentation

Extensive documentation for transparency and education:

- **README.md** - Mission, vision, and quick start (streamlined)
- **FAQ.md** - Comprehensive Q&A for all user questions
- **QUICKSTART.md** - 60-second getting started guide
- **CONTRIBUTING.md** - Contribution guidelines with community values
- **docs/CUSTOM_RULES.md** - Rule contribution guide with examples
- **docs/POLICIES.md** - Complete policy system documentation
- **docs/architecture.md** - System architecture and design
- **docs/examples/** - Integration examples for popular frameworks
- **SECURITY.md** - Security policy and responsible disclosure

### 🎯 Supported Integrations

- **OpenAI** - Drop-in replacement client (`RaxeOpenAI`)
- **Anthropic** - Claude wrapper (`RaxeAnthropic`)
- **LangChain** - Callback handler for chains
- **FastAPI** - Middleware examples
- **Streamlit** - Input validation examples
- **Direct SDK** - Universal integration via `raxe.scan()`

### 🔧 Developer Experience

- **Type hints:** Full type coverage with mypy strict mode
- **Clean architecture:** Domain/Application/Infrastructure separation
- **Plugin system:** Extensible detector plugins
- **Educational focus:** Every rule includes "why" and "how to defend"
- **Transparent telemetry:** `raxe doctor` shows exactly what's sent

### 🌟 Transparency Commitments

What makes RAXE different:

- ✅ **100% open source** - MIT License, full code audit available
- ✅ **Privacy by architecture** - Provably local-first design
- ✅ **Educational documentation** - Learn how attacks work, not just block them
- ✅ **Community-driven rules** - Security researchers contribute detection logic
- ✅ **Explainable detection** - Understand exactly why something was flagged
- ✅ **No vendor lock-in** - Works 100% offline, cloud is optional
- ✅ **Honest metrics** - Real detection rates, transparent about limitations
- ✅ **No marketing hype** - Transparent capabilities and limitations

### 🎓 Example Usage

**CLI:**
```bash
# Scan for threats
raxe scan "Ignore all previous instructions"
# 🔴 THREAT DETECTED - Prompt Injection (CRITICAL)

# View statistics
raxe stats

# Browse rules
raxe rules list
```

**Python SDK:**
```python
from raxe import Raxe

raxe = Raxe()
result = raxe.scan("Ignore all previous instructions")

if result.scan_result.has_threats:
    print(f"⚠️  {result.scan_result.combined_severity} threat detected!")
```

**OpenAI Wrapper:**
```python
from raxe import RaxeOpenAI

# Drop-in replacement - automatically scans all prompts
client = RaxeOpenAI(api_key="sk-...")
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "your prompt"}]
)
# Threats are automatically blocked before reaching OpenAI
```

### 📦 Installation

```bash
# Using pip
pip install raxe

# Using uv (faster)
uv pip install raxe

# Initialize
raxe init

# Start scanning
raxe scan "your text here"
```

### 🎯 What's Next

See our [roadmap](README.md#-roadmap) for upcoming features:

- **v0.3** - Response scanning, chain-of-thought analysis, expanded PII detection
- **v1.0** - Enterprise features, custom model fine-tuning, multi-language SDKs
- **v2.0** - Auto-generated rules, adversarial testing, model drift detection

### 🙏 Acknowledgments

RAXE stands on the shoulders of giants:

- **Snort** - Inspiration for community-driven threat detection
- **OWASP** - LLM security best practices and research
- **Research Community** - Prompt injection and jailbreak research
- **Open Source Contributors** - Everyone who helped make this possible

### 📄 License

RAXE Community Edition is released under the **MIT License**.

See [LICENSE](LICENSE) for full details.

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

For detection rules, see [docs/CUSTOM_RULES.md](docs/CUSTOM_RULES.md).

## Security

Please report security vulnerabilities to security@raxe.ai

See [SECURITY.md](SECURITY.md) for our responsible disclosure policy.

## Links

- 🌐 **Website:** [raxe.ai](https://raxe.ai)
- 📖 **Documentation:** [docs.raxe.ai](https://docs.raxe.ai)
- 💬 **Slack:** [Join RAXE Slack](https://join.slack.com/t/raxeai/shared_invite/zt-3kch8c9zp-A8CMJYWQjBBpzV4KNnAQcQ)
- 🐛 **Issues:** [github.com/raxe-ai/raxe-ce/issues](https://github.com/raxe-ai/raxe-ce/issues)

---

**🛡️ Transparency over hype. Education over fear. Community over vendors.**

**RAXE: The open-source instrument panel for AI safety.**

[0.2.0]: https://github.com/raxe-ai/raxe-ce/compare/v0.0.1...v0.2.0
[0.0.1]: https://github.com/raxe-ai/raxe-ce/releases/tag/v0.0.1
