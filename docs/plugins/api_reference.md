# Plugin API Reference

Complete API reference for RAXE plugin development.

## Core Protocols

### RaxePlugin (Base Protocol)

All plugins must implement this base protocol.

```python
from raxe.plugins import RaxePlugin, PluginMetadata, PluginPriority

class MyPlugin(RaxePlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_plugin",
            version="1.0.0",
            author="Your Name",
            description="My custom plugin",
            priority=PluginPriority.NORMAL,
            requires=("raxe>=0.9.0",),
            tags=("detector", "custom"),
        )

    def on_init(self, config: dict) -> None:
        """Initialize plugin with configuration."""
        self.config = config
```

#### Lifecycle Hooks

| Method | When Called | Purpose |
|--------|-------------|---------|
| `on_init(config)` | Once at load | Initialize with config |
| `on_scan_start(text, context)` | Before each scan | Pre-scan logic |
| `on_scan_complete(result)` | After each scan | Post-scan notification |
| `on_threat_detected(result)` | When threats found | Threat notification |
| `on_shutdown()` | At RAXE shutdown | Cleanup resources |

---

## Plugin Types

### DetectorPlugin

Extends detection with custom logic.

```python
from raxe.plugins import DetectorPlugin, PluginMetadata
from raxe.domain.engine.executor import Detection
from raxe.domain.models import Severity

class CustomDetector(DetectorPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="custom_detector",
            version="1.0.0",
            author="Your Name",
            description="Custom detection logic",
        )

    def on_init(self, config: dict) -> None:
        self.patterns = config.get("patterns", [])

    def detect(self, text: str, context: dict | None = None) -> list[Detection]:
        """Run custom detection on text."""
        detections = []
        for pattern in self.patterns:
            if pattern in text:
                detections.append(Detection(
                    rule_id=f"custom_{self.metadata.name}",
                    severity=Severity.HIGH,
                    confidence=0.9,
                    matched_text=pattern,
                    message=f"Custom pattern detected: {pattern}",
                ))
        return detections

    def get_rules(self) -> list:
        """Optionally provide custom rules."""
        return []

plugin = CustomDetector()  # Required export
```

#### Methods

| Method | Required | Description |
|--------|----------|-------------|
| `detect(text, context)` | Yes | Execute custom detection |
| `get_rules()` | No | Provide custom rules |

---

### ActionPlugin

Executes actions based on scan results.

```python
import requests
from raxe.plugins import ActionPlugin, PluginMetadata
from raxe.application.scan_pipeline import ScanPipelineResult

class WebhookNotifier(ActionPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="webhook_notifier",
            version="1.0.0",
            author="Your Name",
            description="Send webhooks on threats",
        )

    def on_init(self, config: dict) -> None:
        self.webhook_url = config["webhook_url"]
        self.min_severity = config.get("min_severity", "HIGH")

    def should_execute(self, result: ScanPipelineResult) -> bool:
        """Check if action should run."""
        if not result.has_threats:
            return False
        return result.severity in [self.min_severity, "CRITICAL"]

    def execute(self, result: ScanPipelineResult) -> None:
        """Send webhook notification."""
        requests.post(
            self.webhook_url,
            json={
                "has_threats": result.has_threats,
                "severity": result.severity,
                "rule_ids": [d.rule_id for d in result.detections],
            },
            timeout=5,
        )

plugin = WebhookNotifier()  # Required export
```

#### Methods

| Method | Required | Description |
|--------|----------|-------------|
| `should_execute(result)` | Yes | Determine if action should run |
| `execute(result)` | Yes | Execute the action |

---

### TransformPlugin

Transforms text before/after scanning.

```python
import re
from raxe.plugins import TransformPlugin, PluginMetadata
from raxe.application.scan_pipeline import ScanPipelineResult

class TextNormalizer(TransformPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="text_normalizer",
            version="1.0.0",
            author="Your Name",
            description="Normalize text before scanning",
        )

    def on_init(self, config: dict) -> None:
        self.lowercase = config.get("lowercase", False)

    def transform_input(self, text: str, context: dict | None = None) -> str:
        """Transform text before scanning."""
        # Normalize whitespace
        text = " ".join(text.split())
        # Optionally lowercase
        if self.lowercase:
            text = text.lower()
        return text

    def transform_output(self, result: ScanPipelineResult) -> ScanPipelineResult:
        """Transform results after scanning."""
        # Add metadata to result
        import dataclasses
        new_metadata = {**(result.metadata or {}), "normalized": True}
        return dataclasses.replace(result, metadata=new_metadata)

plugin = TextNormalizer()  # Required export
```

#### Methods

| Method | Required | Description |
|--------|----------|-------------|
| `transform_input(text, context)` | No | Transform input text |
| `transform_output(result)` | No | Transform scan result |

---

## Data Classes

### PluginMetadata

Plugin identification and metadata.

```python
from raxe.plugins import PluginMetadata, PluginPriority

metadata = PluginMetadata(
    name="my_plugin",           # Unique identifier (lowercase, no spaces)
    version="1.0.0",            # Semantic version
    author="Your Name",         # Author name/org
    description="My plugin",    # Human-readable description
    priority=PluginPriority.NORMAL,  # Execution priority
    requires=("raxe>=0.9.0",),  # Required RAXE versions
    tags=("detector", "custom"), # Categorization tags
)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | Required | Unique plugin ID |
| `version` | `str` | Required | Semantic version |
| `author` | `str` | Required | Author name |
| `description` | `str` | Required | Description |
| `priority` | `PluginPriority` | `NORMAL` | Execution priority |
| `requires` | `tuple[str, ...]` | `("raxe>=1.0.0",)` | Dependencies |
| `tags` | `tuple[str, ...]` | `()` | Tags |

### PluginPriority

Execution priority for plugins.

```python
from raxe.plugins import PluginPriority

class PluginPriority(Enum):
    CRITICAL = 0   # Security-critical, runs first
    HIGH = 10      # Important functionality
    NORMAL = 50    # Standard priority (default)
    LOW = 100      # Nice-to-have, runs last
```

### Detection

Detection result from detector plugins.

```python
from raxe.domain.engine.executor import Detection
from raxe.domain.models import Severity

detection = Detection(
    rule_id="custom_001",       # Unique rule ID
    severity=Severity.HIGH,     # Severity level
    confidence=0.95,            # Confidence (0.0-1.0)
    matched_text="pattern",     # What was matched
    message="Description",      # Human-readable message
    start_offset=0,             # Start position (optional)
    end_offset=10,              # End position (optional)
)
```

### ScanPipelineResult

Result passed to plugin hooks.

```python
from raxe.application.scan_pipeline import ScanPipelineResult

# Available in on_scan_complete, on_threat_detected, etc.
result.has_threats        # bool: Any threats detected?
result.severity           # str: Highest severity ("CRITICAL", "HIGH", etc.)
result.detections         # list[Detection]: All detections
result.l1_result          # L1Result: Rule-based results
result.l2_result          # L2Result: ML-based results (if enabled)
result.scan_duration_ms   # float: Total scan time
result.metadata           # dict: Custom metadata
```

---

## Configuration

Plugins are configured in `~/.raxe/config.yaml`:

```yaml
plugins:
  # Enable/disable plugins
  enabled:
    - my_detector
    - webhook_notifier

  # Plugin-specific configuration
  my_detector:
    patterns:
      - "malicious"
      - "dangerous"

  webhook_notifier:
    webhook_url: "https://hooks.example.com/webhook"
    min_severity: "HIGH"
```

---

## Plugin Registration

### File-based Plugins

Place plugins in `~/.raxe/plugins/`:

```
~/.raxe/plugins/
├── my_detector.py
├── webhook_notifier.py
└── text_normalizer.py
```

Each file must export a `plugin` variable:

```python
# my_detector.py
class MyDetector(DetectorPlugin):
    ...

plugin = MyDetector()  # Required!
```

### Programmatic Registration

```python
from raxe import Raxe
from raxe.plugins import PluginManager

raxe = Raxe()
plugin_manager = raxe.plugin_manager

# Register plugin
plugin_manager.register(my_plugin)

# Unregister
plugin_manager.unregister("my_plugin")

# List plugins
for name, plugin in plugin_manager.plugins.items():
    print(f"{name}: {plugin.metadata.description}")
```

---

## Best Practices

### Performance

```python
def detect(self, text: str, context: dict | None = None) -> list[Detection]:
    # Target: <5ms execution time
    # Avoid: Network calls, file I/O, complex regex
    # Do: Cache compiled patterns, use efficient algorithms
    pass
```

### Error Handling

```python
def execute(self, result: ScanPipelineResult) -> None:
    try:
        # Your action logic
        requests.post(self.webhook_url, json=data, timeout=5)
    except requests.Timeout:
        logger.warning("Webhook timeout")
    except Exception as e:
        logger.error(f"Plugin error: {e}")
        # Don't re-raise - let other plugins run
```

### Thread Safety

```python
import threading

class ThreadSafePlugin(ActionPlugin):
    def on_init(self, config: dict) -> None:
        self._lock = threading.Lock()
        self._counter = 0

    def execute(self, result: ScanPipelineResult) -> None:
        with self._lock:
            self._counter += 1
```

---

## Related Documentation

- [Plugin Development Guide](plugin_development_guide.md) - Step-by-step guide
- [Custom Rules](../CUSTOM_RULES.md) - Create detection rules
- [Configuration](../configuration.md) - RAXE configuration
