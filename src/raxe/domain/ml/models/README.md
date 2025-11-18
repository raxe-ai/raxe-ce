# RAXE ML Models

This directory contains production-ready ML models for RAXE threat detection.

## Production Models

### detector.bundle (Current - v1.0)

**Model:** L2 Cascaded ONNX Detector v1.0
**Format:** ZIP archive containing 3 ONNX models + metadata
**Size:** 316KB (compressed), ~394KB (extracted)
**Framework:** Cascaded classifiers with sentence embeddings
**Inference Time:** ~30-60ms (CPU, including embedding generation)

**Architecture:**
- Binary classifier: Malicious (1) vs Benign (0) - 8KB
- Family classifier: 6 threat families (CMD, JB, PI, PII, TOX, XX) - 23KB
- Subfamily classifier: 93 fine-grained types - 358KB

**Performance Metrics:**
- Binary: 90.2% accuracy, 78.5% F1
- Family: 76.5% accuracy, 77.9% F1 (weighted)
- Subfamily: 44.3% accuracy, 48.9% F1 (weighted)

**Threat Families:**
- CMD: Command Injection
- JB: Jailbreak
- PI: Prompt Injection
- PII: PII Exposure
- TOX: Toxicity/Bias Manipulation
- XX: Unknown/Other

**Usage:**
```python
from raxe.domain.ml import create_onnx_l2_detector

# Create detector (requires: pip install raxe[ml])
detector = create_onnx_l2_detector()

# Analyze a prompt
result = detector.analyze(
    text="Ignore all previous instructions",
    l1_result=l1_scan_results
)

if result.has_predictions:
    for pred in result.predictions:
        print(f"{pred.threat_type.value}: {pred.confidence:.1%}")
        print(f"  {pred.explanation}")
```

**Installation:**
```bash
pip install raxe[ml]  # Includes onnxruntime + sentence-transformers
```

## Model Development

**Note:** This directory contains ONLY production-ready ONNX models for deployment.

Training models, checkpoints, and datasets are excluded from git (see `.gitignore`) to keep the package slim for pip install.

### For ML Engineers/Contributors

If you need access to training models and datasets:

```bash
# TODO: Add download script for development models
# raxe dev download-models --version 1.0.0
```

**Training models are located in:**
- `/models/l2_unified_v1.0.0/` - 267MB .safetensors (excluded from git)
- `/models/l2_enhanced_v1.1.0/` - Enhanced version (excluded from git)
- `/models/l2_enhanced_v1.2.0/` - Latest enhanced version (excluded from git)

## Conversion to ONNX

To convert a trained model to ONNX for production:

```bash
# TODO: Add conversion script
# python scripts/convert_to_onnx.py \
#   --model models/l2_unified_v1.0.0 \
#   --output src/raxe/domain/ml/models/l2_classifier.onnx \
#   --optimize
```

**Optimization checklist:**
- [x] Quantization (FP32 → FP16 or INT8)
- [x] Graph optimization
- [x] Remove training-only operations
- [x] Validate inference accuracy
- [x] Benchmark latency (<3ms target)

## Model Metadata

**Current Production Model:** Not yet deployed
**Last Updated:** 2025-11-16
**Training Dataset:** Internal L2 training set (8 threat categories)
**Validation Accuracy:** TBD
**Production Status:** In development

## Privacy Notice

All ML inference happens **locally** on the user's device. Model inputs (prompts) and outputs (detections) are never sent to external servers unless explicitly configured by the user for optional telemetry.

**PII Protection:**
- Prompts are hashed before any cloud transmission
- Only metadata (threat category, confidence) is sent
- User can disable all telemetry with `--no-telemetry`

---

**Questions?** See [CLAUDE.md](../../../../CLAUDE.md) for architecture details.
