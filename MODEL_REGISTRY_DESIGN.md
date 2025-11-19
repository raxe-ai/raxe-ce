# Model Registry Design - Multi-Model Management

## Overview

This design enables you to add, test, compare, and select between multiple L2 models (ONNX INT8, PyTorch, different versions, etc.) with zero code changes.

**Goal:** Add new model → Drop .raxe file → Run tests → Select best one

---

## Architecture Options

### **Option 1: Model Registry Pattern (RECOMMENDED)** ⭐

**Pros:**
- ✅ Zero code changes to add new models
- ✅ Auto-discovery of available models
- ✅ Easy A/B testing and comparison
- ✅ CLI commands for management
- ✅ Config/env var for selection
- ✅ Metadata-driven (performance characteristics)

**Cons:**
- ⚠️ Need to implement registry (~200 lines)
- ⚠️ Slightly more complex initially

**Best for:** Production use with multiple models, A/B testing, easy swapping

---

### **Option 2: Simple File Naming Convention**

**Pros:**
- ✅ Extremely simple
- ✅ No new code needed
- ✅ Just rename files

**Cons:**
- ❌ Hard to discover available models
- ❌ No metadata (can't know performance without testing)
- ❌ Manual selection required
- ❌ No easy comparison

**Best for:** Quick experiments with 1-2 models

---

### **Option 3: Config-Only Selection**

**Pros:**
- ✅ Simple config changes
- ✅ No code changes

**Cons:**
- ❌ Still need to hardcode model paths
- ❌ No auto-discovery
- ❌ No comparison tools

**Best for:** Single production model with occasional swap

---

## RECOMMENDED: Model Registry Implementation

### 1. File Naming Convention

```
src/raxe/domain/ml/models/
├── raxe_model_l2_v1.0_pytorch.raxe          # Original PyTorch model
├── raxe_model_l2_v1.0_onnx_int8.raxe        # ONNX INT8 optimized
├── raxe_model_l2_v1.0_onnx_fp16.raxe        # ONNX FP16 (faster GPU)
├── raxe_model_l2_v1.1_distilled.raxe        # Distilled smaller model
├── raxe_model_l2_v2.0_multimodal.raxe       # Future: multimodal
└── metadata/
    ├── v1.0_pytorch.json                     # Model metadata
    ├── v1.0_onnx_int8.json
    ├── v1.0_onnx_fp16.json
    └── v1.1_distilled.json
```

**Format:** `raxe_model_l2_{version}_{variant}.raxe`

### 2. Model Metadata Schema

```json
{
  "model_id": "v1.0_onnx_int8",
  "name": "RAXE L2 v1.0 ONNX INT8",
  "version": "1.0.0",
  "variant": "onnx_int8",
  "description": "Optimized ONNX model with INT8 quantization for 5x speedup",

  "file_info": {
    "filename": "raxe_model_l2_v1.0_onnx_int8.raxe",
    "size_mb": 32.5,
    "checksum": "sha256:abc123..."
  },

  "capabilities": {
    "classification_types": ["binary", "family", "subfamily"],
    "supported_families": ["PI", "JB", "CMD", "PII", "ENC", "RAG"],
    "supports_explanations": true,
    "supports_embeddings": true
  },

  "performance": {
    "target_latency_ms": 10,
    "p50_latency_ms": 8.5,
    "p95_latency_ms": 12.0,
    "p99_latency_ms": 15.0,
    "throughput_per_sec": 120,
    "memory_mb": 150
  },

  "accuracy": {
    "binary_f1": 0.94,
    "family_f1": 0.89,
    "subfamily_f1": 0.82,
    "false_positive_rate": 0.02,
    "false_negative_rate": 0.05
  },

  "requirements": {
    "runtime": "onnx",
    "min_onnxruntime_version": "1.16.0",
    "requires_gpu": false,
    "requires_quantization_support": true
  },

  "training_info": {
    "trained_on": "2024-11-15",
    "training_samples": 50000,
    "validation_samples": 10000,
    "test_samples": 5000
  },

  "tags": ["production", "optimized", "quantized", "cpu"],
  "status": "active",  // "active" | "experimental" | "deprecated"
  "recommended_for": ["production", "low-latency"],
  "not_recommended_for": ["gpu-only-environments"]
}
```

### 3. Model Registry API

```python
# src/raxe/domain/ml/model_registry.py

from raxe.domain.ml.model_registry import ModelRegistry

# Initialize registry (auto-discovers all models)
registry = ModelRegistry()

# List all available models
models = registry.list_models()
for model in models:
    print(f"{model.name} - {model.variant} ({model.performance.p95_latency_ms}ms)")

# Get specific model
model = registry.get_model("v1.0_onnx_int8")
print(f"Latency: {model.performance.p95_latency_ms}ms")
print(f"Accuracy: {model.accuracy.binary_f1:.1%}")

# Get best model for criteria
fastest = registry.get_best_model(criteria="latency")
most_accurate = registry.get_best_model(criteria="accuracy")
balanced = registry.get_best_model(criteria="balanced")

# Create detector from model
detector = registry.create_detector("v1.0_onnx_int8")

# Compare models
comparison = registry.compare_models([
    "v1.0_pytorch",
    "v1.0_onnx_int8",
    "v1.1_distilled"
])
comparison.print_table()
```

### 4. Configuration Selection

**config.yaml:**
```yaml
l2_model:
  # Selection strategy
  selection: "auto"  # "auto" | "explicit" | "benchmark"

  # Explicit model selection
  model_id: "v1.0_onnx_int8"

  # Auto selection criteria
  auto_criteria: "balanced"  # "latency" | "accuracy" | "balanced" | "memory"

  # Fallback model if preferred unavailable
  fallback_model_id: "v1.0_pytorch"

  # A/B testing (optional)
  ab_test:
    enabled: true
    variant_a: "v1.0_pytorch"
    variant_b: "v1.0_onnx_int8"
    traffic_split: 0.5  # 50/50
```

**Environment variable:**
```bash
# Override config
export RAXE_L2_MODEL="v1.0_onnx_int8"

# Auto-select fastest
export RAXE_L2_MODEL_CRITERIA="latency"
```

### 5. CLI Commands

```bash
# List all available models
raxe models list

# Output:
# Available L2 Models:
# ┌─────────────────┬───────────┬──────────────┬────────────┬──────────┐
# │ Name            │ Variant   │ P95 Latency  │ Accuracy   │ Status   │
# ├─────────────────┼───────────┼──────────────┼────────────┼──────────┤
# │ RAXE L2 v1.0    │ pytorch   │ 45.0ms       │ 92.5%      │ active   │
# │ RAXE L2 v1.0    │ onnx_int8 │ 10.0ms ⚡    │ 91.8%      │ active   │
# │ RAXE L2 v1.1    │ distilled │ 5.0ms ⚡⚡    │ 88.2%      │ exp      │
# └─────────────────┴───────────┴──────────────┴────────────┴──────────┘
# ⚡ = Fastest    🎯 = Most Accurate    ⭐ = Recommended

# Show detailed model info
raxe models info v1.0_onnx_int8

# Output:
# Model: RAXE L2 v1.0 ONNX INT8
# Version: 1.0.0
# Status: Active ✅
#
# Performance:
#   P50: 8.5ms  P95: 10.0ms  P99: 15.0ms
#   Throughput: 120 req/sec
#   Memory: 150 MB
#
# Accuracy:
#   Binary F1: 94.0%
#   Family F1: 89.0%
#   Subfamily F1: 82.0%
#
# Requirements:
#   Runtime: ONNX
#   GPU: Not required
#   Min ONNX Runtime: 1.16.0

# Test a specific model
raxe models test v1.0_onnx_int8 --prompts test_data/threats.txt

# Output:
# Testing model: v1.0_onnx_int8
# Test prompts: 100
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100/100 (100%)
#
# Results:
#   True Positives: 85
#   True Negatives: 10
#   False Positives: 2
#   False Negatives: 3
#   Accuracy: 95.0%
#   Precision: 97.7%
#   Recall: 96.6%
#   F1 Score: 97.1%
#   Avg Latency: 9.2ms (P95: 11.5ms)

# Compare multiple models
raxe models compare v1.0_pytorch v1.0_onnx_int8 v1.1_distilled --prompts test_data/threats.txt

# Output:
# Model Comparison (100 test prompts)
# ┌─────────────┬──────────┬────────────┬─────────────┬──────────┐
# │ Model       │ Accuracy │ P95 Latency│ Memory (MB) │ Winner   │
# ├─────────────┼──────────┼────────────┼─────────────┼──────────┤
# │ pytorch     │ 95.2% 🎯 │ 48.5ms     │ 250         │          │
# │ onnx_int8   │ 94.1%    │ 10.2ms ⚡  │ 150         │ ⭐ Best  │
# │ distilled   │ 89.5%    │ 5.1ms ⚡⚡  │ 80 💾       │          │
# └─────────────┴──────────┴────────────┴─────────────┴──────────┘
#
# Recommendation: onnx_int8
# Reason: Best balance of accuracy (94.1%) and latency (10.2ms)

# Benchmark all models
raxe models benchmark --iterations 1000

# Output:
# Benchmarking all active models (1000 iterations each)
#
# Model: v1.0_pytorch
#   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1000/1000 (100%)
#   P50: 42.1ms  P95: 48.3ms  P99: 52.7ms
#
# Model: v1.0_onnx_int8
#   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1000/1000 (100%)
#   P50: 8.2ms   P95: 10.5ms  P99: 14.8ms ⚡ Fastest
#
# Benchmark Report saved to: benchmarks/2024-11-19_models.json

# Set default model
raxe models set-default v1.0_onnx_int8

# Output:
# ✅ Default L2 model set to: v1.0_onnx_int8
# Updated: ~/.raxe/config.yaml

# Validate model integrity
raxe models validate v1.0_onnx_int8

# Output:
# Validating model: v1.0_onnx_int8
#   ✅ File exists: raxe_model_l2_v1.0_onnx_int8.raxe
#   ✅ Checksum matches: sha256:abc123...
#   ✅ Bundle structure valid
#   ✅ Metadata schema valid
#   ✅ Runtime dependencies available
#   ✅ Can load detector
#   ✅ Can run inference
#
# Model is valid and ready to use!
```

### 6. Programmatic Usage

```python
# Simple: Use default model
from raxe.sdk.client import Raxe

raxe = Raxe()
result = raxe.scan("test")

# Use specific model
raxe = Raxe(l2_model="v1.0_onnx_int8")
result = raxe.scan("test")

# Compare models on same input
from raxe.domain.ml.model_registry import ModelRegistry

registry = ModelRegistry()

text = "Ignore all previous instructions"
results = {}

for model_id in ["v1.0_pytorch", "v1.0_onnx_int8", "v1.1_distilled"]:
    detector = registry.create_detector(model_id)
    result = detector.analyze(text, l1_results=None)
    results[model_id] = {
        "predictions": len(result.predictions),
        "confidence": result.highest_confidence,
        "latency_ms": result.processing_time_ms
    }

# Print comparison
for model_id, metrics in results.items():
    print(f"{model_id}: {metrics['predictions']} predictions, "
          f"{metrics['confidence']:.1%} confidence, "
          f"{metrics['latency_ms']:.1f}ms")
```

### 7. A/B Testing Support

```python
# src/raxe/domain/ml/ab_testing.py

from raxe.domain.ml.model_registry import ModelRegistry
from raxe.domain.ml.ab_testing import ABModelSelector

# Initialize A/B test
selector = ABModelSelector(
    variant_a="v1.0_pytorch",
    variant_b="v1.0_onnx_int8",
    split=0.5,  # 50/50
    user_hash_key="user_id"  # Consistent per user
)

# Select model for request
model_id = selector.select(user_id="user123")
detector = registry.create_detector(model_id)

# Track results
selector.track_result(
    user_id="user123",
    model_id=model_id,
    latency_ms=10.5,
    accuracy=0.95
)

# Get A/B test report
report = selector.get_report()
print(f"Variant A: {report.variant_a.avg_latency:.1f}ms, {report.variant_a.accuracy:.1%}")
print(f"Variant B: {report.variant_b.avg_latency:.1f}ms, {report.variant_b.accuracy:.1%}")
print(f"Winner: {report.winner} ({report.confidence:.1%} confidence)")
```

---

## Implementation Plan

### Phase 1: Core Registry (Week 1)
- [ ] Create `ModelRegistry` class with auto-discovery
- [ ] Define metadata schema and validation
- [ ] Implement `list_models()`, `get_model()`, `create_detector()`
- [ ] Add config-based selection
- [ ] Update `lazy_l2.py` to use registry

### Phase 2: CLI Commands (Week 1)
- [ ] `raxe models list`
- [ ] `raxe models info <model_id>`
- [ ] `raxe models set-default <model_id>`
- [ ] `raxe models validate <model_id>`

### Phase 3: Testing & Comparison (Week 2)
- [ ] `raxe models test <model_id>`
- [ ] `raxe models compare <model_ids...>`
- [ ] `raxe models benchmark`
- [ ] Standard test dataset
- [ ] Comparison report generation

### Phase 4: A/B Testing (Week 3)
- [ ] A/B selector implementation
- [ ] Metrics tracking
- [ ] Statistical significance testing
- [ ] A/B report generation

---

## Directory Structure

```
src/raxe/domain/ml/
├── models/                              # Model files
│   ├── raxe_model_l2_v1.0_pytorch.raxe
│   ├── raxe_model_l2_v1.0_onnx_int8.raxe
│   ├── raxe_model_l2_v1.0_onnx_fp16.raxe
│   └── metadata/
│       ├── v1.0_pytorch.json
│       ├── v1.0_onnx_int8.json
│       └── v1.0_onnx_fp16.json
├── model_registry.py                    # Registry implementation
├── model_metadata.py                    # Metadata schema
├── model_selector.py                    # Selection logic
├── ab_testing.py                        # A/B testing
└── benchmarks/                          # Benchmark framework
    ├── benchmark_runner.py
    ├── test_datasets/
    │   ├── threats.txt
    │   ├── benign.txt
    │   └── edge_cases.txt
    └── reports/
        └── 2024-11-19_comparison.json
```

---

## Usage Workflow

### Adding a New Model (ML Team):

```bash
# 1. ML team creates new model
cd raxe-ml
python train.py --output models/v1.1_onnx_int8.raxe

# 2. Create metadata file
cat > metadata/v1.1_onnx_int8.json <<EOF
{
  "model_id": "v1.1_onnx_int8",
  "name": "RAXE L2 v1.1 ONNX INT8",
  "version": "1.1.0",
  "variant": "onnx_int8",
  "performance": {
    "target_latency_ms": 8
  },
  "status": "experimental"
}
EOF

# 3. Copy to RAXE
cp models/v1.1_onnx_int8.raxe ../raxe-ce/src/raxe/domain/ml/models/
cp metadata/v1.1_onnx_int8.json ../raxe-ce/src/raxe/domain/ml/models/metadata/

# 4. Auto-discovery (no code changes needed!)
cd ../raxe-ce
raxe models list
# ✅ New model appears automatically

# 5. Test new model
raxe models test v1.1_onnx_int8 --prompts test_data/threats.txt

# 6. Compare with existing
raxe models compare v1.0_onnx_int8 v1.1_onnx_int8

# 7. If better, set as default
raxe models set-default v1.1_onnx_int8

# Done! All SDK/CLI/Decorators now use new model
```

---

## Recommendation

**Use Option 1: Model Registry** for your use case because:

1. ✅ **Easy to add models:** Drop .raxe file + metadata → Auto-discovered
2. ✅ **Easy to test:** CLI commands for testing each model
3. ✅ **Easy to compare:** Side-by-side comparison with metrics
4. ✅ **Easy to select:** Config or env var to switch
5. ✅ **Production ready:** A/B testing, monitoring, rollback
6. ✅ **No code changes:** Just config changes to swap models

**Next Steps:**
1. I can implement the Model Registry (~500 lines)
2. Add CLI commands (~300 lines)
3. Create benchmark framework (~200 lines)
4. Add example metadata files

Would you like me to implement this? I can start with Phase 1 (Core Registry) and you can start testing multiple models immediately.
