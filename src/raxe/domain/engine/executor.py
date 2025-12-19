"""Rule execution engine.

Pure domain layer - executes rules against text to produce detections.
All functions are stateless and side-effect free.

Performance targets:
- <5ms P95 for 10KB text with 15 L1 rules
- <1ms average for typical prompts
"""
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from raxe.domain.engine.matcher import Match, PatternMatcher
from raxe.domain.rules.models import Rule, Severity


@dataclass(frozen=True)
class Detection:
    """A detected threat from a rule match.

    Immutable value object representing a security threat.

    Attributes:
        rule_id: ID of rule that matched
        rule_version: Version of rule that matched
        severity: Threat severity level
        confidence: Detection confidence (0.0-1.0)
        matches: List of pattern matches that triggered detection
        detected_at: ISO timestamp when detected
        detection_layer: Layer that produced this detection (L1, L2, or PLUGIN)
        layer_latency_ms: Time taken by this layer to produce detection
        category: Category of threat (e.g., prompt_injection, jailbreak)
        message: Human-readable message describing the detection
        explanation: Optional explanation of why this was detected
        risk_explanation: Explanation of why this pattern is dangerous
        remediation_advice: How to fix or mitigate this threat
        docs_url: Link to documentation for learning more
        is_flagged: True if detection was matched by a FLAG suppression
        suppression_reason: Reason for suppression (if flagged or logged)
    """
    rule_id: str
    rule_version: str
    severity: Severity
    confidence: float
    matches: list[Match]
    detected_at: str
    detection_layer: str = "L1"  # Default to L1 for backward compatibility
    layer_latency_ms: float = 0.0
    category: str = "unknown"
    message: str = ""
    explanation: str | None = None
    risk_explanation: str = ""
    remediation_advice: str = ""
    docs_url: str = ""
    is_flagged: bool = False
    suppression_reason: str | None = None

    def __post_init__(self) -> None:
        """Validate detection after construction."""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be 0-1, got {self.confidence}")
        if not self.matches:
            raise ValueError("Detection must have at least one match")
        if self.detection_layer not in ("L1", "L2", "PLUGIN"):
            raise ValueError(f"detection_layer must be L1, L2, or PLUGIN, got {self.detection_layer}")
        if self.layer_latency_ms < 0:
            raise ValueError(f"layer_latency_ms cannot be negative: {self.layer_latency_ms}")

    @property
    def match_count(self) -> int:
        """Number of pattern matches."""
        return len(self.matches)

    @property
    def threat_summary(self) -> str:
        """Human-readable summary of threat.

        Returns:
            Summary string like "CRITICAL: pi-001 (confidence: 0.95, matches: 2)"
        """
        return (
            f"{self.severity.value.upper()}: {self.rule_id} "
            f"(confidence: {self.confidence:.2f}, matches: {self.match_count})"
        )

    @property
    def versioned_rule_id(self) -> str:
        """Full versioned rule identifier.

        Returns:
            String like "pi-001@1.0.0"
        """
        return f"{self.rule_id}@{self.rule_version}"

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of detection
        """
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "match_count": self.match_count,
            "detected_at": self.detected_at,
            "threat_summary": self.threat_summary,
            "detection_layer": self.detection_layer,
            "layer_latency_ms": self.layer_latency_ms,
            "category": self.category,
            "message": self.message,
            "explanation": self.explanation,
            "risk_explanation": self.risk_explanation,
            "remediation_advice": self.remediation_advice,
            "docs_url": self.docs_url,
            "is_flagged": self.is_flagged,
            "suppression_reason": self.suppression_reason,
        }

    def with_flag(self, reason: str) -> "Detection":
        """Create a copy of this detection with is_flagged=True.

        Used by suppression system when FLAG action is matched.

        Args:
            reason: The reason for flagging this detection

        Returns:
            New Detection instance with is_flagged=True
        """
        # Since Detection is frozen, we must create a new instance
        return Detection(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            severity=self.severity,
            confidence=self.confidence,
            matches=self.matches,
            detected_at=self.detected_at,
            detection_layer=self.detection_layer,
            layer_latency_ms=self.layer_latency_ms,
            category=self.category,
            message=self.message,
            explanation=self.explanation,
            risk_explanation=self.risk_explanation,
            remediation_advice=self.remediation_advice,
            docs_url=self.docs_url,
            is_flagged=True,
            suppression_reason=reason,
        )


@dataclass(frozen=True)
class ScanResult:
    """Result of scanning text against rules.

    Aggregates all detections with metadata about the scan.

    Attributes:
        detections: List of detected threats (may be empty)
        scanned_at: ISO timestamp when scan started
        text_length: Length of scanned text in characters
        rules_checked: Number of rules evaluated
        scan_duration_ms: Time taken to scan in milliseconds
    """
    detections: list[Detection]
    scanned_at: str
    text_length: int
    rules_checked: int
    scan_duration_ms: float

    def __post_init__(self) -> None:
        """Validate scan result."""
        if self.text_length < 0:
            raise ValueError(f"text_length cannot be negative: {self.text_length}")
        if self.rules_checked < 0:
            raise ValueError(f"rules_checked cannot be negative: {self.rules_checked}")
        if self.scan_duration_ms < 0:
            raise ValueError(f"scan_duration_ms cannot be negative: {self.scan_duration_ms}")

    @property
    def has_detections(self) -> bool:
        """True if any threats detected."""
        return len(self.detections) > 0

    @property
    def highest_severity(self) -> Severity | None:
        """Highest severity across all detections.

        Returns:
            Highest severity or None if no detections
        """
        if not self.detections:
            return None

        # Severity order (lower number = more severe)
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }

        return min(
            (d.severity for d in self.detections),
            key=lambda s: severity_order[s],
        )

    @property
    def total_matches(self) -> int:
        """Total pattern matches across all detections."""
        return sum(d.match_count for d in self.detections)

    @property
    def detection_count(self) -> int:
        """Number of detections (rules that matched)."""
        return len(self.detections)

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of scan result
        """
        return {
            "has_detections": self.has_detections,
            "detection_count": self.detection_count,
            "highest_severity": self.highest_severity.value if self.highest_severity else None,
            "total_matches": self.total_matches,
            "text_length": self.text_length,
            "rules_checked": self.rules_checked,
            "scan_duration_ms": self.scan_duration_ms,
            "scanned_at": self.scanned_at,
            "detections": [d.to_dict() for d in self.detections],
        }


class RuleExecutor:
    """Execute rules against text to detect threats.

    Pure domain logic - stateless and side-effect free.
    Uses PatternMatcher for actual pattern matching.

    Thread-safe for concurrent scans.
    """

    def __init__(self) -> None:
        """Initialize with pattern matcher."""
        self.matcher = PatternMatcher()

    def execute_rule(self, text: str, rule: Rule) -> Detection | None:
        """Execute a single rule against text.

        Args:
            text: Text to scan
            rule: Rule to apply

        Returns:
            Detection if rule matched, None otherwise

        Note:
            Implements OR logic: if any pattern matches, rule matches.
        """
        # Match all patterns in rule (OR logic)
        matches = self.matcher.match_all_patterns(text, rule.patterns)

        if not matches:
            return None

        # Calculate confidence based on match quality
        confidence = self._calculate_confidence(rule, matches)

        # Derive category from rule family
        category = rule.family.value.lower() if hasattr(rule.family, 'value') else str(rule.family).lower()

        # Create message from rule
        message = f"{rule.name}: {rule.description[:100]}"  # Truncate long descriptions

        # Create detection with explainability fields from rule
        return Detection(
            rule_id=rule.rule_id,
            rule_version=rule.version,
            severity=rule.severity,
            confidence=confidence,
            matches=matches,
            detected_at=datetime.now(timezone.utc).isoformat(),
            detection_layer="L1",  # Executor always produces L1 detections
            layer_latency_ms=0.0,  # Will be set by caller if needed
            category=category,
            message=message,
            explanation=None,
            risk_explanation=rule.risk_explanation,
            remediation_advice=rule.remediation_advice,
            docs_url=rule.docs_url,
        )

    def execute_rules(
        self,
        text: str,
        rules: list[Rule],
    ) -> ScanResult:
        """Execute all rules against text.

        Args:
            text: Text to scan
            rules: Rules to apply

        Returns:
            ScanResult with all detections and metadata

        Note:
            Continues scanning even if individual rules fail.
            Failed rules are skipped (caller should log).
        """
        start_time = time.perf_counter()
        scan_started_at = datetime.now(timezone.utc).isoformat()

        detections: list[Detection] = []

        for rule in rules:
            try:
                detection = self.execute_rule(text, rule)
                if detection:
                    detections.append(detection)
            except Exception:  # noqa: S112
                # Rule failed - skip it and continue
                # Note: Broad except is intentional - domain layer can't log
                # Caller in application layer should log failures
                continue

        duration_ms = (time.perf_counter() - start_time) * 1000

        return ScanResult(
            detections=detections,
            scanned_at=scan_started_at,
            text_length=len(text),
            rules_checked=len(rules),
            scan_duration_ms=duration_ms,
        )

    def _calculate_confidence(
        self,
        rule: Rule,
        matches: list[Match],
    ) -> float:
        """Calculate detection confidence.

        Combines rule's base confidence with match quality factors:
        - Number of matches (more = higher confidence)
        - Match length (longer = higher confidence)
        - Pattern diversity (multiple patterns = higher confidence)

        Args:
            rule: The rule that matched
            matches: Pattern matches

        Returns:
            Confidence score 0.0-1.0 (capped at rule's base confidence)
        """
        base_confidence = rule.confidence

        # Quality factors
        # More matches increases confidence (up to 3 matches = 100% of factor)
        match_count_factor = min(len(matches) / 3.0, 1.0)

        # Multiple different patterns matching is stronger signal
        unique_patterns = len({m.pattern_index for m in matches})
        pattern_diversity_factor = min(unique_patterns / len(rule.patterns), 1.0)

        # Average match length (longer matches = higher confidence)
        avg_match_length = sum(m.match_length for m in matches) / len(matches)
        length_factor = min(avg_match_length / 20.0, 1.0)  # 20+ chars = 100%

        # Combined quality (weighted average)
        quality = (
            0.4 * match_count_factor +
            0.4 * pattern_diversity_factor +
            0.2 * length_factor
        )

        # Final confidence: base * (0.7 + 0.3 * quality)
        # This means:
        # - Minimum 70% of base confidence (at least one match)
        # - Maximum 100% of base confidence (perfect quality)
        combined = base_confidence * (0.7 + 0.3 * quality)

        return min(combined, 1.0)

    def clear_cache(self) -> None:
        """Clear pattern matcher cache.

        Useful for testing or when rules change.
        """
        self.matcher.clear_cache()
