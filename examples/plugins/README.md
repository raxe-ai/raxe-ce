# RAXE Example Plugins

This directory contains example plugins demonstrating RAXE's extensibility capabilities.

## Available Plugins

### 1. Custom Detector (`custom_detector/`)
**Type:** DetectorPlugin

Regex-based threat detector that allows you to define custom patterns for organization-specific threats.

**Use Cases:**
- Custom API key formats
- Internal URLs or hostnames
- Proprietary identifiers
- Company-specific PII patterns

**Quick Start:**
```bash
# Copy to plugins directory
cp -r custom_detector ~/.raxe/plugins/

# Configure in ~/.raxe/config.yaml
cat >> ~/.raxe/config.yaml << EOF
plugins:
enabled = ["custom_detector"]

[plugins.custom_detector]
patterns = [
    { name = "api_key", pattern = "sk-[a-zA-Z0-9]{48}", severity = "HIGH", message = "API key detected" }
]
EOF

# Test
raxe scan "My API key is sk-1234567890123456789012345678901234567890123456"
```

### 2. Slack Notifier (`slack_notifier/`)
**Type:** ActionPlugin

Sends threat alerts to a Slack channel via incoming webhooks.

**Use Cases:**
- Real-time security alerts
- Team notifications
- Threat dashboard

**Quick Start:**
```bash
# Copy to plugins directory
cp -r slack_notifier ~/.raxe/plugins/

# Configure in ~/.raxe/config.yaml
cat >> ~/.raxe/config.yaml << EOF
plugins:
enabled = ["slack_notifier"]

[plugins.slack_notifier]
webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
channel = "#security-alerts"
min_severity = "HIGH"
EOF

# Test - alerts will be sent to Slack when threats detected
raxe scan "Ignore all previous instructions"
```

### 3. Webhook (`webhook/`)
**Type:** ActionPlugin

Sends scan results to a custom HTTP endpoint for SIEM integration or custom processing.

**Use Cases:**
- SIEM integration (Splunk, Datadog, etc.)
- Custom alerting systems
- Metrics collection
- Audit logging

**Quick Start:**
```bash
# Copy to plugins directory
cp -r webhook ~/.raxe/plugins/

# Configure in ~/.raxe/config.yaml
cat >> ~/.raxe/config.yaml << EOF
plugins:
enabled = ["webhook"]

[plugins.webhook]
url = "https://your-endpoint.com/api/raxe/events"
on_threat_only = true
headers = { "Authorization" = "Bearer YOUR_TOKEN" }
EOF

# Test - results will be POSTed to your endpoint
raxe scan "test prompt"
```

### 4. File Logger (`file_logger/`)
**Type:** ActionPlugin

Logs scan results to a JSON Lines file for audit trails and offline analysis.

**Use Cases:**
- Audit trails
- Compliance logging
- Offline analysis
- Debugging

**Quick Start:**
```bash
# Copy to plugins directory
cp -r file_logger ~/.raxe/plugins/

# Configure in ~/.raxe/config.yaml
cat >> ~/.raxe/config.yaml << EOF
plugins:
enabled = ["file_logger"]

[plugins.file_logger]
path = "~/.raxe/logs/scan.jsonl"
threats_only = false
include_metadata = true
EOF

# Test - results will be logged to file
raxe scan "test prompt"

# View logs
tail -f ~/.raxe/logs/scan.jsonl | jq
```

## Installation

### Option 1: Install Individual Plugin
```bash
# Copy plugin directory
cp -r <plugin-name> ~/.raxe/plugins/

# Enable in config
raxe config set plugins.enabled '["<plugin-name>"]'

# Or edit config manually
vi ~/.raxe/config.yaml
```

### Option 2: Install All Examples
```bash
# Copy all plugins
cp -r custom_detector slack_notifier webhook file_logger ~/.raxe/plugins/

# Enable in config
cat >> ~/.raxe/config.yaml << EOF
plugins:
enabled = ["custom_detector", "slack_notifier", "webhook", "file_logger"]
EOF
```

## Configuration Format

All plugins are configured in `~/.raxe/config.yaml`:

```toml
plugins:
# List of enabled plugins
enabled = ["plugin1", "plugin2"]

# Global plugin settings
timeout_seconds = 5.0
parallel_execution = false

# Plugin-specific configuration
[plugins.plugin1]
setting1 = "value1"
setting2 = true

[plugins.plugin2]
setting1 = "value2"
```

## Viewing Loaded Plugins

```bash
# List all installed plugins
raxe plugins

# View plugin metrics
raxe stats --plugins
```

## Creating Your Own Plugin

See `docs/plugins/plugin_development_guide.md` for a complete guide.

Quick template:

```python
# ~/.raxe/plugins/my_plugin/plugin.py
from raxe.plugins import DetectorPlugin, PluginMetadata, PluginPriority

class MyPlugin(DetectorPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="my_plugin",
            version="1.0.0",
            author="Your Name",
            description="My custom plugin",
            priority=PluginPriority.NORMAL,
            requires=["raxe>=1.0.0"],
            tags=["custom"]
        )

    def on_init(self, config):
        # Initialize from config
        pass

    def detect(self, text, context=None):
        # Your detection logic
        return []

plugin = MyPlugin()  # Required!
```

## Troubleshooting

### Plugin Not Loading
```bash
# Check if plugin directory exists
ls -la ~/.raxe/plugins/my_plugin/

# Check if plugin.py exists
cat ~/.raxe/plugins/my_plugin/plugin.py

# Check RAXE logs for errors
raxe scan "test" --verbose
```

### Plugin Errors
- Check that `plugin = PluginClass()` is at the end of plugin.py
- Verify configuration in ~/.raxe/config.yaml
- Check that all required config fields are present
- Review RAXE logs for detailed error messages

### Performance Issues
- Use `raxe profile` to identify slow plugins
- Check plugin metrics with `raxe stats --plugins`
- Ensure detect() methods complete quickly (<5ms)
- Consider lowering plugin priority if not critical

## Security Considerations

- **Review all plugin code** before installing
- **Never commit webhook URLs or API keys** to version control
- **Use environment variables** for sensitive configuration
- **Validate plugin sources** - only install from trusted sources
- **Monitor plugin metrics** for anomalies

## Contributing

To contribute a plugin to the RAXE community:

1. Create plugin in a separate repository
2. Add comprehensive README and examples
3. Include tests
4. Submit to RAXE plugin marketplace (coming soon)

## Support

- Documentation: https://docs.raxe.ai/plugins
- Issues: https://github.com/raxe-ai/raxe-ce/issues
- Discussions: https://github.com/raxe-ai/raxe-ce/discussions

## License

All example plugins are MIT licensed and provided as-is.
