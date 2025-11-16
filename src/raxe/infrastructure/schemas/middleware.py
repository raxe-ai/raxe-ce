"""Schema validation middleware for API boundaries.

This module provides middleware to validate requests and responses against
our JSON schemas at API boundaries.
"""
import logging
from collections.abc import Callable
from functools import wraps
from pathlib import Path

from jsonschema import ValidationError as SchemaValidationError

from raxe.infrastructure.schemas.validator import get_validator

logger = logging.getLogger(__name__)


class SchemaValidationMiddleware:
    """Middleware for validating data against JSON schemas."""

    def __init__(self, schema_dir: Path | None = None):
        """Initialize middleware.

        Args:
            schema_dir: Directory containing JSON schemas
        """
        # Use the same schemas directory as the validator
        # Path from this file: middleware.py -> schemas -> infrastructure -> raxe -> src -> project_root
        self.schema_dir = schema_dir or Path(__file__).parent.parent.parent.parent.parent / "schemas"
        self._validators = {}
        self._validator_instance = None
        logger.info(f"Schema validation middleware initialized with dir: {self.schema_dir}")

    def validate_request(self, schema_name: str):
        """Decorator to validate incoming request data.

        Args:
            schema_name: Name of the schema to validate against

        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Extract request data (first positional arg or 'data' kwarg)
                if args:
                    data = args[0]
                elif 'data' in kwargs:
                    data = kwargs['data']
                else:
                    logger.warning(f"No data to validate for {func.__name__}")
                    return func(*args, **kwargs)

                # Validate against schema
                try:
                    validator = self._get_validator(schema_name)
                    validator.validate(data)
                    logger.debug(f"Request validation passed for {schema_name}")
                except SchemaValidationError as e:
                    logger.error(f"Request validation failed: {e}")
                    raise ValueError(f"Invalid request: {e}") from e

                return func(*args, **kwargs)
            return wrapper
        return decorator

    def validate_response(self, schema_name: str):
        """Decorator to validate outgoing response data.

        Args:
            schema_name: Name of the schema to validate against

        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                result = func(*args, **kwargs)

                # Handle dict/object responses
                if hasattr(result, 'to_dict'):
                    data = result.to_dict()
                elif isinstance(result, dict):
                    data = result
                else:
                    logger.warning(f"Cannot validate non-dict response from {func.__name__}")
                    return result

                # Validate against schema
                try:
                    validator = self._get_validator(schema_name)
                    validator.validate(data)
                    logger.debug(f"Response validation passed for {schema_name}")
                except SchemaValidationError as e:
                    logger.error(f"Response validation failed: {e}")
                    # Log but don't block in production
                    # In development, you might want to raise
                    # raise RuntimeError(f"Invalid response: {e}") from e

                return result
            return wrapper
        return decorator

    def validate_telemetry(self, event_data: dict) -> bool:
        """Validate telemetry event before queueing.

        Args:
            event_data: Telemetry event data

        Returns:
            True if valid, False otherwise
        """
        try:
            # Determine event type
            event_type = event_data.get("event_type", "scan_performed")

            # Map to schema (using versioned paths)
            schema_map = {
                "scan_performed": "v2.1.0/events/scan_performed",
                "rule_hit": "v2.1.0/events/rule_hit",
                "ml_prediction": "v1.2.0/ml/l2_prediction",
            }

            schema_name = schema_map.get(event_type)
            if not schema_name:
                logger.warning(f"Unknown event type: {event_type}")
                return False

            # Validate
            validator = self._get_validator(schema_name)
            validator.validate(event_data)

            logger.debug(f"Telemetry validation passed for {event_type}")
            return True

        except SchemaValidationError as e:
            logger.warning(f"Telemetry validation failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error validating telemetry: {e}")
            return False

    def validate_scan_request(self, request_data: dict) -> dict:
        """Validate and normalize scan request.

        Args:
            request_data: Incoming scan request

        Returns:
            Normalized request data

        Raises:
            ValueError: If validation fails
        """
        try:
            validator = self._get_validator("v1.0.0/config/scan_config")

            # Apply defaults
            normalized = {
                "enabled_layers": request_data.get("enabled_layers", ["l1", "l2"]),
                "timeout_ms": request_data.get("timeout_ms", 1000),
                "max_text_length": request_data.get("max_text_length", 100000),
                "performance_mode": request_data.get("performance_mode", "balanced"),
                "telemetry_enabled": request_data.get("telemetry_enabled", True),
                "policy_enforcement": request_data.get("policy_enforcement", "enforce"),
                "cache_ttl_seconds": request_data.get("cache_ttl_seconds", 300),
            }

            # Add any extra fields
            for key, value in request_data.items():
                if key not in normalized:
                    normalized[key] = value

            # Validate
            validator.validate(normalized)

            return normalized

        except SchemaValidationError as e:
            raise ValueError(f"Invalid scan configuration: {e}") from e

    def validate_ml_output(self, ml_result: dict) -> bool:
        """Validate ML model output.

        Args:
            ml_result: ML prediction result

        Returns:
            True if valid, False otherwise
        """
        try:
            validator = self._get_validator("v1.2.0/ml/l2_prediction")
            validator.validate(ml_result)
            return True
        except SchemaValidationError as e:
            logger.error(f"ML output validation failed: {e}")
            return False

    def _get_validator(self, schema_name: str):
        """Get or create validator for schema.

        Args:
            schema_name: Name of schema (without .json)

        Returns:
            Schema validator
        """
        if schema_name not in self._validators:
            if not self._validator_instance:
                self._validator_instance = get_validator()
            self._validators[schema_name] = self._validator_instance.get_validator(f"{schema_name}.json")
        return self._validators[schema_name]


# Global middleware instance
_middleware = None


def get_middleware() -> SchemaValidationMiddleware:
    """Get global middleware instance.

    Returns:
        Schema validation middleware
    """
    global _middleware
    if _middleware is None:
        _middleware = SchemaValidationMiddleware()
    return _middleware


# Convenience decorators using global middleware
def validate_request(schema_name: str):
    """Convenience decorator for request validation.

    Args:
        schema_name: Schema to validate against

    Returns:
        Decorator function
    """
    return get_middleware().validate_request(schema_name)


def validate_response(schema_name: str):
    """Convenience decorator for response validation.

    Args:
        schema_name: Schema to validate against

    Returns:
        Decorator function
    """
    return get_middleware().validate_response(schema_name)