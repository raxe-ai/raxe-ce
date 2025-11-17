# RAXE Quick Reference Cheat Sheet

## Installation & Setup

```bash
# Install
pip install raxe

# Install with optional features
pip install raxe[wrappers]    # OpenAI, Anthropic, LangChain
pip install raxe[repl]        # Interactive REPL
pip install raxe[all]         # All features

# Initialize
raxe init

# Test setup
raxe test
```

## CLI Commands

### Scanning

```bash
# Scan text
raxe scan "Your text here"

# From stdin
echo "test" | raxe scan --stdin

# JSON output
raxe scan "text" --format json

# L1 only (faster)
raxe scan "text" --l1-only

# With profiling
raxe scan "text" --profile

# Explain detections
raxe scan "text" --explain
```

### Batch Operations

```bash
# Scan file with multiple prompts
raxe batch prompts.txt

# Interactive REPL
raxe repl

# Export scan history
raxe export --format json --output scans.json
raxe export --format csv --output scans.csv
```

### Rules Management

```bash
# List all rules
raxe rules list

# Show specific rule
raxe rules show pi-001

# List by family
raxe rules list --family PI

# Search rules
raxe rules list --search "injection"

# Validate custom rule
raxe validate-rule my-rule.yaml
```

### Analytics & Stats

```bash
# View statistics
raxe stats

# Check achievements
raxe stats --achievements

# System diagnostics
raxe doctor

# Privacy information
raxe privacy
```

### Tuning & Performance

```bash
# Interactive tuning
raxe tune threshold

# Profile performance
raxe profile "test text"

# Suppress false positives
raxe suppress add pi-001 "specific text"
raxe suppress list
raxe suppress remove <id>
```

## Python SDK

### Basic Usage

```python
from raxe import Raxe

# Initialize
raxe = Raxe()

# Scan text
result = raxe.scan("Your text here")

# Check for threats
if result.scan_result.has_threats:
    print(f"Severity: {result.scan_result.combined_severity}")
    for detection in result.scan_result.l1_result.detections:
        print(f"Rule: {detection.rule_id}, Message: {detection.message}")
```

### Decorator Pattern

```python
from raxe import Raxe

raxe = Raxe()

@raxe.protect(block_on_threat=True)
def process_input(user_text: str):
    return llm.generate(user_text)

# Automatically scans and blocks threats
result = process_input("safe text")
```

### Configuration

```python
from raxe import Raxe

# Custom config path
raxe = Raxe(config_path="/path/to/config.yaml")

# L1 only (fast mode)
result = raxe.scan("text", l1_only=True)

# L2 only (ML mode)
result = raxe.scan("text", l2_only=True)

# Custom confidence threshold
result = raxe.scan("text", min_confidence=0.8)

# Dry run (don't save to database)
result = raxe.scan("text", dry_run=True)
```

## Async SDK

### Basic Async

```python
import asyncio
from raxe.async_sdk.client import AsyncRaxe

async def main():
    async with AsyncRaxe() as raxe:
        result = await raxe.scan("text")
        if result.scan_result.has_threats:
            print("Threat detected")

asyncio.run(main())
```

### Batch Scanning

```python
async with AsyncRaxe() as raxe:
    prompts = ["text1", "text2", "text3"]
    results = await raxe.scan_batch(
        prompts,
        max_concurrent=10
    )
```

### Cache Management

```python
async with AsyncRaxe(
    cache_enabled=True,
    cache_ttl=300,       # 5 minutes
    cache_max_size=1000
) as raxe:
    # Check cache stats
    stats = raxe.cache_stats()
    print(f"Hit rate: {stats['hit_rate']}")

    # Clear cache
    raxe.clear_cache()
```

## LLM Wrappers

### OpenAI

```python
from raxe import RaxeOpenAI

# Drop-in replacement
client = RaxeOpenAI(api_key="sk-...")

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "prompt"}]
)
# Prompts automatically scanned
```

### Anthropic

```python
from raxe import RaxeAnthropic

client = RaxeAnthropic(api_key="...")

response = client.messages.create(
    model="claude-3-opus-20240229",
    messages=[{"role": "user", "content": "prompt"}]
)
```

### Async OpenAI

```python
from raxe.async_sdk.wrappers.openai import AsyncRaxeOpenAI

client = AsyncRaxeOpenAI(
    api_key="sk-...",
    block_on_threat=True,     # Raise exception on threats
    scan_responses=True       # Also scan responses
)

response = await client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "prompt"}]
)
```

## Framework Integrations

### FastAPI

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
    return {"response": "safe"}
```

### LangChain

```python
from raxe.sdk.integrations.langchain import RaxeCallbackHandler
from langchain.chains import LLMChain

handler = RaxeCallbackHandler(block_on_threat=True)
chain = LLMChain(llm=llm, callbacks=[handler])
```

## Detection Families

| Family | Code | Description | Rules |
|--------|------|-------------|-------|
| Prompt Injection | PI | Instruction override | 76 |
| Jailbreak | JB | DAN, STAN, role-playing | 105 |
| PII | PII | Credit cards, SSNs, emails | 47 |
| Command Injection | CMD | Shell commands, exfiltration | 24 |
| Encoding/Obfuscation | ENC | Base64, hex, Unicode | 94 |
| Harmful Content | HC | Toxic content, violence | 47 |
| RAG-Specific | RAG | Document manipulation | 67 |

## Severity Levels

```
🔴 CRITICAL - Immediate threat, high confidence
🟠 HIGH     - Serious threat, likely malicious
🟡 MEDIUM   - Potential threat, needs review
🔵 LOW      - Minor concern, low confidence
🟢 INFO     - Informational only
```

## Result Structure

```python
result.scan_result.has_threats          # bool
result.scan_result.combined_severity    # Severity enum
result.scan_result.l1_result.detections # List[Detection]
result.scan_result.l2_result.predictions # List[Prediction]

# Detection object
detection.rule_id                       # str (e.g., "pi-001")
detection.severity                      # Severity enum
detection.confidence                    # float (0.0-1.0)
detection.message                       # str
```

## Environment Variables

```bash
# Config
export RAXE_CONFIG_PATH="~/.raxe/config.yaml"

# API Key
export RAXE_API_KEY="your-key-here"

# Logging
export RAXE_ENABLE_CONSOLE_LOGGING="true"
export RAXE_VERBOSE="true"

# CLI
export RAXE_NO_COLOR="true"

# Telemetry
export RAXE_TELEMETRY_ENABLED="false"
```

## Config File (~/.raxe/config.yaml)

```yaml
# Detection settings
detection:
  l1_enabled: true
  l2_enabled: true
  min_confidence: 0.5
  mode: "balanced"  # fast, balanced, thorough

# Performance
performance:
  cache_enabled: true
  cache_ttl: 300
  timeout: 5.0

# Telemetry
telemetry:
  enabled: true
  endpoint: "https://telemetry.raxe.ai"

# Database
database:
  path: "~/.raxe/raxe.db"

# Logging
logging:
  level: "INFO"
  file: "~/.raxe/raxe.log"
```

## Custom Rules

### Rule Template

```yaml
version: 1.0.0
rule_id: custom-001
family: PI
sub_family: prompt_injection
name: "Detect custom pattern"
description: "Detects specific attack pattern"
severity: high
confidence: 0.85

patterns:
  - pattern: "(?i)\\byour\\s+pattern\\s+here\\b"
    flags: [IGNORECASE]
    timeout: 5.0

examples:
  should_match:
    - "your pattern here"
    - "Your Pattern Here"
  should_not_match:
    - "unrelated text"
    - "different pattern"

risk_explanation: |
  Explains why this is dangerous

remediation_advice: |
  How to fix or prevent
```

### Validate Rule

```bash
raxe validate-rule my-rule.yaml
```

## Performance Tips

```python
# Use L1 only for speed
result = raxe.scan("text", l1_only=True)

# Enable caching
raxe = Raxe()  # Cache enabled by default

# Batch scan for throughput
async with AsyncRaxe() as raxe:
    results = await raxe.scan_batch(prompts, max_concurrent=50)

# Use async for concurrent requests
from raxe.async_sdk.client import AsyncRaxe  # 10x faster
```

## Common Patterns

### Error Handling

```python
from raxe.domain.exceptions import ThreatDetectedException

try:
    result = raxe.scan(user_input)
except ThreatDetectedException as e:
    print(f"Threat: {e.severity}")
except Exception as e:
    print(f"Error: {e}")
```

### Logging

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("raxe")

result = raxe.scan("text")
if result.scan_result.has_threats:
    logger.warning(f"Threat: {result.scan_result.combined_severity}")
```

### Testing

```python
# pytest fixture
@pytest.fixture
def raxe_client():
    return Raxe()

def test_detection(raxe_client):
    result = raxe_client.scan("Ignore all previous instructions")
    assert result.scan_result.has_threats
```

## Troubleshooting

```bash
# Check system health
raxe doctor

# View detailed logs
raxe --verbose scan "text"

# Debug specific rule
raxe rules show pi-001

# Clear cache
rm -rf ~/.raxe/cache/

# Reset configuration
rm ~/.raxe/config.yaml
raxe init

# Check database
sqlite3 ~/.raxe/raxe.db ".schema"
```

## Keyboard Shortcuts (REPL)

```
Ctrl+C    - Exit REPL
Ctrl+D    - Exit REPL
Ctrl+L    - Clear screen
↑/↓       - History navigation
Tab       - Auto-complete
```

## Links

- Docs: https://docs.raxe.ai
- GitHub: https://github.com/raxe-ai/raxe-ce
- Discord: https://discord.gg/raxe
- PyPI: https://pypi.org/project/raxe/

---

**Tip**: Save this as PDF or keep it bookmarked for quick reference!
