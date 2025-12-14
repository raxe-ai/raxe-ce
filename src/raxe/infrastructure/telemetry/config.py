"""
Telemetry configuration management.

Loads telemetry configuration from schema-validated sources with
environment variable overrides for privacy control.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RetryPolicyConfig:
    """Retry policy configuration."""
    max_retries: int = 10
    initial_delay_ms: int = 1000
    max_delay_ms: int = 512000  # 512s max per specification
    backoff_multiplier: float = 2.0
    retry_on_status: list[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])


@dataclass
class TelemetryConfig:
    """
    Telemetry configuration with privacy-first defaults.

    All fields match schemas/v1.0.0/config/telemetry_config.json
    """
    # Core settings
    enabled: bool = True
    endpoint: str = ""  # Will be resolved from centralized endpoints
    privacy_mode: str = "strict"  # strict, standard, detailed

    # Privacy settings
    include_full_prompts: bool = False  # NEVER true by default
    include_context: bool = True
    hash_algorithm: str = "sha256"

    # Batching settings
    batch_size: int = 100
    flush_interval_ms: int = 5000
    max_queue_size: int = 10000

    # Performance settings
    sample_rate: float = 1.0
    compression: str = "gzip"
    send_performance_metrics: bool = True
    send_error_reports: bool = True

    # Retry policy
    retry_policy: RetryPolicyConfig = field(default_factory=RetryPolicyConfig)

    # Custom metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, config_path: Path) -> "TelemetryConfig":
        """
        Load configuration from JSON file.

        Args:
            config_path: Path to configuration file

        Returns:
            TelemetryConfig instance
        """
        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return cls()

        try:
            with open(config_path) as f:
                data = json.load(f)
                return cls.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            return cls()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TelemetryConfig":
        """
        Create configuration from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            TelemetryConfig instance
        """
        # Extract retry policy if present
        retry_policy_data = data.pop("retry_policy", {})
        retry_policy = RetryPolicyConfig(**retry_policy_data)

        # Create config with remaining fields
        config = cls(retry_policy=retry_policy)

        # Update with provided values
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)

        return config

    @classmethod
    def from_environment(cls) -> "TelemetryConfig":
        """
        Load configuration from environment variables.

        Environment variables override file configuration:
        - RAXE_TELEMETRY_ENABLED: true/false
        - RAXE_TELEMETRY_ENDPOINT: URL
        - RAXE_TELEMETRY_PRIVACY_MODE: strict/standard/detailed
        - RAXE_TELEMETRY_SAMPLE_RATE: 0.0-1.0
        - etc.

        Returns:
            TelemetryConfig instance
        """
        config = cls()

        # Map environment variables to config fields
        env_mapping = {
            "RAXE_TELEMETRY_ENABLED": ("enabled", lambda x: x.lower() == "true"),
            "RAXE_TELEMETRY_ENDPOINT": ("endpoint", str),
            "RAXE_TELEMETRY_PRIVACY_MODE": ("privacy_mode", str),
            "RAXE_TELEMETRY_INCLUDE_PROMPTS": ("include_full_prompts", lambda x: x.lower() == "true"),
            "RAXE_TELEMETRY_INCLUDE_CONTEXT": ("include_context", lambda x: x.lower() == "true"),
            "RAXE_TELEMETRY_HASH_ALGORITHM": ("hash_algorithm", str),
            "RAXE_TELEMETRY_BATCH_SIZE": ("batch_size", int),
            "RAXE_TELEMETRY_FLUSH_INTERVAL_MS": ("flush_interval_ms", int),
            "RAXE_TELEMETRY_MAX_QUEUE_SIZE": ("max_queue_size", int),
            "RAXE_TELEMETRY_SAMPLE_RATE": ("sample_rate", float),
            "RAXE_TELEMETRY_COMPRESSION": ("compression", str),
            "RAXE_TELEMETRY_SEND_METRICS": ("send_performance_metrics", lambda x: x.lower() == "true"),
            "RAXE_TELEMETRY_SEND_ERRORS": ("send_error_reports", lambda x: x.lower() == "true"),
        }

        for env_var, (field_name, converter) in env_mapping.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    setattr(config, field_name, converter(value))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid value for {env_var}: {value} ({e})")

        # Handle retry policy from environment
        retry_env_mapping = {
            "RAXE_TELEMETRY_MAX_RETRIES": ("max_retries", int),
            "RAXE_TELEMETRY_INITIAL_DELAY_MS": ("initial_delay_ms", int),
            "RAXE_TELEMETRY_MAX_DELAY_MS": ("max_delay_ms", int),
            "RAXE_TELEMETRY_BACKOFF_MULTIPLIER": ("backoff_multiplier", float),
        }

        for env_var, (field_name, converter) in retry_env_mapping.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    setattr(config.retry_policy, field_name, converter(value))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid value for {env_var}: {value} ({e})")

        return config

    @classmethod
    def load(cls, config_path: Path | None = None) -> "TelemetryConfig":
        """
        Load configuration with cascading precedence.

        Precedence (highest to lowest):
        1. Environment variables
        2. Config file (if provided)
        3. Default values

        Args:
            config_path: Optional path to config file

        Returns:
            Merged configuration
        """
        # Start with defaults
        if config_path and config_path.exists():
            config = cls.from_file(config_path)
        else:
            config = cls()

        # Override with environment variables
        env_config = cls.from_environment()

        # Merge environment overrides
        for field_name in config.__dataclass_fields__:
            env_value = getattr(env_config, field_name)
            default_value = cls().__dict__[field_name]

            # Only override if environment provided a non-default value
            if env_value != default_value:
                setattr(config, field_name, env_value)

        # Validate privacy settings
        config._validate_privacy()

        logger.info(
            f"Telemetry config loaded: enabled={config.enabled}, "
            f"privacy_mode={config.privacy_mode}, endpoint={config.endpoint}"
        )

        return config

    def _validate_privacy(self) -> None:
        """Validate and enforce privacy constraints."""
        # NEVER allow full prompts in strict mode
        if self.privacy_mode == "strict":
            if self.include_full_prompts:
                logger.warning("Disabling include_full_prompts in strict privacy mode")
                self.include_full_prompts = False

        # Warn about dangerous settings
        if self.include_full_prompts:
            logger.warning(
                "WARNING: include_full_prompts is enabled. "
                "This will send actual prompt text to telemetry endpoint. "
                "This is NOT recommended for production use."
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        # Convert retry policy dataclass to dict
        data["retry_policy"] = asdict(self.retry_policy)
        return data

    def is_enabled(self) -> bool:
        """Check if telemetry is enabled."""
        return self.enabled

    def should_sample(self) -> bool:
        """
        Check if current event should be sampled.

        Returns:
            True if event should be sent (based on sample_rate)
        """
        if self.sample_rate >= 1.0:
            return True
        if self.sample_rate <= 0.0:
            return False

        import random
        return random.random() < self.sample_rate