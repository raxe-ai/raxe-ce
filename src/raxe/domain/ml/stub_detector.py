"""Stub L2 detector for MVP.

Simple heuristic-based detector that demonstrates the L2 interface
without requiring a real ML model.

THIS IS A TEMPORARY IMPLEMENTATION:
- Uses simple pattern matching (not ML)
- Low confidence scores (<0.9)
- Will be replaced with ONNX model post-MVP
- Unblocks integration work while real model is in development

Performance target: <1ms (should be trivial since it's just string ops)
"""
import base64
import re
import time
from typing import Any, ClassVar

from raxe.domain.engine.executor import ScanResult as L1ScanResult
from raxe.domain.ml.protocol import L2Prediction, L2Result, L2ThreatType


class StubL2Detector:
    """Stub L2 detector using simple heuristics.

    This is NOT a real ML model - it's a placeholder that:
    1. Demonstrates the L2 interface
    2. Provides basic semantic detection via patterns
    3. Unblocks integration work
    4. Will be replaced with ONNX model post-MVP

    Detection strategies:
    - Encoded content: Look for base64, hex, unicode escapes
    - Code execution: Look for eval, exec, __import__, etc.
    - Context manipulation: Long prompts with L1 detections
    - Obfuscation: Mixed encodings, zero-width chars

    Performance:
    - Target: <1ms (simple string operations)
    - No external calls, no heavy computation
    """

    VERSION = "stub-1.0.0"

    # Suspicious function/method patterns
    SUSPICIOUS_PATTERNS: ClassVar[list] = [
        r"\beval\s*\(",
        r"\bexec\s*\(",
        r"__import__",
        r"\bcompile\s*\(",
        r"\bglobals\s*\(",
        r"\blocals\s*\(",
        r"\.system\s*\(",
        r"\bsubprocess\.",
        r"\bos\.system",
        r"\bpopen\s*\(",
    ]

    # Encoding indicators
    ENCODING_INDICATORS: ClassVar[list] = [
        r"\bbase64\b",
        r"\bb64decode\b",
        r"\bfromhex\b",
        r"\\x[0-9a-fA-F]{2}",  # Hex escapes
        r"&#x[0-9a-fA-F]+;",   # HTML hex entities
        r"\\u[0-9a-fA-F]{4}",  # Unicode escapes
        r"0x[0-9a-fA-F]+",     # Hex literals
    ]

    # Obfuscation patterns
    OBFUSCATION_PATTERNS: ClassVar[list] = [
        r"[\u200B-\u200D\uFEFF]",  # Zero-width characters
        r"[\u0000-\u0008\u000B\u000C\u000E-\u001F]",  # Control characters (excluding \t \n \r)
        r"[^\x00-\x7F]{20,}",       # Long non-ASCII sequences
    ]

    # Role/privilege escalation keywords
    PRIVILEGE_KEYWORDS: ClassVar[list] = [
        r"\bsudo\b",
        r"\badmin\b",
        r"\broot\b",
        r"\belevate.*privilege",
        r"\bassume.*role",
        r"\bbecome\s+(admin|root|superuser)",
    ]

    def __init__(self):
        """Initialize stub detector.

        Pre-compiles regex patterns for performance.
        """
        # Compile patterns once for reuse
        self._suspicious_re = [re.compile(p, re.IGNORECASE) for p in self.SUSPICIOUS_PATTERNS]
        self._encoding_re = [re.compile(p, re.IGNORECASE) for p in self.ENCODING_INDICATORS]
        self._obfuscation_re = [re.compile(p) for p in self.OBFUSCATION_PATTERNS]
        self._privilege_re = [re.compile(p, re.IGNORECASE) for p in self.PRIVILEGE_KEYWORDS]

    def analyze(
        self,
        text: str,
        l1_results: L1ScanResult,
        context: dict[str, Any] | None = None
    ) -> L2Result:
        """Analyze text using simple heuristics.

        This stub looks for:
        1. Encoded content (base64, hex, unicode)
        2. Code execution patterns (eval, exec, etc.)
        3. Context manipulation (long prompts + L1 hits)
        4. Obfuscation techniques
        5. Privilege escalation keywords

        Args:
            text: Text to analyze
            l1_results: Results from L1 rule-based detection
            context: Optional context (unused in stub, but part of protocol)

        Returns:
            L2Result with heuristic predictions
        """
        start = time.perf_counter()

        predictions = []

        # Check for encoded content
        encoded_pred = self._check_encoded_content(text)
        if encoded_pred:
            predictions.append(encoded_pred)

        # Check for code execution patterns
        code_pred = self._check_code_execution(text)
        if code_pred:
            predictions.append(code_pred)

        # Check for context manipulation
        context_pred = self._check_context_manipulation(text, l1_results)
        if context_pred:
            predictions.append(context_pred)

        # Check for obfuscation
        obfuscation_pred = self._check_obfuscation(text)
        if obfuscation_pred:
            predictions.append(obfuscation_pred)

        # Check for privilege escalation
        privilege_pred = self._check_privilege_escalation(text)
        if privilege_pred:
            predictions.append(privilege_pred)

        duration_ms = (time.perf_counter() - start) * 1000

        # Overall confidence is max of individual predictions
        overall_confidence = (
            max(p.confidence for p in predictions)
            if predictions else 0.0
        )

        # Extract features for debugging/logging
        features = {
            "text_length": len(text),
            "l1_detection_count": l1_results.detection_count,
            "l1_highest_severity": l1_results.highest_severity.value if l1_results.highest_severity else None,
            "has_l1_detections": l1_results.has_detections,
        }

        return L2Result(
            predictions=predictions,
            confidence=overall_confidence,
            processing_time_ms=duration_ms,
            model_version=self.VERSION,
            features_extracted=features,
            metadata={
                "detector_type": "stub",
                "is_production_ready": False,
            }
        )

    @property
    def model_info(self) -> dict[str, Any]:
        """Return stub model info."""
        return {
            "name": "RAXE Stub L2 Detector",
            "version": self.VERSION,
            "type": "heuristic",
            "is_stub": True,
            "size_mb": 0.0,  # No model file
            "latency_p95_ms": 1.0,
            "accuracy": 0.6,  # Rough estimate for heuristics
            "description": (
                "Simple pattern-based stub for MVP. "
                "Uses regex patterns to detect encoded content, code execution, "
                "and other threats. Will be replaced with ONNX ML model."
            ),
            "will_be_replaced_with": "ONNX ML model",
            "limitations": [
                "Not a real ML model",
                "Low accuracy compared to ML",
                "High false positive risk",
                "Cannot detect semantic threats",
            ]
        }

    def _check_encoded_content(self, text: str) -> L2Prediction | None:
        """Check if text contains encoded content.

        Looks for:
        - Encoding keywords (base64, fromhex, etc.)
        - Base64-like patterns (long alphanumeric strings)
        - Hex escapes and unicode escapes

        Returns:
            L2Prediction if encoded content detected, None otherwise
        """
        features_triggered = []

        # Check for encoding indicators
        for pattern in self._encoding_re:
            if pattern.search(text):
                features_triggered.append(f"encoding_pattern: {pattern.pattern}")

        # Try to detect base64 strings (rough heuristic)
        # Look for long alphanumeric strings (>30 chars) with typical base64 chars
        base64_pattern = re.compile(r"[A-Za-z0-9+/]{30,}={0,2}")
        potential_base64 = base64_pattern.findall(text)

        for candidate in potential_base64:
            # Skip if it's just repeated characters (e.g., "aaaa...")
            # Real base64 has variety
            unique_chars = len(set(candidate.replace('=', '')))
            if unique_chars < 4:
                continue

            try:
                # Try to decode - if it works, might be base64
                decoded = base64.b64decode(candidate, validate=True)
                # Additionally check if decoded content looks reasonable
                # Base64 should decode to printable or binary data, not just zeros
                if decoded and len(decoded) > 0:
                    features_triggered.append("valid_base64_string")
                    break
            except Exception:
                pass

        if not features_triggered:
            return None

        # Confidence based on number of indicators
        confidence = min(0.5 + (len(features_triggered) * 0.1), 0.85)

        return L2Prediction(
            threat_type=L2ThreatType.ENCODING_OR_OBFUSCATION,
            confidence=confidence,
            explanation=f"Detected potentially encoded content: {', '.join(features_triggered[:3])}",
            features_used=features_triggered,
        )

    def _check_code_execution(self, text: str) -> L2Prediction | None:
        """Check for code execution patterns.

        Looks for suspicious function calls like eval, exec, __import__, etc.

        Returns:
            L2Prediction if code execution detected, None otherwise
        """
        features_triggered = []

        for pattern in self._suspicious_re:
            match = pattern.search(text)
            if match:
                features_triggered.append(f"code_pattern: {match.group(0)}")

        if not features_triggered:
            return None

        # Higher confidence if multiple patterns match
        confidence = min(0.6 + (len(features_triggered) * 0.05), 0.8)

        return L2Prediction(
            threat_type=L2ThreatType.JAILBREAK,
            confidence=confidence,
            explanation=f"Detected code execution patterns: {', '.join(features_triggered[:3])}",
            features_used=features_triggered,
        )

    def _check_context_manipulation(
        self,
        text: str,
        l1_results: L1ScanResult
    ) -> L2Prediction | None:
        """Check for context manipulation.

        Simple heuristic: if L1 detected threats AND text is very long,
        might be attempting to manipulate context or conversation.

        Returns:
            L2Prediction if context manipulation detected, None otherwise
        """
        # Only flag if L1 already detected something
        if not l1_results.has_detections:
            return None

        # And text is suspiciously long (>800 chars)
        if len(text) < 800:
            return None

        # Check for common context manipulation phrases
        manipulation_phrases = [
            "forget",
            "ignore previous",
            "disregard",
            "new instructions",
            "system prompt",
            "override",
        ]

        phrase_count = sum(
            1 for phrase in manipulation_phrases
            if phrase in text.lower()
        )

        if phrase_count == 0:
            return None

        # Confidence based on text length and phrase count
        # Keep it low since this is a rough heuristic
        confidence = min(0.5 + (phrase_count * 0.05), 0.7)

        return L2Prediction(
            threat_type=L2ThreatType.RAG_OR_CONTEXT_ATTACK,
            confidence=confidence,
            explanation=(
                f"Possible context manipulation: long text ({len(text)} chars) "
                f"with {phrase_count} manipulation phrases and {l1_results.detection_count} L1 detections"
            ),
            features_used=[
                "l1_detections",
                "text_length",
                "manipulation_phrases",
            ],
        )

    def _check_obfuscation(self, text: str) -> L2Prediction | None:
        """Check for obfuscation techniques.

        Looks for:
        - Zero-width characters
        - Control characters
        - Long non-ASCII sequences

        Returns:
            L2Prediction if obfuscation detected, None otherwise
        """
        features_triggered = []

        for pattern in self._obfuscation_re:
            match = pattern.search(text)
            if match:
                features_triggered.append(f"obfuscation: {pattern.pattern[:30]}")

        if not features_triggered:
            return None

        confidence = min(0.65 + (len(features_triggered) * 0.1), 0.85)

        return L2Prediction(
            threat_type=L2ThreatType.ENCODING_OR_OBFUSCATION,
            confidence=confidence,
            explanation=f"Detected obfuscation techniques: {', '.join(features_triggered)}",
            features_used=features_triggered,
        )

    def _check_privilege_escalation(self, text: str) -> L2Prediction | None:
        """Check for privilege escalation keywords.

        Looks for terms related to gaining elevated privileges or roles.

        Returns:
            L2Prediction if privilege escalation detected, None otherwise
        """
        features_triggered = []

        for pattern in self._privilege_re:
            match = pattern.search(text)
            if match:
                features_triggered.append(f"privilege_keyword: {match.group(0)}")

        if not features_triggered:
            return None

        confidence = min(0.55 + (len(features_triggered) * 0.08), 0.75)

        return L2Prediction(
            threat_type=L2ThreatType.JAILBREAK,  # Privilege escalation maps to jailbreak
            confidence=confidence,
            explanation=f"Detected privilege escalation keywords: {', '.join(features_triggered[:3])}",
            features_used=features_triggered,
        )
