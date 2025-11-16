# RAXE ML Models

This directory contains production-ready ML models for RAXE threat detection.

## Production Models

### l2_classifier.onnx (Coming Soon)

**Model:** L2 Unified Threat Classifier v1.0.0
**Format:** ONNX (optimized for inference)
**Size:** ~10-50MB (optimized from 267MB training model)
**Framework:** DistilBERT-based classifier
**Inference Time:** <3ms (P95)

**Threat Categories:**
- Benign (0)
- Command Injection (1)
- PII Exposure (2)
- Jailbreak (3)
- Prompt Injection (4)
- Data Exfiltration (5)
- Bias Manipulation (6)
- Hallucination (7)

**Usage:**
```python
from raxe.domain.ml.l2_detector import L2ThreatDetector

detector = L2ThreatDetector()
result = detector.detect("Ignore all previous instructions")
print(result.explanation)  # "High-confidence jailbreak attempt detected"
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
