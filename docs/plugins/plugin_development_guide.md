# RAXE Plugin Development Guide

Complete guide to developing custom RAXE plugins for threat detection and actions.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Plugin Types](#plugin-types)
3. [Plugin Lifecycle](#plugin-lifecycle)
4. [Best Practices](#best-practices)
5. [Testing Plugins](#testing-plugins)
6. [Deployment](#deployment)
7. [Troubleshooting](#troubleshooting)

## Quick Start

### Create Your First Plugin

1. **Create plugin directory:**
```bash
mkdir -p ~/.raxe/plugins/my_detector
cd ~/.raxe/plugins/my_detector
```

2. **Create plugin.py:**
```python
from raxe.plugins import DetectorPlugin, PluginMetadata, PluginPriority
from raxe.domain.engine.executor import Detection
from raxe.domain.rules.models import Severity

class MyDetector(DetectorPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="my_detector",
            version="1.0.0",
            author="Your Name",
            description="My custom threat detector",
            priority=PluginPriority.NORMAL,
            requires=["raxe>=1.0.0"],
            tags=["detector", "custom"]
        )

    def on_init(self, config):
        """Initialize plugin with configuration."""
        self.patterns = config.get("patterns", [])

    def detect(self, text, context=None):
        """Detect threats in text."""
        detections = []

        for pattern in self.patterns:
            if pattern in text:
                detections.append(Detection(
                    rule_id=f"custom_{pattern}",
                    severity=Severity.MEDIUM,
                    confidence=0.8,
                    message=f"Pattern '{pattern}' detected"
                ))

        return detections

# REQUIRED: Export plugin instance
plugin = MyDetector()
```

3. **Configure plugin:**
```toml
# ~/.raxe/config.yaml
plugins:
enabled = ["my_detector"]

[plugins.my_detector]
patterns = ["secret", "confidential", "internal"]
```

4. **Test plugin:**
```bash
raxe plugins  # List plugins
raxe scan "This is a secret document"  # Should detect pattern
```

## Plugin Types

### DetectorPlugin

Adds custom detection logic to threat scanning.

**Use Cases:**
- Organization-specific patterns (API keys, URLs)
- Industry-specific compliance (HIPAA, PCI-DSS)
- Custom PII detection
- Proprietary threat signatures

**Interface:**
```python
class DetectorPlugin(RaxePlugin):
    def detect(self, text: str, context: dict = None) -> list[Detection]:
        """Execute custom detection logic."""
        ...

    def get_rules(self) -> list[Rule]:
        """Optional: Provide custom rules."""
        return []
```

**Example:**
```python
class InternalURLDetector(DetectorPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="internal_url_detector",
            version="1.0.0",
            author="Security Team",
            description="Detects internal company URLs",
            priority=PluginPriority.HIGH,
        )

    def on_init(self, config):
        self.internal_domains = config.get("internal_domains", [])

    def detect(self, text, context=None):
        import re
        detections = []

        for domain in self.internal_domains:
            pattern = rf"https?://{re.escape(domain)}\S+"
            if re.search(pattern, text):
                detections.append(Detection(
                    rule_id="internal_url",
                    severity=Severity.HIGH,
                    confidence=0.95,
                    message=f"Internal URL detected: {domain}"
                ))

        return detections

plugin = InternalURLDetector()
```

### ActionPlugin

Performs actions based on scan results.

**Use Cases:**
- Send alerts (Slack, email, PagerDuty)
- Log to SIEM systems
- Trigger webhooks
- Update dashboards
- File quarantine

**Interface:**
```python
class ActionPlugin(RaxePlugin):
    def should_execute(self, result: ScanPipelineResult) -> bool:
        """Determine if action should run."""
        ...

    def execute(self, result: ScanPipelineResult) -> None:
        """Execute action."""
        ...
```

**Example:**
```python
class EmailNotifier(ActionPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="email_notifier",
            version="1.0.0",
            author="IT Team",
            description="Send email alerts for threats",
        )

    def on_init(self, config):
        import smtplib
        self.smtp_host = config["smtp_host"]
        self.smtp_port = config["smtp_port"]
        self.from_addr = config["from_address"]
        self.to_addrs = config["to_addresses"]
        self.min_severity = config.get("min_severity", "HIGH")

    def should_execute(self, result):
        if not result.has_threats:
            return False
        return result.severity >= self.min_severity

    def execute(self, result):
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = f"RAXE Alert: {result.severity} Threat Detected"
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        msg.set_content(f"Detected {result.total_detections} threats")

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as smtp:
            smtp.send_message(msg)

plugin = EmailNotifier()
```

### TransformPlugin

Transforms text before/after scanning.

**Use Cases:**
- Text normalization
- Redaction
- Format conversion
- Result enrichment

**Interface:**
```python
class TransformPlugin(RaxePlugin):
    def transform_input(self, text: str, context: dict = None) -> str:
        """Transform text before scanning."""
        return text

    def transform_output(self, result: ScanPipelineResult) -> ScanPipelineResult:
        """Transform results after scanning."""
        return result
```

## Plugin Lifecycle

### Initialization Flow

```
1. PluginLoader discovers plugins
   ↓
2. Plugin module loaded
   ↓
3. Plugin instance created (plugin = MyPlugin())
   ↓
4. on_init(config) called
   ↓
5. Plugin registered with PluginManager
```

### Scan Execution Flow

```
For each scan:

1. on_scan_start(text, context) - Pre-scan hook
   ↓
2. detect(text, context) - Detector plugins run
   ↓
3. [Core L1+L2 detection happens]
   ↓
4. on_scan_complete(result) - Post-scan hook
   ↓
5. on_threat_detected(result) - If threats found
   ↓
6. should_execute(result) - Action plugins check
   ↓
7. execute(result) - Action plugins run
```

### Shutdown Flow

```
1. on_shutdown() called on all plugins
   ↓
2. Plugins cleanup resources
   ↓
3. PluginManager shuts down
```

## Best Practices

### Performance

**DO:**
- Keep detect() methods fast (<5ms target)
- Cache compiled regex patterns
- Use efficient data structures
- Implement timeouts for external calls

**DON'T:**
- Make synchronous network calls in detect()
- Load large files during detection
- Use expensive algorithms without caching

```python
# GOOD: Compile patterns once
class FastDetector(DetectorPlugin):
    def on_init(self, config):
        self.patterns = [
            re.compile(p) for p in config["patterns"]
        ]

    def detect(self, text, context=None):
        # Uses pre-compiled patterns
        ...

# BAD: Compile on every scan
class SlowDetector(DetectorPlugin):
    def detect(self, text, context=None):
        patterns = [re.compile(p) for p in self.patterns]  # Slow!
        ...
```

### Error Handling

**Always handle errors gracefully:**

```python
def detect(self, text, context=None):
    try:
        # Detection logic
        return self._scan(text)
    except Exception as e:
        # Log error but don't crash
        logger.error(f"Detection failed: {e}")
        return []  # Return empty list
```

### Configuration

**Validate configuration in on_init:**

```python
def on_init(self, config):
    # Validate required fields
    if "webhook_url" not in config:
        raise ValueError("webhook_url is required")

    # Validate types
    if not isinstance(config.get("timeout", 5), (int, float)):
        raise TypeError("timeout must be numeric")

    # Set defaults
    self.timeout = config.get("timeout", 5)
    self.retries = config.get("retries", 3)
```

### Security

**NEVER:**
- Log sensitive data (prompts, API keys)
- Store PII without encryption
- Execute arbitrary code
- Make unvalidated network calls

```python
# GOOD: Hash sensitive data
def execute(self, result):
    logger.info(
        "threat_detected",
        prompt_hash=hashlib.sha256(text.encode()).hexdigest(),
        severity=result.severity
    )

# BAD: Log actual content
def execute(self, result):
    logger.info(f"Threat in: {text}")  # PII LEAK!
```

## Testing Plugins

### Unit Tests

```python
# tests/test_my_detector.py
import pytest
from my_detector.plugin import MyDetector

def test_detect_pattern():
    detector = MyDetector()
    detector.on_init({"patterns": ["secret"]})

    detections = detector.detect("This is a secret")

    assert len(detections) == 1
    assert detections[0].rule_id == "custom_secret"

def test_no_detection():
    detector = MyDetector()
    detector.on_init({"patterns": ["secret"]})

    detections = detector.detect("This is public")

    assert len(detections) == 0
```

### Integration Tests

```bash
# Test with actual RAXE
raxe scan "test text with patterns" --profile

# Check metrics
raxe stats --plugins
```

### Performance Testing

```python
import time

def test_performance():
    detector = MyDetector()
    detector.on_init(config)

    start = time.perf_counter()
    detector.detect("test" * 1000)
    duration = time.perf_counter() - start

    assert duration < 0.005  # <5ms
```

## Deployment

### Directory Structure

```
~/.raxe/plugins/my_plugin/
├── plugin.py          # Main plugin code (REQUIRED)
├── README.md          # Documentation
├── requirements.txt   # Optional Python dependencies
├── config.schema.json # Optional config validation
└── tests/             # Optional tests
```

### Installation

**Option 1: Manual**
```bash
cp -r my_plugin ~/.raxe/plugins/
```

**Option 2: Git**
```bash
cd ~/.raxe/plugins
git clone https://github.com/user/raxe-plugin-name
```

**Option 3: Package (future)**
```bash
raxe plugin install raxe-plugin-name
```

### Configuration

```toml
# ~/.raxe/config.yaml
plugins:
enabled = ["my_plugin"]
timeout_seconds = 5.0

[plugins.my_plugin]
setting1 = "value1"
setting2 = true
```

## Troubleshooting

### Plugin Not Loading

**Check discovery:**
```bash
ls -la ~/.raxe/plugins/my_plugin/
# Should have plugin.py
```

**Check plugin file:**
```bash
cat ~/.raxe/plugins/my_plugin/plugin.py | grep "plugin ="
# Should end with: plugin = MyPlugin()
```

**Check logs:**
```bash
raxe scan "test" --verbose
# Look for plugin errors
```

### Plugin Not Executing

**Verify enabled:**
```bash
grep -A5 "\\[plugins\\]" ~/.raxe/config.yaml
# Should list your plugin
```

**Check should_execute:**
```python
# For ActionPlugin - make sure should_execute returns True
def should_execute(self, result):
    print(f"Should execute: {result.has_threats}")  # Debug
    return result.has_threats
```

### Performance Issues

**Profile plugin:**
```bash
raxe profile "test text" --iterations 100
```

**Check metrics:**
```bash
raxe stats --plugins
# Look for slow plugins
```

## API Reference

See `docs/plugins/api_reference.md` for complete API documentation.

## Examples

See `examples/plugins/` for working examples:
- custom_detector - Regex-based detector
- slack_notifier - Slack alerts
- webhook - Generic webhook
- file_logger - JSON Lines logging

## Support

- Documentation: https://docs.raxe.ai/plugins
- Issues: https://github.com/raxe-ai/raxe-ce/issues
- Discussions: https://github.com/raxe-ai/raxe-ce/discussions

## Contributing

To contribute your plugin to the community:
1. Create plugin repository
2. Add README and examples
3. Include tests
4. Submit to RAXE plugin marketplace (coming soon)
