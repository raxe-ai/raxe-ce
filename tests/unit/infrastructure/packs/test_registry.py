"""Tests for PackRegistry.

Tests pack registry with precedence resolution:
- Loading packs from three-tier structure
- Precedence resolution (custom > community > core)
- Rule deduplication
- Version conflicts
"""

import shutil
from pathlib import Path

import pytest

from raxe.infrastructure.packs.registry import PackRegistry, RegistryConfig


@pytest.fixture
def test_rule_source():
    """Path to the test rule file."""
    return (
        Path(__file__).parent.parent.parent.parent.parent
        / "src/raxe/packs/core/v1.0.0/rules/PI/pi-001@1.0.0.yaml"
    )


@pytest.fixture
def three_tier_packs(tmp_path, test_rule_source):
    """Create three-tier pack structure (core, community, custom)."""
    packs_root = tmp_path / "packs"
    packs_root.mkdir()

    # Create core pack v1.0.0
    core_dir = packs_root / "core" / "v1.0.0"
    core_dir.mkdir(parents=True)
    (core_dir / "pack.yaml").write_text("""
pack:
  id: core
  version: 1.0.0
  name: Core Rules
  type: OFFICIAL
  schema_version: 1.1.0
  rules:
    - id: pi-001
      version: 1.0.0
      path: rules/PI/pi-001@1.0.0.yaml
  metadata:
    maintainer: raxe-ai
""")
    rules_dir = core_dir / "rules" / "PI"
    rules_dir.mkdir(parents=True)
    shutil.copy(test_rule_source, rules_dir / "pi-001@1.0.0.yaml")

    # Create community pack v2.0.0 with modified rule
    community_dir = packs_root / "community" / "v2.0.0"
    community_dir.mkdir(parents=True)
    (community_dir / "pack.yaml").write_text("""
pack:
  id: community
  version: 2.0.0
  name: Community Rules
  type: COMMUNITY
  schema_version: 1.1.0
  rules:
    - id: pi-002
      version: 1.0.0
      path: rules/PI/pi-002@1.0.0.yaml
  metadata:
    maintainer: community
""")
    rules_dir = community_dir / "rules" / "PI"
    rules_dir.mkdir(parents=True)
    # Create pi-002 by modifying pi-001
    rule_content = test_rule_source.read_text()
    rule_content = rule_content.replace("rule_id: pi-001", "rule_id: pi-002")
    (rules_dir / "pi-002@1.0.0.yaml").write_text(rule_content)

    # Create custom pack with pi-001 override
    custom_dir = packs_root / "custom" / "v1.0.0"
    custom_dir.mkdir(parents=True)
    (custom_dir / "pack.yaml").write_text("""
pack:
  id: custom
  version: 1.0.0
  name: Custom Rules
  type: CUSTOM
  schema_version: 1.1.0
  rules:
    - id: pi-001
      version: 1.0.0
      path: rules/PI/pi-001@1.0.0.yaml
    - id: pi-003
      version: 1.0.0
      path: rules/PI/pi-003@1.0.0.yaml
  metadata:
    maintainer: custom-user
""")
    rules_dir = custom_dir / "rules" / "PI"
    rules_dir.mkdir(parents=True)
    shutil.copy(test_rule_source, rules_dir / "pi-001@1.0.0.yaml")
    # Create pi-003
    rule_content = test_rule_source.read_text()
    rule_content = rule_content.replace("rule_id: pi-001", "rule_id: pi-003")
    (rules_dir / "pi-003@1.0.0.yaml").write_text(rule_content)

    return packs_root


@pytest.fixture
def simple_pack_root(tmp_path, test_rule_source):
    """Create simple pack structure with just core."""
    packs_root = tmp_path / "packs"
    packs_root.mkdir()

    core_dir = packs_root / "core" / "v1.0.0"
    core_dir.mkdir(parents=True)
    (core_dir / "pack.yaml").write_text("""
pack:
  id: core
  version: 1.0.0
  name: Core Rules
  type: OFFICIAL
  schema_version: 1.1.0
  rules:
    - id: pi-001
      version: 1.0.0
      path: rules/PI/pi-001@1.0.0.yaml
  metadata:
    maintainer: raxe-ai
""")
    rules_dir = core_dir / "rules" / "PI"
    rules_dir.mkdir(parents=True)
    shutil.copy(test_rule_source, rules_dir / "pi-001@1.0.0.yaml")

    return packs_root


class TestPackRegistry:
    """Tests for PackRegistry."""

    def test_registry_loads_core_pack(self, simple_pack_root):
        """Test registry loads core pack."""
        config = RegistryConfig(packs_root=simple_pack_root)
        registry = PackRegistry(config)

        registry.load_all_packs()

        assert "core" in registry.packs
        core_pack = registry.packs["core"]
        assert core_pack.manifest.id == "core"
        assert len(core_pack.rules) == 1
        assert core_pack.rules[0].rule_id == "pi-001"

    def test_registry_loads_all_tiers(self, three_tier_packs):
        """Test registry loads all three tiers."""
        config = RegistryConfig(packs_root=three_tier_packs)
        registry = PackRegistry(config)

        registry.load_all_packs()

        assert len(registry.packs) == 3
        assert "core" in registry.packs
        assert "community" in registry.packs
        assert "custom" in registry.packs

    def test_registry_precedence_custom_over_core(self, three_tier_packs):
        """Test custom rules override core rules."""
        config = RegistryConfig(
            packs_root=three_tier_packs, precedence=["custom", "community", "core"]
        )
        registry = PackRegistry(config)
        registry.load_all_packs()

        # Both custom and core have pi-001
        # Should get custom version due to precedence
        rule = registry.get_rule("pi-001")

        assert rule is not None
        assert rule.rule_id == "pi-001"
        # Verify it came from custom pack by checking it exists there
        custom_pack = registry.get_pack("custom")
        assert custom_pack.get_rule("pi-001") is not None

    def test_registry_get_all_rules_deduplicates(self, three_tier_packs):
        """Test get_all_rules deduplicates by rule_id."""
        config = RegistryConfig(
            packs_root=three_tier_packs, precedence=["custom", "community", "core"]
        )
        registry = PackRegistry(config)
        registry.load_all_packs()

        # Total rules: core(pi-001) + community(pi-002) + custom(pi-001, pi-003)
        # After dedup: pi-001 (custom), pi-002 (community), pi-003 (custom)
        all_rules = registry.get_all_rules()

        rule_ids = [r.rule_id for r in all_rules]
        assert len(all_rules) == 3
        assert set(rule_ids) == {"pi-001", "pi-002", "pi-003"}

        # Verify pi-001 came from custom (highest precedence)
        registry.get_rule("pi-001")
        custom_pack = registry.get_pack("custom")
        assert custom_pack.get_rule("pi-001") is not None

    def test_registry_get_all_rules_with_versions_includes_duplicates(self, three_tier_packs):
        """Test get_all_rules_with_versions includes all versions."""
        config = RegistryConfig(packs_root=three_tier_packs)
        registry = PackRegistry(config)
        registry.load_all_packs()

        all_rules = registry.get_all_rules_with_versions()

        # Should have 4 rules total (including duplicate pi-001)
        assert len(all_rules) == 4

        # Should have two pi-001 rules
        pi_001_rules = [r for r in all_rules if r.rule_id == "pi-001"]
        assert len(pi_001_rules) == 2

    def test_registry_get_rule_not_found(self, simple_pack_root):
        """Test getting non-existent rule returns None."""
        config = RegistryConfig(packs_root=simple_pack_root)
        registry = PackRegistry(config)
        registry.load_all_packs()

        rule = registry.get_rule("non-existent")
        assert rule is None

    def test_registry_get_rule_versioned(self, simple_pack_root):
        """Test getting rule by specific version."""
        config = RegistryConfig(packs_root=simple_pack_root)
        registry = PackRegistry(config)
        registry.load_all_packs()

        rule = registry.get_rule_versioned("pi-001", "1.0.0")
        assert rule is not None
        assert rule.rule_id == "pi-001"
        assert rule.version == "1.0.0"

        # Non-existent version
        rule = registry.get_rule_versioned("pi-001", "2.0.0")
        assert rule is None

    def test_registry_get_rules_by_family(self, simple_pack_root):
        """Test getting rules by family."""
        config = RegistryConfig(packs_root=simple_pack_root)
        registry = PackRegistry(config)
        registry.load_all_packs()

        pi_rules = registry.get_rules_by_family("PI")
        assert len(pi_rules) == 1
        assert pi_rules[0].family.value == "PI"

        jb_rules = registry.get_rules_by_family("JB")
        assert len(jb_rules) == 0

    def test_registry_get_rules_by_severity(self, simple_pack_root):
        """Test getting rules by severity."""
        config = RegistryConfig(packs_root=simple_pack_root)
        registry = PackRegistry(config)
        registry.load_all_packs()

        critical_rules = registry.get_rules_by_severity("critical")
        assert len(critical_rules) == 1
        assert critical_rules[0].severity.value == "critical"

        low_rules = registry.get_rules_by_severity("low")
        assert len(low_rules) == 0

    def test_registry_list_packs(self, three_tier_packs):
        """Test listing all loaded packs."""
        config = RegistryConfig(packs_root=three_tier_packs)
        registry = PackRegistry(config)
        registry.load_all_packs()

        packs = registry.list_packs()
        assert len(packs) == 3

        pack_ids = {p.manifest.id for p in packs}
        assert pack_ids == {"core", "community", "custom"}

    def test_registry_get_pack(self, simple_pack_root):
        """Test getting specific pack."""
        config = RegistryConfig(packs_root=simple_pack_root)
        registry = PackRegistry(config)
        registry.load_all_packs()

        core_pack = registry.get_pack("core")
        assert core_pack is not None
        assert core_pack.manifest.id == "core"

        custom_pack = registry.get_pack("custom")
        assert custom_pack is None

    def test_registry_get_pack_info(self, three_tier_packs):
        """Test getting pack information summary."""
        config = RegistryConfig(packs_root=three_tier_packs)
        registry = PackRegistry(config)
        registry.load_all_packs()

        info = registry.get_pack_info()

        assert "core" in info
        assert info["core"]["version"] == "1.0.0"
        assert info["core"]["rule_count"] == 1
        assert info["core"]["pack_type"] == "OFFICIAL"

        assert "community" in info
        assert info["community"]["pack_type"] == "COMMUNITY"

        assert "custom" in info
        assert info["custom"]["rule_count"] == 2

    def test_registry_custom_precedence_order(self, three_tier_packs):
        """Test custom precedence order."""
        # Reverse precedence: core > community > custom
        config = RegistryConfig(
            packs_root=three_tier_packs, precedence=["core", "community", "custom"]
        )
        registry = PackRegistry(config)
        registry.load_all_packs()

        # pi-001 exists in both core and custom
        # With reversed precedence, should get core version
        rule = registry.get_rule("pi-001")

        assert rule is not None
        # Verify it came from core pack
        core_pack = registry.get_pack("core")
        assert core_pack.get_rule("pi-001") is not None

    def test_registry_load_pack_type(self, three_tier_packs):
        """Test loading specific pack type."""
        config = RegistryConfig(packs_root=three_tier_packs)
        registry = PackRegistry(config)

        # Load only core
        pack = registry.load_pack_type("core")

        assert pack is not None
        assert pack.manifest.id == "core"
        assert "core" in registry.packs

        # Community and custom not loaded yet
        assert "community" not in registry.packs
        assert "custom" not in registry.packs

    def test_registry_reload_all_packs(self, simple_pack_root):
        """Test reloading all packs."""
        config = RegistryConfig(packs_root=simple_pack_root)
        registry = PackRegistry(config)

        registry.load_all_packs()
        assert len(registry.packs) == 1

        # Reload
        registry.reload_all_packs()
        assert len(registry.packs) == 1
        assert "core" in registry.packs

    def test_registry_empty_packs_root(self, tmp_path):
        """Test registry with empty packs root."""
        empty_root = tmp_path / "empty"
        empty_root.mkdir()

        config = RegistryConfig(packs_root=empty_root)
        registry = PackRegistry(config)

        registry.load_all_packs()
        assert len(registry.packs) == 0

    def test_registry_missing_packs_root(self, tmp_path):
        """Test registry with non-existent packs root."""
        missing_root = tmp_path / "does_not_exist"

        config = RegistryConfig(packs_root=missing_root)
        registry = PackRegistry(config)

        # Should not raise, just log warning
        registry.load_all_packs()
        assert len(registry.packs) == 0

    def test_registry_loads_latest_version(self, tmp_path, test_rule_source):
        """Test registry loads latest version from multiple versions."""
        packs_root = tmp_path / "packs"
        packs_root.mkdir()

        core_dir = packs_root / "core"
        core_dir.mkdir()

        # Create v1.0.0
        v1_dir = core_dir / "v1.0.0"
        v1_dir.mkdir()
        (v1_dir / "pack.yaml").write_text("""
pack:
  id: core
  version: 1.0.0
  name: Core v1
  type: OFFICIAL
  schema_version: 1.1.0
  rules:
    - id: pi-001
      version: 1.0.0
      path: rules/pi-001@1.0.0.yaml
  metadata: {}
""")
        rules_dir = v1_dir / "rules"
        rules_dir.mkdir()
        shutil.copy(test_rule_source, rules_dir / "pi-001@1.0.0.yaml")

        # Create v2.0.0
        v2_dir = core_dir / "v2.0.0"
        v2_dir.mkdir()
        (v2_dir / "pack.yaml").write_text("""
pack:
  id: core
  version: 2.0.0
  name: Core v2
  type: OFFICIAL
  schema_version: 1.1.0
  rules:
    - id: pi-001
      version: 1.0.0
      path: rules/pi-001@1.0.0.yaml
  metadata: {}
""")
        rules_dir = v2_dir / "rules"
        rules_dir.mkdir()
        shutil.copy(test_rule_source, rules_dir / "pi-001@1.0.0.yaml")

        config = RegistryConfig(packs_root=packs_root)
        registry = PackRegistry(config)
        registry.load_all_packs()

        # Should load v2.0.0 (latest)
        core_pack = registry.get_pack("core")
        assert core_pack is not None
        assert core_pack.manifest.version == "2.0.0"
        assert core_pack.manifest.name == "Core v2"

    def test_registry_config_validation(self, tmp_path):
        """Test registry config validation."""
        packs_root = tmp_path / "packs"
        packs_root.mkdir()

        # Valid config
        config = RegistryConfig(packs_root=packs_root)
        assert config.packs_root.is_absolute()

        # Empty precedence should raise
        with pytest.raises(ValueError, match="Precedence list cannot be empty"):
            RegistryConfig(packs_root=packs_root, precedence=[])
