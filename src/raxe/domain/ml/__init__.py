"""L2 ML-based threat detection.

This module defines the protocol and interfaces for L2 machine learning
threat detection that augments L1 rule-based detection.

L2 provides:
- Semantic threat detection
- Context-aware analysis
- Encoded content detection
- Probabilistic predictions

L2 receives L1 results as features and returns predictions.
All implementations must be <5ms for production use.
"""

from raxe.domain.ml.production_detector import (
    ProductionL2Detector,
    create_production_l2_detector,
)
from raxe.domain.ml.protocol import (
    L2Detector,
    L2Prediction,
    L2Result,
    L2ThreatType,
)
from raxe.domain.ml.stub_detector import StubL2Detector

# ONNX detector (optional - requires onnxruntime)
try:
    from raxe.domain.ml.onnx_production_detector import (
        ProductionONNXDetector,
        create_onnx_l2_detector,
    )
    _has_onnx = True
except ImportError:
    ProductionONNXDetector = None
    create_onnx_l2_detector = None
    _has_onnx = False

__all__ = [
    "L2Detector",
    "L2Prediction",
    "L2Result",
    "L2ThreatType",
    "ProductionL2Detector",
    "StubL2Detector",
    "create_production_l2_detector",
    "ProductionONNXDetector",
    "create_onnx_l2_detector",
]
