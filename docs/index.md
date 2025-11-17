# RAXE - AI Security for LLMs

<div align="center" markdown>
**Privacy-first threat detection for LLM applications**

[![Tests](https://img.shields.io/github/workflow/status/raxe-ai/raxe-ce/Tests?style=flat-square)](https://github.com/raxe-ai/raxe-ce/actions)
[![Coverage](https://img.shields.io/codecov/c/github/raxe-ai/raxe-ce?style=flat-square)](https://codecov.io/gh/raxe-ai/raxe-ce)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue?style=flat-square)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow?style=flat-square)](https://opensource.org/licenses/MIT)
</div>

---

## What is RAXE?

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

## Quick Start

Get up and running in less than 60 seconds:

=== "CLI"

    ```bash
    # Install RAXE
    pip install raxe

    # Initialize configuration
    raxe init

    # Start scanning
    raxe scan "Ignore all previous instructions"
    # 🔴 THREAT DETECTED - Prompt Injection (CRITICAL)
    ```

=== "Python SDK"

    ```python
    from raxe import Raxe

    raxe = Raxe()
    result = raxe.scan("Your user input here")

    if result.scan_result.has_threats:
        print(f"⚠️  {result.scan_result.combined_severity} threat detected!")
    ```

=== "OpenAI Wrapper"

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

=== "Async (FastAPI)"

    ```python
    from fastapi import FastAPI, HTTPException
    from raxe.async_sdk.client import AsyncRaxe

    app = FastAPI()
    raxe = AsyncRaxe()

    @app.post("/chat")
    async def chat(message: str):
        result = await raxe.scan(message)
        if result.scan_result.has_threats:
            raise HTTPException(status_code=400, detail="Threat detected")
        return {"response": "safe to process"}
    ```

[:material-rocket-launch: Get Started](quickstart.md){ .md-button .md-button--primary }
[:material-book-open: Read the Guide](architecture.md){ .md-button }

---

## Key Features

<div class="grid cards" markdown>

-   :shield:{ .lg .middle } **Real-time Threat Detection**

    ---

    Detect prompt injection, jailbreaks, PII leaks, and toxic content in <10ms

    [:octicons-arrow-right-24: Detection Capabilities](architecture.md#what-raxe-detects)

-   :lock:{ .lg .middle } **Privacy-First**

    ---

    Everything runs locally. Your data never leaves your machine

    [:octicons-arrow-right-24: Privacy Details](privacy.md)

-   :zap:{ .lg .middle } **Production-Ready**

    ---

    <10ms scan latency, circuit breakers, graceful degradation

    [:octicons-arrow-right-24: Performance Guide](performance/tuning_guide.md)

-   :plug:{ .lg .middle } **Easy Integration**

    ---

    One line of code. Works with OpenAI, Anthropic, LangChain

    [:octicons-arrow-right-24: Integration Guide](integration_guide.md)

-   :test_tube:{ .lg .middle } **Comprehensive Testing**

    ---

    460 detection rules, 3,364 tests, 80% code coverage

    [:octicons-arrow-right-24: Testing Guide](QUICK_START_TESTING.md)

-   :people_holding_hands:{ .lg .middle } **Community-Driven**

    ---

    Open source, MIT licensed, community-maintained rules

    [:octicons-arrow-right-24: Contributing](CONTRIBUTING.md)

</div>

---

## What RAXE Detects

### L1: Rule-Based Detection
High-confidence pattern matching for known attack types:

| Family | Rules | Description |
|--------|-------|-------------|
| **PI** (Prompt Injection) | 76 | "Ignore all previous instructions..." |
| **JB** (Jailbreaks) | 105 | DAN, STAN, and other jailbreak techniques |
| **PII** (Personal Info) | 47 | Credit cards, SSNs, emails |
| **CMD** (Command Injection) | 24 | Shell commands, data exfiltration |
| **ENC** (Encoding/Obfuscation) | 94 | Base64, hex, Unicode tricks |
| **HC** (Harmful Content) | 47 | Hate speech, violence, harassment |
| **RAG** (RAG-Specific) | 67 | Document manipulation, citation attacks |

### L2: ML-Based Detection
Lightweight CPU-friendly classifier that catches:

- ✅ Obfuscated injection attempts
- ✅ Novel attack patterns
- ✅ Subtle manipulation attempts
- ✅ Context-aware anomalies

[:octicons-arrow-right-24: Learn More About Detection](architecture.md)

---

## Why RAXE?

| Feature | RAXE | Alternatives |
|---------|------|-------------|
| **Privacy** | 100% local processing | Cloud-based scanning |
| **Latency** | <10ms P95 | 50-200ms typical |
| **Cost** | Free, open source | Usage-based pricing |
| **Vendor Lock-in** | None - works offline | Proprietary APIs |
| **Customization** | Full rule control | Limited configuration |
| **Transparency** | Open source | Closed algorithms |

---

## Use Cases

### For Developers
- Protect LLM-powered applications from malicious inputs
- Integrate security in development, not as an afterthought
- Test attack resilience before production
- Track security metrics alongside performance

### For Security Teams
- Real-time visibility into LLM security threats
- Privacy-preserving telemetry for compliance
- No data leaves your infrastructure
- Audit trail for security incidents

### For Enterprises
- Meet compliance requirements (GDPR, SOC 2, HIPAA)
- Control data residency with local deployment
- Scale to production workloads (1000+ req/sec)
- Integrate with existing security infrastructure

---

## Performance

Based on real benchmarks from our test suite:

| Metric | Value |
|--------|-------|
| P50 latency | 0.37ms (13x better than target) |
| P95 latency | 0.49ms (20x better than target) |
| P99 latency | 1.34ms (15x better than target) |
| Throughput | ~1,200 scans/second |
| Memory usage | ~60MB peak |
| False positive rate | 0.00% (on test suite) |

[:octicons-arrow-right-24: Performance Tuning Guide](performance/tuning_guide.md)

---

## Community

Join thousands of developers building safer AI:

- :fontawesome-brands-github: [GitHub Repository](https://github.com/raxe-ai/raxe-ce) - Star, fork, contribute
- :fontawesome-brands-discord: [Discord Community](https://discord.gg/raxe) - Get help, share ideas
- :fontawesome-brands-twitter: [Twitter/X](https://twitter.com/raxe_ai) - Latest updates
- :fontawesome-solid-envelope: [Newsletter](https://raxe.ai/newsletter) - Monthly security tips

[:octicons-people-24: Join the Community](CONTRIBUTING.md){ .md-button }

---

## Next Steps

<div class="grid" markdown>

=== "New to RAXE?"

    1. [Quick Start Guide](quickstart.md) - Get up and running in 60 seconds
    2. [Architecture Overview](architecture.md) - Understand how RAXE works
    3. [Integration Examples](integration_guide.md) - See real-world usage

=== "Ready to Integrate?"

    1. [Python SDK Guide](api/raxe-client.md) - Full API reference
    2. [Async SDK Guide](async-guide.md) - High-performance async usage
    3. [Performance Tuning](performance/tuning_guide.md) - Optimize for production

=== "Want to Contribute?"

    1. [Contributing Guide](CONTRIBUTING.md) - How to get involved
    2. [Rule Submission](CONTRIBUTING_RULES.md) - Add detection rules
    3. [Development Setup](development.md) - Set up dev environment

</div>

---

## License

RAXE Community Edition is released under the **MIT License**.

See [LICENSE](https://github.com/raxe-ai/raxe-ce/blob/main/LICENSE) for details.

---

<div align="center" markdown>

**🛡️ Before AGI arrives, we need visibility.**

**RAXE is the instrument panel for AI safety.**

[Get Started in 60 Seconds →](quickstart.md){ .md-button .md-button--primary }

</div>
