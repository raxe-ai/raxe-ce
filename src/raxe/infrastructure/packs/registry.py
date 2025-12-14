"""Pack registry with precedence resolution.

Manages multiple loaded packs and resolves rule conflicts based on precedence.
Infrastructure layer - coordinates pack loading and rule resolution.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path

from raxe.domain.packs.models import RulePack
from raxe.domain.rules.models import Rule
from raxe.infrastructure.packs.loader import PackLoader, PackLoadError

logger = logging.getLogger(__name__)


@dataclass
class RegistryConfig:
    """Configuration for pack registry.

    Attributes:
        packs_root: Root directory containing pack type subdirectories
                   (e.g., ~/.raxe/packs/)
        precedence: Pack type precedence order (highest to lowest priority).
                   Default: ["custom", "community", "core"]
                   Custom rules override community, community overrides core.
        strict: If True, fail on first error. If False, log warnings and continue.
    """
    packs_root: Path
    precedence: list[str] = field(default_factory=lambda: ["custom", "community", "core"])
    strict: bool = False

    def __post_init__(self) -> None:
        """Validate configuration after construction."""
        if not self.precedence:
            raise ValueError("Precedence list cannot be empty")

        # Ensure packs_root is absolute path
        if not self.packs_root.is_absolute():
            self.packs_root = self.packs_root.resolve()


class PackRegistry:
    """Manages loaded rule packs with precedence.

    Handles:
    - Loading packs from filesystem (core, community, custom)
    - Precedence resolution (custom > community > core by default)
    - Rule deduplication (keeps highest precedence version)
    - Version conflict handling

    Example usage:
        config = RegistryConfig(packs_root=Path("~/.raxe/packs"))
        registry = PackRegistry(config)
        registry.load_all_packs()

        # Get rule (respects precedence)
        rule = registry.get_rule("pi-001")

        # Get all unique rules
        all_rules = registry.get_all_rules()
    """

    def __init__(self, config: RegistryConfig):
        """Initialize pack registry.

        Args:
            config: Registry configuration
        """
        self.config = config
        self.loader = PackLoader(strict=config.strict)
        self.packs: dict[str, RulePack] = {}

    def load_all_packs(self) -> None:
        """Load all packs from configured root directory.

        Loads latest version from each pack type:
        - packs_root/core/v*.*.*/pack.yaml
        - packs_root/community/v*.*.*/pack.yaml
        - packs_root/custom/*/pack.yaml (any subdirectory)

        Logs summary of loaded packs.
        """
        if not self.config.packs_root.exists():
            logger.warning(
                f"Packs root directory does not exist: {self.config.packs_root}"
            )
            return

        loaded_count = 0

        # Load from each pack type in precedence order
        for pack_type in self.config.precedence:
            pack_type_dir = self.config.packs_root / pack_type

            if not pack_type_dir.exists():
                logger.debug(f"Pack type directory does not exist: {pack_type_dir}")
                continue

            try:
                # Load latest version from this type
                latest_pack = self.loader.load_latest_pack(pack_type_dir)

                if latest_pack:
                    self.packs[pack_type] = latest_pack
                    loaded_count += 1
                    logger.info(
                        f"Loaded {pack_type} pack: {latest_pack.manifest.versioned_id} "
                        f"with {len(latest_pack.rules)} rules"
                    )
                else:
                    logger.debug(f"No valid pack found in {pack_type_dir}")

            except PackLoadError as e:
                logger.error(f"Failed to load {pack_type} pack: {e}")
                if self.config.strict:
                    raise

        logger.info(
            f"Pack registry loaded {loaded_count} packs from {self.config.packs_root}"
        )

    def load_pack_type(self, pack_type: str) -> RulePack | None:
        """Load or reload a specific pack type.

        Args:
            pack_type: Pack type identifier ('core', 'community', 'custom')

        Returns:
            Loaded pack, or None if not found

        Raises:
            PackLoadError: If strict mode enabled and load fails
        """
        pack_type_dir = self.config.packs_root / pack_type

        if not pack_type_dir.exists():
            logger.warning(f"Pack type directory not found: {pack_type_dir}")
            return None

        try:
            latest_pack = self.loader.load_latest_pack(pack_type_dir)

            if latest_pack:
                self.packs[pack_type] = latest_pack
                logger.info(
                    f"Loaded {pack_type} pack: {latest_pack.manifest.versioned_id}"
                )
                return latest_pack
            else:
                logger.warning(f"No valid pack found in {pack_type_dir}")
                return None

        except PackLoadError as e:
            logger.error(f"Failed to load {pack_type} pack: {e}")
            if self.config.strict:
                raise
            return None

    def get_rule(self, rule_id: str) -> Rule | None:
        """Get rule by ID, respecting precedence.

        Returns the first matching rule found when searching packs
        in precedence order. Higher precedence packs override lower.

        Args:
            rule_id: Rule identifier (e.g., 'pi-001')

        Returns:
            Rule from highest-precedence pack, or None if not found

        Example:
            # If custom pack has pi-001 v2.0.0 and core has pi-001 v1.0.0,
            # returns custom pack's version (custom > core precedence)
            rule = registry.get_rule("pi-001")
        """
        # Check packs in precedence order
        for pack_type in self.config.precedence:
            pack = self.packs.get(pack_type)
            if not pack:
                continue

            rule = pack.get_rule(rule_id)
            if rule:
                logger.debug(
                    f"Found rule {rule_id} in {pack_type} pack "
                    f"(version {rule.version})"
                )
                return rule

        logger.debug(f"Rule {rule_id} not found in any loaded pack")
        return None

    def get_rule_versioned(self, rule_id: str, version: str) -> Rule | None:
        """Get rule by ID and specific version.

        Searches all packs for exact rule_id@version match.
        Does NOT respect precedence - returns first exact match found.

        Args:
            rule_id: Rule identifier (e.g., 'pi-001')
            version: Semantic version (e.g., '0.0.1')

        Returns:
            Rule with exact version, or None if not found
        """
        for pack_type in self.config.precedence:
            pack = self.packs.get(pack_type)
            if not pack:
                continue

            rule = pack.get_rule_versioned(rule_id, version)
            if rule:
                logger.debug(
                    f"Found rule {rule_id}@{version} in {pack_type} pack"
                )
                return rule

        logger.debug(f"Rule {rule_id}@{version} not found in any loaded pack")
        return None

    def get_all_rules(self) -> list[Rule]:
        """Get all unique rules from all packs.

        Deduplicates by rule_id, keeping highest precedence version.
        If custom pack has pi-001 and core pack has pi-001, only
        custom version is returned.

        Returns:
            List of unique rules (deduplicated by rule_id)

        Example:
            all_rules = registry.get_all_rules()
            # Returns: [pi-001 (custom), pi-002 (core), ...]
        """
        seen_ids = set()
        rules = []

        # Iterate in precedence order
        for pack_type in self.config.precedence:
            pack = self.packs.get(pack_type)
            if not pack:
                continue

            for rule in pack.rules:
                # Only add if we haven't seen this rule_id yet
                if rule.rule_id not in seen_ids:
                    rules.append(rule)
                    seen_ids.add(rule.rule_id)
                else:
                    logger.debug(
                        f"Skipping duplicate rule {rule.rule_id} from {pack_type} pack "
                        f"(already loaded from higher precedence pack)"
                    )

        logger.debug(
            f"Collected {len(rules)} unique rules from {len(self.packs)} packs"
        )
        return rules

    def get_all_rules_with_versions(self) -> list[Rule]:
        """Get all rules from all packs, including duplicates.

        Does NOT deduplicate. Returns every rule from every pack,
        so you may get multiple versions of the same rule_id.

        Returns:
            List of all rules from all packs (may contain duplicate rule_ids)

        Example:
            all_rules = registry.get_all_rules_with_versions()
            # Returns: [pi-001@1.0.0 (core), pi-001@2.0.0 (custom), ...]
        """
        rules = []

        for pack_type in self.config.precedence:
            pack = self.packs.get(pack_type)
            if not pack:
                continue

            rules.extend(pack.rules)

        logger.debug(
            f"Collected {len(rules)} rules (including duplicates) from {len(self.packs)} packs"
        )
        return rules

    def get_rules_by_family(self, family: str) -> list[Rule]:
        """Get all unique rules in a specific family.

        Respects precedence - deduplicates by rule_id.

        Args:
            family: Rule family code (e.g., 'PI', 'JB', 'PII')

        Returns:
            List of unique rules in the specified family
        """
        all_rules = self.get_all_rules()
        return [r for r in all_rules if r.family.value == family]

    def get_rules_by_severity(self, severity: str) -> list[Rule]:
        """Get all unique rules with a specific severity.

        Respects precedence - deduplicates by rule_id.

        Args:
            severity: Severity level (e.g., 'critical', 'high', 'medium')

        Returns:
            List of unique rules with the specified severity
        """
        all_rules = self.get_all_rules()
        return [r for r in all_rules if r.severity.value == severity]

    def list_packs(self) -> list[RulePack]:
        """List all loaded packs.

        Returns:
            List of loaded packs in precedence order
        """
        return [
            self.packs[pack_type]
            for pack_type in self.config.precedence
            if pack_type in self.packs
        ]

    def get_pack(self, pack_type: str) -> RulePack | None:
        """Get pack by type.

        Args:
            pack_type: Pack type identifier ('core', 'community', 'custom')

        Returns:
            Pack if loaded, None otherwise
        """
        return self.packs.get(pack_type)

    def get_pack_info(self) -> dict[str, dict[str, any]]:
        """Get summary information about all loaded packs.

        Returns:
            Dictionary mapping pack_type to pack metadata

        Example:
            {
                'core': {
                    'version': '0.0.1',
                    'rule_count': 5,
                    'pack_type': 'OFFICIAL',
                },
                'custom': {
                    'version': '0.0.1',
                    'rule_count': 2,
                    'pack_type': 'CUSTOM',
                }
            }
        """
        info = {}

        for pack_type, pack in self.packs.items():
            info[pack_type] = {
                'id': pack.manifest.id,
                'version': pack.manifest.version,
                'name': pack.manifest.name,
                'pack_type': pack.manifest.pack_type.value,
                'rule_count': len(pack.rules),
                'schema_version': pack.manifest.schema_version,
            }

        return info

    def reload_all_packs(self) -> None:
        """Reload all packs from filesystem.

        Clears current packs and loads fresh from disk.
        Useful for picking up rule updates.
        """
        logger.info("Reloading all packs from filesystem")
        self.packs.clear()
        self.load_all_packs()
