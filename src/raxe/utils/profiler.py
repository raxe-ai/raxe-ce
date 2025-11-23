"""Performance profiling for scan operations.

Provides detailed performance breakdowns and bottleneck identification.
Application layer - orchestrates domain logic with performance measurement.
"""
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from raxe.domain.engine.executor import RuleExecutor
from raxe.domain.ml.protocol import L2Detector
from raxe.domain.rules.models import Rule


@dataclass(frozen=True)
class RuleProfile:
    """Performance profile for a single rule.

    Attributes:
        rule_id: Rule identifier
        execution_time_ms: Time taken to execute this rule
        matched: Whether the rule matched
        cache_hit: Whether pattern was cached
    """
    rule_id: str
    execution_time_ms: float
    matched: bool
    cache_hit: bool


@dataclass(frozen=True)
class LayerProfile:
    """Performance profile for a detection layer.

    Attributes:
        layer_name: Name of layer (L1, L2, etc.)
        total_time_ms: Total time for this layer
        rule_profiles: Per-rule performance data
        cache_hits: Number of cache hits
        cache_misses: Number of cache misses
    """
    layer_name: str
    total_time_ms: float
    rule_profiles: list[RuleProfile]
    cache_hits: int
    cache_misses: int

    @property
    def cache_hit_rate(self) -> float:
        """Cache hit rate (0.0-1.0)."""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total

    @property
    def average_rule_time_ms(self) -> float:
        """Average time per rule."""
        if not self.rule_profiles:
            return 0.0
        return self.total_time_ms / len(self.rule_profiles)

    @property
    def slowest_rules(self) -> list[RuleProfile]:
        """Top 5 slowest rules."""
        return sorted(
            self.rule_profiles,
            key=lambda r: r.execution_time_ms,
            reverse=True,
        )[:5]


@dataclass(frozen=True)
class ProfileResult:
    """Complete performance profile for a scan.

    Attributes:
        total_time_ms: Total scan time
        text_length: Length of scanned text
        l1_profile: L1 layer profile
        l2_profile: Optional L2 layer profile
        overhead_ms: Pipeline overhead (non-detection time)
        timestamp: When profile was taken
    """
    total_time_ms: float
    text_length: int
    l1_profile: LayerProfile
    l2_profile: LayerProfile | None
    overhead_ms: float
    timestamp: str

    @property
    def l1_percentage(self) -> float:
        """Percentage of time spent in L1."""
        if self.total_time_ms == 0:
            return 0.0
        return (self.l1_profile.total_time_ms / self.total_time_ms) * 100

    @property
    def l2_percentage(self) -> float:
        """Percentage of time spent in L2."""
        if not self.l2_profile or self.total_time_ms == 0:
            return 0.0
        return (self.l2_profile.total_time_ms / self.total_time_ms) * 100

    @property
    def overhead_percentage(self) -> float:
        """Percentage of time spent in overhead."""
        if self.total_time_ms == 0:
            return 0.0
        return (self.overhead_ms / self.total_time_ms) * 100

    def identify_bottlenecks(self) -> list[str]:
        """Identify performance bottlenecks.

        Returns:
            List of bottleneck descriptions
        """
        bottlenecks = []

        # Check L1 performance
        if self.l1_percentage > 50:
            bottlenecks.append(f"L1 detection taking {self.l1_percentage:.1f}% of time")

            # Identify slow rules
            slow_rules = self.l1_profile.slowest_rules
            if slow_rules and slow_rules[0].execution_time_ms > 1.0:
                bottlenecks.append(
                    f"Slow L1 rule: {slow_rules[0].rule_id} ({slow_rules[0].execution_time_ms:.2f}ms)"
                )

        # Check L2 performance
        if self.l2_profile and self.l2_percentage > 64:
            bottlenecks.append(
                f"L2 inference taking {self.l2_percentage:.1f}% of time"
            )

        # Check cache performance
        if self.l1_profile.cache_hit_rate < 0.5:
            bottlenecks.append(
                f"Low L1 cache hit rate: {self.l1_profile.cache_hit_rate * 100:.1f}%"
            )

        # Check overhead
        if self.overhead_percentage > 20:
            bottlenecks.append(
                f"High pipeline overhead: {self.overhead_percentage:.1f}%"
            )

        return bottlenecks

    def get_recommendations(self) -> list[str]:
        """Get performance optimization recommendations.

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Based on bottlenecks
        bottlenecks = self.identify_bottlenecks()

        if any("L2 inference" in b for b in bottlenecks):
            recommendations.append("Consider --mode fast for <3ms scans (L1 only)")

        if any("Slow L1 rule" in b for b in bottlenecks):
            recommendations.append("Review and optimize slow regex patterns")

        if any("Low L1 cache" in b for b in bottlenecks):
            recommendations.append("Increase pattern matcher cache size")

        if any("overhead" in b for b in bottlenecks):
            recommendations.append("Reduce pipeline complexity or disable plugins")

        # General recommendations based on total time
        if self.total_time_ms > 100:
            recommendations.append("Total scan time >100ms - consider optimizing")
        elif self.total_time_ms < 3:
            recommendations.append("Excellent performance - already optimized!")

        return recommendations


class ScanProfiler:
    """Profile scan performance with detailed breakdowns.

    Application layer - measures and analyzes performance.
    """

    def __init__(
        self,
        rule_executor: RuleExecutor,
        l2_detector: L2Detector | None = None,
    ):
        """Initialize profiler.

        Args:
            rule_executor: L1 rule executor
            l2_detector: Optional L2 detector
        """
        self.rule_executor = rule_executor
        self.l2_detector = l2_detector

    def profile_scan(
        self,
        text: str,
        rules: list[Rule],
        *,
        include_l2: bool = True,
    ) -> ProfileResult:
        """Profile a complete scan operation.

        Args:
            text: Text to scan
            rules: Rules to apply
            include_l2: Whether to include L2 profiling

        Returns:
            ProfileResult with detailed performance breakdown
        """
        start_time = time.perf_counter()
        timestamp = datetime.now(timezone.utc).isoformat()

        # Profile L1
        l1_profile = self._profile_l1(text, rules)

        # Profile L2 (if enabled)
        l2_profile = None
        if include_l2 and self.l2_detector:
            l2_profile = self._profile_l2(text, rules)

        # Calculate overhead
        total_time_ms = (time.perf_counter() - start_time) * 1000
        detection_time = l1_profile.total_time_ms
        if l2_profile:
            detection_time += l2_profile.total_time_ms

        overhead_ms = max(0.0, total_time_ms - detection_time)

        return ProfileResult(
            total_time_ms=total_time_ms,
            text_length=len(text),
            l1_profile=l1_profile,
            l2_profile=l2_profile,
            overhead_ms=overhead_ms,
            timestamp=timestamp,
        )

    def _profile_l1(self, text: str, rules: list[Rule]) -> LayerProfile:
        """Profile L1 rule execution.

        Args:
            text: Text to scan
            rules: Rules to execute

        Returns:
            LayerProfile for L1
        """
        l1_start = time.perf_counter()
        rule_profiles = []
        cache_hits = 0
        cache_misses = 0

        for rule in rules:
            rule_start = time.perf_counter()

            # Execute rule
            try:
                detection = self.rule_executor.execute_rule(text, rule)
                matched = detection is not None
            except Exception:
                matched = False

            rule_time_ms = (time.perf_counter() - rule_start) * 1000

            # Cache status (simplified - would need matcher integration)
            cache_hit = rule_time_ms < 0.1  # Heuristic: <0.1ms likely cached
            if cache_hit:
                cache_hits += 1
            else:
                cache_misses += 1

            rule_profiles.append(RuleProfile(
                rule_id=rule.rule_id,
                execution_time_ms=rule_time_ms,
                matched=matched,
                cache_hit=cache_hit,
            ))

        l1_time_ms = (time.perf_counter() - l1_start) * 1000

        return LayerProfile(
            layer_name="L1",
            total_time_ms=l1_time_ms,
            rule_profiles=rule_profiles,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
        )

    def _profile_l2(self, text: str, rules: list[Rule]) -> LayerProfile:
        """Profile L2 ML detection.

        Args:
            text: Text to scan
            rules: Rules (for context)

        Returns:
            LayerProfile for L2
        """
        if not self.l2_detector:
            return LayerProfile(
                layer_name="L2",
                total_time_ms=0.0,
                rule_profiles=[],
                cache_hits=0,
                cache_misses=0,
            )

        l2_start = time.perf_counter()

        # Run L1 first (L2 needs L1 context)
        l1_result = self.rule_executor.execute_rules(text, rules)

        # Run L2
        try:
            self.l2_detector.analyze(text, l1_result, None)
        except Exception:
            pass

        l2_time_ms = (time.perf_counter() - l2_start) * 1000

        # L2 doesn't have per-rule profiling (it's a single model)
        return LayerProfile(
            layer_name="L2",
            total_time_ms=l2_time_ms,
            rule_profiles=[],  # No per-rule data for ML
            cache_hits=0,
            cache_misses=0,
        )
