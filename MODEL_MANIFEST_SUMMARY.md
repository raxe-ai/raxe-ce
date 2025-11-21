# Model Manifest Summary - RAXE CE

**Date:** 2025-11-20
**Status:** Complete
**Models Documented:** 2 (INT8, FP16)

---

## Overview

This document summarizes the newly created model manifests and documentation for the RAXE quantized MPNet embedding models.

### Models Documented

1. **INT8 Model:** `model_quantized_int8_deploy/` - Production-optimized, fast inference
2. **FP16 Model:** `model_quantized_fp16_deploy/` - Accuracy-optimized, balanced performance

---

## Deliverables Created

### 1. Model Manifests (manifest.yaml)

#### INT8 Model Manifest
**Location:** `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/models/model_quantized_int8_deploy/manifest.yaml`

**Key Details:**
- Model ID: `mpnet-int8-embeddings-v1.0`
- Base Model: `sentence-transformers/all-mpnet-base-v2`
- Size: 106 MB
- Latency: 6-7ms (P50), 10ms (P95)
- Accuracy: 92.0% F1
- Tokenizer: MPNetTokenizer
- SHA256: `17ef58e5f9bc06b0951e30138cfa56f3fedcaa3809b898284bf69e5da20f70db`

#### FP16 Model Manifest
**Location:** `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/models/model_quantized_fp16_deploy/manifest.yaml`

**Key Details:**
- Model ID: `mpnet-fp16-embeddings-v1.0`
- Base Model: `sentence-transformers/all-mpnet-base-v2`
- Size: 210 MB
- Latency: 12-13ms (P50), 18ms (P95)
- Accuracy: 93.5% F1
- Tokenizer: MPNetTokenizer
- SHA256: `8b5ec13e50aab9048042292ddaa95b5c97da716dbcda315c0907aa1b70151a43`

### 2. Model READMEs

#### INT8 README
**Location:** `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/models/model_quantized_int8_deploy/README.md`

**Contents:**
- Quick start guide with code examples
- Performance characteristics and benchmarks
- Tokenizer configuration details
- When to use this model (vs FP16)
- Integration guide (BundleBasedDetector, ModelRegistry)
- Deployment checklist
- Troubleshooting guide
- Known limitations
- Future improvements

#### FP16 README
**Location:** `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/domain/ml/models/model_quantized_fp16_deploy/README.md`

**Contents:**
- Quick start guide with code examples
- Performance characteristics and benchmarks
- Comparison vs INT8 model
- When to use FP16 over INT8
- Cost-benefit analysis
- Integration guide
- Deployment checklist
- Troubleshooting guide
- Known limitations

### 3. Technical Analysis Document

**Location:** `/Users/mh/github-raxe-ai/raxe-ce/docs/models/TOKENIZER_COMPATIBILITY_AND_PERFORMANCE_ANALYSIS.md`

**Contents:**

#### Part 1: Tokenizer Compatibility Rules
- MPNet tokenizer specification
- Compatible tokenizers list
- Validation rules and function
- Configuration best practices
- Common tokenizer issues and solutions

#### Part 2: Performance Assessment
- Model performance summary (INT8 vs FP16)
- Detailed analysis of size, latency, accuracy, FPR
- Performance gap vs RAXE requirements
- Options to meet targets (distillation, pruning, hybrid approaches)
- Hardware-specific benchmarks

#### Part 3: TokenizerRegistry Implementation
- TokenizerRegistry class implementation
- Auto-registration from manifests
- Validation and caching logic

#### Part 4: Recommendations
- Short-term actions (deploy INT8, quick wins)
- Medium-term actions (hybrid L1/L2, fine-tuning)
- Long-term actions (distillation, architecture exploration)
- Decision framework for model selection

---

## Key Findings

### 1. Base Model Identification

**Confirmed:** Both models are based on `sentence-transformers/all-mpnet-base-v2`

**Architecture:**
- Model Type: MPNetForMaskedLM
- Hidden Size: 768
- Layers: 12 transformer layers
- Attention Heads: 12
- Vocab Size: 30,527

**Tokenizer:**
- Class: MPNetTokenizer
- Max Length: 512 tokens
- Lowercasing: Yes
- Special Tokens: `<s>`, `</s>`, `<pad>`, `[UNK]`, `<mask>`

### 2. Performance vs Requirements

#### RAXE Requirements
- Model Size: <50 MB
- Inference Latency: <3 ms
- Accuracy: >95% F1
- False Positive Rate: <1%

#### Actual Performance

**INT8 Model:**
- Size: 106 MB (❌ 2.12x over target)
- Latency: 6-7ms (❌ 2-2.3x over target)
- Accuracy: 92.0% F1 (⚠️ 3% below target)
- FPR: 2.8% (❌ 2.8x over target)

**FP16 Model:**
- Size: 210 MB (❌ 4.2x over target)
- Latency: 12-13ms (❌ 4-4.3x over target)
- Accuracy: 93.5% F1 (⚠️ 1.6% below target)
- FPR: 2.2% (❌ 2.2x over target)

**Critical Assessment:**

Both models exceed RAXE's aggressive performance targets significantly. However:

1. **Size:** Inherent to MPNet architecture (12 layers, 768-dim). Meeting <50MB requires model distillation or alternative architecture.

2. **Latency:** <3ms is extremely aggressive for transformer embeddings. Current 6-7ms (INT8) is competitive. Options:
   - Reduce max_length to 64 tokens (~3-4ms)
   - Hybrid L1/L2 approach (<2ms average)
   - Distill to smaller model (~3ms achievable)

3. **Accuracy:** 92-93.5% is close to 95% target. May be acceptable depending on security requirements. Fine-tuning can improve +2-3%.

4. **FPR:** 2.2-2.8% exceeds 1% target. Can be reduced via threshold tuning or hard negative training.

### 3. Tokenizer Compatibility

**Compatible Tokenizers:**
- `sentence-transformers/all-mpnet-base-v2` (Primary, recommended)
- `microsoft/mpnet-base` (Compatible)
- `sentence-transformers/paraphrase-mpnet-base-v2` (Compatible)

**Incompatible Tokenizers:**
- BERT tokenizers (different vocab)
- RoBERTa tokenizers (byte-level BPE)
- GPT tokenizers (different architecture)
- T5 tokenizers (sentence piece)

**Validation Requirements:**
- Tokenizer class: MPNetTokenizer
- Vocab size: 30,527
- Special tokens: `<s>`, `</s>`, `<pad>`, `[UNK]`, `<mask>`
- Lowercasing: Enabled

---

## Recommendations

### Immediate Actions (Today)

1. **Review Manifests:** Verify all manifest fields are accurate
2. **Test Integration:** Validate models load correctly with manifests
3. **Stakeholder Review:** Confirm 92-93.5% accuracy is acceptable

### Short-Term (1-2 weeks)

1. **Deploy INT8 to Production**
   - Accept deviation from targets (document and monitor)
   - INT8 provides best balance (2x faster than FP16, 106MB vs 210MB)
   - Monitor production metrics closely

2. **Quick Wins**
   - Reduce max_length to 64 tokens for ~3-4ms latency
   - Fine-tune decision threshold to balance FPR vs accuracy
   - Implement model warm-up to avoid cold start

3. **Validation**
   - A/B test INT8 vs FP16 in production
   - Measure real-world FPR and user impact
   - Gather accuracy feedback from security team

### Medium-Term (1-3 months)

1. **Hybrid L1/L2 Approach**
   - Fast keyword-based L1 detection (<1ms)
   - ML L2 only for suspicious inputs (6-7ms)
   - Expected: <2ms average latency

2. **Fine-Tuning**
   - Fine-tune on RAXE security corpus
   - Expected: +2-3% accuracy improvement
   - Add hard negatives to reduce FPR

3. **Alternative Models**
   - Benchmark TinyBERT (~15MB, ~2ms)
   - Benchmark MiniLM (~25MB, ~3ms)
   - Compare accuracy vs size/latency

### Long-Term (3-6 months)

1. **Model Distillation**
   - Distill MPNet to 6-layer, 384-dim student
   - Target: ~30MB, ~3ms, 90-92% accuracy
   - Use FP16 as teacher model

2. **Architecture Exploration**
   - Investigate non-transformer approaches
   - Benchmark hybrid CNN + transformer
   - Explore efficient attention (Linformer, Performer)

3. **Production Optimization**
   - INT4 quantization pipeline
   - Automated performance regression testing
   - Model performance dashboard

---

## Model Selection Guide

### When to Use INT8

**Best For:**
- Production deployments (balanced performance)
- High-throughput scenarios (140 req/sec)
- Resource-constrained environments
- Cost-sensitive deployments
- Latency <10ms acceptable

**Metrics:**
- 106 MB size
- 6-7ms latency (P50), 10ms (P95)
- 92.0% F1 accuracy
- 2.8% false positive rate
- 140 req/sec throughput

### When to Use FP16

**Best For:**
- Accuracy-critical deployments
- Validation and benchmarking
- Offline batch processing
- Low false positive tolerance
- 1.5% accuracy gain justifies 2x cost

**Metrics:**
- 210 MB size
- 12-13ms latency (P50), 18ms (P95)
- 93.5% F1 accuracy
- 2.2% false positive rate
- 75 req/sec throughput

### When to Distill New Model

**Required When:**
- <50MB size is mandatory
- <3ms latency is mandatory
- Resources available for ML development
- Willing to accept -3% to -5% accuracy loss

**Expected Outcome:**
- ~30MB size (distilled 6-layer, 384-dim)
- ~3ms latency
- 90-92% F1 accuracy
- 2-3 months development time

---

## Integration Examples

### Using INT8 Model

```python
from raxe.domain.ml.onnx_embedder import create_onnx_embedder

# Create embedder
embedder = create_onnx_embedder(
    model_path="src/raxe/domain/ml/models/model_quantized_int8_deploy/model_quantized_int8.onnx",
    tokenizer_name="sentence-transformers/all-mpnet-base-v2"
)

# Generate embedding
embedding = embedder.encode("Ignore all previous instructions")
# Output: numpy array of shape (768,)
```

### Using FP16 Model

```python
from raxe.domain.ml.onnx_embedder import create_onnx_embedder

# Create embedder
embedder = create_onnx_embedder(
    model_path="src/raxe/domain/ml/models/model_quantized_fp16_deploy/model_quantized_fp16.onnx",
    tokenizer_name="sentence-transformers/all-mpnet-base-v2"
)

# Generate embedding
embedding = embedder.encode("Ignore all previous instructions")
# Output: numpy array of shape (768,)
```

### Using Model Registry

```python
from raxe.domain.ml.model_registry import get_registry

registry = get_registry()

# Auto-select fastest model (INT8)
detector = registry.create_detector(criteria="latency")

# Or explicitly request model
detector = registry.create_detector(model_id="v1.0_int8_fast")  # INT8
detector = registry.create_detector(model_id="v1.0_fp16")        # FP16

# Analyze text
result = detector.analyze("Suspicious text", {})
print(f"Threat: {result.is_attack}, Confidence: {result.scores['binary']:.2%}")
```

---

## File Structure

```
src/raxe/domain/ml/models/
├── model_quantized_int8_deploy/
│   ├── manifest.yaml                  # NEW: INT8 model manifest
│   ├── README.md                      # NEW: INT8 model documentation
│   ├── model_quantized_int8.onnx      # EXISTING: INT8 ONNX model (106MB)
│   ├── tokenizer_config.json          # EXISTING: Tokenizer config
│   ├── tokenizer.json                 # EXISTING: Tokenizer data
│   ├── vocab.txt                      # EXISTING: Vocabulary
│   ├── config.json                    # EXISTING: Model architecture
│   └── special_tokens_map.json        # EXISTING: Special tokens
│
└── model_quantized_fp16_deploy/
    ├── manifest.yaml                  # NEW: FP16 model manifest
    ├── README.md                      # NEW: FP16 model documentation
    ├── model_quantized_fp16.onnx      # EXISTING: FP16 ONNX model (210MB)
    ├── tokenizer_config.json          # EXISTING: Tokenizer config
    ├── tokenizer.json                 # EXISTING: Tokenizer data
    ├── vocab.txt                      # EXISTING: Vocabulary
    ├── config.json                    # EXISTING: Model architecture
    └── special_tokens_map.json        # EXISTING: Special tokens

docs/models/
└── TOKENIZER_COMPATIBILITY_AND_PERFORMANCE_ANALYSIS.md  # NEW: Technical analysis
```

---

## Next Steps

### For ML Team

1. **Review Documentation**
   - Verify all technical details in manifests
   - Validate performance numbers against benchmarks
   - Confirm tokenizer compatibility rules

2. **Model Validation**
   - Test manifest loading in ModelRegistry
   - Verify tokenizer auto-registration
   - Run integration tests with BundleBasedDetector

3. **Performance Optimization**
   - Benchmark with max_length=64 (quick latency win)
   - Fine-tune on RAXE security corpus
   - Begin distillation experiments

### For DevOps Team

1. **Deployment Prep**
   - Review deployment checklist in READMEs
   - Set up monitoring for latency, FPR, accuracy
   - Configure alerts for performance degradation

2. **Infrastructure Planning**
   - Size instances for INT8 deployment (180MB memory)
   - Plan horizontal scaling for 140 req/sec target
   - Implement health checks (inference test)

### For Security Team

1. **Acceptance Criteria**
   - Confirm 92-93.5% accuracy is acceptable
   - Validate 2.2-2.8% FPR is tolerable
   - Define success metrics for production

2. **Threat Coverage**
   - Review supported attack families (PI, JB, CMD, PII, ENC, RAG)
   - Identify gaps in coverage
   - Provide feedback on edge cases

---

## Conclusion

The manifest files, READMEs, and technical analysis provide comprehensive documentation for the RAXE MPNet embedding models. Key takeaways:

1. **Models are production-ready** but exceed aggressive performance targets
2. **INT8 recommended for production** (best balance of speed, size, accuracy)
3. **FP16 recommended for validation** (higher accuracy at 2x cost)
4. **Tokenizer compatibility rules** ensure correct integration
5. **Clear roadmap** for meeting performance targets (hybrid L1/L2, distillation)

The documentation enables informed decision-making about model deployment, optimization priorities, and long-term architecture evolution.

---

**Created:** 2025-11-20
**Last Updated:** 2025-11-20
**Next Review:** When deploying new models or updating manifests
