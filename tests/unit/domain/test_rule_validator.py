"""Tests for rule validation logic."""
import tempfile
from pathlib import Path

import pytest
import yaml

from raxe.domain.rules.validator import RuleValidator, ValidationIssue, ValidationResult


@pytest.fixture
def validator():
    """Create a RuleValidator instance."""
    return RuleValidator()


@pytest.fixture
def valid_rule_data():
    """Create valid rule data for testing."""
    return {
        "version": "1.0.0",
        "rule_id": "test-001",
        "family": "CUSTOM",
        "sub_family": "test_category",
        "name": "Test Rule for Validation",
        "description": "This is a test rule for validation testing purposes",
        "severity": "medium",
        "confidence": 0.75,
        "patterns": [
            {
                "pattern": r"\btest\s+pattern\b",
                "flags": ["IGNORECASE"],
                "timeout": 5.0,
            }
        ],
        "examples": {
            "should_match": [
                "test pattern example 1",
                "test pattern example 2",
                "test pattern example 3",
                "test pattern example 4",
                "test pattern example 5",
            ],
            "should_not_match": [
                "benign example 1",
                "benign example 2",
                "benign example 3",
                "benign example 4",
                "benign example 5",
            ],
        },
        "metrics": {
            "precision": None,
            "recall": None,
            "f1_score": None,
            "last_evaluated": None,
        },
        "mitre_attack": ["T1059"],
        "metadata": {
            "created": "2025-11-17",
            "author": "test-author",
        },
        "risk_explanation": "This is a test risk explanation that is long enough to pass validation requirements.",
        "remediation_advice": "This is test remediation advice that is long enough to pass validation requirements.",
        "docs_url": "https://example.com/docs",
    }


@pytest.fixture
def temp_rule_file(valid_rule_data):
    """Create a temporary rule file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(valid_rule_data, f)
        return f.name


class TestValidationResult:
    """Tests for ValidationResult class."""

    def test_validation_result_initialization(self):
        """Test ValidationResult initialization."""
        result = ValidationResult(valid=True)
        assert result.valid is True
        assert result.issues == []
        assert result.rule_id is None

    def test_warnings_count(self):
        """Test warnings_count property."""
        result = ValidationResult(valid=True)
        result.issues = [
            ValidationIssue('warning', 'field1', 'msg1'),
            ValidationIssue('warning', 'field2', 'msg2'),
            ValidationIssue('error', 'field3', 'msg3'),
        ]
        assert result.warnings_count == 2

    def test_errors_count(self):
        """Test errors_count property."""
        result = ValidationResult(valid=False)
        result.issues = [
            ValidationIssue('error', 'field1', 'msg1'),
            ValidationIssue('error', 'field2', 'msg2'),
            ValidationIssue('warning', 'field3', 'msg3'),
        ]
        assert result.errors_count == 2

    def test_has_errors(self):
        """Test has_errors property."""
        result = ValidationResult(valid=True)
        assert not result.has_errors

        result.issues = [ValidationIssue('error', 'field1', 'msg1')]
        assert result.has_errors


class TestRuleValidator:
    """Tests for RuleValidator class."""

    def test_validate_file_not_found(self, validator):
        """Test validation of non-existent file."""
        result = validator.validate_file("nonexistent.yaml")
        assert not result.valid
        assert result.errors_count == 1
        assert result.issues[0].field == 'file'
        assert 'not found' in result.issues[0].message.lower()

    def test_validate_file_invalid_extension(self, validator, temp_rule_file):
        """Test validation warns about non-yaml extension."""
        # Rename to .txt
        txt_file = temp_rule_file.replace('.yaml', '.txt')
        Path(temp_rule_file).rename(txt_file)

        result = validator.validate_file(txt_file)
        # Should have warning about extension
        warnings = [i for i in result.issues if i.severity == 'warning' and i.field == 'file']
        assert len(warnings) > 0

    def test_validate_file_invalid_yaml(self, validator):
        """Test validation of file with invalid YAML syntax."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: syntax:\n  - broken\n  indentation")
            f.flush()

            result = validator.validate_file(f.name)
            assert not result.valid
            assert result.errors_count >= 1
            assert any('yaml' in i.message.lower() for i in result.issues)

    def test_validate_file_valid_rule(self, validator, temp_rule_file):
        """Test validation of valid rule file."""
        result = validator.validate_file(temp_rule_file)

        # Should be valid (possibly with warnings/info)
        assert result.valid or result.errors_count == 0
        assert result.rule_id == 'test-001'

    def test_validate_missing_required_field(self, validator, valid_rule_data):
        """Test validation fails when required field is missing."""
        del valid_rule_data['name']

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            assert not result.valid
            assert result.errors_count >= 1
            assert any('name' in i.field for i in result.issues)

    def test_validate_invalid_severity(self, validator, valid_rule_data):
        """Test validation fails with invalid severity."""
        valid_rule_data['severity'] = 'super-critical'  # Invalid

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            assert not result.valid
            assert any('severity' in i.field.lower() for i in result.issues)

    def test_validate_invalid_confidence(self, validator, valid_rule_data):
        """Test validation fails with invalid confidence score."""
        valid_rule_data['confidence'] = 1.5  # Out of range

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            assert not result.valid
            assert any('confidence' in i.field.lower() for i in result.issues)

    def test_check_catastrophic_backtracking(self, validator):
        """Test catastrophic backtracking detection."""
        # Known dangerous patterns
        dangerous = [
            "(a+)+",
            "(.*)*",
            "(.+)+",
            "(a*)*",
        ]

        for pattern in dangerous:
            issues = validator._check_catastrophic_backtracking(pattern)
            assert len(issues) > 0, f"Should detect backtracking in: {pattern}"

        # Safe patterns
        safe = [
            "a+",
            ".*",
            r"\btest\b",
            r"(?:foo|bar)+",
        ]

        for pattern in safe:
            issues = validator._check_catastrophic_backtracking(pattern)
            # Should have no or minimal issues
            assert len(issues) < 2, f"Should not flag safe pattern: {pattern}"

    def test_validate_pattern_compilation(self, validator, valid_rule_data):
        """Test validation of pattern compilation."""
        # Invalid regex
        valid_rule_data['patterns'][0]['pattern'] = r"[invalid"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            assert not result.valid
            assert any('pattern' in i.field.lower() for i in result.issues)
            assert any('compile' in i.message.lower() for i in result.issues)

    def test_validate_examples_minimum_count(self, validator, valid_rule_data):
        """Test validation requires minimum number of examples."""
        # Too few positive examples
        valid_rule_data['examples']['should_match'] = ["only one"]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            assert not result.valid
            assert any('should_match' in i.field for i in result.issues)
            assert any('at least' in i.message.lower() for i in result.issues)

    def test_validate_examples_match_patterns(self, validator, valid_rule_data):
        """Test validation checks examples match patterns."""
        # Add a should_match example that doesn't actually match
        valid_rule_data['examples']['should_match'].append("this will not match at all")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            # Should have an error about the example not matching
            errors = [i for i in result.issues if 'does not match' in i.message.lower()]
            assert len(errors) > 0

    def test_validate_examples_should_not_match(self, validator, valid_rule_data):
        """Test validation checks should_not_match examples don't match."""
        # Add a should_not_match example that actually matches
        valid_rule_data['examples']['should_not_match'].append("test pattern this matches")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            # Should have an error about the example matching
            errors = [i for i in result.issues if 'incorrectly matches' in i.message.lower()]
            assert len(errors) > 0

    def test_validate_explainability_fields(self, validator, valid_rule_data):
        """Test validation of explainability fields."""
        # Too short risk_explanation
        valid_rule_data['risk_explanation'] = "Too short"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            assert not result.valid
            errors = [i for i in result.issues if 'risk_explanation' in i.field]
            assert len(errors) > 0

    def test_validate_docs_url(self, validator, valid_rule_data):
        """Test validation of documentation URL."""
        # Invalid URL
        valid_rule_data['docs_url'] = "not-a-valid-url"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            # Should have a warning about invalid URL
            warnings = [i for i in result.issues if 'docs_url' in i.field and i.severity == 'warning']
            assert len(warnings) > 0

    def test_validate_metadata_author(self, validator, valid_rule_data):
        """Test validation checks for author metadata."""
        del valid_rule_data['metadata']['author']

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            # Should have a warning about missing author
            warnings = [i for i in result.issues if 'author' in i.field.lower()]
            assert len(warnings) > 0

    def test_validate_low_confidence(self, validator, valid_rule_data):
        """Test validation warns about low confidence."""
        valid_rule_data['confidence'] = 0.3  # Low confidence

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            # Should have a warning about low confidence
            warnings = [i for i in result.issues if 'confidence' in i.field and i.severity == 'warning']
            assert len(warnings) > 0

    def test_validate_rule_id_format(self, validator, valid_rule_data):
        """Test validation of rule ID format."""
        valid_rule_data['rule_id'] = "INVALID_FORMAT_123"  # Wrong format

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            # Should have a warning about rule ID format
            warnings = [i for i in result.issues if 'rule_id' in i.field and 'convention' in i.message.lower()]
            assert len(warnings) > 0

    def test_validate_duplicate_patterns(self, validator, valid_rule_data):
        """Test validation detects duplicate patterns."""
        # Add duplicate pattern
        valid_rule_data['patterns'].append(valid_rule_data['patterns'][0].copy())

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            # Should have a warning about duplicate
            warnings = [i for i in result.issues if 'duplicate' in i.message.lower()]
            assert len(warnings) > 0

    def test_is_valid_url(self, validator):
        """Test URL validation helper."""
        valid_urls = [
            "https://example.com",
            "http://example.com/path",
            "https://docs.example.com/page?query=value",
        ]

        for url in valid_urls:
            assert validator._is_valid_url(url), f"Should accept valid URL: {url}"

        invalid_urls = [
            "not-a-url",
            "ftp://example.com",  # Not http/https
            "example.com",  # No scheme
            "",
        ]

        for url in invalid_urls:
            assert not validator._is_valid_url(url), f"Should reject invalid URL: {url}"

    def test_get_schema_error_suggestion(self, validator):
        """Test schema error suggestion helper."""
        error_types = [
            ({'type': 'missing'}, 'Add this required field'),
            ({'type': 'type_error'}, 'Check the field type'),
            ({'type': 'value_error'}, 'Check the field value'),
            ({'type': 'extra'}, 'Remove this field'),
            ({'type': 'unknown'}, 'Check the schema'),
        ]

        for error, expected_word in error_types:
            suggestion = validator._get_schema_error_suggestion(error)
            assert expected_word.lower() in suggestion.lower()

    def test_validate_pattern_timeout(self, validator, valid_rule_data):
        """Test validation of pattern timeout values."""
        # Very short timeout
        valid_rule_data['patterns'][0]['timeout'] = 0.5

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            # Should have a warning about short timeout
            warnings = [i for i in result.issues if 'timeout' in i.field and 'short' in i.message.lower()]
            assert len(warnings) > 0

        # Very long timeout
        valid_rule_data['patterns'][0]['timeout'] = 15.0

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            # Should have a warning about long timeout
            warnings = [i for i in result.issues if 'timeout' in i.field and 'long' in i.message.lower()]
            assert len(warnings) > 0

    def test_validate_empty_examples(self, validator, valid_rule_data):
        """Test validation detects empty examples."""
        # Add empty example
        valid_rule_data['examples']['should_match'].append("   ")  # Whitespace only

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            # Should have error about empty example
            errors = [i for i in result.issues if 'empty' in i.message.lower()]
            assert len(errors) > 0

    def test_validate_mitre_attack_format(self, validator, valid_rule_data):
        """Test validation of MITRE ATT&CK technique IDs."""
        # Invalid format (doesn't start with T)
        valid_rule_data['mitre_attack'] = ["INVALID123"]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)
            assert not result.valid
            errors = [i for i in result.issues if 'mitre' in i.message.lower() or 'mitre_attack' in i.field.lower()]
            assert len(errors) > 0


class TestValidationIntegration:
    """Integration tests for full validation workflow."""

    def test_complete_validation_workflow(self, validator, valid_rule_data):
        """Test complete validation workflow with valid rule."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)

            # Should be valid or only have warnings/info
            assert not result.has_errors
            assert result.rule_id == 'test-001'
            assert result.valid or result.errors_count == 0

    def test_validation_with_multiple_errors(self, validator, valid_rule_data):
        """Test validation with multiple errors."""
        # Introduce multiple errors
        valid_rule_data['severity'] = 'invalid'
        valid_rule_data['confidence'] = 2.0
        valid_rule_data['patterns'][0]['pattern'] = '[invalid'
        valid_rule_data['risk_explanation'] = 'short'

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)

            # Should have multiple errors (schema validation catches severity and confidence)
            assert not result.valid
            assert result.errors_count >= 2

    def test_validation_result_has_suggestions(self, validator, valid_rule_data):
        """Test that validation results include helpful suggestions."""
        # Introduce an error
        valid_rule_data['risk_explanation'] = 'too short'

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_rule_data, f)
            f.flush()

            result = validator.validate_file(f.name)

            # Should have issues with suggestions
            issues_with_suggestions = [i for i in result.issues if i.suggestion]
            assert len(issues_with_suggestions) > 0
