"""Custom rule loader - infrastructure layer.

Handles I/O operations for loading custom rules from YAML files.
"""
import logging
from pathlib import Path

import yaml

from raxe.domain.rules.custom import CustomRuleBuilder, CustomRuleValidator
from raxe.domain.rules.models import Rule

logger = logging.getLogger(__name__)


class CustomRuleLoader:
    """Load custom rules from YAML files.

    Infrastructure layer - handles file I/O.
    """

    def __init__(self, custom_rules_dir: Path | str | None = None):
        """Initialize loader.

        Args:
            custom_rules_dir: Directory containing custom rule YAML files
                             Defaults to ~/.raxe/custom_rules/
        """
        if custom_rules_dir is None:
            self.custom_rules_dir = Path.home() / ".raxe" / "custom_rules"
        else:
            self.custom_rules_dir = Path(custom_rules_dir)

        # Create directory if it doesn't exist
        self.custom_rules_dir.mkdir(parents=True, exist_ok=True)

    def load_rule_from_file(self, file_path: Path | str) -> Rule:
        """Load a single rule from a YAML file.

        Args:
            file_path: Path to YAML file

        Returns:
            Rule object

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is invalid or rule is malformed
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Rule file not found: {file_path}")

        try:
            with open(file_path) as f:
                rule_dict = yaml.safe_load(f)

            if not rule_dict:
                raise ValueError(f"Empty rule file: {file_path}")

            # Validate
            is_valid, errors = CustomRuleValidator.validate_rule_dict(rule_dict)
            if not is_valid:
                raise ValueError(f"Invalid rule in {file_path}: {', '.join(errors)}")

            # Build rule
            rule = CustomRuleBuilder.from_dict(rule_dict)

            # Test against examples
            examples_passed, failures = CustomRuleValidator.test_rule_examples(rule)
            if not examples_passed:
                logger.warning(
                    f"Rule {rule.rule_id} examples failed: {', '.join(failures[:3])}"
                )

            logger.info(f"Loaded custom rule: {rule.rule_id}@{rule.version} from {file_path}")
            return rule

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {file_path}: {e}") from e

    def load_all_rules(self) -> list[Rule]:
        """Load all custom rules from the custom rules directory.

        Returns:
            List of Rule objects (may be empty)
        """
        rules = []

        if not self.custom_rules_dir.exists():
            logger.debug(f"Custom rules directory doesn't exist: {self.custom_rules_dir}")
            return rules

        for yaml_file in self.custom_rules_dir.glob("*.yaml"):
            try:
                rule = self.load_rule_from_file(yaml_file)
                rules.append(rule)
            except Exception as e:
                logger.error(f"Failed to load custom rule from {yaml_file}: {e}")
                # Continue loading other rules
                continue

        logger.info(f"Loaded {len(rules)} custom rules from {self.custom_rules_dir}")
        return rules

    def save_rule_to_file(self, rule: Rule, file_path: Path | str | None = None) -> Path:
        """Save a rule to a YAML file.

        Args:
            rule: Rule to save
            file_path: Optional path to save to. If None, uses default location.

        Returns:
            Path where rule was saved

        Raises:
            ValueError: If rule is invalid
        """
        if file_path is None:
            file_path = self.custom_rules_dir / f"{rule.rule_id}.yaml"
        else:
            file_path = Path(file_path)

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict
        rule_dict = CustomRuleBuilder.to_dict(rule)

        # Write to file
        with open(file_path, "w") as f:
            yaml.dump(rule_dict, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Saved custom rule {rule.rule_id} to {file_path}")
        return file_path

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a custom rule file.

        Args:
            rule_id: ID of rule to delete

        Returns:
            True if deleted, False if not found
        """
        rule_file = self.custom_rules_dir / f"{rule_id}.yaml"

        if rule_file.exists():
            rule_file.unlink()
            logger.info(f"Deleted custom rule: {rule_id}")
            return True
        else:
            logger.warning(f"Rule file not found for deletion: {rule_id}")
            return False

    def validate_file(self, file_path: Path | str) -> tuple[bool, list[str]]:
        """Validate a rule file without loading it.

        Args:
            file_path: Path to YAML file

        Returns:
            Tuple of (is_valid, list of errors)
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return False, [f"File not found: {file_path}"]

        try:
            with open(file_path) as f:
                rule_dict = yaml.safe_load(f)

            if not rule_dict:
                return False, ["Empty YAML file"]

            # Validate structure
            is_valid, errors = CustomRuleValidator.validate_rule_dict(rule_dict)

            if is_valid:
                # Also try to build and test
                rule = CustomRuleBuilder.from_dict(rule_dict)
                examples_passed, example_errors = CustomRuleValidator.test_rule_examples(rule)

                if not examples_passed:
                    # Warn about example failures but don't fail validation
                    errors.extend([f"Example test failed: {e}" for e in example_errors])

            return is_valid, errors

        except yaml.YAMLError as e:
            return False, [f"Invalid YAML: {e}"]
        except Exception as e:
            return False, [f"Validation error: {e}"]

    def list_custom_rules(self) -> list[dict[str, str]]:
        """List all custom rule files.

        Returns:
            List of dicts with rule metadata (id, name, version, file_path)
        """
        rules_info = []

        if not self.custom_rules_dir.exists():
            return rules_info

        for yaml_file in self.custom_rules_dir.glob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    rule_dict = yaml.safe_load(f)

                if rule_dict:
                    rules_info.append({
                        "id": rule_dict.get("id", "unknown"),
                        "name": rule_dict.get("name", "unknown"),
                        "version": rule_dict.get("version", "0.0.1"),
                        "file_path": str(yaml_file),
                    })
            except Exception as e:
                logger.debug(f"Could not read metadata from {yaml_file}: {e}")
                continue

        return rules_info
