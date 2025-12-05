"""
Pure functions for creating privacy-preserving telemetry events.

This module contains ONLY pure functions - no I/O operations.
All functions take data and return data without side effects.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any


def hash_text(text: str, algorithm: str = "sha256") -> str:
    """
    Create a privacy-preserving hash of text with algorithm prefix.

    Args:
        text: Text to hash
        algorithm: Hash algorithm (sha256, sha512, blake2b)

    Returns:
        Prefixed hash string in format "{algorithm}:{hex_hash}"
        For sha256: 71 characters total (7 char prefix + 64 char hash)

    Note:
        This is a one-way hash - the original text cannot be recovered.

    Example:
        >>> hash_text("Hello, world!")
        'sha256:315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3'
    """
    if algorithm == "sha256":
        hasher = hashlib.sha256()
    elif algorithm == "sha512":
        hasher = hashlib.sha512()
    elif algorithm == "blake2b":
        hasher = hashlib.blake2b()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    hasher.update(text.encode('utf-8'))
    return f"{algorithm}:{hasher.hexdigest()}"


def hash_identifier(identifier: str, salt: str = "") -> str:
    """
    Hash an identifier (user_id, session_id, etc.) for privacy.

    Args:
        identifier: Identifier to hash
        salt: Optional salt for additional security

    Returns:
        Hashed identifier with sha256: prefix (71 characters)
    """
    if not identifier:
        return ""

    salted = f"{salt}{identifier}" if salt else identifier
    return hash_text(salted)


def create_scan_event(
    scan_result: dict[str, Any],
    customer_id: str,
    api_key_id: str | None = None,
    context: dict[str, Any] | None = None,
    performance_metrics: dict[str, Any] | None = None,
    hash_algorithm: str = "sha256"
) -> dict[str, Any]:
    """
    Create a privacy-preserving scan event from a scan result.

    This is a PURE function - no I/O, no side effects.

    Args:
        scan_result: Scan result from scanning pipeline
        customer_id: Customer identifier
        api_key_id: API key identifier (optional)
        context: Additional context (session_id, user_id, etc.)
        performance_metrics: Performance timing data
        hash_algorithm: Algorithm for hashing

    Returns:
        Event dictionary ready for telemetry (NO PII)

    Schema compliance:
        Matches schemas/v2.1.0/events/scan_performed.json
    """
    # Extract prompt for hashing (never include actual text)
    prompt_text = scan_result.get("prompt", "")
    if isinstance(prompt_text, dict):
        # Handle structured prompt
        prompt_text = prompt_text.get("text", "")

    # Create text hash
    text_hash = hash_text(prompt_text, hash_algorithm) if prompt_text else ""

    # Extract L1 detections (no PII)
    l1_detections = []
    if scan_result.get("l1_result"):
        l1_result = scan_result["l1_result"]
        if "detections" in l1_result:
            for detection in l1_result["detections"]:
                l1_detections.append({
                    "rule_id": detection.get("rule_id", ""),
                    "severity": detection.get("severity", "").lower(),
                    "confidence": detection.get("confidence", 1.0)
                })

    # Extract L2 predictions with rich metadata (no PII)
    # L2 METADATA SHARING POLICY (privacy-safe):
    # ✅ SHARE: model metrics (confidence, scores, processing time, model version)
    # ✅ SHARE: feature names (e.g., "instruction_override", "api_key_pattern")
    # ✅ SHARE: signal quality metrics (consistency, margins, variance)
    # ✅ SHARE: threat classifications (SAFE, ATTACK_LIKELY, FP_LIKELY)
    # ❌ NEVER: actual prompt text, matched content, or any PII
    l2_predictions = []
    l2_metadata = None
    if scan_result.get("l2_result"):
        l2_result = scan_result["l2_result"]

        # Extract L2 result-level metadata (helps improve models)
        l2_metadata = {
            "overall_confidence": l2_result.get("confidence", 0.0),
            "processing_time_ms": l2_result.get("processing_time_ms", 0.0),
            "model_version": l2_result.get("model_version", "unknown"),
        }

        # Add optional L2 metrics (privacy-safe)
        if l2_result.get("hierarchical_score") is not None:
            l2_metadata["hierarchical_score"] = l2_result["hierarchical_score"]
        if l2_result.get("classification"):
            l2_metadata["classification"] = l2_result["classification"]
        if l2_result.get("signal_quality"):
            # Signal quality metrics are privacy-safe (consistency, margins, variance)
            l2_metadata["signal_quality"] = l2_result["signal_quality"]

        # Extract individual predictions with metadata
        if "predictions" in l2_result:
            for pred in l2_result["predictions"]:
                prediction_data = {
                    "threat_type": pred.get("threat_type", ""),
                    "confidence": pred.get("confidence", 0.0),
                }

                # Add features_used if available (feature names are privacy-safe)
                if pred.get("features_used"):
                    prediction_data["features_used"] = pred["features_used"]

                # Add prediction metadata (model-specific metrics, privacy-safe)
                if pred.get("metadata"):
                    prediction_data["metadata"] = pred["metadata"]

                l2_predictions.append(prediction_data)

    # Extract policy decision (privacy: no policy IDs)
    policy_decision = None
    if scan_result.get("policy_result"):
        policy_result = scan_result["policy_result"]
        policy_decision = {
            "action": policy_result.get("action", "ALLOW"),
            # Privacy: DO NOT include policy IDs - they could reveal customer-specific rules
            # "matched_policies": REMOVED for privacy
        }

    # Determine threat detection status
    threat_detected = (
        len(l1_detections) > 0 or
        len(l2_predictions) > 0 or
        (policy_decision and policy_decision["action"] != "ALLOW")
    )

    # Calculate highest severity
    highest_severity = None
    if l1_detections:
        severities = [d["severity"] for d in l1_detections]
        severity_order = ["critical", "high", "medium", "low", "info"]
        for sev in severity_order:
            if sev in severities:
                highest_severity = sev
                break

    # Process context with privacy protection
    processed_context = {}
    if context:
        # Hash any identifiers in context
        if "session_id" in context:
            processed_context["session_id"] = hash_identifier(context["session_id"])
        if "user_id" in context:
            processed_context["user_id"] = hash_identifier(context["user_id"])
        if "app_name" in context:
            processed_context["app_name"] = context["app_name"]
        if "sdk_version" in context:
            processed_context["sdk_version"] = context["sdk_version"]
        if "environment" in context:
            processed_context["environment"] = context["environment"]

    # Build scan result for event
    event_scan_result = {
        "text_hash": text_hash,
        "text_length": len(prompt_text),
        "threat_detected": threat_detected,
        "detection_count": len(l1_detections) + len(l2_predictions),
        "highest_severity": highest_severity,
        "l1_detections": l1_detections,
        "l2_predictions": l2_predictions
    }

    # Add L2 metadata if available (rich ML metrics)
    if l2_metadata:
        event_scan_result["l2_metadata"] = l2_metadata

    if policy_decision:
        event_scan_result["policy_decision"] = policy_decision

    # Create event
    event = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "customer_id": customer_id,
        "scan_result": event_scan_result
    }

    # Add optional fields
    if api_key_id:
        event["api_key_id"] = api_key_id

    if performance_metrics:
        event["performance"] = performance_metrics

    if processed_context:
        event["context"] = processed_context

    return event


def validate_event_privacy(event: dict[str, Any]) -> list[str]:
    """
    Validate that an event contains no PII.

    This is a PURE function for validation.

    Args:
        event: Event to validate

    Returns:
        List of privacy violations (empty if compliant)
    """
    violations = []

    # Check for common PII patterns
    pii_patterns = [
        ("email", r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        ("phone", r"\+?[1-9]\d{10,14}$"),  # More specific phone pattern
        ("ssn", r"\d{3}-\d{2}-\d{4}"),
        ("credit_card", r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}")
    ]

    def check_value(value: Any, path: str) -> None:
        """Recursively check values for PII."""
        if isinstance(value, str):
            # Check if it looks like a prefixed hash (sha256:64hexchars = 71 chars)
            if value.startswith("sha256:") and len(value) == 71:
                hex_part = value[7:]
                if all(c in '0123456789abcdef' for c in hex_part):
                    return  # Valid prefixed hash, safe
            # Also accept legacy format (64 hex chars) for backwards compatibility during transition
            if len(value) == 64 and all(c in '0123456789abcdef' for c in value):
                return  # Likely a legacy hash, safe

            # Skip known safe patterns
            # UUID pattern (event_id, etc)
            import re
            if re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', value):
                return  # UUID, safe

            # ISO timestamp pattern
            if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', value):
                return  # Timestamp, safe

            # Customer ID pattern
            if re.match(r'^cust-[a-z0-9]{8}$', value):
                return  # Customer ID format, safe

            # Check for PII patterns
            for pii_type, pattern in pii_patterns:
                if re.search(pattern, value):
                    violations.append(f"{path} contains potential {pii_type}")

            # Check for raw text that's too long (likely not hashed)
            if len(value) > 100 and path != "error_message":
                violations.append(f"{path} contains unhashed long text")

        elif isinstance(value, dict):
            for k, v in value.items():
                check_value(v, f"{path}.{k}" if path else k)

        elif isinstance(value, list):
            for i, item in enumerate(value):
                check_value(item, f"{path}[{i}]")

    check_value(event, "")

    # Specific checks for required hashes
    if "scan_result" in event:
        scan_result = event["scan_result"]
        if "text_hash" in scan_result:
            text_hash = scan_result["text_hash"]
            # Accept new prefixed format (sha256:64hexchars = 71 chars)
            is_valid_prefixed = (
                isinstance(text_hash, str) and
                text_hash.startswith("sha256:") and
                len(text_hash) == 71
            )
            # Also accept legacy format (64 hex chars) during transition
            is_valid_legacy = isinstance(text_hash, str) and len(text_hash) == 64
            if not (is_valid_prefixed or is_valid_legacy):
                violations.append("scan_result.text_hash is not a valid SHA256 hash (expected sha256:... format)")

    return violations


def calculate_event_priority(event: dict[str, Any]) -> str:
    """
    Calculate priority for an event based on its content.

    This is a PURE function.

    Args:
        event: Event dictionary

    Returns:
        Priority level: "critical", "high", "medium", or "low"
    """
    # Critical: High severity threats or policy blocks
    if "scan_result" in event:
        scan_result = event["scan_result"]

        # Check for critical severity
        if scan_result.get("highest_severity") == "critical":
            return "critical"

        # Check for policy block
        if "policy_decision" in scan_result:
            if scan_result["policy_decision"].get("action") == "BLOCK":
                return "critical"

        # High: High severity or multiple detections
        if scan_result.get("highest_severity") == "high":
            return "high"

        if scan_result.get("detection_count", 0) >= 3:
            return "high"

        # Medium: Any detection
        if scan_result.get("threat_detected"):
            return "medium"

    # Low: Clean scans or other events
    return "low"