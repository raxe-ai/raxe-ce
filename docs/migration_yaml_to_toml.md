# Migration Guide: YAML to TOML Configuration

## Overview

RAXE CE has migrated from YAML to TOML for configuration files. TOML provides better type safety, clearer syntax, and is the Python community standard (used by pyproject.toml).

## Quick Migration

### Before (config.yaml)
```yaml
scan:
  packs_root: ~/.raxe/packs
  enable_l2: true
  fail_fast_on_critical: true

policy:
  block_on_critical: true
  block_on_high: false
  confidence_threshold: 0.7

performance:
  mode: fail_open
  latency_threshold_ms: 10.0

telemetry:
  enabled: false
  batch_size: 10
  async_send: true
```

### After (config.toml)
```toml
[core]
api_key = ""
environment = "production"
version = "1.0.0"

[detection]
l1_enabled = true
l2_enabled = true
mode = "balanced"  # fast|balanced|thorough
confidence_threshold = 0.5
fail_fast_on_critical = true

[policy]
block_on_critical = true
block_on_high = false
allow_on_low_confidence = true
confidence_threshold = 0.7

[telemetry]
enabled = false
batch_size = 50
flush_interval = 300  # seconds
endpoint = "https://telemetry.raxe.ai/v1/events"
async_send = true
max_queue_size = 1000

[performance]
max_queue_size = 10000
scan_timeout = 30  # seconds
circuit_breaker_enabled = true
circuit_breaker_threshold = 5
circuit_breaker_timeout = 30

[logging]
level = "INFO"
directory = "~/.raxe/logs"
rotation_size = "10MB"
rotation_count = 5
enable_file_logging = true
enable_console_logging = true
```

## Migration Steps

### 1. Automatic Migration

```bash
# RAXE will automatically use TOML config if found
# Create default TOML config:
raxe config reset

# This creates ~/.raxe/config.toml with defaults
```

### 2. Manual Migration

If you have custom settings in config.yaml:

```bash
# 1. Backup your YAML config
cp ~/.raxe/config.yaml ~/.raxe/config.yaml.backup

# 2. Create new TOML config
raxe config reset

# 3. Migrate settings manually using CLI
raxe config set detection.l2_enabled true
raxe config set telemetry.enabled true
raxe config set logging.level DEBUG

# 4. Verify config
raxe config show
raxe config validate
```

### 3. Edit Directly

```bash
# Open config in editor
raxe config edit

# Or edit file directly
vim ~/.raxe/config.toml
```

## Key Differences

### Section Reorganization

| YAML (Old) | TOML (New) | Notes |
|------------|------------|-------|
| `scan.*` | `detection.*` | Renamed for clarity |
| `scan.packs_root` | Removed | Now managed automatically |
| `performance.mode` | `detection.mode` | Moved to detection section |
| N/A | `core.*` | New section for API key, environment |
| N/A | `logging.*` | New section for logging config |

### New Settings

TOML config adds several new settings:

- **core.api_key**: RAXE API key (optional)
- **core.environment**: development|production|test
- **detection.mode**: fast|balanced|thorough
- **logging.***: Complete logging configuration
- **performance.max_queue_size**: Queue overflow protection
- **telemetry.flush_interval**: Batch flush interval

### Removed Settings

Settings removed from YAML:

- `scan.packs_root`: Now auto-managed in ~/.raxe/packs
- `scan.enable_schema_validation`: Always enabled in production
- `performance.sample_rate`: Replaced by detection.mode

## Configuration Priority

RAXE uses this fallback chain:

1. **Explicit path**: `raxe scan --config /path/to/config.toml`
2. **Local directory**: `./.raxe/config.toml`
3. **Home directory**: `~/.raxe/config.toml`
4. **Environment variables**: `RAXE_*` env vars
5. **Defaults**: Built-in defaults

## Environment Variables

TOML config can be overridden with environment variables:

```bash
# Format: RAXE_<SECTION>_<KEY>
export RAXE_DETECTION_L2_ENABLED=true
export RAXE_TELEMETRY_ENABLED=false
export RAXE_LOG_LEVEL=DEBUG

# Legacy env vars still work:
export RAXE_API_KEY=your-key
export RAXE_ENABLE_L2=true
```

## CLI Commands

### View Configuration
```bash
raxe config show
```

### Update Settings
```bash
raxe config set detection.mode fast
raxe config set telemetry.batch_size 100
```

### Validate Configuration
```bash
raxe config validate
```

### Reset to Defaults
```bash
raxe config reset
```

## Validation

TOML config includes schema validation:

```bash
$ raxe config validate
✓ Configuration is valid

# Or if errors:
$ raxe config set detection.confidence_threshold 1.5
Validation errors:
  - detection.confidence_threshold must be 0-1, got 1.5
```

## Troubleshooting

### Config not found
```bash
# Create default config
raxe config reset
```

### Invalid TOML syntax
```bash
# Validate config file
raxe config validate

# Common issues:
# - Missing quotes around strings
# - Invalid section names
# - Type mismatches (string vs bool)
```

### Settings not applied
```bash
# Check priority order
raxe config show

# Environment variables override file config
# Unset env vars if needed:
unset RAXE_DETECTION_MODE
```

## Best Practices

1. **Use config file for persistent settings**
   ```bash
   raxe config set detection.mode fast
   ```

2. **Use env vars for temporary overrides**
   ```bash
   RAXE_LOG_LEVEL=DEBUG raxe scan "test prompt"
   ```

3. **Validate after changes**
   ```bash
   raxe config set detection.mode fast
   raxe config validate
   ```

4. **Keep API key in env var**
   ```bash
   export RAXE_API_KEY=your-secret-key
   # Don't put in config file (will be redacted anyway)
   ```

## Support

If you encounter issues during migration:

1. Check validation: `raxe config validate`
2. View effective config: `raxe config show`
3. Reset to defaults: `raxe config reset`
4. File an issue: https://github.com/raxe-ai/raxe-ce/issues

## Deprecation Timeline

- **v1.0.0**: TOML config introduced, YAML still supported
- **v1.1.0**: YAML config deprecated (warning shown)
- **v2.0.0**: YAML config removed (TOML only)

Current version uses TOML exclusively.
