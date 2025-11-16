"""Unit tests for domain rule models.

Tests pure domain logic - no I/O operations, no mocks needed.
These tests should be fast and comprehensive.
"""
import re

import pytest

from raxe.domain.rules.models import (
    Pattern,
    Rule,
    RuleExamples,
    RuleFamily,
    RuleMetrics,
    Severity,
)


class TestPattern:
    """Test Pattern value object."""

    def test_create_pattern_with_defaults(self):
        """Pattern can be created with minimal arguments."""
        pattern = Pattern(pattern=r"\btest\b")

        assert pattern.pattern == r"\btest\b"
        assert pattern.flags == []
        assert pattern.timeout == 5.0

    def test_create_pattern_with_flags(self):
        """Pattern can be created with regex flags."""
        pattern = Pattern(
            pattern=r"(?i)test",
            flags=["IGNORECASE", "MULTILINE"],
            timeout=10.0,
        )

        assert pattern.pattern == r"(?i)test"
        assert pattern.flags == ["IGNORECASE", "MULTILINE"]
        assert pattern.timeout == 10.0

    def test_pattern_is_immutable(self):
        """Pattern is frozen and cannot be modified."""
        pattern = Pattern(pattern=r"test")

        with pytest.raises(AttributeError):
            pattern.pattern = "new"  # type: ignore

    def test_pattern_validates_empty_pattern(self):
        """Pattern raises ValueError for empty pattern string."""
        with pytest.raises(ValueError, match="Pattern cannot be empty"):
            Pattern(pattern="")

    def test_pattern_validates_timeout(self):
        """Pattern raises ValueError for non-positive timeout."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            Pattern(pattern=r"test", timeout=0.0)

        with pytest.raises(ValueError, match="Timeout must be positive"):
            Pattern(pattern=r"test", timeout=-1.0)

    def test_compile_pattern_without_flags(self):
        """Pattern compiles to regex without flags."""
        pattern = Pattern(pattern=r"\btest\b")
        compiled = pattern.compile()

        assert isinstance(compiled, re.Pattern)
        assert compiled.search("this is a test")
        assert not compiled.search("testing")

    def test_compile_pattern_with_ignorecase(self):
        """Pattern compiles with IGNORECASE flag."""
        pattern = Pattern(pattern=r"test", flags=["IGNORECASE"])
        compiled = pattern.compile()

        assert compiled.search("TEST")
        assert compiled.search("Test")
        assert compiled.search("test")

    def test_compile_pattern_with_multiple_flags(self):
        """Pattern compiles with multiple flags."""
        pattern = Pattern(
            pattern=r"^test",
            flags=["IGNORECASE", "MULTILINE"],
        )
        compiled = pattern.compile()

        # MULTILINE makes ^ match at start of each line
        text = "line1\nTEST line2"
        assert compiled.search(text)

    def test_compile_invalid_pattern_raises_error(self):
        """Pattern raises ValueError for invalid regex."""
        pattern = Pattern(pattern=r"[invalid")

        with pytest.raises(ValueError, match="Invalid regex pattern"):
            pattern.compile()

    def test_compile_unknown_flag_raises_error(self):
        """Pattern raises ValueError for unknown flag."""
        pattern = Pattern(pattern=r"test", flags=["INVALID_FLAG"])

        with pytest.raises(ValueError, match="Unknown regex flag"):
            pattern.compile()


class TestRuleMetrics:
    """Test RuleMetrics value object."""

    def test_create_metrics_with_defaults(self):
        """Metrics can be created with all None values."""
        metrics = RuleMetrics()

        assert metrics.precision is None
        assert metrics.recall is None
        assert metrics.f1_score is None
        assert metrics.last_evaluated is None
        assert metrics.counts_30d == {}

    def test_create_metrics_with_values(self):
        """Metrics can be created with specific values."""
        metrics = RuleMetrics(
            precision=0.95,
            recall=0.90,
            f1_score=0.92,
            last_evaluated="2025-11-15",
            counts_30d={"true_positive": 10, "false_positive": 1},
        )

        assert metrics.precision == 0.95
        assert metrics.recall == 0.90
        assert metrics.f1_score == 0.92
        assert metrics.last_evaluated == "2025-11-15"
        assert metrics.counts_30d["true_positive"] == 10

    def test_metrics_validates_precision_range(self):
        """Metrics validates precision is between 0 and 1."""
        with pytest.raises(ValueError, match="precision must be between 0 and 1"):
            RuleMetrics(precision=1.5)

        with pytest.raises(ValueError, match="precision must be between 0 and 1"):
            RuleMetrics(precision=-0.1)

    def test_metrics_validates_recall_range(self):
        """Metrics validates recall is between 0 and 1."""
        with pytest.raises(ValueError, match="recall must be between 0 and 1"):
            RuleMetrics(recall=2.0)

    def test_metrics_validates_f1_range(self):
        """Metrics validates f1_score is between 0 and 1."""
        with pytest.raises(ValueError, match="f1_score must be between 0 and 1"):
            RuleMetrics(f1_score=-0.5)


class TestRuleExamples:
    """Test RuleExamples value object."""

    def test_create_examples_empty(self):
        """Examples can be created empty."""
        examples = RuleExamples()

        assert examples.should_match == []
        assert examples.should_not_match == []

    def test_create_examples_with_values(self):
        """Examples can be created with test cases."""
        examples = RuleExamples(
            should_match=["test1", "test2"],
            should_not_match=["nottest1", "nottest2"],
        )

        assert len(examples.should_match) == 2
        assert len(examples.should_not_match) == 2


class TestRule:
    """Test Rule value object."""

    def test_create_minimal_rule(self):
        """Rule can be created with minimal required fields."""
        rule = Rule(
            rule_id="test-001",
            version="1.0.0",
            family=RuleFamily.PI,
            sub_family="test_category",
            name="Test Rule",
            description="A test rule",
            severity=Severity.HIGH,
            confidence=0.9,
            patterns=[Pattern(pattern=r"test")],
            examples=RuleExamples(),
            metrics=RuleMetrics(),
        )

        assert rule.rule_id == "test-001"
        assert rule.version == "1.0.0"
        assert rule.family == RuleFamily.PI
        assert rule.severity == Severity.HIGH

    def test_rule_is_immutable(self):
        """Rule is frozen and cannot be modified."""
        rule = Rule(
            rule_id="test-001",
            version="1.0.0",
            family=RuleFamily.PI,
            sub_family="test",
            name="Test",
            description="Test",
            severity=Severity.HIGH,
            confidence=0.9,
            patterns=[Pattern(pattern=r"test")],
            examples=RuleExamples(),
            metrics=RuleMetrics(),
        )

        with pytest.raises(AttributeError):
            rule.rule_id = "new-id"  # type: ignore

    def test_rule_validates_empty_rule_id(self):
        """Rule raises ValueError for empty rule_id."""
        with pytest.raises(ValueError, match="rule_id cannot be empty"):
            Rule(
                rule_id="",
                version="1.0.0",
                family=RuleFamily.PI,
                sub_family="test",
                name="Test",
                description="Test",
                severity=Severity.HIGH,
                confidence=0.9,
                patterns=[Pattern(pattern=r"test")],
                examples=RuleExamples(),
                metrics=RuleMetrics(),
            )

    def test_rule_validates_semver_version(self):
        """Rule validates version is in semver format."""
        with pytest.raises(ValueError, match="version must be semver format"):
            Rule(
                rule_id="test-001",
                version="invalid",
                family=RuleFamily.PI,
                sub_family="test",
                name="Test",
                description="Test",
                severity=Severity.HIGH,
                confidence=0.9,
                patterns=[Pattern(pattern=r"test")],
                examples=RuleExamples(),
                metrics=RuleMetrics(),
            )

        with pytest.raises(ValueError, match="version must be semver format"):
            Rule(
                rule_id="test-001",
                version="1.0",  # Missing patch
                family=RuleFamily.PI,
                sub_family="test",
                name="Test",
                description="Test",
                severity=Severity.HIGH,
                confidence=0.9,
                patterns=[Pattern(pattern=r"test")],
                examples=RuleExamples(),
                metrics=RuleMetrics(),
            )

    def test_rule_validates_confidence_range(self):
        """Rule validates confidence is between 0 and 1."""
        with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
            Rule(
                rule_id="test-001",
                version="1.0.0",
                family=RuleFamily.PI,
                sub_family="test",
                name="Test",
                description="Test",
                severity=Severity.HIGH,
                confidence=1.5,
                patterns=[Pattern(pattern=r"test")],
                examples=RuleExamples(),
                metrics=RuleMetrics(),
            )

    def test_rule_validates_patterns_not_empty(self):
        """Rule validates patterns list is not empty."""
        with pytest.raises(ValueError, match="must have at least one pattern"):
            Rule(
                rule_id="test-001",
                version="1.0.0",
                family=RuleFamily.PI,
                sub_family="test",
                name="Test",
                description="Test",
                severity=Severity.HIGH,
                confidence=0.9,
                patterns=[],
                examples=RuleExamples(),
                metrics=RuleMetrics(),
            )

    def test_rule_validates_sub_family_not_empty(self):
        """Rule validates sub_family is not empty."""
        with pytest.raises(ValueError, match="sub_family cannot be empty"):
            Rule(
                rule_id="test-001",
                version="1.0.0",
                family=RuleFamily.PI,
                sub_family="",
                name="Test",
                description="Test",
                severity=Severity.HIGH,
                confidence=0.9,
                patterns=[Pattern(pattern=r"test")],
                examples=RuleExamples(),
                metrics=RuleMetrics(),
            )

    def test_rule_validates_mitre_attack_format(self):
        """Rule validates MITRE ATT&CK IDs start with T."""
        with pytest.raises(ValueError, match="Invalid MITRE ATT&CK ID format"):
            Rule(
                rule_id="test-001",
                version="1.0.0",
                family=RuleFamily.PI,
                sub_family="test",
                name="Test",
                description="Test",
                severity=Severity.HIGH,
                confidence=0.9,
                patterns=[Pattern(pattern=r"test")],
                examples=RuleExamples(),
                metrics=RuleMetrics(),
                mitre_attack=["INVALID"],
            )

    def test_versioned_id_property(self):
        """Rule.versioned_id returns rule_id@version format."""
        rule = Rule(
            rule_id="pi-001",
            version="1.2.3",
            family=RuleFamily.PI,
            sub_family="test",
            name="Test",
            description="Test",
            severity=Severity.HIGH,
            confidence=0.9,
            patterns=[Pattern(pattern=r"test")],
            examples=RuleExamples(),
            metrics=RuleMetrics(),
        )

        assert rule.versioned_id == "pi-001@1.2.3"

    def test_compile_patterns(self):
        """Rule can compile all its patterns."""
        rule = Rule(
            rule_id="test-001",
            version="1.0.0",
            family=RuleFamily.PI,
            sub_family="test",
            name="Test",
            description="Test",
            severity=Severity.HIGH,
            confidence=0.9,
            patterns=[
                Pattern(pattern=r"test1"),
                Pattern(pattern=r"test2", flags=["IGNORECASE"]),
            ],
            examples=RuleExamples(),
            metrics=RuleMetrics(),
        )

        compiled = rule.compile_patterns()

        assert len(compiled) == 2
        assert all(isinstance(p, re.Pattern) for p in compiled)

    def test_matches_examples_all_pass(self):
        """Rule.matches_examples returns empty lists when all examples pass."""
        rule = Rule(
            rule_id="test-001",
            version="1.0.0",
            family=RuleFamily.PI,
            sub_family="test",
            name="Test",
            description="Test",
            severity=Severity.HIGH,
            confidence=0.9,
            patterns=[Pattern(pattern=r"\bignore\b", flags=["IGNORECASE"])],
            examples=RuleExamples(
                should_match=["ignore this", "IGNORE that"],
                should_not_match=["do not forget", "acknowledge"],
            ),
            metrics=RuleMetrics(),
        )

        failed_match, failed_not_match = rule.matches_examples()

        assert failed_match == []
        assert failed_not_match == []

    def test_matches_examples_some_fail(self):
        """Rule.matches_examples returns failures."""
        rule = Rule(
            rule_id="test-001",
            version="1.0.0",
            family=RuleFamily.PI,
            sub_family="test",
            name="Test",
            description="Test",
            severity=Severity.HIGH,
            confidence=0.9,
            patterns=[Pattern(pattern=r"\bignore\b", flags=["IGNORECASE"])],
            examples=RuleExamples(
                should_match=["ignore this", "forget this"],  # "forget" will fail
                should_not_match=["safe text", "ignore that"],  # "ignore that" will fail
            ),
            metrics=RuleMetrics(),
        )

        failed_match, failed_not_match = rule.matches_examples()

        assert "forget this" in failed_match
        assert "ignore that" in failed_not_match
