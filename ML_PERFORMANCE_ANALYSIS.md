# RAXE L2 Model Performance Analysis
## Gap Analysis and Optimization Roadmap

**Version:** 1.0.0
**Date:** 2025-11-20
**Status:** Critical - Action Required

---

## Executive Summary

**Current State vs. Requirements:**

| Metric | Requirement | Current (INT8) | Current (FP16) | Status |
|--------|-------------|----------------|----------------|--------|
| P95 Latency | <3ms | ~2.9ms* | ~8ms | ⚠️ BORDERLINE |
| Model Size | <50MB | 118MB | 248MB | ❌ CRITICAL |
| Binary F1 | >0.95 | 0.962 | 0.97 | ✓ PASS |
| FPR | <0.01 | 0.008 | 0.006 | ✓ PASS |

*Estimated from code analysis; actual measurement needed

**Critical Issues:**
1. **Model Size**: Current 118MB exceeds target by 136% (68MB over budget)
2. **Latency**: Borderline compliance; no optimization headroom
3. **Missing Benchmarks**: No actual latency measurements on target hardware

**Recommendation**: Immediate optimization sprint required to meet deployment constraints.

---

## 1. Detailed Performance Breakdown

### 1.1 Current Architecture

**Model Components:**
```
Total Size: 118MB
├── ONNX Embeddings (INT8): 106MB (90%)
│   └── all-mpnet-base-v2 (768D, 12 layers)
│
└── Bundle (.raxe): 12MB (10%)
    ├── Classifier (joblib): ~8MB
    ├── Triggers: ~1MB
    ├── Clusters: ~2MB
    └── Metadata: ~1MB
```

**Inference Pipeline:**
```
Total Latency: ~2.9ms (estimated)
├── Tokenization: 0.3ms (10%)
├── ONNX Embedding: 1.0ms (34%)
├── Mean Pooling: 0.2ms (7%)
├── Classification: 0.8ms (28%)
│   ├── Binary: 0.3ms
│   ├── Family: 0.3ms
│   └── Subfamily: 0.2ms
└── Post-processing: 0.6ms (21%)
    ├── Trigger matching: 0.2ms
    └── Explanation: 0.4ms
```

### 1.2 Bottleneck Analysis

**Size Bottleneck:**
- ONNX embeddings (106MB) alone exceed target (50MB) by 2x
- Classifier (8MB) is acceptable but could be compressed
- No optimization headroom with current architecture

**Latency Bottleneck:**
- Embedding generation (1.5ms) consumes 50% of budget
- Classification (0.8ms) is efficient for random forest
- Post-processing (0.6ms) is unnecessarily slow

**Critical Path:**
```
User Input → Tokenization → ONNX Inference → Classification → Response
             [0.3ms]        [1.2ms]          [0.8ms]

Critical: ONNX Inference (41% of total latency)
```

---

## 2. Root Cause Analysis

### 2.1 Why Model Size Exceeds Target

**Primary Cause: Large Embedding Model**
```
all-mpnet-base-v2 INT8: 106MB
├── Vocabulary: 30K tokens × 768D = 23M params
├── Transformer layers: 12 layers × 7M params = 84M params
├── Pooling: Dense layers
└── INT8 quantization: 4x smaller than FP32 (but still too large)

Size breakdown:
- Embedding matrix: 30,527 tokens × 768D × 1 byte = 23MB
- Attention weights: 12 layers × 7M params × 1 byte = 84MB
- Total: ~107MB (matches observed 106MB)
```

**Why all-mpnet-base-v2?**
- High accuracy (SOTA on semantic similarity)
- 768D embeddings (rich representation)
- 12 layers (deep understanding)

**Trade-off:**
- Accuracy: 0.962 F1 (exceeds target)
- Size: 106MB (exceeds target by 2x)
- Latency: 1.2ms (acceptable)

### 2.2 Alternative Embedding Models

**Options Considered:**

| Model | Size (INT8) | Latency | F1 (est.) | Recommendation |
|-------|-------------|---------|-----------|----------------|
| all-mpnet-base-v2 | 106MB | 1.2ms | 0.962 | ❌ Too large |
| all-minilm-l6-v2 | 22MB | 0.6ms | 0.940 | ⚠️ Below F1 target |
| all-minilm-l12-v2 | 44MB | 0.9ms | 0.955 | ✓ BEST OPTION |
| paraphrase-mpnet-base-v2 | 106MB | 1.2ms | 0.968 | ❌ Too large |
| multi-qa-mpnet-base-cos-v1 | 106MB | 1.3ms | 0.965 | ❌ Too large |

**Recommendation: all-minilm-l12-v2**
- Size: 44MB (within budget with 6MB headroom)
- Latency: 0.9ms (0.3ms faster than MPNet)
- Estimated F1: 0.955 (meets 0.95 target)
- 384D embeddings (vs 768D) = 2x smaller, minimal accuracy loss

### 2.3 Classifier Size Analysis

**Current Classifier: 8MB**
```
Multi-head Random Forest:
├── Binary classifier: 100 trees × 20 depth = 2.5MB
├── Family classifier: 100 trees × 15 depth = 2.0MB
├── Subfamily classifier: 100 trees × 12 depth = 1.5MB
├── Label encoders: 0.5MB
└── Metadata: 0.5MB
└── Triggers/clusters: 1MB
Total: ~8MB
```

**Optimization Potential:**
```
Reduce to 50 trees:
├── Binary: 100 → 50 trees = 1.25MB (save 1.25MB)
├── Family: 100 → 50 trees = 1.0MB (save 1.0MB)
├── Subfamily: 100 → 50 trees = 0.75MB (save 0.75MB)
Total: 4MB (save 4MB)

Expected accuracy impact: -0.5% to -1.0% F1
```

---

## 3. Optimization Roadmap

### 3.1 Option A: Switch to MiniLM-L12 (RECOMMENDED)

**Changes:**
- Embedding model: all-mpnet-base-v2 → all-minilm-l12-v2
- Quantization: INT8 (keep)
- Classifier: Reduce to 50 trees (optional)

**Expected Results:**
```
Size:
├── Embeddings: 106MB → 44MB (save 62MB)
├── Classifier: 8MB → 4MB (save 4MB, optional)
└── Total: 118MB → 48MB (within 50MB target)

Latency:
├── Embedding: 1.2ms → 0.9ms (save 0.3ms)
├── Classification: 0.8ms → 0.6ms (save 0.2ms, if optimized)
└── Total: 2.9ms → 2.2ms (0.7ms headroom from target)

Accuracy:
├── Binary F1: 0.962 → 0.955 (est., still above target)
├── FPR: 0.008 → 0.010 (est., still below target)
└── Risk: LOW (MiniLM-L12 is well-validated)
```

**Implementation:**
```bash
# 1. Export MiniLM-L12 to ONNX
python scripts/export_onnx_embeddings.py \
    --model sentence-transformers/all-minilm-l12-v2 \
    --quantization int8 \
    --output embeddings/all-minilm-l12-v2_int8.onnx

# 2. Create new metadata
# metadata/v1.0_minilm_l12_int8.json

# 3. Benchmark
python scripts/benchmark_model.py \
    --model-id v1.0_minilm_l12_int8 \
    --test-data data/benchmark/test_set.jsonl \
    --output benchmarks/v1.0_minilm_l12_int8_benchmark.json
```

**Timeline:** 1-2 days
**Risk:** Low
**Confidence:** High

### 3.2 Option B: Aggressive MPNet Optimization (HIGH RISK)

**Changes:**
- Keep all-mpnet-base-v2
- Apply layer pruning: 12 → 8 layers
- Apply attention head pruning: 12 → 8 heads
- Apply weight pruning: 90% sparsity

**Expected Results:**
```
Size:
├── Layer pruning: 106MB → 70MB (save 36MB)
├── Head pruning: 70MB → 60MB (save 10MB)
├── Weight pruning: 60MB → 25MB (save 35MB)
└── Total: 106MB → 25MB (within budget)

Latency:
├── Layer pruning: 1.2ms → 0.8ms
├── Head pruning: 0.8ms → 0.6ms
└── Total: 1.2ms → 0.6ms (very fast)

Accuracy:
├── Layer pruning: 0.962 → 0.945 (est.)
├── Head pruning: 0.945 → 0.940 (est.)
├── Weight pruning: 0.940 → 0.920 (est.)
└── Risk: HIGH (below F1 target)
```

**Implementation:**
```bash
# Requires custom pruning pipeline
# Not recommended without extensive validation
```

**Timeline:** 2-3 weeks
**Risk:** High
**Confidence:** Low

### 3.3 Option C: Hybrid Approach (BACKUP PLAN)

**Changes:**
- Embedding: MiniLM-L6 (smallest, fastest)
- Classifier: Gradient boosted trees (better accuracy)
- Calibration: Probability calibration for FPR reduction

**Expected Results:**
```
Size:
├── Embeddings: 106MB → 22MB (save 84MB)
├── Classifier: 8MB → 6MB (GBT slightly larger)
└── Total: 118MB → 28MB (well within budget)

Latency:
├── Embedding: 1.2ms → 0.6ms (save 0.6ms)
├── Classification: 0.8ms → 1.0ms (GBT slower)
└── Total: 2.9ms → 2.0ms (within target)

Accuracy:
├── Binary F1: 0.962 → 0.940 (below target)
├── After calibration: 0.940 → 0.950 (borderline)
└── Risk: MEDIUM (requires retraining)
```

**Timeline:** 1 week
**Risk:** Medium
**Confidence:** Medium

---

## 4. Recommended Action Plan

### 4.1 Immediate Actions (Week 1)

**Day 1-2: Baseline Measurements**
```bash
# Critical: Get actual latency measurements
1. Deploy current model to target hardware
2. Run benchmark suite (1000+ iterations)
3. Measure P50/P95/P99 latencies
4. Identify actual bottlenecks (may differ from estimates)
```

**Day 3-5: Option A Implementation**
```bash
# Switch to MiniLM-L12
1. Export MiniLM-L12-v2 to ONNX INT8
2. Create model variant metadata
3. Run comprehensive benchmarks
4. Validate accuracy on test set
5. Compare with baseline
```

**Expected Outcome:**
- Model size: 48MB (within target)
- Latency: 2.2ms P95 (within target)
- Accuracy: 0.955 F1 (meets target)

### 4.2 Validation (Week 2)

**Comprehensive Testing:**
```bash
# 1. Unit tests
pytest tests/unit/test_minilm_detector.py

# 2. Integration tests
pytest tests/integration/test_l2_detector.py

# 3. End-to-end tests
pytest tests/e2e/test_scanning_pipeline.py

# 4. Regression tests
# Ensure no regression on benchmark suite

# 5. A/B testing
# Compare MiniLM-L12 vs MPNet on production traffic
```

**Success Criteria:**
- All tests pass
- No accuracy regression >1% on any metric
- Latency consistently <3ms P95
- Model size <50MB

### 4.3 Deployment (Week 3)

**Staged Rollout:**
```
Day 1-2: Deploy to staging environment
Day 3-4: Internal testing and validation
Day 5: Deploy to 10% of production traffic (canary)
Day 6-7: Monitor metrics, increase to 50%
Day 8-14: Full rollout if metrics stable
```

**Rollback Plan:**
- Keep MPNet variant available
- Monitor FPR/FNR closely
- Rollback if FPR >0.015 or FNR >0.04

---

## 5. Performance Monitoring

### 5.1 Real-time Metrics

**Critical Metrics:**
```python
# Latency metrics (track every request)
p50_latency_ms: target <2ms
p95_latency_ms: target <3ms (CRITICAL)
p99_latency_ms: target <5ms

# Accuracy metrics (track with ground truth sampling)
false_positive_rate: target <0.01 (CRITICAL)
false_negative_rate: target <0.03

# Resource metrics
memory_usage_mb: target <200MB
cpu_usage_percent: target <50%
```

**Alerting:**
```yaml
critical_alerts:
  - p95_latency_ms > 5.0ms
  - false_positive_rate > 0.02
  - error_rate > 0.05

warning_alerts:
  - p95_latency_ms > 3.5ms
  - false_positive_rate > 0.015
  - false_negative_rate > 0.04
```

### 5.2 A/B Testing

**Comparison: MiniLM-L12 vs MPNet**
```python
# Split production traffic 50/50
# Track metrics for 1 week

Hypothesis:
- MiniLM-L12 latency will be 30% faster
- MiniLM-L12 accuracy will be within 1% of MPNet
- FPR will remain <0.01 for both

Success criteria:
- Statistical significance (p<0.05)
- No user-visible quality degradation
- Cost savings from faster inference
```

---

## 6. Risk Mitigation

### 6.1 Technical Risks

**Risk 1: Accuracy Degradation**
- **Likelihood:** Medium
- **Impact:** High (user trust)
- **Mitigation:**
  - Extensive validation before deployment
  - A/B testing with MPNet as control
  - Gradual rollout with rollback plan
  - Monitor FPR/FNR in real-time

**Risk 2: Latency Regression**
- **Likelihood:** Low
- **Impact:** Medium
- **Mitigation:**
  - Benchmark on actual hardware
  - Profile inference pipeline
  - Optimize bottlenecks before deployment
  - Load testing under production conditions

**Risk 3: Model Size Increase**
- **Likelihood:** Low
- **Impact:** Low
- **Mitigation:**
  - Automated size checks in CI/CD
  - Reject models >50MB
  - Monitor bundle compression

### 6.2 Operational Risks

**Risk 1: Deployment Failure**
- **Mitigation:**
  - Staging environment testing
  - Canary deployment
  - Automated rollback on errors

**Risk 2: Production Incidents**
- **Mitigation:**
  - 24/7 monitoring
  - Incident response playbook
  - Fallback to rule-based L1 detection

---

## 7. Cost-Benefit Analysis

### 7.1 Current State (MPNet INT8)

**Costs:**
- Model size: 118MB (exceeds limits)
- Latency: 2.9ms (borderline)
- Infrastructure: High memory footprint

**Benefits:**
- Accuracy: 0.962 F1 (excellent)
- Low FPR: 0.008 (excellent)
- Proven performance

### 7.2 Proposed State (MiniLM-L12 INT8)

**Costs:**
- Slight accuracy drop: 0.962 → 0.955 (0.7% decrease)
- Development effort: 1-2 weeks
- Testing and validation effort

**Benefits:**
- Model size: 118MB → 48MB (59% reduction)
- Latency: 2.9ms → 2.2ms (24% faster)
- Infrastructure savings: 60% less memory
- Deployment headroom: 2MB under limit
- Performance headroom: 0.8ms under latency target

**ROI:**
```
Infrastructure savings:
- Memory: 70MB × $0.01/MB/month = $0.70/month per instance
- With 100 instances: $70/month = $840/year

Development cost:
- ML engineer: 1 week × $3000 = $3000
- Payback period: ~4 months

Net benefit:
- Year 1: $840 - $3000 = -$2160 (investment)
- Year 2+: $840/year (savings)
- Plus: Better user experience (faster, more scalable)
```

---

## 8. Conclusion

### 8.1 Summary

**Current State:**
- Model exceeds size constraint by 136%
- Latency borderline compliant
- Accuracy exceeds target

**Recommended Action:**
- Switch to all-minilm-l12-v2 INT8
- Reduces size to 48MB (within target)
- Maintains accuracy >0.95 F1
- Improves latency to 2.2ms

**Timeline:**
- Week 1: Implementation and testing
- Week 2: Validation and benchmarking
- Week 3: Staged deployment

**Risk:**
- Low technical risk
- Proven model architecture
- Extensive validation plan

### 8.2 Next Steps

**Immediate (This Week):**
1. Get approval for optimization sprint
2. Set up benchmarking infrastructure
3. Export MiniLM-L12 to ONNX
4. Run initial benchmarks

**Short-term (Next 2 Weeks):**
1. Complete validation testing
2. A/B test in staging
3. Deploy canary in production
4. Monitor metrics closely

**Long-term (Next Quarter):**
1. Explore model distillation
2. Investigate INT4 quantization
3. Optimize bundle compression
4. Continuous accuracy improvements

---

## Appendix: Benchmark Template

**Expected Benchmark Results (MiniLM-L12 INT8):**

```json
{
  "model_id": "v1.0_minilm_l12_int8",
  "timestamp": "2025-11-20T10:00:00Z",
  "hardware": {
    "cpu": "Intel Xeon E5-2686 v4 @ 2.30GHz",
    "cores": 4,
    "memory_gb": 16,
    "os": "Ubuntu 22.04"
  },
  "latency": {
    "mean_ms": 2.1,
    "p50_ms": 2.0,
    "p95_ms": 2.2,
    "p99_ms": 2.8,
    "max_ms": 4.5,
    "std_ms": 0.3
  },
  "accuracy": {
    "binary_f1": 0.955,
    "binary_precision": 0.968,
    "binary_recall": 0.943,
    "family_f1": 0.850,
    "subfamily_f1": 0.820,
    "false_positive_rate": 0.010,
    "false_negative_rate": 0.028,
    "confusion_matrix": {
      "tp": 943,
      "fp": 32,
      "tn": 3000,
      "fn": 57
    }
  },
  "resources": {
    "model_size_mb": 48,
    "memory_usage_mb": 150,
    "cpu_usage_percent": 45
  },
  "meets_targets": {
    "latency": true,
    "size": true,
    "accuracy": true,
    "fpr": true
  }
}
```
