"""Async SDK for high-throughput RAXE scanning.

This module provides async versions of the RAXE SDK components
for use cases requiring >1000 req/sec throughput.

Key components:
- AsyncRaxe: Async client with LRU caching
- AsyncLRUCache: Thread-safe async cache
- ScanResultCache: Specialized cache for scan results

Example usage:
    from raxe.async_sdk import AsyncRaxe

    # Basic async scanning
    async with AsyncRaxe() as raxe:
        result = await raxe.scan("test prompt")

    # Batch scanning
    raxe = AsyncRaxe(cache_size=1000)
    results = await raxe.scan_batch(prompts, max_concurrency=100)

Performance:
- Throughput: >1000 req/sec (10x sync client)
- Cache hit rate: >80% for repeated prompts
- P95 latency: <10ms (same as sync)
"""
from raxe.async_sdk.cache import AsyncLRUCache, ScanResultCache
from raxe.async_sdk.client import AsyncRaxe

__all__ = [
    "AsyncLRUCache",
    "AsyncRaxe",
    "ScanResultCache",
]
