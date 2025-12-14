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

from raxe.infrastructure.telemetry.hook import TelemetryConfig
from raxe.utils.performance import PerformanceConfig, PerformanceMode


@dataclass
class L2ScoringConfig:
    """L2 hierarchical threat scoring configuration.

    Provides two modes:
    - Simple mode: Just set `mode` (high_security, balanced, or low_fp)
    - Expert mode: Override individual thresholds and weights

    The hierarchical scorer uses multiple confidence signals to reduce false positives:
    - Binary threat score (is_attack)
    - Family classification confidence
    - Subfamily classification confidence
    - Signal consistency checks
    - Decision margin analysis

    Attributes:
        mode: Scoring mode (high_security, balanced, or low_fp)
        custom_thresholds: Expert override for classification thresholds
        weights: Expert override for hierarchical weights (binary, family, subfamily)
        family_adjustments: Expert override for per-family threshold adjustments
        enable_consistency_check: Check for signal variance (default: True)
        enable_margin_analysis: Analyze decision margins (default: True)
        enable_entropy: Enable entropy-based uncertainty (future feature, default: False)
    """
    mode: str = "balanced"
    custom_thresholds: dict[str, float] | None = None
    weights: dict[str, float] | None = None
    family_adjustments: dict[str, dict[str, float]] | None = None
    enable_consistency_check: bool = True
    enable_margin_analysis: bool = True
    enable_entropy: bool = False

    def __post_init__(self) -> None:
        """Validate scoring configuration."""
        valid_modes = ("high_security", "balanced", "low_fp")
        if self.mode not in valid_modes:
            raise ValueError(
                f"mode must be one of {valid_modes}, got '{self.mode}'"
            )

        # Validate custom thresholds if provided
        if self.custom_thresholds:
            for key, value in self.custom_thresholds.items():
                if not (0.0 <= value <= 1.0):
                    raise ValueError(
                        f"custom_thresholds['{key}'] must be 0-1, got {value}"
                    )

        # Validate weights if provided
        if self.weights:
            expected_keys = {"binary", "family", "subfamily"}
            if not set(self.weights.keys()).issubset(expected_keys):
                raise ValueError(
                    f"weights must only contain {expected_keys}, "
                    f"got {set(self.weights.keys())}"
                )
            for key, value in self.weights.items():
                if not (0.0 <= value <= 1.0):
                    raise ValueError(
                        f"weights['{key}'] must be 0-1, got {value}"
                    )

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for serialization."""
        return {
            "mode": self.mode,
            "custom_thresholds": self.custom_thresholds,
            "weights": self.weights,
            "family_adjustments": self.family_adjustments,
            "enable_consistency_check": self.enable_consistency_check,
            "enable_margin_analysis": self.enable_margin_analysis,
            "enable_entropy": self.enable_entropy,
        }


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
        performance: Performance monitoring config
        telemetry: Telemetry configuration
        l2_scoring: L2 hierarchical scoring configuration
        api_key: Optional RAXE API key
        customer_id: Optional customer ID override
    """
    packs_root: Path = field(default_factory=lambda: Path.home() / ".raxe" / "packs")
    enable_l2: bool = True
    use_production_l2: bool = True
    l2_confidence_threshold: float = 0.5
    fail_fast_on_critical: bool = False  # Changed: Always run both L1 and L2 in parallel
    min_confidence_for_skip: float = 0.7
    enable_schema_validation: bool = False
    schema_validation_mode: str = "log_only"  # log_only, warn, enforce
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    l2_scoring: L2ScoringConfig = field(default_factory=L2ScoringConfig)
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
        performance_data = data.get("performance", {})
        telemetry_data = data.get("telemetry", {})
        l2_scoring_data = data.get("l2_scoring", {})

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

        # Build telemetry config - endpoint uses centralized config if not specified
        from raxe.infrastructure.config.endpoints import get_telemetry_endpoint
        telemetry = TelemetryConfig(
            enabled=telemetry_data.get("enabled", False),
            api_key=telemetry_data.get("api_key"),
            endpoint=telemetry_data.get("endpoint", "") or get_telemetry_endpoint(),
            batch_size=telemetry_data.get("batch_size", 10),
            flush_interval_seconds=telemetry_data.get("flush_interval_seconds", 30.0),
            max_queue_size=telemetry_data.get("max_queue_size", 1000),
            async_send=telemetry_data.get("async_send", True),
        )

        # Build L2 scoring config
        l2_scoring = L2ScoringConfig(
            mode=l2_scoring_data.get("mode", "balanced"),
            custom_thresholds=l2_scoring_data.get("custom_thresholds"),
            weights=l2_scoring_data.get("weights"),
            family_adjustments=l2_scoring_data.get("family_adjustments"),
            enable_consistency_check=l2_scoring_data.get("enable_consistency_check", True),
            enable_margin_analysis=l2_scoring_data.get("enable_margin_analysis", True),
            enable_entropy=l2_scoring_data.get("enable_entropy", False),
        )

        # Build scan config
        packs_root = scan_data.get("packs_root", str(Path.home() / ".raxe" / "packs"))
        return cls(
            packs_root=Path(packs_root),
            enable_l2=scan_data.get("enable_l2", True),
            use_production_l2=scan_data.get("use_production_l2", True),
            l2_confidence_threshold=scan_data.get("l2_confidence_threshold", 0.5),
            fail_fast_on_critical=scan_data.get("fail_fast_on_critical", False),  # Changed default to False
            min_confidence_for_skip=scan_data.get("min_confidence_for_skip", 0.7),
            enable_schema_validation=scan_data.get("enable_schema_validation", False),
            schema_validation_mode=scan_data.get("schema_validation_mode", "log_only"),
            performance=performance,
            telemetry=telemetry,
            l2_scoring=l2_scoring,
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
        fail_fast = os.getenv("RAXE_FAIL_FAST_ON_CRITICAL", "false").lower() == "true"  # Changed default to false
        min_confidence_for_skip = float(os.getenv("RAXE_MIN_CONFIDENCE_FOR_SKIP", "0.7"))
        enable_schema_validation = os.getenv("RAXE_ENABLE_SCHEMA_VALIDATION", "false").lower() == "true"
        schema_validation_mode = os.getenv("RAXE_SCHEMA_VALIDATION_MODE", "log_only")
        api_key = os.getenv("RAXE_API_KEY")
        customer_id = os.getenv("RAXE_CUSTOMER_ID")

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
            "l2_scoring": self.l2_scoring.to_dict(),
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
