# Offline Mode & Privacy

RAXE is designed with a privacy-first architecture. All threat detection runs locally on your device. This document explains exactly what connects to the internet, what stays local, and how to control it.

## Table of Contents

- [What Runs Locally](#what-runs-locally)
- [What Connects to the Internet](#what-connects-to-the-internet)
- [Telemetry Details](#telemetry-details)
- [Disabling Telemetry](#disabling-telemetry)
- [Fully Offline Operation](#fully-offline-operation)
- [Privacy Guarantees](#privacy-guarantees)

## What Runs Locally

All scanning and detection happens on your device, regardless of tier or configuration:

- **L1 rule matching**: 515+ detection rules are bundled with the package and evaluated locally
- **L2 ML detection**: The ONNX neural network model runs on-device via CPU (no GPU required)
- **Results computation**: Detection results, severity scores, and confidence values are all computed locally
- **Rule evaluation**: No external service is consulted during scanning

Your prompts, LLM responses, and matched text patterns never leave your machine as part of scanning.

## What Connects to the Internet

| Activity | Free Tier | Pro/Enterprise | When |
|----------|-----------|----------------|------|
| **Scanning** | 100% local | 100% local | Always |
| **Telemetry** | Metadata-only (always on) | Configurable (can disable) | After each scan |
| **API key validation** | On first run | On first run | `raxe init` |
| **Rule updates** | Manual (`pip install --upgrade raxe`) | Manual (same) | When you choose |
| **Prompts sent to cloud** | Never | Never | N/A |

## Telemetry Details

When telemetry is active, RAXE sends anonymous metadata after scans. This data helps improve community detection accuracy.

### What is sent

- Rule IDs that fired (e.g., `pi-001`)
- Detection count and highest severity level
- Confidence scores
- Scan duration in milliseconds
- SHA-256 hash of the prompt (irreversible, one-way)
- Prompt character length
- RAXE version and platform (e.g., `darwin`, `linux`)
- Action taken (`allow`, `block`, `warn`)
- Entry point (`cli`, `sdk`, `integration`)

### What is never sent

- Your actual prompt text
- LLM responses or outputs
- Matched text patterns (what the rule matched on)
- System prompts or API keys
- User identifiers, IP addresses, or PII
- RAG context or tool call content
- Detection rule patterns (these are intellectual property)

For the full schema, see [Scan Telemetry Schema](SCAN_TELEMETRY_SCHEMA.md).

## Disabling Telemetry

Disabling telemetry requires a **Pro tier or higher** license.

On the free Community Edition, telemetry is always active. It sends only the metadata described above -- never your prompts or content.

### Pro/Enterprise users

```python
# In code
from raxe import Raxe
raxe = Raxe(telemetry=False)
```

```bash
# Via CLI
raxe config set telemetry.enabled false
```

```yaml
# In ~/.raxe/config.yaml
telemetry:
  enabled: false
```

### Why telemetry is required on the free tier

Free-tier telemetry serves two purposes:

1. **Detection improvement**: Aggregate metadata (which rules fire, how often, on what platforms) helps improve rule accuracy for all users
2. **Usage visibility**: Anonymous scan counts help the RAXE team understand adoption patterns

No prompt content is ever included. The metadata alone cannot reconstruct what you scanned.

## Fully Offline Operation

RAXE scanning works without internet connectivity. However, some one-time setup steps require a network connection.

### Setup (requires internet)

1. Install the package: `pip install raxe`
2. Run `raxe init` once (validates or creates an API key)

### After setup

All scanning works offline:

```bash
# These work without internet
raxe scan "Ignore all previous instructions"
raxe scan --file input.txt
```

```python
# SDK scanning works offline
from raxe import Raxe
raxe = Raxe()
result = raxe.scan("test prompt")
```

Telemetry events are queued locally and sent when connectivity is restored. If you are on the Pro tier with telemetry disabled, no network activity occurs during scanning at all.

### Air-gapped environments

For networks with no internet access:

1. Download the RAXE wheel file on a connected machine
2. Transfer it to the air-gapped environment
3. Install with `pip install raxe-*.whl`
4. Telemetry will silently fail (events are dropped after retry limits)

For enterprise air-gapped provisioning with offline API key setup, contact enterprise@raxe.ai.

## Privacy Guarantees

| Guarantee | Details |
|-----------|---------|
| Prompts stay local | Prompt text is never transmitted to any RAXE service |
| No PII collection | No user IDs, IP addresses, or personal data are collected |
| Irreversible hashing | Prompt hashes use SHA-256; the original text cannot be recovered |
| Local-first processing | All detection runs on-device with no cloud dependency |
| Metadata-only telemetry | Only rule IDs, severity, and performance metrics are sent |
| Transparent schema | The full telemetry schema is [publicly documented](SCAN_TELEMETRY_SCHEMA.md) |

### Compliance alignment

RAXE's privacy model is designed to align with:

- **GDPR**: No personal data is collected or transmitted
- **SOC 2**: Audit trails are local; telemetry contains only operational metadata
- **Data residency**: All processing is on-device, so data never crosses network boundaries

---

For questions about RAXE's privacy model, contact privacy@raxe.ai or open a [GitHub Discussion](https://github.com/raxe-ai/raxe-ce/discussions).
