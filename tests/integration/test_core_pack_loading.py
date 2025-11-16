"""Integration test for loading the real core pack.

This test validates the actual pack distribution system works with the
real core pack from src/raxe/packs/core/v1.0.0/.
"""
from pathlib import Path

import pytest

from raxe.domain.packs.models import PackType
from raxe.infrastructure.packs.loader import PackLoader
from raxe.infrastructure.packs.registry import PackRegistry, RegistryConfig


@pytest.fixture
def registry_root():
    """Path to the bundled packs directory."""
    return Path(__file__).parent.parent.parent / "src" / "raxe" / "packs"


class TestCorePackLoading:
    """Integration tests for core pack loading."""

    def test_load_core_pack_directly(self, registry_root):
        """Test loading core pack v1.0.0 directly."""
        core_pack_dir = registry_root / "core" / "v1.0.0"

        # Verify pack structure exists
        assert core_pack_dir.exists(), f"Core pack not found at {core_pack_dir}"
        assert (core_pack_dir / "pack.yaml").exists(), "pack.yaml not found"
        assert (core_pack_dir / "rules" / "PI").exists(), "rules/PI directory not found"

        # Load pack
        loader = PackLoader(strict=True)
        pack = loader.load_pack(core_pack_dir)

        # Validate pack metadata
        assert pack.manifest.id == "core"
        assert pack.manifest.version == "1.0.0"
        assert pack.manifest.name == "RAXE Core LLM Safety Rules"
        assert pack.manifest.pack_type == PackType.OFFICIAL
        assert pack.manifest.schema_version == "1.1.0"

        # Validate rules loaded
        assert len(pack.rules) >= 1, "Core pack should have at least one rule"

        # Verify pi-001 is present
        pi_001 = pack.get_rule("pi-001")
        assert pi_001 is not None, "pi-001 rule should be in core pack"
        assert pi_001.rule_id == "pi-001"
        assert pi_001.version == "1.0.0"
        assert pi_001.family.value == "PI"

    def test_load_core_pack_via_registry(self, registry_root):
        """Test loading core pack through PackRegistry."""
        # Simulate ~/.raxe/packs structure by using registry directly
        config = RegistryConfig(
            packs_root=registry_root,
            precedence=["core"]
        )

        registry = PackRegistry(config)
        registry.load_all_packs()

        # Verify core pack loaded
        assert "core" in registry.packs
        core_pack = registry.packs["core"]

        assert core_pack.manifest.id == "core"
        assert core_pack.manifest.version == "1.0.0"
        assert len(core_pack.rules) >= 1

    def test_core_pack_rules_executable(self, registry_root):
        """Test that core pack rules are actually executable."""
        core_pack_dir = registry_root / "core" / "v1.0.0"

        loader = PackLoader()
        pack = loader.load_pack(core_pack_dir)

        # Get pi-001 rule
        pi_001 = pack.get_rule("pi-001")
        assert pi_001 is not None

        # Verify patterns compile
        compiled_patterns = pi_001.compile_patterns()
        assert len(compiled_patterns) > 0

        # Test pattern matching on examples
        # Note: We're testing that patterns CAN be compiled and executed,
        # not that they necessarily match perfectly (that's the rule author's job)
        matched_count = 0
        for example in pi_001.examples.should_match:
            matched = any(pattern.search(example) for pattern in compiled_patterns)
            if matched:
                matched_count += 1

        # At least some examples should match
        assert matched_count > 0, "At least some should_match examples should match"

        # None of the should_not_match examples should match
        for example in pi_001.examples.should_not_match:
            matched = any(pattern.search(example) for pattern in compiled_patterns)
            assert not matched, f"Pattern should NOT match: {example}"

    def test_core_pack_manifest_integrity(self, registry_root):
        """Test core pack manifest integrity."""
        core_pack_dir = registry_root / "core" / "v1.0.0"

        loader = PackLoader()
        pack = loader.load_pack(core_pack_dir)

        # Verify all manifest rules are loaded
        for pack_rule in pack.manifest.rules:
            rule = pack.get_rule_versioned(pack_rule.id, pack_rule.version)
            assert rule is not None, f"Rule {pack_rule.versioned_id} declared in manifest but not loaded"

        # Verify metadata
        assert "maintainer" in pack.manifest.metadata
        assert pack.manifest.metadata["maintainer"] == "raxe-ai"
        assert "created" in pack.manifest.metadata
        assert "description" in pack.manifest.metadata

    def test_registry_get_all_rules_from_core(self, registry_root):
        """Test getting all rules from registry."""
        config = RegistryConfig(
            packs_root=registry_root,
            precedence=["core"]
        )

        registry = PackRegistry(config)
        registry.load_all_packs()

        # Get all rules
        all_rules = registry.get_all_rules()

        assert len(all_rules) >= 1
        assert any(r.rule_id == "pi-001" for r in all_rules)

    def test_registry_get_rules_by_family(self, registry_root):
        """Test getting rules by family from registry."""
        config = RegistryConfig(
            packs_root=registry_root,
            precedence=["core"]
        )

        registry = PackRegistry(config)
        registry.load_all_packs()

        # Get PI family rules
        pi_rules = registry.get_rules_by_family("PI")

        assert len(pi_rules) >= 1
        assert all(r.family.value == "PI" for r in pi_rules)

    def test_core_pack_versioned_directory_structure(self, registry_root):
        """Test core pack follows versioned directory structure."""
        core_dir = registry_root / "core"

        assert core_dir.exists()

        # Check for v1.0.0 directory
        v1_dir = core_dir / "v1.0.0"
        assert v1_dir.exists()
        assert v1_dir.is_dir()

        # Verify structure
        assert (v1_dir / "pack.yaml").exists()
        assert (v1_dir / "rules").exists()
        assert (v1_dir / "rules").is_dir()

    def test_pack_loader_latest_version(self, registry_root):
        """Test PackLoader.load_latest_pack gets v1.0.0."""
        core_dir = registry_root / "core"

        loader = PackLoader()
        pack = loader.load_latest_pack(core_dir)

        assert pack is not None
        assert pack.manifest.version == "1.0.0"
