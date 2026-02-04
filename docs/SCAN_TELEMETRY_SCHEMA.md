# RAXE Scan Telemetry Schema v3.0

> **CANONICAL SOURCE**: This is the authoritative schema definition for scan telemetry events.
> All telemetry entry points (CLI, SDK, wrappers, decorators) MUST comply with this schema.

## Schema Version

```
Version: 3.0.0
Last Updated: 2026-01-29
Status: LOCKED (changes require version bump)
```

## Privacy Compliance

All fields in this schema have been reviewed for privacy compliance per `CLAUDE.md`:

- ✅ **SAFE**: All fields are model outputs, metrics, or enum values
- ❌ **FORBIDDEN**: No prompt text, matched content, PII, or rule patterns

---

## Complete Schema Definition

```json
{
  "event_id": "evt_<16_hex_chars>",
  "event_type": "scan",
  "schema_version": "3.0.0",
  "priority": "critical|standard",
  "timestamp": "ISO8601_UTC",

  "payload": {
    "prompt_hash": "sha256:<64_hex_chars>",
    "prompt_length": "<int: len(prompt)>",
    "threat_detected": "<bool: l1.hit OR l2.hit>",
    "scan_duration_ms": "<float: total scan time>",
    "action_taken": "allow|block|warn|redact",
    "entry_point": "cli|sdk|wrapper|integration",
    "wrapper_type": "openai|anthropic|langchain|none|null",

    "tenant_id": "<string|null: tenant identifier>",
    "app_id": "<string|null: application identifier>",
    "policy_id": "<string|null: policy identifier>",
    "policy_name": "<string|null: human-readable policy name>",
    "policy_mode": "monitor|balanced|strict|custom|null",
    "policy_version": "<int|null: policy version number>",
    "resolution_source": "request|app|tenant|system_default|null",

    "mssp_id": "<string|null: MSSP/Partner identifier (mssp_xxx)>",
    "customer_id": "<string|null: Customer identifier (cust_xxx)>",
    "agent_id": "<string|null: Agent identifier (agent_xxx)>",

    "_mssp_context": {
      "mssp_id": "<string: MSSP/Partner identifier>",
      "data_mode": "full|privacy_safe",
      "customer_id": "<string|null: Customer identifier>",
      "customer_name": "<string|null: Human-readable customer name>",
      "app_id": "<string|null: Application identifier>",
      "agent_id": "<string|null: Agent identifier>",
      "data_fields": ["<string: configured fields>"]
    },

    "_mssp_data": {
      "prompt_text": "<string|null: Raw prompt (only in full mode)>",
      "matched_text": ["<string: L1 matched text snippets>"]
    },

    "agent": {
      "version": "<string: RAXE version (e.g., 0.9.0)>",
      "platform": "<string: OS platform (darwin|linux|win32)>",
      "integration": "<string|null: Integration type (langchain|crewai|etc)>"
    },

    "l1": {
      "hit": "<bool: detection_count > 0>",
      "duration_ms": "<float: L1 scan time>",
      "detection_count": "<int: len(detections)>",
      "highest_severity": "none|low|medium|high|critical",
      "families": ["<unique family strings>"],
      "detections": [
        {
          "rule_id": "<string: rule identifier>",
          "family": "<string: rule family>",
          "severity": "<string: rule severity>",
          "confidence": "<float: 0.0-1.0>"
        }
      ]
    },

    "l2": {
      "enabled": "<bool: L2 was enabled>",
      "hit": "<bool: is_threat property>",
      "duration_ms": "<float: processing_time_ms>",
      "model_version": "<string: model identifier>",
      "token_count": "<int|null: number of tokens after tokenization (max 512)>",
      "tokens_truncated": "<bool: true if input was truncated to 512 tokens>",

      "binary": {
        "is_threat": "<bool: argmax == threat>",
        "threat_probability": "<float: 0.0-1.0>",
        "safe_probability": "<float: 0.0-1.0>"
      },

      "family": {
        "prediction": "<string: 14-class enum>",
        "confidence": "<float: max probability>",
        "top3": [
          {"label": "<string>", "probability": "<float>"}
        ]
      },

      "severity": {
        "prediction": "<string: 3-class enum (none|moderate|severe)>",
        "confidence": "<float: max probability>",
        "distribution": {
          "none": "<float>",
          "moderate": "<float>",
          "severe": "<float>"
        }
      },

      "technique": {
        "prediction": "<string|null: 35-class enum>",
        "confidence": "<float: max probability>",
        "top3": [
          {"label": "<string>", "probability": "<float>"}
        ]
      },

      "harm_types": {
        "active_labels": ["<string: triggered harms>"],
        "active_count": "<int: len(active_labels)>",
        "max_probability": "<float: highest probability>",
        "probabilities": {
          "cbrn_or_weapons": "<float>",
          "crime_or_fraud": "<float>",
          "cybersecurity_or_malware": "<float>",
          "hate_or_harassment": "<float>",
          "misinformation_or_disinfo": "<float>",
          "other_harm": "<float>",
          "privacy_or_pii": "<float>",
          "self_harm_or_suicide": "<float>",
          "sexual_content": "<float>",
          "violence_or_physical_harm": "<float>"
        }
      },

      "classification": "HIGH_THREAT|THREAT|LIKELY_THREAT|REVIEW|FP_LIKELY|SAFE",
      "recommended_action": "BLOCK_ALERT|BLOCK|BLOCK_WITH_REVIEW|MANUAL_REVIEW|ALLOW_WITH_LOG|ALLOW",
      "risk_score": "<float: 0.0-100.0>",
      "hierarchical_score": "<float: 0.0-1.0>",

      "quality": {
        "uncertain": "<bool: model uncertainty>",
        "head_agreement": "<bool: heads agree>",
        "binary_margin": "<float: |prob - 0.5|>",
        "family_entropy": "<float: distribution entropy>",
        "consistency_score": "<float: 0.0-1.0>"
      },

      "voting": {
        "decision": "safe|review|threat",
        "confidence": "<float: 0.0-1.0>",
        "preset_used": "balanced|high_security|low_fp",
        "decision_rule_triggered": "<string: rule name>",
        "threat_vote_count": "<int: heads voting THREAT>",
        "safe_vote_count": "<int: heads voting SAFE>",
        "abstain_vote_count": "<int: heads abstaining>",
        "weighted_threat_score": "<float: sum of weighted THREAT votes>",
        "weighted_safe_score": "<float: sum of weighted SAFE votes>",
        "weighted_ratio": "<float: threat_score / safe_score>",
        "per_head_votes": {
          "binary": {
            "vote": "safe|abstain|threat",
            "confidence": "<float: 0.0-1.0>",
            "weight": "<float: head weight>",
            "raw_probability": "<float: 0.0-1.0>",
            "threshold_used": "<float: decision threshold>",
            "prediction": "<string: head prediction>",
            "rationale": "<string: vote explanation>"
          },
          "family": { "...same structure..." },
          "severity": { "...same structure..." },
          "technique": { "...same structure..." },
          "harm": { "...same structure..." }
        },
        "aggregated_scores": {
          "safe": "<float: total safe weight>",
          "threat": "<float: total threat weight>",
          "ratio": "<float: weighted ratio>"
        }
      }
    }
  },

  "_metadata": {
    "received_at": "ISO8601_UTC (backend adds)",
    "api_key_id": "key_<12_hex_chars>",
    "installation_id": "inst_<16_hex_chars>",
    "batch_id": "batch_<32_hex_chars>",
    "region": "<string: GCP region>",
    "api_version": "<string: API version>"
  }
}
```

---

## Field Calculation Rules

### Core Fields

| Field | Calculation | Source |
|-------|-------------|--------|
| `prompt_hash` | `f"sha256:{hashlib.sha256(prompt.encode()).hexdigest()}"` | Input |
| `prompt_length` | `len(prompt)` | Input |
| `threat_detected` | `l1.hit or l2.hit` | Derived |
| `scan_duration_ms` | `(end_time - start_time) * 1000` | Timer |
| `action_taken` | Policy decision | Policy engine |

### Multi-Tenant & Policy Attribution Fields (NEW in v2.3)

| Field | Calculation | Source |
|-------|-------------|--------|
| `tenant_id` | Tenant identifier for multi-tenant deployments | Request/Config |
| `app_id` | Application identifier within tenant | Request/Config |
| `policy_id` | Effective policy ID after resolution | PolicyResolutionResult |
| `policy_name` | Human-readable policy name | TenantPolicy.name |
| `policy_mode` | Policy mode preset (monitor/balanced/strict/custom) | TenantPolicy.mode.value |
| `policy_version` | Policy version for audit trail | TenantPolicy.version |
| `resolution_source` | How the policy was resolved | PolicyResolutionResult.resolution_source |

**Resolution Source Values:**
- `request`: Policy explicitly specified in the scan request
- `app`: Policy resolved from application default
- `tenant`: Policy resolved from tenant default
- `system_default`: System default policy (balanced) used

**Note:** These fields are optional and only present when multi-tenant policy management is active. They support audit/compliance requirements by providing full attribution of which policy was applied to each scan.

### MSSP/Partner Ecosystem Fields (NEW in v3.0)

| Field | Calculation | Source |
|-------|-------------|--------|
| `mssp_id` | MSSP/Partner identifier (must start with 'mssp_') | Request/Config |
| `customer_id` | Customer identifier within MSSP (must start with 'cust_') | Request/Config |
| `agent_id` | Agent identifier (must start with 'agent_') | Request/Config |
| `_mssp_context.data_mode` | Privacy mode ('full' or 'privacy_safe') | Customer config |
| `_mssp_context.customer_name` | Human-readable customer name | Customer config |
| `_mssp_context.data_fields` | List of configured data fields | Customer config |
| `_mssp_data.prompt_text` | Raw prompt text (only when data_mode='full' and 'prompt' in data_fields) | Input |
| `_mssp_data.matched_text` | Array of L1 matched text snippets (only when data_mode='full' and 'matched_text' in data_fields) | L1 detections |
| `agent.version` | RAXE package version | raxe.__version__ |
| `agent.platform` | OS platform (darwin, linux, win32) | sys.platform |
| `agent.integration` | Integration framework if applicable | Request/Config |

**Privacy Notes:**
- `_mssp_context` and `_mssp_data` blocks are ONLY sent to MSSP webhooks, NEVER to RAXE backend
- In `privacy_safe` mode, `_mssp_data` block is not included
- `data_fields` controls which fields appear in `_mssp_data`
- If `data_fields` is empty, all available fields are included in full mode

**Agent Block:**
- `agent.version` comes from `raxe.__version__`
- `agent.platform` comes from `sys.platform`
- `agent.integration` is only present when using an integration (langchain, crewai, etc.)

### L1 Fields

| Field | Calculation | Source |
|-------|-------------|--------|
| `l1.hit` | `l1_result.detection_count > 0` | L1Result |
| `l1.duration_ms` | `l1_result.scan_duration_ms` | L1Result |
| `l1.detection_count` | `len(l1_result.detections)` | L1Result |
| `l1.highest_severity` | `max(d.severity for d in detections)` | L1Result |
| `l1.families` | Extracted from `d.category` field, normalized to uppercase (e.g., "pi" → "PI") | Detection.category |
| `l1.detections[].confidence` | `detection.confidence` (default 1.0) | Detection |

### L2 Fields (5-Head Model)

| Field | Calculation | Source |
|-------|-------------|--------|
| `l2.enabled` | Config check | ScanConfig |
| `l2.hit` | `l2_result.is_threat` property | L2Result |
| `l2.duration_ms` | `l2_result.processing_time_ms` | L2Result |
| `l2.model_version` | `l2_result.model_version` | L2Result |
| `l2.token_count` | Number of tokens after tokenization (max 512) | L2Result.metadata |
| `l2.tokens_truncated` | `original_token_count > 512` | L2Result.metadata |

#### Head 1: Binary (is_threat)

| Field | Calculation | Source |
|-------|-------------|--------|
| `binary.is_threat` | `classification_result.is_threat` | GemmaClassificationResult |
| `binary.threat_probability` | `classification_result.threat_probability` | GemmaClassificationResult |
| `binary.safe_probability` | `classification_result.safe_probability` | GemmaClassificationResult |

#### Head 2: Family (9 classes)

| Field | Calculation | Source |
|-------|-------------|--------|
| `family.prediction` | `classification_result.threat_family.value` | GemmaClassificationResult |
| `family.confidence` | `classification_result.family_confidence` | GemmaClassificationResult |
| `family.top3` | `sorted(zip(labels, probs), key=lambda x: -x[1])[:3]` | family_probabilities |

#### Head 3: Severity (5 classes)

| Field | Calculation | Source |
|-------|-------------|--------|
| `severity.prediction` | `classification_result.severity.value` | GemmaClassificationResult |
| `severity.confidence` | `classification_result.severity_confidence` | GemmaClassificationResult |
| `severity.distribution` | `dict(zip(SEVERITY_LABELS, severity_probabilities))` | severity_probabilities |

#### Head 4: Technique (22 classes)

| Field | Calculation | Source |
|-------|-------------|--------|
| `technique.prediction` | `classification_result.primary_technique.value or None` | GemmaClassificationResult |
| `technique.confidence` | `classification_result.technique_confidence` | GemmaClassificationResult |
| `technique.top3` | `sorted(zip(labels, probs), key=lambda x: -x[1])[:3]` | technique_probabilities |

#### Head 5: Harm Types (10 multilabel)

| Field | Calculation | Source |
|-------|-------------|--------|
| `harm_types.active_labels` | `[h.value for h in harm_types.active_labels]` | MultilabelResult |
| `harm_types.active_count` | `len(active_labels)` | MultilabelResult |
| `harm_types.max_probability` | `max(probabilities.values())` | MultilabelResult |
| `harm_types.probabilities` | `dict(zip(HARM_LABELS, raw_probabilities))` | MultilabelResult |

#### Derived / Ensemble

| Field | Calculation | Source |
|-------|-------------|--------|
| `classification` | Threshold-based mapping | L2Result |
| `recommended_action` | Classification → Action mapping | L2Result |
| `risk_score` | `threat_probability * 100` | Derived |
| `hierarchical_score` | `l2_result.hierarchical_score or confidence` | L2Result |

#### Quality Signals (Drift Detection)

| Field | Calculation | Source |
|-------|-------------|--------|
| `quality.uncertain` | `family_confidence < 0.5 or threat_probability < 0.6` | Derived |
| `quality.head_agreement` | Binary agrees with family (both threat or both benign) | Derived |
| `quality.binary_margin` | `abs(threat_probability - 0.5)` | Derived |
| `quality.family_entropy` | `-sum(p * log(p) for p in family_probs if p > 0)` | Derived |
| `quality.consistency_score` | Custom head agreement metric | Derived |

#### Family Uncertainty Metadata (NEW in v2.2)

When the binary classifier detects a threat but the family classifier returns "benign" with low confidence, this indicates a potential novel attack pattern that doesn't fit known threat families.

| Field | Calculation | Source |
|-------|-------------|--------|
| `metadata.family_uncertain` | `family == "benign" and family_confidence < 0.60` | Derived |
| `metadata.threat_type_display` | `"uncategorized_threat"` when family_uncertain is true | Derived |

**CLI Behavior:** When `family_uncertain` is true, the CLI displays "Uncategorized Threat" instead of "Benign" to avoid user confusion.

#### Voting Engine (NEW in v2.1)

The voting engine provides transparent weighted voting across all 5 classifier heads.

| Field | Calculation | Source |
|-------|-------------|--------|
| `voting.decision` | Final decision (safe, review, threat) | VotingResult |
| `voting.confidence` | Overall confidence in decision | VotingResult |
| `voting.preset_used` | Voting preset name (balanced, high_security, low_fp) | VotingResult |
| `voting.decision_rule_triggered` | Which rule made the final call | VotingResult |
| `voting.threat_vote_count` | Number of heads voting THREAT | VotingResult |
| `voting.safe_vote_count` | Number of heads voting SAFE | VotingResult |
| `voting.abstain_vote_count` | Number of heads abstaining | VotingResult |
| `voting.weighted_threat_score` | Sum of weighted THREAT votes | VotingResult |
| `voting.weighted_safe_score` | Sum of weighted SAFE votes | VotingResult |
| `voting.weighted_ratio` | `weighted_threat / weighted_safe` | Derived |

##### Per-Head Vote Details

Each head in `voting.per_head_votes` contains:

| Field | Description |
|-------|-------------|
| `vote` | Vote cast (safe, abstain, threat) |
| `confidence` | Confidence in the vote (0.0-1.0) |
| `weight` | Weight applied to this head's vote |
| `raw_probability` | Raw model output probability |
| `threshold_used` | Threshold that triggered this vote |
| `prediction` | Head's prediction label |
| `rationale` | Human-readable explanation |

##### Voting Presets

| Preset | Description | Use Case |
|--------|-------------|----------|
| `balanced` | Default, balances FPs and FNs | Most production use cases |
| `high_security` | Lower thresholds, more aggressive | High-risk environments |
| `low_fp` | Higher thresholds, fewer FPs | Cost-sensitive environments |

##### Decision Rules (Priority Order)

1. **High-confidence override**: Any head THREAT + conf >= 85% + 1 other THREAT
2. **Severity veto**: severity="none" -> need 3+ other THREAT votes to override
3. **Min votes**: Need >= min_threat_votes to classify as THREAT
4. **Weighted ratio**: threat_weight / safe_weight >= threat_ratio
5. **Review zone**: ratio in [review_ratio_min, threat_ratio) -> REVIEW
6. **Tie-breaker**: Ties favor SAFE

---

## Enum Values Reference

### L2 Family (15 classes)
```
agent_goal_hijack, benign, data_exfiltration, encoding_or_obfuscation_attack,
human_trust_exploit, inter_agent_attack, jailbreak, memory_poisoning,
other_security, privilege_escalation, prompt_injection, rag_or_context_attack,
rogue_behavior, tool_or_command_abuse, toxic_or_policy_violating_content
```

### L2 Severity (3 classes)
```
none, moderate, severe
```

### L2 Primary Technique (35 classes)
```
none, agent_spoofing, cascade_trigger, chain_of_thought_or_internal_state_leak,
context_or_delimiter_injection, context_poisoning, credential_theft_via_tool,
cross_agent_injection, data_exfil_system_prompt_or_config, data_exfil_user_content,
encoding_or_obfuscation, eval_or_guardrail_evasion, goal_redirection,
hidden_or_steganographic_prompt, identity_confusion, indirect_injection_via_content,
instruction_override, memory_injection, mode_switch_or_privilege_escalation,
multi_turn_or_crescendo, objective_substitution, other_attack_technique,
payload_splitting_or_staging, policy_override_or_rewriting, privilege_escalation_via_tool,
rag_poisoning_or_context_bias, reasoning_manipulation, role_or_persona_manipulation,
safety_bypass_harmful_output, session_hijacking, social_engineering_content,
system_prompt_or_config_extraction, tool_abuse_or_unintended_action,
tool_chain_abuse, tool_or_command_injection
```

### L2 Harm Types (10 classes)
```
cbrn_or_weapons, crime_or_fraud, cybersecurity_or_malware,
hate_or_harassment, misinformation_or_disinfo, other_harm,
privacy_or_pii, self_harm_or_suicide, sexual_content,
violence_or_physical_harm
```

### Classification Thresholds
| Level | Threshold | Action |
|-------|-----------|--------|
| HIGH_THREAT | >= 0.90 | BLOCK_ALERT |
| THREAT | >= 0.75 | BLOCK |
| LIKELY_THREAT | >= 0.60 | BLOCK_WITH_REVIEW |
| REVIEW | >= 0.40 | MANUAL_REVIEW |
| FP_LIKELY | < 0.40 | ALLOW_WITH_LOG |
| SAFE | is_threat=false | ALLOW |

---

## Entry Point Compliance

All telemetry entry points MUST use `ScanTelemetryBuilder`:

| Entry Point | File | Method |
|-------------|------|--------|
| SDK (sync) | `src/raxe/sdk/client.py` | `_track_scan()` |
| SDK (async) | `src/raxe/async_sdk/client.py` | `_track_scan()` |
| CLI scan | Via SDK | Uses SDK |
| CLI batch | Via SDK | Uses SDK |
| Decorators | Via SDK | Uses `raxe.scan()` |
| OpenAI wrapper | Via SDK | Uses `self.raxe.scan()` |
| Anthropic wrapper | Via SDK | Uses `self.raxe.scan()` |

---

## Builder Location

```python
# Canonical builder implementation
from raxe.domain.telemetry.scan_telemetry_builder import ScanTelemetryBuilder

# Usage
builder = ScanTelemetryBuilder()
telemetry = builder.build(
    prompt=prompt,
    l1_result=l1_result,
    l2_result=l2_result,
    scan_duration_ms=duration_ms,
    entry_point="sdk",
    action_taken=policy_action,
    # Policy attribution (optional, for multi-tenant)
    policy_id="balanced",
    policy_name="Balanced Mode",
    policy_mode="balanced",
    policy_version=1,
)
```

---

## Backwards Compatibility

- `schema_version: "3.0.0"` enables MSSP/Partner ecosystem fields
- `schema_version: "2.0.0"` enables L2 and voting engine fields
- Backend accepts v1, v2, and v3 schemas
- v1 events without `schema_version` field are treated as legacy
- MSSP fields (`_mssp_context`, `_mssp_data`, `agent`) are optional and only present when MSSP mode is active

---

## Changelog

### v3.0.0 (2026-01-29)
- **MAJOR**: Added MSSP/Partner Ecosystem support for multi-tenant MSSP deployments
- Added `mssp_id`, `customer_id`, `agent_id` top-level fields for hierarchy identification
- Added `_mssp_context` block containing:
  - `mssp_id`, `customer_id`, `customer_name`: Identification
  - `data_mode`: Privacy mode (full or privacy_safe)
  - `data_fields`: Configured fields for full mode
  - `app_id`, `agent_id`: Optional identifiers
- Added `_mssp_data` block (MSSP webhook only, never sent to RAXE backend):
  - `prompt_text`: Raw prompt text (in full mode when 'prompt' in data_fields)
  - `matched_text`: Array of L1 matched text snippets (in full mode when 'matched_text' in data_fields)
- Added `agent` block containing:
  - `version`: RAXE package version
  - `platform`: OS platform (darwin, linux, win32)
  - `integration`: Integration framework if applicable (langchain, crewai, etc.)
- Privacy: `_mssp_data` block supports configurable privacy modes per customer

### v2.4.0 (2026-01-22)
- Added `l2.token_count`: Number of tokens after tokenization (max 512)
- Added `l2.tokens_truncated`: Boolean flag indicating if input was truncated
- These fields help monitor tokenization behavior and detect input truncation
- Token count reveals encoding length without exposing actual token IDs (privacy-safe)

### v2.3.0 (2026-01-13)
- Added policy attribution fields for multi-tenant support:
  - `policy_id`: Effective policy identifier after resolution
  - `policy_name`: Human-readable policy name for display
  - `policy_mode`: Policy mode preset (monitor/balanced/strict/custom)
  - `policy_version`: Version number for audit trail and change tracking
- These fields support audit/billing visibility requirements (Jose Lopez feedback)

### v2.2.0 (2026-01-12)
- Fixed L1 family extraction to read from `Detection.category` field (was incorrectly looking for non-existent `family` field)
- Added `L1_CATEGORY_TO_FAMILY` mapping for consistent uppercase family codes (e.g., "pi" → "PI")
- Added `metadata.family_uncertain` flag for L2 when binary=threat but family=benign with low confidence
- Added `metadata.threat_type_display` for CLI to show "Uncategorized Threat" in uncertain cases

### v2.1.0 (2025-12-13)
- Added `l2.voting` block for ensemble voting engine transparency
- Added per-head vote details with confidence, weight, and rationale
- Added voting presets (balanced, high_security, low_fp)
- Added decision rule tracking for explainability
- Added weighted vote counts and ratio calculations

### v2.0.0 (2025-12-12)
- Added full L2 telemetry block with all 5 heads
- Added `l1.detections[]` per-rule breakdown
- Added `l2.quality` signals for drift detection
- Added `schema_version` field
- Restructured L1/L2 into nested blocks
- Added `top3` distributions for family/technique
- Added full `harm_types.probabilities` dict
