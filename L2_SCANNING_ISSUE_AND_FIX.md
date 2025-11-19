# L2 Scanning Issue and Fix

## Issue Summary

**Problem:** L2-only scanning (`raxe scan --l2-only` or `l2_enabled=True, l1_enabled=False`) returns no detections even for obvious threats.

**Root Cause:** The L2 ML model file (`raxe_model_l2.raxe`) is missing from the installation, causing the system to fall back to a stub detector that doesn't actually detect threats.

## Current Behavior

```bash
# L2-only scan returns no detections
$ raxe scan "Ignore all previous instructions" --l2-only
✅ SAFE - No threats detected
  L1 detections: 0
  L2 detections: 0  ← Should detect prompt injection!
```

## Technical Details

### What's Happening

1. **L2 detector initialization**: `LazyL2Detector` (src/raxe/application/lazy_l2.py:55-86)
   - Searches for model file: `src/raxe/domain/ml/models/raxe_model_l2.raxe`
   - If not found, falls back to `StubL2Detector`

2. **Stub detector behavior**: `StubL2Detector` (src/raxe/domain/ml/stub_detector.py)
   - Simple placeholder that returns empty results
   - Not designed for production use
   - Cannot detect actual threats

3. **Model file status**:
   ```bash
   $ ls src/raxe/domain/ml/models/
   README.md  metadata/  # ← No .raxe model file!

   $ raxe models list
   No models found matching criteria
   ```

### Why the Model is Missing

The model files are:
- Trained in a separate `raxe-ml` repository
- Not included in the source repository (too large for git)
- Expected to be downloaded or built separately

Reference: `src/raxe/domain/ml/models/README.md:106-117`

## Solutions

### Option 1: Use L1 Detection (Recommended for Now)

L1 regex-based detection works without any ML model:

```bash
# L1-only scanning (works immediately)
raxe scan "Ignore all previous instructions" --l1-only

# Or in Python
from raxe import Raxe
raxe = Raxe()
result = raxe.scan(
    "Ignore all previous instructions",
    l1_enabled=True,
    l2_enabled=False
)
```

L1 detection provides:
- ✅ Immediate functionality (no model required)
- ✅ Fast performance (<5ms)
- ✅ High precision for known patterns
- ✅ 460+ detection rules

### Option 2: Obtain the L2 Model (For ML Detection)

To enable L2 scanning, you need the model file:

#### A. From `raxe-ml` Repository (If Available)

```bash
# Clone the raxe-ml repository
git clone https://github.com/raxe-ai/raxe-ml.git

# Copy the model file
cp raxe-ml/models/raxe_model_l2.raxe src/raxe/domain/ml/models/

# Verify installation
raxe models list
```

#### B. Train Your Own Model (Advanced)

If you have access to the `raxe-ml` repository:

```bash
cd raxe-ml
python scripts/train_model.py
python scripts/export_bundle.py --output raxe_model_l2.raxe

# Copy to raxe-ce
cp raxe_model_l2.raxe ../raxe-ce/src/raxe/domain/ml/models/
```

#### C. Check for Pre-trained Models

The project may provide pre-trained models via:
- GitHub Releases
- Model registry (future feature)
- Separate download link

Check the project documentation or GitHub releases page.

### Option 3: Use Both L1 and L2 (Default)

The recommended approach is to use both layers:

```bash
# Balanced mode (default) - uses both L1 and L2
raxe scan "text"  # Uses L1 + L2 (falls back to L1 if L2 unavailable)

# Thorough mode - all detection layers
raxe scan "text" --mode thorough
```

## Validation

To check if L2 is working:

```bash
# Check available models
raxe models list

# Should show something like:
# ✓ raxe_model_l2.raxe (v1.0, 644KB)

# Test L2 detection
python3 << 'EOF'
from raxe import Raxe
raxe = Raxe()

# Check detector type
detector = raxe.pipeline.l2_detector._ensure_initialized()
print(f"Detector: {type(detector).__name__}")
print(f"Is stub: {detector.model_info.get('is_stub', False)}")

# Should print:
# Detector: BundleDetector  ← Not StubL2Detector
# Is stub: False
EOF
```

## Impact

### With L2 Model Missing

- ❌ L2-only scanning returns no detections
- ⚠️ Balanced/thorough modes fall back to L1 only
- ⚠️ ML-based semantic detection unavailable
- ✅ L1 regex detection still works

### With L2 Model Present

- ✅ Full detection capability
- ✅ Semantic threat detection
- ✅ Better coverage for novel attacks
- ✅ Multi-head classification (family, subfamily)

## Next Steps

1. **Immediate**: Use L1 detection (`--l1-only` or `mode="fast"`)
2. **Short-term**: Check if pre-trained models are available in project releases
3. **Long-term**: Set up model training pipeline if needed

## Related Files

- Model loading: `src/raxe/application/lazy_l2.py`
- Stub detector: `src/raxe/domain/ml/stub_detector.py`
- Bundle detector: `src/raxe/domain/ml/bundle_detector.py`
- Model README: `src/raxe/domain/ml/models/README.md`
- Model registry: `src/raxe/cli/models.py`

## Questions?

- Check documentation: `docs/MODEL_BUNDLE_INTEGRATION.md`
- Model registry design: `MODEL_REGISTRY_DESIGN.md`
- Training guide: `UNIFIED_BUNDLE_INTEGRATION_SUMMARY.md`
