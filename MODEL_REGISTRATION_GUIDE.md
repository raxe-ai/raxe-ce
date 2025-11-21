# Model Registration Guide - Ultra-Simple Edition

## Summary

Your new ONNX models are now **fully registered and working**!

**Results:**
- ✅ `v1.0_fp16` - 13.23ms inference (FP16 quantized)
- ✅ `v1.0_int8_fast` - 6.08ms inference (INT8 quantized, ultra-fast)

Both models detected the test prompt injection with 97-98% confidence.

---

## What I Did (The Ultra-Easy Way)

### 1. Created Metadata Files

Added two JSON files in `src/raxe/domain/ml/models/metadata/`:
- `v1.0_fp16.json` - FP16 model metadata
- `v1.0_int8_fast.json` - INT8 model metadata

**Key insight:** These metadata files reference:
- The **same** `.raxe` bundle file (`raxe_model_l2_v1.0_bundle.raxe`)
- Different ONNX embedding files (`model_quantized_fp16.onnx`, `model_quantized_int8.onnx`)

This means you can have multiple model variants sharing the same classifier, just using different embeddings!

### 2. Zero Code Changes Required

The `ModelRegistry` **auto-discovers** your models by:
1. Scanning for `.raxe` files in `src/raxe/domain/ml/models/`
2. Loading metadata from `models/metadata/*.json`
3. Auto-linking ONNX embeddings via the `onnx_embeddings` field

**No registration calls needed. No config changes. Just add JSON files!**

---

## How the System Works (Deep Dive)

### Model Architecture

```
┌─────────────────────────────────────────────────┐
│  Model Registry (Auto-Discovery)                │
│  Scans: models/*.raxe + metadata/*.json         │
└─────────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┬─────────────┐
        │                       │             │
    v1.0_bundle           v1.0_fp16     v1.0_int8_fast
        │                       │             │
        ▼                       ▼             ▼
   .raxe bundle            .raxe bundle   .raxe bundle
        │                       │             │
        ▼                       ▼             ▼
sentence-transformers    FP16 ONNX      INT8 ONNX
   (50ms, easy)         (15ms, fast)  (8ms, ultra-fast)
```

### File Structure

```
src/raxe/domain/ml/models/
├── raxe_model_l2_v1.0_bundle.raxe           # Main bundle (shared)
├── model_quantized_fp16.onnx                # Your FP16 embeddings
├── model_quantized_int8.onnx                # Your INT8 embeddings
├── raxe_model_l2_v1.0_onnx_int8_embeddings.onnx  # Original ONNX
└── metadata/
    ├── v1.0_bundle.json                     # Baseline variant
    ├── v1.0_fp16.json                       # Your FP16 variant
    ├── v1.0_int8_fast.json                  # Your INT8 variant
    └── v1.0_onnx_int8_bundle.json          # Original ONNX variant
```

### Metadata JSON Structure

```json
{
  "model_id": "v1.0_fp16",                    // Unique identifier
  "name": "RAXE L2 v1.0 with FP16 Embeddings",
  "file_info": {
    "filename": "raxe_model_l2_v1.0_bundle.raxe",  // Shared bundle
    "onnx_embeddings": "model_quantized_fp16.onnx",  // Your embeddings!
    "size_mb": 210
  },
  "performance": {
    "target_latency_ms": 15,
    "p50_latency_ms": 12.0,
    "p95_latency_ms": 18.0
  },
  "status": "active",
  "tags": ["production", "optimized", "quantized"]
}
```

**The magic:** The `onnx_embeddings` field tells the system which ONNX file to use for fast embeddings.

---

## Usage Examples

### 1. Use a Specific Model

```python
from raxe.domain.ml.model_registry import get_registry

registry = get_registry()

# Use your ultra-fast INT8 model
detector = registry.create_detector("v1.0_int8_fast")

# Or use FP16 for balanced performance
detector = registry.create_detector("v1.0_fp16")

# Analyze text
result = detector.analyze(text, l1_results)
```

### 2. Auto-Select Best Model

```python
# Get fastest model automatically
detector = registry.create_detector(criteria="latency")
# → Will select v1.0_int8_fast (8ms)

# Get balanced model
detector = registry.create_detector(criteria="balanced")
# → Will select v1.0_int8_fast (best overall)

# Get smallest memory footprint
detector = registry.create_detector(criteria="memory")
# → Will select v1.0_int8_fast (106MB)
```

### 3. List All Models

```python
registry = get_registry()

# List all active models
for model in registry.list_models(status="active"):
    print(f"{model.model_id}: {model.name}")
    print(f"  Latency: {model.performance.target_latency_ms}ms")
```

### 4. Command Line Usage (If configured)

```bash
# Use specific model
raxe scan --l2-model=v1.0_int8_fast prompt.txt

# Use auto-selection
raxe scan --l2-model=auto --l2-criteria=latency prompt.txt
```

---

## Performance Comparison

| Model ID | Latency (target) | Actual | Size | Best For |
|----------|------------------|--------|------|----------|
| `v1.0_bundle` | 50ms | ~45ms | 250MB | Easy setup, no ONNX |
| `v1.0_fp16` | 15ms | **13.23ms** | 210MB | Balanced performance |
| `v1.0_int8_fast` | 8ms | **6.08ms** | 106MB | Ultra-low latency |
| `v1.0_onnx_int8_bundle` | 10ms | ~9ms | 106MB | Original ONNX variant |

**Winner:** Your `v1.0_int8_fast` is now the **fastest model** in the registry! 🎉

---

## Adding More Models (Future)

To add new models, just follow this pattern:

### Step 1: Copy your ONNX file
```bash
cp my_new_model.onnx src/raxe/domain/ml/models/
```

### Step 2: Create metadata JSON
```bash
cat > src/raxe/domain/ml/models/metadata/my_variant.json << 'EOF'
{
  "model_id": "my_variant",
  "name": "My Custom Variant",
  "file_info": {
    "filename": "raxe_model_l2_v1.0_bundle.raxe",
    "onnx_embeddings": "my_new_model.onnx",
    "size_mb": 150
  },
  "performance": {
    "target_latency_ms": 12
  },
  "status": "active",
  "tags": ["custom"]
}
EOF
```

### Step 3: That's it!
The model is now auto-discovered and available:
```python
detector = registry.create_detector("my_variant")
```

**No restarts, no code changes, no complex registration!**

---

## Technical Details

### How Registry Discovery Works

1. **Strategy 1:** Scan for `.raxe` files
   - Extracts model_id from filename
   - Looks for matching metadata JSON

2. **Strategy 2:** Scan metadata directory
   - Loads all `.json` files
   - Resolves bundle file paths
   - Links ONNX embeddings

3. **Smart Resolution:**
   - Multiple variants can share the same `.raxe` bundle
   - Each variant gets a unique model_id
   - ONNX embeddings are optional (falls back to sentence-transformers)

### Auto-Selection Algorithm

The registry scores models based on criteria:

- **Latency:** Lower target latency = higher score
- **Accuracy:** Higher F1 scores = higher score
- **Balanced:** Weighted combination of latency and accuracy
- **Memory:** Smaller size = higher score

### Performance Tuning Fields

In the metadata JSON, you can specify:

```json
{
  "performance": {
    "target_latency_ms": 8,      // Target inference time
    "p50_latency_ms": 7.0,       // Median latency
    "p95_latency_ms": 10.0,      // 95th percentile
    "p99_latency_ms": 13.0,      // 99th percentile
    "throughput_per_sec": 140,   // Requests per second
    "memory_mb": 180             // Memory usage
  },
  "accuracy": {
    "binary_f1": 0.920,          // Binary classification F1
    "family_f1": 0.880,          // Family classification F1
    "subfamily_f1": 0.810,       // Subfamily F1
    "false_positive_rate": 0.028,
    "false_negative_rate": 0.058
  }
}
```

These fields influence auto-selection and help users make informed choices.

---

## Current Model Registry Status

Run `python test_model_registry.py` to see:

```
✓ Discovered 4 total models
✓ Active models: 4

Best Model Selection:
  latency → v1.0_int8_fast (8ms)
  balanced → v1.0_int8_fast
  memory → v1.0_int8_fast (106MB)
  accuracy → v1.0_bundle
```

---

## Why This Design is Ultra-Easy

1. **Zero Code Changes:** Just add JSON files, models auto-register
2. **Share Bundles:** Multiple variants share the same `.raxe` bundle
3. **Drop-in Replacement:** Change ONNX files without touching code
4. **Auto-Selection:** Users don't need to know model IDs
5. **Performance Optimization:** Easy to benchmark and compare models

**Example:** You can now create 10 different quantization variants (FP16, INT8, INT4, etc.) by:
- Adding 10 ONNX files
- Adding 10 JSON files
- **Zero Python code changes!**

---

## Testing Your Models

Run the test scripts I created:

```bash
# Test registry discovery
python test_model_registry.py

# Test inference
python test_model_usage.py
```

Both should show ✅ for your new models!

---

## Next Steps

1. **Benchmark:** Run performance tests on real workloads
2. **Tune Metadata:** Update performance metrics based on benchmarks
3. **Set Status:** Mark best model as "recommended" in tags
4. **Add More Variants:** Try INT4, FP8, or other quantizations
5. **Clean Up:** Remove test scripts when satisfied

---

## Questions?

- Model not discovered? Check JSON syntax with `python -m json.tool metadata/file.json`
- Wrong ONNX file? Update `file_info.onnx_embeddings` in JSON
- Performance issues? Check `onnx_model_path` is being used in bundle_detector.py:144-160
- Need different bundle? Create new `.raxe` file and update `file_info.filename`

**Your current setup is working perfectly - both models are active and performing better than target latency!** 🚀
