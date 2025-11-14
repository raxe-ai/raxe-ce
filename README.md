# 🛡️ RAXE CE – AI Safety Telemetry & Guardrails (Community Edition)

[![Tests](https://github.com/raxe-ai/raxe-ce/workflows/Tests/badge.svg)](https://github.com/raxe-ai/raxe-ce/actions)
[![codecov](https://codecov.io/gh/raxe-ai/raxe-ce/branch/main/graph/badge.svg)](https://codecov.io/gh/raxe-ai/raxe-ce)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**RAXE CE** is an open-source AI safety & security layer for developers building with LLMs.
It gives you **real-time visibility, prompt-injection detection, risk signals, and guardrails**—all from your local machine.

**Think of it as:**
> 📟 **The instrument panel for your LLM application.**
> Before AGI arrives, we need to know what's happening under the hood.

RAXE CE brings modern security thinking (IDS/IPS, telemetry, visibility, explainability) to the world of LLMs.

---

## 🚀 What is RAXE?

RAXE is a **developer-first safety observability layer** for LLM apps:

- 🧩 **Local agent + CLI** – wrap LLM calls instantly
- 🕵️ **L1 detection (rules)** – high-precision pattern-based detection
- 🧠 **L2 detection (ML)** – CPU-friendly classifier for subtle attacks
- 📡 **Telemetry pipeline** – structured safety events
- 📊 **Cloud dashboard (optional)** – risk trends, alerts, explanations
- 🔒 **Privacy-first** – no PII stored by default, local redaction before sending
- 🧪 **Rulepacks** – community-driven threat detection for LLM safety

**RAXE CE is open-source and runs fully on your machine.**
Cloud features are optional and free for the first 15 days (see [telemetry section](#-telemetry-transparency)).

---

## ✨ Key Features

### 🧩 1. Simple to Integrate

Wrap any LLM in seconds:

```bash
pip install raxe
raxe init
raxe run python app.py
```

Or in Python:

```python
from raxe import guard_openai_client

client = guard_openai_client(openai.api_key)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "ignore all previous instructions ..."}]
)
```

### 🛡️ 2. L1 Detection (Rules Engine)

A fast, deterministic, community-maintained ruleset detecting:

- ✅ Prompt injection
- ✅ Jailbreak attempts
- ✅ Data exfiltration
- ✅ PII leakage
- ✅ Toxic output
- ✅ Content policy bypassing

**All rules are stored in the [raxe-rules](https://github.com/raxe-ai/raxe-rules) open-source repo.**

### 🧠 3. L2 Detection (Machine Learning)

A lightweight, CPU-friendly classifier:

- Learns from rule outcomes (weak supervision)
- Reduces false positives
- Detects subtle or obfuscated injection attempts
- **Runs locally—no GPU required**

### 🔍 4. Explainable Safety Signals

Every detection includes:

- Which rules fired
- Model probability
- Final decision (allow / block / flag)
- Severity & confidence
- Metadata you can use in CI/CD

### 📡 5. Local Telemetry Pipeline

RAXE CE emits structured safety events (JSON), including:

- Rule matches
- L2 probabilities
- Latencies
- Environment
- Machine runtime info

Events are batched locally, stored in a resilient queue, and can be sent to RAXE Cloud.

### 📊 6. Optional Cloud Dashboard (Free 15-Day Trial)

RAXE CE automatically uses a **15-day anonymous trial** to help you see real dashboards without setup.

**After 15 days:**
- CE continues scanning
- Telemetry pauses
- Signing up for a free API key re-enables cloud dashboards

This helps devs see value instantly while keeping CE fully functional.

---

## 🔭 Why RAXE Exists

**AI is accelerating rapidly.**
Before we talk about AGI safety, alignment, or governance…

**We need visibility.**

> You can't govern what you can't see.
> You can't defend what you can't measure.

RAXE is built because:

- ❌ Developers are unknowingly shipping insecure LLM integrations
- ❌ Prompt injection is evolving faster than any one team can track
- ❌ Organizations have zero observability into AI risk
- ❌ Safety must be transparent, open-source, and accountable
- ❌ Guardrails should be explainable, not black-box magic

**RAXE CE is our contribution to open, community-driven AI safety infrastructure.**

---

## 🛠️ Installation

```bash
pip install raxe
```

### Initialize

```bash
raxe init
```

### Wrap Your Application

```bash
raxe run python app.py
```

Or use the **Python SDK**:

```python
from raxe import guard_openai_client
```

---

## 📚 Quick Start

### 1. Install & Initialize

```bash
pip install raxe
raxe init
```

### 2. Run Your App Through RAXE

```bash
raxe run python app.py
```

### 3. Trigger Some Prompts

Open the RAXE portal to see:

- Detections
- Severity breakdown
- Top risks
- Per-rule insights

---

## 🔐 Telemetry Transparency

**RAXE CE is open-source + privacy-first.**

### What is Collected?

RAXE collects **only redacted, hashed, PII-free safety signals**:

- A SHA-256 hash of your prompt
- Rule matches
- Severity
- L2 probability
- Device metadata (Python version, OS)

**No raw prompt content** (unless you explicitly allow it in Enterprise)

### Why Send Telemetry?

Telemetry helps you:

- See real dashboards
- Understand attack patterns
- Investigate risks
- Improve safety posture

It also helps us improve rulepacks and classifier accuracy.

### 15-Day Trial

RAXE CE automatically sends telemetry for the first 15 days under a temporary anonymous project.

**After that:**
- Scanning continues
- Telemetry stops
- Creating an API key re-enables dashboards

**This ensures transparency + user control.**

---

## 🧾 Rulepacks (Community-Driven)

Rules live in a separate open-source repo:
👉 **[github.com/raxe-ai/raxe-rules](https://github.com/raxe-ai/raxe-rules)**

### Why Separate?

- ✅ Full transparency
- ✅ Independent community governance
- ✅ Security isolation
- ✅ Safe versioning

Each rule includes:

- Severity
- Confidence
- Regex patterns
- Examples (should_match / should_not_match)
- MITRE mapping
- TP/FP/FN/TN metrics (from cloud telemetry)

**Contributions welcome!**

---

## 🧠 Architecture Overview

```
+-------------------+         +-------------------+         +------------------+
|   Developer App   |  LLM    |   RAXE CE Agent   |  HTTP   |    RAXE Cloud    |
| (Python, FastAPI) | <-----> | (SDK, Rules, ML)  | ------> |  Ingest + Alerts |
+-------------------+         +-------------------+         +------------------+
                                  |         ^
                                  v         |
                             Local Queue  Backoff
                                  |
                                  v
                               Disk (SQLite)
```

### Core Components

- **L1 Rule Engine** – Pattern-based detection
- **L2 Classifier** – ML-based detection
- **Redaction Processor** – PII removal
- **SQLite-backed Queue** – Event storage
- **Batch Sender** – Cloud telemetry
- **Token & Config Manager** – Configuration
- **Integration Wrappers** – OpenAI/Anthropic/LangChain

See [Architecture Documentation](docs/architecture.md) for details.

---

## 🌍 Roadmap

### v1.0 (Current)

- CLI, SDK, integrations
- L1/L2 hybrid detection
- Cloud telemetry
- Portal dashboards
- Community rulepacks

### v1.1 (Next)

- Visual breakdown of what contributed to detections
- Rule quality reports
- Improved PII detection & redaction
- Additional client integrations

### v1.5 (Future)

- Policy-as-code framework
- SSO (Teams/Enterprise)
- Multi-region cloud ingestion
- Data governance workflows

### v2 (Vision)

- Model-driven rule generation
- Automated drift detection
- Model governance reports
- On-prem enterprise deployment

---

## 🤝 Contributing

We welcome contributions from:

- Security researchers
- ML safety experts
- LLM app developers
- Infra & cloud engineers
- Regulators & governance researchers

### Ways to Help

- ✅ Improve rulepacks
- ✅ Add test cases
- ✅ Report new prompt injection vectors
- ✅ Improve detection logic
- ✅ Add integrations (Cohere, Ollama, etc.)

Please read:

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

---

## ⭐ Support the Mission

**RAXE is part of a broader vision:**

> Open, transparent, community-driven AI safety infrastructure
> accessible to every developer.

If you believe in this mission:

- ⭐ **Star the repo**
- 📣 **Share with AI/security teams**
- 🔧 **Contribute rules & tests**
- 📝 **Suggest new threat types**
- 🛡️ **Join discussions around AGI safety instrumentation**

**Together we make AI safer.**

---

## 📄 License

RAXE CE is open-source under the **MIT License**.
Rulepacks may have mixed licensing depending on contributors.
Cloud features are commercial but optional.

---

## 🔗 Links

- **Homepage:** [raxe.ai](https://raxe.ai)
- **Documentation:** [docs.raxe.ai](https://docs.raxe.ai)
- **Rules Repository:** [github.com/raxe-ai/raxe-rules](https://github.com/raxe-ai/raxe-rules)
- **Community:** [Discord](https://discord.gg/raxe) | [Twitter](https://twitter.com/raxe_ai)

---

**Before AGI arrives, we need visibility.**
**RAXE is the instrument panel for AI safety.**

🛡️ **Start protecting your LLM apps today.**
