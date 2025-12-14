"""L2 Detection Configuration - Threshold and Ensemble Rules.

This module provides configurable thresholds for the 5-head Gemma classifier.
Configuration can be loaded from:
1. Environment variables (RAXE_L2_*)
2. Config file (~/.raxe/l2_config.yaml or ./l2_config.yaml)
3. Programmatic overrides

NEW: Voting Engine Configuration
The voting engine replaces boost-based ensemble logic with weighted voting.
Use voting_preset to select: balanced (default), high_security, low_fp, or harm_focused.

Example config file (l2_config.yaml):
```yaml
# NEW: Voting engine preset (replaces ensemble section)
voting:
  preset: balanced  # balanced | high_security | low_fp | harm_focused

thresholds:
  threat: 0.35
  family_override: 0.25
  severity_min: 0.30
  technique_min: 0.20
  harm_type: 0.50

harm_type_thresholds:
  privacy_or_pii: 0.40
  self_harm_or_suicide: 0.40
  violence_or_physical_harm: 0.40
```
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from raxe.domain.ml.voting import VotingPreset, get_voting_config


@dataclass
class L2ThresholdConfig:
    """Configuration for L2 detection thresholds.

    All threshold values are floats between 0.0 and 1.0.
    """

    # Primary threat threshold (is_threat binary classifier)
    threat_threshold: float = 0.35

    # Family override: if family != benign AND confidence >= this, classify as threat
    # even if is_threat is below threat_threshold
    family_override_threshold: float = 0.25

    # Minimum confidence to report severity (below this, use "unknown")
    severity_min_confidence: float = 0.30

    # Minimum confidence to report technique (below this, use "unknown")
    technique_min_confidence: float = 0.20

    # Default threshold for multilabel harm types
    harm_type_default_threshold: float = 0.50

    # Per-harm-type thresholds (lower for safety-critical types)
    harm_type_thresholds: dict[str, float] = field(default_factory=lambda: {
        "cbrn_or_weapons": 0.50,
        "crime_or_fraud": 0.50,
        "cybersecurity_or_malware": 0.50,
        "hate_or_harassment": 0.50,
        "misinformation_or_disinfo": 0.50,
        "other_harm": 0.50,
        "privacy_or_pii": 0.40,  # Lower for safety
        "self_harm_or_suicide": 0.40,  # Lower for safety
        "sexual_content": 0.50,
        "violence_or_physical_harm": 0.40,  # Lower for safety
    })

    def get_harm_threshold(self, harm_type: str) -> float:
        """Get threshold for a specific harm type."""
        return self.harm_type_thresholds.get(
            harm_type, self.harm_type_default_threshold
        )


@dataclass
class L2EnsembleConfig:
    """Configuration for ensemble decision logic.

    The ensemble combines multiple classifier heads to make the final decision.
    """

    # Use family override: threat if family != benign even when is_threat is low
    use_family_override: bool = True

    # Boost threat probability when severity head predicts high/critical
    use_severity_boost: bool = True
    severity_boost_amount: float = 0.15  # Add this to threat_prob for high/critical

    # Boost threat probability when technique head is confident about an attack
    use_technique_boost: bool = True
    technique_boost_threshold: float = 0.60
    technique_boost_amount: float = 0.10

    # Families that should ALWAYS trigger threat (even if is_threat is very low)
    always_threat_families: list[str] = field(default_factory=lambda: [
        # "jailbreak",  # Uncomment to always flag jailbreak attempts
        # "data_exfiltration",  # Uncomment to always flag exfil attempts
    ])

    # Techniques that indicate high confidence threat
    high_confidence_techniques: list[str] = field(default_factory=lambda: [
        "instruction_override",
        "system_prompt_or_config_extraction",
        "tool_or_command_injection",
        "data_exfil_system_prompt_or_config",
        "data_exfil_user_content",
    ])


@dataclass
class L2VotingConfig:
    """Configuration for the ensemble voting engine.

    The voting engine replaces boost-based ensemble logic with weighted
    voting across all 5 classifier heads.

    Attributes:
        enabled: Enable voting engine (default: True, set False to use legacy ensemble)
        preset: Voting preset name (balanced, high_security, low_fp)
    """

    enabled: bool = True
    preset: str = "balanced"  # balanced | high_security | low_fp


@dataclass
class L2Config:
    """Complete L2 detection configuration."""

    thresholds: L2ThresholdConfig = field(default_factory=L2ThresholdConfig)
    ensemble: L2EnsembleConfig = field(default_factory=L2EnsembleConfig)
    voting: L2VotingConfig = field(default_factory=L2VotingConfig)

    # Classification labels based on threat probability
    classification_thresholds: dict[str, float] = field(default_factory=lambda: {
        "HIGH_THREAT": 0.90,
        "THREAT": 0.75,
        "LIKELY_THREAT": 0.60,
        "REVIEW": 0.40,
        "FP_LIKELY": 0.0,  # Below 0.40
    })

    def get_classification(self, threat_prob: float) -> str:
        """Get classification label based on threat probability."""
        if threat_prob >= self.classification_thresholds["HIGH_THREAT"]:
            return "HIGH_THREAT"
        elif threat_prob >= self.classification_thresholds["THREAT"]:
            return "THREAT"
        elif threat_prob >= self.classification_thresholds["LIKELY_THREAT"]:
            return "LIKELY_THREAT"
        elif threat_prob >= self.classification_thresholds["REVIEW"]:
            return "REVIEW"
        else:
            return "FP_LIKELY"

    def get_action(self, classification: str) -> str:
        """Get recommended action based on classification."""
        actions = {
            "HIGH_THREAT": "BLOCK_ALERT",
            "THREAT": "BLOCK",
            "LIKELY_THREAT": "BLOCK_WITH_REVIEW",
            "REVIEW": "MANUAL_REVIEW",
            "FP_LIKELY": "ALLOW_WITH_LOG",
            "SAFE": "ALLOW",
        }
        return actions.get(classification, "MANUAL_REVIEW")


# Global config instance
_config: L2Config | None = None


def get_l2_config() -> L2Config:
    """Get the current L2 configuration.

    Loads from config file or environment on first call.
    """
    global _config
    if _config is None:
        _config = load_l2_config()
    return _config


def set_l2_config(config: L2Config) -> None:
    """Set the L2 configuration programmatically."""
    global _config
    _config = config


def reset_l2_config() -> None:
    """Reset to default configuration."""
    global _config
    _config = None


def load_l2_config() -> L2Config:
    """Load L2 configuration from file and environment.

    Priority (highest to lowest):
    1. Environment variables (RAXE_L2_*)
    2. Local config file (./l2_config.yaml)
    3. User config file (~/.raxe/l2_config.yaml)
    4. Default values
    """
    config = L2Config()

    # Try to load from config files
    config_paths = [
        Path("./l2_config.yaml"),
        Path("./l2_config.yml"),
        Path.home() / ".raxe" / "l2_config.yaml",
        Path.home() / ".raxe" / "l2_config.yml",
    ]

    for config_path in config_paths:
        if config_path.exists():
            try:
                config = _load_config_file(config_path)
                break
            except Exception:
                pass  # Fall through to next config file or defaults

    # Override with environment variables
    config = _apply_env_overrides(config)

    return config


def _load_config_file(path: Path) -> L2Config:
    """Load configuration from YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    if not data:
        return L2Config()

    thresholds = L2ThresholdConfig()
    ensemble = L2EnsembleConfig()
    voting = L2VotingConfig()

    # Parse thresholds section
    if "thresholds" in data:
        t = data["thresholds"]
        if "threat" in t:
            thresholds.threat_threshold = float(t["threat"])
        if "family_override" in t:
            thresholds.family_override_threshold = float(t["family_override"])
        if "severity_min" in t:
            thresholds.severity_min_confidence = float(t["severity_min"])
        if "technique_min" in t:
            thresholds.technique_min_confidence = float(t["technique_min"])
        if "harm_type" in t:
            thresholds.harm_type_default_threshold = float(t["harm_type"])

    # Parse per-harm-type thresholds
    if "harm_type_thresholds" in data:
        for harm_type, threshold in data["harm_type_thresholds"].items():
            thresholds.harm_type_thresholds[harm_type] = float(threshold)

    # Parse voting section (NEW)
    if "voting" in data:
        v = data["voting"]
        if "enabled" in v:
            voting.enabled = bool(v["enabled"])
        if "preset" in v:
            preset_val = str(v["preset"]).lower()
            if preset_val in ("balanced", "high_security", "low_fp", "harm_focused"):
                voting.preset = preset_val

    # Parse ensemble section (legacy, still supported if voting disabled)
    if "ensemble" in data:
        e = data["ensemble"]
        if "use_family_override" in e:
            ensemble.use_family_override = bool(e["use_family_override"])
        if "use_severity_boost" in e:
            ensemble.use_severity_boost = bool(e["use_severity_boost"])
        if "severity_boost_amount" in e:
            ensemble.severity_boost_amount = float(e["severity_boost_amount"])
        if "use_technique_boost" in e:
            ensemble.use_technique_boost = bool(e["use_technique_boost"])
        if "technique_boost_threshold" in e:
            ensemble.technique_boost_threshold = float(e["technique_boost_threshold"])
        if "technique_boost_amount" in e:
            ensemble.technique_boost_amount = float(e["technique_boost_amount"])
        if "always_threat_families" in e:
            ensemble.always_threat_families = list(e["always_threat_families"])
        if "high_confidence_techniques" in e:
            ensemble.high_confidence_techniques = list(e["high_confidence_techniques"])

    # Parse classification thresholds
    classification_thresholds = {
        "HIGH_THREAT": 0.90,
        "THREAT": 0.75,
        "LIKELY_THREAT": 0.60,
        "REVIEW": 0.40,
        "FP_LIKELY": 0.0,
    }
    if "classification_thresholds" in data:
        classification_thresholds.update(data["classification_thresholds"])

    return L2Config(
        thresholds=thresholds,
        ensemble=ensemble,
        voting=voting,
        classification_thresholds=classification_thresholds,
    )


def _apply_env_overrides(config: L2Config) -> L2Config:
    """Apply environment variable overrides to config."""
    # Threshold overrides
    if val := os.environ.get("RAXE_L2_THREAT_THRESHOLD"):
        config.thresholds.threat_threshold = float(val)
    if val := os.environ.get("RAXE_L2_FAMILY_OVERRIDE_THRESHOLD"):
        config.thresholds.family_override_threshold = float(val)
    if val := os.environ.get("RAXE_L2_HARM_TYPE_THRESHOLD"):
        config.thresholds.harm_type_default_threshold = float(val)

    # Voting engine overrides (NEW)
    if val := os.environ.get("RAXE_L2_VOTING_ENABLED"):
        config.voting.enabled = val.lower() in ("true", "1", "yes")
    if val := os.environ.get("RAXE_L2_VOTING_PRESET"):
        preset_val = val.lower()
        if preset_val in ("balanced", "high_security", "low_fp", "harm_focused"):
            config.voting.preset = preset_val

    # Legacy ensemble overrides (used when voting is disabled)
    if val := os.environ.get("RAXE_L2_USE_FAMILY_OVERRIDE"):
        config.ensemble.use_family_override = val.lower() in ("true", "1", "yes")
    if val := os.environ.get("RAXE_L2_USE_SEVERITY_BOOST"):
        config.ensemble.use_severity_boost = val.lower() in ("true", "1", "yes")
    if val := os.environ.get("RAXE_L2_SEVERITY_BOOST_AMOUNT"):
        config.ensemble.severity_boost_amount = float(val)

    return config


def create_example_config() -> str:
    """Generate example YAML config content."""
    return """# RAXE L2 Detection Configuration
# Place this file at ./l2_config.yaml or ~/.raxe/l2_config.yaml

# NEW: Voting Engine Configuration
# The voting engine replaces boost-based ensemble logic with weighted voting.
# Presets:
#   - balanced (default): Balances false positives and false negatives
#   - high_security: More aggressive blocking, lower thresholds
#   - low_fp: Fewer false positives, higher thresholds
#   - harm_focused: Sensitive to violence/harm content (higher FP on sensitive topics)
voting:
  enabled: true
  preset: balanced  # balanced | high_security | low_fp | harm_focused

thresholds:
  # Primary threat threshold (is_threat binary classifier)
  # Lower = more sensitive, Higher = fewer false positives
  threat: 0.35

  # Family override: classify as threat if family != benign
  # AND family_confidence >= this threshold
  family_override: 0.25

  # Minimum confidence to report severity/technique
  severity_min: 0.30
  technique_min: 0.20

  # Default threshold for multilabel harm types
  harm_type: 0.50

# Per-harm-type thresholds (lower for safety-critical types)
harm_type_thresholds:
  privacy_or_pii: 0.40
  self_harm_or_suicide: 0.40
  violence_or_physical_harm: 0.40
  cbrn_or_weapons: 0.50
  crime_or_fraud: 0.50
  cybersecurity_or_malware: 0.50
  hate_or_harassment: 0.50
  misinformation_or_disinfo: 0.50
  other_harm: 0.50
  sexual_content: 0.50

# LEGACY: Ensemble configuration (only used if voting.enabled: false)
ensemble:
  # Use family override: threat if family != benign even when is_threat is low
  use_family_override: true

  # Boost threat probability when severity is high/critical
  use_severity_boost: true
  severity_boost_amount: 0.15

  # Boost threat probability when technique is confident
  use_technique_boost: true
  technique_boost_threshold: 0.60
  technique_boost_amount: 0.10

  # Families that ALWAYS trigger threat
  always_threat_families: []
  # Uncomment to always flag these:
  # - jailbreak
  # - data_exfiltration

  # Techniques that indicate high confidence threat
  high_confidence_techniques:
    - instruction_override
    - system_prompt_or_config_extraction
    - tool_or_command_injection
    - data_exfil_system_prompt_or_config
    - data_exfil_user_content

# Classification labels based on final threat probability
classification_thresholds:
  HIGH_THREAT: 0.90
  THREAT: 0.75
  LIKELY_THREAT: 0.60
  REVIEW: 0.40
"""
