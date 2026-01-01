<div align="center">
  <img src="https://github.com/raxe-ai/raxe-ce/blob/main/docs/assets/logo-name-only.png?raw=true" alt="RAXE Logo" width="400"/>

  <h1>Quick Start</h1>

  <p><strong>AI Safety Research &amp; Threat Detection for LLMs</strong></p>

  <p><em>v0.4.0 Beta | Community Edition | Free Forever</em></p>
</div>

---

> **📦 Consolidation Notice:** This guide is being merged into [docs/getting-started.md](docs/getting-started.md).
> This file will be removed in v0.5.0. The getting-started guide provides a more complete onboarding experience.

---

> ⚠️ **Beta Notice:** This is an early beta release. All data will be wiped before going into production.

---

## Install

```bash
pip install raxe
```

---

## Authenticate

### Option 1: Browser Authentication (Recommended)

```bash
raxe auth
```

This opens your browser to:
1. Create a free Community account (or sign in)
2. Automatically link your CLI
3. Configure your API key

```
RAXE CLI Authentication

Opening browser for authentication...
Waiting for authentication... (press Ctrl+C to cancel)

Success! CLI linked to your account.
API key configured: raxe_live_xxxxx
```

### Option 2: Link Code (From Web Console)

If you already have an API key in the web console:

1. Go to [console.raxe.ai](https://console.raxe.ai) → API Keys
2. Click "Link CLI" on any key card
3. Copy the 6-character code

```bash
raxe link ABC123
```

### Option 3: Manual Configuration

```bash
# Set API key directly
raxe config set api_key YOUR_API_KEY

# Or use environment variable
export RAXE_API_KEY=YOUR_API_KEY
```

---

## Your First Scan

### CLI

```bash
raxe scan "Ignore all previous instructions"
```

Output:
```
THREAT DETECTED

Severity: CRITICAL
Family: Prompt Injection (PI)
Confidence: 95%

Detected Rules:
  • pi-001: Instruction override attempt
```

### Python SDK

```python
from raxe import Raxe

raxe = Raxe()
result = raxe.scan("Ignore all previous instructions")

if result.has_threats:
    print(f"BLOCKED: {result.severity}")  # CRITICAL
```

**That's it.** Your prompts are scanned locally. Nothing leaves your machine.

---

## The Complete Flow

```bash
# 1. Install
pip install raxe

# 2. Authenticate (opens browser)
raxe auth

# 3. Verify setup
raxe doctor
# → API key: valid
# → Rules loaded: 460
# → ML model: ready

# 4. Scan prompts
raxe scan "Your prompt here"

# 5. Check statistics
raxe stats

# 6. Check auth status
raxe auth status
```

---

## Protect Your LLM

### Option 1: Drop-in OpenAI Wrapper

```python
from raxe import RaxeOpenAI

# Default: log-only mode (safe for production)
client = RaxeOpenAI(api_key="sk-...")

# Threats logged automatically, requests pass through
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": user_input}]
)

# Or enable blocking mode
client = RaxeOpenAI(api_key="sk-...", raxe_block_on_threat=True)
```

### Option 2: Decorator Pattern

```python
from raxe import Raxe

raxe = Raxe()

@raxe.protect
def generate_response(prompt: str) -> str:
    return your_llm.generate(prompt)

# Threats detected and logged (monitor mode by default)
response = generate_response(user_input)
```

### Option 3: Manual Validation

```python
from raxe import Raxe
from fastapi import FastAPI, HTTPException

app = FastAPI()
raxe = Raxe()

@app.post("/chat")
async def chat(user_input: str):
    result = raxe.scan(user_input)

    if result.has_threats:
        raise HTTPException(400, f"Blocked: {result.severity}")

    return {"response": your_llm.generate(user_input)}
```

---

## Explore

```bash
raxe rules list          # See all 460+ detection rules
raxe rules show pi-001   # View rule details with examples
raxe doctor              # Check system health
raxe stats               # View scan statistics
raxe repl                # Interactive scanning mode
raxe auth status         # Check authentication status
```

---

## What RAXE Detects

| Family | Rules | Examples |
|--------|-------|----------|
| **Prompt Injection** | 76 | "Ignore all previous instructions" |
| **Jailbreaks** | 105 | "You are now DAN" |
| **PII Leaks** | 47 | Credit cards, SSNs, API keys |
| **Encoding Tricks** | 94 | Base64, Unicode obfuscation |
| **Command Injection** | 38 | Shell command attempts |
| **Toxic Content** | 52 | Hate speech, violence |
| **RAG Attacks** | 48 | Data exfiltration |

**All 100% local** – your data never leaves your machine.

---

## Performance & Privacy

| Metric | Value |
|--------|-------|
| P95 Latency | <10ms |
| False Positive Rate | <0.1% |
| Detection Rate | 95%+ |
| Processing | 100% local |
| Data Sent | Metadata only (never prompts) |

---

## Next Steps

| Resource | Description |
|----------|-------------|
| [README.md](README.md) | Full documentation |
| [docs/CUSTOM_RULES.md](docs/CUSTOM_RULES.md) | Create your own rules |
| [docs/POLICIES.md](docs/POLICIES.md) | Configure threat handling |
| [FAQ.md](FAQ.md) | Common questions |

### CLI Reference

```bash
raxe --help              # All commands
raxe scan --help         # Scan options
raxe auth --help         # Authentication options
raxe doctor              # Health check
```

---

## Troubleshooting

**Python version:** Requires 3.10+
```bash
python --version
```

**Command not found:**
```bash
python -m raxe.cli.main scan "test"
```

**Import errors:**
```bash
pip install --upgrade raxe
```

**Authentication issues:**
```bash
raxe auth status         # Check current status
raxe auth                # Re-authenticate
```

---

## Join the Community

- **Twitter:** [@raboraxe](https://twitter.com/raboraxe)
- **GitHub:** [Discussions](https://github.com/raxe-ai/raxe-ce/discussions)
- **Website:** [raxe.ai](https://raxe.ai)

---

<div align="center">

**RAXE Community Edition - Open Beta v0.4.0**

100% local. Under 10ms. Free forever.

</div>
