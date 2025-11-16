"""Scan configuration management.

Manages configuration for the scan pipeline:
- Loads from .raxe/config.yaml
- Environment variable overrides
- Performance tuning options
- Policy configuration
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from raxe.domain.models import ScanPolicy
from raxe.infrastructure.telemetry.hook import TelemetryConfig
from raxe.utils.performance import PerformanceConfig, PerformanceMode


@dataclass
class ScanConfig:
    """Complete scan configuration.

    Attributes:
        packs_root: Root directory for rule packs
        enable_l2: Enable L2 ML detection
        use_production_l2: Use production ML model instead of stub (default: True)
        l2_confidence_threshold: Minimum confidence for L2 predictions (default: 0.5)
        fail_fast_on_critical: Skip L2 if CRITICAL detected
        min_confidence_for_skip: Minimum L1 confidence to skip L2 on CRITICAL (default: 0.7)
        enable_schema_validation: Enable runtime schema validation (default: False)
        schema_validation_mode: How to handle validation failures ('log_only', 'warn', 'enforce')
        policy: Scan policy for decision making
        performance: Performance monitoring config
        telemetry: Telemetry configuration
        api_key: Optional RAXE API key
        customer_id: Optional customer ID override
    """
    packs_root: Path = field(default_factory=lambda: Path.home() / ".raxe" / "packs")
    enable_l2: bool = True
    use_production_l2: bool = True
    l2_confidence_threshold: float = 0.5
    fail_fast_on_critical: bool = True
    min_confidence_for_skip: float = 0.7
    enable_schema_validation: bool = False
    schema_validation_mode: str = "log_only"  # log_only, warn, enforce
    policy: ScanPolicy = field(default_factory=ScanPolicy)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    api_key: str | None = None
    customer_id: str | None = None

    def __post_init__(self) -> None:
        """Validate configuration after construction."""
        # Ensure packs_root is absolute
        if not self.packs_root.is_absolute():
            self.packs_root = self.packs_root.resolve()

        # Validate confidence thresholds
        if not (0.0 <= self.l2_confidence_threshold <= 1.0):
            raise ValueError(f"l2_confidence_threshold must be 0-1, got {self.l2_confidence_threshold}")
        if not (0.0 <= self.min_confidence_for_skip <= 1.0):
            raise ValueError(f"min_confidence_for_skip must be 0-1, got {self.min_confidence_for_skip}")

    @classmethod
    def from_file(cls, config_path: Path) -> "ScanConfig":
        """Load configuration from YAML file.

        Args:
            config_path: Path to config.yaml

        Returns:
            ScanConfig loaded from file

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config format invalid
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Empty config file: {config_path}")

        # Extract sections
        scan_data = data.get("scan", {})
        policy_data = data.get("policy", {})
        performance_data = data.get("performance", {})
        telemetry_data = data.get("telemetry", {})

        # Build policy
        policy = ScanPolicy(
            block_on_critical=policy_data.get("block_on_critical", True),
            block_on_high=policy_data.get("block_on_high", False),
            allow_on_low_confidence=policy_data.get("allow_on_low_confidence", True),
            confidence_threshold=policy_data.get("confidence_threshold", 0.7),
        )

        # Build performance config
        perf_mode_str = performance_data.get("mode", "fail_open")
        performance = PerformanceConfig(
            mode=PerformanceMode(perf_mode_str),
            failure_threshold=performance_data.get("failure_threshold", 5),
            reset_timeout_seconds=performance_data.get("reset_timeout_seconds", 30.0),
            half_open_requests=performance_data.get("half_open_requests", 3),
            sample_rate=performance_data.get("sample_rate", 10),
            latency_threshold_ms=performance_data.get("latency_threshold_ms", 10.0),
        )

        # Build telemetry config
        telemetry = TelemetryConfig(
            enabled=telemetry_data.get("enabled", False),
            api_key=telemetry_data.get("api_key"),
            endpoint=telemetry_data.get("endpoint", "https://telemetry.raxe.ai/v1/events"),
            batch_size=telemetry_data.get("batch_size", 10),
            flush_interval_seconds=telemetry_data.get("flush_interval_seconds", 30.0),
            max_queue_size=telemetry_data.get("max_queue_size", 1000),
            async_send=telemetry_data.get("async_send", True),
        )

        # Build scan config
        packs_root = scan_data.get("packs_root", str(Path.home() / ".raxe" / "packs"))
        return cls(
            packs_root=Path(packs_root),
            enable_l2=scan_data.get("enable_l2", True),
            use_production_l2=scan_data.get("use_production_l2", True),
            l2_confidence_threshold=scan_data.get("l2_confidence_threshold", 0.5),
            fail_fast_on_critical=scan_data.get("fail_fast_on_critical", True),
            min_confidence_for_skip=scan_data.get("min_confidence_for_skip", 0.7),
            enable_schema_validation=scan_data.get("enable_schema_validation", False),
            schema_validation_mode=scan_data.get("schema_validation_mode", "log_only"),
            policy=policy,
            performance=performance,
            telemetry=telemetry,
            api_key=scan_data.get("api_key"),
            customer_id=scan_data.get("customer_id"),
        )

    @classmethod
    def from_env(cls) -> "ScanConfig":
        """Load configuration from environment variables.

        Environment variables:
            RAXE_PACKS_ROOT: Pack root directory
            RAXE_ENABLE_L2: Enable L2 detection
            RAXE_FAIL_FAST_ON_CRITICAL: Skip L2 on CRITICAL detections
            RAXE_MIN_CONFIDENCE_FOR_SKIP: Min L1 confidence to skip L2 (default: 0.7)
            RAXE_API_KEY: RAXE API key
            RAXE_TELEMETRY_ENABLED: Enable telemetry
            RAXE_PERFORMANCE_MODE: Performance mode

        Returns:
            ScanConfig from environment
        """
        # Scan settings
        packs_root = os.getenv("RAXE_PACKS_ROOT", str(Path.home() / ".raxe" / "packs"))
        enable_l2 = os.getenv("RAXE_ENABLE_L2", "true").lower() == "true"
        use_production_l2 = os.getenv("RAXE_USE_PRODUCTION_L2", "true").lower() == "true"
        l2_confidence_threshold = float(os.getenv("RAXE_L2_CONFIDENCE_THRESHOLD", "0.5"))
        fail_fast = os.getenv("RAXE_FAIL_FAST_ON_CRITICAL", "true").lower() == "true"
        min_confidence_for_skip = float(os.getenv("RAXE_MIN_CONFIDENCE_FOR_SKIP", "0.7"))
        enable_schema_validation = os.getenv("RAXE_ENABLE_SCHEMA_VALIDATION", "false").lower() == "true"
        schema_validation_mode = os.getenv("RAXE_SCHEMA_VALIDATION_MODE", "log_only")
        api_key = os.getenv("RAXE_API_KEY")
        customer_id = os.getenv("RAXE_CUSTOMER_ID")

        # Policy settings
        block_critical = os.getenv("RAXE_BLOCK_ON_CRITICAL", "true").lower() == "true"
        block_high = os.getenv("RAXE_BLOCK_ON_HIGH", "false").lower() == "true"

        policy = ScanPolicy(
            block_on_critical=block_critical,
            block_on_high=block_high,
        )

        # Performance settings
        perf_mode_str = os.getenv("RAXE_PERFORMANCE_MODE", "fail_open")
        performance = PerformanceConfig(
            mode=PerformanceMode(perf_mode_str),
        )

        # Telemetry settings
        telemetry_enabled = os.getenv("RAXE_TELEMETRY_ENABLED", "false").lower() == "true"
        telemetry = TelemetryConfig(
            enabled=telemetry_enabled,
            api_key=api_key,
        )

        return cls(
            packs_root=Path(packs_root),
            enable_l2=enable_l2,
            use_production_l2=use_production_l2,
            l2_confidence_threshold=l2_confidence_threshold,
            fail_fast_on_critical=fail_fast,
            min_confidence_for_skip=min_confidence_for_skip,
            enable_schema_validation=enable_schema_validation,
            schema_validation_mode=schema_validation_mode,
            policy=policy,
            performance=performance,
            telemetry=telemetry,
            api_key=api_key,
            customer_id=customer_id,
        )

    @classmethod
    def load(cls, config_path: Path | None = None) -> "ScanConfig":
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
            Loaded ScanConfig
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

        # Fall back to environment
        return cls.from_env()

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            "scan": {
                "packs_root": str(self.packs_root),
                "enable_l2": self.enable_l2,
                "use_production_l2": self.use_production_l2,
                "l2_confidence_threshold": self.l2_confidence_threshold,
                "fail_fast_on_critical": self.fail_fast_on_critical,
                "enable_schema_validation": self.enable_schema_validation,
                "schema_validation_mode": self.schema_validation_mode,
                "api_key": "***" if self.api_key else None,  # Redact
                "customer_id": self.customer_id,
            },
            "policy": {
                "block_on_critical": self.policy.block_on_critical,
                "block_on_high": self.policy.block_on_high,
                "allow_on_low_confidence": self.policy.allow_on_low_confidence,
                "confidence_threshold": self.policy.confidence_threshold,
            },
            "performance": {
                "mode": self.performance.mode.value,
                "failure_threshold": self.performance.failure_threshold,
                "reset_timeout_seconds": self.performance.reset_timeout_seconds,
                "latency_threshold_ms": self.performance.latency_threshold_ms,
            },
            "telemetry": {
                "enabled": self.telemetry.enabled,
                "batch_size": self.telemetry.batch_size,
                "async_send": self.telemetry.async_send,
            },
        }

    def save(self, config_path: Path) -> None:
        """Save configuration to YAML file.

        Args:
            config_path: Path where to save config
        """
        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            yaml.safe_dump(self.to_dict(), f, default_flow_style=False)
