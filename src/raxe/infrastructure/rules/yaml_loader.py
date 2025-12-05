"""YAML rule loader for RAXE CE.

Loads and validates rule definitions from YAML files matching
the v1.1 specification. Infrastructure layer - handles file I/O.
"""
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from raxe.domain.rules.models import (
    Pattern,
    Rule,
    RuleExamples,
    RuleFamily,
    RuleMetrics,
    Severity,
)
from raxe.domain.rules.schema import RuleSchema
from raxe.infrastructure.rules.versioning import VersionChecker, VersionError


class YAMLLoadError(Exception):
    """Exception raised when YAML file cannot be loaded or validated."""
    pass


class YAMLLoader:
    """Load threat detection rules from YAML files.

    Handles file I/O and conversion from YAML to domain Rule objects.
    Validates against schema and ensures version compatibility.
    """

    def __init__(
        self,
        *,
        version_checker: VersionChecker | None = None,
        strict: bool = True,
    ) -> None:
        """Initialize YAML loader.

        Args:
            version_checker: Version compatibility checker (uses default if None)
            strict: If True, raise on any validation warnings
        """
        self.version_checker = version_checker or VersionChecker()
        self.strict = strict

    def load_rule(self, path: Path) -> Rule:
        """Load a single rule from YAML file.

        Args:
            path: Path to YAML file

        Returns:
            Validated Rule domain object

        Raises:
            FileNotFoundError: If file doesn't exist
            YAMLLoadError: If YAML is malformed or validation fails
            VersionError: If schema version is incompatible
        """
        # 1. Validate path exists
        if not path.exists():
            raise FileNotFoundError(f"Rule file not found: {path}")

        if not path.is_file():
            raise YAMLLoadError(f"Path is not a file: {path}")

        # 2. Read and parse YAML
        try:
            with open(path, encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise YAMLLoadError(f"Failed to parse YAML from {path}: {e}") from e
        except Exception as e:
            raise YAMLLoadError(f"Failed to read file {path}: {e}") from e

        if data is None:
            raise YAMLLoadError(f"Empty YAML file: {path}")

        if not isinstance(data, dict):
            raise YAMLLoadError(f"YAML root must be a dictionary, got {type(data)}: {path}")

        # 3. Check version compatibility
        version = data.get('version')
        if not version:
            raise YAMLLoadError(f"Missing required 'version' field in {path}")

        try:
            self.version_checker.check_compatibility(str(version))
        except VersionError as e:
            raise YAMLLoadError(f"Version incompatibility in {path}: {e}") from e

        # 4. Validate against schema
        try:
            schema = RuleSchema(**data)
        except ValidationError as e:
            raise YAMLLoadError(
                f"Validation failed for {path}:\n{self._format_validation_error(e)}"
            ) from e

        # 5. Convert to domain Rule object
        try:
            rule = self._schema_to_domain(schema)
        except Exception as e:
            raise YAMLLoadError(f"Failed to convert rule from {path}: {e}") from e

        return rule

    def load_rules_from_directory(
        self,
        directory: Path,
        *,
        recursive: bool = False,
        pattern: str = "*.yaml",
    ) -> list[Rule]:
        """Load all YAML rules from directory.

        Args:
            directory: Directory containing rule files
            recursive: If True, search subdirectories recursively
            pattern: Glob pattern for rule files (default: *.yaml)

        Returns:
            List of validated Rule objects

        Raises:
            NotADirectoryError: If directory doesn't exist or isn't a directory
            YAMLLoadError: If any rule file fails to load
        """
        if not directory.exists():
            raise NotADirectoryError(f"Directory not found: {directory}")

        if not directory.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {directory}")

        # Find all matching files
        if recursive:
            rule_files = list(directory.rglob(pattern))
        else:
            rule_files = list(directory.glob(pattern))

        if not rule_files:
            return []

        # Load each rule file
        rules = []
        errors = []

        for rule_file in sorted(rule_files):
            try:
                rule = self.load_rule(rule_file)
                rules.append(rule)
            except Exception as e:
                error_msg = f"{rule_file.name}: {e}"
                errors.append(error_msg)
                if self.strict:
                    raise YAMLLoadError(
                        "Failed to load rules. Errors:\n" + "\n".join(errors)
                    ) from e

        if errors and self.strict:
            raise YAMLLoadError(
                f"Failed to load {len(errors)} rule file(s):\n" + "\n".join(errors)
            )

        return rules

    def _schema_to_domain(self, schema: RuleSchema) -> Rule:
        """Convert Pydantic schema to domain Rule object.

        Args:
            schema: Validated RuleSchema object

        Returns:
            Domain Rule object

        Raises:
            ValueError: If conversion fails
        """
        # Convert patterns
        patterns = [
            Pattern(
                pattern=p.pattern,
                flags=p.flags,
                timeout=p.timeout,
            )
            for p in schema.patterns
        ]

        # Convert examples
        examples = RuleExamples(
            should_match=schema.examples.should_match,
            should_not_match=schema.examples.should_not_match,
        )

        # Convert metrics
        metrics = RuleMetrics(
            precision=schema.metrics.precision,
            recall=schema.metrics.recall,
            f1_score=schema.metrics.f1_score,
            last_evaluated=schema.metrics.last_evaluated,
            counts_30d=schema.metrics.counts_30d,
        )

        # Convert enums
        try:
            severity = Severity(schema.severity)
        except ValueError as e:
            raise ValueError(f"Invalid severity value: {schema.severity}") from e

        try:
            family = RuleFamily(schema.family)
        except ValueError as e:
            raise ValueError(f"Invalid family value: {schema.family}") from e

        # Create Rule
        return Rule(
            rule_id=schema.rule_id,
            version=schema.version,
            family=family,
            sub_family=schema.sub_family,
            name=schema.name,
            description=schema.description,
            severity=severity,
            confidence=schema.confidence,
            patterns=patterns,
            examples=examples,
            metrics=metrics,
            mitre_attack=schema.mitre_attack,
            metadata=schema.metadata,
            rule_hash=schema.rule_hash,
            risk_explanation=schema.risk_explanation,
            remediation_advice=schema.remediation_advice,
            docs_url=schema.docs_url,
        )

    @staticmethod
    def _format_validation_error(error: ValidationError) -> str:
        """Format Pydantic validation error for user-friendly output.

        Args:
            error: Pydantic ValidationError

        Returns:
            Formatted error message
        """
        messages = []
        for err in error.errors():
            loc = " -> ".join(str(item) for item in err['loc'])
            msg = err['msg']
            messages.append(f"  {loc}: {msg}")
        return "\n".join(messages)

    def validate_yaml_structure(self, data: dict[str, Any]) -> None:
        """Validate YAML structure matches v1.1 spec.

        Args:
            data: Parsed YAML data

        Raises:
            YAMLLoadError: If validation fails
        """
        # Check for required top-level fields
        required_fields = {
            'version', 'rule_id', 'family', 'sub_family', 'name',
            'description', 'severity', 'confidence', 'patterns',
            'examples', 'metrics'
        }

        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            raise YAMLLoadError(
                f"Missing required fields: {', '.join(sorted(missing_fields))}"
            )

        # Validate using Pydantic schema
        try:
            RuleSchema(**data)
        except ValidationError as e:
            raise YAMLLoadError(
                f"YAML structure validation failed:\n{self._format_validation_error(e)}"
            ) from e
