"""
Schema validation tests for RAXE CE.

Tests all JSON schemas against valid and invalid fixtures to ensure
proper validation behavior.
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

# Schema and fixture base paths
SCHEMAS_DIR = Path(__file__).parent.parent.parent.parent.parent / "schemas"
FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "schemas"


def load_schema(schema_path: str) -> dict:
    """Load a JSON schema from file."""
    full_path = SCHEMAS_DIR / schema_path
    with open(full_path) as f:
        return json.load(f)


def load_fixture(fixture_name: str) -> dict:
    """Load a test fixture from file."""
    full_path = FIXTURES_DIR / fixture_name
    with open(full_path) as f:
        return json.load(f)


def validate_data(data: dict, schema: dict) -> tuple[bool, list[str]]:
    """
    Validate data against schema.

    Returns:
        Tuple of (is_valid, error_messages)
    """
    validator = Draft7Validator(schema)
    errors = []

    for error in validator.iter_errors(data):
        errors.append(f"{'.'.join(str(p) for p in error.path)}: {error.message}")

    return len(errors) == 0, errors


class TestIdentitySchemas:
    """Test identity and multi-tenancy schemas."""

    def test_organization_schema_valid(self):
        """Test organization schema with valid data."""
        schema = load_schema("v1.0.0/identity/organization.json")
        data = load_fixture("valid_organization.json")

        is_valid, errors = validate_data(data, schema)

        assert is_valid, f"Validation failed: {errors}"

    def test_project_schema_valid(self):
        """Test project schema with valid data."""
        schema = load_schema("v1.0.0/identity/project.json")
        data = load_fixture("valid_project.json")

        is_valid, errors = validate_data(data, schema)

        assert is_valid, f"Validation failed: {errors}"


class TestConfigSchemas:
    """Test configuration schemas."""

    def test_scan_config_schema_valid(self):
        """Test scan config schema with valid data."""
        schema = load_schema("v1.0.0/config/scan_config.json")
        data = load_fixture("valid_scan_config.json")

        is_valid, errors = validate_data(data, schema)

        assert is_valid, f"Validation failed: {errors}"


class TestBillingSchemas:
    """Test billing and usage schemas."""

    def test_usage_metrics_schema_valid(self):
        """Test usage metrics schema with valid data."""
        schema = load_schema("v1.0.0/billing/usage_metrics.json")
        data = load_fixture("valid_usage_metrics.json")

        is_valid, errors = validate_data(data, schema)

        assert is_valid, f"Validation failed: {errors}"


def test_all_schemas_are_valid_json_schema():
    """Test that all schema files are valid JSON Schema draft-07."""
    schema_files = list(SCHEMAS_DIR.rglob("*.json"))

    # Exclude non-schema files
    schema_files = [f for f in schema_files if "MIGRATION" not in f.name]

    assert len(schema_files) > 0, "No schema files found"

    for schema_file in schema_files:
        with open(schema_file) as f:
            schema = json.load(f)

        # Verify it has required JSON Schema fields
        assert "$schema" in schema, f"{schema_file.name} missing $schema"

        # Verify it's valid by creating a validator
        try:
            Draft7Validator.check_schema(schema)
        except Exception as e:
            pytest.fail(f"Schema {schema_file.name} is not valid: {e}")
