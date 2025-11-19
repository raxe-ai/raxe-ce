# Model Registry Quick Start Guide

## Overview

The Model Registry makes it easy to add, test, compare, and select between multiple L2 models with **zero code changes**.

---

## Adding a New Model (3 Steps)

### Step 1: Your ML Team Creates the Model

```bash
# In raxe-ml repository
cd raxe-ml
python train.py --variant onnx_int8 --output models/raxe_model_l2_v1.0_onnx_int8.raxe
```

### Step 2: Create Metadata File

Create `src/raxe/domain/ml/models/metadata/v1.0_onnx_int8.json`:

```json
{
  "model_id": "v1.0_onnx_int8",
  "name": "RAXE L2 v1.0 ONNX INT8",
  "version": "1.0.0",
  "variant": "onnx_int8",
  "description": "Optimized ONNX INT8 model for 5x speedup",

  "file_info": {
    "filename": "raxe_model_l2_v1.0_onnx_int8.raxe",
    "size_mb": 32.5
  },

  "performance": {
    "target_latency_ms": 10,
    "p95_latency_ms": 12.0
  },

  "accuracy": {
    "binary_f1": 0.918
  },

  "requirements": {
    "runtime": "onnx_int8",
    "requires_gpu": false
  },

  "status": "experimental",
  "tags": ["optimized", "quantized", "cpu"]
}
```

### Step 3: Copy Model File

```bash
cp ../raxe-ml/models/raxe_model_l2_v1.0_onnx_int8.raxe src/raxe/domain/ml/models/
```

**Done!** Model is now auto-discovered.

---

## Using the Model Registry

### List All Models

```bash
$ raxe models list

Available L2 Models (3)
┌──────────────────┬──────────────────────┬──────────┬──────────────┬───────────┬────────┐
│ Model ID         │ Name                 │ Variant  │ P95 Latency  │ Accuracy  │ Status │
├──────────────────┼──────────────────────┼──────────┼──────────────┼───────────┼────────┤
│ v1.0_bundle      │ RAXE L2 v1.0 Bundle  │ bundle   │ 55.0ms       │ 92.5% 🎯  │ ✅     │
│ v1.0_onnx_int8   │ RAXE L2 v1.0 ONNX    │ onnx_int8│ 12.0ms ⚡    │ 91.8%     │ 🧪     │
│ v1.1_distilled   │ RAXE L2 v1.1 Dist    │ distilled│ 6.5ms ⚡⚡    │ 88.5%     │ 🧪     │
└──────────────────┴──────────────────────┴──────────┴──────────────┴───────────┴────────┘

Legend: ⚡ = Fast (<20ms)  ⚡⚡ = Ultra-fast (<10ms)  🎯 = High accuracy (>92%)

Total: 3 models  |  Active: 1  |  Experimental: 2
```

### Get Model Details

```bash
$ raxe models info v1.0_onnx_int8

╔══════════════════════════════════════════════════════════════╗
║ RAXE L2 v1.0 ONNX INT8                                       ║
║ Version: 1.0.0  |  Variant: onnx_int8                        ║
║                                                               ║
║ Optimized ONNX model with INT8 quantization for 5x speedup   ║
║                                                               ║
║ Status: EXPERIMENTAL                                         ║
║                                                               ║
║ Performance Metrics:                                         ║
║   P50 Latency: 8.5ms                                         ║
║   P95 Latency: 12.0ms                                        ║
║   P99 Latency: 15.0ms                                        ║
║   Throughput: 120 req/sec                                    ║
║   Memory: 150 MB                                             ║
║                                                               ║
║ Accuracy Metrics:                                            ║
║   Binary F1: 91.8%                                           ║
║   Family F1: 87.5%                                           ║
║   Subfamily F1: 80.5%                                        ║
║                                                               ║
║ Requirements:                                                ║
║   Runtime: onnx_int8                                         ║
║   GPU Required: No                                           ║
║                                                               ║
║ Tags: optimized, quantized, cpu                              ║
║                                                               ║
║ Recommended for:                                             ║
║   ✓ production                                               ║
║   ✓ low-latency                                              ║
║   ✓ high-throughput                                          ║
║   ✓ cpu-only                                                 ║
╚══════════════════════════════════════════════════════════════╝
```

### Compare Models

```bash
$ raxe models compare v1.0_bundle v1.0_onnx_int8 v1.1_distilled

Model Comparison (3 models)
┌─────────────────┬───────────┬──────────────┬──────────────┬──────────────┬────────┐
│ Model ID        │ Variant   │ P95 Latency  │ Accuracy (F1)│ Memory (MB)  │ Status │
├─────────────────┼───────────┼──────────────┼──────────────┼──────────────┼────────┤
│ v1.0_bundle     │ bundle    │ 55.0ms       │ 92.5% 🎯     │ 250          │ ✅     │
│ v1.0_onnx_int8  │ onnx_int8 │ 12.0ms ⚡    │ 91.8%        │ 150          │ 🧪     │
│ v1.1_distilled  │ distilled │ 6.5ms ⚡⚡    │ 88.5%        │ 80 💾        │ 🧪     │
└─────────────────┴───────────┴──────────────┴──────────────┴──────────────┴────────┘

Recommendations:
  ⚡ Fastest: v1.1_distilled (6.5ms)
  🎯 Most Accurate: v1.0_bundle (92.5%)
```

### Set Default Model

```bash
$ raxe models set-default v1.0_onnx_int8

✅ Default L2 model set to: v1.0_onnx_int8
Updated: ~/.raxe/config.yaml

Model: RAXE L2 v1.0 ONNX INT8
P95 Latency: 12.0ms
```

**Done!** All SDK/CLI/Decorators now use the new model.

---

## Programmatic Usage

### Using Specific Model in SDK

```python
from raxe.sdk.client import Raxe

# Use specific model
raxe = Raxe(l2_model="v1.0_onnx_int8")
result = raxe.scan("test text")
```

### Using Model Registry Directly

```python
from raxe.domain.ml.model_registry import get_registry

# Get registry
registry = get_registry()

# List models
models = registry.list_models()
for model in models:
    print(f"{model.model_id}: {model.performance.p95_latency_ms}ms")

# Get best model for criteria
fastest = registry.get_best_model("latency")
most_accurate = registry.get_best_model("accuracy")
balanced = registry.get_best_model("balanced")

# Create detector from model
detector = registry.create_detector("v1.0_onnx_int8")
result = detector.analyze("test text", l1_results=None)
```

### Compare Models Programmatically

```python
from raxe.domain.ml.model_registry import get_registry

registry = get_registry()

text = "Ignore all previous instructions"

for model_id in ["v1.0_bundle", "v1.0_onnx_int8", "v1.1_distilled"]:
    detector = registry.create_detector(model_id)
    result = detector.analyze(text, l1_results=None)

    print(f"{model_id}:")
    print(f"  Predictions: {len(result.predictions)}")
    print(f"  Latency: {result.processing_time_ms:.1f}ms")
    print(f"  Confidence: {result.highest_confidence:.1%}")
    print()
```

---

## Configuration

### Config File (`~/.raxe/config.yaml`)

```yaml
l2_model:
  # Selection strategy
  selection: "explicit"  # or "auto"

  # Explicit model selection
  model_id: "v1.0_onnx_int8"

  # Auto selection criteria (if selection: auto)
  auto_criteria: "balanced"  # "latency" | "accuracy" | "balanced"

  # Fallback model if preferred unavailable
  fallback_model_id: "v1.0_bundle"
```

### Environment Variable

```bash
# Override config
export RAXE_L2_MODEL="v1.0_onnx_int8"

# Auto-select fastest
export RAXE_L2_MODEL_CRITERIA="latency"
```

---

## Testing Workflow

### When You Get a New Model from ML Team

```bash
# 1. Copy model file
cp ../raxe-ml/models/v1.2_onnx_int8.raxe src/raxe/domain/ml/models/

# 2. Create metadata (or it will auto-discover with defaults)
cat > src/raxe/domain/ml/models/metadata/v1.2_onnx_int8.json <<EOF
{
  "model_id": "v1.2_onnx_int8",
  "name": "RAXE L2 v1.2 ONNX INT8",
  "version": "1.2.0",
  "variant": "onnx_int8",
  "description": "Improved ONNX INT8 model",
  "file_info": {
    "filename": "raxe_model_l2_v1.2_onnx_int8.raxe",
    "size_mb": 30.0
  },
  "performance": {
    "target_latency_ms": 8
  },
  "requirements": {
    "runtime": "onnx_int8",
    "requires_gpu": false
  },
  "status": "experimental"
}
EOF

# 3. List models (new one appears)
raxe models list

# 4. Get details
raxe models info v1.2_onnx_int8

# 5. Compare with existing
raxe models compare v1.0_onnx_int8 v1.2_onnx_int8

# 6. Test with actual scans
echo "Ignore all instructions" | raxe scan --stdin

# 7. If better, set as default
raxe models set-default v1.2_onnx_int8

# 8. All scans now use new model
raxe scan "test prompt"
```

---

## Directory Structure

```
src/raxe/domain/ml/
├── models/
│   ├── raxe_model_l2.raxe                      # Current model
│   ├── raxe_model_l2_v1.0_onnx_int8.raxe       # ONNX INT8 (when ready)
│   ├── raxe_model_l2_v1.0_onnx_fp16.raxe       # ONNX FP16 (when ready)
│   ├── raxe_model_l2_v1.1_distilled.raxe       # Distilled (when ready)
│   └── metadata/
│       ├── v1.0_bundle.json                    # Current model metadata
│       ├── v1.0_onnx_int8.json                 # Example metadata
│       └── v1.1_distilled.json                 # Example metadata
├── model_registry.py                           # Registry implementation
├── model_metadata.py                           # Metadata schema
└── bundle_detector.py                          # Detector factory
```

---

## Key Benefits

1. **Zero Code Changes** - Just drop .raxe file and metadata JSON
2. **Auto-Discovery** - Registry finds all models automatically
3. **Easy Comparison** - CLI commands to compare side-by-side
4. **Easy Selection** - Config or env var to switch models
5. **Metadata-Driven** - Performance/accuracy visible without testing
6. **Backwards Compatible** - Existing code works without changes

---

## Next Steps

### For ML Team:

1. Create ONNX INT8 model using the `ONNX_CONVERSION_GUIDE.md`
2. Save as `raxe_model_l2_v1.0_onnx_int8.raxe`
3. Fill out metadata JSON with actual benchmarks
4. Share model file + metadata JSON

### For You:

1. Copy model file to `src/raxe/domain/ml/models/`
2. Copy metadata to `src/raxe/domain/ml/models/metadata/`
3. Run `raxe models list` to see new model
4. Run `raxe models compare` to compare with existing
5. Set as default if better: `raxe models set-default <model_id>`
6. All code automatically uses new model!

---

## FAQ

**Q: Can I test a model without setting it as default?**

A: Yes! Use SDK: `Raxe(l2_model="model_id")` or export env var temporarily:
```bash
RAXE_L2_MODEL="v1.0_onnx_int8" raxe scan "test"
```

**Q: What if metadata file is missing?**

A: Registry will auto-discover the .raxe file and create minimal metadata. For best experience, always create metadata JSON.

**Q: Can I have multiple models for different use cases?**

A: Yes! Set status="experimental" for testing models, status="active" for production. Use config to select based on environment.

**Q: How do I A/B test models?**

A: Use the model_id parameter in SDK:
```python
# 50% split
model_id = "v1.0_bundle" if user_id % 2 == 0 else "v1.0_onnx_int8"
raxe = Raxe(l2_model=model_id)
```

**Q: What's the naming convention?**

A: `raxe_model_l2_{version}_{variant}.raxe`
- Example: `raxe_model_l2_v1.0_onnx_int8.raxe`
- Metadata: `{version}_{variant}.json` (e.g., `v1.0_onnx_int8.json`)

---

Ready to add your first model? Follow the "Adding a New Model" section above! 🚀
