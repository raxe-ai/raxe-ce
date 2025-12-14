"""Async-safe LRU cache for rules and scan results.

Provides thread-safe caching with TTL support for:
- Compiled rule patterns (avoid repeated compilation)
- Scan results (deduplicate identical prompts)

Performance targets:
- Cache hit rate: >80% for repeated prompts
- Cache overhead: <1ms per lookup
- Memory overhead: <100MB for default cache size
"""
import asyncio
import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class CacheEntry(Generic[T]):
    """Cache entry with value and expiration.

    Attributes:
        value: Cached value
        expires_at: Timestamp when entry expires (None for no expiration)
        created_at: Timestamp when entry was created
    """
    value: T
    expires_at: float | None
    created_at: float

    def is_expired(self) -> bool:
        """Check if entry has expired.

        Returns:
            True if entry is expired
        """
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class AsyncLRUCache(Generic[T]):
    """Thread-safe async LRU cache with TTL support.

    Features:
    - LRU eviction when maxsize reached
    - Optional TTL for cache entries
    - Thread-safe with asyncio.Lock
    - Cache metrics (hits, misses, evictions)

    Example usage:
        cache = AsyncLRUCache[str](maxsize=1000, ttl=3600)

        # Set value
        await cache.set("key", "value")

        # Get value
        value = await cache.get("key")

        # Check metrics
        stats = cache.stats()
        print(f"Hit rate: {stats['hit_rate']:.2%}")
    """

    def __init__(
        self,
        maxsize: int = 1000,
        ttl: float | None = None,
    ):
        """Initialize async LRU cache.

        Args:
            maxsize: Maximum number of entries (default: 1000)
            ttl: Time-to-live in seconds (None for no expiration)
        """
        if maxsize < 1:
            raise ValueError(f"maxsize must be >= 1, got {maxsize}")
        if ttl is not None and ttl <= 0:
            raise ValueError(f"ttl must be > 0 or None, got {ttl}")

        self._maxsize = maxsize
        self._ttl = ttl
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = asyncio.Lock()

        # Metrics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

    async def get(self, key: str) -> T | None:
        """Get cached value if exists and not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            # Check expiration
            if entry.is_expired():
                # Remove expired entry
                del self._cache[key]
                self._expirations += 1
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value

    async def set(self, key: str, value: T) -> None:
        """Cache value with optional TTL.

        Args:
            key: Cache key
            value: Value to cache
        """
        async with self._lock:
            now = time.time()
            expires_at = now + self._ttl if self._ttl else None

            entry = CacheEntry(
                value=value,
                expires_at=expires_at,
                created_at=now,
            )

            # If key exists, update in place
            if key in self._cache:
                self._cache[key] = entry
                self._cache.move_to_end(key)
                return

            # If at capacity, evict LRU
            if len(self._cache) >= self._maxsize:
                # Remove oldest (first) entry
                self._cache.popitem(last=False)
                self._evictions += 1

            # Add new entry
            self._cache[key] = entry

    async def delete(self, key: str) -> bool:
        """Delete cached entry.

        Args:
            key: Cache key

        Returns:
            True if entry was deleted, False if not found
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all cached entries."""
        async with self._lock:
            self._cache.clear()

    async def size(self) -> int:
        """Get current cache size.

        Returns:
            Number of entries in cache
        """
        async with self._lock:
            return len(self._cache)

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache metrics:
                - hits: Cache hits
                - misses: Cache misses
                - evictions: LRU evictions
                - expirations: TTL expirations
                - hit_rate: Cache hit rate (0.0 to 1.0)
                - size: Current cache size
                - maxsize: Maximum cache size
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "expirations": self._expirations,
            "hit_rate": hit_rate,
            "size": len(self._cache),
            "maxsize": self._maxsize,
        }

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0


class ScanResultCache:
    """Specialized cache for scan results.

    Uses text hash as key to deduplicate identical prompts.
    """

    def __init__(self, maxsize: int = 1000, ttl: float = 300.0):
        """Initialize scan result cache.

        Args:
            maxsize: Maximum number of cached results (default: 1000)
            ttl: Time-to-live in seconds (default: 300 = 5 minutes)
        """
        self._cache: AsyncLRUCache[Any] = AsyncLRUCache(maxsize=maxsize, ttl=ttl)

    def _hash_text(self, text: str) -> str:
        """Create hash of text for cache key.

        Args:
            text: Text to hash

        Returns:
            SHA256 hash (hex encoded)
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def get(self, text: str) -> Any | None:
        """Get cached scan result for text.

        Args:
            text: Text to lookup

        Returns:
            Cached scan result or None
        """
        key = self._hash_text(text)
        return await self._cache.get(key)

    async def set(self, text: str, result: Any) -> None:
        """Cache scan result for text.

        Args:
            text: Text that was scanned
            result: Scan result to cache
        """
        key = self._hash_text(text)
        await self._cache.set(key, result)

    async def clear(self) -> None:
        """Clear all cached results."""
        await self._cache.clear()

    async def size(self) -> int:
        """Get current cache size.

        Returns:
            Number of cached results
        """
        return await self._cache.size()

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache metrics
        """
        return self._cache.stats()
