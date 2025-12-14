"""A/B Testing framework for detector configuration.

Allows gradual rollout and comparison of L1-only vs L1+L2 detection modes.
"""
import hashlib
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DetectorMode(Enum):
    """Detection modes for A/B testing."""

    L1_ONLY = "l1_only"
    L1_AND_L2 = "l1_and_l2"


@dataclass(frozen=True)
class ABTestConfig:
    """A/B test configuration."""

    l2_rollout_percentage: float = 10.0  # Default 10% rollout
    enabled: bool = True
    customer_overrides: dict[str, DetectorMode] = None

    def __post_init__(self):
        """Validate configuration."""
        if not 0 <= self.l2_rollout_percentage <= 100:
            raise ValueError("Rollout percentage must be between 0 and 100")

        # Handle frozen dataclass field initialization
        if self.customer_overrides is None:
            object.__setattr__(self, 'customer_overrides', {})


class ABTestManager:
    """Manages A/B testing for detector modes."""

    def __init__(self, config: ABTestConfig = None):
        """Initialize with config.

        Args:
            config: AB test configuration
        """
        self.config = config or ABTestConfig()
        self._cohort_cache = {}
        logger.info(
            f"AB test manager initialized: L2 rollout={self.config.l2_rollout_percentage}%"
        )

    def get_detector_mode(
        self,
        customer_id: str | None = None,
        session_id: str | None = None
    ) -> DetectorMode:
        """Determine which detector mode to use.

        Uses consistent hashing to assign users to cohorts.

        Args:
            customer_id: Customer identifier for consistent assignment
            session_id: Session identifier as fallback

        Returns:
            DetectorMode to use for this request
        """
        if not self.config.enabled:
            return DetectorMode.L1_AND_L2  # Default to full detection

        # Check for customer override
        if customer_id and customer_id in self.config.customer_overrides:
            mode = self.config.customer_overrides[customer_id]
            logger.debug(f"Customer {customer_id} has override: {mode.value}")
            return mode

        # Use customer_id or session_id for consistent assignment
        cohort_key = customer_id or session_id or "anonymous"

        # Check cache
        if cohort_key in self._cohort_cache:
            return self._cohort_cache[cohort_key]

        # Calculate cohort assignment using consistent hashing
        mode = self._calculate_cohort(cohort_key)

        # Cache the assignment
        self._cohort_cache[cohort_key] = mode

        logger.debug(f"Assigned {cohort_key} to mode: {mode.value}")
        return mode

    def _calculate_cohort(self, cohort_key: str) -> DetectorMode:
        """Calculate cohort assignment using consistent hashing.

        Args:
            cohort_key: Key to hash for assignment

        Returns:
            Assigned detector mode
        """
        # Hash the key to get consistent assignment
        hash_value = hashlib.sha256(cohort_key.encode()).hexdigest()

        # Convert first 8 hex chars to int (32-bit value)
        hash_int = int(hash_value[:8], 16)

        # Map to 0-100 range
        percentage = (hash_int % 10000) / 100.0

        # Assign based on rollout percentage
        if percentage < self.config.l2_rollout_percentage:
            return DetectorMode.L1_AND_L2
        else:
            return DetectorMode.L1_ONLY

    def record_outcome(
        self,
        mode: DetectorMode,
        customer_id: str | None,
        detected_threat: bool,
        processing_time_ms: float
    ) -> None:
        """Record A/B test outcome for analysis.

        Args:
            mode: Which mode was used
            customer_id: Customer identifier
            detected_threat: Whether a threat was detected
            processing_time_ms: Processing time in milliseconds
        """
        # In production, this would send to analytics
        logger.info(
            f"AB test outcome: mode={mode.value}, "
            f"customer={customer_id or 'anonymous'}, "
            f"threat={detected_threat}, "
            f"time_ms={processing_time_ms:.2f}"
        )

    def get_cohort_stats(self) -> dict:
        """Get current cohort statistics.

        Returns:
            Statistics about cohort assignments
        """
        l1_only_count = sum(
            1 for mode in self._cohort_cache.values()
            if mode == DetectorMode.L1_ONLY
        )
        l1_l2_count = sum(
            1 for mode in self._cohort_cache.values()
            if mode == DetectorMode.L1_AND_L2
        )

        total = len(self._cohort_cache)

        return {
            "total_assignments": total,
            "l1_only": l1_only_count,
            "l1_and_l2": l1_l2_count,
            "l1_only_percentage": (l1_only_count / total * 100) if total > 0 else 0,
            "l1_and_l2_percentage": (l1_l2_count / total * 100) if total > 0 else 0,
            "config_rollout_percentage": self.config.l2_rollout_percentage,
        }

    def clear_cache(self) -> None:
        """Clear cohort assignment cache."""
        self._cohort_cache.clear()
        logger.debug("Cohort cache cleared")