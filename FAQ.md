<div align="center">
  <img src="https://github.com/raxe-ai/raxe-ce/blob/main/docs/assets/logo-name-only.png?raw=true" alt="RAXE Logo" width="400"/>

  <h1>FAQ</h1>
  <p><em>Everything you need to know about RAXE Community Edition</em></p>
</div>

---

## General Questions

### Is RAXE really free?

**Yes, forever!** RAXE Community Edition will always remain free with:
- 515+ detection rules shared with the community
- L2 CPU-based ML classifier
- Privacy-first local scanning
- CLI tool and Python SDK

There are no hidden costs, trials, or feature time-bombs. Community Edition is genuinely free forever.

**Need enterprise features?** RAXE Enterprise includes 1000+ advanced rules, GPU-accelerated classifiers, cloud dashboards, team collaboration, SSO, compliance reporting, and SLA. [Learn more →](https://raxe.ai/enterprise)

### Does RAXE work offline?

**Absolutely!** All scanning happens locally on your device. RAXE is designed with a privacy-first architecture where:
- All threat detection happens on your machine
- No internet connection required for scanning
- Pro users can disable telemetry for 100% offline operation
- Your prompts never leave your device

Perfect for air-gapped environments, sensitive data processing, or privacy-conscious applications.

### How does RAXE compare to other AI security tools?

RAXE Community Edition is fundamentally different from most AI security solutions:

| Feature | RAXE Community | Typical Solutions |
|---------|----------------|-------------------|
| **Detection Rules** | 515+ community rules | Closed source, proprietary |
| **Privacy** | Local-first, your data stays on device | Cloud-only, sends prompts to vendor |
| **Transparency** | Detection rules shared with community | Black-box "trust us" approach |
| **Education** | Explains how attacks work | Just blocks, no learning |
| **Vendor Lock-in** | None, works 100% offline | Tight ecosystem dependency |
| **Cost** | **Free forever** | Subscription required |

**Bottom line:** RAXE prioritizes transparency, privacy, and education over marketing hype.

**Need more?** RAXE Pro and Enterprise offer advanced features. [Compare editions →](https://raxe.ai/pricing)

### Why "instrument panel for LLMs"?

Just like a car's dashboard shows you what's happening under the hood (speed, fuel, engine temperature), RAXE gives you **visibility** into LLM security threats in real-time.

You wouldn't drive a car blindfolded – why run LLMs without monitoring? RAXE provides:
- Real-time threat detection indicators
- Severity levels and confidence scores
- Historical analytics and trends
- Actionable insights for defense

**Visibility enables control.** That's the RAXE philosophy.

---

## Technical Questions

### What LLM providers are supported?

**Currently supported:**
- ✅ **OpenAI** - Drop-in wrapper (`RaxeOpenAI`)
- ✅ **Anthropic** - Claude wrapper (`RaxeAnthropic`)
- ✅ **LangChain** - Callback handler integration
- ✅ **Direct SDK** - Universal integration for any provider

**Coming soon:**
- Cohere
- Ollama (local models)
- Hugging Face Inference API
- Azure OpenAI
- Google PaLM/Gemini
- AWS Bedrock

Want support for a specific provider? [Request it here →](https://github.com/raxe-ai/raxe-ce/discussions)

### How accurate is the detection?

RAXE uses a **dual-layer detection system** with complementary strengths:

**L1 Rule-Based Detection:**
- **~95% precision** on known attack patterns
- Extremely fast (<1ms per scan)
- Zero false positives on well-crafted rules
- 515+ curated rules maintained by security researchers

**L2 ML-Based Detection:**
- **~85% recall** on novel/obfuscated attacks
- Catches attacks L1 misses (encoding, obfuscation, new techniques)
- Context-aware anomaly detection
- Continuously improving with community data

**Combined System:**
- **95%+ detection rate** on real-world threats
- **<0.1% false positive rate** in production testing
- Handles evasion techniques (l33t speak, base64, unicode)
- Educational explanations for every detection

**Note:** Accuracy depends on rule quality and configuration. We publish [quarterly accuracy reports](https://raxe.ai/accuracy) with real-world data.

### Can I use RAXE in production?

**Yes!** RAXE is production-ready and designed for high-scale deployments:

**Performance:**
- **<10ms P95 latency** (L1 only)
- **<50ms P95 latency** (L1+L2 combined)
- Handles **1,000+ requests per second**
- Circuit breaker for reliability
- Graceful degradation under load

**Reliability:**
- Comprehensive test suite (5,255 tests)
- Golden file regression tests (prevent accidental changes)
- Fail-safe defaults (monitors first, blocks only when configured)
- Battle-tested in production environments

**Security:**
- REDOS protection (all patterns validated)
- Input sanitization and boundary checks
- No code execution (pure pattern matching)
- Regular security audits

**Best Practices:**
1. Start in **passive monitoring mode** (default ALLOW policy)
2. Monitor detection patterns for 1-2 weeks
3. Tune policies based on your risk tolerance
4. Gradually enable blocking for high-confidence threats
5. Set up alerting and logging infrastructure

Thousands of production requests processed daily with zero outages.

### What programming languages are supported?

**Currently:**
- ✅ **Python 3.10+** (primary SDK)

**Planned:**
- 🔜 **TypeScript/JavaScript** (v1.0)
- 🔜 **Go** (v1.0)
- 🔜 **Rust** (v1.5)
- 🔜 **Java** (v2.0)

**Workarounds today:**
- Use Python SDK via subprocess/FFI bindings
- Call `raxe scan` CLI from any language
- HTTP API wrapper (community contribution)

Want to help build SDKs for other languages? [Join the effort →](https://github.com/raxe-ai/raxe-ce/discussions)

### Does RAXE slow down my application?

**No!** RAXE is designed for **zero-overhead integration**:

**Performance Impact:**
- **L1 scanning:** <1ms per request (negligible overhead)
- **L2 scanning:** ~3-5ms per request (optional, disable if needed)
- **Async telemetry:** Zero blocking (runs in background thread)
- **Batch optimization:** Process 1,000s of requests concurrently

**Optimization Strategies:**
```python
# 1. L1-only mode (fastest)
raxe = Raxe(l2_enabled=False)  # <1ms latency

# 2. Loop for multiple prompts
for prompt in prompts:
    result = raxe.scan(prompt)

# 3. Async batch processing (parallel, using AsyncRaxe)
from raxe import AsyncRaxe
async_raxe = AsyncRaxe()
results = await async_raxe.scan_batch(prompts, max_concurrency=10)  # 10x faster
```

**Real-world impact:** Users report <2% latency increase in production workloads.

### How do I report a security issue?

**🔒 Security vulnerabilities should NEVER be reported publicly.**

**Responsible Disclosure Process:**

1. **Email:** security@raxe.ai with:
   - Detailed description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Your contact information (optional, for credit)

2. **Response Time:**
   - Initial acknowledgment: **<24 hours**
   - Severity assessment: **<72 hours**
   - Fix timeline: Based on severity (critical = days, low = weeks)

3. **Recognition:**
   - Security researchers credited in SECURITY.md
   - Hall of Fame for responsible disclosures
   - Swag and thank-you notes for meaningful contributions

4. **Coordinated Disclosure:**
   - We'll work with you on disclosure timeline
   - Public disclosure only after fix is deployed
   - Security advisories published with proper attribution

See [SECURITY.md](SECURITY.md) for complete policy.

---

## Privacy & Trust

### What data does RAXE collect?

**By default:** RAXE ships with telemetry **enabled by default** to help improve community detection quality. **Pro users** can opt-out via `raxe telemetry disable`.

We collect:

**✅ What we SHARE:**
```json
{
  // Authentication & Identification
  "api_key": "raxe_...",         // Client identification for service access
  "prompt_hash": "sha256:...",   // SHA-256 hash for uniqueness tracking

  // Detection metadata
  "rule_id": "pi-001",           // Which rule triggered
  "severity": "HIGH",            // Threat severity level
  "confidence": 0.95,            // Detection confidence score
  "detection_count": 3,          // Number of detections
  "l1_hit": true,                // L1 detection occurred
  "l2_hit": false,               // L2 detection occurred

  // Performance metrics
  "scan_duration_ms": 4.2,       // Total scan time
  "l1_duration_ms": 1.1,         // L1 processing time
  "l2_duration_ms": 3.1,         // L2 processing time

  // L2 ML metrics
  "l2_metadata": {
    "overall_confidence": 0.92,
    "model_version": "raxe-ml-v2",
    "classification": "ATTACK_LIKELY"
  },

  // Context
  "timestamp": "2025-11-24T10:30:00Z",
  "version": "0.0.1",
  "platform": "darwin"
}
```

**❌ What we NEVER SHARE:**
- ❌ Actual prompt text or responses
- ❌ Matched text or rule patterns
- ❌ End-user identifiers (their IP, their user_id from your app)
- ❌ System prompts or configuration
- ❌ Any customer PII or sensitive data

**Why we share what we share:**
- **API key** - Identifies your client for service access control
- **Prompt hash** - SHA-256 is computationally hard to reverse; enables deduplication
- **Detection metadata** - Improves detection accuracy across the community
- **Performance metrics** - Helps us optimize scan latency

**Verify yourself:** All telemetry code is auditable.

### Can I verify RAXE's privacy claims?

**Yes!** Transparency is our core principle.

**How to verify:**

1. **Run privacy tests:**
   ```bash
   # Automated privacy validation
   pytest tests/unit/infrastructure/test_telemetry.py -v
   pytest tests/integration/test_telemetry_privacy.py -v
   ```

2. **Inspect telemetry in real-time:**
   ```bash
   # Enable debug logging
   export RAXE_LOG_LEVEL=DEBUG
   raxe scan "test prompt"

   # Shows exactly what's sent (if telemetry enabled)
   ```

3. **Network monitoring:**
   ```bash
   # Monitor network traffic (if telemetry enabled)
   tcpdump -i any -A host telemetry.raxe.ai
   ```

4. **Enterprise audits:**
   - Source code available for audit under NDA for enterprise customers
   - Security audits published in [SECURITY.md](SECURITY.md)
   - Quarterly privacy reviews by external researchers

**Trust, but verify.** Privacy is guaranteed, not promised.

### How is RAXE different from proprietary solutions?

| Aspect | RAXE Community | Proprietary Solutions |
|--------|----------------|---------------------|
| **Detection Rules** | 515+ community rules | Closed, can't audit |
| **Privacy** | Local-first, verifiable | Cloud-only, trust required |
| **Detection Logic** | Rules shared with community | Black-box "magic" |
| **Data Handling** | You control everything | Vendor controls your data |
| **Cost** | **Free forever** | Subscription lock-in |
| **Customization** | Propose new rules via GitHub | Limited to vendor API |
| **Vendor Lock-in** | None, works 100% offline | Tight ecosystem dependency |
| **Learning** | Educational explanations | "It works, trust us" |
| **Community** | Driven by researchers | Driven by sales goals |

**RAXE Philosophy:** Transparency over hype. Education over fear. Community over vendors.

---

## Configuration & Policies

### What are policies and how do they work?

**Policies** are the brain of RAXE – they decide how to handle detected threats.

**4 Policy Actions:**
1. **ALLOW** - Passive monitoring (log only, no blocking)
2. **FLAG** - Warning mode (log + alert, request proceeds)
3. **BLOCK** - Enforcement (reject request, raise exception)
4. **LOG** - Silent monitoring (local logging, no telemetry)

**Example Policy:**
```yaml
policies:
  - policy_id: "block-critical-pi"
    name: "Block critical prompt injection"
    conditions:
      - severity: "CRITICAL"
        rule_ids: ["pi-*"]
        min_confidence: 0.9
    action: "BLOCK"
    priority: 100
```

**How it works:**
1. RAXE scans input → finds threats
2. Evaluates policies in priority order (100 → 0)
3. First matching policy wins
4. Executes action (ALLOW/FLAG/BLOCK/LOG)

**Advanced Features:**
- Target specific rules (`pi-001`) or families (`pi-*`)
- L2 ML detections via virtual rules (`l2-context-manipulation`)
- Confidence-based filtering (`min_confidence: 0.9`)
- Severity thresholds (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`)
- Priority-based conflict resolution

**📖 Complete guide:** [docs/POLICIES.md](docs/POLICIES.md)

### Should I start with blocking or monitoring?

**Always start with MONITORING** (passive ALLOW policy). Here's why:

**Phase 1: Monitoring (Week 1-2)**
```yaml
policies:
  - policy_id: "monitor-all"
    name: "Monitor all threats passively"
    conditions: []  # Match everything
    action: "ALLOW"  # Log only, don't block
    priority: 100
```

**What to do:**
- Run RAXE in production with passive monitoring
- Review `raxe stats` daily to see detection patterns
- Identify false positives (legitimate inputs flagged)
- Tune detection rules if needed
- Build confidence in the system

**Phase 2: Selective Blocking (Week 3-4)**
```yaml
policies:
  # Block only CRITICAL threats with high confidence
  - policy_id: "block-critical"
    name: "Block critical threats"
    conditions:
      - severity: "CRITICAL"
        min_confidence: 0.95
    action: "BLOCK"
    priority: 100

  # Continue monitoring everything else
  - policy_id: "monitor-rest"
    name: "Monitor other threats"
    conditions: []
    action: "ALLOW"
    priority: 50
```

**Phase 3: Full Enforcement (Month 2+)**
- Expand blocking to HIGH severity threats
- Fine-tune confidence thresholds
- Add custom rules for your use case
- Set up alerting and incident response

**Best Practice:** Measure twice, block once. Monitoring prevents broken user experiences.

### Can I create custom detection rules?

**Yes!** Custom rules are encouraged and easy to create.

**Step 1: Create Rule File**
```yaml
# my-custom-rule.yaml
version: 1.0.0
rule_id: "custom-001"
family: "PI"  # Prompt Injection
sub_family: "custom"
name: "My custom prompt injection detection"
severity: "HIGH"
confidence: 0.85

patterns:
  - pattern: "(?i)\\bmy\\s+custom\\s+pattern\\b"
    flags: ["IGNORECASE"]

examples:
  should_match:
    - "my custom pattern here"
    - "My Custom Pattern Here"
  should_not_match:
    - "not matching this"
    - "different text"

risk_explanation: |
  Explain why this pattern is dangerous.

remediation_advice: |
  Explain how to defend against this threat.

metrics:
  false_positive_rate: 0.01
  detection_rate: 0.95
```

**Step 2: Validate Rule**
```bash
raxe validate-rule my-custom-rule.yaml
```

Checks for:
- ✅ YAML syntax and schema compliance
- ✅ Pattern safety (no catastrophic backtracking)
- ✅ Sufficient test coverage (5+ examples each)
- ✅ Educational context required

**Step 3: Use Rule**
```bash
# Place in rule pack directory
cp my-custom-rule.yaml ~/.raxe/packs/custom/rules/PI/

# Or specify in config
raxe config set rules.custom_path ~/.raxe/custom-rules/
```

**📖 Complete guide:** [docs/CUSTOM_RULES.md](docs/CUSTOM_RULES.md)

---

## Integration & Development

### How do I integrate RAXE with my framework?

RAXE provides **three integration patterns** for maximum flexibility:

**1. Decorator Pattern (Recommended)**
```python
from raxe import Raxe

raxe = Raxe()

@raxe.protect  # Monitor mode (logs only)
def generate_response(user_input: str) -> str:
    return llm.generate(user_input)

# Or blocking mode (raises exception on threat)
@raxe.protect(block=True)
def secure_generate(user_input: str) -> str:
    return llm.generate(user_input)
```

**2. Direct Scanning**
```python
result = raxe.scan(user_input)

if result.has_threats:
    print(f"Threat detected: {result.severity}")
    # Custom handling logic here
```

**3. LLM Wrappers (Drop-in Replacement)**
```python
# OpenAI
from raxe import RaxeOpenAI
client = RaxeOpenAI(api_key="sk-...")

# Anthropic
from raxe import RaxeAnthropic
client = RaxeAnthropic(api_key="...")

# LangChain
from raxe.sdk.integrations.langchain import RaxeCallbackHandler
handler = RaxeCallbackHandler()
chain = LLMChain(llm=llm, callbacks=[handler])
```

**Framework-Specific Examples:**
- [FastAPI Integration](docs/examples/fastapi-integration.md)
- [Streamlit Integration](docs/examples/streamlit-integration.md)
- [LangChain Integration](docs/examples/langchain-integration.md)
- [Flask Integration](docs/examples/flask-integration.md)

### Can RAXE scan LLM responses?

**Yes, but with important limitations:**

**What RAXE CAN do:**
- ✅ Detect threats in LLM-generated responses
- ✅ Alert/flag unsafe outputs
- ✅ Log response threats for monitoring
- ✅ Provide severity and confidence scores

**What RAXE CANNOT do:**
- ❌ Modify or sanitize LLM responses
- ❌ Prevent unsafe outputs (response already generated)
- ❌ Block responses in real-time (too late)

**Recommended Pattern:**
```python
# Scan response for monitoring
response = llm.generate(prompt)
result = raxe.scan(response)

if not result:  # False when threats detected
    # Log the issue
    logger.warning(f"Unsafe response: {result.severity}")

    # Implement fallback (your responsibility)
    response = "I cannot provide that information. [Policy violation detected]"

return response
```

**Best Practices:**
1. Use response scanning for **monitoring and alerting** only
2. Implement **application-level fallbacks** when threats detected
3. Focus on **input scanning** for prevention (more effective)
4. Train models with safety fine-tuning for better outputs

**Why not modify responses?**
- LLM responses are already generated (can't prevent)
- Modifying text can break formatting, code, JSON, etc.
- False positives could corrupt valid responses
- Better to prevent unsafe prompts upfront

### How do I contribute to RAXE?

**We welcome contributions!** RAXE Community Edition uses a **community-driven** model (not open-source):

**✅ What You Can Contribute:**

**1. Detection Rules**
- Propose new threat detection patterns
- Improve existing rules for better accuracy
- Report false positives/negatives
- See [docs/CUSTOM_RULES.md](docs/CUSTOM_RULES.md)

**2. Documentation**
- Fix typos and improve clarity
- Add tutorials and guides
- Write blog posts and case studies

**3. Bug Reports**
- Report issues with detection accuracy
- Test edge cases and report findings
- Submit false positive/negative reports

**4. Community Support**
- Answer questions in GitHub Discussions
- Help users troubleshoot issues
- Share integration examples

**❌ Code Contributions:**
- Source code is proprietary (not accepting code PRs)
- ML models are proprietary (Enterprise features)

**Submit Detection Rules:**
```bash
# Propose a new rule via GitHub Issues
# Tag with "rule-submission" label
# Community review and validation process
```

**📖 Full guide:** [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Troubleshooting

### RAXE is showing false positives. What should I do?

**False positives happen.** Here's how to handle them:

**Step 1: Verify it's actually a false positive**
```bash
raxe scan "flagged input" --explain
```

Look at the explanation – sometimes it's a real (but subtle) threat.

**Step 2: Adjust confidence thresholds**
```yaml
policies:
  - policy_id: "reduce-fps"
    name: "Require higher confidence"
    conditions:
      - rule_ids: ["rule-causing-fps"]
        min_confidence: 0.95  # Increase threshold
    action: "FLAG"
    priority: 90
```

**Step 3: Create suppression policy**
```yaml
policies:
  - policy_id: "allow-false-positive"
    name: "Suppress known false positive"
    conditions:
      - rule_ids: ["pii-credit-card"]
        max_confidence: 0.7  # Only FPs below this
    action: "ALLOW"
    priority: 100  # Highest priority
```

**Step 4: Report to improve rules**
```bash
# Submit false positive report
raxe report-fp "flagged input" --rule pi-001 --reason "test credit card number"
```

This helps us improve detection accuracy for everyone!

**Step 5: Create custom rule override**
If needed, add a custom rule that matches your specific use case:
```yaml
rule_id: "custom-allow-001"
family: "ALLOW"
name: "Allow specific pattern"
# ... (see CUSTOM_RULES.md)
```

### Installation fails. How do I fix it?

**Common issues and solutions:**

**1. Python version too old**
```bash
# RAXE requires Python 3.10+
python --version  # Check version

# Install Python 3.10+ if needed
# macOS: brew install python@3.10
# Ubuntu: sudo apt install python3.10
# Windows: Download from python.org
```

**2. pip install fails with dependency errors**
```bash
# Upgrade pip first
pip install --upgrade pip setuptools wheel

# Then install RAXE
pip install raxe
```

**3. Permission denied errors**
```bash
# Use user install (no sudo needed)
pip install --user raxe

# Or use virtual environment (recommended)
python -m venv venv
source venv/bin/activate
pip install raxe
```

**4. SSL certificate errors**
```bash
# Update certificates
pip install --upgrade certifi

# Or use trusted host (not recommended)
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org raxe
```

**Still having issues?** [Report it here →](https://github.com/raxe-ai/raxe-ce/issues)

### How do I update RAXE to the latest version?

**Update is simple:**

```bash
# Using pip
pip install --upgrade raxe

# Using uv (faster)
uv pip install --upgrade raxe

# Verify new version
raxe --version
```

**After update:**
```bash
# Regenerate config if needed
raxe init --force

# Check system health
raxe doctor

# Review changelog
raxe changelog
```

**Breaking changes?** Check [CHANGELOG.md](CHANGELOG.md) for migration guides.

---

## Community & Support

### Where can I get help?

**Multiple support channels available:**

1. **📖 Documentation** (Start here!)
   - [Quick Start Guide](QUICKSTART.md)
   - [Complete Documentation](docs/)
   - [API Reference](docs/api-reference.md)
   - [Troubleshooting Guide](docs/troubleshooting.md)

2. **💬 GitHub Discussions** (Community Q&A)
   - Ask questions: [github.com/raxe-ai/raxe-ce/discussions](https://github.com/raxe-ai/raxe-ce/discussions)
   - Share ideas and feedback
   - Vote on feature requests

3. **🐛 GitHub Issues** (Bug reports only)
   - Report bugs: [github.com/raxe-ai/raxe-ce/issues](https://github.com/raxe-ai/raxe-ce/issues)
   - Include: steps to reproduce, expected vs actual behavior, version info

4. **💬 Slack Community** (Real-time chat)
   - Join: [RAXE Slack](https://join.slack.com/t/raxeai/shared_invite/zt-3kch8c9zp-A8CMJYWQjBBpzV4KNnAQcQ)
   - Get help from community members
   - Share best practices

5. **📧 Email Support**
   - General: community@raxe.ai
   - Security: security@raxe.ai (responsible disclosure only)

**Best Practices:**
- Search existing issues/discussions first
- Provide context (version, OS, example code)
- Be respectful and patient
- Help others when you can!

### How can I stay updated on RAXE development?

**Follow along:**

- 🐦 **Twitter/X:** [@raxeai](https://twitter.com/raxeai) - Product updates
- 📰 **Blog:** [raxe.ai/blog](https://raxe.ai/blog) - Deep dives and tutorials
- 💬 **Slack:** [Join RAXE Slack](https://join.slack.com/t/raxeai/shared_invite/zt-3kch8c9zp-A8CMJYWQjBBpzV4KNnAQcQ) - Community discussions
- 📧 **Newsletter:** [raxe.ai/newsletter](https://raxe.ai/newsletter) - Monthly updates
- ⭐ **GitHub:** [Watch releases](https://github.com/raxe-ai/raxe-ce) - Version announcements

**Release Schedule:**
- Minor versions (0.x): Every 4-6 weeks
- Patch versions (0.x.y): As needed for bugs
- Major versions (x.0): Annually

### What's the difference between Community, Pro, and Enterprise?

| Feature | Community | Pro | Enterprise |
|---------|-----------|-----|------------|
| **Detection** | L1 + L2 (515+ rules) | L1-L6 (1000+ rules) | Custom models |
| **Latency** | <10ms P95 | <5ms P95 | <3ms P95 |
| **Deployment** | Local only | Local + Cloud | On-prem + Cloud |
| **Dashboard** | CLI | Web Console | Custom + SSO |
| **Support** | Community | Priority | Dedicated + SLA |
| **Price** | **FREE FOREVER** | $99/month | Custom |

**When to upgrade to Pro:**
- Need cloud dashboards (not CLI logs)
- Scanning >100k prompts/day
- Want L3-L6 advanced detection layers

**When to upgrade to Enterprise:**
- Regulated industries (FinTech, Healthcare, Gov)
- Need on-prem/air-gapped deployment
- Require custom detection models
- Want dedicated security partnership

**Community Edition Commitment:**
- Will **always** remain free
- Local scanning will **never** require cloud services
- Privacy-first architecture is **non-negotiable**
- Core security capabilities never paywalled

**[Join Pro Waitlist →](https://raxe.ai/waitlist) | [Enterprise Contact →](mailto:enterprise@raxe.ai)**

---

## Advanced Topics

### Can I self-host RAXE's telemetry backend?

**Yes!** RAXE's telemetry system is designed to be self-hostable.

**Steps to self-host:**

1. **Clone telemetry server repo** (coming soon)
   ```bash
   git clone https://github.com/raxe-ai/raxe-telemetry-server.git
   cd raxe-telemetry-server
   ```

2. **Deploy with Docker**
   ```bash
   docker-compose up -d
   ```

3. **Configure RAXE to use your server**
   ```yaml
   # ~/.raxe/config.yaml
   telemetry:
     enabled: true
     endpoint: "https://your-telemetry-server.com/v1/telemetry"
     api_key: "your-api-key"
   ```

4. **Verify connection**
   ```bash
   raxe doctor --check-telemetry
   ```

**Benefits:**
- Full control over detection data
- Air-gapped environments supported
- Custom analytics and dashboards
- Compliance requirements met

**Coming in a future release**

### How does L2 ML detection work?

**L2 uses a lightweight ML classifier** to catch threats L1 rules miss.

**Architecture:**
1. **Embedding Model** - Converts text to numeric vectors
2. **Threat Classifier** - Predicts threat type and confidence
3. **Signal Quality Analyzer** - Assesses prediction reliability

**Threat Types Detected:**
- `l2-context-manipulation` - Conversation hijacking
- `l2-semantic-jailbreak` - Subtle jailbreak patterns
- `l2-encoded-injection` - Obfuscated attacks
- `l2-privilege-escalation` - Role elevation attempts
- `l2-data-exfil-pattern` - Data extraction patterns
- `l2-obfuscated-command` - Hidden commands

**Performance:**
- **Inference time:** <5ms on CPU
- **Model size:** ~50MB (ONNX format)
- **Accuracy:** ~85% recall on novel attacks
- **Privacy:** All processing happens locally

**Optional:** L2 can be disabled if you prefer rules-only:
```python
raxe = Raxe(l2_enabled=False)  # L1-only mode
```

**Technical details:** [docs/architecture.md](docs/architecture.md)

### Can I fine-tune RAXE's ML models for my use case?

**Not yet, but coming soon!**

**Planned for v1.0:**
```bash
# Fine-tune on your data
raxe train --dataset my-training-data.jsonl \
           --base-model raxe-ml-v2 \
           --output my-custom-model.onnx

# Use custom model
raxe config set ml.model_path ~/.raxe/models/my-custom-model.onnx
```

**What you'll need:**
- Labeled dataset (threats + benign examples)
- 1,000+ examples minimum (10,000+ recommended)
- Python 3.10+ with ML dependencies (`pip install raxe[ml-training]`)

**Want early access?** [Join the ML beta program →](https://github.com/raxe-ai/raxe-ce/discussions)

---

## Legal & Licensing

### Can I use RAXE in commercial products?

**Yes!** RAXE Community Edition is proprietary software available for free forever.

**You may:**
- ✅ Use for personal, educational, or commercial purposes
- ✅ Integrate into your applications
- ✅ Use in production environments
- ✅ Redistribute as part of your application (with attribution)

**You may NOT:**
- ❌ Modify or reverse engineer the software
- ❌ Extract detection rules for competing products
- ❌ Redistribute modified versions
- ❌ Remove or alter copyright notices

**Requirements:**
- Preserve attribution to RAXE Technologies, Inc.
- Include reference to LICENSE file

**Read the full license:** [LICENSE](LICENSE)

### What happens if RAXE detects something incorrectly?

**RAXE provides detection, not guarantees.** Legal disclaimers:

**License Disclaimer:**
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.

**What this means:**
- RAXE is a **tool to help you**, not a silver bullet
- You're responsible for how you use it
- False positives and false negatives can occur
- No liability for missed threats or incorrect flags

**Best Practices:**
- Use RAXE as **one layer** of defense (defense in depth)
- Implement monitoring and alerting
- Review detection logs regularly
- Test your specific use case thoroughly
- Don't rely solely on automated detection

**RAXE reduces risk but doesn't eliminate it.** Security is a process, not a product.

---

<div align="center">

**Still have questions?**

[Ask in Discussions](https://github.com/raxe-ai/raxe-ce/discussions) | [Join Slack](https://join.slack.com/t/raxeai/shared_invite/zt-3kch8c9zp-A8CMJYWQjBBpzV4KNnAQcQ) | [Email Us](mailto:community@raxe.ai)

**🛡️ Transparency over hype. Education over fear. Community over vendors.**

[Back to README →](README.md)

</div>
