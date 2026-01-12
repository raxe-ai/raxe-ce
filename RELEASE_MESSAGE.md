# RAXE v0.7.0 - Enhanced ML Detection for Agent Runtime Security

**Protecting Agents from Agents at Runtime**

RAXE v0.7.0 delivers significant ML model improvements for higher-quality threat detection in agentic AI systems. As agents increasingly communicate with other agents, the attack surface expands—RAXE now catches more sophisticated threats with greater accuracy.

## What's New

### ML Model v3: BinaryFirstEngine

A completely redesigned voting engine that prioritizes the binary threat classifier for faster, more accurate decisions:

- **Higher accuracy** - Binary-first approach reduces false positives while maintaining high recall
- **Faster decisions** - Optimized inference path for sub-3ms latency
- **Better explainability** - Clear voting rationale shows why threats were detected
- **Novel attack detection** - Identifies "Uncategorized Threats" that don't fit known families

### Improved Detection Quality

- **Handcrafted feature alignment** - Feature extraction now matches training exactly, improving model consistency
- **Family classification** - L1 detections now correctly report threat families (PI, JB, PII, CMD, ENC, RAG)
- **Uncertainty handling** - When the model detects a threat but can't classify the family, it now clearly indicates uncertainty rather than mislabeling

### Agent-to-Agent Security

RAXE protects the full agent communication chain:

```
User → Agent A → Agent B → Tool → Response
         ↓          ↓        ↓
       RAXE      RAXE     RAXE
```

Every message between agents is scanned for:
- Prompt injection attempts
- Jailbreak escalation
- Tool abuse patterns
- Data exfiltration
- Encoded/obfuscated attacks

### Integration Highlights

Works with all major agentic frameworks:

| Framework | Integration |
|-----------|-------------|
| LangChain | `RaxeCallbackHandler` |
| CrewAI | `RaxeCrewGuard` |
| AutoGen | `RaxeConversationGuard` |
| LlamaIndex | `RaxeLlamaIndexCallback` |
| LiteLLM | `RaxeLiteLLMCallback` |
| OpenAI SDK | `RaxeOpenAI` wrapper |

## Upgrade

```bash
pip install --upgrade raxe
```

The ML model will auto-download on first scan (~235MB).

## Technical Details

- **Voting Engine**: `BinaryFirstEngine` with configurable presets (balanced, high_security, low_fp)
- **Telemetry Schema**: v2.2.0 with improved family tracking and uncertainty metadata
- **Dependencies**: scikit-learn 1.7.x pinned for feature scaler compatibility

## Documentation

- [Detection Engine](https://docs.raxe.ai/concepts/detection-engine)
- [Threat Families](https://docs.raxe.ai/concepts/threat-families)
- [Integration Guide](https://docs.raxe.ai/integrations)

---

Questions? Join our [Slack](https://join.slack.com/t/raxeai/shared_invite/zt-3kch8c9zp-A8CMJYWQjBBpzV4KNnAQcQ) or email community@raxe.ai
