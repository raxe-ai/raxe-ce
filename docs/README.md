<div align="center">
  <img src="https://github.com/raxe-ai/raxe-ce/blob/main/docs/assets/logo-name-only.png?raw=true" alt="RAXE" width="400"/>

  <h1>RAXE Documentation</h1>

  <p>Welcome to the RAXE Community Edition documentation. This guide will help you understand, integrate, and contribute to RAXE's privacy-first AI security platform.</p>
</div>

## Quick Navigation

### Getting Started
- [Quick Start Guide](../QUICKSTART.md) - Get up and running in 60 seconds
- [Installation](getting-started.md#installation) - Install RAXE via pip or uv
- [Configuration](configuration.md) - Configure RAXE for your use case
- [First Scan](getting-started.md#your-first-scan) - Run your first threat detection

### Core Documentation
- [Architecture](architecture.md) - System design and technical decisions
- [API Reference](api_reference.md) - Complete API documentation
- [Error Codes](ERROR_CODES.md) - Comprehensive error reference

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
- [Troubleshooting](troubleshooting.md) - Common issues and solutions

## Documentation Structure

```
docs/
├── README.md (you are here)
│
├── Getting Started
│   ├── getting-started.md - Complete getting started guide
│   ├── configuration.md - Configuration guide
│   └── troubleshooting.md - Common issues
│
├── Core Documentation
│   ├── architecture.md - System architecture
│   ├── api_reference.md - API documentation
│   ├── ERROR_CODES.md - Error reference
│   └── api/ - Detailed API docs
│
├── Integration Examples
│   ├── examples/
│   │   ├── basic-usage.md - Simple integration
│   │   └── openai-integration.md - OpenAI wrapper
│   ├── CUSTOM_RULES.md - Rule development guide
│   └── POLICIES.md - Policy configuration
│
├── Advanced Topics
│   ├── async-guide.md - Async SDK usage
│   └── performance/
│       └── tuning_guide.md - Performance optimization
│
└── Development
    ├── development.md - Developer guide
    └── plugins/ - Plugin development
```

## By Use Case

### I want to...

**Get started quickly**
[Quick Start Guide](../QUICKSTART.md)

**Integrate RAXE into my Python app**
[Python SDK Examples](examples/basic-usage.md)

**Protect my OpenAI/Anthropic API calls**
[LLM Client Wrappers](examples/openai-integration.md)

**Create custom detection rules**
[Custom Rules Guide](CUSTOM_RULES.md)

**Understand how RAXE works**
[Architecture Documentation](architecture.md)

**Optimize performance**
[Performance Tuning](performance/tuning_guide.md)

**Contribute to RAXE**
[Contributing Guide](../CONTRIBUTING.md)

**Troubleshoot an issue**
[Troubleshooting Guide](troubleshooting.md)

## Key Concepts

### Threat Detection

RAXE uses a **dual-layer detection system**:

- **L1 (Rule-Based)**: Fast pattern matching with 460+ curated YAML rules
- **L2 (ML-Based)**: Adaptive detection for obfuscated and novel attacks

See [Architecture](architecture.md#dual-layer-detection-system) for details.

### Privacy-First Design

All scanning happens **locally** on your machine:

- No raw prompts transmitted to cloud (verifiable in code)
- Telemetry sends detection metadata, API key, prompt hash, and performance metrics
- Never sends raw prompt text, matched text, rule patterns, or end-user identifiers
- Works 100% offline with zero degradation

See [Architecture](architecture.md#privacy-first-architecture) for details.

### Detection Families

RAXE detects 7 threat families:

| Family | Description |
|--------|-------------|
| **PI** | Prompt Injection |
| **JB** | Jailbreak Attempts |
| **PII** | Personal Identifiable Information |
| **CMD** | Command Injection |
| **ENC** | Encoding/Obfuscation |
| **HC** | Harmful Content |
| **RAG** | RAG-Specific Attacks |

See [Custom Rules](CUSTOM_RULES.md) for rule development.

## Quick Reference

### Installation

```bash
pip install raxe
raxe init
raxe doctor  # Verify setup
```

### Basic Usage

```python
from raxe import Raxe

raxe = Raxe()
result = raxe.scan("Ignore all previous instructions")

# Clean, flat API
if result.has_threats:
    print(f"Threat detected: {result.severity}")
    for detection in result.detections:
        print(f"  - {detection.rule_id}: {detection.severity}")
else:
    print("Safe to proceed")

# Boolean evaluation - True when safe
if result:
    process_safe_input()
```

### CLI Commands

```bash
# Scan text
raxe scan "your text here"

# Interactive mode
raxe repl

# View rules
raxe rules list

# Check system health
raxe doctor

# View stats
raxe stats
```

## Additional Resources

### Community
- [GitHub Discussions](https://github.com/raxe-ai/raxe-ce/discussions) - Ask questions, share ideas
- [Slack Community](https://join.slack.com/t/raxeai/shared_invite/zt-3kch8c9zp-A8CMJYWQjBBpzV4KNnAQcQ) - Real-time chat
- [GitHub Issues](https://github.com/raxe-ai/raxe-ce/issues) - Bug reports and features

### Support
- [Troubleshooting Guide](troubleshooting.md) - Common issues
- [FAQ](../FAQ.md) - Frequently asked questions
- [Email Support](mailto:community@raxe.ai) - Direct support

## Contributing to Documentation

Documentation improvements are always welcome! See our [Contributing Guide](../CONTRIBUTING.md) for:

- How to submit documentation fixes
- Documentation style guidelines
- Adding new examples

---

**Remember:** RAXE exists to make AI safer through transparency, not hype. Every piece of documentation should help you understand, verify, and trust the system.

**Happy building!**
