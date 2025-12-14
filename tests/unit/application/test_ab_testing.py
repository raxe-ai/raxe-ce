"""Tests for A/B testing framework."""
import pytest

from raxe.application.ab_testing import ABTestConfig, ABTestManager, DetectorMode


class TestABTestConfig:
    """Test A/B test configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ABTestConfig()
        assert config.l2_rollout_percentage == 10.0
        assert config.enabled is True
        assert config.customer_overrides == {}

    def test_custom_config(self):
        """Test custom configuration."""
        config = ABTestConfig(
            l2_rollout_percentage=25.0,
            enabled=False,
            customer_overrides={"customer1": DetectorMode.L1_ONLY}
        )
        assert config.l2_rollout_percentage == 25.0
        assert config.enabled is False
        assert "customer1" in config.customer_overrides

    def test_invalid_rollout_percentage(self):
        """Test rollout percentage validation."""
        with pytest.raises(ValueError, match="between 0 and 100"):
            ABTestConfig(l2_rollout_percentage=101)

        with pytest.raises(ValueError, match="between 0 and 100"):
            ABTestConfig(l2_rollout_percentage=-1)


class TestABTestManager:
    """Test A/B test manager."""

    def test_disabled_ab_test(self):
        """Test behavior when A/B testing is disabled."""
        config = ABTestConfig(enabled=False)
        manager = ABTestManager(config)

        # Should always return L1+L2 when disabled
        assert manager.get_detector_mode("user1") == DetectorMode.L1_AND_L2
        assert manager.get_detector_mode("user2") == DetectorMode.L1_AND_L2

    def test_customer_override(self):
        """Test customer-specific overrides."""
        config = ABTestConfig(
            customer_overrides={
                "premium_customer": DetectorMode.L1_AND_L2,
                "test_customer": DetectorMode.L1_ONLY
            }
        )
        manager = ABTestManager(config)

        assert manager.get_detector_mode("premium_customer") == DetectorMode.L1_AND_L2
        assert manager.get_detector_mode("test_customer") == DetectorMode.L1_ONLY
        # Other customers get normal assignment
        mode = manager.get_detector_mode("regular_customer")
        assert mode in [DetectorMode.L1_ONLY, DetectorMode.L1_AND_L2]

    def test_consistent_assignment(self):
        """Test that same customer gets consistent assignment."""
        config = ABTestConfig(l2_rollout_percentage=50)
        manager = ABTestManager(config)

        # Same customer should always get same mode
        first_mode = manager.get_detector_mode("customer123")
        for _ in range(10):
            assert manager.get_detector_mode("customer123") == first_mode

    def test_rollout_distribution(self):
        """Test that rollout percentage is approximately correct."""
        config = ABTestConfig(l2_rollout_percentage=30)
        manager = ABTestManager(config)

        # Test with many customers
        l2_count = 0
        total = 1000
        for i in range(total):
            mode = manager.get_detector_mode(f"customer_{i}")
            if mode == DetectorMode.L1_AND_L2:
                l2_count += 1

        # Should be approximately 30% (with some tolerance)
        percentage = (l2_count / total) * 100
        assert 25 <= percentage <= 35, f"Got {percentage}% L2 assignments"

    def test_session_fallback(self):
        """Test session ID is used when customer ID not provided."""
        config = ABTestConfig(l2_rollout_percentage=50)
        manager = ABTestManager(config)

        # Session ID should be used consistently
        mode = manager.get_detector_mode(session_id="session123")
        for _ in range(5):
            assert manager.get_detector_mode(session_id="session123") == mode

    def test_anonymous_fallback(self):
        """Test anonymous mode when no IDs provided."""
        config = ABTestConfig(l2_rollout_percentage=100)
        manager = ABTestManager(config)

        # Anonymous should get consistent assignment
        mode = manager.get_detector_mode()
        assert mode == DetectorMode.L1_AND_L2  # 100% rollout

    def test_record_outcome(self):
        """Test outcome recording doesn't raise errors."""
        manager = ABTestManager()

        # Should not raise
        manager.record_outcome(
            mode=DetectorMode.L1_AND_L2,
            customer_id="customer1",
            detected_threat=True,
            processing_time_ms=15.5
        )

    def test_cohort_stats(self):
        """Test cohort statistics calculation."""
        config = ABTestConfig(l2_rollout_percentage=50)
        manager = ABTestManager(config)

        # Generate some assignments
        for i in range(100):
            manager.get_detector_mode(f"customer_{i}")

        stats = manager.get_cohort_stats()

        assert stats["total_assignments"] == 100
        assert stats["l1_only"] + stats["l1_and_l2"] == 100
        assert stats["config_rollout_percentage"] == 50

        # Percentages should add to 100
        assert abs(stats["l1_only_percentage"] + stats["l1_and_l2_percentage"] - 100) < 0.1

    def test_cache_clearing(self):
        """Test cache clearing."""
        manager = ABTestManager()

        # Create some assignments
        manager.get_detector_mode("customer1")
        manager.get_detector_mode("customer2")

        stats_before = manager.get_cohort_stats()
        assert stats_before["total_assignments"] == 2

        # Clear cache
        manager.clear_cache()

        stats_after = manager.get_cohort_stats()
        assert stats_after["total_assignments"] == 0

    def test_deterministic_hashing(self):
        """Test that hashing is deterministic across instances."""
        config = ABTestConfig(l2_rollout_percentage=50)

        # Create two separate managers
        manager1 = ABTestManager(config)
        manager2 = ABTestManager(config)

        # Same customer should get same assignment in both
        customers = ["user_a", "user_b", "user_c", "premium_123"]
        for customer in customers:
            assert manager1.get_detector_mode(customer) == manager2.get_detector_mode(customer)