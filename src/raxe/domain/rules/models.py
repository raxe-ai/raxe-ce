"""Domain models for rules and detections.

Pure domain layer - NO I/O operations allowed.
This module defines immutable value objects that represent threat detection rules
matching the YAML v1.1 specification.
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from re import Pattern as RePattern
from typing import Any


class Severity(Enum):
    """Threat severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RuleFamily(Enum):
    """Rule family categories."""
    PI = "PI"           # Prompt Injection
    JB = "JB"           # Jailbreak
    PII = "PII"         # PII/Data Leak
    CMD = "CMD"         # Command Injection
    ENC = "ENC"         # Encoding/Obfuscation Attacks
    RAG = "RAG"         # RAG-specific Attacks
    HC = "HC"           # Harmful Content
    SEC = "SEC"         # Security
    QUAL = "QUAL"       # Quality
    CUSTOM = "CUSTOM"   # User-defined


@dataclass(frozen=True)
class Pattern:
    """A single regex pattern within a rule.

    Attributes:
        pattern: The regex pattern string
        flags: List of regex flag names (e.g., ['IGNORECASE'])
        timeout: Maximum time in seconds for pattern matching
    """
    pattern: str
    flags: list[str] = field(default_factory=list)
    timeout: float = 5.0

    def __post_init__(self) -> None:
        """Validate pattern after construction."""
        if not self.pattern:
            raise ValueError("Pattern cannot be empty")
        if self.timeout <= 0:
            raise ValueError(f"Timeout must be positive, got {self.timeout}")

    def compile(self) -> RePattern[str]:
        """Compile regex pattern with flags.

        Returns:
            Compiled regex pattern

        Raises:
            ValueError: If pattern is invalid or flags are unknown

        Note:
            This is OK in domain - compiling regex is a pure operation
        """
        # Convert string flags to re module flags
        flag_value = 0
        for flag_name in self.flags:
            flag_upper = flag_name.upper()
            if not hasattr(re, flag_upper):
                raise ValueError(f"Unknown regex flag: {flag_name}")
            flag_value |= getattr(re, flag_upper)

        try:
            return re.compile(self.pattern, flag_value)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{self.pattern}': {e}") from e


@dataclass(frozen=True)
class RuleMetrics:
    """Performance metrics for a rule.

    Attributes:
        precision: Precision score (0-1) or None if not evaluated
        recall: Recall score (0-1) or None if not evaluated
        f1_score: F1 score (0-1) or None if not evaluated
        last_evaluated: ISO timestamp of last evaluation or None
        counts_30d: Dict of detection counts over 30 days
    """
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    last_evaluated: str | None = None
    counts_30d: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate metrics after construction."""
        for metric_name, value in [
            ("precision", self.precision),
            ("recall", self.recall),
            ("f1_score", self.f1_score),
        ]:
            if value is not None and not (0.0 <= value <= 1.0):
                raise ValueError(f"{metric_name} must be between 0 and 1, got {value}")


@dataclass(frozen=True)
class RuleExamples:
    """Test examples for a rule.

    Attributes:
        should_match: List of strings that should trigger the rule
        should_not_match: List of strings that should not trigger the rule
    """
    should_match: list[str] = field(default_factory=list)
    should_not_match: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Rule:
    """A threat detection rule.

    Immutable value object matching YAML v1.1 specification.
    Pure domain model - no I/O operations.

    Attributes:
        rule_id: Unique identifier (e.g., 'pi-001')
        version: Semantic version (e.g., '0.0.1')
        family: Rule family category (PI, JB, PII, etc.)
        sub_family: Subcategory within family
        name: Human-readable rule name
        description: Detailed description of what the rule detects
        severity: Threat severity level
        confidence: Confidence score (0-1) in detection accuracy
        patterns: List of regex patterns to match
        examples: Test examples for validation
        metrics: Performance metrics
        mitre_attack: List of MITRE ATT&CK technique IDs
        metadata: Additional metadata (author, dates, custom fields)
        rule_hash: SHA256 hash of rule content for versioning
        risk_explanation: Explanation of why this pattern is dangerous
        remediation_advice: How to fix or mitigate this threat
        docs_url: Link to documentation for learning more
    """
    # Core identity
    rule_id: str
    version: str
    family: RuleFamily
    sub_family: str

    # Detection
    name: str
    description: str
    severity: Severity
    confidence: float
    patterns: list[Pattern]

    # Testing & validation
    examples: RuleExamples

    # Performance tracking
    metrics: RuleMetrics

    # Metadata
    mitre_attack: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    rule_hash: str | None = None

    # Explainability fields
    risk_explanation: str = ""
    remediation_advice: str = ""
    docs_url: str = ""

    def __post_init__(self) -> None:
        """Validate rule after construction.

        Raises:
            ValueError: If any field fails validation
        """
        # Validate rule_id format
        if not self.rule_id:
            raise ValueError("rule_id cannot be empty")

        # Validate version is semver format
        if not self._is_valid_semver(self.version):
            raise ValueError(f"version must be semver format (e.g., '0.0.1'), got '{self.version}'")

        # Validate confidence is 0-1
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be between 0 and 1, got {self.confidence}")

        # Validate patterns not empty
        if not self.patterns:
            raise ValueError("Rule must have at least one pattern")

        # Validate sub_family not empty
        if not self.sub_family:
            raise ValueError("sub_family cannot be empty")

        # Validate MITRE ATT&CK IDs format (basic check)
        for technique_id in self.mitre_attack:
            if not technique_id.startswith("T"):
                raise ValueError(f"Invalid MITRE ATT&CK ID format: {technique_id}")

    @staticmethod
    def _is_valid_semver(version: str) -> bool:
        """Check if version string is valid semantic version.

        Args:
            version: Version string to validate

        Returns:
            True if valid semver, False otherwise
        """
        parts = version.split(".")
        if len(parts) != 3:
            return False

        try:
            major, minor, patch = parts
            # Check each part is a non-negative integer
            int(major), int(minor), int(patch)
            return True
        except ValueError:
            return False

    def compile_patterns(self) -> list[RePattern[str]]:
        """Compile all patterns for this rule.

        Returns:
            List of compiled regex patterns

        Raises:
            ValueError: If any pattern fails to compile
        """
        return [p.compile() for p in self.patterns]

    @property
    def versioned_id(self) -> str:
        """Return rule_id@version format.

        Returns:
            String in format 'rule_id@version' (e.g., 'pi-001@1.0.0')
        """
        return f"{self.rule_id}@{self.version}"

    def matches_examples(self) -> tuple[list[str], list[str]]:
        """Test rule against its own examples.

        Returns:
            Tuple of (failed_should_match, failed_should_not_match) lists

        Note:
            This is a pure function for validation, not for actual detection.
            Returns failures, empty lists mean all examples passed.
        """
        compiled_patterns = self.compile_patterns()

        failed_should_match = []
        for example in self.examples.should_match:
            if not any(pattern.search(example) for pattern in compiled_patterns):
                failed_should_match.append(example)

        failed_should_not_match = []
        for example in self.examples.should_not_match:
            if any(pattern.search(example) for pattern in compiled_patterns):
                failed_should_not_match.append(example)

        return failed_should_match, failed_should_not_match
