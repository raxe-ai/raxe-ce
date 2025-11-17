# RAXE Brand Style Guide

## Brand Overview

**Mission**: Make AI safer for everyone through privacy-first threat detection.

**Vision**: Every LLM application protected by open, transparent security.

**Positioning**: "Snort for AI prompts" – Real-time threat detection for LLM applications

## Brand Personality

- **Technical**: Precise, data-driven, evidence-based
- **Trustworthy**: Privacy-first, transparent, open source
- **Developer-Friendly**: Simple, fast, pragmatic
- **Proactive**: Security before incidents, prevention over cure
- **Community-Driven**: Open, collaborative, inclusive

## Visual Identity

### Logo

#### ASCII Logo (Terminal/CLI)
```
╔═══════════════════════════════╗
║   ██▀▀▀ ▄▀▀▄ ▀▄ ▄▀ ██▀▀▀      ║
║   ██▄▄  █▄▄█  ▄█▄  ██▄▄       ║
║   ██ ▀▀ █  █ ▀▀ ▀▀ ██▄▄▄      ║
║                               ║
║   AI Security Engine          ║
╚═══════════════════════════════╝
```

**Usage:**
- CLI welcome screens
- Terminal output headers
- Monospace contexts

#### Compact Logo
```
██ RAXE ██ AI Security
```

**Usage:**
- CLI command headers
- Minimal contexts
- Progress indicators

### Color Palette

#### Primary Colors

**Indigo (#4F46E5)** - Trust & Security
- Primary brand color
- Buttons, links, highlights
- WCAG AA compliant on white

**Deep Blue (#1E40AF)** - Reliability
- Headers, titles
- Dark mode primary
- Technical authority

#### Severity Colors

**Critical Red (#DC2626)** - `#DC2626`
- Critical threats
- Urgent warnings
- Stop actions

**High Orange (#F59E0B)** - `#F59E0B`
- High severity
- Important warnings
- Caution states

**Medium Yellow (#FCD34D)** - `#FCD34D`
- Medium severity
- General warnings
- Review needed

**Low Blue (#3B82F6)** - `#3B82F6`
- Low severity
- Informational
- Safe to proceed

**Info Green (#10B981)** - `#10B981`
- Success states
- Safe content
- Positive feedback

#### Neutral Colors

**Slate Gray (#64748B)** - Text/UI
- Body text: #1E293B (slate-900)
- Secondary text: #475569 (slate-600)
- Borders: #CBD5E1 (slate-300)
- Background: #F8FAFC (slate-50)

### Typography

#### Monospace (Terminal/CLI)
**Family**: System default monospace
- macOS: SF Mono, Menlo
- Linux: DejaVu Sans Mono, Liberation Mono
- Windows: Consolas, Courier New

**Usage:**
- All CLI output
- Code blocks
- Terminal interfaces
- ASCII art

#### Sans-Serif (Documentation/Web)
**Family**: Inter, system-ui, -apple-system, sans-serif

**Sizes:**
- H1: 36px / 2.25rem (Bold)
- H2: 30px / 1.875rem (SemiBold)
- H3: 24px / 1.5rem (SemiBold)
- H4: 20px / 1.25rem (Medium)
- Body: 16px / 1rem (Regular)
- Small: 14px / 0.875rem (Regular)
- Code: 14px / 0.875rem (Mono)

### Iconography

#### Severity Icons
- 🔴 Critical - Red circle
- 🟠 High - Orange circle
- 🟡 Medium - Yellow circle
- 🔵 Low - Blue circle
- 🟢 Safe/Info - Green circle

#### Status Icons
- ✅ Success / Safe
- ❌ Failure / Blocked
- ⚠️  Warning / Caution
- 🔍 Scanning / Detection
- 🛡️ Protected / Security
- ⚡ Performance / Fast
- 🔒 Privacy / Locked
- 📊 Analytics / Stats
- 🎯 Accuracy / Precision
- 🚀 Launch / Deploy

#### Feature Icons
- 🕵️ Threat Detection
- 📈 Tracking / Trends
- 🧩 Integration
- 🎮 Gamification
- 🔥 Streak / Active
- ⭐ Achievement
- 🏆 Top Tier

**Guidelines:**
- Use sparingly in documentation
- Never in formal/enterprise contexts
- Appropriate for tutorials, READMEs
- Always provide text alternative

## Writing Style

### Tone of Voice

#### Documentation (Formal)
```markdown
✅ Good:
"RAXE scans LLM interactions for security threats including prompt
injection, jailbreaks, and PII leaks. All detection occurs locally
on your machine."

❌ Avoid:
"RAXE is totally awesome! It catches all the bad stuff that hackers
try to do to your AI! 🚀🔥"
```

#### README/Marketing (Friendly-Professional)
```markdown
✅ Good:
"Get started in 60 seconds. Install, initialize, and start protecting
your LLM applications."

❌ Avoid:
"It's super easy and anyone can do it!"
```

#### CLI Output (Concise)
```markdown
✅ Good:
"⚠️  CRITICAL threat detected - Prompt Injection (confidence: 95%)"

❌ Avoid:
"Oh no! We found something really bad in your prompt that could be
dangerous!"
```

### Writing Guidelines

**Do:**
- Use active voice
- Be specific and concrete
- Provide examples
- Explain "why" not just "how"
- Use industry terminology correctly
- Include code examples
- Link to related documentation

**Don't:**
- Use marketing fluff
- Make unsubstantiated claims
- Use all caps (except: LLM, API, CLI, PII)
- Overuse exclamation marks
- Use "simply" or "just" (condescending)
- Assume knowledge levels

### Terminology

**Standard Terms:**
- LLM (not AI, not GPT)
- Prompt injection (lowercase, two words)
- Jailbreak (one word)
- PII (Personal Identifiable Information)
- Threat detection (not attack detection)
- Privacy-first (hyphenated)
- Open source (two words)

**Product Names:**
- RAXE (all caps)
- RAXE Community Edition or RAXE CE
- AsyncRaxe (camelCase)
- RaxeOpenAI (camelCase)

**Avoid:**
- "Bulletproof" (unrealistic)
- "Unhackable" (impossible)
- "Military-grade" (meaningless)
- "Enterprise-ready" (use specifics instead)
- "Revolutionary" (hyperbolic)

## Code Examples

### Style Consistency

```python
# ✅ Good: Clear, commented, realistic
from raxe import Raxe

raxe = Raxe()
result = raxe.scan(user_input)

if result.scan_result.has_threats:
    # Log the threat and block request
    logger.warning(f"Threat: {result.scan_result.combined_severity}")
    raise HTTPException(status_code=400, detail="Threat detected")
```

```python
# ❌ Avoid: Incomplete, no context
raxe.scan(text)
```

### Code Block Guidelines

**Always include:**
- Language identifier for syntax highlighting
- Comments explaining non-obvious code
- Complete, runnable examples
- Import statements
- Error handling where relevant

**Format:**
````markdown
```python
from raxe import Raxe

# Initialize client
raxe = Raxe()

# Scan user input
result = raxe.scan("user text here")
```
````

## Marketing Materials

### Taglines

**Primary**: "Snort for AI prompts"
**Secondary**: "Privacy-first threat detection for LLM applications"
**Alternative**: "Real-time AI security, running locally"

### Key Messages

**Privacy:**
> "All scanning happens locally. Your prompts never leave your machine. Zero vendor lock-in."

**Performance:**
> "Sub-10ms scan latency. Production-ready performance. Scales to thousands of requests per second."

**Developer Experience:**
> "One line of code. 60 seconds to start. Works with OpenAI, Anthropic, LangChain."

**Community:**
> "Open source, community-driven, transparent. 460+ detection rules, continuously improving."

### Elevator Pitch (30 seconds)

> "RAXE is privacy-first threat detection for LLM applications. It scans prompts and responses
> for security threats like prompt injection, jailbreaks, and PII leaks—all running locally on
> your machine in under 10 milliseconds. It's open source, works with any LLM provider, and
> takes just one line of code to integrate."

### Value Propositions by Audience

**Developers:**
- One-line integration
- Fast (<10ms)
- Works offline
- Multiple integration patterns

**Security Teams:**
- Privacy-preserving telemetry
- Real-time threat visibility
- Compliance-ready
- No vendor lock-in

**Enterprises:**
- Local deployment
- Production-ready
- Comprehensive logging
- Open source (auditable)

## Social Media

### Hashtags

**Primary**: #AISecurityRaxe, #RAXE
**Industry**: #AISecure, #LLMSecurity, #PromptInjection
**Tech**: #OpenSource, #Python, #DevSecOps
**Audience**: #AI, #MachineLearning, #Cybersecurity

### Post Style

**Twitter/X (280 chars):**
```
🛡️ New: RAXE 0.0.2 released!

✅ 460 detection rules
⚡ <10ms scan latency
🔒 100% local, privacy-first
🆓 Free & open source

Protect your LLM apps in 60 seconds.

pip install raxe

Docs: https://docs.raxe.ai
```

**LinkedIn (Professional):**
```
We're excited to announce RAXE Community Edition - privacy-first threat
detection for LLM applications.

RAXE helps developers and security teams detect prompt injection,
jailbreaks, and PII leaks in real-time, with all scanning happening
locally on your infrastructure.

Key features:
• Sub-10ms scan latency
• 460+ community-maintained detection rules
• Works with OpenAI, Anthropic, LangChain
• 100% free and open source

Built for developers who care about security without sacrificing privacy.

Learn more: https://raxe.ai
```

## Badge Design

### GitHub Badges

```markdown
![Tests](https://img.shields.io/github/workflow/status/raxe-ai/raxe-ce/Tests?label=tests&style=flat-square)
![Coverage](https://img.shields.io/codecov/c/github/raxe-ai/raxe-ce?style=flat-square)
![Python](https://img.shields.io/badge/python-3.10+-blue?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-yellow?style=flat-square)
```

**Style**: flat-square (modern, clean)
**Colors**: Match brand palette where possible

### Custom Badges

**Protected by RAXE:**
```markdown
[![Protected by RAXE](https://img.shields.io/badge/Protected_by-RAXE-4F46E5?style=for-the-badge&logo=shield)](https://raxe.ai)
```

**Scans Performed:**
```markdown
[![RAXE Scans](https://img.shields.io/badge/RAXE_Scans-1M+-10B981?style=flat-square)](https://raxe.ai)
```

## Documentation Design

### Admonitions (Callouts)

**Note (Informational):**
```markdown
> **Note**: All scanning happens locally. Your prompts never leave your machine.
```

**Warning (Caution):**
```markdown
> ⚠️  **Warning**: This configuration disables L2 detection. Only recommended for
> latency-critical applications.
```

**Tip (Helpful):**
```markdown
> 💡 **Tip**: Enable caching for frequently scanned prompts to improve performance.
```

**Security (Critical):**
```markdown
> 🔒 **Security**: Never commit API keys to version control. Use environment
> variables or secret management.
```

### Code Documentation

```python
def scan(self, text: str) -> ScanPipelineResult:
    """
    Scan text for security threats.

    This method executes the full detection pipeline including L1 rule-based
    detection and L2 ML-based prediction. Results are cached by default.

    Args:
        text: The text to scan (user prompt, LLM response, etc.)

    Returns:
        ScanPipelineResult containing detections and metadata

    Raises:
        ThreatDetectedException: If block_on_threat=True and threats found
        ValueError: If text is empty or None

    Example:
        >>> raxe = Raxe()
        >>> result = raxe.scan("Ignore all previous instructions")
        >>> if result.scan_result.has_threats:
        ...     print(f"Threat: {result.scan_result.combined_severity}")
    """
```

## File Naming Conventions

**Documentation:**
- `UPPERCASE.md` - Important files (README, CONTRIBUTING, SECURITY)
- `lowercase-with-hyphens.md` - Regular docs
- `api/` - API reference
- `guides/` - How-to guides

**Code:**
- `lowercase_with_underscores.py` - Python files
- `PascalCase` - Class names
- `snake_case` - Functions, variables
- `SCREAMING_SNAKE_CASE` - Constants

## Accessibility

### Color Contrast
All color combinations must meet WCAG AA standards:
- Normal text: 4.5:1 contrast ratio
- Large text (18pt+): 3:1 contrast ratio
- UI components: 3:1 contrast ratio

### Alt Text
All images must have descriptive alt text:
```markdown
![RAXE architecture diagram showing data flow from user input through
L1 and L2 detection layers to final scan result](architecture.png)
```

### CLI Accessibility
- Support `--no-color` flag
- Provide text alternatives to icons
- Use semantic CLI output (parseable)
- Support screen readers via plain text mode

## Legal/Compliance

### Copyright Notice
```
Copyright © 2025 RAXE Team
Released under the MIT License
```

### License Mention
Always reference MIT license in:
- README
- Package metadata
- Documentation footer
- Source code headers (optional)

### Privacy Statement
Include in relevant contexts:
> "RAXE is privacy-first. All scanning happens locally. Only anonymized
> SHA-256 hashes are transmitted if telemetry is enabled. Never your prompts."

## Contact & Links

**Official Channels:**
- Website: https://raxe.ai
- Documentation: https://docs.raxe.ai
- GitHub: https://github.com/raxe-ai/raxe-ce
- Discord: https://discord.gg/raxe
- Twitter/X: [@raxe_ai](https://twitter.com/raxe_ai)
- Email: community@raxe.ai

**Support:**
- Community: Discord, GitHub Discussions
- Security: security@raxe.ai
- Conduct: conduct@raxe.ai

---

**Version**: 1.0
**Last Updated**: 2025-11-17
**Maintainer**: RAXE Team
