# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2025-11-17

**🎉 Initial Public Release - Transparent AI Security for Everyone**

RAXE Community Edition v0.1.0 is the first open-source, privacy-first threat detection system for LLM applications. Built on transparency, not hype.

### 🛡️ Core Features

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

#### Privacy-First Architecture
- **100% local scanning** - Prompts never leave your device
- **Optional telemetry** - Privacy-preserving (only SHA-256 hashes sent, never raw text)
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
- `raxe profile` - Performance profiling for optimization

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

- **1,383 unit tests** with >80% code coverage
- **428 golden file tests** for regression prevention
- **180+ integration tests** covering:
  - Edge cases and boundary conditions
  - Evasion techniques and obfuscation
  - False positive prevention
  - Performance benchmarks
- **Test data:** 1,000 benign samples + 412 threat samples

### 📚 Documentation

Extensive documentation for transparency and education:

- **README.md** - Quick start and overview with transparency focus
- **CONTRIBUTING.md** - Contribution guidelines with community values
- **CONTRIBUTING_RULES.md** - Rule contribution guide with examples
- **SECURITY.md** - Security policy and responsible disclosure
- **docs/quickstart.md** - 60-second getting started guide
- **docs/architecture.md** - System architecture and design
- **docs/troubleshooting.md** - Common issues and solutions
- **examples/** - Integration examples for popular frameworks

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
- ✅ **Honest metrics** - Real detection rates, published quarterly
- ✅ **No marketing hype** - Transparent capabilities and limitations

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

### 🎯 What's Next

See our [roadmap](README.md#-roadmap) for upcoming features:

- **v0.2** - Response scanning, chain-of-thought analysis, expanded PII detection
- **v1.0** - Enterprise features, policy-as-code, multi-language SDKs
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

For detection rules, see [CONTRIBUTING_RULES.md](CONTRIBUTING_RULES.md).

## Security

Please report security vulnerabilities to security@raxe.ai

See [SECURITY.md](SECURITY.md) for our responsible disclosure policy.

## Links

- 🌐 **Website:** [raxe.ai](https://raxe.ai)
- 📖 **Documentation:** [docs.raxe.ai](https://docs.raxe.ai)
- 💬 **Discord:** [discord.gg/raxe](https://discord.gg/raxe)
- 🐦 **Twitter:** [@raxe_ai](https://twitter.com/raxe_ai)
- 🐛 **Issues:** [github.com/raxe-ai/raxe-ce/issues](https://github.com/raxe-ai/raxe-ce/issues)

---

**🛡️ Transparency over hype. Education over fear. Community over vendors.**

**RAXE: The open-source instrument panel for AI safety.**

[0.1.0]: https://github.com/raxe-ai/raxe-ce/releases/tag/v0.1.0
