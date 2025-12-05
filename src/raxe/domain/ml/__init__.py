"""L2 ML-based threat detection.

This module defines the protocol and interfaces for L2 machine learning
threat detection that augments L1 rule-based detection.

L2 provides:
- Semantic threat detection using ONNX embeddings
- Multi-head classification (binary, family, subfamily)
- Context-aware analysis with explainability
- Encoded content detection
- Probabilistic predictions with confidence scores

L2 uses folder-based ONNX models containing:
- ONNX embeddings model
- ONNX classifier models (binary, family, subfamily)
- Label encoders
- Model configuration

Note: ML features require optional dependencies: pip install raxe[ml]
"""

# Protocol and base types (no ML dependencies required)
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

# ML-dependent imports (require numpy, onnxruntime)
# These are lazily imported to allow basic SDK usage without ML deps
_ML_AVAILABLE = False
_ML_IMPORT_ERROR = None

try:
    from raxe.domain.ml.folder_detector import (
        FolderL2Detector,
        create_folder_detector,
    )
    from raxe.domain.ml.threat_scorer import HierarchicalThreatScorer
    _ML_AVAILABLE = True
except ImportError as e:
    _ML_IMPORT_ERROR = str(e)
    # Provide stub implementations for when ML deps are missing
    FolderL2Detector = None  # type: ignore[assignment, misc]
    HierarchicalThreatScorer = None  # type: ignore[assignment, misc]

    def create_folder_detector(*args, **kwargs):  # type: ignore[misc]
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
    # Threat Scoring
    "ActionType",
    # L2 Detection
    "FolderL2Detector",
    "HierarchicalThreatScorer",
    "L2Detector",
    "L2Prediction",
    "L2Result",
    "L2ThreatType",
    "ScoringMode",
    "ScoringResult",
    "ScoringThresholds",
    "StubL2Detector",
    "ThreatLevel",
    "ThreatScore",
    "create_folder_detector",
]
