# ONNX-First Model Loading Strategy

## Overview

RAXE CE implements an ONNX-first model loading strategy for L2 ML detection that significantly improves initialization performance:

- **ONNX INT8 Loading**: ~2.3s (includes tokenizer + quantized embeddings)
- **Bundle Loading**: ~5s (sentence-transformers)
- **Speedup**: 2-3x faster initialization

Additionally, ONNX provides:
- **5x faster inference**: ~4.5ms vs ~25ms
- **Smaller memory footprint**: 200MB vs 600MB
- **Predictable performance**: Quantized INT8 weights

## Architecture

### Components

1. **ModelDiscoveryService** (`src/raxe/infrastructure/models/discovery.py`)
   - Discovers available models in priority order
   - Searches for ONNX INT8 variant first (fastest)
   - Falls back to bundle with sentence-transformers
   - Falls back to stub detector if no models found

2. **EagerL2Detector** (`src/raxe/application/eager_l2.py`)
   - Loads model during `__init__()` (not lazy)
   - Uses ONNX embeddings when available
   - Provides detailed initialization statistics
   - Gracefully falls back on errors

3. **ONNXEmbedder** (`src/raxe/domain/ml/onnx_embedder.py`)
   - Fast ONNX Runtime-based embedding generation
   - INT8 quantized weights for efficiency
   - Performance tracking and telemetry
   - Compatible with sentence-transformers API

### Discovery Strategy

The discovery service implements the following priority order:

```
1. Try ONNX INT8 variant
   ├─ Look for metadata file (v1.0_onnx_int8_bundle.json)
   ├─ Verify ONNX embeddings file exists (.onnx)
   ├─ Verify bundle file exists (.raxe)
   └─ Return ONNX model (estimated load: 500ms)

2. Fall back to bundle-only
   ├─ Look for .raxe bundle files
   └─ Return bundle model (estimated load: 5000ms)

3. Fall back to stub
   └─ Return stub detector (no real detection)
```

## Performance Benchmarks

### Initialization Performance

| Metric | ONNX INT8 | Bundle (ST) | Improvement |
|--------|-----------|-------------|-------------|
| Load Time | ~2.3s | ~5.0s | 2.2x faster |
| Discovery | <1ms | <1ms | Same |
| Tokenizer Load | ~400ms | N/A | - |
| Model Load | ~1.9s | ~5.0s | 2.6x faster |

### Inference Performance

| Metric | ONNX INT8 | Bundle (ST) | Improvement |
|--------|-----------|-------------|-------------|
| Avg Inference | 4.5ms | 25ms | 5.6x faster |
| P50 Latency | 4.0ms | 22ms | 5.5x faster |
| P95 Latency | 6.2ms | 30ms | 4.8x faster |
| P99 Latency | 6.5ms | 35ms | 5.4x faster |

### Resource Usage

| Metric | ONNX INT8 | Bundle (ST) | Improvement |
|--------|-----------|-------------|-------------|
| Model Size | 106MB | 420MB | 4x smaller |
| Memory Usage | 200MB | 600MB | 3x smaller |
| First Scan | ~2.3s | ~5.0s | 2.2x faster |

## Usage

### Using EagerL2Detector

```python
from raxe.application.eager_l2 import EagerL2Detector

# Create detector (loads immediately)
detector = EagerL2Detector(use_production=True)

# Check initialization stats
stats = detector.initialization_stats
print(f"Load time: {stats['load_time_ms']}ms")
print(f"Model type: {stats['model_type']}")
print(f"Has ONNX: {stats['has_onnx']}")

# Use detector (fast - already loaded)
result = detector.analyze(text, l1_results)
```

### Using ModelDiscoveryService

```python
from raxe.infrastructure.models.discovery import ModelDiscoveryService

# Discover best model
service = ModelDiscoveryService()
model = service.find_best_model(criteria="latency")

print(f"Model ID: {model.model_id}")
print(f"Has ONNX: {model.has_onnx}")
print(f"Estimated load: {model.estimated_load_time_ms}ms")

# Verify model
is_valid, errors = service.verify_model(model)
if not is_valid:
    print(f"Validation errors: {errors}")
```

### Direct ONNX Embedder

```python
from raxe.domain.ml.onnx_embedder import create_onnx_embedder

# Create ONNX embedder
embedder = create_onnx_embedder(
    model_path="models/embeddings.onnx",
    tokenizer_name="sentence-transformers/all-mpnet-base-v2"
)

# Generate embeddings (fast)
embedding = embedder.encode("test text")

# Check performance stats
stats = embedder.performance_stats
print(f"Init time: {stats['init_time_ms']}ms")
print(f"Avg encode time: {stats['avg_encode_time_ms']}ms")
```

## Configuration

### Model Files Location

```
src/raxe/domain/ml/models/
├── raxe_model_l2_v1.0_bundle.raxe           (629KB - classifier)
├── raxe_model_l2_v1.0_onnx_int8_embeddings.onnx  (106MB - embeddings)
└── metadata/
    ├── v1.0_bundle.json
    └── v1.0_onnx_int8_bundle.json
```

### Metadata Format

The discovery service uses metadata files to find ONNX variants:

```json
{
  "model_id": "v1.0_onnx_int8_bundle",
  "file_info": {
    "filename": "raxe_model_l2_v1.0_bundle.raxe",
    "onnx_embeddings": "raxe_model_l2_v1.0_onnx_int8_embeddings.onnx",
    "size_mb": 33.1
  },
  "performance": {
    "target_latency_ms": 10,
    "p95_latency_ms": 12.0
  }
}
```

## Fallback Behavior

The system implements graceful degradation:

1. **ONNX model found**: Use ONNX embeddings (fastest)
2. **ONNX missing**: Fall back to bundle with sentence-transformers (slower but functional)
3. **Bundle missing**: Fall back to stub detector (no real detection, warning displayed)
4. **Bundle corrupted**: Fall back to stub detector (error logged)

### Stub Warning

When no models are available, users see:

```
⚠️  Warning: L2 ML model not found. Using stub detector (no threat detection).
   Expected location: src/raxe/domain/ml/models/raxe_model_l2.raxe
   See L2_SCANNING_ISSUE_AND_FIX.md or 'raxe models list' for details.
```

## Telemetry

### Initialization Logs

```json
{
  "event": "model_discovery_success",
  "model_type": "onnx_int8",
  "model_id": "v1.0_onnx_int8_bundle",
  "has_onnx": true,
  "estimated_load_ms": 500,
  "discovery_time_ms": 0.27
}

{
  "event": "onnx_embedder_initialized",
  "model": "raxe_model_l2_v1.0_onnx_int8_embeddings.onnx",
  "model_size_mb": 106.0,
  "tokenizer_load_ms": 412.5,
  "model_load_ms": 1890.3,
  "total_init_ms": 2302.8
}

{
  "event": "production_detector_loaded",
  "model_type": "onnx_int8",
  "model_id": "v1.0_onnx_int8_bundle",
  "has_onnx": true,
  "load_time_ms": 2357.2
}
```

### Inference Logs (First 3 Calls)

```json
{
  "event": "onnx_encode_timing",
  "call_number": 1,
  "num_texts": 1,
  "tokenize_ms": 1.2,
  "inference_ms": 2.8,
  "pooling_ms": 0.5,
  "total_ms": 4.5
}
```

## Benchmarking

### Run Benchmarks

```bash
# Full benchmark suite
python benchmarks/benchmark_onnx_loading.py

# Expected output:
# - Model discovery: <1ms
# - ONNX loading: ~2.3s
# - Bundle loading: ~5s (if tested)
# - Inference: ~4.5ms average
```

### Integration Tests

```bash
# Run ONNX-specific tests
pytest tests/integration/test_onnx_model_discovery.py -v

# Test discovery
pytest tests/integration/test_onnx_model_discovery.py::TestModelDiscovery -v

# Test eager loading
pytest tests/integration/test_onnx_model_discovery.py::TestEagerL2Detector -v

# Test fallback scenarios
pytest tests/integration/test_onnx_model_discovery.py::TestFallbackScenarios -v
```

## Troubleshooting

### ONNX Model Not Found

**Symptom**: Falls back to bundle or stub

**Solution**:
1. Check model files exist:
   ```bash
   ls -lh src/raxe/domain/ml/models/*.onnx
   ls -lh src/raxe/domain/ml/models/*.raxe
   ```

2. Check metadata file:
   ```bash
   cat src/raxe/domain/ml/models/metadata/v1.0_onnx_int8_bundle.json
   ```

3. Verify paths in metadata match actual files

### Slow ONNX Loading

**Symptom**: ONNX loading takes >5s

**Possible causes**:
1. Slow disk I/O (check with `iostat`)
2. Large model file (check size with `ls -lh`)
3. CPU throttling (check CPU governor)
4. Memory pressure (check `free -h` or Activity Monitor)

**Solution**:
1. Use SSD for models directory
2. Ensure adequate RAM (>4GB free)
3. Check CPU not throttled
4. Profile with `time` command

### ONNX Runtime Errors

**Symptom**: ImportError or ONNX session creation fails

**Solution**:
```bash
# Install/upgrade onnxruntime
pip install --upgrade onnxruntime>=1.16.0

# Verify installation
python -c "import onnxruntime as ort; print(ort.__version__)"
```

### Validation Errors

**Symptom**: `verify_model()` returns errors

**Solution**:
1. Check bundle integrity:
   ```python
   from raxe.domain.ml.bundle_loader import ModelBundleLoader
   loader = ModelBundleLoader()
   is_valid, errors = loader.validate_bundle("path/to/model.raxe")
   print(errors)
   ```

2. Re-download model if corrupted

3. Check ONNX model:
   ```python
   import onnxruntime as ort
   session = ort.InferenceSession("path/to/model.onnx")
   ```

## Migration Guide

### From LazyL2Detector to EagerL2Detector

**Before** (lazy loading):
```python
from raxe.application.lazy_l2 import LazyL2Detector

detector = LazyL2Detector(
    config=config,
    use_production=True,
    confidence_threshold=0.5
)

# Model loads here (can timeout)
result = detector.analyze(text, l1_results)
```

**After** (eager loading):
```python
from raxe.application.eager_l2 import EagerL2Detector

# Model loads immediately (predictable)
detector = EagerL2Detector(
    use_production=True,
    confidence_threshold=0.5
)

# Fast inference (model already loaded)
result = detector.analyze(text, l1_results)

# Check initialization stats
stats = detector.initialization_stats
print(f"Loaded in {stats['load_time_ms']}ms")
```

### Key Differences

| Aspect | LazyL2Detector | EagerL2Detector |
|--------|----------------|-----------------|
| Loading | On first `analyze()` | During `__init__()` |
| Predictability | Can timeout | Known upfront |
| Stats | Limited | Comprehensive |
| ONNX Support | Manual | Automatic |
| Fallback | Error-prone | Graceful |

## Performance Tuning

### For Fastest Loading

1. **Use ONNX INT8 variant** (automatic with discovery service)
2. **Pre-warm model** during application startup
3. **Use SSD** for model storage
4. **Allocate sufficient RAM** (>4GB recommended)

### For Smallest Memory Footprint

1. **Use ONNX INT8 variant** (200MB vs 600MB)
2. **Disable caching** if not needed
3. **Use quantized models** (already default)

### For Best Inference Performance

1. **Use ONNX INT8 variant** (5x faster)
2. **Batch requests** when possible
3. **Cache embeddings** for repeated texts
4. **Profile bottlenecks** with built-in telemetry

## Future Improvements

Planned enhancements:

1. **Async model loading**: Load model in background thread
2. **Model caching**: Keep loaded model in memory across requests
3. **Multi-model support**: Load multiple models for A/B testing
4. **Dynamic model swapping**: Hot-swap models without restart
5. **GPU acceleration**: ONNX Runtime GPU provider support

## References

- **ONNX Runtime**: https://onnxruntime.ai/
- **INT8 Quantization**: https://onnxruntime.ai/docs/performance/quantization.html
- **Model Registry**: `src/raxe/domain/ml/model_registry.py`
- **Bundle Loader**: `src/raxe/domain/ml/bundle_loader.py`
- **Discovery Service**: `src/raxe/infrastructure/models/discovery.py`

## Support

For issues related to ONNX model loading:

1. Check logs for detailed error messages
2. Run benchmark suite to verify performance
3. Run integration tests to verify functionality
4. Review this documentation for troubleshooting
5. File issue on GitHub with logs and benchmark results
