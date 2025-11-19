"""
Bundle-Based L2 Detector

Implements L2Detector protocol using unified .raxe model bundles from raxe-ml.

This detector:
1. Loads .raxe bundles (single file with all components)
2. Uses sentence transformers + multi-head classifier
3. Returns predictions with new output schema:
   - is_attack: Binary classification
   - family: Attack family (PI, JB, CMD, PII, ENC, RAG)
   - sub_family: Specific attack subfamily (47+ classes)
   - scores: Confidence scores
   - why_it_hit: Explanations/reasons
   - recommended_action: ALLOW, WARN, or BLOCK
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from raxe.domain.engine.executor import ScanResult as L1ScanResult
from raxe.domain.ml.bundle_loader import BundleComponents, ModelBundleLoader
from raxe.domain.ml.protocol import L2Detector, L2Prediction, L2Result, L2ThreatType
from raxe.utils.logging import get_logger

logger = get_logger(__name__)


class BundleBasedDetector:
    """
    L2 Detector using unified .raxe bundles from raxe-ml.

    This detector loads models exported by raxe-ml's unified bundle system
    and provides predictions with the complete output schema including:
    - is_attack, family, sub_family
    - scores, why_it_hit, recommended_action

    Performance:
    - Average inference: 10-50ms (depending on embedding model)
    - P95: <150ms
    - Includes explanation generation

    Example:
        # Load from bundle
        detector = BundleBasedDetector(bundle_path='models/my_model.raxe')

        # Analyze text
        result = detector.analyze("Ignore all instructions", l1_results)

        # Access predictions with new schema
        for pred in result.predictions:
            print(f"Threat: {pred.threat_type.value}")
            print(f"Confidence: {pred.confidence:.2%}")
            print(f"Why: {pred.explanation}")

            # New fields from bundle
            if pred.metadata.get('family'):
                print(f"Family: {pred.metadata['family']}")
                print(f"Sub-family: {pred.metadata['sub_family']}")
                print(f"Recommended: {pred.metadata['recommended_action']}")
    """

    # Map bundle families to L2 threat types
    FAMILY_TO_L2_TYPE = {
        "PI": L2ThreatType.CONTEXT_MANIPULATION,
        "JB": L2ThreatType.SEMANTIC_JAILBREAK,
        "CMD": L2ThreatType.OBFUSCATED_COMMAND,
        "PII": L2ThreatType.DATA_EXFIL_PATTERN,
        "ENC": L2ThreatType.ENCODED_INJECTION,
        "RAG": L2ThreatType.DATA_EXFIL_PATTERN,
        "BENIGN": L2ThreatType.UNKNOWN,
    }

    # Map confidence to recommended action
    BLOCK_THRESHOLD = 0.8
    WARN_THRESHOLD = 0.5

    def __init__(
        self,
        bundle_path: str | Path | None = None,
        components: BundleComponents | None = None,
        confidence_threshold: float = 0.5,
        include_explanations: bool = True,
        onnx_model_path: str | Path | None = None,
    ):
        """
        Initialize bundle-based detector.

        Args:
            bundle_path: Path to .raxe bundle file (OR components)
            components: Pre-loaded BundleComponents (OR bundle_path)
            confidence_threshold: Minimum confidence to report predictions
            include_explanations: Whether to generate explanations (default: True)
            onnx_model_path: Optional path to ONNX model for faster embeddings (5x speedup)

        Note: Provide either bundle_path OR components, not both.

        Example:
            # Load from bundle path
            detector = BundleBasedDetector(bundle_path='models/my_model.raxe')

            # OR use pre-loaded components
            loader = ModelBundleLoader()
            components = loader.load_bundle('models/my_model.raxe')
            detector = BundleBasedDetector(components=components)

            # With ONNX quantized model for 5x speedup
            detector = BundleBasedDetector(
                bundle_path='models/my_model.raxe',
                onnx_model_path='models/quantized_int8.onnx'
            )
        """
        if bundle_path is None and components is None:
            raise ValueError("Must provide either bundle_path or components")

        if bundle_path is not None and components is not None:
            raise ValueError("Provide either bundle_path or components, not both")

        self.confidence_threshold = confidence_threshold
        self.include_explanations = include_explanations

        # Load bundle
        if components is not None:
            logger.info("Using pre-loaded bundle components")
            self.components = components
        else:
            logger.info(f"Loading bundle from: {bundle_path}")
            loader = ModelBundleLoader()
            self.components = loader.load_bundle(bundle_path, validate=True)

        # Extract key components
        self.manifest = self.components.manifest
        self.classifier = self.components.classifier
        self.triggers = self.components.triggers
        self.clusters = self.components.clusters
        self.embedding_config = self.components.embedding_config
        self.schema = self.components.schema

        # Load embedding model (ONNX or sentence-transformers)
        if onnx_model_path:
            # Use ONNX embedder for 5x speedup
            logger.info(f"Loading ONNX embedder: {onnx_model_path}")
            try:
                from raxe.domain.ml.onnx_embedder import create_onnx_embedder
            except ImportError as e:
                raise ImportError(
                    "ONNX embedder requires onnxruntime and transformers. "
                    "Install with: pip install onnxruntime transformers"
                ) from e

            self.embedder = create_onnx_embedder(
                model_path=onnx_model_path,
                tokenizer_name=self.embedding_config['model_name']
            )
            self.embedder.max_seq_length = self.embedding_config['max_length']
            logger.info(f"✓ Bundle-based detector ready (ONNX mode) - Model ID: {self.manifest.model_id}")

        else:
            # Use sentence-transformers (slower but easier)
            logger.info(f"Loading embedder: {self.embedding_config['model_name']}")
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise ImportError(
                    "Bundle-based detector requires sentence-transformers. "
                    "Install with: pip install sentence-transformers"
                ) from e

            self.embedder = SentenceTransformer(self.embedding_config['model_name'])
            self.embedder.max_seq_length = self.embedding_config['max_length']
            logger.info(f"✓ Bundle-based detector ready (Model ID: {self.manifest.model_id})")

    def analyze(
        self,
        text: str,
        l1_results: L1ScanResult,
        context: dict[str, Any] | None = None
    ) -> L2Result:
        """
        Analyze text using bundle-based ML model.

        Implements L2Detector protocol with new output schema.

        Args:
            text: Text to analyze
            l1_results: L1 rule-based detection results
            context: Optional context dictionary

        Returns:
            L2Result with predictions in new format

        Example:
            result = detector.analyze("Ignore all instructions", l1_results)

            if result.has_predictions:
                for pred in result.predictions:
                    # Access new schema fields
                    print(pred.metadata['family'])        # "PI"
                    print(pred.metadata['sub_family'])    # "instruction_override"
                    print(pred.metadata['why_it_hit'])    # ["Detected trigger..."]
                    print(pred.metadata['recommended_action'])  # "BLOCK"
        """
        start_time = time.perf_counter()

        try:
            # 1. Generate embedding
            embedding = self.embedder.encode(text, normalize_embeddings=True)

            # 2. Run classifier inference
            prediction = self._predict(embedding, text)

            # 3. Map to L2 protocol format
            predictions = []

            if prediction['is_attack'] == 1 and prediction['scores']['attack_probability'] >= self.confidence_threshold:
                # Map family to L2 threat type
                family = prediction['family']
                l2_type = self.FAMILY_TO_L2_TYPE.get(family, L2ThreatType.UNKNOWN)

                # Generate explanation
                explanation = self._generate_explanation(prediction)

                # Create L2 prediction with extended metadata
                l2_pred = L2Prediction(
                    threat_type=l2_type,
                    confidence=prediction['scores']['attack_probability'],
                    explanation=explanation if self.include_explanations else None,
                    features_used=[
                        f"family={family}",
                        f"subfamily={prediction['sub_family']}",
                        f"trigger_matches={len(prediction.get('trigger_matches', []))}",
                    ],
                    metadata={
                        # New schema fields
                        "is_attack": prediction['is_attack'],
                        "family": family,
                        "sub_family": prediction['sub_family'],
                        "scores": prediction['scores'],
                        "why_it_hit": prediction.get('why_it_hit', []),
                        "recommended_action": prediction.get('recommended_action', []),
                        "trigger_matches": prediction.get('trigger_matches', []),
                        "similar_attacks": prediction.get('similar_attacks', []),
                        "uncertain": prediction.get('uncertain', False),
                    }
                )
                predictions.append(l2_pred)

            # Calculate processing time
            processing_time_ms = (time.perf_counter() - start_time) * 1000

            # Create L2 result
            return L2Result(
                predictions=predictions,
                confidence=prediction['scores']['attack_probability'] if prediction['is_attack'] else 1.0 - prediction['scores']['attack_probability'],
                processing_time_ms=processing_time_ms,
                model_version=f"bundle-{self.manifest.bundle_version}-{self.manifest.model_id[:8]}",
                features_extracted={
                    "text_length": len(text),
                    "embedding_dim": len(embedding),
                    "l1_detections": l1_results.detection_count if l1_results else 0,
                },
                metadata={
                    "model_id": self.manifest.model_id,
                    "bundle_version": self.manifest.bundle_version,
                    "schema_version": self.manifest.schema_version,
                    "embedding_model": self.embedding_config['model_name'],
                    "capabilities": self.manifest.capabilities,
                }
            )

        except Exception as e:
            # Graceful degradation
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Bundle detector error: {e}", exc_info=True)

            return L2Result(
                predictions=[],
                confidence=0.0,
                processing_time_ms=processing_time_ms,
                model_version=f"bundle-{self.manifest.bundle_version}-error",
                metadata={
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )

    def _predict(self, embedding, text: str) -> dict[str, Any]:
        """
        Run prediction using bundle classifier.

        This replicates the inference logic from raxe-ml's AdversarialDetector.

        Args:
            embedding: Text embedding vector
            text: Original text (for trigger matching)

        Returns:
            Prediction dict with complete output schema
        """
        import numpy as np

        embedding = np.array(embedding).reshape(1, -1)

        # Get binary prediction
        binary_proba = self.classifier['binary_clf'].predict_proba(embedding)[0]
        is_attack = int(binary_proba[1] > 0.5)
        attack_probability = float(binary_proba[1])

        # Get family and subfamily predictions
        if is_attack:
            family_proba = self.classifier['family_clf'].predict_proba(embedding)[0]
            family_idx = int(np.argmax(family_proba))
            family = self.classifier['family_encoder'].inverse_transform([family_idx])[0]
            family_confidence = float(family_proba[family_idx])

            subfamily_proba = self.classifier['subfamily_clf'].predict_proba(embedding)[0]
            subfamily_idx = int(np.argmax(subfamily_proba))
            sub_family = self.classifier['subfamily_encoder'].inverse_transform([subfamily_idx])[0]
            subfamily_confidence = float(subfamily_proba[subfamily_idx])
        else:
            family = "BENIGN"
            sub_family = "benign"
            family_confidence = 1.0 - attack_probability
            subfamily_confidence = 1.0 - attack_probability

        # Check for trigger matches
        trigger_matches = self._check_triggers(text)

        # Determine recommended action
        if attack_probability >= self.BLOCK_THRESHOLD:
            recommended_action = ["High confidence attack - BLOCK immediately"]
        elif attack_probability >= self.WARN_THRESHOLD:
            recommended_action = ["Medium confidence - WARN and log"]
        else:
            recommended_action = ["Low confidence - ALLOW with monitoring"]

        # Generate why_it_hit explanations
        why_it_hit = []
        if is_attack:
            if trigger_matches:
                why_it_hit.append(f"Detected {len(trigger_matches)} trigger pattern(s): {', '.join(trigger_matches[:3])}")
            if family_confidence > 0.7:
                why_it_hit.append(f"High confidence {family} attack pattern")
            if subfamily_confidence > 0.6:
                why_it_hit.append(f"Matches {sub_family} subfamily pattern")
            if not why_it_hit:
                why_it_hit.append("ML model detected anomalous pattern")

        # Find similar attacks (from clusters)
        similar_attacks = self._find_similar_attacks(embedding, family, subfamily_idx)

        # Determine if uncertain
        uncertain = (
            is_attack and
            (family_confidence < 0.6 or subfamily_confidence < 0.5)
        )

        return {
            "is_attack": is_attack,
            "family": family,
            "sub_family": sub_family,
            "scores": {
                "attack_probability": attack_probability,
                "family_confidence": family_confidence,
                "subfamily_confidence": subfamily_confidence,
            },
            "why_it_hit": why_it_hit,
            "recommended_action": recommended_action,
            "trigger_matches": trigger_matches,
            "similar_attacks": similar_attacks[:3],  # Top 3
            "uncertain": uncertain,
        }

    def _check_triggers(self, text: str) -> list[str]:
        """Check for trigger pattern matches."""
        import re

        matches = []
        text_lower = text.lower()

        for pattern_name, pattern_data in self.triggers.items():
            # Simple pattern matching (could be regex)
            if isinstance(pattern_data, dict) and 'pattern' in pattern_data:
                pattern = pattern_data['pattern']
                if pattern.lower() in text_lower:
                    matches.append(pattern_name)
            elif isinstance(pattern_data, str):
                if pattern_data.lower() in text_lower:
                    matches.append(pattern_name)

        return matches

    def _find_similar_attacks(self, embedding, family: str, subfamily_idx: int) -> list[dict]:
        """Find similar attacks from training clusters."""
        # This would use the cluster data from the bundle
        # For now, return empty list (can be enhanced later)
        return []

    def _generate_explanation(self, prediction: dict) -> str:
        """Generate human-readable explanation."""
        family = prediction['family']
        sub_family = prediction['sub_family']
        confidence = prediction['scores']['attack_probability']

        if confidence >= 0.8:
            level = "High"
        elif confidence >= 0.6:
            level = "Medium"
        else:
            level = "Low"

        return f"{level} confidence {family} attack ({sub_family})"

    @property
    def model_info(self) -> dict[str, Any]:
        """Get model metadata."""
        return {
            "name": f"RAXE Bundle-Based Detector ({self.manifest.model_id[:8]})",
            "version": self.manifest.bundle_version,
            "model_id": self.manifest.model_id,
            "type": "ml-bundle",
            "is_stub": False,
            "created_at": self.manifest.created_at,
            "author": self.manifest.metadata.get('author', 'unknown'),
            "description": self.manifest.metadata.get('description', 'Bundle-based ML detector'),
            "latency_p95_ms": 150.0,  # Estimated
            "embedding_model": self.embedding_config['model_name'],
            "embedding_dim": self.embedding_config['embedding_dim'],
            "capabilities": self.manifest.capabilities,
            "families": self.manifest.capabilities.get('families', []),
            "num_subfamilies": self.manifest.capabilities.get('num_subfamilies', 'unknown'),
            "training_metrics": self.components.training_stats,
        }


def create_bundle_detector(
    bundle_path: str | Path,
    confidence_threshold: float = 0.5,
    onnx_path: str | Path | None = None,
) -> L2Detector:
    """
    Factory function to create bundle-based detector.

    Args:
        bundle_path: Path to .raxe bundle file
        confidence_threshold: Minimum confidence to report predictions
        onnx_path: Optional path to ONNX embeddings model for 5x speedup

    Returns:
        L2Detector implementation (BundleBasedDetector)

    Example:
        detector = create_bundle_detector('models/production_v1.raxe')
        result = detector.analyze(text, l1_results)

        # With ONNX embeddings for 5x speedup
        detector = create_bundle_detector(
            'models/production_v1.raxe',
            onnx_path='models/embeddings.onnx'
        )
    """
    return BundleBasedDetector(
        bundle_path=bundle_path,
        confidence_threshold=confidence_threshold,
        onnx_model_path=onnx_path,
    )
