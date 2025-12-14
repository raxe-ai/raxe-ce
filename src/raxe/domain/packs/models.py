"""Domain models for rule packs.

Pure domain layer - NO I/O operations.
This module defines immutable value objects for rule pack management,
supporting the three-tier pack distribution system (Core/Community/Custom).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from raxe.domain.rules.models import Rule


class PackType(Enum):
    """Type of rule pack.

    Defines the tier in the three-tier pack distribution system:
    - OFFICIAL: Raxe-maintained core packs bundled with installation
    - COMMUNITY: Community-contributed packs downloaded from registry
    - CUSTOM: User-created packs for organization-specific rules
    """
    OFFICIAL = "OFFICIAL"
    COMMUNITY = "COMMUNITY"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True)
class PackRule:
    """Reference to a rule within a pack.

    Points to a specific versioned rule file within the pack structure.

    Attributes:
        id: Rule identifier (e.g., 'pi-001')
        version: Semantic version of the rule (e.g., '0.0.1')
        path: Relative path to rule YAML file within pack directory

    Example:
        PackRule(
            id='pi-001',
            version='0.0.1',
            path='rules/PI/pi-001@0.0.1.yaml'
        )
    """
    id: str
    version: str
    path: str

    def __post_init__(self) -> None:
        """Validate pack rule reference after construction.

        Raises:
            ValueError: If any field is empty or invalid
        """
        if not self.id:
            raise ValueError("Rule id cannot be empty")
        if not self.version:
            raise ValueError("Rule version cannot be empty")
        if not self.path:
            raise ValueError("Rule path cannot be empty")

    @property
    def versioned_id(self) -> str:
        """Return rule_id@version format.

        Returns:
            String in format 'rule_id@version' (e.g., 'pi-001@1.0.0')
        """
        return f"{self.id}@{self.version}"


@dataclass(frozen=True)
class PackManifest:
    """Pack manifest metadata.

    Describes the contents and metadata of a rule pack.
    Loaded from pack.yaml file in pack directory.

    Attributes:
        id: Pack identifier (e.g., 'core', 'community', 'custom')
        version: Semantic version of the pack (e.g., '0.0.1')
        name: Human-readable pack name
        pack_type: Type of pack (OFFICIAL, COMMUNITY, CUSTOM)
        schema_version: Rule schema version this pack uses
        rules: List of rule references included in this pack
        metadata: Additional metadata (maintainer, created, description, etc.)
        signature: Cryptographic signature of pack (added in Phase 3b)
        signature_algorithm: Algorithm used for signature (e.g., 'ed25519')

    Example:
        PackManifest(
            id='core',
            version='0.0.1',
            name='RAXE Core LLM Safety Rules',
            pack_type=PackType.OFFICIAL,
            schema_version='0.0.1',
            rules=[PackRule(id='pi-001', version='0.0.1', path='rules/PI/pi-001@0.0.1.yaml')],
            metadata={'maintainer': 'raxe-ai', 'created': '2025-11-15'}
        )
    """
    id: str
    version: str
    name: str
    pack_type: PackType
    schema_version: str
    rules: list[PackRule]
    metadata: dict[str, Any] = field(default_factory=dict)
    signature: str | None = None
    signature_algorithm: str | None = None

    def __post_init__(self) -> None:
        """Validate manifest after construction.

        Raises:
            ValueError: If validation fails
        """
        if not self.id:
            raise ValueError("Pack id cannot be empty")
        if not self.version:
            raise ValueError("Pack version cannot be empty")
        if not self.name:
            raise ValueError("Pack name cannot be empty")
        if not self.schema_version:
            raise ValueError("Pack schema_version cannot be empty")
        if not self.rules:
            raise ValueError("Pack must contain at least one rule")

        # Validate version is semver format (basic check)
        if not self._is_valid_semver(self.version):
            raise ValueError(
                f"Pack version must be semver format (e.g., '0.0.1'), got '{self.version}'"
            )

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
            # Check each part is a non-negative integer
            for part in parts:
                int(part)
            return True
        except ValueError:
            return False

    @property
    def rule_count(self) -> int:
        """Number of rules declared in pack manifest.

        Returns:
            Count of rules in manifest
        """
        return len(self.rules)

    @property
    def versioned_id(self) -> str:
        """Return pack_id@version format.

        Returns:
            String in format 'pack_id@version' (e.g., 'core@1.0.0')
        """
        return f"{self.id}@{self.version}"


@dataclass(frozen=True)
class RulePack:
    """A collection of loaded rules with metadata.

    Immutable value object containing a pack manifest and all loaded rules.
    Represents a complete, validated rule pack ready for use.

    Attributes:
        manifest: Pack manifest with metadata
        rules: List of loaded Rule objects

    Example:
        RulePack(
            manifest=PackManifest(...),
            rules=[Rule(...), Rule(...)]
        )
    """
    manifest: PackManifest
    rules: list[Rule]

    def __post_init__(self) -> None:
        """Validate pack after construction.

        Raises:
            ValueError: If pack validation fails
        """
        # Verify rule count matches manifest
        if len(self.rules) != self.manifest.rule_count:
            raise ValueError(
                f"Pack has {len(self.rules)} loaded rules but manifest "
                f"declares {self.manifest.rule_count} rules"
            )

        # Verify each rule matches a manifest entry
        manifest_rule_ids = {r.versioned_id for r in self.manifest.rules}
        loaded_rule_ids = {r.versioned_id for r in self.rules}

        missing = manifest_rule_ids - loaded_rule_ids
        if missing:
            raise ValueError(
                f"Pack is missing rules declared in manifest: {missing}"
            )

        extra = loaded_rule_ids - manifest_rule_ids
        if extra:
            raise ValueError(
                f"Pack contains rules not declared in manifest: {extra}"
            )

    def get_rule(self, rule_id: str) -> Rule | None:
        """Get rule by ID (without version).

        Args:
            rule_id: Rule identifier (e.g., 'pi-001')

        Returns:
            Rule if found, None otherwise

        Note:
            If multiple versions exist, returns first match.
            Use get_rule_versioned() for specific version.
        """
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None

    def get_rule_versioned(self, rule_id: str, version: str) -> Rule | None:
        """Get rule by ID and specific version.

        Args:
            rule_id: Rule identifier (e.g., 'pi-001')
            version: Semantic version (e.g., '0.0.1')

        Returns:
            Rule if found with exact version, None otherwise
        """
        for rule in self.rules:
            if rule.rule_id == rule_id and rule.version == version:
                return rule
        return None

    def get_rules_by_family(self, family: str) -> list[Rule]:
        """Get all rules in a specific family.

        Args:
            family: Rule family code (e.g., 'PI', 'JB', 'PII')

        Returns:
            List of rules in the specified family
        """
        return [r for r in self.rules if r.family.value == family]

    def get_rules_by_severity(self, severity: str) -> list[Rule]:
        """Get all rules with a specific severity.

        Args:
            severity: Severity level (e.g., 'critical', 'high')

        Returns:
            List of rules with the specified severity
        """
        return [r for r in self.rules if r.severity.value == severity]

    @property
    def pack_id(self) -> str:
        """Pack identifier.

        Returns:
            Pack ID from manifest
        """
        return self.manifest.id

    @property
    def version(self) -> str:
        """Pack version.

        Returns:
            Pack version from manifest
        """
        return self.manifest.version

    @property
    def pack_type(self) -> PackType:
        """Pack type.

        Returns:
            Pack type from manifest
        """
        return self.manifest.pack_type
