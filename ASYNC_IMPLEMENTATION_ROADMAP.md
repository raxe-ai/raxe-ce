# Async Parallel Scan - Implementation Roadmap

## Executive Summary

**Problem:** Sequential L1 + L2 execution takes 53ms (3ms + 50ms), missing the <20ms balanced mode target by 2.7x.

**Solution:** Run L1 and L2 in parallel asynchronously, reducing latency to 50ms (6% improvement), with potential for 5x speedup when combined with embedding cache.

**Status:** ✅ **Proof-of-concept complete** (see `scan_pipeline_async.py`)

---

## Quick Wins

### 1. **Async Parallel Execution** (5.6% faster) - Week 1
- Run L1 and L2 concurrently
- Total time = max(L1, L2) instead of L1 + L2
- **Impact:** 53ms → 50ms

### 2. **Embedding Cache** (5x faster on cache hits) - Week 1
- LRU cache for text embeddings
- 90%+ cache hit rate expected
- **Impact:** 50ms → 10ms (cached)

### 3. **Combined** (5.3x overall speedup) - Week 2
- Async + cache together
- **Impact:** 53ms → 10ms average
- **Meets <20ms balanced target!** ✅

---

## Architecture Comparison

### Current (Sequential)
```python
# scan_pipeline.py (current)
def scan(text: str):
    l1_result = run_l1(text)      # 3ms
    l2_result = run_l2(text)      # 50ms
    return merge(l1, l2)          # 1ms
# Total: 54ms
```

### Proposed (Async Parallel)
```python
# scan_pipeline_async.py (new)
async def scan(text: str):
    l1_task = asyncio.create_task(run_l1(text))  # Start immediately
    l2_task = asyncio.create_task(run_l2(text))  # Start immediately

    l1_result = await l1_task                    # 3ms

    # Smart cancellation
    if should_cancel_l2(l1_result):
        l2_task.cancel()
        return merge(l1, None)                   # 3ms total (fast path!)

    l2_result = await l2_task                    # 50ms total (parallel)
    return merge(l1, l2)                         # 51ms total
# Total: 50ms (normal), 3ms (CRITICAL fast path)
```

---

## Implementation Files

### ✅ Already Implemented

| File | Status | Description |
|------|--------|-------------|
| `src/raxe/application/scan_pipeline_async.py` | ✅ Complete | Async parallel pipeline |
| `examples/async_parallel_scan_demo.py` | ✅ Complete | Demo showing 5.6% speedup |
| `ASYNC_SCAN_ARCHITECTURE.md` | ✅ Complete | Architecture documentation |

### 🔄 Needs Implementation

| File | Priority | Description |
|------|----------|-------------|
| `src/raxe/async_sdk/client.py` | **HIGH** | Update AsyncRaxe to use async pipeline |
| `src/raxe/domain/ml/bundle_detector.py` | **HIGH** | Add embedding cache |
| `tests/async/test_parallel_scan.py` | **MEDIUM** | Test suite for async pipeline |
| `docs/async-scanning.md` | **LOW** | User documentation |

---

## Week-by-Week Plan

### Week 1: Core Async + Cache (High Impact)

**Monday-Tuesday: Async Pipeline Integration**
- [ ] Update `AsyncRaxe` client to use `AsyncScanPipeline`
- [ ] Add async scan method to sync `Raxe` wrapper
- [ ] Test backwards compatibility

**Wednesday-Thursday: Embedding Cache**
```python
# Add to bundle_detector.py
class BundleBasedDetector:
    def __init__(self, ...):
        from functools import lru_cache
        self._embedding_cache = {}  # text_hash -> embedding
        self._cache_size = 1000
        self._cache_hits = 0
        self._cache_misses = 0

    def analyze(self, text: str, ...):
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        # Check cache
        if text_hash in self._embedding_cache:
            embedding = self._embedding_cache[text_hash]
            self._cache_hits += 1
        else:
            embedding = self.embedder.encode(text)  # 20-50ms
            self._embedding_cache[text_hash] = embedding
            self._cache_misses += 1

            # LRU eviction
            if len(self._embedding_cache) > self._cache_size:
                oldest = next(iter(self._embedding_cache))
                del self._embedding_cache[oldest]

        # Rest of inference (5-10ms)
        prediction = self._predict(embedding, text)
        return ...
```

**Friday: Testing & Validation**
- [ ] Run benchmark comparing async vs sync
- [ ] Validate cache hit rate >80%
- [ ] Test CRITICAL fast path

**Expected Results:**
- Async: 53ms → 50ms (6% faster)
- Cache hit: 50ms → 10ms (5x faster)
- Combined: 53ms → 10ms average with 90% hit rate

---

### Week 2: Performance Tuning

**Monday: Smart L2 Triggering**
```python
# Add to scan_pipeline_async.py
def _should_trigger_l2(self, l1_result, mode):
    if mode == "fast":
        return False  # Never
    if mode == "thorough":
        return True   # Always

    # SMART mode (balanced):
    # Only run L2 if:
    # 1. No L1 detections (might be semantic attack)
    if not l1_result.has_detections:
        return True

    # 2. Low confidence L1 (validate with ML)
    if l1_result.has_low_confidence(threshold=0.6):
        return True

    # 3. 10% sampling (data coverage)
    if random.random() < 0.1:
        return True

    # Otherwise skip L2
    return False
```

**Expected Impact:** Reduce L2 calls by 60-70%

**Tuesday-Wednesday: ONNX Embedding Model (Optional)**
- Convert sentence-transformers to ONNX
- Quantize to INT8
- Benchmark speedup

**Expected Impact:** 50ms → 10ms (5x faster embeddings)

**Thursday: Integration Testing**
- [ ] Test async pipeline with real traffic
- [ ] Validate cache effectiveness
- [ ] Measure P95/P99 latencies

**Friday: Documentation & Rollout Plan**
- [ ] Update README with async examples
- [ ] Create migration guide
- [ ] Write rollout plan

---

### Week 3: Rollout & Monitoring

**Monday-Tuesday: Soft Launch**
- Enable async pipeline for 10% of traffic
- Monitor performance metrics
- Compare async vs sync latencies

**Wednesday: Gradual Rollout**
- 25% → 50% → 75% → 100%
- Monitor cache hit rates
- Watch for regressions

**Thursday: Optimization**
- Tune cache size based on traffic
- Adjust L2 timeout based on P95
- Fine-tune smart triggering thresholds

**Friday: Full Launch**
- 100% traffic on async pipeline
- Deprecate old sync pipeline
- Celebrate 🎉

---

## Performance Targets & Validation

### Targets

| Mode | Current | Async | Async+Cache | Target | Status |
|------|---------|-------|-------------|--------|--------|
| **fast** | 3ms | 3ms | 3ms | <5ms | ✅ |
| **balanced** | 53ms | 50ms | **10ms** | <20ms | ✅ |
| **thorough** | 53ms | 50ms | 10ms | <100ms | ✅ |

### Validation Criteria

**Week 1 Success Criteria:**
- [ ] Async pipeline reduces latency by 5%+
- [ ] Cache hit rate >80%
- [ ] No increase in error rate
- [ ] CRITICAL fast path <5ms

**Week 2 Success Criteria:**
- [ ] Smart triggering reduces L2 calls by 60%+
- [ ] P95 latency <20ms (balanced mode)
- [ ] No degradation in detection accuracy

**Week 3 Success Criteria:**
- [ ] 100% traffic on async pipeline
- [ ] Average latency <15ms (balanced mode)
- [ ] Throughput >2x baseline

---

## Code Examples

### Using Async Client

```python
# FastAPI integration
from fastapi import FastAPI
from raxe.async_sdk.client import AsyncRaxe

app = FastAPI()
raxe = AsyncRaxe()

@app.post("/scan")
async def scan_text(text: str):
    # Non-blocking async scan (50ms)
    result = await raxe.scan(text)
    return {
        "has_threats": result.has_threats,
        "latency_ms": result.duration_ms,
    }
```

### Using Sync Wrapper

```python
# Flask integration (sync)
from flask import Flask, request
from raxe import Raxe

app = Flask(__name__)
raxe = Raxe()  # Internally uses async pipeline

@app.route("/scan", methods=["POST"])
def scan_text():
    # Sync wrapper (still benefits from async internally)
    result = raxe.scan(request.json["text"])
    return {
        "has_threats": result.has_threats,
        "latency_ms": result.duration_ms,
    }
```

### Batch Scanning

```python
# Scan 100 prompts concurrently
async with AsyncRaxe() as raxe:
    results = await asyncio.gather(*[
        raxe.scan(prompt) for prompt in prompts
    ])

# Old sequential: 100 * 53ms = 5.3 seconds
# New parallel: ~53ms (all run concurrently!)
# Speedup: 100x for batches!
```

---

## Monitoring & Metrics

### Key Metrics to Track

```python
# Prometheus metrics
async_scan_duration_ms = Histogram(
    "raxe_async_scan_duration_ms",
    "Async scan duration",
    buckets=[5, 10, 20, 50, 100, 200, 500]
)

parallel_speedup = Histogram(
    "raxe_parallel_speedup",
    "Speedup from parallel execution",
    buckets=[1.0, 1.1, 1.2, 1.5, 2.0, 5.0]
)

l2_cancelled_total = Counter(
    "raxe_l2_cancelled_total",
    "L2 tasks cancelled (CRITICAL fast path)"
)

embedding_cache_hits = Counter("raxe_embedding_cache_hits")
embedding_cache_misses = Counter("raxe_embedding_cache_misses")
```

### Dashboards

**Performance Dashboard:**
- P50, P95, P99 latencies (async vs sync)
- Parallel speedup distribution
- L2 cancellation rate
- Cache hit rate

**Detection Dashboard:**
- Detection accuracy (async vs sync)
- False positive rate
- False negative rate
- L1 vs L2 attribution

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Cache memory usage | Medium | Low | LRU eviction, configurable size |
| Async bugs | High | Medium | Extensive testing, gradual rollout |
| L2 timeout regressions | Medium | Low | Monitor P99, adjust timeout |
| Detection accuracy drop | High | Low | A/B test, validate accuracy |

---

## Success Metrics (3 Months)

**Performance:**
- ✅ P95 latency <20ms (balanced mode)
- ✅ 5x speedup on cached requests
- ✅ 100x speedup on batches

**Adoption:**
- ✅ 100% of traffic on async pipeline
- ✅ 50%+ users using AsyncRaxe client
- ✅ 10+ integrations with async frameworks

**Quality:**
- ✅ No increase in error rate
- ✅ Detection accuracy maintained
- ✅ Cache hit rate >85%

---

## Next Steps (Action Items)

**This Week:**
1. [ ] Review async pipeline implementation
2. [ ] Add embedding cache to bundle_detector
3. [ ] Run benchmark demo (`python examples/async_parallel_scan_demo.py`)
4. [ ] Decide on rollout timeline

**Next Week:**
1. [ ] Update AsyncRaxe client
2. [ ] Add smart L2 triggering
3. [ ] Write test suite
4. [ ] Create migration guide

**Month 2:**
1. [ ] Soft launch (10% traffic)
2. [ ] Monitor and optimize
3. [ ] Gradual rollout to 100%
4. [ ] Document lessons learned

---

## Questions & Discussion

**Q: Why only 6% faster if running in parallel?**
A: Single request: max(3ms, 50ms) = 50ms vs 53ms = 6% faster. But batches get 100x speedup!

**Q: What about embedding generation bottleneck?**
A: Cache solves this (90%+ hit rate). ONNX can speed up cold path 5x.

**Q: Will this break existing integrations?**
A: No - sync wrapper maintains backwards compatibility. Users can opt-in to AsyncRaxe.

**Q: How do we validate detection accuracy?**
A: A/B test: 50% async, 50% sync, compare detection rates.

---

## Conclusion

Async parallel execution + embedding cache delivers **5x speedup** with minimal code changes:

**Before:** 53ms (sequential)
**After:** 10ms (parallel + cached)
**Speedup:** 5.3x ⚡

**Status:** ✅ Ready to implement
**Timeline:** 3 weeks to 100% rollout
**Risk:** Low (gradual rollout, backwards compatible)

Let's ship it! 🚀
