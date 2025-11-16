"""Pack loader infrastructure.

Handles loading rule packs from filesystem.
Infrastructure layer - performs I/O operations.
"""
import logging
from pathlib import Path

import yaml

from raxe.domain.packs.models import (
    PackManifest,
    PackRule,
    PackType,
    RulePack,
)
from raxe.domain.rules.models import Rule
from raxe.infrastructure.rules.yaml_loader import YAMLLoader, YAMLLoadError

logger = logging.getLogger(__name__)


class PackLoadError(Exception):
    """Exception raised when pack cannot be loaded."""
    pass


class PackLoader:
    """Load rule packs from filesystem.

    Infrastructure layer - handles I/O operations for loading packs.
    A pack consists of:
    - pack.yaml: Pack manifest with metadata
    - rules/: Directory containing rule YAML files

    Example directory structure:
        pack_dir/
        ├── pack.yaml
        └── rules/
            └── PI/
                └── pi-001@1.0.0.yaml
    """

    def __init__(self, *, strict: bool = False) -> None:
        """Initialize pack loader.

        Args:
            strict: If True, fail on first error. If False, log warnings and continue.
        """
        self.strict = strict
        self.rule_loader = YAMLLoader(strict=strict)

    def load_pack(self, pack_dir: Path) -> RulePack:
        """Load a complete pack from directory.

        Args:
            pack_dir: Directory containing pack.yaml and rules

        Returns:
            Loaded RulePack with manifest and rules

        Raises:
            FileNotFoundError: If pack.yaml missing
            PackLoadError: If pack is invalid or cannot be loaded
        """
        # Validate pack directory exists
        if not pack_dir.exists():
            raise FileNotFoundError(f"Pack directory not found: {pack_dir}")

        if not pack_dir.is_dir():
            raise PackLoadError(f"Pack path is not a directory: {pack_dir}")

        # Load manifest
        manifest_path = pack_dir / "pack.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Pack manifest not found: {manifest_path}"
            )

        try:
            manifest = self._load_manifest(manifest_path)
        except Exception as e:
            raise PackLoadError(
                f"Failed to load pack manifest from {manifest_path}: {e}"
            ) from e

        # Load all rules referenced in manifest
        rules = []
        load_errors = []

        for pack_rule in manifest.rules:
            rule_path = pack_dir / pack_rule.path

            if not rule_path.exists():
                error_msg = f"Rule file not found: {rule_path} (referenced in manifest)"
                logger.warning(error_msg)
                load_errors.append(error_msg)

                if self.strict:
                    raise PackLoadError(error_msg)
                continue

            try:
                rule = self.rule_loader.load_rule(rule_path)

                # Verify rule matches manifest declaration
                self._validate_rule_matches_manifest(rule, pack_rule, rule_path)

                rules.append(rule)

            except YAMLLoadError as e:
                error_msg = f"Failed to load rule {pack_rule.versioned_id}: {e}"
                logger.warning(error_msg)
                load_errors.append(error_msg)

                if self.strict:
                    raise PackLoadError(error_msg) from e
                continue
            except Exception as e:
                error_msg = f"Unexpected error loading rule {pack_rule.versioned_id}: {e}"
                logger.error(error_msg)
                load_errors.append(error_msg)

                if self.strict:
                    raise PackLoadError(error_msg) from e
                continue

        # Log summary if there were errors in non-strict mode
        if load_errors and not self.strict:
            logger.warning(
                f"Loaded pack '{manifest.versioned_id}' with {len(load_errors)} errors. "
                f"Successfully loaded {len(rules)}/{manifest.rule_count} rules."
            )

        # Create and return pack (will validate rule count matches)
        try:
            return RulePack(manifest=manifest, rules=rules)
        except ValueError as e:
            # In non-strict mode, we may have partial rule loading
            # which will fail RulePack validation
            if not self.strict:
                logger.warning(
                    f"Pack validation failed but continuing in non-strict mode: {e}"
                )
                # Create a modified manifest with actual loaded rules
                loaded_pack_rules = [
                    pr for pr in manifest.rules
                    if any(r.versioned_id == pr.versioned_id for r in rules)
                ]

                # If no rules loaded, create a dummy rule entry to satisfy validation
                if not loaded_pack_rules and not rules:
                    # Return None or raise in strict mode
                    logger.warning("No rules successfully loaded from pack")
                    # Create minimal valid manifest with no rules would fail
                    # So we need to return something or raise
                    raise PackLoadError(
                        "Pack validation failed: No rules successfully loaded"
                    ) from e

                adjusted_manifest = PackManifest(
                    id=manifest.id,
                    version=manifest.version,
                    name=manifest.name,
                    pack_type=manifest.pack_type,
                    schema_version=manifest.schema_version,
                    rules=loaded_pack_rules,
                    metadata=manifest.metadata,
                    signature=manifest.signature,
                    signature_algorithm=manifest.signature_algorithm,
                )
                return RulePack(manifest=adjusted_manifest, rules=rules)
            raise PackLoadError(f"Pack validation failed: {e}") from e

    def _load_manifest(self, manifest_path: Path) -> PackManifest:
        """Load pack manifest from YAML file.

        Args:
            manifest_path: Path to pack.yaml

        Returns:
            Parsed PackManifest

        Raises:
            PackLoadError: If manifest is invalid
        """
        try:
            with open(manifest_path, encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise PackLoadError(
                f"Failed to parse manifest YAML: {e}"
            ) from e
        except Exception as e:
            raise PackLoadError(
                f"Failed to read manifest file: {e}"
            ) from e

        if not isinstance(data, dict):
            raise PackLoadError(
                f"Manifest must be a YAML dictionary, got {type(data)}"
            )

        # Extract pack section
        pack_data = data.get("pack")
        if not pack_data:
            raise PackLoadError(
                "Manifest missing required 'pack' section"
            )

        # Parse pack rules
        pack_rules = []
        rules_data = pack_data.get("rules", [])

        if not rules_data:
            raise PackLoadError("Pack must declare at least one rule")

        for i, rule_data in enumerate(rules_data):
            if not isinstance(rule_data, dict):
                raise PackLoadError(
                    f"Rule entry {i} must be a dictionary, got {type(rule_data)}"
                )

            # Validate required fields
            for field in ["id", "version", "path"]:
                if field not in rule_data:
                    raise PackLoadError(
                        f"Rule entry {i} missing required field: {field}"
                    )

            try:
                pack_rules.append(PackRule(
                    id=rule_data["id"],
                    version=rule_data["version"],
                    path=rule_data["path"],
                ))
            except ValueError as e:
                raise PackLoadError(
                    f"Invalid rule entry {i}: {e}"
                ) from e

        # Parse pack type
        try:
            pack_type = PackType(pack_data.get("type", "CUSTOM"))
        except ValueError as e:
            raise PackLoadError(
                f"Invalid pack type: {pack_data.get('type')}"
            ) from e

        # Create manifest
        try:
            return PackManifest(
                id=pack_data["id"],
                version=pack_data["version"],
                name=pack_data["name"],
                pack_type=pack_type,
                schema_version=pack_data["schema_version"],
                rules=pack_rules,
                metadata=pack_data.get("metadata", {}),
                signature=pack_data.get("signature"),
                signature_algorithm=pack_data.get("signature_algorithm"),
            )
        except KeyError as e:
            raise PackLoadError(
                f"Manifest missing required field: {e}"
            ) from e
        except ValueError as e:
            raise PackLoadError(
                f"Invalid manifest data: {e}"
            ) from e

    def _validate_rule_matches_manifest(
        self,
        rule: Rule,
        pack_rule: PackRule,
        rule_path: Path,
    ) -> None:
        """Validate loaded rule matches manifest declaration.

        Args:
            rule: Loaded Rule object
            pack_rule: PackRule from manifest
            rule_path: Path to rule file (for error messages)

        Raises:
            PackLoadError: If rule doesn't match manifest
        """
        # Check rule ID matches
        if rule.rule_id != pack_rule.id:
            raise PackLoadError(
                f"Rule ID mismatch in {rule_path}: "
                f"manifest declares '{pack_rule.id}' but rule has '{rule.rule_id}'"
            )

        # Check version matches
        if rule.version != pack_rule.version:
            raise PackLoadError(
                f"Rule version mismatch in {rule_path}: "
                f"manifest declares '{pack_rule.version}' but rule has '{rule.version}'"
            )

    def load_packs_from_directory(
        self,
        packs_root: Path,
    ) -> list[RulePack]:
        """Load all packs from a directory.

        Scans for subdirectories containing pack.yaml files.

        Args:
            packs_root: Root directory containing pack subdirectories

        Returns:
            List of successfully loaded packs

        Example:
            packs_root/
            ├── core/v1.0.0/pack.yaml       -> loaded as pack
            ├── community/v2.0.0/pack.yaml  -> loaded as pack
            └── custom/my-rules/pack.yaml   -> loaded as pack
        """
        packs = []

        if not packs_root.exists():
            logger.info(f"Packs root directory does not exist: {packs_root}")
            return packs

        if not packs_root.is_dir():
            logger.warning(f"Packs root path is not a directory: {packs_root}")
            return packs

        # Recursively find all pack.yaml files
        manifest_files = list(packs_root.rglob("pack.yaml"))

        logger.info(f"Found {len(manifest_files)} pack manifests in {packs_root}")

        for manifest_path in manifest_files:
            pack_dir = manifest_path.parent

            try:
                pack = self.load_pack(pack_dir)
                packs.append(pack)
                logger.info(
                    f"Loaded pack: {pack.manifest.versioned_id} "
                    f"with {len(pack.rules)} rules"
                )
            except Exception as e:
                error_msg = f"Failed to load pack from {pack_dir}: {e}"
                logger.warning(error_msg)

                if self.strict:
                    raise PackLoadError(error_msg) from e
                continue

        return packs

    def load_latest_pack(self, type_dir: Path) -> RulePack | None:
        """Load latest version from pack type directory.

        Finds version directories (v1.0.0, v2.0.0, etc.) and loads
        the one with the highest version number.

        Args:
            type_dir: Directory containing versioned pack subdirectories
                     (e.g., ~/.raxe/packs/core/)

        Returns:
            Latest versioned pack, or None if no valid packs found

        Example:
            type_dir/
            ├── v1.0.0/pack.yaml
            ├── v2.0.0/pack.yaml  <- this one loaded
            └── v1.5.0/pack.yaml
        """
        if not type_dir.exists():
            logger.debug(f"Pack type directory does not exist: {type_dir}")
            return None

        if not type_dir.is_dir():
            logger.warning(f"Pack type path is not a directory: {type_dir}")
            return None

        # Find version directories (must start with 'v')
        version_dirs = [
            d for d in type_dir.iterdir()
            if d.is_dir() and d.name.startswith("v")
        ]

        if not version_dirs:
            logger.debug(f"No version directories found in {type_dir}")
            return None

        # Sort by version (reverse to get highest first)
        # Simple string sort works for semver like v1.0.0, v2.0.0
        version_dirs.sort(reverse=True)
        latest_dir = version_dirs[0]

        logger.info(f"Loading latest pack from {latest_dir}")

        try:
            return self.load_pack(latest_dir)
        except Exception as e:
            logger.error(f"Failed to load pack from {latest_dir}: {e}")
            if self.strict:
                raise
            return None
