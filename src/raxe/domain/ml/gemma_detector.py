"""Gemma-based 5-head multilabel L2 detector.

This detector uses the EmbeddingGemma-300M model with 5 classifier heads:
1. is_threat (binary): benign vs threat
2. threat_family (multiclass, 9): Attack category
3. severity (multiclass, 5): Threat severity level
4. primary_technique (multiclass, 22): Specific attack technique
5. harm_types (multilabel, 10): Types of potential harm

Model files expected in model directory:
- model_int8.onnx: EmbeddingGemma-300M (INT8 quantized)
- classifier_is_threat_int8.onnx
- classifier_threat_family_int8.onnx
- classifier_severity_int8.onnx
- classifier_primary_technique_int8.onnx
- classifier_harm_types_int8.onnx
- tokenizer.json, config.json, label_config.json, model_metadata.json

NEW: Voting Engine Integration
The ensemble decision logic now uses VotingEngine for transparent weighted voting
instead of boost-based heuristics. Set L2Config.voting.enabled=False to use legacy logic.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from raxe.domain.engine.executor import ScanResult as L1ScanResult
from raxe.domain.ml.gemma_models import (
    DEFAULT_HARM_THRESHOLDS,
    GemmaClassificationResult,
    HarmType,
    MultilabelResult,
    PrimaryTechnique,
    Severity,
    ThreatFamily,
)
from raxe.domain.ml.l2_config import L2Config, get_l2_config
from raxe.domain.ml.protocol import L2Prediction, L2Result, L2ThreatType
from raxe.domain.ml.voting import (
    Decision,
    HeadOutputs,
    VotingEngine,
    VotingResult,
)
from raxe.utils.logging import get_logger

logger = get_logger(__name__)


class GemmaL2Detector:
    """Gemma-based 5-head L2 detector.

    Implements L2Detector protocol with the new Gemma multilabel architecture.

    Performance targets:
    - P95 latency: <50ms (with cache miss)
    - P50 latency: <10ms (with cache hit)
    - Memory: <400MB

    Example:
        detector = GemmaL2Detector(model_dir="/path/to/models")
        result = detector.analyze(text, l1_results)
    """

    VERSION = "gemma-compact-v1"
    EMBEDDING_DIM = 256  # Matryoshka truncation from 768

    def __init__(
        self,
        model_dir: str | Path,
        *,
        confidence_threshold: float | None = None,
        harm_thresholds: dict[str, float] | None = None,
        cache_size: int = 1000,
        scorer: Any | None = None,
        l2_config: L2Config | None = None,
        voting_preset: str | None = None,
    ):
        """Initialize Gemma L2 detector.

        Args:
            model_dir: Path to directory containing ONNX models
            confidence_threshold: Override threshold for binary threat classification
                                  (uses L2Config if not provided)
            harm_thresholds: Per-class thresholds for harm_types multilabel
            cache_size: Size of embedding cache (0 to disable)
            scorer: Optional HierarchicalThreatScorer instance
            l2_config: L2 configuration (uses global config if not provided)
            voting_preset: Voting preset override (balanced, high_security, low_fp)
        """
        self.model_dir = Path(model_dir)
        self._l2_config = l2_config or get_l2_config()
        # Use provided threshold, or config threshold
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else self._l2_config.thresholds.threat_threshold
        )
        # Use provided harm thresholds, or config thresholds
        self.harm_thresholds = (
            harm_thresholds
            if harm_thresholds is not None
            else self._l2_config.thresholds.harm_type_thresholds.copy()
        )
        self.scorer = scorer

        # Initialize voting engine if enabled
        self._voting_enabled = self._l2_config.voting.enabled
        if self._voting_enabled:
            # Use override preset if provided, otherwise use config preset
            preset = voting_preset or self._l2_config.voting.preset
            self._voting_engine = VotingEngine(preset=preset)
            logger.info(
                "VotingEngine initialized",
                preset=preset,
                enabled=True,
            )
        else:
            self._voting_engine = None
            logger.info("VotingEngine disabled, using legacy ensemble logic")

        # Lazy imports for ONNX runtime
        import onnxruntime as ort
        from transformers import PreTrainedTokenizerFast

        self._ort = ort

        # Load tokenizer from tokenizer.json (portable format)
        logger.info("Loading Gemma tokenizer", model_dir=str(self.model_dir))
        tokenizer_path = self.model_dir / "tokenizer.json"
        if not tokenizer_path.exists():
            raise FileNotFoundError(f"tokenizer.json not found in {self.model_dir}")
        self._tokenizer = PreTrainedTokenizerFast(tokenizer_file=str(tokenizer_path))

        # Configure special tokens from config.json
        config_path = self.model_dir / "config.json"
        if config_path.exists():
            import json
            with open(config_path) as f:
                config = json.load(f)
            # Set pad_token_id (Gemma uses id 0 for padding)
            if "pad_token_id" in config:
                self._tokenizer.pad_token_id = config["pad_token_id"]
                # Set pad_token if not already set
                if self._tokenizer.pad_token is None:
                    self._tokenizer.pad_token = self._tokenizer.decode([config["pad_token_id"]])
            if "eos_token_id" in config:
                self._tokenizer.eos_token_id = config["eos_token_id"]
            if "bos_token_id" in config:
                self._tokenizer.bos_token_id = config["bos_token_id"]

        # Create session options
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.log_severity_level = 3  # ERROR only
        sess_options.intra_op_num_threads = 4
        sess_options.inter_op_num_threads = 1
        sess_options.enable_mem_pattern = True
        sess_options.enable_cpu_mem_arena = True

        providers = ["CPUExecutionProvider"]

        # Load embedding model
        embedding_path = self._find_model_file("model", ".onnx")
        logger.info("Loading embedding model", path=str(embedding_path))
        self._embedding_session = ort.InferenceSession(
            str(embedding_path), sess_options, providers=providers
        )

        # Load classifier heads
        self._classifiers: dict[str, ort.InferenceSession] = {}
        for head in ["is_threat", "threat_family", "severity", "primary_technique", "harm_types"]:
            classifier_path = self._find_model_file(f"classifier_{head}", ".onnx")
            logger.info(f"Loading classifier: {head}", path=str(classifier_path))
            self._classifiers[head] = ort.InferenceSession(
                str(classifier_path), sess_options, providers=providers
            )

        # Load label config
        label_config_path = self.model_dir / "label_config.json"
        if label_config_path.exists():
            with open(label_config_path) as f:
                self._label_config = json.load(f)
        else:
            self._label_config = {}

        # Load model metadata
        metadata_path = self.model_dir / "model_metadata.json"
        if metadata_path.exists():
            with open(metadata_path) as f:
                self._model_metadata = json.load(f)
        else:
            self._model_metadata = {}

        # Setup embedding cache
        self._cache_enabled = cache_size > 0
        if self._cache_enabled:
            from raxe.domain.ml.embedding_cache import EmbeddingCache
            self._embedding_cache = EmbeddingCache(max_size=cache_size)
        else:
            self._embedding_cache = None

        logger.info(
            "GemmaL2Detector initialized",
            model_dir=str(self.model_dir),
            embedding_dim=self.EMBEDDING_DIM,
            cache_size=cache_size,
            confidence_threshold=confidence_threshold,
        )

    def _find_model_file(self, prefix: str, suffix: str) -> Path:
        """Find model file with INT8 preference."""
        # Prefer INT8 quantized version
        int8_path = self.model_dir / f"{prefix}_int8{suffix}"
        if int8_path.exists():
            return int8_path

        # Fall back to non-quantized
        regular_path = self.model_dir / f"{prefix}{suffix}"
        if regular_path.exists():
            return regular_path

        # Try glob pattern
        matches = list(self.model_dir.glob(f"{prefix}*{suffix}"))
        if matches:
            # Prefer INT8 if available
            for match in matches:
                if "int8" in match.name:
                    return match
            return matches[0]

        raise FileNotFoundError(
            f"No model file found for {prefix}*{suffix} in {self.model_dir}"
        )

    def analyze(
        self,
        text: str,
        l1_results: L1ScanResult,
        context: dict[str, Any] | None = None,
    ) -> L2Result:
        """Analyze text for threats using Gemma 5-head classifier.

        Args:
            text: Text to analyze
            l1_results: Results from L1 rule-based detection
            context: Optional context metadata

        Returns:
            L2Result with predictions from all 5 heads and voting metadata
        """
        start_time = time.perf_counter()

        try:
            # Generate embeddings (with caching)
            embeddings = self._generate_embeddings(text)

            # Run classification (returns both classification and voting result)
            classification, voting_result = self._classify(embeddings)

            # Build predictions
            predictions = self._build_predictions(classification, text, voting_result)

            # Apply scorer if available
            hierarchical_score = None
            classification_label = None
            recommended_action = None
            decision_rationale = None
            signal_quality = None

            if self.scorer and classification.is_threat:
                scoring_result = self._apply_scorer(classification, text)
                if scoring_result:
                    hierarchical_score = scoring_result.hierarchical_score
                    classification_label = scoring_result.classification.value
                    recommended_action = scoring_result.action.value
                    decision_rationale = scoring_result.reason
                    signal_quality = {
                        "is_consistent": scoring_result.is_consistent,
                        "variance": scoring_result.variance,
                        "weak_margins_count": scoring_result.weak_margins_count,
                    }

            # Build classification and action from voting result if available
            if voting_result:
                classification_label = self._voting_decision_to_classification(
                    voting_result.decision, voting_result.confidence
                )
                recommended_action = self._voting_decision_to_action(voting_result.decision)
                decision_rationale = f"Voting rule: {voting_result.decision_rule_triggered}"

            duration_ms = (time.perf_counter() - start_time) * 1000

            # Build voting metadata for telemetry
            voting_metadata = voting_result.to_dict() if voting_result else None

            return L2Result(
                predictions=predictions,
                confidence=classification.threat_probability,
                processing_time_ms=duration_ms,
                model_version=self.VERSION,
                features_extracted={
                    "text_length": len(text),
                    "l1_detection_count": l1_results.detection_count,
                    "embedding_dim": self.EMBEDDING_DIM,
                },
                metadata={
                    "detector_type": "gemma",
                    "classification_result": classification.to_dict(),
                    "voting_enabled": self._voting_enabled,
                },
                hierarchical_score=hierarchical_score,
                classification=classification_label,
                recommended_action=recommended_action,
                decision_rationale=decision_rationale,
                signal_quality=signal_quality,
                voting=voting_metadata,
            )

        except Exception as e:
            logger.error("Gemma detection failed", error=str(e), exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            return L2Result(
                predictions=[],
                confidence=0.0,
                processing_time_ms=duration_ms,
                model_version=self.VERSION,
                metadata={"error": str(e), "detector_type": "gemma"},
            )

    def _voting_decision_to_classification(
        self, decision: Decision, confidence: float
    ) -> str:
        """Map voting decision to classification label."""
        if decision == Decision.THREAT:
            if confidence >= 0.9:
                return "HIGH_THREAT"
            elif confidence >= 0.75:
                return "THREAT"
            else:
                return "LIKELY_THREAT"
        elif decision == Decision.REVIEW:
            return "REVIEW"
        else:
            return "SAFE"

    def _voting_decision_to_action(self, decision: Decision) -> str:
        """Map voting decision to recommended action."""
        if decision == Decision.THREAT:
            return "BLOCK"
        elif decision == Decision.REVIEW:
            return "MANUAL_REVIEW"
        else:
            return "ALLOW"

    def _generate_embeddings(self, text: str) -> np.ndarray:
        """Generate embeddings with optional caching.

        The EmbeddingGemma model outputs two tensors:
        - outputs[0]: token embeddings (batch, seq_len, hidden_dim)
        - outputs[1]: pooled embedding (batch, hidden_dim) - used directly
        """
        # Check cache
        if self._cache_enabled and self._embedding_cache:
            cached = self._embedding_cache.get(text)
            if cached is not None:
                return cached

        # Tokenize
        inputs = self._tokenizer(
            text,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="np",
        )

        # Get embeddings from model
        outputs = self._embedding_session.run(
            None,
            {
                "input_ids": inputs["input_ids"].astype(np.int64),
                "attention_mask": inputs["attention_mask"].astype(np.int64),
            },
        )

        # outputs[1] is the model's pooled embedding (batch_size, hidden_dim)
        # The model already does internal pooling, so use it directly
        embeddings = outputs[1]

        # Truncate to 256 dims (Matryoshka)
        embeddings = embeddings[:, :self.EMBEDDING_DIM]

        # L2 normalize
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / (norms + 1e-9)

        # Cache result
        if self._cache_enabled and self._embedding_cache:
            self._embedding_cache.put(text, embeddings)

        return embeddings

    def _classify(
        self, embeddings: np.ndarray
    ) -> tuple[GemmaClassificationResult, VotingResult | None]:
        """Run all 5 classifier heads with ensemble logic.

        Each classifier returns 2 outputs:
        - [0]: predicted class (int64)
        - [1]: probabilities (float32)

        Returns:
            Tuple of (GemmaClassificationResult, VotingResult or None)
            VotingResult is None if voting engine is disabled.
        """
        embeddings_f32 = embeddings.astype(np.float32)

        # ════════════════════════════════════════════════════════════════════
        # Run all 5 classifier heads (always run all for voting engine)
        # ════════════════════════════════════════════════════════════════════

        # 1. Binary threat classification
        is_threat_outputs = self._classifiers["is_threat"].run(
            None, {"embeddings": embeddings_f32}
        )
        is_threat_proba = is_threat_outputs[1][0]  # [benign_prob, threat_prob]
        safe_prob = float(is_threat_proba[0])
        threat_prob = float(is_threat_proba[1])

        # 2. Threat family
        family_outputs = self._classifiers["threat_family"].run(
            None, {"embeddings": embeddings_f32}
        )
        family_proba = family_outputs[1][0]
        family_idx = int(np.argmax(family_proba))
        family_confidence = float(family_proba[family_idx])
        threat_family = ThreatFamily.from_index(family_idx)

        # 3. Severity
        severity_outputs = self._classifiers["severity"].run(
            None, {"embeddings": embeddings_f32}
        )
        severity_proba = severity_outputs[1][0]
        severity_idx = int(np.argmax(severity_proba))
        severity_confidence = float(severity_proba[severity_idx])
        severity = Severity.from_index(severity_idx)

        # 4. Primary technique (always run for voting engine)
        technique_outputs = self._classifiers["primary_technique"].run(
            None, {"embeddings": embeddings_f32}
        )
        technique_proba_arr = technique_outputs[1][0]
        technique_idx = int(np.argmax(technique_proba_arr))
        technique_confidence = float(technique_proba_arr[technique_idx])
        primary_technique = PrimaryTechnique.from_index(technique_idx)
        technique_proba = tuple(float(p) for p in technique_proba_arr)

        # 5. Harm types (always run for voting engine)
        harm_outputs = self._classifiers["harm_types"].run(
            None, {"embeddings": embeddings_f32}
        )
        harm_proba = harm_outputs[1][0]
        harm_types_result = self._process_multilabel_harm_types(harm_proba)
        harm_max_prob = max(float(p) for p in harm_proba)
        harm_active_labels = [h.value for h in harm_types_result.active_labels]

        # ════════════════════════════════════════════════════════════════════
        # DECISION LOGIC: Voting Engine or Legacy Ensemble
        # ════════════════════════════════════════════════════════════════════

        voting_result: VotingResult | None = None

        if self._voting_enabled and self._voting_engine:
            # Use new VotingEngine for transparent weighted voting
            head_outputs = HeadOutputs(
                binary_threat_prob=threat_prob,
                binary_safe_prob=safe_prob,
                family_prediction=threat_family.value,
                family_confidence=family_confidence,
                severity_prediction=severity.value,
                severity_confidence=severity_confidence,
                technique_prediction=primary_technique.value if primary_technique else None,
                technique_confidence=technique_confidence,
                harm_max_probability=harm_max_prob,
                harm_active_labels=harm_active_labels,
            )

            voting_result = self._voting_engine.vote(head_outputs)

            # Map voting decision to is_threat and effective probability
            is_threat = voting_result.decision in (Decision.THREAT, Decision.REVIEW)
            final_threat_prob = voting_result.confidence
            family_override_triggered = False  # Not used with voting engine
        else:
            # Legacy boost-based ensemble logic
            is_threat, final_threat_prob, family_override_triggered = (
                self._legacy_ensemble_logic(
                    threat_prob=threat_prob,
                    threat_family=threat_family,
                    family_confidence=family_confidence,
                    severity=severity,
                    primary_technique=primary_technique,
                    technique_confidence=technique_confidence,
                )
            )

        # Determine harm_types for result (only include if threat)
        harm_types = harm_types_result if is_threat else None

        result = GemmaClassificationResult(
            is_threat=is_threat,
            threat_probability=final_threat_prob,
            safe_probability=1.0 - final_threat_prob,
            threat_family=threat_family,
            family_confidence=family_confidence,
            family_probabilities=tuple(float(p) for p in family_proba),
            severity=severity,
            severity_confidence=severity_confidence,
            severity_probabilities=tuple(float(p) for p in severity_proba),
            primary_technique=primary_technique,
            technique_confidence=technique_confidence,
            technique_probabilities=technique_proba,
            harm_types=harm_types,
            raw_threat_probability=threat_prob,
            family_override_triggered=family_override_triggered,
        )

        return result, voting_result

    def _legacy_ensemble_logic(
        self,
        threat_prob: float,
        threat_family: ThreatFamily,
        family_confidence: float,
        severity: Severity,
        primary_technique: PrimaryTechnique | None,
        technique_confidence: float,
    ) -> tuple[bool, float, bool]:
        """Legacy boost-based ensemble logic (used when voting is disabled).

        Returns:
            Tuple of (is_threat, effective_threat_prob, family_override_triggered)
        """
        cfg = self._l2_config
        ensemble = cfg.ensemble

        # Start with binary head decision
        effective_threat_prob = threat_prob
        is_threat = threat_prob >= self.confidence_threshold

        # Check for family override
        family_override_triggered = False
        if ensemble.use_family_override:
            family_is_benign = threat_family == ThreatFamily.BENIGN
            family_override_threshold = cfg.thresholds.family_override_threshold

            if not family_is_benign and family_confidence >= family_override_threshold:
                family_override_triggered = True
                is_threat = True
                if effective_threat_prob < self.confidence_threshold:
                    effective_threat_prob = max(
                        effective_threat_prob,
                        self.confidence_threshold + 0.05
                    )

        # Check for always-threat families
        if threat_family.value in ensemble.always_threat_families:
            is_threat = True
            effective_threat_prob = max(effective_threat_prob, 0.75)

        # Apply severity boost
        if ensemble.use_severity_boost:
            if severity in (Severity.HIGH, Severity.CRITICAL):
                effective_threat_prob = min(
                    1.0, effective_threat_prob + ensemble.severity_boost_amount
                )
                if severity == Severity.CRITICAL and not is_threat:
                    is_threat = True

        # Apply technique boost
        if ensemble.use_technique_boost and primary_technique:
            if (
                technique_confidence >= ensemble.technique_boost_threshold
                and primary_technique.value in ensemble.high_confidence_techniques
            ):
                effective_threat_prob = min(
                    1.0, effective_threat_prob + ensemble.technique_boost_amount
                )
                if not is_threat:
                    is_threat = True

        return is_threat, effective_threat_prob, family_override_triggered

    def _process_multilabel_harm_types(
        self, probabilities: np.ndarray
    ) -> MultilabelResult:
        """Process multilabel harm types with per-class thresholds."""
        harm_classes = HarmType.all_classes()
        active_labels = []
        proba_dict: dict[str, float] = {}
        thresholds_dict: dict[str, float] = {}

        for i, harm_type in enumerate(harm_classes):
            prob = float(probabilities[i])
            threshold = self.harm_thresholds.get(harm_type.value, 0.5)
            proba_dict[harm_type.value] = prob
            thresholds_dict[harm_type.value] = threshold

            if prob >= threshold:
                active_labels.append(harm_type)

        return MultilabelResult(
            active_labels=tuple(active_labels),
            probabilities=proba_dict,
            thresholds_used=thresholds_dict,
        )

    def _build_predictions(
        self,
        classification: GemmaClassificationResult,
        text: str,
        voting_result: VotingResult | None = None,
    ) -> list[L2Prediction]:
        """Build L2Predictions from classification result."""
        if not classification.is_threat:
            return []

        # Map family to L2ThreatType
        threat_type = L2ThreatType.from_family(classification.threat_family.value)

        # Build explanation
        explanation_parts = [
            f"Detected {classification.threat_family.value} threat",
            f"with {classification.severity.value} severity",
        ]
        if classification.primary_technique:
            explanation_parts.append(
                f"using {classification.primary_technique.value} technique"
            )
        if classification.harm_types and classification.harm_types.has_active_labels:
            harm_labels = [h.value for h in classification.harm_types.active_labels]
            explanation_parts.append(f"causing potential harm: {', '.join(harm_labels)}")

        explanation = " ".join(explanation_parts)

        # Build metadata
        # Calculate classification label based on confidence
        if classification.threat_probability >= 0.9:
            classification_label = "HIGH_THREAT"
            action = "BLOCK_ALERT"
        elif classification.threat_probability >= 0.75:
            classification_label = "THREAT"
            action = "BLOCK"
        elif classification.threat_probability >= 0.6:
            classification_label = "LIKELY_THREAT"
            action = "BLOCK_WITH_REVIEW"
        elif classification.threat_probability >= 0.4:
            classification_label = "REVIEW"
            action = "MANUAL_REVIEW"
        else:
            classification_label = "FP_LIKELY"
            action = "ALLOW_WITH_LOG"

        metadata: dict[str, Any] = {
            "is_attack": True,
            "family": classification.threat_family.value,
            "severity": classification.severity.value,
            "classification": classification_label,
            "action": action,
            "risk_score": classification.threat_probability * 100,
            "hierarchical_score": classification.threat_probability,
            "scores": {
                "attack_probability": classification.threat_probability,
                "family_confidence": classification.family_confidence,
                "severity_confidence": classification.severity_confidence,
                "subfamily_confidence": classification.technique_confidence,
            },
        }

        if classification.primary_technique:
            metadata["primary_technique"] = classification.primary_technique.value
            metadata["technique_confidence"] = classification.technique_confidence
            # Alias for CLI formatter compatibility
            metadata["sub_family"] = classification.primary_technique.value

        if classification.harm_types:
            metadata["harm_types"] = classification.harm_types.to_dict()

        # Generate "why_it_hit" explanations
        why_it_hit = self._generate_why_it_hit(classification)
        metadata["why_it_hit"] = why_it_hit

        # Generate recommended actions
        recommended_actions = self._generate_recommended_actions(classification)
        metadata["recommended_action"] = recommended_actions

        # Uncertainty flag
        metadata["uncertain"] = (
            classification.family_confidence < 0.5 or
            classification.threat_probability < 0.6
        )

        # Add voting information if available
        if voting_result:
            metadata["voting"] = {
                "decision": voting_result.decision.value,
                "confidence": voting_result.confidence,
                "preset_used": voting_result.preset_used,
                "decision_rule_triggered": voting_result.decision_rule_triggered,
                "threat_vote_count": voting_result.threat_vote_count,
                "safe_vote_count": voting_result.safe_vote_count,
                "abstain_vote_count": voting_result.abstain_vote_count,
                "weighted_ratio": voting_result.weighted_ratio,
            }
            # Update classification and action from voting
            metadata["classification"] = self._voting_decision_to_classification(
                voting_result.decision, voting_result.confidence
            )
            metadata["action"] = self._voting_decision_to_action(voting_result.decision)

        return [
            L2Prediction(
                threat_type=threat_type,
                confidence=classification.threat_probability,
                explanation=explanation,
                features_used=[
                    f"family={classification.threat_family.value}",
                    f"severity={classification.severity.value}",
                    f"technique={classification.primary_technique.value if classification.primary_technique else 'none'}",  # noqa: E501
                    "model=gemma-compact",
                ],
                metadata=metadata,
            )
        ]

    def _generate_why_it_hit(
        self, classification: GemmaClassificationResult
    ) -> list[str]:
        """Generate human-readable explanations for detection."""
        reasons = []

        # Threat family reason
        family_descriptions = {
            "prompt_injection": "Prompt injection attempting to override instructions",
            "jailbreak": "Jailbreak attempt to bypass safety guidelines",
            "data_exfiltration": "Data exfiltration pattern detected",
            "encoding_or_obfuscation_attack": "Encoded or obfuscated malicious content",
            "rag_or_context_attack": "RAG or context manipulation attack",
            "tool_or_command_abuse": "Tool or command abuse attempt",
            "toxic_or_policy_violating_content": "Toxic or policy-violating content",
            "other_security": "Security-related threat pattern detected",
        }
        family_desc = family_descriptions.get(
            classification.threat_family.value,
            f"{classification.threat_family.value} threat detected"
        )
        reasons.append(family_desc)

        # Severity reason
        if classification.severity in (Severity.HIGH, Severity.CRITICAL):
            reasons.append(
                f"{classification.severity.value.upper()} severity - immediate action recommended"
            )

        # Technique reason
        has_technique = (
            classification.primary_technique
            and classification.primary_technique != PrimaryTechnique.NONE
        )
        if has_technique:
            technique_desc = classification.primary_technique.value.replace("_", " ")
            reasons.append(f"Specific attack technique: {technique_desc}")

        # Harm types reason
        if classification.harm_types and classification.harm_types.has_active_labels:
            harm_count = classification.harm_types.active_count
            if harm_count == 1:
                harm_label = classification.harm_types.active_labels[0].value.replace("_", " ")
                reasons.append(f"Potential harm type: {harm_label}")
            else:
                reasons.append(f"Multiple harm types detected ({harm_count} categories)")

        return reasons

    def _generate_recommended_actions(
        self, classification: GemmaClassificationResult
    ) -> list[str]:
        """Generate recommended actions based on classification."""
        actions = []

        if classification.severity == Severity.CRITICAL:
            actions.append("CRITICAL threat - BLOCK immediately and alert security team")
        elif classification.severity == Severity.HIGH:
            actions.append("HIGH severity - BLOCK and log for review")
        elif classification.severity == Severity.MEDIUM:
            actions.append("MEDIUM severity - Consider blocking or require additional validation")
        elif classification.severity == Severity.LOW:
            actions.append("LOW severity - Log and monitor, allow with caution")
        else:
            actions.append("Minimal severity - Allow with logging")

        # Family-specific recommendations
        if classification.threat_family == ThreatFamily.DATA_EXFILTRATION:
            actions.append("Review data access controls and implement DLP policies")
        elif classification.threat_family == ThreatFamily.JAILBREAK:
            actions.append("Block and update guardrails to prevent similar attempts")
        elif classification.threat_family == ThreatFamily.PROMPT_INJECTION:
            actions.append("Sanitize input and validate instruction boundaries")

        return actions

    def _apply_scorer(
        self, classification: GemmaClassificationResult, text: str
    ) -> Any:
        """Apply hierarchical threat scorer if available."""
        if not self.scorer:
            return None

        try:
            from raxe.domain.ml.scoring_models import ThreatScore

            # Map to ThreatScore format
            threat_score = ThreatScore(
                binary_threat_score=classification.threat_probability,
                binary_safe_score=classification.safe_probability,
                family_confidence=classification.family_confidence,
                subfamily_confidence=classification.technique_confidence,
                binary_proba=[
                    classification.safe_probability,
                    classification.threat_probability,
                ],
                family_proba=list(classification.family_probabilities),
                subfamily_proba=list(classification.technique_probabilities or [0.0]),
                family_name=classification.threat_family.value,
                subfamily_name=(
                    classification.primary_technique.value
                    if classification.primary_technique
                    else None
                ),
            )

            return self.scorer.score(threat_score, prompt=text)
        except Exception as e:
            logger.warning("Scorer failed", error=str(e))
            return None

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        """Apply softmax to logits."""
        exp_x = np.exp(x - np.max(x))
        return exp_x / exp_x.sum()

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        """Apply sigmoid to logits."""
        return 1 / (1 + np.exp(-x))

    @property
    def model_info(self) -> dict[str, Any]:
        """Return model information."""
        return {
            "name": "Gemma 5-Head Multilabel Classifier",
            "version": self.VERSION,
            "type": "onnx",
            "is_stub": False,
            "size_mb": 300,  # Approximate
            "latency_p95_ms": 50,
            "embedding_model": "google/embeddinggemma-300m",
            "embedding_dim": self.EMBEDDING_DIM,
            "heads": [
                "is_threat",
                "threat_family",
                "severity",
                "primary_technique",
                "harm_types",
            ],
            "families": [f.value for f in ThreatFamily],
            "description": (
                "Gemma-based 5-head multilabel classifier with EmbeddingGemma-300M "
                "for threat detection, family classification, severity assessment, "
                "technique identification, and harm type prediction."
            ),
        }


def create_gemma_detector(
    model_dir: str | Path,
    *,
    confidence_threshold: float = 0.5,
    harm_thresholds: dict[str, float] | None = None,
    cache_size: int = 1000,
    scorer: Any | None = None,
    voting_preset: str | None = None,
) -> GemmaL2Detector:
    """Factory function to create Gemma L2 detector.

    Args:
        model_dir: Path to directory containing ONNX models
        confidence_threshold: Threshold for binary threat classification
        harm_thresholds: Per-class thresholds for harm_types multilabel
        cache_size: Size of embedding cache (0 to disable)
        scorer: Optional HierarchicalThreatScorer instance
        voting_preset: Voting preset override (balanced, high_security, low_fp)

    Returns:
        GemmaL2Detector instance
    """
    return GemmaL2Detector(
        model_dir=model_dir,
        confidence_threshold=confidence_threshold,
        harm_thresholds=harm_thresholds,
        cache_size=cache_size,
        scorer=scorer,
        voting_preset=voting_preset,
    )
