<div align="center">
  <img src="https://github.com/raxe-ai/raxe-ce/blob/main/docs/assets/logo-name-only.png?raw=true" alt="RAXE Logo" width="400"/>

  <h1>RAXE Documentation</h1>
  <p><strong>Privacy-first threat detection for LLM applications</strong></p>
</div>

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Community Edition](https://img.shields.io/badge/Edition-Community-blue.svg)](https://raxe.ai)
[![Always Free](https://img.shields.io/badge/Pricing-Free%20Forever-green.svg)](https://raxe.ai/pricing)

---

## Quick Start (60 Seconds)

```bash
# Install
pip install raxe

# Detect your first threat
raxe scan "Ignore all previous instructions"
# THREAT DETECTED - Prompt Injection (CRITICAL)
```

### Python SDK

```python
from raxe import Raxe

raxe = Raxe()
result = raxe.scan("Your user input here")

# Clean, flat API
if result.has_threats:
    print(f"Threat: {result.severity}")
    print(f"Detections: {result.total_detections}")
else:
    print("Safe to proceed")
```

### Drop-in LLM Wrappers

```python
from raxe import RaxeOpenAI

# Automatic threat blocking on all prompts
client = RaxeOpenAI(api_key="sk-...")
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "your prompt"}]
)
```

[Get Started in 60 Seconds](getting-started.md) | [Full README](../README.md)

---

## Key Features

### Real-time Threat Detection
Detect prompt injection, jailbreaks, PII leaks, and toxic content in <10ms.

### Privacy-First
Everything runs locally. Your data never leaves your machine.

### Production-Ready
<10ms P95 latency, circuit breakers, graceful degradation.

### Easy Integration
One line of code. Works with OpenAI, Anthropic, LangChain.

### 514 Detection Rules
Community-driven detection rules across 7 threat families.

---

## What RAXE Detects

### L1: Rule-Based Detection

Fast pattern matching with 514 curated YAML rules:

| Family | Description | Example |
|--------|-------------|---------|
| **PI** | Prompt Injection | "Ignore all previous instructions..." |
| **JB** | Jailbreaks | DAN, STAN, and other jailbreak techniques |
| **PII** | Personal Info | Credit cards, SSNs, emails, API keys |
| **CMD** | Command Injection | Shell commands, data exfiltration |
| **ENC** | Encoding/Obfuscation | Base64, hex, Unicode tricks |
| **HC** | Harmful Content | Hate speech, violence, harassment |
| **RAG** | RAG-Specific | Document manipulation, citation attacks |

### L2: ML-Based Detection

Lightweight CPU-friendly classifier that catches:
- Obfuscated injection attempts
- Novel attack patterns
- Subtle manipulation attempts
- Context-aware anomalies

---

## Documentation

### Getting Started
- [Getting Started Guide](getting-started.md) - Complete onboarding in 5 minutes
- [Authentication Guide](authentication.md) - API keys, CLI auth, CI/CD setup
- [Configuration](configuration.md) - Configure RAXE for your use case
- [Troubleshooting](troubleshooting.md) - Common issues and solutions

### Core Documentation
- [Architecture](architecture.md) - System design and technical decisions
- [API Reference](api_reference.md) - Complete API documentation
- [Error Codes](ERROR_CODES.md) - Comprehensive error code reference

### Integration Guides
- [Python SDK](examples/basic-usage.md) - Integrate RAXE into Python applications
- [OpenAI Integration](examples/openai-integration.md) - Protect OpenAI API calls
- [Custom Rules](CUSTOM_RULES.md) - Create your own detection rules
- [Policy Configuration](POLICIES.md) - Control threat handling

### Advanced Topics
- [Performance Tuning](performance/tuning_guide.md) - Optimize for your workload
- [Plugin Development](plugins/plugin_development_guide.md) - Extend RAXE with plugins
- [Async SDK](async-guide.md) - High-performance async usage

### Development
- [Development Guide](development.md) - Set up development environment
- [Contributing](../CONTRIBUTING.md) - How to contribute to RAXE

---

## Usage Examples

### Validate User Input

```python
from raxe import Raxe

raxe = Raxe()

def process_user_input(user_input: str) -> str:
    result = raxe.scan(user_input)

    # Boolean check - True when safe
    if not result:
        return f"Blocked: {result.severity} threat detected"

    return generate_response(user_input)
```

### Protect Functions with Decorator

```python
from raxe import Raxe

raxe = Raxe()

@raxe.protect  # Monitor mode (logs threats, doesn't block)
def generate_response(prompt: str) -> str:
    return your_llm.generate(prompt)

# All prompts are scanned automatically
response = generate_response("What is AI?")
```

### FastAPI Integration

```python
from fastapi import FastAPI, HTTPException
from raxe import Raxe

app = FastAPI()
raxe = Raxe()

@app.post("/chat")
async def chat(user_input: str):
    result = raxe.scan(user_input)

    if not result:  # False when threats detected
        raise HTTPException(400, f"Blocked: {result.severity}")

    return {"response": your_llm.generate(user_input)}
```

### Batch Scanning

```python
from raxe import AsyncRaxe

async_raxe = AsyncRaxe()

prompts = ["prompt 1", "prompt 2", "prompt 3"]
results = await async_raxe.scan_batch(prompts, max_concurrency=5)

for prompt, result in zip(prompts, results):
    status = "THREAT" if result.has_threats else "SAFE"
    print(f"{status}: {prompt[:30]}...")
```

---

## Privacy & Trust

### Local-First Scanning

All scanning happens locally on your device:
- No prompts transmitted to cloud
- No internet connection required
- Works 100% offline with zero degradation

### What We Never Share

Even when telemetry is enabled:
- Actual prompt text or responses
- Matched text snippets or rule patterns
- End-user identifiers (their IP, user_id from your app)

### What Telemetry Shares (When Enabled)

Detection metadata and performance metrics:
- API key (client identification for service access)
- Prompt hash (SHA-256 for uniqueness - hard to reverse)
- Rule ID that triggered detection
- Severity level and confidence score
- Detection count (not content)
- Performance metrics (scan duration, L1/L2 timing)
- Timestamp and RAXE version

[Privacy Details](../README.md#-privacy--trust-our-core-principles)

---

## Performance

Based on real benchmarks:

| Metric | Value |
|--------|-------|
| P50 latency | <1ms |
| P95 latency | <10ms (L1), <50ms (L1+L2) |
| Throughput | ~1,200 scans/second |
| Memory usage | ~60MB peak |
| False positive rate | <0.1% |

[Performance Tuning Guide](performance/tuning_guide.md)

---

## Community & Support

- [GitHub Discussions](https://github.com/raxe-ai/raxe-ce/discussions) - Ask questions, share ideas
- [Slack Community](https://join.slack.com/t/raxeai/shared_invite/zt-3kch8c9zp-A8CMJYWQjBBpzV4KNnAQcQ) - Real-time chat
- [GitHub Issues](https://github.com/raxe-ai/raxe-ce/issues) - Bug reports
- [FAQ](../FAQ.md) - Frequently asked questions

---

## License

RAXE Community Edition is proprietary software available for **free forever**.

**You may:** Use for personal, educational, or commercial purposes
**You may NOT:** Modify, reverse engineer, or redistribute modified versions

See [LICENSE](https://github.com/raxe-ai/raxe-ce/blob/main/LICENSE) for complete terms.

---

<div align="center">

**RAXE: Transparency over hype. Privacy by design. Always free.**

[Get Started](../QUICKSTART.md) | [Enterprise Edition](https://raxe.ai/enterprise)

</div>
