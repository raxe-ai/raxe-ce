"""
LRU Embedding Cache for L2 ML Inference

Thread-safe LRU cache for storing text embeddings to speed up repeated
inference on the same or similar prompts.

Performance characteristics:
- Cache hit: ~0.1ms (vs ~2ms for embedding generation)
- Memory: ~3KB per cached embedding (768 floats * 4 bytes)
- Thread-safe: Uses threading.Lock for concurrent access

This module is part of the domain layer and contains PURE logic:
- No I/O operations (database, network, file system)
- No logging (statistics are returned, not logged)
- Deterministic behavior for testability

Example:
    cache = EmbeddingCache(max_size=1000)

    # Check cache before generating embeddings
    cached = cache.get("Hello world")
    if cached is None:
        embedding = generate_embedding("Hello world")
        cache.put("Hello world", embedding)
    else:
        embedding = cached

    # Check cache statistics
    print(f"Hit rate: {cache.hit_rate:.1%}")
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True)
class CacheStats:
    """
    Immutable cache statistics snapshot.

    Attributes:
        hits: Number of cache hits
        misses: Number of cache misses
        size: Current number of entries in cache
        max_size: Maximum cache capacity
        hit_rate: Ratio of hits to total requests (0.0-1.0)
        evictions: Number of entries evicted due to capacity
    """

    hits: int
    misses: int
    size: int
    max_size: int
    hit_rate: float
    evictions: int


@dataclass
class EmbeddingCache:
    """
    Thread-safe LRU cache for text embeddings.

    Uses an OrderedDict for O(1) LRU operations and a threading.Lock
    for thread safety. Cache keys are derived from SHA256 hashes of
    the input text (first 16 characters for compactness).

    Performance targets:
    - Cache hit: ~0.1ms
    - Cache miss overhead: ~0.01ms
    - Memory per entry: ~3KB (768 floats * 4 bytes)

    Attributes:
        max_size: Maximum number of entries (default 1000)
                  Set to 0 to disable caching

    Example:
        # Create cache with default size
        cache = EmbeddingCache()

        # Create cache with custom size
        cache = EmbeddingCache(max_size=5000)

        # Disable caching
        cache = EmbeddingCache(max_size=0)

        # Use cache
        embedding = cache.get("test prompt")
        if embedding is None:
            embedding = model.encode("test prompt")
            cache.put("test prompt", embedding)

        # Check statistics
        stats = cache.stats
        print(f"Hit rate: {stats.hit_rate:.1%}")
    """

    max_size: int = 1000

    # Private fields initialized in __post_init__
    _cache: OrderedDict[str, "np.ndarray"] = field(
        default_factory=OrderedDict, repr=False
    )
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _hits: int = field(default=0, repr=False)
    _misses: int = field(default=0, repr=False)
    _evictions: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.max_size < 0:
            raise ValueError("max_size must be non-negative")

    @staticmethod
    def _compute_key(text: str) -> str:
        """
        Compute cache key from text using SHA256 hash.

        Uses first 16 characters of hex digest for compactness while
        maintaining extremely low collision probability.

        Args:
            text: Input text to hash

        Returns:
            16-character hex string cache key
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    @property
    def enabled(self) -> bool:
        """Return True if caching is enabled (max_size > 0)."""
        return self.max_size > 0

    @property
    def size(self) -> int:
        """Return current number of cached entries."""
        with self._lock:
            return len(self._cache)

    @property
    def hits(self) -> int:
        """Return number of cache hits."""
        with self._lock:
            return self._hits

    @property
    def misses(self) -> int:
        """Return number of cache misses."""
        with self._lock:
            return self._misses

    @property
    def evictions(self) -> int:
        """Return number of cache evictions."""
        with self._lock:
            return self._evictions

    @property
    def hit_rate(self) -> float:
        """
        Return cache hit rate as ratio (0.0-1.0).

        Returns:
            Hit rate as float between 0.0 and 1.0.
            Returns 0.0 if no requests have been made.
        """
        with self._lock:
            total = self._hits + self._misses
            if total == 0:
                return 0.0
            return self._hits / total

    @property
    def stats(self) -> CacheStats:
        """
        Return snapshot of current cache statistics.

        Thread-safe: Takes a consistent snapshot under lock.

        Returns:
            CacheStats immutable dataclass with current statistics
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                size=len(self._cache),
                max_size=self.max_size,
                hit_rate=hit_rate,
                evictions=self._evictions,
            )

    def get(self, text: str) -> "np.ndarray | None":
        """
        Retrieve cached embedding for text.

        If found, moves entry to end of OrderedDict (most recently used).
        Thread-safe operation.

        Args:
            text: Input text to look up

        Returns:
            Cached numpy array embedding, or None if not found.
            Returns None immediately if caching is disabled.
        """
        if not self.enabled:
            return None

        key = self._compute_key(text)

        with self._lock:
            if key in self._cache:
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            else:
                self._misses += 1
                return None

    def put(self, text: str, embedding: "np.ndarray") -> None:
        """
        Store embedding in cache.

        If cache is at capacity, evicts least recently used entry.
        Thread-safe operation.

        Args:
            text: Input text (used to compute cache key)
            embedding: Numpy array embedding to cache

        Note:
            Does nothing if caching is disabled (max_size=0).
            If the text is already cached, updates the embedding
            and moves entry to most recently used position.
        """
        if not self.enabled:
            return

        key = self._compute_key(text)

        with self._lock:
            # If key exists, update and move to end
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = embedding
                return

            # Check if we need to evict
            if len(self._cache) >= self.max_size:
                # Remove oldest (first) item
                self._cache.popitem(last=False)
                self._evictions += 1

            # Add new entry at end (most recently used)
            self._cache[key] = embedding

    def clear(self) -> None:
        """
        Clear all cached entries.

        Thread-safe operation. Resets hits/misses/evictions counters.
        """
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def contains(self, text: str) -> bool:
        """
        Check if text is in cache without affecting statistics.

        Thread-safe operation. Does not update hit/miss counters
        or change LRU order.

        Args:
            text: Input text to check

        Returns:
            True if text is cached, False otherwise.
            Returns False immediately if caching is disabled.
        """
        if not self.enabled:
            return False

        key = self._compute_key(text)

        with self._lock:
            return key in self._cache

    def __len__(self) -> int:
        """Return current number of cached entries."""
        return self.size

    def __contains__(self, text: str) -> bool:
        """Support 'in' operator for cache membership check."""
        return self.contains(text)
