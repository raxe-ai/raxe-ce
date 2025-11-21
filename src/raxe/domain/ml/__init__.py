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
"""

from raxe.domain.ml.folder_detector import (
    FolderL2Detector,
    create_folder_detector,
)
from raxe.domain.ml.protocol import (
    L2Detector,
    L2Prediction,
    L2Result,
    L2ThreatType,
)
from raxe.domain.ml.stub_detector import StubL2Detector

__all__ = [
    "FolderL2Detector",
    "L2Detector",
    "L2Prediction",
    "L2Result",
    "L2ThreatType",
    "StubL2Detector",
    "create_folder_detector",
]
