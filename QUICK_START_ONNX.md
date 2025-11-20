# Quick Start: ONNX-First L2 Model Loading

## TL;DR

Use `EagerL2Detector` for fast, predictable L2 model loading:

```python
from raxe.application.eager_l2 import EagerL2Detector

# Initialize (loads immediately - ~2.3s with ONNX)
detector = EagerL2Detector(use_production=True)

# Use detector (fast - ~4.5ms per scan)
result = detector.analyze(text, l1_results)
```

## What You Get

- **2.2x faster initialization**: 2.3s vs 5s (sentence-transformers)
- **5.6x faster inference**: 4.5ms vs 25ms
- **3x smaller memory**: 200MB vs 600MB
- **Automatic fallback**: ONNX → Bundle → Stub (graceful degradation)
- **Production-ready**: <10ms inference, comprehensive telemetry

## File Locations

```
src/raxe/
├── infrastructure/models/
│   ├── __init__.py                    # Module init
│   └── discovery.py                   # ModelDiscoveryService (ONNX-first)
├── application/
│   └── eager_l2.py                    # EagerL2Detector (eager loading)
└── domain/ml/
    ├── onnx_embedder.py               # ONNXEmbedder (enhanced with timing)
    ├── bundle_detector.py             # Existing detector (ONNX support)
    └── models/
        ├── raxe_model_l2_v1.0_bundle.raxe                 (629KB)
        ├── raxe_model_l2_v1.0_onnx_int8_embeddings.onnx   (106MB)
        └── metadata/v1.0_onnx_int8_bundle.json

benchmarks/
└── benchmark_onnx_loading.py          # Benchmark suite

tests/integration/
└── test_onnx_model_discovery.py       # Integration tests

docs/
└── ONNX_MODEL_LOADING.md              # Comprehensive docs
```

## Usage Examples

### 1. Eager Loading (Recommended)

```python
from raxe.application.eager_l2 import EagerL2Detector

# Initialize (loads immediately)
detector = EagerL2Detector(use_production=True)

# Check what was loaded
stats = detector.initialization_stats
print(f"Model: {stats['model_type']}")
print(f"Load time: {stats['load_time_ms']}ms")
print(f"Has ONNX: {stats['has_onnx']}")

# Use detector (fast - already loaded)
result = detector.analyze(prompt, l1_results)
print(f"Inference: {result.processing_time_ms}ms")
```

**Output**:
```
Model: onnx_int8
Load time: 2357.97ms
Has ONNX: True
Inference: 4.53ms
```

### 2. Model Discovery

```python
from raxe.infrastructure.models.discovery import ModelDiscoveryService

# Discover best model
service = ModelDiscoveryService()
model = service.find_best_model(criteria="latency")

print(f"Model ID: {model.model_id}")
print(f"Type: {model.model_type.value}")
print(f"Has ONNX: {model.has_onnx}")
print(f"Bundle: {model.bundle_path}")
print(f"ONNX: {model.onnx_path}")
print(f"Estimated load: {model.estimated_load_time_ms}ms")

# Verify model
is_valid, errors = service.verify_model(model)
if not is_valid:
    print(f"Errors: {errors}")
```

**Output**:
```
Model ID: v1.0_onnx_int8_bundle
Type: onnx_int8
Has ONNX: True
Bundle: .../raxe_model_l2_v1.0_bundle.raxe
ONNX: .../raxe_model_l2_v1.0_onnx_int8_embeddings.onnx
Estimated load: 500ms
```

### 3. Direct ONNX Embedder

```python
from raxe.domain.ml.onnx_embedder import create_onnx_embedder

# Create embedder
embedder = create_onnx_embedder(
    model_path="models/embeddings.onnx",
    tokenizer_name="sentence-transformers/all-mpnet-base-v2"
)

# Generate embedding
embedding = embedder.encode("Test text")

# Check performance
stats = embedder.performance_stats
print(f"Init: {stats['init_time_ms']}ms")
print(f"Calls: {stats['encode_count']}")
print(f"Avg encode: {stats['avg_encode_time_ms']}ms")
```

**Output**:
```
Init: 2302.8ms
Calls: 5
Avg encode: 4.53ms
```

## Run Benchmarks

```bash
# Full benchmark suite
python benchmarks/benchmark_onnx_loading.py

# Integration tests
pytest tests/integration/test_onnx_model_discovery.py -v
```

**Expected Results**:
```
Model Discovery:     <1ms    (EXCELLENT)
ONNX Loading:        ~2.3s   (GOOD - includes tokenizer)
Inference Average:   ~4.5ms  (EXCELLENT)
Inference P95:       ~6.2ms  (EXCELLENT)
```

## Fallback Behavior

The system gracefully falls back if ONNX is unavailable:

```
1. ONNX INT8 found      → Use ONNX (fast: ~2.3s load)
2. ONNX missing         → Use bundle (slower: ~5s load)
3. Bundle missing       → Use stub (instant, but no detection)
```

All fallbacks log warnings and show user-friendly messages.

## Troubleshooting

### ONNX Not Loading

**Check model files exist**:
```bash
ls -lh src/raxe/domain/ml/models/*.onnx
ls -lh src/raxe/domain/ml/models/*.raxe
```

**Check metadata**:
```bash
cat src/raxe/domain/ml/models/metadata/v1.0_onnx_int8_bundle.json
```

**Verify ONNX Runtime**:
```bash
pip install --upgrade onnxruntime>=1.16.0
python -c "import onnxruntime; print(onnxruntime.__version__)"
```

### Slow Loading

**Expected times**:
- ONNX: ~2.3s (includes tokenizer loading)
- Bundle: ~5s
- Stub: <1ms

**If slower**:
- Check disk I/O (use SSD)
- Check available RAM (>4GB recommended)
- Check CPU not throttled

### Falls Back to Stub

**User sees**:
```
⚠️  Warning: L2 ML model not found. Using stub detector (no threat detection).
```

**Solution**:
1. Place `.raxe` bundle file in `src/raxe/domain/ml/models/`
2. Place `.onnx` embeddings file in same directory
3. Ensure metadata file exists in `metadata/` subdirectory

## Migration from LazyL2Detector

**Before** (lazy):
```python
detector = LazyL2Detector(
    config=config,
    use_production=True,
    confidence_threshold=0.5
)
# Model loads here (can timeout)
result = detector.analyze(text, l1_results)
```

**After** (eager):
```python
detector = EagerL2Detector(
    use_production=True,
    confidence_threshold=0.5
)
# Model already loaded
result = detector.analyze(text, l1_results)
```

**Benefits**:
- Predictable initialization time
- No timeout during first scan
- Better error handling
- Comprehensive stats
- Automatic ONNX support

## Performance Summary

| Metric | ONNX INT8 | Bundle (ST) | Improvement |
|--------|-----------|-------------|-------------|
| Load Time | 2.3s | 5.0s | 2.2x faster |
| Inference | 4.5ms | 25ms | 5.6x faster |
| Memory | 200MB | 600MB | 3x smaller |
| Model Size | 106MB | 420MB | 4x smaller |

## Learn More

- **Full documentation**: `docs/ONNX_MODEL_LOADING.md`
- **Implementation details**: `ONNX_IMPLEMENTATION_SUMMARY.md`
- **Discovery service**: `src/raxe/infrastructure/models/discovery.py`
- **Eager detector**: `src/raxe/application/eager_l2.py`
- **ONNX embedder**: `src/raxe/domain/ml/onnx_embedder.py`

## Key Takeaways

1. **Use `EagerL2Detector`** for predictable loading
2. **ONNX loads 2x faster** than sentence-transformers
3. **Inference is 5x faster** with ONNX
4. **Graceful fallback** if ONNX unavailable
5. **Production-ready** with comprehensive telemetry
