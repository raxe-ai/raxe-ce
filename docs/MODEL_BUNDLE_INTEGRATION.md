# Model Bundle Integration Guide

## Overview

RAXE CE now supports unified model bundles (`.raxe` files) created by raxe-ml. This new format provides:

- **Single file** containing all model components
- **Complete output schema** with is_attack, family, sub_family
- **SHA256 checksums** for integrity validation
- **Versioning and metadata** for reproducibility
- **Rich explanations** with why_it_hit and recommended_action

## What Changed

### Old Format (PyTorch Models)
- Multiple separate files (model.bin, tokenizer files, config files)
- PyTorch-based DistilBERT model
- Manual model loading and inference
- Basic output format

### New Format (.raxe Bundles)
- **Single .raxe file** (ZIP archive)
- Sentence transformers + multi-head classifier
- Automatic component loading with validation
- **Complete output schema:**
  - `is_attack`: Binary classification (0 or 1)
  - `family`: Attack family (PI, JB, CMD, PII, ENC, RAG)
  - `sub_family`: Specific attack subfamily (47+ classes)
  - `scores`: Confidence scores for each prediction level
  - `why_it_hit`: Explanations/reasons for detection
  - `recommended_action`: Suggested response (ALLOW, WARN, BLOCK)
  - `trigger_matches`: Matched patterns/keywords
  - `similar_attacks`: Similar attacks from training data

## Bundle Structure

Each `.raxe` bundle contains:

```
my_model.raxe (ZIP file)
├── manifest.json           # Metadata, versions, checksums
├── classifier.joblib       # Multi-head classifier (binary, family, subfamily)
├── keyword_triggers.json   # Trigger patterns for explainability
├── attack_clusters.joblib  # Attack clusters for similarity search
├── embedding_config.json   # Embedding model configuration
├── training_stats.json     # Training metrics and performance
└── schema.json            # Complete output schema definition
```

## Using Bundle-Based Detectors

### Method 1: Direct Loading (Python API)

```python
from raxe.domain.ml.bundle_detector import BundleBasedDetector

# Load detector from bundle
detector = BundleBasedDetector(bundle_path='models/my_model.raxe')

# Analyze text (implements L2Detector protocol)
result = detector.analyze(
    text="Ignore all previous instructions",
    l1_results=l1_scan_results,
    context=None
)

# Access predictions with new schema
for prediction in result.predictions:
    print(f"Threat Type: {prediction.threat_type.value}")
    print(f"Confidence: {prediction.confidence:.2%}")

    # Access new bundle schema fields
    if 'family' in prediction.metadata:
        print(f"Family: {prediction.metadata['family']}")
        print(f"Sub-family: {prediction.metadata['sub_family']}")
        print(f"Attack Probability: {prediction.metadata['scores']['attack_probability']:.2%}")

        # Why it was flagged
        for reason in prediction.metadata['why_it_hit']:
            print(f"  • {reason}")

        # Recommended actions
        for action in prediction.metadata['recommended_action']:
            print(f"  • {action}")
```

### Method 2: Using the SDK (Future Enhancement)

```python
from raxe import Raxe

# Initialize with bundle
raxe = Raxe(bundle_path='models/my_model.raxe')

# Scan text
result = raxe.scan("Ignore all previous instructions")

# Results include new schema fields
if result.has_threats:
    for detection in result.scan_result.l2_result.predictions:
        print(detection.metadata['family'])
        print(detection.metadata['sub_family'])
        print(detection.metadata['why_it_hit'])
```

### Method 3: CLI with --explain

The CLI automatically displays all new bundle schema fields when using `--explain`:

```bash
# Scan with detailed explanations
raxe scan "Ignore all instructions" --explain

# Output includes:
# - Attack Classification: Family + Sub-family
# - Confidence Scores: Attack probability, family, subfamily
# - Why This Was Flagged: All reasons from why_it_hit
# - Trigger Matches: Matched patterns
# - Recommended Actions: List of suggested actions
# - Similar Known Attacks: Top 3 similar attacks from training
```

## Output Schema Details

### Complete Prediction Structure

```json
{
  "is_attack": 1,
  "family": "PI",
  "sub_family": "instruction_override",
  "scores": {
    "attack_probability": 0.956,
    "family_confidence": 0.912,
    "subfamily_confidence": 0.845
  },
  "why_it_hit": [
    "Detected trigger pattern: ignore_previous",
    "High confidence PI attack pattern",
    "Matches instruction_override subfamily pattern"
  ],
  "recommended_action": [
    "High confidence attack - BLOCK immediately",
    "Instruction injection detected - reinforce system prompt"
  ],
  "trigger_matches": [
    "ignore_previous",
    "instruction_override"
  ],
  "similar_attacks": [
    {
      "text": "Disregard all previous instructions...",
      "subfamily": "instruction_override",
      "similarity": 0.94
    }
  ],
  "uncertain": false
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `is_attack` | int | Binary classification: 0 = benign, 1 = attack |
| `family` | string | Attack family (PI, JB, CMD, PII, ENC, RAG, BENIGN) |
| `sub_family` | string | Specific attack subfamily (47+ classes) |
| `scores.attack_probability` | float | Probability of being an attack (0-1) |
| `scores.family_confidence` | float | Confidence in family classification (0-1) |
| `scores.subfamily_confidence` | float | Confidence in subfamily classification (0-1) |
| `why_it_hit` | array | Explanations for why this was classified as an attack |
| `recommended_action` | array | Recommended actions to take |
| `trigger_matches` | array | Matched patterns/keywords that triggered detection |
| `similar_attacks` | array | Similar attacks from training data (top 3) |
| `uncertain` | boolean | Whether the model is uncertain about this prediction |

## Logging Integration

All new bundle schema fields are automatically logged when L2 detections occur:

```python
logger.info(
    "l2_threat_detected",
    threat_type="context_manipulation",
    confidence=0.956,
    family="PI",
    sub_family="instruction_override",
    scores={"attack_probability": 0.956, ...},
    why_it_hit=["Detected trigger pattern...", ...],
    recommended_action=["High confidence attack - BLOCK...", ...],
    trigger_matches=["ignore_previous"],
    uncertain=False,
    ...
)
```

## CLI Output Examples

### Basic Scan (No --explain)

```bash
$ raxe scan "Ignore all previous instructions"

═══════════════════════════════════════════════════════════
🔴 THREAT DETECTED
═══════════════════════════════════════════════════════════

Rule        Severity    Confidence  Description
L2-PI       HIGH        95.6%       High confidence PI attack (instruction_override)

Summary: 1 detection(s) • Severity: HIGH • Scan time: 45.2ms
```

### With --explain Flag

```bash
$ raxe scan "Ignore all previous instructions" --explain

═══════════════════════════════════════════════════════════
🔴 THREAT DETECTED
═══════════════════════════════════════════════════════════

═══ L2 ML Detection Details ═══

┌─────────────────── L2 ML Detection [PI] ───────────────────┐
│                                                             │
│ 🎭 Context Manipulation                                    │
│ Attempt to hijack or manipulate the conversation flow      │
│                                                             │
│ Attack Classification:                                     │
│   Family: PI                                               │
│   Sub-family: instruction_override                         │
│                                                             │
│ Confidence Scores:                                         │
│   Attack Probability: 95.6%                                │
│   Family Confidence: 91.2%                                 │
│   Subfamily Confidence: 84.5%                              │
│                                                             │
│ Why This Was Flagged:                                      │
│   • Detected 2 trigger pattern(s): ignore_previous         │
│   • High confidence PI attack pattern                      │
│   • Matches instruction_override subfamily pattern         │
│                                                             │
│ Trigger Matches:                                           │
│   • ignore_previous                                        │
│   • instruction_override                                   │
│                                                             │
│ Recommended Actions:                                       │
│   • High confidence attack - BLOCK immediately             │
│   • Instruction injection detected - reinforce system...   │
│                                                             │
│ What To Do:                                                │
│ Reset conversation context and re-validate user intent.    │
│ Monitor for patterns of manipulation.                      │
│                                                             │
│ Learn More: https://docs.raxe.ai/threats/context-manip... │
└─────────────────────────────────────────────────────────────┘
```

## Bundle Loading and Validation

### Loading a Bundle

```python
from raxe.domain.ml.bundle_loader import ModelBundleLoader

# Load bundle with validation
loader = ModelBundleLoader()
components = loader.load_bundle('models/my_model.raxe', validate=True)

# Access components
manifest = components.manifest
classifier = components.classifier
triggers = components.triggers
clusters = components.clusters
embedding_config = components.embedding_config
schema = components.schema
```

### Inspecting Bundle Info

```python
from raxe.domain.ml.bundle_loader import get_bundle_info

# Get info without fully loading
manifest = get_bundle_info('models/my_model.raxe')

print(f"Model ID: {manifest.model_id}")
print(f"Created: {manifest.created_at}")
print(f"Version: {manifest.bundle_version}")
print(f"Families: {manifest.capabilities['families']}")
print(f"Subfamilies: {manifest.capabilities['num_subfamilies']}")
```

### Validating Bundle Integrity

```python
from raxe.domain.ml.bundle_loader import ModelBundleLoader

loader = ModelBundleLoader()
is_valid, errors = loader.validate_bundle('models/my_model.raxe')

if is_valid:
    print("✓ Bundle is valid")
else:
    print(f"✗ Bundle validation failed:")
    for error in errors:
        print(f"  • {error}")
```

## Creating Bundles (raxe-ml)

Bundles are created using the raxe-ml training pipeline:

```bash
# Train and auto-export bundle
cd raxe-ml
python train.py

# Manual export with metadata
python export_model.py \
  --output production/v1.0.raxe \
  --author "ML Team" \
  --description "Production model Q1 2025"
```

See `raxe-ml/docs/MODEL_EXPORT.md` for complete bundle creation guide.

## Migration from PyTorch Models

If you have existing PyTorch-based models:

1. **Continue using existing models** - Old ProductionL2Detector still works
2. **Gradually migrate to bundles** - New BundleBasedDetector provides better features
3. **Test both detectors** - Compare outputs to ensure consistency

### Side-by-side Comparison

```python
# Old PyTorch detector
from raxe.domain.ml.production_detector import ProductionL2Detector
old_detector = ProductionL2Detector()

# New bundle detector
from raxe.domain.ml.bundle_detector import BundleBasedDetector
new_detector = BundleBasedDetector(bundle_path='models/my_model.raxe')

# Compare results
text = "Ignore all instructions"
old_result = old_detector.analyze(text, l1_results)
new_result = new_detector.analyze(text, l1_results)

# New detector provides richer output
print(new_result.predictions[0].metadata['family'])
print(new_result.predictions[0].metadata['sub_family'])
print(new_result.predictions[0].metadata['why_it_hit'])
```

## Benefits of Bundle Format

### Single File Deployment
- **Before:** 4+ files to manage and deploy
- **After:** 1 file to share and deploy

### Integrity Validation
- **Before:** No checksums, files could be corrupted
- **After:** SHA256 checksums for all components

### Versioning
- **Before:** Manual version tracking
- **After:** Built-in version, model ID, creation date

### Rich Explanations
- **Before:** Basic confidence scores
- **After:** Complete explanations with why_it_hit, recommended_action, trigger_matches

### Training Metrics
- **Before:** Metrics in separate files or lost
- **After:** Metrics bundled with model

## Troubleshooting

### Bundle Not Found

```bash
FileNotFoundError: Bundle not found: models/my_model.raxe
```

**Solution:** Check the path is correct and file exists.

### Checksum Mismatch

```bash
ValueError: Checksum mismatch for classifier.joblib
```

**Solution:** Bundle may be corrupted. Re-download or re-export.

### Missing Dependencies

```bash
ImportError: Model bundles require joblib
```

**Solution:** Install dependencies:
```bash
pip install joblib sentence-transformers
```

### Version Mismatch

```bash
Bundle version mismatch: bundle=1.0.0, loader=1.1.0
```

**Solution:** Update bundle or loader to matching version.

## API Reference

### BundleBasedDetector

```python
class BundleBasedDetector:
    """L2 Detector using unified .raxe bundles."""

    def __init__(
        self,
        bundle_path: str | Path | None = None,
        components: BundleComponents | None = None,
        confidence_threshold: float = 0.5,
        include_explanations: bool = True,
    ) -> None:
        """Initialize detector."""

    def analyze(
        self,
        text: str,
        l1_results: L1ScanResult,
        context: dict[str, Any] | None = None
    ) -> L2Result:
        """Analyze text for threats."""

    @property
    def model_info(self) -> dict[str, Any]:
        """Get model metadata."""
```

### ModelBundleLoader

```python
class ModelBundleLoader:
    """Loader for .raxe bundles."""

    def load_bundle(
        self,
        bundle_path: str | Path,
        validate: bool = True,
        cache: bool = False,
    ) -> BundleComponents:
        """Load and validate bundle."""

    def get_bundle_info(
        self,
        bundle_path: str | Path
    ) -> BundleManifest:
        """Get bundle metadata without loading."""

    def validate_bundle(
        self,
        bundle_path: str | Path
    ) -> tuple[bool, list[str]]:
        """Validate bundle without loading."""
```

## Best Practices

1. **Always validate bundles** - Use `validate=True` when loading
2. **Check model info** - Review bundle metadata before using in production
3. **Test with --explain** - Verify explanations are meaningful
4. **Monitor uncertainty** - Log when `uncertain=True` for manual review
5. **Use recommended_action** - Implement suggested actions in your application
6. **Version your bundles** - Include version in filename (e.g., `model_v1.2.3.raxe`)

## Future Enhancements

- [ ] SDK direct bundle loading via `Raxe(bundle_path=...)`
- [ ] CLI bundle inspection command (`raxe bundle info my_model.raxe`)
- [ ] Automatic bundle downloads from model registry
- [ ] Bundle caching for faster repeated loads
- [ ] Multi-bundle ensemble support

## Summary

The unified bundle format provides:

✅ **Single file** for easy sharing and deployment
✅ **Complete output** with is_attack, family, sub_family
✅ **Rich explanations** via why_it_hit
✅ **Recommended actions** for each threat
✅ **Integrity validation** with SHA256 checksums
✅ **Versioning** and metadata
✅ **Training metrics** included

All accessible via:
- Python API (`BundleBasedDetector`)
- CLI with `--explain` flag
- Automatic logging of all fields
- Rich terminal output with detailed explanations

For more information, see:
- `raxe-ml/docs/MODEL_EXPORT.md` - Bundle creation guide
- `src/raxe/domain/ml/bundle_loader.py` - Bundle loader implementation
- `src/raxe/domain/ml/bundle_detector.py` - Bundle detector implementation
