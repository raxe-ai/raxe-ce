"""L2 ML-based threat detection.

This module defines the protocol and interfaces for L2 machine learning
threat detection that augments L1 rule-based detection.

L2 provides:
- Semantic threat detection using Gemma embeddings
- 5-head classification (is_threat, family, severity, technique, harm_types)
- Multilabel harm type classification
- Context-aware analysis with explainability
- Probabilistic predictions with confidence scores

L2 uses Gemma-based ONNX models containing:
- EmbeddingGemma-300M ONNX model (256d embeddings)
- 5 classifier heads (is_threat, threat_family, severity, primary_technique, harm_types)
- Gemma tokenizer
- Label configuration

Note: ML features require optional dependencies: pip install raxe[ml]
"""

# Protocol and base types (no ML dependencies required)
# Domain models (no ML dependencies required)
from raxe.domain.ml.gemma_models import (
    DEFAULT_HARM_THRESHOLDS,
    GemmaClassificationResult,
    HarmType,
    MultilabelResult,
    PrimaryTechnique,
    Severity,
    ThreatFamily,
)
from raxe.domain.ml.l2_config import (
    L2Config,
    L2EnsembleConfig,
    L2ThresholdConfig,
    create_example_config,
    get_l2_config,
    load_l2_config,
    reset_l2_config,
    set_l2_config,
)
from raxe.domain.ml.protocol import (
    L2Detector,
    L2Prediction,
    L2Result,
    L2ThreatType,
)
from raxe.domain.ml.scoring_models import (
    ActionType,
    ScoringMode,
    ScoringResult,
    ScoringThresholds,
    ThreatLevel,
    ThreatScore,
)
from raxe.domain.ml.stub_detector import StubL2Detector

# ML-dependent imports (require numpy, onnxruntime, transformers)
# These are lazily imported to allow basic SDK usage without ML deps
_ML_AVAILABLE = False
_ML_IMPORT_ERROR = None

try:
    from raxe.domain.ml.gemma_detector import (
        GemmaL2Detector,
        create_gemma_detector,
    )
    from raxe.domain.ml.threat_scorer import HierarchicalThreatScorer
    _ML_AVAILABLE = True
except ImportError as e:
    _ML_IMPORT_ERROR = str(e)
    # Provide stub implementations for when ML deps are missing
    GemmaL2Detector = None  # type: ignore[assignment, misc]
    HierarchicalThreatScorer = None  # type: ignore[assignment, misc]

    def create_gemma_detector(*args, **kwargs):  # type: ignore[misc]
        """Stub: ML dependencies not installed."""
        raise ImportError(
            f"ML features require optional dependencies. "
            f"Install with: pip install raxe[ml]\n"
            f"Original error: {_ML_IMPORT_ERROR}"
        )


def is_ml_available() -> bool:
    """Check if ML dependencies are available."""
    return _ML_AVAILABLE


def get_ml_import_error() -> str | None:
    """Get the ML import error message if ML is not available."""
    return _ML_IMPORT_ERROR


__all__ = [
    # Availability check
    "get_ml_import_error",
    "is_ml_available",
    # Domain Models (Gemma)
    "DEFAULT_HARM_THRESHOLDS",
    "GemmaClassificationResult",
    "HarmType",
    "MultilabelResult",
    "PrimaryTechnique",
    "Severity",
    "ThreatFamily",
    # Configuration
    "L2Config",
    "L2EnsembleConfig",
    "L2ThresholdConfig",
    "create_example_config",
    "get_l2_config",
    "load_l2_config",
    "reset_l2_config",
    "set_l2_config",
    # Threat Scoring
    "ActionType",
    "ScoringMode",
    "ScoringResult",
    "ScoringThresholds",
    "ThreatLevel",
    "ThreatScore",
    # L2 Detection
    "GemmaL2Detector",
    "HierarchicalThreatScorer",
    "L2Detector",
    "L2Prediction",
    "L2Result",
    "L2ThreatType",
    "StubL2Detector",
    "create_gemma_detector",
]
