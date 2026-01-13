"""Tests for PolicyCache.

TDD: Tests written BEFORE implementation.
"""

import time

import pytest

from raxe.domain.tenants.models import PolicyMode, TenantPolicy
from raxe.infrastructure.tenants.cache import PolicyCache


@pytest.fixture
def sample_policy() -> TenantPolicy:
    """Create a sample policy for testing."""
    return TenantPolicy(
        policy_id="test_policy",
        name="Test Policy",
        tenant_id="acme",
        mode=PolicyMode.BALANCED,
        blocking_enabled=True,
    )


@pytest.fixture
def sample_policies() -> dict[str, TenantPolicy]:
    """Create sample policies for testing."""
    return {
        "balanced": TenantPolicy(
            policy_id="balanced",
            name="Balanced",
            tenant_id=None,
            mode=PolicyMode.BALANCED,
            blocking_enabled=True,
        ),
        "strict": TenantPolicy(
            policy_id="strict",
            name="Strict",
            tenant_id=None,
            mode=PolicyMode.STRICT,
            blocking_enabled=True,
        ),
        "monitor": TenantPolicy(
            policy_id="monitor",
            name="Monitor",
            tenant_id=None,
            mode=PolicyMode.MONITOR,
            blocking_enabled=False,
        ),
    }


class TestPolicyCache:
    """Tests for PolicyCache."""

    def test_init_with_default_maxsize(self) -> None:
        """Cache initializes with default maxsize."""
        cache = PolicyCache()
        assert cache.maxsize == 128

    def test_init_with_custom_maxsize(self) -> None:
        """Cache initializes with custom maxsize."""
        cache = PolicyCache(maxsize=256)
        assert cache.maxsize == 256

    def test_get_nonexistent_returns_none(self) -> None:
        """Getting nonexistent policy returns None."""
        cache = PolicyCache()
        assert cache.get("nonexistent") is None

    def test_set_and_get_policy(self, sample_policy: TenantPolicy) -> None:
        """Can set and get a policy."""
        cache = PolicyCache()
        cache.set(sample_policy.policy_id, sample_policy)
        retrieved = cache.get(sample_policy.policy_id)

        assert retrieved is not None
        assert retrieved.policy_id == sample_policy.policy_id
        assert retrieved.mode == PolicyMode.BALANCED

    def test_set_overwrites_existing(self, sample_policy: TenantPolicy) -> None:
        """Setting same key overwrites existing."""
        cache = PolicyCache()
        cache.set("policy1", sample_policy)

        new_policy = TenantPolicy(
            policy_id="policy1",
            name="Updated Policy",
            tenant_id="acme",
            mode=PolicyMode.STRICT,
            blocking_enabled=True,
        )
        cache.set("policy1", new_policy)

        retrieved = cache.get("policy1")
        assert retrieved is not None
        assert retrieved.mode == PolicyMode.STRICT

    def test_delete_removes_policy(self, sample_policy: TenantPolicy) -> None:
        """Can delete a policy from cache."""
        cache = PolicyCache()
        cache.set(sample_policy.policy_id, sample_policy)
        assert cache.get(sample_policy.policy_id) is not None

        cache.delete(sample_policy.policy_id)
        assert cache.get(sample_policy.policy_id) is None

    def test_delete_nonexistent_no_error(self) -> None:
        """Deleting nonexistent key does not raise error."""
        cache = PolicyCache()
        cache.delete("nonexistent")  # Should not raise

    def test_clear_removes_all(self, sample_policies: dict[str, TenantPolicy]) -> None:
        """Clear removes all cached policies."""
        cache = PolicyCache()
        for policy_id, policy in sample_policies.items():
            cache.set(policy_id, policy)

        assert len(cache) == 3
        cache.clear()
        assert len(cache) == 0

    def test_len_returns_cache_size(self, sample_policies: dict[str, TenantPolicy]) -> None:
        """len() returns number of cached items."""
        cache = PolicyCache()
        assert len(cache) == 0

        for policy_id, policy in sample_policies.items():
            cache.set(policy_id, policy)

        assert len(cache) == 3

    def test_contains_check(self, sample_policy: TenantPolicy) -> None:
        """Can check if policy exists in cache."""
        cache = PolicyCache()
        assert "test_policy" not in cache

        cache.set(sample_policy.policy_id, sample_policy)
        assert "test_policy" in cache

    def test_lru_eviction(self) -> None:
        """Oldest entries are evicted when maxsize is reached."""
        cache = PolicyCache(maxsize=2)

        policy1 = TenantPolicy(
            policy_id="p1",
            name="Policy 1",
            tenant_id=None,
            mode=PolicyMode.MONITOR,
            blocking_enabled=False,
        )
        policy2 = TenantPolicy(
            policy_id="p2",
            name="Policy 2",
            tenant_id=None,
            mode=PolicyMode.BALANCED,
            blocking_enabled=True,
        )
        policy3 = TenantPolicy(
            policy_id="p3",
            name="Policy 3",
            tenant_id=None,
            mode=PolicyMode.STRICT,
            blocking_enabled=True,
        )

        cache.set("p1", policy1)
        cache.set("p2", policy2)
        assert len(cache) == 2

        # Adding p3 should evict p1 (least recently used)
        cache.set("p3", policy3)
        assert len(cache) == 2
        assert cache.get("p1") is None  # Evicted
        assert cache.get("p2") is not None
        assert cache.get("p3") is not None

    def test_lru_access_updates_recency(self) -> None:
        """Accessing an entry updates its recency."""
        cache = PolicyCache(maxsize=2)

        policy1 = TenantPolicy(
            policy_id="p1",
            name="Policy 1",
            tenant_id=None,
            mode=PolicyMode.MONITOR,
            blocking_enabled=False,
        )
        policy2 = TenantPolicy(
            policy_id="p2",
            name="Policy 2",
            tenant_id=None,
            mode=PolicyMode.BALANCED,
            blocking_enabled=True,
        )
        policy3 = TenantPolicy(
            policy_id="p3",
            name="Policy 3",
            tenant_id=None,
            mode=PolicyMode.STRICT,
            blocking_enabled=True,
        )

        cache.set("p1", policy1)
        cache.set("p2", policy2)

        # Access p1 to make it more recently used
        cache.get("p1")

        # Adding p3 should evict p2 (now least recently used)
        cache.set("p3", policy3)
        assert cache.get("p1") is not None  # Kept (recently accessed)
        assert cache.get("p2") is None  # Evicted
        assert cache.get("p3") is not None

    def test_get_or_set(self, sample_policy: TenantPolicy) -> None:
        """get_or_set returns cached value or sets new value."""
        cache = PolicyCache()

        # First call should call factory and set
        call_count = 0

        def factory() -> TenantPolicy:
            nonlocal call_count
            call_count += 1
            return sample_policy

        result1 = cache.get_or_set("test_policy", factory)
        assert result1.policy_id == "test_policy"
        assert call_count == 1

        # Second call should return cached, not call factory
        result2 = cache.get_or_set("test_policy", factory)
        assert result2.policy_id == "test_policy"
        assert call_count == 1  # Factory not called again

    def test_stats_tracking(self, sample_policy: TenantPolicy) -> None:
        """Cache tracks hits and misses."""
        cache = PolicyCache()

        # Miss
        cache.get("nonexistent")

        # Set and hit
        cache.set(sample_policy.policy_id, sample_policy)
        cache.get(sample_policy.policy_id)
        cache.get(sample_policy.policy_id)

        stats = cache.stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == pytest.approx(2 / 3)

    def test_stats_after_clear(self, sample_policy: TenantPolicy) -> None:
        """Stats are reset after clear."""
        cache = PolicyCache()
        cache.set(sample_policy.policy_id, sample_policy)
        cache.get(sample_policy.policy_id)

        cache.clear()
        stats = cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0


class TestPolicyCachePerformance:
    """Performance tests for PolicyCache."""

    def test_lookup_under_1ms(self) -> None:
        """Policy lookup must be under 1ms (P95)."""
        cache = PolicyCache(maxsize=1000)

        # Pre-populate cache
        for i in range(100):
            policy = TenantPolicy(
                policy_id=f"policy_{i}",
                name=f"Policy {i}",
                tenant_id=None,
                mode=PolicyMode.BALANCED,
                blocking_enabled=True,
            )
            cache.set(f"policy_{i}", policy)

        # Measure lookup times
        times = []
        for _ in range(1000):
            start = time.perf_counter()
            cache.get("policy_50")  # Lookup middle entry
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)

        times.sort()
        p95 = times[949]  # 95th percentile
        p99 = times[989]  # 99th percentile

        assert p95 < 1.0, f"P95 lookup time {p95:.3f}ms exceeds 1ms target"
        assert p99 < 2.0, f"P99 lookup time {p99:.3f}ms exceeds 2ms target"

    def test_set_under_1ms(self) -> None:
        """Policy set must be under 1ms (P95)."""
        cache = PolicyCache(maxsize=1000)

        policy = TenantPolicy(
            policy_id="test",
            name="Test",
            tenant_id=None,
            mode=PolicyMode.BALANCED,
            blocking_enabled=True,
        )

        times = []
        for i in range(1000):
            start = time.perf_counter()
            cache.set(f"policy_{i}", policy)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)

        times.sort()
        p95 = times[949]

        assert p95 < 1.0, f"P95 set time {p95:.3f}ms exceeds 1ms target"
