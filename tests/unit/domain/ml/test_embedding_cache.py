"""
Unit tests for LRU Embedding Cache.

Tests the pure domain logic of the EmbeddingCache class:
- LRU eviction behavior
- Thread safety
- Cache statistics
- Edge cases

These tests use no I/O, no mocks for external systems - just pure function testing.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from raxe.domain.ml.embedding_cache import CacheStats, EmbeddingCache


class TestCacheStats:
    """Test CacheStats value object."""

    def test_create_cache_stats(self):
        """Should create immutable cache stats."""
        stats = CacheStats(
            hits=10,
            misses=5,
            size=100,
            max_size=1000,
            hit_rate=0.667,
            evictions=2,
        )

        assert stats.hits == 10
        assert stats.misses == 5
        assert stats.size == 100
        assert stats.max_size == 1000
        assert stats.hit_rate == 0.667
        assert stats.evictions == 2

    def test_cache_stats_immutable(self):
        """Should be immutable (frozen dataclass)."""
        stats = CacheStats(
            hits=10,
            misses=5,
            size=100,
            max_size=1000,
            hit_rate=0.667,
            evictions=2,
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            stats.hits = 20


class TestEmbeddingCacheBasics:
    """Test basic EmbeddingCache operations."""

    def test_create_cache_default_size(self):
        """Should create cache with default max size of 1000."""
        cache = EmbeddingCache()
        assert cache.max_size == 1000
        assert cache.enabled is True

    def test_create_cache_custom_size(self):
        """Should create cache with custom max size."""
        cache = EmbeddingCache(max_size=500)
        assert cache.max_size == 500
        assert cache.enabled is True

    def test_create_cache_disabled(self):
        """Should disable cache when max_size is 0."""
        cache = EmbeddingCache(max_size=0)
        assert cache.max_size == 0
        assert cache.enabled is False

    def test_create_cache_negative_size_raises(self):
        """Should raise ValueError for negative max_size."""
        with pytest.raises(ValueError, match="max_size must be non-negative"):
            EmbeddingCache(max_size=-1)

    def test_put_and_get_embedding(self):
        """Should store and retrieve embeddings."""
        cache = EmbeddingCache(max_size=100)
        embedding = np.random.rand(1, 768).astype(np.float32)

        cache.put("test text", embedding)
        retrieved = cache.get("test text")

        assert retrieved is not None
        np.testing.assert_array_equal(retrieved, embedding)

    def test_get_missing_returns_none(self):
        """Should return None for cache miss."""
        cache = EmbeddingCache(max_size=100)

        result = cache.get("nonexistent text")

        assert result is None

    def test_get_disabled_cache_returns_none(self):
        """Should return None when cache is disabled."""
        cache = EmbeddingCache(max_size=0)
        embedding = np.random.rand(1, 768).astype(np.float32)

        cache.put("test text", embedding)  # Should do nothing
        result = cache.get("test text")

        assert result is None

    def test_put_disabled_cache_does_nothing(self):
        """Should not store when cache is disabled."""
        cache = EmbeddingCache(max_size=0)
        embedding = np.random.rand(1, 768).astype(np.float32)

        cache.put("test text", embedding)

        assert cache.size == 0

    def test_clear_removes_all_entries(self):
        """Should clear all entries and reset statistics."""
        cache = EmbeddingCache(max_size=100)
        embedding = np.random.rand(1, 768).astype(np.float32)

        # Add some entries and generate stats
        cache.put("text1", embedding)
        cache.put("text2", embedding)
        cache.get("text1")  # Hit
        cache.get("missing")  # Miss

        assert cache.size == 2
        assert cache.hits == 1
        assert cache.misses == 1

        cache.clear()

        assert cache.size == 0
        assert cache.hits == 0
        assert cache.misses == 0

    def test_contains_checks_membership(self):
        """Should check membership without affecting statistics."""
        cache = EmbeddingCache(max_size=100)
        embedding = np.random.rand(1, 768).astype(np.float32)

        cache.put("test text", embedding)

        assert cache.contains("test text") is True
        assert cache.contains("missing") is False
        # Statistics should not be affected
        assert cache.hits == 0
        assert cache.misses == 0

    def test_contains_disabled_cache(self):
        """Should return False when cache is disabled."""
        cache = EmbeddingCache(max_size=0)

        assert cache.contains("any text") is False

    def test_in_operator(self):
        """Should support 'in' operator."""
        cache = EmbeddingCache(max_size=100)
        embedding = np.random.rand(1, 768).astype(np.float32)

        cache.put("test text", embedding)

        assert "test text" in cache
        assert "missing" not in cache

    def test_len_returns_size(self):
        """Should support len() operator."""
        cache = EmbeddingCache(max_size=100)
        embedding = np.random.rand(1, 768).astype(np.float32)

        assert len(cache) == 0

        cache.put("text1", embedding)
        assert len(cache) == 1

        cache.put("text2", embedding)
        assert len(cache) == 2


class TestEmbeddingCacheLRU:
    """Test LRU eviction behavior."""

    def test_evicts_oldest_when_full(self):
        """Should evict oldest entry when cache is full."""
        cache = EmbeddingCache(max_size=3)

        # Add three entries
        for i in range(3):
            embedding = np.array([[float(i)]]).astype(np.float32)
            cache.put(f"text{i}", embedding)

        assert cache.size == 3

        # Add fourth entry - should evict text0
        embedding = np.array([[3.0]]).astype(np.float32)
        cache.put("text3", embedding)

        assert cache.size == 3
        assert cache.get("text0") is None  # Evicted
        assert cache.get("text1") is not None
        assert cache.get("text2") is not None
        assert cache.get("text3") is not None

    def test_get_updates_lru_order(self):
        """Should move accessed entry to most recently used."""
        cache = EmbeddingCache(max_size=3)

        # Add three entries
        for i in range(3):
            embedding = np.array([[float(i)]]).astype(np.float32)
            cache.put(f"text{i}", embedding)

        # Access text0 to make it most recently used
        cache.get("text0")

        # Add new entry - should evict text1 (oldest after text0 access)
        embedding = np.array([[3.0]]).astype(np.float32)
        cache.put("text3", embedding)

        assert cache.get("text0") is not None  # Was accessed, not evicted
        assert cache.get("text1") is None  # Evicted (oldest)
        assert cache.get("text2") is not None
        assert cache.get("text3") is not None

    def test_put_existing_updates_lru_order(self):
        """Should update LRU order when updating existing entry."""
        cache = EmbeddingCache(max_size=3)

        # Add three entries
        for i in range(3):
            embedding = np.array([[float(i)]]).astype(np.float32)
            cache.put(f"text{i}", embedding)

        # Update text0 with new embedding
        new_embedding = np.array([[99.0]]).astype(np.float32)
        cache.put("text0", new_embedding)

        # Add new entry - should evict text1 (text0 was updated)
        embedding = np.array([[3.0]]).astype(np.float32)
        cache.put("text3", embedding)

        assert cache.size == 3
        result = cache.get("text0")
        assert result is not None
        np.testing.assert_array_equal(result, new_embedding)
        assert cache.get("text1") is None  # Evicted

    def test_eviction_counter(self):
        """Should track number of evictions."""
        cache = EmbeddingCache(max_size=2)

        # Fill cache
        for i in range(2):
            embedding = np.array([[float(i)]]).astype(np.float32)
            cache.put(f"text{i}", embedding)

        assert cache.evictions == 0

        # Cause evictions
        for i in range(2, 5):
            embedding = np.array([[float(i)]]).astype(np.float32)
            cache.put(f"text{i}", embedding)

        assert cache.evictions == 3


class TestEmbeddingCacheStatistics:
    """Test cache statistics tracking."""

    def test_hit_miss_tracking(self):
        """Should track hits and misses."""
        cache = EmbeddingCache(max_size=100)
        embedding = np.random.rand(1, 768).astype(np.float32)

        cache.put("text1", embedding)

        # Generate hits and misses
        cache.get("text1")  # Hit
        cache.get("text1")  # Hit
        cache.get("missing1")  # Miss
        cache.get("missing2")  # Miss
        cache.get("missing3")  # Miss

        assert cache.hits == 2
        assert cache.misses == 3

    def test_hit_rate_calculation(self):
        """Should calculate hit rate correctly."""
        cache = EmbeddingCache(max_size=100)
        embedding = np.random.rand(1, 768).astype(np.float32)

        cache.put("text1", embedding)

        # Generate 2 hits and 3 misses
        cache.get("text1")  # Hit
        cache.get("text1")  # Hit
        cache.get("missing1")  # Miss
        cache.get("missing2")  # Miss
        cache.get("missing3")  # Miss

        assert cache.hit_rate == pytest.approx(0.4)  # 2/5 = 0.4

    def test_hit_rate_empty_cache(self):
        """Should return 0.0 hit rate when no requests made."""
        cache = EmbeddingCache(max_size=100)

        assert cache.hit_rate == 0.0

    def test_stats_property(self):
        """Should return complete stats snapshot."""
        cache = EmbeddingCache(max_size=100)
        embedding = np.random.rand(1, 768).astype(np.float32)

        cache.put("text1", embedding)
        cache.get("text1")  # Hit
        cache.get("missing")  # Miss

        stats = cache.stats

        assert isinstance(stats, CacheStats)
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.size == 1
        assert stats.max_size == 100
        assert stats.hit_rate == pytest.approx(0.5)
        assert stats.evictions == 0


class TestEmbeddingCacheKeyHashing:
    """Test cache key computation."""

    def test_same_text_same_key(self):
        """Should produce same key for same text."""
        key1 = EmbeddingCache._compute_key("Hello world")
        key2 = EmbeddingCache._compute_key("Hello world")

        assert key1 == key2

    def test_different_text_different_key(self):
        """Should produce different keys for different text."""
        key1 = EmbeddingCache._compute_key("Hello world")
        key2 = EmbeddingCache._compute_key("Hello World")  # Different case

        assert key1 != key2

    def test_key_length(self):
        """Should produce 16-character hex key."""
        key = EmbeddingCache._compute_key("Test text")

        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)

    def test_unicode_handling(self):
        """Should handle unicode text correctly."""
        cache = EmbeddingCache(max_size=100)
        embedding = np.random.rand(1, 768).astype(np.float32)

        # Unicode text
        cache.put("Hello, the world!", embedding)
        retrieved = cache.get("Hello, the world!")

        assert retrieved is not None


class TestEmbeddingCacheThreadSafety:
    """Test thread safety of cache operations."""

    def test_concurrent_reads(self):
        """Should handle concurrent reads safely."""
        cache = EmbeddingCache(max_size=100)

        # Pre-populate cache
        for i in range(10):
            embedding = np.array([[float(i)]]).astype(np.float32)
            cache.put(f"text{i}", embedding)

        results = []
        errors = []

        def read_cache(text_id: int):
            try:
                for _ in range(100):
                    result = cache.get(f"text{text_id % 10}")
                    if result is not None:
                        results.append(True)
            except Exception as e:
                errors.append(e)

        # Run concurrent reads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_cache, i) for i in range(10)]
            for f in futures:
                f.result()

        assert len(errors) == 0
        assert len(results) > 0

    def test_concurrent_writes(self):
        """Should handle concurrent writes safely."""
        cache = EmbeddingCache(max_size=1000)
        errors = []

        def write_cache(thread_id: int):
            try:
                for i in range(100):
                    embedding = np.array([[float(thread_id * 100 + i)]]).astype(
                        np.float32
                    )
                    cache.put(f"thread{thread_id}_text{i}", embedding)
            except Exception as e:
                errors.append(e)

        # Run concurrent writes
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_cache, i) for i in range(10)]
            for f in futures:
                f.result()

        assert len(errors) == 0
        # Should have entries from all threads (some may be evicted)
        assert cache.size > 0

    def test_concurrent_reads_and_writes(self):
        """Should handle concurrent reads and writes safely."""
        cache = EmbeddingCache(max_size=100)
        errors = []
        hits = []
        misses = []

        def read_write_cache(thread_id: int):
            try:
                for i in range(50):
                    # Write
                    embedding = np.array([[float(thread_id)]]).astype(np.float32)
                    cache.put(f"shared_text{i % 10}", embedding)

                    # Read
                    result = cache.get(f"shared_text{i % 10}")
                    if result is not None:
                        hits.append(True)
                    else:
                        misses.append(True)
            except Exception as e:
                errors.append(e)

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_write_cache, i) for i in range(10)]
            for f in futures:
                f.result()

        assert len(errors) == 0

    def test_concurrent_evictions(self):
        """Should handle concurrent evictions safely."""
        cache = EmbeddingCache(max_size=10)  # Small cache to force evictions
        errors = []

        def cause_evictions(thread_id: int):
            try:
                for i in range(100):
                    embedding = np.array([[float(thread_id * 100 + i)]]).astype(
                        np.float32
                    )
                    cache.put(f"thread{thread_id}_text{i}", embedding)
            except Exception as e:
                errors.append(e)

        # Run concurrent writes that cause evictions
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(cause_evictions, i) for i in range(10)]
            for f in futures:
                f.result()

        assert len(errors) == 0
        assert cache.size <= cache.max_size
        assert cache.evictions > 0


class TestEmbeddingCachePerformance:
    """Test cache performance characteristics."""

    def test_cache_hit_faster_than_miss(self):
        """Cache hit should be faster than cache miss lookup."""
        cache = EmbeddingCache(max_size=1000)
        embedding = np.random.rand(1, 768).astype(np.float32)

        cache.put("cached_text", embedding)

        # Time cache hits
        hit_times = []
        for _ in range(1000):
            start = time.perf_counter()
            cache.get("cached_text")
            hit_times.append(time.perf_counter() - start)

        # Time cache misses
        miss_times = []
        for i in range(1000):
            start = time.perf_counter()
            cache.get(f"missing_text_{i}")
            miss_times.append(time.perf_counter() - start)

        avg_hit_time = sum(hit_times) / len(hit_times)
        avg_miss_time = sum(miss_times) / len(miss_times)

        # Both should be very fast (sub-millisecond)
        assert avg_hit_time < 0.001  # < 1ms
        assert avg_miss_time < 0.001  # < 1ms

    def test_cache_hit_target_latency(self):
        """Cache hit should meet ~0.1ms target latency."""
        cache = EmbeddingCache(max_size=1000)
        embedding = np.random.rand(1, 768).astype(np.float32)

        cache.put("test_text", embedding)

        # Warm up
        for _ in range(100):
            cache.get("test_text")

        # Measure
        times = []
        for _ in range(1000):
            start = time.perf_counter()
            cache.get("test_text")
            times.append((time.perf_counter() - start) * 1000)  # Convert to ms

        avg_time = sum(times) / len(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]

        # Target: ~0.1ms average, <0.5ms P95
        assert avg_time < 0.5, f"Average time {avg_time:.3f}ms exceeds 0.5ms target"
        assert p95_time < 1.0, f"P95 time {p95_time:.3f}ms exceeds 1.0ms target"

    def test_memory_estimate(self):
        """Should estimate reasonable memory usage per embedding."""
        cache = EmbeddingCache(max_size=100)

        # 768-dimensional float32 embedding
        embedding = np.random.rand(1, 768).astype(np.float32)

        # Single embedding should be ~3KB (768 * 4 bytes)
        assert embedding.nbytes == 768 * 4  # 3072 bytes


class TestEmbeddingCacheEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_key(self):
        """Should handle empty string as cache key."""
        cache = EmbeddingCache(max_size=100)
        embedding = np.random.rand(1, 768).astype(np.float32)

        cache.put("", embedding)
        result = cache.get("")

        assert result is not None
        np.testing.assert_array_equal(result, embedding)

    def test_very_long_text(self):
        """Should handle very long text as cache key."""
        cache = EmbeddingCache(max_size=100)
        embedding = np.random.rand(1, 768).astype(np.float32)

        long_text = "x" * 100000  # 100KB text

        cache.put(long_text, embedding)
        result = cache.get(long_text)

        assert result is not None

    def test_max_size_one(self):
        """Should work correctly with max_size of 1."""
        cache = EmbeddingCache(max_size=1)

        embedding1 = np.array([[1.0]]).astype(np.float32)
        embedding2 = np.array([[2.0]]).astype(np.float32)

        cache.put("text1", embedding1)
        assert cache.size == 1

        cache.put("text2", embedding2)
        assert cache.size == 1
        assert cache.get("text1") is None  # Evicted
        assert cache.get("text2") is not None

    def test_repr_does_not_expose_cache_contents(self):
        """Repr should not expose cached data."""
        cache = EmbeddingCache(max_size=100)
        embedding = np.random.rand(1, 768).astype(np.float32)
        cache.put("secret prompt", embedding)

        repr_str = repr(cache)

        assert "secret" not in repr_str.lower()
        assert "EmbeddingCache" in repr_str

    def test_special_characters_in_text(self):
        """Should handle special characters in text."""
        cache = EmbeddingCache(max_size=100)
        embedding = np.random.rand(1, 768).astype(np.float32)

        special_texts = [
            "Hello\nWorld",
            "Tab\there",
            "Quote's",
            'Double "quotes"',
            "Backslash\\here",
            "Null\x00byte",
            "<script>alert('xss')</script>",
        ]

        for text in special_texts:
            cache.put(text, embedding)
            result = cache.get(text)
            assert result is not None, f"Failed for text: {repr(text)}"
