"""Preload and optimize components for fast scanning.

Application layer - loads and caches components at startup to minimize
per-scan overhead. This is critical for achieving <10ms P95 latency.

Optimization strategies:
1. Preload rule packs at startup (not per scan)
2. Compile regex patterns upfront
3. Warm up L2 detector
4. Cache configuration

Performance impact:
- Startup time: +100-200ms (one-time cost)
- Per-scan latency: -5-10ms (recurring benefit)
"""
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from raxe.application.scan_merger import ScanMerger
from raxe.application.scan_pipeline import ScanPipeline
from raxe.domain.engine.executor import RuleExecutor
from raxe.domain.ml import StubL2Detector, create_bundle_detector
from raxe.infrastructure.config.scan_config import ScanConfig
from raxe.infrastructure.packs.registry import PackRegistry, RegistryConfig
from raxe.infrastructure.telemetry.hook import TelemetryHook

logger = logging.getLogger(__name__)


def get_bundled_packs_root() -> Path:
    """Get path to bundled core packs shipped with the package.

    Returns:
        Path to src/raxe/packs directory in installed package
    """
    # __file__ is this module (preloader.py)
    # src/raxe/application/preloader.py -> src/raxe/packs
    return Path(__file__).parent.parent / "packs"


@dataclass
class PreloadStats:
    """Statistics from preloading operation.

    Attributes:
        duration_ms: Total preload time
        packs_loaded: Number of packs loaded
        rules_loaded: Number of rules loaded
        patterns_compiled: Number of regex patterns compiled
        config_loaded: True if config loaded successfully
        telemetry_initialized: True if telemetry initialized
    """
    duration_ms: float
    packs_loaded: int
    rules_loaded: int
    patterns_compiled: int
    config_loaded: bool
    telemetry_initialized: bool

    def __str__(self) -> str:
        """Human-readable summary."""
        return (
            f"Preload complete in {self.duration_ms:.1f}ms: "
            f"{self.packs_loaded} packs, {self.rules_loaded} rules, "
            f"{self.patterns_compiled} patterns compiled"
        )


class PipelinePreloader:
    """Preload and optimize scan pipeline at startup.

    This class handles one-time initialization to ensure subsequent
    scans are as fast as possible.

    Example usage:
        # At application startup
        preloader = PipelinePreloader()
        pipeline, stats = preloader.preload()

        print(f"Startup: {stats}")
        # Startup complete in 150ms: 3 packs, 15 rules, 45 patterns

        # Fast scans (everything cached)
        result = pipeline.scan("test")
        # <5ms per scan
    """

    def __init__(
        self,
        config_path: Path | None = None,
        config: ScanConfig | None = None,
        suppression_manager: object | None = None,
    ):
        """Initialize preloader.

        Args:
            config_path: Optional path to config file
            config: Optional explicit config (overrides config_path)
            suppression_manager: Optional suppression manager for false positive handling
        """
        self.config_path = config_path
        self._config = config
        self.suppression_manager = suppression_manager

    def preload(self) -> tuple[ScanPipeline, PreloadStats]:
        """Preload all components and create ready-to-use pipeline.

        Returns:
            Tuple of (pipeline, stats)

        Raises:
            Exception: If critical components fail to load
        """
        start_time = time.perf_counter()
        logger.info("Starting pipeline preload")

        # 1. Load configuration
        if self._config:
            config = self._config
            config_loaded = True
        else:
            try:
                config = ScanConfig.load(self.config_path)
                config_loaded = True
                logger.info(f"Loaded config from {config.packs_root}")
            except Exception as e:
                logger.warning(f"Failed to load config: {e}. Using defaults.")
                config = ScanConfig()
                config_loaded = False

        # 2. Load pack registry and rules
        # Try user packs first, fall back to bundled packs if needed
        packs_root = config.packs_root

        # Check if user packs exist, if not use bundled packs
        if not packs_root.exists() or not any(packs_root.iterdir()):
            bundled_root = get_bundled_packs_root()
            logger.info(
                f"User packs not found at {packs_root}, "
                f"falling back to bundled packs at {bundled_root}"
            )
            packs_root = bundled_root

        registry_config = RegistryConfig(
            packs_root=packs_root,
            precedence=["custom", "community", "core"],
            strict=False,
        )
        pack_registry = PackRegistry(registry_config)

        try:
            pack_registry.load_all_packs()
            packs_loaded = len(pack_registry.list_packs())
            all_rules = pack_registry.get_all_rules()
            rules_loaded = len(all_rules)
            logger.info(
                f"Loaded {rules_loaded} rules from {packs_loaded} packs"
            )
        except Exception as e:
            logger.error(f"Failed to load packs: {e}")
            # Continue with empty registry (degraded mode)
            packs_loaded = 0
            rules_loaded = 0
            all_rules = []

        # 3. Initialize and warm up rule executor
        rule_executor = RuleExecutor()

        # Warm up: compile all patterns
        patterns_compiled = 0
        if all_rules:
            try:
                # Run a dummy scan to compile all patterns
                warmup_text = "warmup scan to compile patterns"
                rule_executor.execute_rules(warmup_text, all_rules)
                patterns_compiled = sum(len(r.patterns) for r in all_rules)
                logger.info(f"Compiled {patterns_compiled} regex patterns")
            except Exception as e:
                logger.warning(f"Failed to warm up rule executor: {e}")

        # 4. Initialize L2 detector (LAZY LOADING for faster startup)
        # Instead of loading L2 detector immediately, create a lazy wrapper
        # This reduces first scan startup time from ~4s to <2s
        # L2 will be loaded on first use (when l2_enabled=True in scan)
        from raxe.application.lazy_l2 import LazyL2Detector

        l2_detector = LazyL2Detector(
            config=config,
            use_production=config.use_production_l2,
            confidence_threshold=config.l2_confidence_threshold
        )
        logger.info("L2 detector configured for lazy loading (loads on first use)")

        # 5. Initialize scan merger
        scan_merger = ScanMerger()

        # 6. Initialize telemetry (if enabled)
        telemetry_hook = None
        telemetry_initialized = False
        if config.telemetry.enabled:
            try:
                telemetry_hook = TelemetryHook(config.telemetry)
                telemetry_initialized = True
                logger.info("Telemetry initialized")
            except Exception as e:
                logger.error(f"Failed to initialize telemetry: {e}")

        # 7. Create pipeline with all preloaded components
        pipeline = ScanPipeline(
            pack_registry=pack_registry,
            rule_executor=rule_executor,
            l2_detector=l2_detector,
            scan_merger=scan_merger,
            policy=config.policy,
            telemetry_hook=telemetry_hook,
            suppression_manager=self.suppression_manager,
            enable_l2=config.enable_l2,
            fail_fast_on_critical=config.fail_fast_on_critical,
            min_confidence_for_skip=config.min_confidence_for_skip,
            enable_schema_validation=config.enable_schema_validation,
            schema_validation_mode=config.schema_validation_mode,
        )

        # Calculate stats
        duration_ms = (time.perf_counter() - start_time) * 1000
        stats = PreloadStats(
            duration_ms=duration_ms,
            packs_loaded=packs_loaded,
            rules_loaded=rules_loaded,
            patterns_compiled=patterns_compiled,
            config_loaded=config_loaded,
            telemetry_initialized=telemetry_initialized,
        )

        logger.info(f"Preload complete: {stats}")
        return pipeline, stats

    @staticmethod
    def create_default_pipeline() -> ScanPipeline:
        """Create pipeline with default configuration (no preloading).

        This is slower than using preload() but simpler for quick usage.

        Returns:
            ScanPipeline with default settings
        """
        config = ScanConfig()

        registry_config = RegistryConfig(
            packs_root=config.packs_root,
            strict=False,
        )
        pack_registry = PackRegistry(registry_config)
        pack_registry.load_all_packs()

        # Choose detector based on config
        if config.use_production_l2:
            try:
                l2_detector = create_bundle_detector(
                    confidence_threshold=config.l2_confidence_threshold
                )
            except Exception:
                l2_detector = StubL2Detector()
        else:
            l2_detector = StubL2Detector()

        return ScanPipeline(
            pack_registry=pack_registry,
            rule_executor=RuleExecutor(),
            l2_detector=l2_detector,
            scan_merger=ScanMerger(),
            policy=config.policy,
            enable_l2=config.enable_l2,
            enable_schema_validation=config.enable_schema_validation,
            schema_validation_mode=config.schema_validation_mode,
        )


def preload_pipeline(
    config_path: Path | None = None,
    config: ScanConfig | None = None,
    suppression_manager: object | None = None,
) -> tuple[ScanPipeline, PreloadStats]:
    """Convenience function to preload pipeline.

    Args:
        config_path: Optional path to config file
        config: Optional explicit config
        suppression_manager: Optional suppression manager for false positive handling

    Returns:
        Tuple of (pipeline, stats)

    Example:
        pipeline, stats = preload_pipeline()
        print(stats)
        result = pipeline.scan("test")
    """
    preloader = PipelinePreloader(config_path, config, suppression_manager)
    return preloader.preload()
