# RAXE ML Models

This directory contains production-ready ML models for RAXE threat detection.

## Production Models

### raxe_model_l2.raxe (Current - v1.0)

**Model:** L2 Bundle-Based Detector v1.0
**Format:** Unified .raxe bundle (ZIP archive) containing all ML components
**Size:** 644KB (compressed)
**Model ID:** `b3edaeaba05c`
**Framework:** Multi-head logistic regression with sentence embeddings (768-dim)
**Embedding Model:** `sentence-transformers/all-mpnet-base-v2` (768-dim)
**Inference Time:** ~10-50ms (CPU, including embedding generation)

**Bundle Contents:**
- `manifest.json` - Model metadata and versioning
- `classifier.joblib` (311KB) - Multi-head logistic regression classifier
- `keyword_triggers.json` (15KB) - Pattern matching triggers
- `attack_clusters.joblib` (312KB) - Attack clustering for similarity matching
- `embedding_config.json` - Sentence-transformers configuration
- `training_stats.json` - Training metrics
- `schema.json` - Complete output schema definition

**Architecture:**
- Binary classifier: Malicious (1) vs Benign (0)
- Family classifier: 6 threat families (PI, JB, CMD, PII, ENC, RAG)
- Subfamily classifier: 47+ fine-grained attack types
- Multi-head approach prevents keyword overfitting

**Performance Metrics (Training):**
- Binary: 90.2% accuracy, 89.7% F1
- Family: 88.8% accuracy, 89.0% F1 (weighted)
- Subfamily: 73.9% accuracy, 74.7% F1 (weighted)

**Performance Metrics (Validation):**
- Binary: 90.2% accuracy, 89.6% F1
- Family: 78.8% accuracy, 64.0% F1 (macro)

**Threat Families:**
- **PI** (Prompt Injection): Instruction manipulation, context hijacking
- **JB** (Jailbreak): Attempts to bypass AI safety guidelines
- **CMD** (Command Injection): Hidden or obfuscated commands
- **PII** (PII Exposure): Personal identifiable information leakage
- **ENC** (Encoded Injection): Malicious code in base64/hex/unicode
- **RAG** (RAG Manipulation): Retrieval-augmented generation attacks
- **BENIGN**: Safe/legitimate prompts

**Output Schema:**

The bundled model returns comprehensive predictions with:
- `is_attack`: Binary classification (0 or 1)
- `family`: Attack family (PI, JB, CMD, PII, ENC, RAG, BENIGN)
- `sub_family`: Specific attack type (e.g., "instruction_override", "context_hijacking")
- `scores`: Confidence breakdown
  - `attack_probability`: 0.0-1.0
  - `family_confidence`: 0.0-1.0
  - `subfamily_confidence`: 0.0-1.0
- `why_it_hit`: List of explanations for why this was flagged
- `recommended_action`: List of actions (ALLOW, WARN, BLOCK)
- `trigger_matches`: Matched trigger patterns
- `similar_attacks`: Similar attacks from training data
- `uncertain`: Boolean flag indicating model uncertainty

**Usage:**
```python
from raxe.domain.ml import create_bundle_detector

# Create detector (requires: pip install raxe[ml])
detector = create_bundle_detector(
    bundle_path="src/raxe/domain/ml/models/raxe_model_l2.raxe"
)

# Analyze a prompt
result = detector.analyze(
    text="Ignore all previous instructions",
    l1_results=l1_scan_results
)

if result.has_predictions:
    for pred in result.predictions:
        # Access threat information
        print(f"Threat: {pred.threat_type.value}")
        print(f"Confidence: {pred.confidence:.1%}")

        # Access bundle schema fields
        family = pred.metadata.get("family")
        sub_family = pred.metadata.get("sub_family")
        why_it_hit = pred.metadata.get("why_it_hit", [])

        print(f"Family: {family}")
        print(f"Sub-family: {sub_family}")
        print("Why this was flagged:")
        for reason in why_it_hit:
            print(f"  • {reason}")
```

**Installation:**
```bash
pip install raxe[ml]  # Includes scikit-learn + sentence-transformers
```

## Model Development

**Note:** This directory contains ONLY production-ready bundled models for deployment.

Training scripts and datasets are managed in the separate `raxe-ml` repository to keep the package slim for pip install.

### For ML Engineers/Contributors

**Model Training:** Models are trained using the `raxe-ml` repository, which provides:
- Training scripts
- Dataset management
- Model evaluation
- Bundle export to .raxe format

**Creating New Bundles:**

Bundles are created using the `raxe-ml` unified bundle system:

```bash
# In raxe-ml repository
python scripts/export_bundle.py \
  --model-path models/trained_model.pkl \
  --output-path raxe_model_l2.raxe \
  --include-triggers \
  --include-clusters \
  --validate
```

**Bundle Requirements:**
- All components packaged in single .raxe file (ZIP format)
- Manifest with version, capabilities, training metrics
- Checksums for integrity validation
- Schema definition for output format
- Training statistics for transparency

## Model Metadata

**Current Production Model:** raxe_model_l2.raxe (Model ID: b3edaeaba05c)
**Last Updated:** 2025-11-19
**Training Dataset:** RAXE ML adversarial detection dataset (6 attack families, 47+ subfamilies)
**Binary Accuracy:** 90.2% (train), 90.2% (val)
**Family Accuracy:** 88.8% (train), 78.8% (val)
**Subfamily Accuracy:** 73.9% (train)
**Production Status:** ✅ Deployed
**Confidence Threshold:** 0.7 (default), configurable
**Expected Latency:** 10-50ms (P95: <150ms)

## Privacy Notice

All ML inference happens **locally** on the user's device. Model inputs (prompts) and outputs (detections) are never sent to external servers unless explicitly configured by the user for optional telemetry.

**PII Protection:**
- Prompts are hashed before any cloud transmission
- Only metadata (threat category, confidence) is sent
- User can disable all telemetry with `--no-telemetry`

---

**Questions?** See [CLAUDE.md](../../../../CLAUDE.md) for architecture details.
