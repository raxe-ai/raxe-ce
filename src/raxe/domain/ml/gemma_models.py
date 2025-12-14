"""Domain models for Gemma-based 5-head multilabel classifier.

Pure domain models - NO I/O operations.
These models represent the classification outputs from the Gemma ML model.

Model Architecture:
- is_threat: Binary classifier (benign/threat)
- threat_family: 9-class multiclass
- severity: 5-class multiclass
- primary_technique: 22-class multiclass (threats only)
- harm_types: 10-class MULTILABEL (threats only)
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ThreatFamily(Enum):
    """Threat family classifications from Gemma model (9 classes)."""
    BENIGN = "benign"
    DATA_EXFILTRATION = "data_exfiltration"
    ENCODING_OR_OBFUSCATION_ATTACK = "encoding_or_obfuscation_attack"
    JAILBREAK = "jailbreak"
    OTHER_SECURITY = "other_security"
    PROMPT_INJECTION = "prompt_injection"
    RAG_OR_CONTEXT_ATTACK = "rag_or_context_attack"
    TOOL_OR_COMMAND_ABUSE = "tool_or_command_abuse"
    TOXIC_OR_POLICY_VIOLATING_CONTENT = "toxic_or_policy_violating_content"

    @classmethod
    def from_index(cls, index: int) -> "ThreatFamily":
        """Convert model output index to ThreatFamily."""
        classes = [
            cls.BENIGN,
            cls.DATA_EXFILTRATION,
            cls.ENCODING_OR_OBFUSCATION_ATTACK,
            cls.JAILBREAK,
            cls.OTHER_SECURITY,
            cls.PROMPT_INJECTION,
            cls.RAG_OR_CONTEXT_ATTACK,
            cls.TOOL_OR_COMMAND_ABUSE,
            cls.TOXIC_OR_POLICY_VIOLATING_CONTENT,
        ]
        if 0 <= index < len(classes):
            return classes[index]
        return cls.BENIGN


class Severity(Enum):
    """Severity levels from Gemma model (5 classes)."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_index(cls, index: int) -> "Severity":
        """Convert model output index to Severity."""
        classes = [cls.NONE, cls.LOW, cls.MEDIUM, cls.HIGH, cls.CRITICAL]
        if 0 <= index < len(classes):
            return classes[index]
        return cls.NONE


class PrimaryTechnique(Enum):
    """Primary attack technique classifications (22 classes).

    These represent specific attack vectors detected by the model.
    Only populated when is_threat=True.
    """
    CHAIN_OF_THOUGHT_OR_INTERNAL_STATE_LEAK = "chain_of_thought_or_internal_state_leak"
    CONTEXT_OR_DELIMITER_INJECTION = "context_or_delimiter_injection"
    DATA_EXFIL_SYSTEM_PROMPT_OR_CONFIG = "data_exfil_system_prompt_or_config"
    DATA_EXFIL_USER_CONTENT = "data_exfil_user_content"
    ENCODING_OR_OBFUSCATION = "encoding_or_obfuscation"
    EVAL_OR_GUARDRAIL_EVASION = "eval_or_guardrail_evasion"
    HIDDEN_OR_STEGANOGRAPHIC_PROMPT = "hidden_or_steganographic_prompt"
    INDIRECT_INJECTION_VIA_CONTENT = "indirect_injection_via_content"
    INSTRUCTION_OVERRIDE = "instruction_override"
    MODE_SWITCH_OR_PRIVILEGE_ESCALATION = "mode_switch_or_privilege_escalation"
    MULTI_TURN_OR_CRESCENDO = "multi_turn_or_crescendo"
    NONE = "none"
    OTHER_ATTACK_TECHNIQUE = "other_attack_technique"
    PAYLOAD_SPLITTING_OR_STAGING = "payload_splitting_or_staging"
    POLICY_OVERRIDE_OR_REWRITING = "policy_override_or_rewriting"
    RAG_POISONING_OR_CONTEXT_BIAS = "rag_poisoning_or_context_bias"
    ROLE_OR_PERSONA_MANIPULATION = "role_or_persona_manipulation"
    SAFETY_BYPASS_HARMFUL_OUTPUT = "safety_bypass_harmful_output"
    SOCIAL_ENGINEERING_CONTENT = "social_engineering_content"
    SYSTEM_PROMPT_OR_CONFIG_EXTRACTION = "system_prompt_or_config_extraction"
    TOOL_ABUSE_OR_UNINTENDED_ACTION = "tool_abuse_or_unintended_action"
    TOOL_OR_COMMAND_INJECTION = "tool_or_command_injection"

    @classmethod
    def from_index(cls, index: int) -> "PrimaryTechnique":
        """Convert model output index to PrimaryTechnique."""
        classes = [
            cls.CHAIN_OF_THOUGHT_OR_INTERNAL_STATE_LEAK,
            cls.CONTEXT_OR_DELIMITER_INJECTION,
            cls.DATA_EXFIL_SYSTEM_PROMPT_OR_CONFIG,
            cls.DATA_EXFIL_USER_CONTENT,
            cls.ENCODING_OR_OBFUSCATION,
            cls.EVAL_OR_GUARDRAIL_EVASION,
            cls.HIDDEN_OR_STEGANOGRAPHIC_PROMPT,
            cls.INDIRECT_INJECTION_VIA_CONTENT,
            cls.INSTRUCTION_OVERRIDE,
            cls.MODE_SWITCH_OR_PRIVILEGE_ESCALATION,
            cls.MULTI_TURN_OR_CRESCENDO,
            cls.NONE,
            cls.OTHER_ATTACK_TECHNIQUE,
            cls.PAYLOAD_SPLITTING_OR_STAGING,
            cls.POLICY_OVERRIDE_OR_REWRITING,
            cls.RAG_POISONING_OR_CONTEXT_BIAS,
            cls.ROLE_OR_PERSONA_MANIPULATION,
            cls.SAFETY_BYPASS_HARMFUL_OUTPUT,
            cls.SOCIAL_ENGINEERING_CONTENT,
            cls.SYSTEM_PROMPT_OR_CONFIG_EXTRACTION,
            cls.TOOL_ABUSE_OR_UNINTENDED_ACTION,
            cls.TOOL_OR_COMMAND_INJECTION,
        ]
        if 0 <= index < len(classes):
            return classes[index]
        return cls.NONE


class HarmType(Enum):
    """Harm type classifications (MULTILABEL - 10 classes).

    Multiple harm types can be active for a single detection.
    Only populated when is_threat=True.
    """
    CBRN_OR_WEAPONS = "cbrn_or_weapons"
    CRIME_OR_FRAUD = "crime_or_fraud"
    CYBERSECURITY_OR_MALWARE = "cybersecurity_or_malware"
    HATE_OR_HARASSMENT = "hate_or_harassment"
    MISINFORMATION_OR_DISINFO = "misinformation_or_disinfo"
    OTHER_HARM = "other_harm"
    PRIVACY_OR_PII = "privacy_or_pii"
    SELF_HARM_OR_SUICIDE = "self_harm_or_suicide"
    SEXUAL_CONTENT = "sexual_content"
    VIOLENCE_OR_PHYSICAL_HARM = "violence_or_physical_harm"

    @classmethod
    def from_index(cls, index: int) -> "HarmType":
        """Convert model output index to HarmType."""
        classes = [
            cls.CBRN_OR_WEAPONS,
            cls.CRIME_OR_FRAUD,
            cls.CYBERSECURITY_OR_MALWARE,
            cls.HATE_OR_HARASSMENT,
            cls.MISINFORMATION_OR_DISINFO,
            cls.OTHER_HARM,
            cls.PRIVACY_OR_PII,
            cls.SELF_HARM_OR_SUICIDE,
            cls.SEXUAL_CONTENT,
            cls.VIOLENCE_OR_PHYSICAL_HARM,
        ]
        if 0 <= index < len(classes):
            return classes[index]
        return cls.OTHER_HARM

    @classmethod
    def all_classes(cls) -> list["HarmType"]:
        """Return all harm type classes in order."""
        return [
            cls.CBRN_OR_WEAPONS,
            cls.CRIME_OR_FRAUD,
            cls.CYBERSECURITY_OR_MALWARE,
            cls.HATE_OR_HARASSMENT,
            cls.MISINFORMATION_OR_DISINFO,
            cls.OTHER_HARM,
            cls.PRIVACY_OR_PII,
            cls.SELF_HARM_OR_SUICIDE,
            cls.SEXUAL_CONTENT,
            cls.VIOLENCE_OR_PHYSICAL_HARM,
        ]


@dataclass(frozen=True)
class MultilabelResult:
    """Result from multilabel classification head (harm_types).

    Unlike multiclass (softmax), multilabel uses sigmoid activation
    and each class is independently predicted.

    Attributes:
        active_labels: Labels that exceeded their threshold
        probabilities: All label probabilities (0.0-1.0 each)
        thresholds_used: Threshold used per label for decision
    """
    active_labels: tuple[HarmType, ...]
    probabilities: dict[str, float]  # HarmType.value -> probability
    thresholds_used: dict[str, float]  # HarmType.value -> threshold

    @property
    def has_active_labels(self) -> bool:
        """True if any harm type exceeded threshold."""
        return len(self.active_labels) > 0

    @property
    def active_count(self) -> int:
        """Number of active harm labels."""
        return len(self.active_labels)

    @property
    def highest_probability_label(self) -> tuple[HarmType | None, float]:
        """Get label with highest probability."""
        if not self.probabilities:
            return None, 0.0
        max_key = max(self.probabilities, key=lambda k: self.probabilities[k])
        # Convert string key back to HarmType
        for harm_type in HarmType:
            if harm_type.value == max_key:
                return harm_type, self.probabilities[max_key]
        return None, 0.0

    @property
    def max_probability(self) -> float:
        """Get maximum probability across all harm types."""
        if not self.probabilities:
            return 0.0
        return max(self.probabilities.values())

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "active_labels": [label.value for label in self.active_labels],
            "probabilities": self.probabilities,
            "thresholds_used": self.thresholds_used,
            "active_count": self.active_count,
            "max_probability": self.max_probability,
        }


@dataclass(frozen=True)
class GemmaClassificationResult:
    """Complete classification result from Gemma 5-head model.

    Immutable value object containing all head outputs.

    Attributes:
        is_threat: Binary classification result
        threat_probability: Probability of threat (0.0-1.0)
        safe_probability: Probability of benign (0.0-1.0)
        threat_family: Predicted family
        family_confidence: Confidence in family prediction
        family_probabilities: Full family probability distribution
        severity: Predicted severity
        severity_confidence: Confidence in severity
        severity_probabilities: Full severity probability distribution
        primary_technique: Predicted technique (if threat)
        technique_confidence: Confidence in technique
        technique_probabilities: Full technique probability distribution
        harm_types: Multilabel harm types result (if threat)
    """
    # Binary head
    is_threat: bool
    threat_probability: float
    safe_probability: float

    # Family head (always populated)
    threat_family: ThreatFamily
    family_confidence: float
    family_probabilities: tuple[float, ...]

    # Severity head (always populated)
    severity: Severity
    severity_confidence: float
    severity_probabilities: tuple[float, ...]

    # Primary technique head (only if threat)
    primary_technique: PrimaryTechnique | None
    technique_confidence: float
    technique_probabilities: tuple[float, ...] | None

    # Harm types head (only if threat, MULTILABEL)
    harm_types: MultilabelResult | None

    # Ensemble debug info
    raw_threat_probability: float | None = None  # Original binary head output
    family_override_triggered: bool = False  # True if family override was applied

    def __post_init__(self) -> None:
        """Validate classification result."""
        if not 0.0 <= self.threat_probability <= 1.0:
            raise ValueError(
                f"threat_probability must be 0-1, got {self.threat_probability}"
            )
        if not 0.0 <= self.safe_probability <= 1.0:
            raise ValueError(
                f"safe_probability must be 0-1, got {self.safe_probability}"
            )
        if not 0.0 <= self.family_confidence <= 1.0:
            raise ValueError(
                f"family_confidence must be 0-1, got {self.family_confidence}"
            )
        if not 0.0 <= self.severity_confidence <= 1.0:
            raise ValueError(
                f"severity_confidence must be 0-1, got {self.severity_confidence}"
            )
        if not 0.0 <= self.technique_confidence <= 1.0:
            raise ValueError(
                f"technique_confidence must be 0-1, got {self.technique_confidence}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict for telemetry/logging."""
        result = {
            "is_threat": self.is_threat,
            "threat_probability": self.threat_probability,
            "safe_probability": self.safe_probability,
            "threat_family": self.threat_family.value,
            "family_confidence": self.family_confidence,
            "severity": self.severity.value,
            "severity_confidence": self.severity_confidence,
        }

        if self.primary_technique is not None:
            result["primary_technique"] = self.primary_technique.value
            result["technique_confidence"] = self.technique_confidence

        if self.harm_types is not None:
            result["harm_types"] = self.harm_types.to_dict()

        # Ensemble debug info
        if self.raw_threat_probability is not None:
            result["raw_threat_probability"] = self.raw_threat_probability
        result["family_override_triggered"] = self.family_override_triggered

        return result


# Default thresholds for multilabel harm_types classification
DEFAULT_HARM_THRESHOLDS: dict[str, float] = {
    HarmType.CBRN_OR_WEAPONS.value: 0.5,
    HarmType.CRIME_OR_FRAUD.value: 0.5,
    HarmType.CYBERSECURITY_OR_MALWARE.value: 0.5,
    HarmType.HATE_OR_HARASSMENT.value: 0.5,
    HarmType.MISINFORMATION_OR_DISINFO.value: 0.5,
    HarmType.OTHER_HARM.value: 0.5,
    HarmType.PRIVACY_OR_PII.value: 0.4,  # Lower for privacy - safety critical
    HarmType.SELF_HARM_OR_SUICIDE.value: 0.4,  # Lower for safety
    HarmType.SEXUAL_CONTENT.value: 0.5,
    HarmType.VIOLENCE_OR_PHYSICAL_HARM.value: 0.4,  # Lower for safety
}
