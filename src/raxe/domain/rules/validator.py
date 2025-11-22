"""Rule validation logic for community submissions.

This module provides comprehensive validation for rule YAML files including:
- Schema validation
- Pattern compilation and safety checks
- Catastrophic backtracking detection
- Field completeness checks
- Test example validation
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

import yaml
from pydantic import ValidationError

from raxe.domain.rules.schema import RuleSchema


@dataclass
class ValidationIssue:
    """A single validation issue.

    Attributes:
        severity: Issue severity (error, warning, info)
        field: Field or pattern where issue was found
        message: Human-readable description of the issue
        suggestion: Optional suggestion for fixing the issue
    """
    severity: str  # 'error', 'warning', 'info'
    field: str
    message: str
    suggestion: str = ""


@dataclass
class ValidationResult:
    """Result of rule validation.

    Attributes:
        valid: Whether the rule passed all validations
        issues: List of validation issues found
        rule_id: Extracted rule ID if available
        warnings_count: Number of warnings
        errors_count: Number of errors
    """
    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    rule_id: str | None = None

    @property
    def warnings_count(self) -> int:
        """Count of warning-level issues."""
        return sum(1 for issue in self.issues if issue.severity == 'warning')

    @property
    def errors_count(self) -> int:
        """Count of error-level issues."""
        return sum(1 for issue in self.issues if issue.severity == 'error')

    @property
    def has_errors(self) -> bool:
        """Whether there are any errors."""
        return self.errors_count > 0


class RuleValidator:
    """Validates rule files for submission.

    Performs comprehensive validation including:
    - YAML syntax validation
    - Schema compliance checking
    - Pattern compilation and safety
    - Catastrophic backtracking detection
    - Field completeness validation
    - Test example validation
    """

    # Known dangerous regex patterns that can cause catastrophic backtracking
    BACKTRACKING_PATTERNS: ClassVar[list] = [
        (r'\(\.\*\)\+', "Nested quantifiers (.*)+"),
        (r'\(\.\+\)\+', "Nested quantifiers (.+)+"),
        (r'\(\.\*\)\*', "Nested quantifiers (.*)* "),
        (r'\(\.\+\)\*', "Nested quantifiers (.+)*"),
        (r'\([^)]*\+\)\+', "Nested quantifiers like (a+)+"),
        (r'\([^)]*\*\)\*', "Nested quantifiers like (a*)*"),
        (r'\([^)]*\)\+\+', "Possessive quantifier without atomic group"),
        (r'\([^)]*\{[^}]*,[^}]*\}\)\+', "Nested quantified groups"),
    ]

    # Minimum requirements for explainability
    MIN_RISK_EXPLANATION_LENGTH = 20
    MIN_REMEDIATION_LENGTH = 20
    MIN_EXAMPLES_SHOULD_MATCH = 5
    MIN_EXAMPLES_SHOULD_NOT_MATCH = 5

    def __init__(self) -> None:
        """Initialize the rule validator."""
        pass

    def validate_file(self, file_path: str | Path) -> ValidationResult:
        """Validate a rule file.

        Args:
            file_path: Path to the rule YAML file

        Returns:
            ValidationResult with all validation issues
        """
        file_path = Path(file_path)
        result = ValidationResult(valid=True)

        # Check file exists
        if not file_path.exists():
            result.valid = False
            result.issues.append(ValidationIssue(
                severity='error',
                field='file',
                message=f"File not found: {file_path}",
                suggestion="Check the file path and ensure the file exists"
            ))
            return result

        # Check file extension
        if file_path.suffix not in ['.yaml', '.yml']:
            result.issues.append(ValidationIssue(
                severity='warning',
                field='file',
                message=f"File has extension '{file_path.suffix}', expected .yaml or .yml",
                suggestion="Rename file to use .yaml or .yml extension"
            ))

        # Load YAML
        try:
            with open(file_path, encoding='utf-8') as f:
                rule_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            result.valid = False
            result.issues.append(ValidationIssue(
                severity='error',
                field='yaml',
                message=f"Invalid YAML syntax: {e}",
                suggestion="Fix YAML syntax errors. Check indentation and special characters."
            ))
            return result
        except Exception as e:
            result.valid = False
            result.issues.append(ValidationIssue(
                severity='error',
                field='file',
                message=f"Failed to read file: {e}",
                suggestion="Ensure file is readable and contains valid UTF-8 text"
            ))
            return result

        # Validate against schema
        try:
            rule_schema = RuleSchema(**rule_data)
            result.rule_id = rule_schema.rule_id
        except ValidationError as e:
            result.valid = False
            for error in e.errors():
                field_path = '.'.join(str(loc) for loc in error['loc'])
                result.issues.append(ValidationIssue(
                    severity='error',
                    field=field_path,
                    message=error['msg'],
                    suggestion=self._get_schema_error_suggestion(error)
                ))
            # If schema validation fails, we can't continue with other checks
            return result
        except Exception as e:
            result.valid = False
            result.issues.append(ValidationIssue(
                severity='error',
                field='schema',
                message=f"Schema validation failed: {e}",
                suggestion="Check that all required fields are present and have correct types"
            ))
            return result

        # Additional validation checks
        self._validate_patterns(rule_schema, result)
        self._validate_examples(rule_schema, result)
        self._validate_explainability(rule_schema, result)
        self._validate_metadata(rule_schema, result)
        self._check_best_practices(rule_schema, result)

        # Update valid flag based on errors
        result.valid = not result.has_errors

        return result

    def _validate_patterns(self, rule_schema: RuleSchema, result: ValidationResult) -> None:
        """Validate regex patterns.

        Args:
            rule_schema: Validated rule schema
            result: ValidationResult to append issues to
        """
        for i, pattern_schema in enumerate(rule_schema.patterns):
            pattern_str = pattern_schema.pattern

            # Check pattern compiles
            try:
                # Convert flags
                flags = 0
                for flag_name in pattern_schema.flags:
                    flag_upper = flag_name.upper()
                    if hasattr(re, flag_upper):
                        flags |= getattr(re, flag_upper)
                    else:
                        result.issues.append(ValidationIssue(
                            severity='error',
                            field=f'patterns[{i}].flags',
                            message=f"Unknown regex flag: {flag_name}",
                            suggestion="Use valid regex flags like IGNORECASE, MULTILINE, DOTALL"
                        ))
                        continue

                _ = re.compile(pattern_str, flags)  # Validate pattern compiles

            except re.error as e:
                result.issues.append(ValidationIssue(
                    severity='error',
                    field=f'patterns[{i}].pattern',
                    message=f"Pattern does not compile: {e}",
                    suggestion="Fix the regex syntax. Test with online regex validators."
                ))
                continue

            # Check for catastrophic backtracking
            backtracking_issues = self._check_catastrophic_backtracking(pattern_str)
            for issue_msg in backtracking_issues:
                result.issues.append(ValidationIssue(
                    severity='error',
                    field=f'patterns[{i}].pattern',
                    message=f"Potential catastrophic backtracking: {issue_msg}",
                    suggestion="Simplify the pattern or use atomic groups to prevent backtracking"
                ))

            # Check pattern timeout
            if pattern_schema.timeout < 1.0:
                result.issues.append(ValidationIssue(
                    severity='warning',
                    field=f'patterns[{i}].timeout',
                    message=f"Timeout {pattern_schema.timeout}s is very short",
                    suggestion="Consider using timeout >= 1.0s to avoid false negatives"
                ))
            elif pattern_schema.timeout > 10.0:
                result.issues.append(ValidationIssue(
                    severity='warning',
                    field=f'patterns[{i}].timeout',
                    message=f"Timeout {pattern_schema.timeout}s is very long",
                    suggestion="Consider optimizing the pattern or reducing timeout to <= 10.0s"
                ))

            # Check pattern length
            if len(pattern_str) > 500:
                result.issues.append(ValidationIssue(
                    severity='warning',
                    field=f'patterns[{i}].pattern',
                    message=f"Pattern is very long ({len(pattern_str)} chars)",
                    suggestion="Consider breaking into multiple simpler patterns"
                ))

    def _check_catastrophic_backtracking(self, pattern: str) -> list[str]:
        """Check for patterns that may cause catastrophic backtracking.

        Args:
            pattern: Regex pattern to check

        Returns:
            List of issue messages (empty if no issues)
        """
        issues = []

        for danger_pattern, description in self.BACKTRACKING_PATTERNS:
            if re.search(danger_pattern, pattern):
                issues.append(description)

        # Additional heuristic checks
        # Count nested quantifiers
        nested_count = len(re.findall(r'\([^)]*[*+][^)]*\)[*+]', pattern))
        if nested_count > 2:
            issues.append(f"Multiple nested quantifiers detected ({nested_count})")

        # Check for alternation with overlapping patterns
        if '|' in pattern:
            alternates = pattern.split('|')
            if len(alternates) > 10:
                issues.append(f"Many alternatives ({len(alternates)}) may slow matching")

        return issues

    def _validate_examples(self, rule_schema: RuleSchema, result: ValidationResult) -> None:
        """Validate test examples.

        Args:
            rule_schema: Validated rule schema
            result: ValidationResult to append issues to
        """
        examples = rule_schema.examples

        # Check minimum examples
        if len(examples.should_match) < self.MIN_EXAMPLES_SHOULD_MATCH:
            result.issues.append(ValidationIssue(
                severity='error',
                field='examples.should_match',
                message=f"Need at least {self.MIN_EXAMPLES_SHOULD_MATCH} positive examples, "
                        f"got {len(examples.should_match)}",
                suggestion=f"Add {self.MIN_EXAMPLES_SHOULD_MATCH - len(examples.should_match)} more examples that should match"
            ))

        if len(examples.should_not_match) < self.MIN_EXAMPLES_SHOULD_NOT_MATCH:
            result.issues.append(ValidationIssue(
                severity='error',
                field='examples.should_not_match',
                message=f"Need at least {self.MIN_EXAMPLES_SHOULD_NOT_MATCH} negative examples, "
                        f"got {len(examples.should_not_match)}",
                suggestion=f"Add {self.MIN_EXAMPLES_SHOULD_NOT_MATCH - len(examples.should_not_match)} more examples that should NOT match"
            ))

        # Check examples are non-empty
        for i, example in enumerate(examples.should_match):
            if not example.strip():
                result.issues.append(ValidationIssue(
                    severity='error',
                    field=f'examples.should_match[{i}]',
                    message="Example is empty or whitespace-only",
                    suggestion="Provide a meaningful test example"
                ))

        for i, example in enumerate(examples.should_not_match):
            if not example.strip():
                result.issues.append(ValidationIssue(
                    severity='error',
                    field=f'examples.should_not_match[{i}]',
                    message="Example is empty or whitespace-only",
                    suggestion="Provide a meaningful test example"
                ))

        # Test patterns against examples
        try:
            patterns = []
            for pattern_schema in rule_schema.patterns:
                flags = 0
                for flag_name in pattern_schema.flags:
                    flag_upper = flag_name.upper()
                    if hasattr(re, flag_upper):
                        flags |= getattr(re, flag_upper)
                patterns.append(re.compile(pattern_schema.pattern, flags))

            # Check should_match examples
            for i, example in enumerate(examples.should_match):
                matched = any(p.search(example) for p in patterns)
                if not matched:
                    result.issues.append(ValidationIssue(
                        severity='error',
                        field=f'examples.should_match[{i}]',
                        message=f"Example does not match any pattern: '{example[:50]}...'",
                        suggestion="Fix the pattern or the example to ensure it matches"
                    ))

            # Check should_not_match examples
            for i, example in enumerate(examples.should_not_match):
                matched = any(p.search(example) for p in patterns)
                if matched:
                    result.issues.append(ValidationIssue(
                        severity='error',
                        field=f'examples.should_not_match[{i}]',
                        message=f"Example incorrectly matches pattern: '{example[:50]}...'",
                        suggestion="Fix the pattern to not match this example, or remove the example"
                    ))

        except Exception as e:
            result.issues.append(ValidationIssue(
                severity='warning',
                field='examples',
                message=f"Could not test examples against patterns: {e}",
                suggestion="Ensure patterns compile correctly"
            ))

    def _validate_explainability(self, rule_schema: RuleSchema, result: ValidationResult) -> None:
        """Validate explainability fields.

        Args:
            rule_schema: Validated rule schema
            result: ValidationResult to append issues to
        """
        # Check risk_explanation
        if not rule_schema.risk_explanation or len(rule_schema.risk_explanation.strip()) < self.MIN_RISK_EXPLANATION_LENGTH:
            result.issues.append(ValidationIssue(
                severity='error',
                field='risk_explanation',
                message=f"risk_explanation must be at least {self.MIN_RISK_EXPLANATION_LENGTH} characters",
                suggestion="Provide a clear explanation of why this pattern is dangerous and what risks it poses"
            ))

        # Check remediation_advice
        if not rule_schema.remediation_advice or len(rule_schema.remediation_advice.strip()) < self.MIN_REMEDIATION_LENGTH:
            result.issues.append(ValidationIssue(
                severity='error',
                field='remediation_advice',
                message=f"remediation_advice must be at least {self.MIN_REMEDIATION_LENGTH} characters",
                suggestion="Provide clear advice on how to fix or mitigate this threat"
            ))

        # Check docs_url format
        if rule_schema.docs_url:
            if not self._is_valid_url(rule_schema.docs_url):
                result.issues.append(ValidationIssue(
                    severity='warning',
                    field='docs_url',
                    message=f"docs_url appears invalid: {rule_schema.docs_url}",
                    suggestion="Provide a valid HTTP/HTTPS URL or leave empty"
                ))
        else:
            result.issues.append(ValidationIssue(
                severity='info',
                field='docs_url',
                message="No documentation URL provided",
                suggestion="Consider adding a docs_url for users to learn more"
            ))

    def _validate_metadata(self, rule_schema: RuleSchema, result: ValidationResult) -> None:
        """Validate metadata fields.

        Args:
            rule_schema: Validated rule schema
            result: ValidationResult to append issues to
        """
        metadata = rule_schema.metadata

        # Check for author
        if 'author' not in metadata or not metadata['author']:
            result.issues.append(ValidationIssue(
                severity='warning',
                field='metadata.author',
                message="No author specified",
                suggestion="Add 'author' field to metadata for attribution"
            ))

        # Check for created date
        if 'created' not in metadata:
            result.issues.append(ValidationIssue(
                severity='info',
                field='metadata.created',
                message="No creation date specified",
                suggestion="Add 'created' field to metadata (YYYY-MM-DD format)"
            ))

        # Validate confidence score
        if rule_schema.confidence < 0.5:
            result.issues.append(ValidationIssue(
                severity='warning',
                field='confidence',
                message=f"Low confidence score: {rule_schema.confidence}",
                suggestion="Consider improving the pattern or providing more evidence for higher confidence"
            ))

        # Check MITRE ATT&CK mappings
        if not rule_schema.mitre_attack:
            result.issues.append(ValidationIssue(
                severity='info',
                field='mitre_attack',
                message="No MITRE ATT&CK techniques mapped",
                suggestion="Consider mapping to relevant MITRE ATT&CK techniques for better threat context"
            ))

    def _check_best_practices(self, rule_schema: RuleSchema, result: ValidationResult) -> None:
        """Check for best practices and style guidelines.

        Args:
            rule_schema: Validated rule schema
            result: ValidationResult to append issues to
        """
        # Check naming convention
        rule_id = rule_schema.rule_id
        if not re.match(r'^[a-z]{2,6}-\d+$', rule_id, re.IGNORECASE):
            result.issues.append(ValidationIssue(
                severity='warning',
                field='rule_id',
                message=f"Rule ID '{rule_id}' doesn't follow convention (family-number)",
                suggestion="Use format like 'pi-001', 'jb-042', etc."
            ))

        # Check description quality
        if len(rule_schema.description) < 30:
            result.issues.append(ValidationIssue(
                severity='warning',
                field='description',
                message="Description is very short",
                suggestion="Provide a more detailed description of what the rule detects"
            ))

        # Check name quality
        if len(rule_schema.name) < 10:
            result.issues.append(ValidationIssue(
                severity='info',
                field='name',
                message="Rule name is very short",
                suggestion="Consider a more descriptive name"
            ))

        # Check for duplicate patterns
        patterns_set = set()
        for i, pattern_schema in enumerate(rule_schema.patterns):
            pattern_key = (pattern_schema.pattern, tuple(pattern_schema.flags))
            if pattern_key in patterns_set:
                result.issues.append(ValidationIssue(
                    severity='warning',
                    field=f'patterns[{i}]',
                    message="Duplicate pattern detected",
                    suggestion="Remove duplicate patterns to improve performance"
                ))
            patterns_set.add(pattern_key)

    def _is_valid_url(self, url: str) -> bool:
        """Check if string is a valid URL.

        Args:
            url: URL string to validate

        Returns:
            True if valid HTTP/HTTPS URL
        """
        try:
            result = urlparse(url)
            return all([result.scheme in ['http', 'https'], result.netloc])
        except Exception:
            return False

    def _get_schema_error_suggestion(self, error: dict[str, Any]) -> str:
        """Get helpful suggestion for schema validation error.

        Args:
            error: Pydantic error dict

        Returns:
            Suggestion string
        """
        error_type = error.get('type', '')

        if 'missing' in error_type:
            return "Add this required field to the YAML file"
        elif 'type_error' in error_type:
            return "Check the field type matches the schema requirements"
        elif 'value_error' in error_type:
            return "Check the field value is in the allowed range/format"
        elif 'extra' in error_type:
            return "Remove this field or check for typos in field name"
        else:
            return "Check the schema documentation for field requirements"
