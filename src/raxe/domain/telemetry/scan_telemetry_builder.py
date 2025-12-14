"""Scan Telemetry Builder - Canonical implementation for schema v2.1.

This builder creates telemetry payloads that comply with SCAN_TELEMETRY_SCHEMA.md.
All fields are dynamically calculated from L1/L2 results - NO hardcoded values.

Usage:
    builder = ScanTelemetryBuilder()
    telemetry = builder.build(
        prompt=prompt,
        l1_result=l1_result,
        l2_result=l2_result,
        scan_duration_ms=duration_ms,
        entry_point="sdk",
    )

See: docs/SCAN_TELEMETRY_SCHEMA.md for field definitions.

NEW in v2.1: Voting engine telemetry support
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from raxe.domain.detections import L1Result
    from raxe.domain.ml.protocol import L2Result

# Schema version - bump when schema changes
SCHEMA_VERSION = "2.1.0"

# Enum labels for probability distributions
FAMILY_LABELS = [
    "benign",
    "data_exfiltration",
    "encoding_or_obfuscation_attack",
    "jailbreak",
    "other_security",
    "prompt_injection",
    "rag_or_context_attack",
    "tool_or_command_abuse",
    "toxic_or_policy_violating_content",
]

SEVERITY_LABELS = ["none", "low", "medium", "high", "critical"]

TECHNIQUE_LABELS = [
    "chain_of_thought_or_internal_state_leak",
    "context_or_delimiter_injection",
    "data_exfil_system_prompt_or_config",
    "data_exfil_user_content",
    "encoding_or_obfuscation",
    "eval_or_guardrail_evasion",
    "hidden_or_steganographic_prompt",
    "indirect_injection_via_content",
    "instruction_override",
    "mode_switch_or_privilege_escalation",
    "multi_turn_or_crescendo",
    "none",
    "other_attack_technique",
    "payload_splitting_or_staging",
    "policy_override_or_rewriting",
    "rag_poisoning_or_context_bias",
    "role_or_persona_manipulation",
    "safety_bypass_harmful_output",
    "social_engineering_content",
    "system_prompt_or_config_extraction",
    "tool_abuse_or_unintended_action",
    "tool_or_command_injection",
]

HARM_TYPE_LABELS = [
    "cbrn_or_weapons",
    "crime_or_fraud",
    "cybersecurity_or_malware",
    "hate_or_harassment",
    "misinformation_or_disinfo",
    "other_harm",
    "privacy_or_pii",
    "self_harm_or_suicide",
    "sexual_content",
    "violence_or_physical_harm",
]

# Severity ordering for comparison
SEVERITY_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass
class ScanTelemetryBuilder:
    """Builder for scan telemetry payloads following schema v2.0.

    All fields are dynamically calculated from input data.
    NO hardcoded values - everything derived from actual scan results.
    """

    max_l1_detections: int = 10  # Limit per-rule details

    def build(
        self,
        l1_result: L1Result | None,
        l2_result: L2Result | None,
        scan_duration_ms: float,
        entry_point: Literal["cli", "sdk", "wrapper", "integration"] = "sdk",
        *,
        prompt: str | None = None,
        prompt_hash: str | None = None,
        prompt_length: int | None = None,
        wrapper_type: Literal["openai", "anthropic", "langchain", "none"] | None = None,
        action_taken: Literal["allow", "block", "warn", "redact"] = "allow",
        l2_enabled: bool = True,
    ) -> dict[str, Any]:
        """Build complete scan telemetry payload.

        Provide either `prompt` OR both `prompt_hash` and `prompt_length`.

        Args:
            l1_result: L1 rule-based detection result
            l2_result: L2 ML detection result
            scan_duration_ms: Total scan duration in milliseconds
            entry_point: How scan was triggered
            prompt: Original prompt text (preferred - calculates hash and length)
            prompt_hash: Pre-computed SHA-256 hash (if prompt not available)
            prompt_length: Pre-computed prompt length (if prompt not available)
            wrapper_type: SDK wrapper type if applicable
            action_taken: Policy action taken
            l2_enabled: Whether L2 was enabled for this scan

        Returns:
            Complete telemetry payload dict matching schema v2.0
        """
        # Calculate prompt_hash and prompt_length
        if prompt is not None:
            computed_hash = self._compute_prompt_hash(prompt)
            computed_length = len(prompt)
        elif prompt_hash is not None and prompt_length is not None:
            # Use pre-computed values - ensure hash has prefix
            if not prompt_hash.startswith("sha256:"):
                computed_hash = f"sha256:{prompt_hash}"
            else:
                computed_hash = prompt_hash
            computed_length = prompt_length
        else:
            raise ValueError(
                "Must provide either 'prompt' or both 'prompt_hash' and 'prompt_length'"
            )

        # Build L1 block
        l1_block = self._build_l1_block(l1_result)

        # Build L2 block
        l2_block = self._build_l2_block(l2_result, l2_enabled)

        # Determine overall threat detection
        l1_hit = l1_block.get("hit", False) if l1_block else False
        l2_hit = l2_block.get("hit", False) if l2_block else False
        threat_detected = l1_hit or l2_hit

        # Build payload
        payload: dict[str, Any] = {
            # Core fields - all dynamically calculated
            "prompt_hash": computed_hash,
            "prompt_length": computed_length,
            "threat_detected": threat_detected,
            "scan_duration_ms": scan_duration_ms,
            "action_taken": action_taken,
            "entry_point": entry_point,
        }

        # Optional wrapper type
        if wrapper_type:
            payload["wrapper_type"] = wrapper_type

        # Add L1 block if available
        if l1_block:
            payload["l1"] = l1_block

        # Add L2 block if available
        if l2_block:
            payload["l2"] = l2_block

        return payload

    def _compute_prompt_hash(self, prompt: str) -> str:
        """Compute SHA-256 hash of prompt with prefix.

        Args:
            prompt: Text to hash

        Returns:
            Hash string with sha256: prefix
        """
        hash_bytes = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return f"sha256:{hash_bytes}"

    def _build_l1_block(self, l1_result: L1Result | None) -> dict[str, Any] | None:
        """Build L1 telemetry block from L1Result.

        Args:
            l1_result: L1 detection result

        Returns:
            L1 block dict or None if no L1 result
        """
        if l1_result is None:
            return None

        # Get detections list
        detections = getattr(l1_result, "detections", []) or []
        detection_count = len(detections)

        # Calculate hit status
        hit = detection_count > 0

        # Get duration
        duration_ms = getattr(l1_result, "scan_duration_ms", 0.0) or 0.0

        # Extract unique families
        families: list[str] = []
        for detection in detections:
            family = getattr(detection, "family", None)
            if family and family not in families:
                families.append(family)

        # Calculate highest severity
        highest_severity = "none"
        highest_order = 0
        for detection in detections:
            severity = getattr(detection, "severity", "none")
            if isinstance(severity, str):
                severity_str = severity.lower()
            else:
                severity_str = str(severity.value).lower() if hasattr(severity, "value") else "none"
            order = SEVERITY_ORDER.get(severity_str, 0)
            if order > highest_order:
                highest_order = order
                highest_severity = severity_str

        # Build per-detection details (limited)
        detection_details: list[dict[str, Any]] = []
        for detection in detections[: self.max_l1_detections]:
            rule_id = getattr(detection, "rule_id", "unknown")
            family = getattr(detection, "family", "unknown")
            severity = getattr(detection, "severity", "none")
            confidence = getattr(detection, "confidence", 1.0)

            # Handle severity enum
            if hasattr(severity, "value"):
                severity = severity.value
            severity_str = str(severity).lower()

            detection_details.append({
                "rule_id": rule_id,
                "family": family,
                "severity": severity_str,
                "confidence": float(confidence) if confidence is not None else 1.0,
            })

        return {
            "hit": hit,
            "duration_ms": duration_ms,
            "detection_count": detection_count,
            "highest_severity": highest_severity,
            "families": families,
            "detections": detection_details,
        }

    def _build_l2_block(
        self, l2_result: L2Result | None, l2_enabled: bool
    ) -> dict[str, Any] | None:
        """Build L2 telemetry block from L2Result.

        Args:
            l2_result: L2 ML detection result
            l2_enabled: Whether L2 was enabled

        Returns:
            L2 block dict or None if L2 disabled
        """
        if not l2_enabled:
            return {"enabled": False, "hit": False}

        if l2_result is None:
            return {"enabled": True, "hit": False}

        # Check if L2 has predictions
        predictions = getattr(l2_result, "predictions", []) or []
        if not predictions:
            # Even without predictions, include voting data if available
            base_result: dict[str, Any] = {
                "enabled": True,
                "hit": False,
                "duration_ms": getattr(l2_result, "processing_time_ms", 0.0) or 0.0,
                "model_version": getattr(l2_result, "model_version", "unknown"),
            }
            # Include voting block for transparency on SAFE decisions
            voting_block = self._build_voting_block(l2_result)
            if voting_block:
                base_result["voting"] = voting_block
            return base_result

        # Get first prediction's metadata (contains all 5-head data)
        pred = predictions[0]
        metadata = getattr(pred, "metadata", {}) or {}

        # Extract values from metadata with safe fallbacks
        is_attack = metadata.get("is_attack", False)
        scores = metadata.get("scores", {}) or {}

        # Build binary head block
        threat_prob = scores.get("attack_probability", 0.0)
        binary_block = {
            "is_threat": bool(is_attack),
            "threat_probability": float(threat_prob),
            "safe_probability": 1.0 - float(threat_prob),
        }

        # Build family head block
        family_prediction = metadata.get("family", "benign")
        family_confidence = scores.get("family_confidence", 0.0)
        family_top3 = self._extract_top3_from_metadata(metadata, "family")
        family_block = {
            "prediction": family_prediction,
            "confidence": float(family_confidence),
            "top3": family_top3,
        }

        # Build severity head block
        severity_prediction = metadata.get("severity", "none")
        severity_confidence = scores.get("severity_confidence", 0.0)
        severity_dist = self._extract_severity_distribution(metadata)
        severity_block = {
            "prediction": severity_prediction,
            "confidence": float(severity_confidence),
            "distribution": severity_dist,
        }

        # Build technique head block
        technique_prediction = metadata.get("primary_technique") or metadata.get("sub_family")
        technique_confidence = scores.get("subfamily_confidence", 0.0) or metadata.get(
            "technique_confidence", 0.0
        )
        technique_top3 = self._extract_top3_from_metadata(metadata, "technique")
        technique_block = {
            "prediction": technique_prediction,
            "confidence": float(technique_confidence),
            "top3": technique_top3,
        }

        # Build harm types head block
        harm_types_data = metadata.get("harm_types", {}) or {}
        harm_types_block = self._build_harm_types_block(harm_types_data)

        # Extract derived/ensemble values
        classification = metadata.get("classification", "SAFE")
        recommended_action = metadata.get("action", "ALLOW")
        risk_score = metadata.get("risk_score", threat_prob * 100)
        hierarchical_score = metadata.get("hierarchical_score", threat_prob)

        # Build quality signals for drift detection
        quality_block = self._build_quality_block(
            threat_prob=threat_prob,
            family_confidence=family_confidence,
            is_attack=is_attack,
            family_prediction=family_prediction,
            metadata=metadata,
        )

        # Get L2 hit status from is_threat property
        l2_hit = getattr(l2_result, "is_threat", False)

        # Build voting block if available (NEW in v2.1)
        voting_block = self._build_voting_block(l2_result)

        result = {
            "enabled": True,
            "hit": l2_hit,
            "duration_ms": getattr(l2_result, "processing_time_ms", 0.0) or 0.0,
            "model_version": getattr(l2_result, "model_version", "unknown"),
            "binary": binary_block,
            "family": family_block,
            "severity": severity_block,
            "technique": technique_block,
            "harm_types": harm_types_block,
            "classification": classification,
            "recommended_action": recommended_action,
            "risk_score": float(risk_score),
            "hierarchical_score": float(hierarchical_score),
            "quality": quality_block,
        }

        # Add voting block if available
        if voting_block:
            result["voting"] = voting_block

        return result

    def _build_voting_block(
        self, l2_result: L2Result | None
    ) -> dict[str, Any] | None:
        """Build voting block from L2Result voting field.

        Args:
            l2_result: L2 ML detection result

        Returns:
            Voting telemetry block or None if voting not available
        """
        if l2_result is None:
            return None

        # Get voting data from L2Result
        voting_data = getattr(l2_result, "voting", None)
        if not voting_data:
            return None

        # Return voting data as-is (already in dict format from VotingResult.to_dict())
        # The voting data includes: decision, confidence, preset_used, per_head_votes,
        # aggregated_scores, decision_rule_triggered, threat/safe/abstain counts, etc.
        return voting_data

    def _extract_top3_from_metadata(
        self, metadata: dict[str, Any], head_type: str
    ) -> list[dict[str, Any]]:
        """Extract top-3 predictions for a head from metadata.

        Args:
            metadata: Prediction metadata dict
            head_type: "family" or "technique"

        Returns:
            List of top-3 {label, probability} dicts
        """
        # Try to get probabilities from metadata
        if head_type == "family":
            probs_key = "family_probabilities"
            labels = FAMILY_LABELS
            prediction = metadata.get("family", "benign")
            confidence = (metadata.get("scores", {}) or {}).get("family_confidence", 0.0)
        else:  # technique
            probs_key = "technique_probabilities"
            labels = TECHNIQUE_LABELS
            prediction = metadata.get("primary_technique") or metadata.get("sub_family", "none")
            confidence = (metadata.get("scores", {}) or {}).get("subfamily_confidence", 0.0)

        # If full probabilities available, use them
        probs = metadata.get(probs_key)
        if probs and isinstance(probs, (list, tuple)) and len(probs) == len(labels):
            # Sort by probability descending
            sorted_items = sorted(
                zip(labels, probs), key=lambda x: -x[1]
            )[:3]
            return [{"label": label, "probability": float(prob)} for label, prob in sorted_items]

        # Fallback: construct from prediction and confidence
        if prediction and confidence:
            return [{"label": prediction, "probability": float(confidence)}]

        return []

    def _extract_severity_distribution(
        self, metadata: dict[str, Any]
    ) -> dict[str, float]:
        """Extract severity distribution from metadata.

        Args:
            metadata: Prediction metadata dict

        Returns:
            Dict mapping severity levels to probabilities
        """
        # Try to get full distribution
        probs = metadata.get("severity_probabilities")
        if probs and isinstance(probs, (list, tuple)) and len(probs) == 5:
            return dict(zip(SEVERITY_LABELS, [float(p) for p in probs]))

        # Fallback: construct from prediction and confidence
        prediction = metadata.get("severity", "none")
        confidence = (metadata.get("scores", {}) or {}).get("severity_confidence", 0.0)

        # Initialize with small values
        dist = {label: 0.01 for label in SEVERITY_LABELS}
        if prediction in dist:
            dist[prediction] = float(confidence)
            # Normalize
            total = sum(dist.values())
            if total > 0:
                dist = {k: v / total for k, v in dist.items()}

        return dist

    def _build_harm_types_block(
        self, harm_types_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Build harm types block from harm types result.

        Args:
            harm_types_data: Harm types dict from metadata

        Returns:
            Harm types telemetry block
        """
        if not harm_types_data:
            return {
                "active_labels": [],
                "active_count": 0,
                "max_probability": 0.0,
                "probabilities": {label: 0.0 for label in HARM_TYPE_LABELS},
            }

        # Extract active labels
        active_labels = harm_types_data.get("active_labels", [])
        if active_labels and hasattr(active_labels[0], "value"):
            active_labels = [h.value for h in active_labels]

        # Extract probabilities
        probs_data = harm_types_data.get("probabilities", {})
        if isinstance(probs_data, dict):
            probabilities = {label: float(probs_data.get(label, 0.0)) for label in HARM_TYPE_LABELS}
        else:
            probabilities = {label: 0.0 for label in HARM_TYPE_LABELS}

        # Calculate max probability
        max_prob = harm_types_data.get("max_probability", 0.0)
        if not max_prob and probabilities:
            max_prob = max(probabilities.values()) if probabilities else 0.0

        return {
            "active_labels": list(active_labels) if active_labels else [],
            "active_count": len(active_labels) if active_labels else 0,
            "max_probability": float(max_prob),
            "probabilities": probabilities,
        }

    def _build_quality_block(
        self,
        threat_prob: float,
        family_confidence: float,
        is_attack: bool,
        family_prediction: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Build quality signals block for drift detection.

        Args:
            threat_prob: Binary head threat probability
            family_confidence: Family head confidence
            is_attack: Binary classification result
            family_prediction: Family head prediction
            metadata: Full prediction metadata

        Returns:
            Quality signals block
        """
        # Calculate uncertain flag
        uncertain = family_confidence < 0.5 or (0.35 <= threat_prob < 0.6)

        # Calculate head agreement (binary agrees with family)
        family_is_benign = family_prediction == "benign"
        binary_is_benign = not is_attack
        head_agreement = family_is_benign == binary_is_benign

        # Calculate binary margin (distance from decision boundary)
        binary_margin = abs(threat_prob - 0.5)

        # Calculate family entropy if probabilities available
        family_probs = metadata.get("family_probabilities")
        if family_probs and isinstance(family_probs, (list, tuple)):
            family_entropy = self._calculate_entropy(list(family_probs))
        else:
            # Estimate entropy from confidence
            family_entropy = -math.log(max(family_confidence, 0.01)) if family_confidence > 0 else 0.0

        # Calculate consistency score (multi-head agreement metric)
        # Higher score = heads agree, lower = confusion
        consistency_signals = [
            1.0 if head_agreement else 0.0,
            min(1.0, binary_margin * 2),  # Scaled margin
            family_confidence,
        ]
        consistency_score = sum(consistency_signals) / len(consistency_signals)

        return {
            "uncertain": uncertain,
            "head_agreement": head_agreement,
            "binary_margin": round(binary_margin, 4),
            "family_entropy": round(family_entropy, 4),
            "consistency_score": round(consistency_score, 4),
        }

    def _calculate_entropy(self, probabilities: list[float]) -> float:
        """Calculate Shannon entropy of probability distribution.

        Args:
            probabilities: List of probabilities (should sum to ~1.0)

        Returns:
            Entropy value (higher = more uncertain)
        """
        entropy = 0.0
        for p in probabilities:
            if p > 0:
                entropy -= p * math.log(p)
        return entropy


# Singleton instance for convenience
_builder: ScanTelemetryBuilder | None = None


def get_scan_telemetry_builder() -> ScanTelemetryBuilder:
    """Get singleton ScanTelemetryBuilder instance.

    Returns:
        ScanTelemetryBuilder instance
    """
    global _builder
    if _builder is None:
        _builder = ScanTelemetryBuilder()
    return _builder


def build_scan_telemetry(
    l1_result: Any,
    l2_result: Any,
    scan_duration_ms: float,
    entry_point: Literal["cli", "sdk", "wrapper", "integration"] = "sdk",
    *,
    prompt: str | None = None,
    prompt_hash: str | None = None,
    prompt_length: int | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience function to build scan telemetry.

    Provide either `prompt` OR both `prompt_hash` and `prompt_length`.

    Args:
        l1_result: L1 detection result
        l2_result: L2 ML detection result
        scan_duration_ms: Total scan duration
        entry_point: How scan was triggered
        prompt: Original prompt text (preferred)
        prompt_hash: Pre-computed SHA-256 hash
        prompt_length: Pre-computed prompt length
        **kwargs: Additional arguments passed to builder

    Returns:
        Complete telemetry payload dict
    """
    builder = get_scan_telemetry_builder()
    return builder.build(
        l1_result=l1_result,
        l2_result=l2_result,
        scan_duration_ms=scan_duration_ms,
        entry_point=entry_point,
        prompt=prompt,
        prompt_hash=prompt_hash,
        prompt_length=prompt_length,
        **kwargs,
    )
