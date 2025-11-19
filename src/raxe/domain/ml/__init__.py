"""L2 ML-based threat detection.

This module defines the protocol and interfaces for L2 machine learning
threat detection that augments L1 rule-based detection.

L2 provides:
- Semantic threat detection using sentence-transformers embeddings
- Multi-head classification (binary, family, subfamily)
- Context-aware analysis with explainability
- Encoded content detection
- Probabilistic predictions with confidence scores

L2 uses unified .raxe model bundles from raxe-ml for all ML components:
- Classifier (multi-head logistic regression)
- Keyword triggers (pattern matching)
- Attack clusters (similarity matching)
- Embedding configuration
- Training statistics
"""

from raxe.domain.ml.bundle_detector import (
    BundleBasedDetector,
    create_bundle_detector,
)
from raxe.domain.ml.protocol import (
    L2Detector,
    L2Prediction,
    L2Result,
    L2ThreatType,
)
from raxe.domain.ml.stub_detector import StubL2Detector

__all__ = [
    "L2Detector",
    "L2Prediction",
    "L2Result",
    "L2ThreatType",
    "BundleBasedDetector",
    "create_bundle_detector",
    "StubL2Detector",
]
