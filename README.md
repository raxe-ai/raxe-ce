# 🛡️ RAXE – The Instrument Panel for LLMs

[![Tests](https://github.com/raxe-ai/raxe-ce/workflows/Tests/badge.svg)](https://github.com/raxe-ai/raxe-ce/actions)
[![codecov](https://codecov.io/gh/raxe-ai/raxe-ce/branch/main/graph/badge.svg)](https://codecov.io/gh/raxe-ai/raxe-ce)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **"Snort for AI prompts"** – Real-time threat detection for your LLM applications

RAXE is a **privacy-first, developer-friendly AI security tool** that scans LLM interactions for threats like prompt injection, jailbreaks, and PII leaks—all running locally on your machine.

```
╔═══════════════════════════════╗
║   ██▀▀▀ ▄▀▀▄ ▀▄ ▄▀ ██▀▀▀      ║
║   ██▄▄  █▄▄█  ▄█▄  ██▄▄       ║
║   ██ ▀▀ █  █ ▀▀ ▀▀ ██▄▄▄      ║
║                               ║
║   AI Security Engine          ║
╚═══════════════════════════════╝
```

---

## ⚡ Quick Start (< 60 seconds)

### 1️⃣ Install

```bash
pip install raxe
```

### 2️⃣ Initialize

```bash
raxe init
```

### 3️⃣ Start Scanning

**Option A: CLI**
```bash
raxe scan "Ignore all previous instructions"
# 🔴 THREAT DETECTED - Prompt Injection (CRITICAL)
```

**Option B: Python SDK**
```python
from raxe import Raxe

raxe = Raxe()
result = raxe.scan("Your user input here")

if result.scan_result.has_threats:
    print(f"⚠️  {result.scan_result.combined_severity} threat detected!")
```

**Option C: Wrap Your OpenAI Client**
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

**That's it!** You're now protected against prompt injection, jailbreaks, and PII leaks.

---

## 🎯 What is RAXE?

RAXE gives you **real-time visibility into what's happening with your LLM applications**:

- 🕵️ **Detect threats** – Prompt injection, jailbreaks, PII leaks, toxic output
- 📊 **Track usage** – Scans, detections, trends, and streaks
- 🔒 **Privacy-first** – Everything runs locally, no PII leaves your device
- ⚡ **Fast** – <10ms scan latency, works in production
- 🧩 **Easy integration** – One line of code, works with OpenAI, Anthropic, LangChain
- 🆓 **100% Free & Open Source** – MIT license, community-driven

### Think of it as:

> **The instrument panel for your LLM application.**
> Before AGI arrives, we need to know what's happening under the hood.

---

## 🚀 Why RAXE?

**Problem:** Developers are unknowingly shipping insecure LLM applications

- ❌ Zero visibility into prompt injection attempts
- ❌ No way to track what users are asking your AI
- ❌ PII accidentally leaking into prompts
- ❌ Can't prove compliance or safety to customers
- ❌ Black-box LLM providers give you no control

**Solution:** RAXE gives you the observability layer you need

- ✅ See every threat attempt in real-time
- ✅ Block malicious prompts before they reach your LLM
- ✅ Track usage patterns and detect anomalies
- ✅ Privacy-preserving telemetry (only hashes sent to cloud)
- ✅ Community-driven detection rules that improve over time

---

## 🛡️ What RAXE Detects

RAXE uses a **dual-layer detection system**:

### L1: Rule-Based Detection (Fast & Precise)
High-confidence pattern matching for known attack types:

- ✅ **Prompt Injection** – "Ignore all previous instructions..."
- ✅ **Jailbreaks** – "You are now DAN (Do Anything Now)..."
- ✅ **PII Leaks** – Credit cards, SSNs, emails in prompts
- ✅ **Data Exfiltration** – Attempts to extract training data
- ✅ **Toxic Content** – Hate speech, violence, harassment
- ✅ **System Prompts** – Attempts to reveal your system instructions

### L2: ML-Based Detection (Smart & Adaptive)
Lightweight CPU-friendly classifier that catches:

- ✅ Obfuscated injection attempts
- ✅ Novel attack patterns
- ✅ Subtle manipulation attempts
- ✅ Context-aware anomalies

**All detection happens locally** – your data never leaves your machine unless you opt-in to telemetry.

---

## 📦 Installation & Setup

### Install RAXE

```bash
# Using pip
pip install raxe

# Using uv (faster)
uv pip install raxe
```

### Initialize Configuration

```bash
raxe init
```

This creates `~/.raxe/config.yaml` with:
- Detection rules
- Performance settings
- Optional telemetry configuration

### Test Your Setup

```bash
raxe test
```

Runs health checks to verify:
- Rules are loaded correctly
- Local scanning works
- Configuration is valid

---

## 🎨 CLI Commands

RAXE comes with a beautiful, easy-to-use CLI:

### Core Commands

```bash
raxe scan "your text"          # Scan text for threats
raxe init                      # Initialize configuration
raxe test                      # Test your setup
raxe stats                     # View usage statistics & achievements
```

### Analysis Commands

```bash
raxe batch prompts.txt         # Scan multiple prompts from file
raxe repl                      # Interactive scanning mode
raxe export                    # Export scan history to JSON/CSV
```

### Configuration Commands

```bash
raxe rules list                # List all detection rules
raxe rules show pi-001         # Show details for a specific rule
raxe doctor                    # Diagnose issues
raxe tune threshold            # Fine-tune confidence settings
```

### Advanced Commands

```bash
raxe profile "text"            # Profile scan performance
raxe --verbose                 # Enable detailed logging
raxe --help                    # Show all commands
```

---

## 🐍 Python SDK

### Basic Scanning

```python
from raxe import Raxe

raxe = Raxe()
result = raxe.scan("Ignore all previous instructions")

if result.scan_result.has_threats:
    print(f"Threat: {result.scan_result.combined_severity}")
    for detection in result.scan_result.l1_result.detections:
        print(f"  - Rule {detection.rule_id}: {detection.severity}")
```

### Decorator Pattern

```python
@raxe.protect(block_on_threat=True)
def generate_response(user_prompt: str) -> str:
    return llm.generate(user_prompt)

# Automatically scans input and blocks threats
response = generate_response("safe prompt")  # ✅ Works
response = generate_response("jailbreak attempt")  # 🚫 Raises ThreatDetectedException
```

### Wrap LLM Clients

**OpenAI:**
```python
from raxe import RaxeOpenAI

client = RaxeOpenAI(api_key="sk-...")
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "prompt"}]
)
# Automatically scans prompts and responses
```

**Anthropic:**
```python
from raxe import RaxeAnthropic

client = RaxeAnthropic(api_key="...")
response = client.messages.create(
    model="claude-3-opus-20240229",
    messages=[{"role": "user", "content": "prompt"}]
)
```

**LangChain:**
```python
from raxe.sdk.integrations.langchain import RaxeCallbackHandler

handler = RaxeCallbackHandler()
chain = LLMChain(llm=llm, callbacks=[handler])
```

---

## 🔒 Privacy & Telemetry

### Privacy-First Design

**RAXE is built with privacy as a core principle:**

- ✅ **All scanning happens locally** – Your prompts never leave your machine
- ✅ **No PII storage** – Only SHA-256 hashes are stored
- ✅ **Optional telemetry** – You control what data is sent
- ✅ **Open source** – Audit the code yourself
- ✅ **No vendor lock-in** – Works 100% offline

### What Gets Sent (If You Opt-In)

When telemetry is enabled, RAXE sends **only**:

```json
{
  "prompt_hash": "sha256:abc123...",  // NOT the actual prompt
  "rule_matches": ["pi-001"],
  "severity": "CRITICAL",
  "confidence": 0.95,
  "timestamp": "2025-11-16T12:00:00Z",
  "python_version": "3.10.0",
  "os": "Darwin"
}
```

**Never sent:**
- ❌ Raw prompt text
- ❌ LLM responses
- ❌ API keys
- ❌ User PII
- ❌ IP addresses (anonymized)

### Disable Telemetry

```bash
raxe init --no-telemetry
```

Or in `~/.raxe/config.yaml`:
```yaml
telemetry:
  enabled: false
```

**RAXE works 100% offline** – telemetry is purely optional.

---

## 📊 Community & Achievements

RAXE includes a **gamified achievement system** to encourage security-conscious development:

### Track Your Progress

```bash
raxe stats
```

See your:
- 📈 Total scans performed
- 🎯 Threats detected and blocked
- 🔥 Daily streak (consecutive days of use)
- ⭐ Achievements unlocked
- ⚡ Average scan performance

### Unlock Achievements

- 🏆 **First Scan** – Run your first threat scan
- 🔍 **Threat Hunter** – Detect your first real threat
- 🔥 **On Fire** – 7-day scanning streak
- 🛡️ **Guardian** – Block 100 threats
- ⚡ **Speed Demon** – Maintain <5ms average scan time
- 🎯 **Eagle Eye** – 95%+ detection accuracy
- 📊 **Data Collector** – Export 1000+ scan records
- 🧪 **Rule Contributor** – Submit a custom rule
- 🌟 **Community Champion** – Help others in Discord
- 🚀 **Production Ready** – Deploy RAXE to production

---

## 🧩 Integration Examples

### FastAPI Application

```python
from fastapi import FastAPI, HTTPException
from raxe import Raxe

app = FastAPI()
raxe = Raxe()

@app.post("/chat")
async def chat(user_input: str):
    # Scan user input before processing
    result = raxe.scan(user_input)

    if result.scan_result.has_threats:
        raise HTTPException(
            status_code=400,
            detail=f"Threat detected: {result.scan_result.combined_severity}"
        )

    # Safe to process
    response = llm.generate(user_input)
    return {"response": response}
```

### Batch Processing

```python
from raxe import Raxe

raxe = Raxe()

# Scan multiple prompts from a file
with open("user_prompts.txt") as f:
    prompts = f.readlines()

for prompt in prompts:
    result = raxe.scan(prompt.strip())
    if result.scan_result.has_threats:
        print(f"⚠️  Threat in: {prompt[:50]}...")
```

### Streamlit Chatbot

```python
import streamlit as st
from raxe import Raxe

raxe = Raxe()

user_input = st.text_input("Ask me anything:")

if user_input:
    result = raxe.scan(user_input)

    if result.scan_result.has_threats:
        st.error(f"🚫 Blocked: {result.scan_result.combined_severity} threat detected")
    else:
        response = llm.generate(user_input)
        st.success(response)
```

---

## 🧪 Detection Rules

RAXE uses **community-maintained detection rules** stored in the registry:

### View All Rules

```bash
raxe rules list
```

### Inspect a Rule

```bash
raxe rules show pi-001
```

Shows:
- Rule name and description
- Pattern/regex used
- Severity level
- Example matches
- Performance metrics

### Custom Rules

Create your own detection rules in `~/.raxe/custom_rules/`:

```yaml
# ~/.raxe/custom_rules/my-rule.yaml
rule_id: custom-001
name: Detect company secrets
family: SEC
severity: CRITICAL
confidence: 0.95
pattern: "API[_-]?KEY[_-]?[A-Za-z0-9]{32}"
description: Detects exposure of API keys
examples:
  should_match:
    - "My API_KEY_abc123xyz456..."
  should_not_match:
    - "Use your API key here"
```

Load custom rules:
```bash
raxe init --load-custom-rules
```

---

## 🎓 Learning Resources

### Quick Tutorials

- 📹 [5-Minute Setup Video](https://www.youtube.com/watch?v=xxx) (Coming Soon)
- 📝 [Getting Started Guide](docs/getting-started.md)
- 🔧 [Integration Examples](examples/)
- 🧪 [Testing Best Practices](docs/testing.md)

### Documentation

- 📖 [Full Documentation](https://docs.raxe.ai)
- 🏗️ [Architecture Overview](docs/architecture.md)
- 🔌 [API Reference](docs/api/)
- 🛡️ [Security Guide](SECURITY.md)

### Community

- 💬 [Discord Community](https://discord.gg/raxe) – Get help and share ideas
- 🐦 [Twitter/X](https://twitter.com/raxe_ai) – Latest updates
- 📧 [Newsletter](https://raxe.ai/newsletter) – Monthly security tips
- 🐛 [Report Issues](https://github.com/raxe-ai/raxe-ce/issues)

---

## 🤝 Contributing

**RAXE is community-driven** – we welcome contributions from:

- 🔐 Security researchers
- 🧠 ML/AI engineers
- 🛠️ LLM app developers
- 📊 Data scientists
- 📚 Technical writers
- 🎨 UX designers

### Ways to Contribute

1. **Add Detection Rules** – Help us catch more threats
2. **Report Vulnerabilities** – Found a bypass? Tell us!
3. **Improve Documentation** – Make onboarding easier
4. **Share Integration Examples** – Show how you use RAXE
5. **Test Edge Cases** – Help us improve accuracy
6. **Translate** – Help international developers

### Quick Contribution Guide

```bash
# Fork and clone the repo
git clone https://github.com/YOUR_USERNAME/raxe-ce.git
cd raxe-ce

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Make your changes and submit a PR!
```

Read our full [Contributing Guide](CONTRIBUTING.md) for details.

---

## 🗺️ Roadmap

### ✅ v1.0 (Current) – Foundation
- Local CLI and Python SDK
- L1 rule-based detection
- L2 ML-based detection
- Privacy-preserving telemetry
- Achievement system
- OpenAI/Anthropic wrappers

### 🚧 v1.1 (Next Quarter) – Enhanced Detection
- Improved PII detection
- Response scanning
- Chain-of-thought analysis
- Expanded rule library
- Performance optimizations
- LangChain deep integration

### 🔮 v1.5 (Future) – Enterprise Features
- Policy-as-code framework
- Custom model fine-tuning
- Multi-region support
- SSO integration
- Advanced analytics
- Compliance reports (SOC 2, GDPR)

### 🌟 v2.0 (Vision) – AI-Powered Security
- Auto-generate rules from incidents
- Adversarial testing framework
- Model drift detection
- Zero-trust architecture
- On-premise deployment option

**Vote on features:** [GitHub Discussions](https://github.com/raxe-ai/raxe-ce/discussions)

---

## ❓ FAQ

### Is RAXE really free?

**Yes!** RAXE Community Edition is 100% free and open source (MIT license). Cloud dashboards and team features are optional paid add-ons.

### Does RAXE work offline?

**Yes!** All scanning happens locally. You can disable telemetry and use RAXE completely offline.

### What LLM providers are supported?

Currently: OpenAI, Anthropic, LangChain, and direct SDK.
Coming soon: Cohere, Ollama, Hugging Face, Azure OpenAI.

### How accurate is the detection?

L1 rules have **~95% precision** on known patterns. L2 ML model adds an additional layer with **~85% recall** on novel attacks. Together, the hybrid system achieves strong real-world performance.

### Can I use RAXE in production?

**Yes!** RAXE is designed for production use with:
- <10ms p95 latency
- Circuit breaker for reliability
- Graceful degradation modes
- Comprehensive error handling

Thousands of requests per second? No problem.

### How do I report a security issue?

Please **do not open a public issue**. Email security@raxe.ai with details. We'll respond within 24 hours.

See our [Security Policy](SECURITY.md) for our responsible disclosure process.

---

## 🙏 Acknowledgments

RAXE stands on the shoulders of giants:

- **Snort** – Inspiration for rule-based threat detection
- **OWASP** – LLM security best practices
- **Research Community** – Prompt injection research
- **Open Source Contributors** – Everyone who's helped improve RAXE

Special thanks to early adopters and beta testers who helped shape RAXE!

---

## ⭐ Support the Mission

**RAXE exists to make AI safer for everyone.**

If you believe in transparent, community-driven AI security:

- ⭐ **Star this repo** – Show your support
- 🐦 **Share on social media** – Spread the word
- 📝 **Write about RAXE** – Blog posts, tutorials, case studies
- 🤝 **Contribute** – Code, rules, docs, feedback
- 💬 **Join our community** – Discord, GitHub Discussions

**Together, we're building the future of AI security.**

---

## 📄 License

RAXE Community Edition is released under the **MIT License**.

See [LICENSE](LICENSE) for details.

---

## 🔗 Links

- 🌐 **Website:** [raxe.ai](https://raxe.ai)
- 📖 **Documentation:** [docs.raxe.ai](https://docs.raxe.ai)
- 💬 **Discord:** [discord.gg/raxe](https://discord.gg/raxe)
- 🐦 **Twitter:** [@raxe_ai](https://twitter.com/raxe_ai)
- 🐛 **Issues:** [github.com/raxe-ai/raxe-ce/issues](https://github.com/raxe-ai/raxe-ce/issues)
- 📧 **Email:** community@raxe.ai

---

<div align="center">

**🛡️ Before AGI arrives, we need visibility.**

**RAXE is the instrument panel for AI safety.**

[Get Started in 60 Seconds →](https://github.com/raxe-ai/raxe-ce#-quick-start--60-seconds)

</div>
