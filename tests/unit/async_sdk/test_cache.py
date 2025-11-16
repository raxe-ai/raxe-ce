"""Unit tests for async LRU cache."""
import asyncio

import pytest

from raxe.async_sdk.cache import AsyncLRUCache, ScanResultCache


@pytest.mark.asyncio
class TestAsyncLRUCache:
    """Tests for AsyncLRUCache."""

    async def test_basic_get_set(self):
        """Test basic cache operations."""
        cache: AsyncLRUCache[str] = AsyncLRUCache(maxsize=10)

        # Set value
        await cache.set("key1", "value1")

        # Get value
        value = await cache.get("key1")
        assert value == "value1"

        # Check stats
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 0
        assert stats["size"] == 1

    async def test_cache_miss(self):
        """Test cache miss returns None."""
        cache: AsyncLRUCache[str] = AsyncLRUCache(maxsize=10)

        value = await cache.get("nonexistent")
        assert value is None

        stats = cache.stats()
        assert stats["misses"] == 1

    async def test_lru_eviction(self):
        """Test LRU eviction when maxsize reached."""
        cache: AsyncLRUCache[str] = AsyncLRUCache(maxsize=3)

        # Add 3 entries (at capacity)
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")

        assert await cache.size() == 3

        # Add 4th entry - should evict key1 (oldest)
        await cache.set("key4", "value4")

        assert await cache.size() == 3
        assert await cache.get("key1") is None  # Evicted
        assert await cache.get("key4") == "value4"  # Present

        stats = cache.stats()
        assert stats["evictions"] == 1

    async def test_lru_ordering(self):
        """Test LRU ordering with access."""
        cache: AsyncLRUCache[str] = AsyncLRUCache(maxsize=3)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")

        # Access key1 (makes it most recent)
        await cache.get("key1")

        # Add key4 - should evict key2 (now oldest)
        await cache.set("key4", "value4")

        assert await cache.get("key1") == "value1"  # Still present
        assert await cache.get("key2") is None  # Evicted
        assert await cache.get("key3") == "value3"  # Still present
        assert await cache.get("key4") == "value4"  # Present

    async def test_ttl_expiration(self):
        """Test TTL expiration."""
        cache: AsyncLRUCache[str] = AsyncLRUCache(maxsize=10, ttl=0.1)  # 100ms TTL

        await cache.set("key1", "value1")

        # Should be present immediately
        assert await cache.get("key1") == "value1"

        # Wait for expiration
        await asyncio.sleep(0.15)

        # Should be expired
        assert await cache.get("key1") is None

        stats = cache.stats()
        assert stats["expirations"] == 1

    async def test_update_existing_key(self):
        """Test updating existing key."""
        cache: AsyncLRUCache[str] = AsyncLRUCache(maxsize=10)

        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"

        # Update value
        await cache.set("key1", "value2")
        assert await cache.get("key1") == "value2"

        # Size should still be 1
        assert await cache.size() == 1

    async def test_delete(self):
        """Test deleting cache entry."""
        cache: AsyncLRUCache[str] = AsyncLRUCache(maxsize=10)

        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"

        # Delete key
        deleted = await cache.delete("key1")
        assert deleted is True

        # Should be gone
        assert await cache.get("key1") is None

        # Delete non-existent key
        deleted = await cache.delete("nonexistent")
        assert deleted is False

    async def test_clear(self):
        """Test clearing all entries."""
        cache: AsyncLRUCache[str] = AsyncLRUCache(maxsize=10)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")

        assert await cache.size() == 3

        # Clear all
        await cache.clear()

        assert await cache.size() == 0
        assert await cache.get("key1") is None

    async def test_stats_hit_rate(self):
        """Test hit rate calculation."""
        cache: AsyncLRUCache[str] = AsyncLRUCache(maxsize=10)

        await cache.set("key1", "value1")

        # 2 hits, 1 miss
        await cache.get("key1")  # Hit
        await cache.get("key1")  # Hit
        await cache.get("key2")  # Miss

        stats = cache.stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == pytest.approx(2/3, rel=0.01)

    async def test_concurrent_access(self):
        """Test thread safety with concurrent access."""
        cache: AsyncLRUCache[int] = AsyncLRUCache(maxsize=100)

        async def worker(i: int):
            for j in range(10):
                key = f"key_{i}_{j}"
                await cache.set(key, i * 10 + j)
                value = await cache.get(key)
                assert value == i * 10 + j

        # Run 10 concurrent workers
        tasks = [worker(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # All entries should be present (100 total)
        assert await cache.size() == 100

    async def test_invalid_maxsize(self):
        """Test invalid maxsize raises error."""
        with pytest.raises(ValueError, match="maxsize must be >= 1"):
            AsyncLRUCache(maxsize=0)

        with pytest.raises(ValueError, match="maxsize must be >= 1"):
            AsyncLRUCache(maxsize=-1)

    async def test_invalid_ttl(self):
        """Test invalid ttl raises error."""
        with pytest.raises(ValueError, match="ttl must be > 0 or None"):
            AsyncLRUCache(maxsize=10, ttl=0)

        with pytest.raises(ValueError, match="ttl must be > 0 or None"):
            AsyncLRUCache(maxsize=10, ttl=-1)

    async def test_reset_stats(self):
        """Test resetting statistics."""
        cache: AsyncLRUCache[str] = AsyncLRUCache(maxsize=10)

        await cache.set("key1", "value1")
        await cache.get("key1")  # Hit
        await cache.get("key2")  # Miss

        stats = cache.stats()
        assert stats["hits"] > 0
        assert stats["misses"] > 0

        # Reset stats
        cache.reset_stats()

        stats = cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0


@pytest.mark.asyncio
class TestScanResultCache:
    """Tests for ScanResultCache."""

    async def test_hash_based_lookup(self):
        """Test cache uses text hash as key."""
        cache = ScanResultCache(maxsize=10, ttl=300)

        # Create mock result
        result = {"has_threats": False, "severity": None}

        # Cache result
        await cache.set("test prompt", result)

        # Retrieve by same text
        cached = await cache.get("test prompt")
        assert cached == result

    async def test_different_text_different_cache(self):
        """Test different texts have different cache entries."""
        cache = ScanResultCache(maxsize=10, ttl=300)

        result1 = {"has_threats": False}
        result2 = {"has_threats": True}

        await cache.set("prompt1", result1)
        await cache.set("prompt2", result2)

        assert await cache.get("prompt1") == result1
        assert await cache.get("prompt2") == result2

    async def test_clear(self):
        """Test clearing scan result cache."""
        cache = ScanResultCache(maxsize=10, ttl=300)

        await cache.set("prompt1", {"has_threats": False})
        await cache.set("prompt2", {"has_threats": True})

        # Clear all
        await cache.clear()

        assert await cache.get("prompt1") is None
        assert await cache.get("prompt2") is None

    async def test_stats(self):
        """Test cache statistics."""
        cache = ScanResultCache(maxsize=10, ttl=300)

        await cache.set("prompt1", {"has_threats": False})
        await cache.get("prompt1")  # Hit
        await cache.get("prompt2")  # Miss

        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
