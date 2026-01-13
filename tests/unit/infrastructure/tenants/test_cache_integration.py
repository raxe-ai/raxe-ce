"""Tests for PolicyCache integration into the scan path.

Verifies that:
- Cache is used for policy lookups
- Cache reduces file I/O
- Cache invalidation works correctly
"""

import pytest

from raxe.domain.tenants.models import PolicyMode, TenantPolicy
from raxe.infrastructure.tenants.yaml_repository import (
    CachedPolicyRepository,
    YamlPolicyRepository,
)


@pytest.fixture
def sample_policy():
    """Create a sample policy for testing."""
    return TenantPolicy(
        policy_id="strict",
        name="Strict Mode",
        tenant_id="acme",
        mode=PolicyMode.STRICT,
        blocking_enabled=True,
        block_severity_threshold="MEDIUM",
        block_confidence_threshold=0.5,
    )


@pytest.fixture
def policy_repo_with_policy(tmp_path, sample_policy):
    """Create a policy repository with a saved policy."""
    repo = YamlPolicyRepository(tmp_path)
    repo.save_policy(sample_policy)
    return repo


class TestCachedPolicyRepository:
    """Tests for CachedPolicyRepository wrapper."""

    def test_cache_hit_avoids_file_io(self, tmp_path, sample_policy):
        """Second lookup should hit cache, not file system."""
        base_repo = YamlPolicyRepository(tmp_path)
        base_repo.save_policy(sample_policy)

        cached_repo = CachedPolicyRepository(base_repo)

        # First call - cache miss, reads from file
        policy1 = cached_repo.get_policy("strict", "acme")
        assert policy1 is not None
        assert cached_repo.cache_stats()["misses"] == 1
        assert cached_repo.cache_stats()["hits"] == 0

        # Second call - cache hit, no file I/O
        policy2 = cached_repo.get_policy("strict", "acme")
        assert policy2 is not None
        assert cached_repo.cache_stats()["hits"] == 1
        assert cached_repo.cache_stats()["misses"] == 1

        # Same object reference
        assert policy1 == policy2

    def test_cache_miss_reads_from_base(self, tmp_path, sample_policy):
        """Cache miss delegates to base repository."""
        base_repo = YamlPolicyRepository(tmp_path)
        base_repo.save_policy(sample_policy)

        cached_repo = CachedPolicyRepository(base_repo)

        # First lookup - miss
        policy = cached_repo.get_policy("strict", "acme")
        assert policy is not None
        assert policy.policy_id == "strict"

    def test_cache_key_includes_tenant_id(self, tmp_path):
        """Different tenants should have different cache keys."""
        # Create two policies with same ID but different tenants
        policy_acme = TenantPolicy(
            policy_id="custom",
            name="Acme Custom",
            tenant_id="acme",
            mode=PolicyMode.BALANCED,
            blocking_enabled=True,
        )
        policy_bunny = TenantPolicy(
            policy_id="custom",
            name="Bunny Custom",
            tenant_id="bunny",
            mode=PolicyMode.STRICT,
            blocking_enabled=True,
        )

        base_repo = YamlPolicyRepository(tmp_path)
        base_repo.save_policy(policy_acme)
        base_repo.save_policy(policy_bunny)

        cached_repo = CachedPolicyRepository(base_repo)

        # Get both policies
        p1 = cached_repo.get_policy("custom", "acme")
        p2 = cached_repo.get_policy("custom", "bunny")

        # Should be different policies
        assert p1.tenant_id == "acme"
        assert p2.tenant_id == "bunny"
        assert p1.mode != p2.mode

    def test_save_invalidates_cache(self, tmp_path, sample_policy):
        """Saving a policy should invalidate cache entry."""
        base_repo = YamlPolicyRepository(tmp_path)
        base_repo.save_policy(sample_policy)

        cached_repo = CachedPolicyRepository(base_repo)

        # Populate cache
        cached_repo.get_policy("strict", "acme")
        assert cached_repo.cache_stats()["size"] == 1

        # Update policy
        updated_policy = TenantPolicy(
            policy_id="strict",
            name="Updated Strict",
            tenant_id="acme",
            mode=PolicyMode.STRICT,
            blocking_enabled=False,  # Changed
            block_severity_threshold="MEDIUM",
            block_confidence_threshold=0.5,
        )
        cached_repo.save_policy(updated_policy)

        # Cache should be invalidated for this entry
        # Next get should return updated policy
        policy = cached_repo.get_policy("strict", "acme")
        assert policy.blocking_enabled is False

    def test_delete_invalidates_cache(self, tmp_path, sample_policy):
        """Deleting a policy should invalidate cache entry."""
        base_repo = YamlPolicyRepository(tmp_path)
        base_repo.save_policy(sample_policy)

        cached_repo = CachedPolicyRepository(base_repo)

        # Populate cache
        cached_repo.get_policy("strict", "acme")
        assert cached_repo.cache_stats()["size"] == 1

        # Delete policy
        cached_repo.delete_policy("strict", "acme")

        # Cache entry should be gone
        policy = cached_repo.get_policy("strict", "acme")
        assert policy is None

    def test_global_presets_cached(self, tmp_path):
        """Global presets (tenant_id=None) should be cacheable."""
        from raxe.domain.tenants.presets import POLICY_BALANCED

        base_repo = YamlPolicyRepository(tmp_path)
        cached_repo = CachedPolicyRepository(base_repo)

        # Pre-populate with global preset
        cached_repo.cache.set("balanced:None", POLICY_BALANCED)

        # Lookup should hit cache
        policy = cached_repo.get_policy("balanced", None)
        assert policy is not None
        assert policy.policy_id == "balanced"
        assert cached_repo.cache_stats()["hits"] == 1

    def test_cache_size_limit_respected(self, tmp_path):
        """Cache should evict entries when maxsize is reached."""
        base_repo = YamlPolicyRepository(tmp_path)
        cached_repo = CachedPolicyRepository(base_repo, cache_maxsize=3)

        # Create and save 5 policies
        for i in range(5):
            policy = TenantPolicy(
                policy_id=f"policy-{i}",
                name=f"Policy {i}",
                tenant_id="acme",
                mode=PolicyMode.BALANCED,
                blocking_enabled=True,
            )
            base_repo.save_policy(policy)
            cached_repo.get_policy(f"policy-{i}", "acme")

        # Cache should only have 3 entries
        assert cached_repo.cache_stats()["size"] <= 3

    def test_clear_cache(self, tmp_path, sample_policy):
        """clear_cache should empty the cache."""
        base_repo = YamlPolicyRepository(tmp_path)
        base_repo.save_policy(sample_policy)

        cached_repo = CachedPolicyRepository(base_repo)
        cached_repo.get_policy("strict", "acme")

        assert cached_repo.cache_stats()["size"] == 1

        cached_repo.clear_cache()

        assert cached_repo.cache_stats()["size"] == 0


class TestPolicyCachePerformance:
    """Performance-focused tests for cache behavior."""

    def test_cache_lookup_is_fast(self, tmp_path, sample_policy):
        """Cache lookup should be under 1ms."""
        import time

        base_repo = YamlPolicyRepository(tmp_path)
        base_repo.save_policy(sample_policy)

        cached_repo = CachedPolicyRepository(base_repo)

        # Prime the cache
        cached_repo.get_policy("strict", "acme")

        # Time 1000 cache lookups
        start = time.perf_counter()
        for _ in range(1000):
            cached_repo.get_policy("strict", "acme")
        elapsed = time.perf_counter() - start

        avg_lookup_ms = (elapsed / 1000) * 1000
        assert avg_lookup_ms < 1, f"Average lookup {avg_lookup_ms:.3f}ms exceeds 1ms"

    def test_high_cache_hit_rate_with_repeated_lookups(self, tmp_path, sample_policy):
        """Repeated lookups should achieve >95% hit rate."""
        base_repo = YamlPolicyRepository(tmp_path)
        base_repo.save_policy(sample_policy)

        cached_repo = CachedPolicyRepository(base_repo)

        # Simulate realistic usage pattern
        for _ in range(100):
            cached_repo.get_policy("strict", "acme")

        stats = cached_repo.cache_stats()
        assert stats["hit_rate"] >= 0.95, f"Hit rate {stats['hit_rate']} below 95%"
