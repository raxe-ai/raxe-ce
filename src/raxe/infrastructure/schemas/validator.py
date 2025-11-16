"""JSON Schema validation implementation.

Provides validation for all RAXE data structures using JSON Schema draft-07.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft7Validator, RefResolver, ValidationError
    from jsonschema.validators import validator_for  # noqa: F401 - Reserved for future use
except ImportError:
    raise ImportError(
        "jsonschema is required for schema validation. "
        "Install with: pip install jsonschema"
    )


class SchemaValidator:
    """Validates data against RAXE JSON schemas."""

    def __init__(self, schema_root: Path | None = None):
        """Initialize validator with schema directory.

        Args:
            schema_root: Root directory containing schemas.
                        Defaults to /schemas relative to project root.
        """
        if schema_root is None:
            # Find project root (contains pyproject.toml)
            current = Path(__file__).resolve()
            while current.parent != current:
                if (current / "pyproject.toml").exists():
                    schema_root = current / "schemas"
                    break
                current = current.parent
            else:
                raise ValueError("Could not find project root with schemas directory")

        self.schema_root = schema_root
        if not self.schema_root.exists():
            raise ValueError(f"Schema directory does not exist: {self.schema_root}")

        self._validators: dict[str, Draft7Validator] = {}

    @lru_cache(maxsize=32)
    def _load_schema(self, schema_path: str) -> dict[str, Any]:
        """Load a schema from file.

        Args:
            schema_path: Relative path to schema (e.g., 'v1.1.0/rules/rule.json')

        Returns:
            Loaded JSON schema

        Raises:
            FileNotFoundError: If schema file doesn't exist
            json.JSONDecodeError: If schema is invalid JSON
        """
        full_path = self.schema_root / schema_path
        if not full_path.exists():
            raise FileNotFoundError(f"Schema not found: {full_path}")

        with open(full_path) as f:
            return json.load(f)

    def get_validator(self, schema_path: str) -> Draft7Validator:
        """Get or create a validator for a schema.

        Args:
            schema_path: Relative path to schema

        Returns:
            JSON schema validator

        Raises:
            FileNotFoundError: If schema doesn't exist
            ValidationError: If schema itself is invalid
        """
        if schema_path not in self._validators:
            schema = self._load_schema(schema_path)

            # Create resolver for $ref resolution
            schema_uri = f"file://{self.schema_root.resolve()}/"
            resolver = RefResolver(schema_uri, schema)

            # Validate the schema itself
            Draft7Validator.check_schema(schema)

            # Create validator
            self._validators[schema_path] = Draft7Validator(
                schema,
                resolver=resolver
            )

        return self._validators[schema_path]

    def validate(
        self,
        data: Any,
        schema_path: str,
        raise_on_error: bool = True
    ) -> tuple[bool, list[str] | None]:
        """Validate data against a schema.

        Args:
            data: Data to validate
            schema_path: Relative path to schema (e.g., 'v1.1.0/rules/rule.json')
            raise_on_error: If True, raise exception on validation failure

        Returns:
            Tuple of (is_valid, error_messages)
            If valid, returns (True, None)
            If invalid, returns (False, list_of_error_messages)

        Raises:
            ValidationError: If raise_on_error=True and validation fails
            FileNotFoundError: If schema doesn't exist
        """
        validator = self.get_validator(schema_path)

        errors = list(validator.iter_errors(data))

        if errors:
            error_messages = [
                f"{'.'.join(str(p) for p in error.path)}: {error.message}"
                if error.path else error.message
                for error in errors
            ]

            if raise_on_error:
                raise ValidationError(
                    f"Validation failed: {'; '.join(error_messages)}"
                )

            return False, error_messages

        return True, None

    def validate_rule(self, rule_data: dict[str, Any]) -> tuple[bool, list[str] | None]:
        """Validate a rule against the v1.1.0 schema.

        Args:
            rule_data: Rule data to validate

        Returns:
            Validation result tuple
        """
        return self.validate(rule_data, "v1.1.0/rules/rule.json", raise_on_error=False)

    def validate_policy(self, policy_data: dict[str, Any]) -> tuple[bool, list[str] | None]:
        """Validate a policy against the v1.0.0 schema.

        Args:
            policy_data: Policy data to validate

        Returns:
            Validation result tuple
        """
        return self.validate(policy_data, "v1.0.0/policies/policy.json", raise_on_error=False)

    def validate_scan_request(self, request_data: dict[str, Any]) -> tuple[bool, list[str] | None]:
        """Validate a scan API request.

        Args:
            request_data: Request data to validate

        Returns:
            Validation result tuple
        """
        return self.validate(request_data, "v1.0.0/api/scan_request.json", raise_on_error=False)

    def validate_scan_response(self, response_data: dict[str, Any]) -> tuple[bool, list[str] | None]:
        """Validate a scan API response.

        Args:
            response_data: Response data to validate

        Returns:
            Validation result tuple
        """
        return self.validate(response_data, "v1.0.0/api/scan_response.json", raise_on_error=False)

    def validate_scan_event(self, event_data: dict[str, Any]) -> tuple[bool, list[str] | None]:
        """Validate a scan telemetry event.

        Args:
            event_data: Event data to validate

        Returns:
            Validation result tuple
        """
        return self.validate(event_data, "v2.1.0/events/scan_performed.json", raise_on_error=False)

    def validate_l2_prediction(self, prediction_data: dict[str, Any]) -> tuple[bool, list[str] | None]:
        """Validate L2 ML prediction output.

        Args:
            prediction_data: Prediction data to validate

        Returns:
            Validation result tuple
        """
        return self.validate(prediction_data, "v1.2.0/ml/l2_prediction.json", raise_on_error=False)


# Global validator instance
_validator: SchemaValidator | None = None


def get_validator() -> SchemaValidator:
    """Get the global schema validator instance.

    Returns:
        SchemaValidator instance

    Raises:
        ValueError: If schemas directory not found
    """
    global _validator
    if _validator is None:
        _validator = SchemaValidator()
    return _validator


def validate_data(
    data: Any,
    schema_path: str,
    raise_on_error: bool = True
) -> tuple[bool, list[str] | None]:
    """Convenience function to validate data against a schema.

    Args:
        data: Data to validate
        schema_path: Relative path to schema
        raise_on_error: Whether to raise on validation failure

    Returns:
        Validation result tuple

    Raises:
        ValidationError: If raise_on_error=True and validation fails
    """
    return get_validator().validate(data, schema_path, raise_on_error)