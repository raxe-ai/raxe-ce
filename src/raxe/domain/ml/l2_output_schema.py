"""L2 Gemma Model Output Schema.

This module documents the complete output structure from the Gemma 5-head
multilabel classifier. Use this as the canonical reference for all layers
(detector, pipeline, SDK, CLI, telemetry).

Model Architecture:
==================
The Gemma classifier uses 5 independent classification heads:

1. is_threat (binary) - Determines if input is a threat
2. threat_family (multiclass, 9) - Categorizes threat type
3. severity (multiclass, 5) - Assesses threat severity
4. primary_technique (multiclass, 22) - Identifies attack technique (threats only)
5. harm_types (multilabel, 10) - Identifies potential harms (threats only)

Data Flow:
=========
GemmaL2Detector → L2Result → ScanPipelineResult → SDK/CLI/Telemetry

Field Naming Conventions:
========================
- Model fields use snake_case (e.g., threat_family, primary_technique)
- Confidence fields are 0.0-1.0 floats
- Probability distributions are tuples/lists of floats summing to 1.0 (softmax)
- Multilabel probabilities are independent 0.0-1.0 values (sigmoid)
"""
from dataclasses import dataclass
from typing import Any

# =============================================================================
# HEAD 1: is_threat (Binary Classification)
# =============================================================================
IS_THREAT_SCHEMA = {
    "head_name": "is_threat",
    "type": "binary",
    "classes": ["benign", "threat"],
    "output_fields": {
        "is_threat": {
            "type": "bool",
            "description": "True if classified as threat",
            "source": "argmax(probabilities) == 1",
        },
        "threat_probability": {
            "type": "float",
            "range": [0.0, 1.0],
            "description": "Probability of threat class",
            "telemetry_key": "scores.attack_probability",
        },
        "safe_probability": {
            "type": "float",
            "range": [0.0, 1.0],
            "description": "Probability of benign class",
            "note": "safe_probability + threat_probability = 1.0",
        },
    },
}

# =============================================================================
# HEAD 2: threat_family (Multiclass, 9 classes)
# =============================================================================
THREAT_FAMILY_SCHEMA = {
    "head_name": "threat_family",
    "type": "multiclass",
    "num_classes": 9,
    "classes": [
        "benign",
        "data_exfiltration",
        "encoding_or_obfuscation_attack",
        "jailbreak",
        "other_security",
        "prompt_injection",
        "rag_or_context_attack",
        "tool_or_command_abuse",
        "toxic_or_policy_violating_content",
    ],
    "output_fields": {
        "threat_family": {
            "type": "str",
            "description": "Predicted threat family name",
            "telemetry_key": "family",
        },
        "family_confidence": {
            "type": "float",
            "range": [0.0, 1.0],
            "description": "Confidence in family prediction (max probability)",
            "telemetry_key": "scores.family_confidence",
        },
        "family_probabilities": {
            "type": "tuple[float, ...]",
            "length": 9,
            "description": "Full probability distribution over all families",
            "note": "Sums to 1.0 (softmax output)",
        },
    },
}

# =============================================================================
# HEAD 3: severity (Multiclass, 5 classes)
# =============================================================================
SEVERITY_SCHEMA = {
    "head_name": "severity",
    "type": "multiclass",
    "num_classes": 5,
    "classes": ["none", "low", "medium", "high", "critical"],
    "output_fields": {
        "severity": {
            "type": "str",
            "description": "Predicted severity level",
            "telemetry_key": "severity",
        },
        "severity_confidence": {
            "type": "float",
            "range": [0.0, 1.0],
            "description": "Confidence in severity prediction",
            "telemetry_key": "scores.severity_confidence",
        },
        "severity_probabilities": {
            "type": "tuple[float, ...]",
            "length": 5,
            "description": "Full probability distribution over severity levels",
        },
    },
}

# =============================================================================
# HEAD 4: primary_technique (Multiclass, 22 classes) - THREATS ONLY
# =============================================================================
PRIMARY_TECHNIQUE_SCHEMA = {
    "head_name": "primary_technique",
    "type": "multiclass",
    "num_classes": 22,
    "condition": "is_threat == True",
    "classes": [
        "chain_of_thought_or_internal_state_leak",
        "context_or_delimiter_injection",
        "data_exfil_system_prompt_or_config",
        "data_exfil_user_content",
        "encoding_or_obfuscation",
        "eval_or_guardrail_evasion",
        "hidden_or_steganographic_prompt",
        "indirect_injection_via_content",
        "instruction_override",
        "mode_switch_or_privilege_escalation",
        "multi_turn_or_crescendo",
        "none",
        "other_attack_technique",
        "payload_splitting_or_staging",
        "policy_override_or_rewriting",
        "rag_poisoning_or_context_bias",
        "role_or_persona_manipulation",
        "safety_bypass_harmful_output",
        "social_engineering_content",
        "system_prompt_or_config_extraction",
        "tool_abuse_or_unintended_action",
        "tool_or_command_injection",
    ],
    "output_fields": {
        "primary_technique": {
            "type": "str | None",
            "description": "Predicted attack technique (None if benign)",
            "telemetry_key": "primary_technique",
            "alias": "sub_family",  # For CLI formatter compatibility
        },
        "technique_confidence": {
            "type": "float",
            "range": [0.0, 1.0],
            "description": "Confidence in technique prediction",
            "telemetry_key": "technique_confidence",
            "alias_key": "scores.subfamily_confidence",  # For CLI formatter
        },
        "technique_probabilities": {
            "type": "tuple[float, ...] | None",
            "length": 22,
            "description": "Full probability distribution over techniques",
        },
    },
}

# =============================================================================
# HEAD 5: harm_types (Multilabel, 10 classes) - THREATS ONLY
# =============================================================================
HARM_TYPES_SCHEMA = {
    "head_name": "harm_types",
    "type": "multilabel",
    "num_classes": 10,
    "condition": "is_threat == True",
    "classes": [
        "cbrn_or_weapons",
        "crime_or_fraud",
        "cybersecurity_or_malware",
        "hate_or_harassment",
        "misinformation_or_disinfo",
        "other_harm",
        "privacy_or_pii",
        "self_harm_or_suicide",
        "sexual_content",
        "violence_or_physical_harm",
    ],
    "default_thresholds": {
        "cbrn_or_weapons": 0.5,
        "crime_or_fraud": 0.5,
        "cybersecurity_or_malware": 0.5,
        "hate_or_harassment": 0.5,
        "misinformation_or_disinfo": 0.5,
        "other_harm": 0.5,
        "privacy_or_pii": 0.4,  # Lower for safety
        "self_harm_or_suicide": 0.4,  # Lower for safety
        "sexual_content": 0.5,
        "violence_or_physical_harm": 0.4,  # Lower for safety
    },
    "output_fields": {
        "harm_types": {
            "type": "dict",
            "description": "Multilabel harm classification result",
            "telemetry_key": "harm_types",
            "subfields": {
                "active_labels": {
                    "type": "list[str]",
                    "description": "Harm types exceeding threshold",
                },
                "probabilities": {
                    "type": "dict[str, float]",
                    "description": "Probability for each harm type (0.0-1.0)",
                    "note": "Independent probabilities (sigmoid), don't sum to 1",
                },
                "thresholds_used": {
                    "type": "dict[str, float]",
                    "description": "Threshold used for each harm type",
                },
                "active_count": {
                    "type": "int",
                    "description": "Number of active harm labels",
                },
                "max_probability": {
                    "type": "float",
                    "description": "Highest probability among all harm types",
                },
            },
        },
    },
}

# =============================================================================
# DERIVED FIELDS (Computed from model outputs)
# =============================================================================
DERIVED_FIELDS_SCHEMA = {
    "classification": {
        "type": "str",
        "values": [
            "HIGH_THREAT",  # threat_probability >= 0.9
            "THREAT",  # threat_probability >= 0.75
            "LIKELY_THREAT",  # threat_probability >= 0.6
            "REVIEW",  # threat_probability >= 0.4
            "FP_LIKELY",  # threat_probability < 0.4
            "SAFE",  # is_threat == False
        ],
        "description": "Classification label derived from threat probability",
    },
    "action": {
        "type": "str",
        "values": [
            "BLOCK_ALERT",  # HIGH_THREAT
            "BLOCK",  # THREAT
            "BLOCK_WITH_REVIEW",  # LIKELY_THREAT
            "MANUAL_REVIEW",  # REVIEW
            "ALLOW_WITH_LOG",  # FP_LIKELY
            "ALLOW",  # SAFE
        ],
        "description": "Recommended action based on classification",
    },
    "risk_score": {
        "type": "float",
        "range": [0.0, 100.0],
        "description": "Risk score (threat_probability * 100)",
    },
    "hierarchical_score": {
        "type": "float",
        "range": [0.0, 1.0],
        "description": "Hierarchical confidence score (same as threat_probability)",
    },
    "uncertain": {
        "type": "bool",
        "description": "True if family_confidence < 0.5 or threat_probability < 0.6",
    },
    "why_it_hit": {
        "type": "list[str]",
        "description": "Human-readable explanations for detection",
    },
    "recommended_action": {
        "type": "list[str]",
        "description": "List of recommended security actions",
    },
}

# =============================================================================
# COMPLETE L2 PREDICTION METADATA SCHEMA
# =============================================================================
L2_PREDICTION_METADATA_SCHEMA = {
    "description": "Complete metadata structure in L2Prediction.metadata",
    "fields": {
        # Core model outputs
        "is_attack": {"type": "bool", "source": "is_threat"},
        "family": {"type": "str", "source": "threat_family.value"},
        "severity": {"type": "str", "source": "severity.value"},
        "primary_technique": {"type": "str | None", "source": "primary_technique.value"},
        "technique_confidence": {"type": "float", "source": "technique_confidence"},
        "sub_family": {"type": "str | None", "alias_of": "primary_technique"},
        "harm_types": {"type": "dict | None", "source": "harm_types.to_dict()"},
        # Confidence scores
        "scores": {
            "type": "dict",
            "fields": {
                "attack_probability": {"source": "threat_probability"},
                "family_confidence": {"source": "family_confidence"},
                "severity_confidence": {"source": "severity_confidence"},
                "subfamily_confidence": {"source": "technique_confidence"},
            },
        },
        # Derived fields
        "classification": {"type": "str", "computed": True},
        "action": {"type": "str", "computed": True},
        "risk_score": {"type": "float", "computed": True},
        "hierarchical_score": {"type": "float", "computed": True},
        "uncertain": {"type": "bool", "computed": True},
        "why_it_hit": {"type": "list[str]", "computed": True},
        "recommended_action": {"type": "list[str]", "computed": True},
    },
}

# =============================================================================
# TELEMETRY FIELD MAPPING
# =============================================================================
TELEMETRY_FIELD_MAPPING = {
    "description": "Mapping from model fields to telemetry event fields",
    "l2_predictions": {
        "threat_type": "L2ThreatType mapped from family",
        "confidence": "threat_probability",
        "features_used": "List of feature strings",
        "metadata": "Full L2_PREDICTION_METADATA_SCHEMA",
    },
    "l2_metadata": {
        "overall_confidence": "L2Result.confidence",
        "processing_time_ms": "L2Result.processing_time_ms",
        "model_version": "L2Result.model_version",
        "hierarchical_score": "L2Result.hierarchical_score (if available)",
        "classification": "L2Result.classification (if available)",
        "signal_quality": "L2Result.signal_quality (if available)",
    },
}

# =============================================================================
# CLI DISPLAY FIELD MAPPING
# =============================================================================
CLI_DISPLAY_MAPPING = {
    "description": "Fields displayed in CLI output",
    "default_mode": {
        "Classification": "metadata.classification",
        "Risk Score": "metadata.risk_score",
        "Final Decision": "metadata.action + hierarchical_score",
        "Confidence": "binary + family + subfamily percentages",
    },
    "explain_mode": {
        "Classification": "metadata.classification",
        "Confidence": "metadata.hierarchical_score * 100",
        "Why This Was Flagged": "metadata.why_it_hit",
        "Confidence Signals": {
            "Binary Threat": "scores.attack_probability",
            "Threat Family": "family + scores.family_confidence",
            "Subfamily": "sub_family + scores.subfamily_confidence",
        },
        "Hierarchical Score": "metadata.hierarchical_score * 100",
        "Signal Quality": {
            "Consistency": "metadata.is_consistent (computed)",
            "Binary Margin": "metadata.margins.binary (computed)",
            "Weak Margins": "metadata.weak_margins_count (computed)",
        },
        "Decision Rationale": "metadata.reason",
        "Recommended Action": "metadata.action",
    },
}


@dataclass
class L2OutputSchema:
    """Container for complete L2 output schema documentation."""

    is_threat = IS_THREAT_SCHEMA
    threat_family = THREAT_FAMILY_SCHEMA
    severity = SEVERITY_SCHEMA
    primary_technique = PRIMARY_TECHNIQUE_SCHEMA
    harm_types = HARM_TYPES_SCHEMA
    derived_fields = DERIVED_FIELDS_SCHEMA
    prediction_metadata = L2_PREDICTION_METADATA_SCHEMA
    telemetry_mapping = TELEMETRY_FIELD_MAPPING
    cli_mapping = CLI_DISPLAY_MAPPING

    @classmethod
    def get_all_model_fields(cls) -> dict[str, Any]:
        """Get all fields output by the model."""
        return {
            "is_threat": cls.is_threat,
            "threat_family": cls.threat_family,
            "severity": cls.severity,
            "primary_technique": cls.primary_technique,
            "harm_types": cls.harm_types,
        }

    @classmethod
    def get_required_telemetry_fields(cls) -> list[str]:
        """Get fields that MUST be sent in telemetry."""
        return [
            "threat_type",
            "confidence",
            "metadata.is_attack",
            "metadata.family",
            "metadata.severity",
            "metadata.scores.attack_probability",
            "metadata.scores.family_confidence",
            "metadata.scores.severity_confidence",
            "metadata.scores.subfamily_confidence",
            "metadata.primary_technique",
            "metadata.harm_types",
            "metadata.classification",
            "metadata.action",
            "metadata.risk_score",
        ]

    @classmethod
    def get_required_cli_fields(cls) -> list[str]:
        """Get fields that MUST be displayed in CLI."""
        return [
            "classification",
            "risk_score",
            "action",
            "threat_type",
            "family",
            "subfamily (primary_technique)",
            "scores.attack_probability",
            "scores.family_confidence",
            "scores.subfamily_confidence",
            "why_it_hit",
        ]
