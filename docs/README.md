# RAXE Documentation

Welcome to the RAXE Community Edition documentation. This guide will help you understand, integrate, and contribute to RAXE's privacy-first AI security platform.

## Quick Navigation

### Getting Started
- [Quick Start Guide](quickstart.md) - Get up and running in 60 seconds
- [Installation](quickstart.md#installation) - Install RAXE via pip or uv
- [Configuration](configuration.md) - Configure RAXE for your use case
- [First Scan](quickstart.md#your-first-scan) - Run your first threat detection

### Core Documentation
- [Architecture](architecture.md) - System design and technical decisions
- [API Reference](api-reference.md) - Complete API documentation
- [CLI Reference](cli-reference.md) - Command-line interface guide
- [Configuration Guide](configuration.md) - Detailed configuration options

### Integration Guides
- [Python SDK](examples/basic-usage.md) - Integrate RAXE into Python applications
- [OpenAI Integration](examples/openai-integration.md) - Protect OpenAI API calls
- [Framework Integrations](examples/) - FastAPI, Flask, Django, Streamlit examples
- [Custom Rules](CUSTOM_RULES.md) - Create your own detection rules

### Advanced Topics
- [ML Models](advanced/ml-models.md) - Understanding L2 detection
- [Performance Tuning](PERFORMANCE_TUNING.md) - Optimize for your workload
- [Plugin Development](plugins/plugin_development_guide.md) - Extend RAXE with plugins
- [Security Best Practices](advanced/security.md) - Deployment security

### Development
- [Development Guide](development.md) - Set up development environment
- [Contributing](../CONTRIBUTING.md) - How to contribute to RAXE
- [Testing](development.md#testing) - Run and write tests
- [Troubleshooting](troubleshooting.md) - Common issues and solutions

## Documentation Structure

```
docs/
├── README.md (you are here)
│
├── Getting Started
│   ├── quickstart.md - 60-second quick start
│   ├── configuration.md - Configuration guide
│   └── troubleshooting.md - Common issues
│
├── Core Documentation
│   ├── architecture.md - System architecture
│   ├── api-reference.md - API documentation
│   └── cli-reference.md - CLI commands
│
├── Integration Examples
│   ├── examples/
│   │   ├── basic-usage.md - Simple integration
│   │   ├── openai-integration.md - OpenAI wrapper
│   │   └── custom-rules.md - Custom detection rules
│   └── CUSTOM_RULES.md - Rule development guide
│
├── Advanced Topics
│   └── advanced/
│       ├── ml-models.md - ML detection details
│       ├── performance-tuning.md - Optimization
│       └── security.md - Security hardening
│
└── Development
    ├── development.md - Developer guide
    ├── plugins/ - Plugin development
    └── api/ - Detailed API docs
```

## By Use Case

### I want to...

**Get started quickly**
→ [Quick Start Guide](quickstart.md)

**Integrate RAXE into my Python app**
→ [Python SDK Examples](examples/basic-usage.md)

**Protect my OpenAI/Anthropic API calls**
→ [LLM Client Wrappers](examples/openai-integration.md)

**Add RAXE to my web framework**
→ [Framework Examples](../examples/) (FastAPI, Flask, Django)

**Create custom detection rules**
→ [Custom Rules Guide](CUSTOM_RULES.md)

**Understand how RAXE works**
→ [Architecture Documentation](architecture.md)

**Optimize performance**
→ [Performance Tuning](PERFORMANCE_TUNING.md)

**Contribute to RAXE**
→ [Contributing Guide](../CONTRIBUTING.md)

**Report a security issue**
→ [Security Policy](../SECURITY.md)

**Troubleshoot an issue**
→ [Troubleshooting Guide](troubleshooting.md)

## Documentation Principles

This documentation follows RAXE's core values:

1. **Transparency** - Complete, honest information about capabilities and limitations
2. **Education** - Teach the "why" behind the "how"
3. **Accessibility** - Clear examples for developers of all levels
4. **Code-First** - Working code examples, not just descriptions
5. **Time to Value** - Quick starts get you productive in <60 seconds

## Key Concepts

### Threat Detection

RAXE uses a **dual-layer detection system**:

- **L1 (Rule-Based)**: Fast pattern matching with 460+ curated YAML rules
- **L2 (ML-Based)**: Adaptive detection for obfuscated and novel attacks

See [Architecture](architecture.md#dual-layer-detection-system) for details.

### Privacy-First Design

All scanning happens **locally** on your machine:

- No prompts transmitted to cloud (verifiable in code)
- Optional telemetry sends only SHA-256 hashes
- Works 100% offline with zero degradation

See [Architecture](architecture.md#privacy-first-architecture) for details.

### Detection Families

RAXE detects 7 threat families:

| Family | Description | Rules |
|--------|-------------|-------|
| **PI** | Prompt Injection | 59 rules |
| **JB** | Jailbreak Attempts | 77 rules |
| **PII** | Personal Identifiable Information | 112 rules |
| **CMD** | Command Injection | 65 rules |
| **ENC** | Encoding/Obfuscation | 70 rules |
| **HC** | Harmful Content | 65 rules |
| **RAG** | RAG-Specific Attacks | 12 rules |

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

if result.scan_result.has_threats:
    print(f"Threat detected: {result.scan_result.combined_severity}")
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
- [Discord Community](https://discord.gg/raxe) - Real-time chat
- [GitHub Issues](https://github.com/raxe-ai/raxe-ce/issues) - Bug reports and features

### Research & Learning
- [OWASP LLM Top 10](https://owasp.org/www-project-top-ten/) - LLM security risks
- [Prompt Injection Research](https://github.com/raxe-ai/raxe-ce/discussions) - Latest research
- [Security Blog](https://raxe.ai/blog) - Articles and case studies

### Support
- [Troubleshooting Guide](troubleshooting.md) - Common issues
- [FAQ](../README.md#-faq) - Frequently asked questions
- [Email Support](mailto:community@raxe.ai) - Direct support

## Contributing to Documentation

Documentation improvements are always welcome! See our [Contributing Guide](../CONTRIBUTING.md) for:

- How to submit documentation fixes
- Documentation style guidelines
- Adding new examples
- Translating documentation

## Documentation Roadmap

We're continuously improving our documentation:

**Current (v0.1)**
- ✅ Quick start guide
- ✅ Architecture documentation
- ✅ API reference
- ✅ Framework examples

**Coming Soon (v0.2)**
- 📝 Video tutorials
- 📝 Interactive documentation
- 📝 Jupyter notebook examples
- 📝 Performance benchmarking guide
- 📝 Multi-language support (TypeScript, Go)

**Future (v1.0+)**
- 📝 Enterprise deployment guide
- 📝 Compliance documentation (SOC 2, GDPR)
- 📝 Advanced customization cookbook
- 📝 Migration guides

## Feedback

Have suggestions for improving our documentation?

- Open an [issue](https://github.com/raxe-ai/raxe-ce/issues) with the `documentation` label
- Submit a [pull request](https://github.com/raxe-ai/raxe-ce/pulls) with improvements
- Join the discussion in our [Discord](https://discord.gg/raxe)

---

**Remember**: RAXE exists to make AI safer through transparency, not hype. Every piece of documentation should help you understand, verify, and trust the system.

**Happy building! 🛡️**
