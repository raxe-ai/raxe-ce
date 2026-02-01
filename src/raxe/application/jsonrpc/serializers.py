"""JSON-RPC scan result serializers.

Application layer - converts domain objects to JSON-RPC response format.

CRITICAL PRIVACY REQUIREMENTS (ZERO TOLERANCE):
- NEVER include raw prompt text
- NEVER include matched_text from detections
- NEVER include system_prompt or response_text
- NEVER include patterns from rules
- NEVER include Match objects with sensitive data

MUST Include (for useful responses):
- has_threats: boolean
- severity: string (highest severity)
- action: string (allow/block/warn)
- detections: list of detection metadata (NO matched_text)
- scan_duration_ms: float
- prompt_hash: string (SHA256 hash)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raxe.application.scan_pipeline import ScanPipelineResult
    from raxe.domain.ml.protocol import L2Prediction


class ScanResultSerializer:
    """Serialize ScanPipelineResult to privacy-safe JSON-RPC format.

    This is the SINGLE SOURCE OF TRUTH for converting scan results
    to JSON-RPC response format. All output must be privacy-safe.

    CRITICAL: This serializer is designed to NEVER expose:
    - Raw prompt text
    - matched_text from detections
    - Pattern details from rules
    - Any PII or sensitive data

    Example:
        >>> serializer = ScanResultSerializer()
        >>> serialized = serializer.serialize(scan_result)
        >>> # serialized is safe to send over JSON-RPC
    """

    def serialize(
        self,
        result: ScanPipelineResult,
        *,
        include_detections: bool = True,
    ) -> dict[str, Any]:
        """Serialize scan result to privacy-safe JSON-RPC format.

        Args:
            result: The ScanPipelineResult to serialize
            include_detections: Whether to include detection metadata (default: True)

        Returns:
            Dictionary safe for JSON-RPC response with:
            - has_threats: bool
            - severity: str | None
            - action: str
            - detections: list[dict] (metadata only, NO matched_text)
            - scan_duration_ms: float
            - prompt_hash: str

        Note:
            Detection metadata includes ONLY:
            - rule_id
            - severity
            - confidence
            - category/family
            - detection_layer

            Detection metadata NEVER includes:
            - matched_text
            - pattern
            - context_before/context_after
            - Match objects
        """
        # Build safe response dictionary
        response: dict[str, Any] = {
            "has_threats": result.has_threats,
            "severity": self._serialize_severity(result),
            "action": result.policy_decision.value.lower(),
            "scan_duration_ms": result.duration_ms,
            "prompt_hash": result.text_hash,
        }

        # Add detections if requested (always privacy-safe)
        if include_detections:
            response["detections"] = self._serialize_detections(result)
        else:
            response["detections"] = []

        # Add L2 predictions if available (privacy-safe metadata only)
        l2_predictions = self._serialize_l2_predictions(result)
        if l2_predictions:
            response["l2_predictions"] = l2_predictions

        return response

    def _serialize_severity(self, result: ScanPipelineResult) -> str | None:
        """Extract severity as lowercase string or None.

        Args:
            result: ScanPipelineResult

        Returns:
            Severity string (lowercase) or None if no threats
        """
        if result.scan_result.combined_severity:
            return result.scan_result.combined_severity.value.lower()
        return None

    def _serialize_detections(
        self,
        result: ScanPipelineResult,
    ) -> list[dict[str, Any]]:
        """Serialize detections to privacy-safe format.

        CRITICAL: This method MUST NOT include:
        - matched_text
        - pattern details
        - Match objects
        - context_before/context_after

        Args:
            result: ScanPipelineResult containing detections

        Returns:
            List of detection dictionaries with safe metadata only
        """
        detections = []

        for detection in result.scan_result.l1_detections:
            # PRIVACY-SAFE: Only include metadata, NEVER include matched_text
            safe_detection: dict[str, Any] = {
                "rule_id": detection.rule_id,
                "severity": detection.severity.value.lower(),
                "confidence": detection.confidence,
                "category": detection.category,
                "detection_layer": detection.detection_layer,
            }

            # Include optional non-sensitive fields
            if detection.message:
                safe_detection["message"] = detection.message

            detections.append(safe_detection)

        return detections

    def _serialize_l2_predictions(
        self,
        result: ScanPipelineResult,
    ) -> list[dict[str, Any]]:
        """Serialize L2 predictions to privacy-safe format.

        CRITICAL: This method MUST NOT include:
        - matched_text from metadata
        - Any raw text content

        Args:
            result: ScanPipelineResult containing L2 predictions

        Returns:
            List of L2 prediction dictionaries with safe metadata only
        """
        predictions: list[dict[str, Any]] = []

        l2_result = result.scan_result.l2_result
        if not l2_result or not l2_result.predictions:
            return predictions

        for prediction in l2_result.predictions:
            safe_prediction = self._serialize_single_l2_prediction(prediction)
            predictions.append(safe_prediction)

        return predictions

    def _serialize_single_l2_prediction(
        self,
        prediction: L2Prediction,
    ) -> dict[str, Any]:
        """Serialize a single L2 prediction to privacy-safe format.

        Args:
            prediction: L2Prediction object

        Returns:
            Dictionary with safe metadata only
        """
        safe_prediction: dict[str, Any] = {
            "threat_type": prediction.threat_type.value,
            "confidence": prediction.confidence,
        }

        # Include explanation if available (should not contain PII)
        if prediction.explanation:
            safe_prediction["explanation"] = prediction.explanation

        # Include features_used if available (these are just feature names, not content)
        if prediction.features_used:
            safe_prediction["features_used"] = prediction.features_used

        # Filter metadata to remove any sensitive fields
        if prediction.metadata:
            safe_metadata = self._filter_safe_metadata(prediction.metadata)
            if safe_metadata:
                safe_prediction["metadata"] = safe_metadata

        return safe_prediction

    def _filter_safe_metadata(
        self,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Filter metadata to include only safe (non-PII) fields.

        CRITICAL: This method filters OUT any fields that might contain
        sensitive data from L2 predictions.

        Args:
            metadata: Raw metadata from L2 prediction

        Returns:
            Filtered metadata with only safe fields
        """
        # List of fields that are SAFE to include
        safe_fields = {
            "is_attack",
            "family",
            "sub_family",
            "scores",
            "recommended_action",
            "uncertain",
            "model_version",
            "processing_time_ms",
        }

        # Fields that must NEVER be included (contain potential PII)
        # NOTE: We explicitly list these to ensure they are never included
        # even if added to metadata in the future
        forbidden_fields = {
            "matched_text",
            "prompt",
            "prompt_text",
            "response",
            "response_text",
            "system_prompt",
            "context",
            "raw_text",
            "input_text",
            "output_text",
            "user_input",
            "trigger_matches",  # May contain text snippets
            "why_it_hit",  # May contain text snippets
        }

        # Filter to only safe fields
        return {
            key: value
            for key, value in metadata.items()
            if key in safe_fields and key not in forbidden_fields
        }


__all__ = ["ScanResultSerializer"]
