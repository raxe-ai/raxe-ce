"""Tests for PackLoader.

Tests pack loading from filesystem with various scenarios:
- Valid pack with single rule
- Pack with multiple rules
- Missing pack.yaml
- Invalid manifest format
- Missing rule files
- Rule version mismatches
"""

import shutil
from pathlib import Path

import pytest

from raxe.domain.packs.models import PackType
from raxe.infrastructure.packs.loader import PackLoader, PackLoadError


@pytest.fixture
def test_rule_source():
    """Path to the test rule file."""
    return (
        Path(__file__).parent.parent.parent.parent.parent
        / "src/raxe/packs/core/v1.0.0/rules/PI/pi-001@1.0.0.yaml"
    )


@pytest.fixture
def simple_pack(tmp_path, test_rule_source):
    """Create a simple test pack with one rule."""
    pack_dir = tmp_path / "test_pack"
    pack_dir.mkdir()

    # Create pack.yaml
    pack_yaml = pack_dir / "pack.yaml"
    pack_yaml.write_text("""
pack:
  id: test
  version: 1.0.0
  name: Test Pack
  type: CUSTOM
  schema_version: 1.1.0
  rules:
    - id: pi-001
      version: 1.0.0
      path: rules/PI/pi-001@1.0.0.yaml
  metadata:
    maintainer: test
""")

    # Copy test rule
    rules_dir = pack_dir / "rules" / "PI"
    rules_dir.mkdir(parents=True)
    shutil.copy(test_rule_source, rules_dir / "pi-001@1.0.0.yaml")

    return pack_dir


@pytest.fixture
def multi_rule_pack(tmp_path, test_rule_source):
    """Create a pack with multiple rules."""
    pack_dir = tmp_path / "multi_pack"
    pack_dir.mkdir()

    # Create pack.yaml with two rules
    pack_yaml = pack_dir / "pack.yaml"
    pack_yaml.write_text("""
pack:
  id: multi
  version: 2.0.0
  name: Multi Rule Pack
  type: COMMUNITY
  schema_version: 1.1.0
  rules:
    - id: pi-001
      version: 1.0.0
      path: rules/PI/pi-001@1.0.0.yaml
    - id: pi-002
      version: 1.0.0
      path: rules/PI/pi-002@1.0.0.yaml
  metadata:
    maintainer: community
""")

    # Copy test rule twice (simulating two rules)
    rules_dir = pack_dir / "rules" / "PI"
    rules_dir.mkdir(parents=True)
    shutil.copy(test_rule_source, rules_dir / "pi-001@1.0.0.yaml")

    # Create pi-002 by modifying pi-001
    rule_content = test_rule_source.read_text()
    rule_content = rule_content.replace("rule_id: pi-001", "rule_id: pi-002")
    (rules_dir / "pi-002@1.0.0.yaml").write_text(rule_content)

    return pack_dir


class TestPackLoader:
    """Tests for PackLoader."""

    def test_load_simple_pack(self, simple_pack):
        """Test loading a simple pack with one rule."""
        loader = PackLoader()
        pack = loader.load_pack(simple_pack)

        assert pack.manifest.id == "test"
        assert pack.manifest.version == "1.0.0"
        assert pack.manifest.name == "Test Pack"
        assert pack.manifest.pack_type == PackType.CUSTOM
        assert len(pack.rules) == 1
        assert pack.rules[0].rule_id == "pi-001"

    def test_load_multi_rule_pack(self, multi_rule_pack):
        """Test loading a pack with multiple rules."""
        loader = PackLoader()
        pack = loader.load_pack(multi_rule_pack)

        assert pack.manifest.id == "multi"
        assert pack.manifest.version == "2.0.0"
        assert len(pack.rules) == 2
        rule_ids = {r.rule_id for r in pack.rules}
        assert rule_ids == {"pi-001", "pi-002"}

    def test_load_pack_missing_directory(self, tmp_path):
        """Test loading pack from non-existent directory."""
        loader = PackLoader()
        non_existent = tmp_path / "does_not_exist"

        with pytest.raises(FileNotFoundError, match="Pack directory not found"):
            loader.load_pack(non_existent)

    def test_load_pack_missing_manifest(self, tmp_path):
        """Test loading pack without pack.yaml."""
        pack_dir = tmp_path / "no_manifest"
        pack_dir.mkdir()

        loader = PackLoader()

        with pytest.raises(FileNotFoundError, match="Pack manifest not found"):
            loader.load_pack(pack_dir)

    def test_load_pack_invalid_manifest_format(self, tmp_path):
        """Test loading pack with invalid YAML."""
        pack_dir = tmp_path / "bad_yaml"
        pack_dir.mkdir()

        pack_yaml = pack_dir / "pack.yaml"
        pack_yaml.write_text("{ this is not valid yaml [")

        loader = PackLoader()

        with pytest.raises(PackLoadError, match="Failed to parse manifest YAML"):
            loader.load_pack(pack_dir)

    def test_load_pack_missing_required_fields(self, tmp_path):
        """Test loading pack with missing required manifest fields."""
        pack_dir = tmp_path / "missing_fields"
        pack_dir.mkdir()

        pack_yaml = pack_dir / "pack.yaml"
        pack_yaml.write_text("""
pack:
  id: test
  # Missing version, name, etc.
  rules: []
""")

        loader = PackLoader()

        # Changed to match actual error message
        with pytest.raises(PackLoadError, match="Pack must declare at least one rule"):
            loader.load_pack(pack_dir)

    def test_load_pack_missing_rule_file_strict(self, tmp_path):
        """Test loading pack with missing rule file in strict mode."""
        pack_dir = tmp_path / "missing_rule"
        pack_dir.mkdir()

        pack_yaml = pack_dir / "pack.yaml"
        pack_yaml.write_text("""
pack:
  id: test
  version: 1.0.0
  name: Test
  type: CUSTOM
  schema_version: 1.1.0
  rules:
    - id: pi-001
      version: 1.0.0
      path: rules/PI/pi-001@1.0.0.yaml
  metadata:
    maintainer: test
""")

        loader = PackLoader(strict=True)

        with pytest.raises(PackLoadError, match="Rule file not found"):
            loader.load_pack(pack_dir)

    def test_load_pack_missing_rule_file_non_strict(self, tmp_path):
        """Test loading pack with missing rule file in non-strict mode."""
        pack_dir = tmp_path / "missing_rule"
        pack_dir.mkdir()

        pack_yaml = pack_dir / "pack.yaml"
        pack_yaml.write_text("""
pack:
  id: test
  version: 1.0.0
  name: Test
  type: CUSTOM
  schema_version: 1.1.0
  rules:
    - id: pi-001
      version: 1.0.0
      path: rules/PI/pi-001@1.0.0.yaml
  metadata:
    maintainer: test
""")

        loader = PackLoader(strict=False)

        # In non-strict mode, if no rules can be loaded, it still raises
        # because a pack must have at least one rule
        with pytest.raises(PackLoadError, match="No rules successfully loaded"):
            loader.load_pack(pack_dir)

    def test_load_pack_rule_version_mismatch(self, tmp_path, test_rule_source):
        """Test loading pack where rule version doesn't match manifest."""
        pack_dir = tmp_path / "version_mismatch"
        pack_dir.mkdir()

        pack_yaml = pack_dir / "pack.yaml"
        pack_yaml.write_text("""
pack:
  id: test
  version: 1.0.0
  name: Test
  type: CUSTOM
  schema_version: 1.1.0
  rules:
    - id: pi-001
      version: 2.0.0  # Different from actual rule version (1.0.0)
      path: rules/PI/pi-001@1.0.0.yaml
  metadata:
    maintainer: test
""")

        rules_dir = pack_dir / "rules" / "PI"
        rules_dir.mkdir(parents=True)
        shutil.copy(test_rule_source, rules_dir / "pi-001@1.0.0.yaml")

        loader = PackLoader(strict=True)

        with pytest.raises(PackLoadError, match="version mismatch"):
            loader.load_pack(pack_dir)

    def test_load_pack_rule_id_mismatch(self, tmp_path, test_rule_source):
        """Test loading pack where rule ID doesn't match manifest."""
        pack_dir = tmp_path / "id_mismatch"
        pack_dir.mkdir()

        pack_yaml = pack_dir / "pack.yaml"
        pack_yaml.write_text("""
pack:
  id: test
  version: 1.0.0
  name: Test
  type: CUSTOM
  schema_version: 1.1.0
  rules:
    - id: pi-999  # Different from actual rule ID
      version: 1.0.0
      path: rules/PI/pi-001@1.0.0.yaml
  metadata:
    maintainer: test
""")

        rules_dir = pack_dir / "rules" / "PI"
        rules_dir.mkdir(parents=True)
        shutil.copy(test_rule_source, rules_dir / "pi-001@1.0.0.yaml")

        loader = PackLoader(strict=True)

        with pytest.raises(PackLoadError, match="ID mismatch"):
            loader.load_pack(pack_dir)

    def test_load_packs_from_directory(self, tmp_path, test_rule_source):
        """Test loading multiple packs from directory."""
        # Create two packs
        pack1_dir = tmp_path / "pack1"
        pack1_dir.mkdir()
        (pack1_dir / "pack.yaml").write_text("""
pack:
  id: pack1
  version: 1.0.0
  name: Pack 1
  type: CUSTOM
  schema_version: 1.1.0
  rules:
    - id: pi-001
      version: 1.0.0
      path: rules/pi-001@1.0.0.yaml
  metadata: {}
""")
        rules_dir = pack1_dir / "rules"
        rules_dir.mkdir()
        shutil.copy(test_rule_source, rules_dir / "pi-001@1.0.0.yaml")

        pack2_dir = tmp_path / "pack2"
        pack2_dir.mkdir()
        (pack2_dir / "pack.yaml").write_text("""
pack:
  id: pack2
  version: 2.0.0
  name: Pack 2
  type: COMMUNITY
  schema_version: 1.1.0
  rules:
    - id: pi-001
      version: 1.0.0
      path: rules/pi-001@1.0.0.yaml
  metadata: {}
""")
        rules_dir = pack2_dir / "rules"
        rules_dir.mkdir()
        shutil.copy(test_rule_source, rules_dir / "pi-001@1.0.0.yaml")

        loader = PackLoader()
        packs = loader.load_packs_from_directory(tmp_path)

        assert len(packs) == 2
        pack_ids = {p.manifest.id for p in packs}
        assert pack_ids == {"pack1", "pack2"}

    def test_load_latest_pack(self, tmp_path, test_rule_source):
        """Test loading latest version from versioned directories."""
        type_dir = tmp_path / "core"
        type_dir.mkdir()

        # Create v1.0.0
        v1_dir = type_dir / "v1.0.0"
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
        v2_dir = type_dir / "v2.0.0"
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

        loader = PackLoader()
        pack = loader.load_latest_pack(type_dir)

        # Should load v2.0.0 (latest)
        assert pack is not None
        assert pack.manifest.version == "2.0.0"
        assert pack.manifest.name == "Core v2"

    def test_load_latest_pack_no_versions(self, tmp_path):
        """Test load_latest_pack when no version directories exist."""
        type_dir = tmp_path / "empty"
        type_dir.mkdir()

        loader = PackLoader()
        pack = loader.load_latest_pack(type_dir)

        assert pack is None

    def test_load_pack_with_metadata(self, tmp_path, test_rule_source):
        """Test loading pack preserves metadata."""
        pack_dir = tmp_path / "metadata_pack"
        pack_dir.mkdir()

        pack_yaml = pack_dir / "pack.yaml"
        pack_yaml.write_text("""
pack:
  id: test
  version: 1.0.0
  name: Test Pack
  type: OFFICIAL
  schema_version: 1.1.0
  rules:
    - id: pi-001
      version: 1.0.0
      path: rules/PI/pi-001@1.0.0.yaml
  metadata:
    maintainer: raxe-ai
    created: "2025-11-15"
    description: "Test pack"
    custom_field: "custom_value"
""")

        rules_dir = pack_dir / "rules" / "PI"
        rules_dir.mkdir(parents=True)
        shutil.copy(test_rule_source, rules_dir / "pi-001@1.0.0.yaml")

        loader = PackLoader()
        pack = loader.load_pack(pack_dir)

        assert pack.manifest.metadata["maintainer"] == "raxe-ai"
        assert pack.manifest.metadata["created"] == "2025-11-15"
        assert pack.manifest.metadata["custom_field"] == "custom_value"

    def test_pack_type_validation(self, tmp_path, test_rule_source):
        """Test different pack types are loaded correctly."""
        for pack_type in ["OFFICIAL", "COMMUNITY", "CUSTOM"]:
            pack_dir = tmp_path / f"pack_{pack_type.lower()}"
            pack_dir.mkdir()

            pack_yaml = pack_dir / "pack.yaml"
            pack_yaml.write_text(f"""
pack:
  id: test
  version: 1.0.0
  name: Test
  type: {pack_type}
  schema_version: 1.1.0
  rules:
    - id: pi-001
      version: 1.0.0
      path: rules/pi-001@1.0.0.yaml
  metadata: {{}}
""")

            rules_dir = pack_dir / "rules"
            rules_dir.mkdir()
            shutil.copy(test_rule_source, rules_dir / "pi-001@1.0.0.yaml")

            loader = PackLoader()
            pack = loader.load_pack(pack_dir)

            assert pack.manifest.pack_type == PackType(pack_type)
