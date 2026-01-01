"""Tests for pack domain models.

Pure domain layer tests - fast, no I/O, no mocks needed.
"""
import pytest

from raxe.domain.packs.models import (
    PackManifest,
    PackRule,
    PackType,
    RulePack,
)
from raxe.domain.rules.models import (
    Pattern,
    Rule,
    RuleExamples,
    RuleFamily,
    RuleMetrics,
    Severity,
)


@pytest.fixture
def sample_rule():
    """Create a sample rule for testing."""
    return Rule(
        rule_id="pi-001",
        version="0.0.1",
        family=RuleFamily.PI,
        sub_family="instruction_override",
        name="Test Rule",
        description="Test rule description",
        severity=Severity.CRITICAL,
        confidence=0.95,
        patterns=[Pattern(pattern=r"test", flags=[], timeout=5.0)],
        examples=RuleExamples(should_match=[], should_not_match=[]),
        metrics=RuleMetrics(),
        mitre_attack=[],
        metadata={},
        rule_hash=None,
    )


class TestPackType:
    """Tests for PackType enum."""

    def test_pack_type_values(self):
        """Test pack type enum values."""
        assert PackType.OFFICIAL.value == "OFFICIAL"
        assert PackType.COMMUNITY.value == "COMMUNITY"
        assert PackType.CUSTOM.value == "CUSTOM"

    def test_pack_type_from_string(self):
        """Test creating pack type from string."""
        assert PackType("OFFICIAL") == PackType.OFFICIAL
        assert PackType("COMMUNITY") == PackType.COMMUNITY
        assert PackType("CUSTOM") == PackType.CUSTOM


class TestPackRule:
    """Tests for PackRule domain model."""

    def test_pack_rule_creation(self):
        """Test creating a pack rule."""
        pack_rule = PackRule(
            id="pi-001",
            version="1.0.0",
            path="rules/PI/pi-001@1.0.0.yaml"
        )

        assert pack_rule.id == "pi-001"
        assert pack_rule.version == "1.0.0"
        assert pack_rule.path == "rules/PI/pi-001@1.0.0.yaml"

    def test_pack_rule_versioned_id(self):
        """Test versioned_id property."""
        pack_rule = PackRule(
            id="pi-001",
            version="1.0.0",
            path="rules/PI/pi-001@1.0.0.yaml"
        )

        assert pack_rule.versioned_id == "pi-001@1.0.0"

    def test_pack_rule_validation_empty_id(self):
        """Test validation fails with empty ID."""
        with pytest.raises(ValueError, match="Rule id cannot be empty"):
            PackRule(id="", version="0.0.1", path="rules/pi-001.yaml")

    def test_pack_rule_validation_empty_version(self):
        """Test validation fails with empty version."""
        with pytest.raises(ValueError, match="Rule version cannot be empty"):
            PackRule(id="pi-001", version="", path="rules/pi-001.yaml")

    def test_pack_rule_validation_empty_path(self):
        """Test validation fails with empty path."""
        with pytest.raises(ValueError, match="Rule path cannot be empty"):
            PackRule(id="pi-001", version="0.0.1", path="")

    def test_pack_rule_immutable(self):
        """Test pack rule is immutable."""
        pack_rule = PackRule(
            id="pi-001",
            version="0.0.1",
            path="rules/pi-001.yaml"
        )

        with pytest.raises(AttributeError):
            pack_rule.id = "pi-002"


class TestPackManifest:
    """Tests for PackManifest domain model."""

    def test_pack_manifest_creation(self):
        """Test creating a pack manifest."""
        pack_rules = [
            PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml")
        ]

        manifest = PackManifest(
            id="core",
            version="0.0.1",
            name="Core Rules",
            pack_type=PackType.OFFICIAL,
            schema_version="0.0.1",
            rules=pack_rules,
            metadata={"maintainer": "raxe-ai"},
        )

        assert manifest.id == "core"
        assert manifest.version == "0.0.1"
        assert manifest.name == "Core Rules"
        assert manifest.pack_type == PackType.OFFICIAL
        assert manifest.schema_version == "0.0.1"
        assert len(manifest.rules) == 1
        assert manifest.metadata["maintainer"] == "raxe-ai"

    def test_pack_manifest_versioned_id(self):
        """Test versioned_id property."""
        manifest = PackManifest(
            id="core",
            version="0.0.1",
            name="Core",
            pack_type=PackType.OFFICIAL,
            schema_version="0.0.1",
            rules=[PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml")],
        )

        assert manifest.versioned_id == "core@0.0.1"

    def test_pack_manifest_rule_count(self):
        """Test rule_count property."""
        pack_rules = [
            PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml"),
            PackRule(id="pi-002", version="0.0.1", path="rules/pi-002.yaml"),
        ]

        manifest = PackManifest(
            id="core",
            version="0.0.1",
            name="Core",
            pack_type=PackType.OFFICIAL,
            schema_version="0.0.1",
            rules=pack_rules,
        )

        assert manifest.rule_count == 2

    def test_pack_manifest_validation_empty_id(self):
        """Test validation fails with empty ID."""
        with pytest.raises(ValueError, match="Pack id cannot be empty"):
            PackManifest(
                id="",
                version="0.0.1",
                name="Test",
                pack_type=PackType.CUSTOM,
                schema_version="0.0.1",
                rules=[PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml")],
            )

    def test_pack_manifest_validation_empty_version(self):
        """Test validation fails with empty version."""
        with pytest.raises(ValueError, match="Pack version cannot be empty"):
            PackManifest(
                id="core",
                version="",
                name="Test",
                pack_type=PackType.CUSTOM,
                schema_version="0.0.1",
                rules=[PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml")],
            )

    def test_pack_manifest_validation_invalid_semver(self):
        """Test validation fails with invalid semver."""
        with pytest.raises(ValueError, match="must be semver format"):
            PackManifest(
                id="core",
                version="1.0",  # Invalid - needs major.minor.patch
                name="Test",
                pack_type=PackType.CUSTOM,
                schema_version="0.0.1",
                rules=[PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml")],
            )

    def test_pack_manifest_validation_no_rules(self):
        """Test validation fails with no rules."""
        with pytest.raises(ValueError, match="must contain at least one rule"):
            PackManifest(
                id="core",
                version="0.0.1",
                name="Test",
                pack_type=PackType.CUSTOM,
                schema_version="0.0.1",
                rules=[],  # Empty rules list
            )

    def test_pack_manifest_with_signature(self):
        """Test manifest with signature fields."""
        manifest = PackManifest(
            id="community",
            version="0.0.1",
            name="Community",
            pack_type=PackType.COMMUNITY,
            schema_version="0.0.1",
            rules=[PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml")],
            signature="abc123signature",
            signature_algorithm="ed25519",
        )

        assert manifest.signature == "abc123signature"
        assert manifest.signature_algorithm == "ed25519"

    def test_pack_manifest_immutable(self):
        """Test manifest is immutable."""
        manifest = PackManifest(
            id="core",
            version="0.0.1",
            name="Core",
            pack_type=PackType.OFFICIAL,
            schema_version="0.0.1",
            rules=[PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml")],
        )

        with pytest.raises(AttributeError):
            manifest.id = "custom"


class TestRulePack:
    """Tests for RulePack domain model."""

    def test_rule_pack_creation(self, sample_rule):
        """Test creating a rule pack."""
        manifest = PackManifest(
            id="core",
            version="0.0.1",
            name="Core",
            pack_type=PackType.OFFICIAL,
            schema_version="0.0.1",
            rules=[PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml")],
        )

        pack = RulePack(manifest=manifest, rules=[sample_rule])

        assert pack.manifest == manifest
        assert len(pack.rules) == 1
        assert pack.rules[0].rule_id == "pi-001"

    def test_rule_pack_validation_count_mismatch(self, sample_rule):
        """Test validation fails when rule count doesn't match manifest."""
        manifest = PackManifest(
            id="core",
            version="0.0.1",
            name="Core",
            pack_type=PackType.OFFICIAL,
            schema_version="0.0.1",
            rules=[
                PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml"),
                PackRule(id="pi-002", version="0.0.1", path="rules/pi-002.yaml"),
            ],
        )

        # Only provide 1 rule when manifest declares 2
        with pytest.raises(ValueError, match="has 1 loaded rules but manifest declares 2"):
            RulePack(manifest=manifest, rules=[sample_rule])

    def test_rule_pack_validation_missing_rule(self, sample_rule):
        """Test validation fails when rule in manifest is not loaded."""
        manifest = PackManifest(
            id="core",
            version="0.0.1",
            name="Core",
            pack_type=PackType.OFFICIAL,
            schema_version="0.0.1",
            rules=[PackRule(id="pi-999", version="0.0.1", path="rules/pi-999.yaml")],
        )

        # Rule pi-001 provided but manifest expects pi-999
        with pytest.raises(ValueError, match="missing rules declared in manifest"):
            RulePack(manifest=manifest, rules=[sample_rule])

    def test_rule_pack_get_rule(self, sample_rule):
        """Test getting rule by ID."""
        manifest = PackManifest(
            id="core",
            version="0.0.1",
            name="Core",
            pack_type=PackType.OFFICIAL,
            schema_version="0.0.1",
            rules=[PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml")],
        )

        pack = RulePack(manifest=manifest, rules=[sample_rule])

        rule = pack.get_rule("pi-001")
        assert rule is not None
        assert rule.rule_id == "pi-001"

        rule = pack.get_rule("pi-999")
        assert rule is None

    def test_rule_pack_get_rule_versioned(self, sample_rule):
        """Test getting rule by ID and version."""
        manifest = PackManifest(
            id="core",
            version="0.0.1",
            name="Core",
            pack_type=PackType.OFFICIAL,
            schema_version="0.0.1",
            rules=[PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml")],
        )

        pack = RulePack(manifest=manifest, rules=[sample_rule])

        rule = pack.get_rule_versioned("pi-001", "0.0.1")
        assert rule is not None
        assert rule.rule_id == "pi-001"
        assert rule.version == "0.0.1"

        rule = pack.get_rule_versioned("pi-001", "2.0.0")
        assert rule is None

    def test_rule_pack_get_rules_by_family(self, sample_rule):
        """Test getting rules by family."""
        manifest = PackManifest(
            id="core",
            version="0.0.1",
            name="Core",
            pack_type=PackType.OFFICIAL,
            schema_version="0.0.1",
            rules=[PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml")],
        )

        pack = RulePack(manifest=manifest, rules=[sample_rule])

        pi_rules = pack.get_rules_by_family("PI")
        assert len(pi_rules) == 1
        assert pi_rules[0].family == RuleFamily.PI

        jb_rules = pack.get_rules_by_family("JB")
        assert len(jb_rules) == 0

    def test_rule_pack_get_rules_by_severity(self, sample_rule):
        """Test getting rules by severity."""
        manifest = PackManifest(
            id="core",
            version="0.0.1",
            name="Core",
            pack_type=PackType.OFFICIAL,
            schema_version="0.0.1",
            rules=[PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml")],
        )

        pack = RulePack(manifest=manifest, rules=[sample_rule])

        critical_rules = pack.get_rules_by_severity("critical")
        assert len(critical_rules) == 1
        assert critical_rules[0].severity == Severity.CRITICAL

        low_rules = pack.get_rules_by_severity("low")
        assert len(low_rules) == 0

    def test_rule_pack_properties(self, sample_rule):
        """Test pack convenience properties."""
        manifest = PackManifest(
            id="core",
            version="0.0.1",
            name="Core",
            pack_type=PackType.OFFICIAL,
            schema_version="0.0.1",
            rules=[PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml")],
        )

        pack = RulePack(manifest=manifest, rules=[sample_rule])

        assert pack.pack_id == "core"
        assert pack.version == "0.0.1"
        assert pack.pack_type == PackType.OFFICIAL

    def test_rule_pack_immutable(self, sample_rule):
        """Test pack is immutable."""
        manifest = PackManifest(
            id="core",
            version="0.0.1",
            name="Core",
            pack_type=PackType.OFFICIAL,
            schema_version="0.0.1",
            rules=[PackRule(id="pi-001", version="0.0.1", path="rules/pi-001.yaml")],
        )

        pack = RulePack(manifest=manifest, rules=[sample_rule])

        with pytest.raises(AttributeError):
            pack.manifest = None
