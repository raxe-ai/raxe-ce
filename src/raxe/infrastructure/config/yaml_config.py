"""YAML-based configuration management.

Modern configuration system using YAML format.
Provides schema validation, type safety, and clear error messages.

Configuration file: ~/.raxe/config.yaml

Example YAML config:
    core:
      api_key: ""
      environment: production
      version: "0.0.1"

    detection:
      l1_enabled: true
      l2_enabled: true
      mode: balanced  # fast|balanced|thorough
      confidence_threshold: 0.5

    telemetry:
      enabled: true
      batch_size: 50
      flush_interval: 300

    performance:
      max_queue_size: 10000
      scan_timeout: 30

    logging:
      level: INFO
      directory: ~/.raxe/logs
      rotation_size: 10MB
      rotation_count: 5
"""
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml


@dataclass
class CoreConfig:
    """Core configuration settings."""
    api_key: str = ""
    environment: Literal["development", "production", "test", "local", "staging"] = "production"
    version: str = "0.0.1"


@dataclass
class DetectionConfig:
    """Detection engine configuration."""
    l1_enabled: bool = True
    l2_enabled: bool = True
    mode: Literal["fast", "balanced", "thorough"] = "balanced"
    confidence_threshold: float = 0.5
    fail_fast_on_critical: bool = False  # Changed: Always run both L1 and L2 in parallel
    min_confidence_for_skip: float = 0.7


@dataclass
class TelemetryConfig:
    """Telemetry configuration."""
    enabled: bool = True
    batch_size: int = 50
    flush_interval: int = 300  # seconds
    endpoint: str = ""  # Will be resolved from centralized endpoints if empty
    async_send: bool = True
    max_queue_size: int = 1000


@dataclass
class PerformanceConfig:
    """Performance and reliability configuration."""
    max_queue_size: int = 10000
    scan_timeout: int = 30  # seconds
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 30  # seconds


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    directory: str = "~/.raxe/logs"
    rotation_size: str = "10MB"
    rotation_count: int = 5
    enable_file_logging: bool = True
    enable_console_logging: bool = True


@dataclass
class RaxeConfig:
    """Complete RAXE configuration.

    Attributes:
        core: Core settings (API key, environment)
        detection: Detection engine settings
        telemetry: Telemetry settings
        performance: Performance settings
        logging: Logging settings
    """
    core: CoreConfig = field(default_factory=CoreConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def from_file(cls, config_path: Path) -> "RaxeConfig":
        """Load configuration from YAML file.

        Args:
            config_path: Path to config.yaml file

        Returns:
            RaxeConfig loaded from file

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config format is invalid
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        try:
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            raise ValueError(f"Failed to parse YAML config: {e}") from e

        return cls._from_dict(data)

    @classmethod
    def _filter_known_fields(cls, dataclass_type: type, data: dict[str, Any]) -> dict[str, Any]:
        """Filter dictionary to only include fields that exist in the dataclass.

        This allows config files to have extra fields (for forward compatibility)
        without causing errors when loading.

        Args:
            dataclass_type: The dataclass type to filter for
            data: Dictionary of configuration values

        Returns:
            Filtered dictionary with only known fields
        """
        import dataclasses
        known_fields = {f.name for f in dataclasses.fields(dataclass_type)}
        return {k: v for k, v in data.items() if k in known_fields}

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "RaxeConfig":
        """Build RaxeConfig from dictionary.

        Args:
            data: Configuration dictionary from YAML

        Returns:
            RaxeConfig instance

        Note:
            Unknown fields in config sections are silently ignored for
            forward compatibility with newer config files.
        """
        from raxe.infrastructure.config.endpoints import get_telemetry_endpoint

        # Build sub-configs, filtering unknown fields for compatibility
        core = CoreConfig(**cls._filter_known_fields(CoreConfig, data.get("core", {})))
        detection = DetectionConfig(**cls._filter_known_fields(DetectionConfig, data.get("detection", {})))
        telemetry = TelemetryConfig(**cls._filter_known_fields(TelemetryConfig, data.get("telemetry", {})))
        performance = PerformanceConfig(**cls._filter_known_fields(PerformanceConfig, data.get("performance", {})))
        logging_cfg = LoggingConfig(**cls._filter_known_fields(LoggingConfig, data.get("logging", {})))

        # Resolve empty telemetry endpoint from centralized config
        if not telemetry.endpoint:
            telemetry = TelemetryConfig(
                enabled=telemetry.enabled,
                batch_size=telemetry.batch_size,
                flush_interval=telemetry.flush_interval,
                endpoint=get_telemetry_endpoint(),
                async_send=telemetry.async_send,
                max_queue_size=telemetry.max_queue_size,
            )

        return cls(
            core=core,
            detection=detection,
            telemetry=telemetry,
            performance=performance,
            logging=logging_cfg,
        )

    @classmethod
    def from_env(cls) -> "RaxeConfig":
        """Load configuration from environment variables.

        Environment variables override defaults with pattern:
            RAXE_<SECTION>_<KEY>

        Examples:
            RAXE_CORE_API_KEY=xxx
            RAXE_DETECTION_L2_ENABLED=true
            RAXE_LOGGING_LEVEL=DEBUG

        Returns:
            RaxeConfig from environment
        """
        # Helper to get bool from env
        def get_bool(key: str, default: bool) -> bool:
            return os.getenv(key, str(default)).lower() in ("true", "1", "yes")

        # Helper to get int from env
        def get_int(key: str, default: int) -> int:
            return int(os.getenv(key, str(default)))

        # Helper to get float from env
        def get_float(key: str, default: float) -> float:
            return float(os.getenv(key, str(default)))

        # Core settings
        core = CoreConfig(
            api_key=os.getenv("RAXE_CORE_API_KEY", "") or os.getenv("RAXE_API_KEY", ""),
            environment=os.getenv("RAXE_CORE_ENVIRONMENT", "production"),  # type: ignore
            version=os.getenv("RAXE_CORE_VERSION", "0.0.1"),
        )

        # Detection settings
        detection = DetectionConfig(
            l1_enabled=get_bool("RAXE_DETECTION_L1_ENABLED", True),
            l2_enabled=get_bool("RAXE_DETECTION_L2_ENABLED", True),
            mode=os.getenv("RAXE_DETECTION_MODE", "balanced"),  # type: ignore
            confidence_threshold=get_float("RAXE_DETECTION_CONFIDENCE_THRESHOLD", 0.5),
            fail_fast_on_critical=get_bool("RAXE_DETECTION_FAIL_FAST_ON_CRITICAL", False),  # Changed default to False
            min_confidence_for_skip=get_float("RAXE_DETECTION_MIN_CONFIDENCE_FOR_SKIP", 0.7),
        )

        # Telemetry settings - endpoint resolved from centralized config if not overridden
        from raxe.infrastructure.config.endpoints import get_telemetry_endpoint

        telemetry = TelemetryConfig(
            enabled=get_bool("RAXE_TELEMETRY_ENABLED", True),
            batch_size=get_int("RAXE_TELEMETRY_BATCH_SIZE", 50),
            flush_interval=get_int("RAXE_TELEMETRY_FLUSH_INTERVAL", 300),
            endpoint=os.getenv("RAXE_TELEMETRY_ENDPOINT", "") or get_telemetry_endpoint(),
            async_send=get_bool("RAXE_TELEMETRY_ASYNC_SEND", True),
            max_queue_size=get_int("RAXE_TELEMETRY_MAX_QUEUE_SIZE", 1000),
        )

        # Performance settings
        performance = PerformanceConfig(
            max_queue_size=get_int("RAXE_PERFORMANCE_MAX_QUEUE_SIZE", 10000),
            scan_timeout=get_int("RAXE_PERFORMANCE_SCAN_TIMEOUT", 30),
            circuit_breaker_enabled=get_bool("RAXE_PERFORMANCE_CIRCUIT_BREAKER_ENABLED", True),
            circuit_breaker_threshold=get_int("RAXE_PERFORMANCE_CIRCUIT_BREAKER_THRESHOLD", 5),
            circuit_breaker_timeout=get_int("RAXE_PERFORMANCE_CIRCUIT_BREAKER_TIMEOUT", 30),
        )

        # Logging settings
        logging_cfg = LoggingConfig(
            level=os.getenv("RAXE_LOG_LEVEL", "INFO").upper(),  # type: ignore
            directory=os.getenv("RAXE_LOG_DIR", "~/.raxe/logs"),
            rotation_size=os.getenv("RAXE_LOG_ROTATION_SIZE", "10MB"),
            rotation_count=get_int("RAXE_LOG_ROTATION_COUNT", 5),
            enable_file_logging=get_bool("RAXE_ENABLE_FILE_LOGGING", True),
            enable_console_logging=get_bool("RAXE_ENABLE_CONSOLE_LOGGING", True),
        )

        return cls(
            core=core,
            detection=detection,
            telemetry=telemetry,
            performance=performance,
            logging=logging_cfg,
        )

    @classmethod
    def load(cls, config_path: Path | None = None) -> "RaxeConfig":
        """Load configuration with fallback chain.

        Priority:
        1. Explicit config file path
        2. .raxe/config.yaml in current directory
        3. ~/.raxe/config.yaml in home directory
        4. Environment variables
        5. Defaults

        Args:
            config_path: Optional explicit config file path

        Returns:
            Loaded RaxeConfig
        """
        # Try explicit path first
        if config_path and config_path.exists():
            return cls.from_file(config_path)

        # Try current directory
        local_config = Path(".raxe/config.yaml")
        if local_config.exists():
            return cls.from_file(local_config)

        # Try home directory
        home_config = Path.home() / ".raxe" / "config.yaml"
        if home_config.exists():
            return cls.from_file(home_config)

        # Fall back to environment variables
        return cls.from_env()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation (suitable for YAML writing)
        """
        return {
            "core": {
                **asdict(self.core),
                "api_key": "***" if self.core.api_key else "",  # Redact
            },
            "detection": asdict(self.detection),
            "telemetry": {
                **asdict(self.telemetry),
            },
            "performance": asdict(self.performance),
            "logging": asdict(self.logging),
        }

    def save(self, config_path: Path) -> None:
        """Save configuration to YAML file.

        Args:
            config_path: Path where to save config
        """
        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict (with redactions)
        config_dict = self.to_dict()

        # Write YAML
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

    def validate(self) -> list[str]:
        """Validate configuration values.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate confidence thresholds
        if not 0 <= self.detection.confidence_threshold <= 1:
            errors.append(
                f"detection.confidence_threshold must be 0-1, got {self.detection.confidence_threshold}"
            )

        # Validate queue sizes
        if self.performance.max_queue_size < 100:
            errors.append(
                f"performance.max_queue_size must be >= 100, got {self.performance.max_queue_size}"
            )

        if self.telemetry.max_queue_size < 10:
            errors.append(
                f"telemetry.max_queue_size must be >= 10, got {self.telemetry.max_queue_size}"
            )

        # Validate timeouts
        if self.performance.scan_timeout < 1:
            errors.append(
                f"performance.scan_timeout must be >= 1, got {self.performance.scan_timeout}"
            )

        # Validate batch size
        if self.telemetry.batch_size < 1:
            errors.append(
                f"telemetry.batch_size must be >= 1, got {self.telemetry.batch_size}"
            )

        # Validate flush interval
        if self.telemetry.flush_interval < 1:
            errors.append(
                f"telemetry.flush_interval must be >= 1, got {self.telemetry.flush_interval}"
            )

        return errors

    def update(self, key_path: str, value: Any) -> None:
        """Update a configuration value by dot-separated path.

        Args:
            key_path: Dot-separated path (e.g., "detection.l2_enabled")
            value: New value to set

        Raises:
            ValueError: If key path is invalid
        """
        parts = key_path.split(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid key path: {key_path}. Must be <section>.<key>")

        section, key = parts

        # Get section object
        section_obj = getattr(self, section, None)
        if section_obj is None:
            raise ValueError(f"Invalid section: {section}")

        # Check if key exists
        if not hasattr(section_obj, key):
            raise ValueError(f"Invalid key: {key} in section {section}")

        # Set value
        setattr(section_obj, key, value)

    def get(self, key_path: str) -> Any:
        """Get a configuration value by dot-separated path.

        Args:
            key_path: Dot-separated path (e.g., "detection.l2_enabled")

        Returns:
            Configuration value

        Raises:
            ValueError: If key path is invalid
        """
        parts = key_path.split(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid key path: {key_path}. Must be <section>.<key>")

        section, key = parts

        # Get section object
        section_obj = getattr(self, section, None)
        if section_obj is None:
            raise ValueError(f"Invalid section: {section}")

        # Get value
        return getattr(section_obj, key)


def create_default_config(config_path: Path) -> RaxeConfig:
    """Create a default configuration file.

    Args:
        config_path: Path where to save config

    Returns:
        Created RaxeConfig instance
    """
    config = RaxeConfig()
    config.save(config_path)
    return config
