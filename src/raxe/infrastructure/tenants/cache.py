"""Policy cache with LRU eviction for fast lookups.

Provides <1ms policy lookups with configurable cache size.
"""

import logging
from collections import OrderedDict
from collections.abc import Callable

from raxe.domain.tenants.models import TenantPolicy

logger = logging.getLogger(__name__)


class PolicyCache:
    """LRU cache for TenantPolicy lookups.

    Provides O(1) get/set operations with automatic eviction
    of least recently used entries when maxsize is reached.

    Thread Safety:
        This implementation is NOT thread-safe. For multi-threaded
        use, wrap operations with appropriate locking.
    """

    def __init__(self, maxsize: int = 128) -> None:
        """Initialize cache.

        Args:
            maxsize: Maximum number of policies to cache
        """
        self._maxsize = maxsize
        self._cache: OrderedDict[str, TenantPolicy] = OrderedDict()
        self._hits = 0
        self._misses = 0

    @property
    def maxsize(self) -> int:
        """Maximum cache size."""
        return self._maxsize

    def get(self, policy_id: str) -> TenantPolicy | None:
        """Get a policy from cache.

        Args:
            policy_id: Policy identifier

        Returns:
            Cached policy or None if not found
        """
        if policy_id not in self._cache:
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(policy_id)
        self._hits += 1
        return self._cache[policy_id]

    def set(self, policy_id: str, policy: TenantPolicy) -> None:
        """Set a policy in cache.

        Args:
            policy_id: Policy identifier
            policy: Policy to cache
        """
        if policy_id in self._cache:
            # Update existing and move to end
            self._cache.move_to_end(policy_id)
            self._cache[policy_id] = policy
        else:
            # Add new entry
            self._cache[policy_id] = policy

            # Evict oldest if over capacity
            if len(self._cache) > self._maxsize:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
                logger.debug(
                    "cache_eviction",
                    extra={"evicted_policy_id": oldest, "cache_size": len(self._cache)},
                )

    def delete(self, policy_id: str) -> None:
        """Remove a policy from cache.

        Args:
            policy_id: Policy identifier
        """
        self._cache.pop(policy_id, None)

    def clear(self) -> None:
        """Remove all entries from cache and reset stats."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_or_set(
        self,
        policy_id: str,
        factory: Callable[[], TenantPolicy],
    ) -> TenantPolicy:
        """Get a policy from cache or set it using factory.

        Args:
            policy_id: Policy identifier
            factory: Callable that returns the policy if not cached

        Returns:
            Cached or newly created policy
        """
        cached = self.get(policy_id)
        if cached is not None:
            return cached

        policy = factory()
        self.set(policy_id, policy)
        return policy

    def stats(self) -> dict[str, float]:
        """Get cache statistics.

        Returns:
            Dictionary with hits, misses, and hit_rate
        """
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "size": len(self._cache),
            "maxsize": self._maxsize,
        }

    def __len__(self) -> int:
        """Return number of cached items."""
        return len(self._cache)

    def __contains__(self, policy_id: str) -> bool:
        """Check if policy is in cache."""
        return policy_id in self._cache
