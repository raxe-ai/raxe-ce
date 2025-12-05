"""Custom Rule Framework.

Allows users to define custom detection rules in YAML format.
Rules are loaded from ~/.raxe/rules/ and executed alongside
core detection rules.

Example rule file (~/.raxe/rules/my_rule.yaml):
    ```yaml
    id: "CUSTOM_001"
    name: "API Key Detection"
    description: "Detects hardcoded API keys"
    version: "0.0.1"
    author: "security-team"

    pattern:
      type: "regex"
      value: "(api[_-]?key)\\s*[:=]\\s*['\"][a-zA-Z0-9]{32,}['\"]"
      flags: ["IGNORECASE"]

    severity: "HIGH"
    confidence: 0.9
    category: "SECURITY"

    tags:
      - "api-key"
      - "credentials"

    metadata:
      cwe_id: "CWE-798"

    conditions:
      min_length: 20
      max_length: 100000

    actions:
      block: true
      alert: true
      log: true
    ```
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from raxe.domain.engine.executor import Detection
from raxe.domain.engine.matcher import Match
from raxe.domain.rules.models import Severity

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CustomRule:
    """User-defined custom detection rule.

    Represents a custom rule loaded from YAML configuration.
    Rules can use regex patterns and include metadata for
    categorization and policy enforcement.

    Attributes:
        id: Unique rule identifier (e.g., "CUSTOM_001")
        name: Human-readable rule name
        description: What the rule detects
        pattern: Compiled regex pattern
        severity: Threat severity level
        confidence: Detection confidence (0.0-1.0)
        category: Rule category (SECURITY, PII, etc.)
        tags: List of tags for categorization
        metadata: Additional metadata (CWE ID, etc.)
        conditions: Conditions for rule application
        actions: Actions to take when rule matches
    """

    id: str
    name: str
    description: str
    pattern: re.Pattern[str]
    severity: Severity
    confidence: float
    category: str
    tags: tuple[str, ...]
    metadata: dict[str, Any]
    conditions: dict[str, Any]
    actions: dict[str, bool]

    def __post_init__(self) -> None:
        """Validate rule after construction."""
        if not self.id:
            raise ValueError("Rule ID cannot be empty")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Confidence must be 0.0-1.0, got {self.confidence}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CustomRule":
        """Create custom rule from dictionary.

        Args:
            data: Rule data from YAML

        Returns:
            CustomRule instance

        Raises:
            ValueError: If data is invalid
        """
        # Compile pattern
        pattern_config = data.get("pattern", {})
        if not pattern_config:
            raise ValueError("Rule must have 'pattern' field")

        pattern_type = pattern_config.get("type", "regex")
        if pattern_type != "regex":
            raise ValueError(f"Unsupported pattern type: {pattern_type}")

        pattern_value = pattern_config.get("value")
        if not pattern_value:
            raise ValueError("Pattern must have 'value' field")

        # Compile regex with flags
        flags = 0
        for flag_name in pattern_config.get("flags", []):
            if hasattr(re, flag_name):
                flags |= getattr(re, flag_name)
            else:
                logger.warning(f"Unknown regex flag: {flag_name}")

        try:
            pattern = re.compile(pattern_value, flags)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}") from e

        # Parse severity
        severity_str = data.get("severity", "MEDIUM")
        try:
            severity = Severity[severity_str.upper()]
        except KeyError:
            raise ValueError(
                f"Invalid severity: {severity_str}. "
                f"Must be one of: {[s.name for s in Severity]}"
            ) from None

        # Create rule
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            pattern=pattern,
            severity=severity,
            confidence=data.get("confidence", 0.8),
            category=data.get("category", "CUSTOM"),
            tags=tuple(data.get("tags", [])),
            metadata=data.get("metadata", {}),
            conditions=data.get("conditions", {}),
            actions=data.get("actions", {}),
        )

    def should_apply(self, text: str) -> bool:
        """Check if rule should be applied to text.

        Evaluates conditions like min/max length.

        Args:
            text: Text to check

        Returns:
            True if rule should be applied
        """
        text_len = len(text)

        # Check minimum length
        min_len = self.conditions.get("min_length", 0)
        if text_len < min_len:
            return False

        # Check maximum length
        max_len = self.conditions.get("max_length", float("inf"))
        if text_len > max_len:
            return False

        return True

    def match(self, text: str) -> bool:
        """Check if pattern matches text.

        Args:
            text: Text to match against

        Returns:
            True if pattern matches
        """
        return self.pattern.search(text) is not None


class CustomRuleLoader:
    """Loads and manages custom user-defined rules.

    Scans ~/.raxe/rules/ for YAML rule definitions and loads them
    for use in detection. Rules are compiled once and cached for
    performance.

    Example:
        ```python
        loader = CustomRuleLoader()
        loader.load_rules()

        # Use in detection
        detections = loader.detect("api_key=secret123...")
        ```

    Attributes:
        rules_dir: Directory containing rule YAML files
        rules: List of loaded custom rules
    """

    def __init__(self, rules_dir: Path | None = None):
        """Initialize custom rule loader.

        Args:
            rules_dir: Directory containing rule files
                      (default: ~/.raxe/rules/)
        """
        self.rules_dir = rules_dir or (Path.home() / ".raxe" / "rules")
        self.rules: list[CustomRule] = []
        logger.debug(f"CustomRuleLoader initialized (dir={self.rules_dir})")

    def load_rules(self) -> None:
        """Load all custom rules from directory.

        Scans for *.yaml files in rules_dir and loads them.
        Invalid rules are logged but don't prevent loading others.
        """
        if not self.rules_dir.exists():
            logger.info(
                f"Custom rules directory does not exist: {self.rules_dir}. "
                f"Create it to add custom rules."
            )
            return

        logger.info(f"Loading custom rules from {self.rules_dir}")
        loaded_count = 0
        error_count = 0

        for rule_file in self.rules_dir.glob("*.yaml"):
            try:
                rule = self._load_rule_file(rule_file)
                self.rules.append(rule)
                loaded_count += 1
                logger.debug(f"Loaded custom rule: {rule.id} ({rule.name})")
            except Exception as e:
                error_count += 1
                logger.warning(f"Failed to load rule {rule_file}: {e}")

        logger.info(
            f"Loaded {loaded_count} custom rules "
            f"({error_count} failed)"
        )

    def _load_rule_file(self, path: Path) -> CustomRule:
        """Load a single rule file.

        Args:
            path: Path to YAML rule file

        Returns:
            Loaded CustomRule

        Raises:
            ValueError: If rule file is invalid
        """
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "PyYAML is required for custom rules. "
                "Install with: pip install pyyaml"
            ) from None

        # Load YAML
        with open(path) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError("Empty rule file")

        # Create rule from data
        return CustomRule.from_dict(data)

    def detect(self, text: str) -> list[Detection]:
        """Apply custom rules to text.

        Runs all loaded rules against the text and returns
        detections for any matches.

        Args:
            text: Text to scan

        Returns:
            List of detections

        Note:
            Rules are only applied if their conditions are met
            (e.g., min/max length).
        """
        detections: list[Detection] = []

        for rule in self.rules:
            # Check if rule should apply
            if not rule.should_apply(text):
                continue

            # Check if pattern matches
            if rule.match(text):
                # Create a simple Match object for the detection
                match = Match(
                    pattern="custom_rule",
                    text=text[:100],  # Include first 100 chars as context
                    start=0,
                    end=min(100, len(text))
                )

                detection = Detection(
                    rule_id=rule.id,
                    rule_version="0.0.1",  # Default version for custom rules
                    severity=rule.severity,
                    confidence=rule.confidence,
                    matches=[match],
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    detection_layer="PLUGIN",
                    category=rule.category,
                    message=f"{rule.name}: {rule.description}",
                )
                detections.append(detection)

                logger.debug(
                    f"Custom rule matched: {rule.id} "
                    f"(severity={rule.severity.name})"
                )

        return detections

    def get_rule(self, rule_id: str) -> CustomRule | None:
        """Get a rule by ID.

        Args:
            rule_id: Rule identifier

        Returns:
            CustomRule or None if not found
        """
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def list_rules(self) -> list[CustomRule]:
        """Get all loaded rules.

        Returns:
            List of custom rules
        """
        return self.rules.copy()

    def reload(self) -> None:
        """Reload all rules from disk.

        Clears existing rules and loads fresh from directory.
        Useful for hot-reloading configuration changes.
        """
        self.rules = []
        self.load_rules()
        logger.info(f"Reloaded {len(self.rules)} custom rules")


__all__ = ["CustomRule", "CustomRuleLoader"]
