# RAXE Voting Engine

> **Ensemble decision system for L2 threat detection**

## Overview

The Voting Engine is an ensemble decision system that replaces the previous boost-based logic with a transparent, weighted voting approach across all 5 classifier heads. It provides:

- **Transparent decisions**: Full visibility into which heads voted and why
- **Configurable presets**: balanced, high_security, low_fp
- **Three-way classification**: SAFE, REVIEW, THREAT
- **Explainable outputs**: Every decision includes rationale and vote breakdown

## Quick Start

```python
from raxe import Raxe

# Use balanced preset (default)
raxe = Raxe()
result = raxe.scan("Ignore all previous instructions")

# Use high_security preset (more aggressive)
raxe = Raxe(voting_preset="high_security")
result = raxe.scan("Ignore all previous instructions")

# Access voting details
if result.scan_result and result.scan_result.l2_result:
    voting = result.scan_result.l2_result.voting
    print(f"Decision: {voting['decision']}")
    print(f"Rule triggered: {voting['decision_rule_triggered']}")
    print(f"Vote counts: {voting['threat_vote_count']} THREAT, {voting['safe_vote_count']} SAFE")
```

## How It Works

### Five Classifier Heads

The Gemma L2 detector uses 5 specialized classifier heads:

| Head | Description | Weight | Signal Quality |
|------|-------------|--------|----------------|
| **binary** | Is threat? (yes/no) | 1.0 | Baseline |
| **family** | Threat category (14 classes) | 1.2 | Strong |
| **severity** | Threat level (none/moderate/severe) | 1.5 | Highest |
| **technique** | Attack technique (35 classes) | 1.0 | Good |
| **harm** | Harm types (10 labels, multilabel) | 0.8 | Prone to FPs |

### Per-Head Voting Rules

Each head casts one of three votes: **SAFE**, **ABSTAIN**, or **THREAT**.

#### Binary Head
```
THREAT if threat_probability >= 0.65
SAFE   if threat_probability <  0.40
ABSTAIN otherwise (gray zone)
```

#### Family Head
```
THREAT if family != "benign" AND confidence >= 0.55
SAFE   if family == "benign" OR confidence < 0.35
ABSTAIN otherwise
```

#### Severity Head
```
THREAT if severity in (moderate, severe)
SAFE   if severity == "none"
No abstain - severity always has an opinion
```

#### Technique Head
```
THREAT if technique != "none" AND confidence >= 0.50
SAFE   if technique == "none" OR confidence < 0.30
ABSTAIN otherwise
```

#### Harm Head
```
THREAT if max_probability >= 0.92
SAFE   if max_probability <  0.50
ABSTAIN otherwise
```

### Decision Rules (Priority Order)

The voting engine applies these rules in order until a decision is made:

1. **High-Confidence Override**
   - If ANY head votes THREAT with confidence >= 85% AND at least 1 other head also votes THREAT
   - Decision: **THREAT**

2. **Severity Veto**
   - If severity head votes SAFE (severity="none")
   - Need 3+ other THREAT votes to override
   - Else decision: **SAFE**

3. **Minimum Votes**
   - Need >= 2 THREAT votes to consider as THREAT
   - With only 1 THREAT vote, may go to REVIEW

4. **Weighted Ratio**
   - Calculate: `threat_weight / safe_weight`
   - If ratio >= 1.3: **THREAT**
   - If ratio in [1.0, 1.3): **REVIEW**

5. **Tie Breaker**
   - Ties favor SAFE (reduce false positives)

## Presets

### balanced (default)

Default configuration balancing false positives and false negatives.

```yaml
thresholds:
  binary_threat: 0.65
  binary_safe: 0.40
  family_threat_confidence: 0.55
  technique_threat_confidence: 0.50
  harm_threat_threshold: 0.92

weights:
  binary: 1.0
  family: 1.2
  severity: 1.5
  technique: 1.0
  harm: 0.8

decision:
  min_threat_votes: 2
  threat_ratio: 1.3
  review_ratio_min: 1.0
```

### high_security

More aggressive blocking for high-risk environments.

```yaml
thresholds:
  binary_threat: 0.50  # Lower (more sensitive)
  binary_safe: 0.30
  family_threat_confidence: 0.40  # Lower
  technique_threat_confidence: 0.35
  harm_threat_threshold: 0.80  # Lower

decision:
  min_threat_votes: 1  # Single vote can trigger
  threat_ratio: 1.1  # Lower ratio needed
```

### low_fp

Fewer false positives for cost-sensitive environments.

```yaml
thresholds:
  binary_threat: 0.80  # Higher (less sensitive)
  binary_safe: 0.50
  family_threat_confidence: 0.70  # Higher
  technique_threat_confidence: 0.65
  harm_threat_threshold: 0.95  # Very high

decision:
  min_threat_votes: 3  # Require more votes
  threat_ratio: 1.5  # Higher ratio needed
```

## Configuration

### Environment Variables

```bash
# Enable/disable voting engine (default: enabled)
export RAXE_L2_VOTING_ENABLED=true

# Set voting preset
export RAXE_L2_VOTING_PRESET=balanced  # or high_security, low_fp
```

### Config File (l2_config.yaml)

```yaml
# Place in ~/.raxe/l2_config.yaml or ./l2_config.yaml

voting:
  enabled: true
  preset: balanced  # balanced | high_security | low_fp
```

### Programmatic Configuration

```python
from raxe import Raxe

# Use preset
raxe = Raxe(voting_preset="high_security")

# Or via environment before initialization
import os
os.environ["RAXE_L2_VOTING_PRESET"] = "low_fp"
raxe = Raxe()
```

## Voting Result Structure

The L2Result includes a `voting` field with full transparency:

```python
{
    "decision": "threat",  # safe | review | threat
    "confidence": 0.85,
    "preset_used": "balanced",
    "decision_rule_triggered": "weighted_ratio_threshold",

    # Vote counts
    "threat_vote_count": 4,
    "safe_vote_count": 1,
    "abstain_vote_count": 0,

    # Weighted scores
    "weighted_threat_score": 4.5,
    "weighted_safe_score": 0.8,
    "weighted_ratio": 5.625,

    # Per-head breakdown
    "per_head_votes": {
        "binary": {
            "vote": "threat",
            "confidence": 0.82,
            "weight": 1.0,
            "raw_probability": 0.82,
            "threshold_used": 0.65,
            "prediction": "threat",
            "rationale": "threat_probability (82.00%) >= threat_threshold (65.00%)"
        },
        "family": { ... },
        "severity": { ... },
        "technique": { ... },
        "harm": { ... }
    },

    # Aggregated scores
    "aggregated_scores": {
        "safe": 0.8,
        "threat": 4.5,
        "ratio": 5.625
    }
}
```

## Telemetry

Voting metadata is included in scan telemetry (see `docs/SCAN_TELEMETRY_SCHEMA.md`):

```json
{
    "l2": {
        "voting": {
            "decision": "threat",
            "confidence": 0.85,
            "preset_used": "balanced",
            "decision_rule_triggered": "weighted_ratio_threshold",
            "threat_vote_count": 4,
            "safe_vote_count": 1,
            "weighted_ratio": 5.625
        }
    }
}
```

## Tuning Thresholds

### When to Use high_security

- High-risk applications (financial, healthcare)
- When false negatives are costly
- When human review is available for false positives

### When to Use low_fp

- Production environments with high volume
- When false positives are costly (user friction)
- When manual review is not feasible

### Custom Thresholds

For advanced use cases, you can create a custom VotingConfig:

```python
from raxe.domain.ml.voting import (
    VotingConfig,
    BinaryHeadThresholds,
    DecisionThresholds,
    HeadWeights,
)

custom_config = VotingConfig(
    name="custom",
    binary=BinaryHeadThresholds(
        threat_threshold=0.70,
        safe_threshold=0.35,
    ),
    weights=HeadWeights(
        binary=1.0,
        family=1.5,  # Increase family weight
        severity=2.0,  # Increase severity weight
        technique=1.0,
        harm=0.5,  # Decrease harm weight
    ),
    decision=DecisionThresholds(
        min_threat_votes=2,
        threat_ratio=1.4,
    ),
)

# Note: Custom config requires code changes to GemmaL2Detector
```

## L2 Classification Categories

### Threat Families (15 classes)

| Family | Description |
|--------|-------------|
| `benign` | No threat detected |
| `agent_goal_hijack` | Attempts to redirect agent objectives |
| `data_exfiltration` | Stealing sensitive data |
| `encoding_or_obfuscation_attack` | Using encoding to evade detection |
| `human_trust_exploit` | Social engineering via LLM |
| `inter_agent_attack` | Attacks targeting multi-agent systems |
| `jailbreak` | Bypassing safety guidelines |
| `memory_poisoning` | Corrupting agent memory/context |
| `other_security` | Other security concerns |
| `privilege_escalation` | Gaining elevated access |
| `prompt_injection` | Instruction override attacks |
| `rag_or_context_attack` | RAG/retrieval manipulation |
| `rogue_behavior` | Causing unintended agent actions |
| `tool_or_command_abuse` | Misusing tools/commands |
| `toxic_or_policy_violating_content` | Harmful or policy-violating output |

### Severity Levels (3 classes)

| Severity | Description |
|----------|-------------|
| `none` | No threat detected |
| `moderate` | Medium-risk threat, may require review |
| `severe` | High-risk threat, should be blocked |

### Primary Techniques (35 classes)

The model classifies attacks into 35 specific techniques, including:
- `instruction_override` - Direct instruction manipulation
- `role_or_persona_manipulation` - Persona hijacking (DAN, etc.)
- `system_prompt_or_config_extraction` - Extracting hidden prompts
- `encoding_or_obfuscation` - l33t speak, Base64, etc.
- `indirect_injection_via_content` - Attacks via external content
- `tool_abuse_or_unintended_action` - Misusing agent tools
- And 29 more specialized technique categories

See `src/raxe/domain/ml/gemma_models.py` for the complete list.

### Harm Types (10 classes, multilabel)

| Harm Type | Description |
|-----------|-------------|
| `cbrn_or_weapons` | Chemical/biological/nuclear/weapons content |
| `crime_or_fraud` | Criminal activity or fraud |
| `cybersecurity_or_malware` | Hacking, malware creation |
| `hate_or_harassment` | Hate speech, harassment |
| `misinformation_or_disinfo` | False information |
| `other_harm` | Other harmful content |
| `privacy_or_pii` | Privacy violations, PII exposure |
| `self_harm_or_suicide` | Self-harm content |
| `sexual_content` | Adult/sexual content |
| `violence_or_physical_harm` | Violence, physical harm |

## Architecture

The voting engine follows Clean Architecture principles:

```
src/raxe/domain/ml/voting/
    __init__.py      # Exports
    config.py        # VotingConfig, presets
    models.py        # Vote, HeadVoteDetail, VotingResult
    head_voters.py   # Per-head voting logic
    engine.py        # VotingEngine orchestration
```

Key design principles:
- **Pure domain logic**: No I/O in voting module
- **Immutable value objects**: All dataclasses use `frozen=True`
- **Type hints**: All functions fully typed
- **Testable**: Pure functions enable comprehensive testing

## Comparison: Old vs New

| Aspect | Old (Boost-Based) | New (Voting Engine) |
|--------|-------------------|---------------------|
| Decision logic | Sequential boosts | Parallel voting |
| Transparency | Limited | Full vote breakdown |
| Configurability | Per-head thresholds | Presets + fine-tuning |
| Three-way output | No (binary) | Yes (SAFE/REVIEW/THREAT) |
| Explainability | Minimal | Decision rule + rationale |
| Telemetry | Basic | Full voting metadata |

## Migration from Boost-Based Logic

If you were using the previous boost-based ensemble:

1. **No action required**: The voting engine is the new default
2. **Equivalent behavior**: The `balanced` preset approximates previous behavior
3. **Disable if needed**: Set `RAXE_L2_VOTING_ENABLED=false` to use legacy logic

## Related Documentation

- [SCAN_TELEMETRY_SCHEMA.md](SCAN_TELEMETRY_SCHEMA.md) - Telemetry schema with voting fields
- [L2 Config](../src/raxe/domain/ml/l2_config.py) - L2 configuration
- [Gemma Detector](../src/raxe/domain/ml/gemma_detector.py) - L2 detector implementation
