#!/usr/bin/env python3
"""
Test script for the new CLI output formatting with hierarchical scoring.

This script creates mock L2 results with hierarchical scoring data and tests
the formatting in both default and explain modes.
"""

from rich.console import Console

from raxe.cli.l2_formatter import L2ResultFormatter
from raxe.domain.ml.protocol import L2Prediction, L2Result, L2ThreatType


def create_mock_threat_prediction() -> L2Prediction:
    """Create a mock threat prediction with hierarchical scoring."""
    return L2Prediction(
        threat_type=L2ThreatType.SEMANTIC_JAILBREAK,
        confidence=0.902,
        explanation="Detected patterns indicating system role override and instruction bypass typical of jailbreak attempts.",
        features_used=["instruction_override", "role_manipulation", "system_bypass"],
        metadata={
            "classification": "THREAT",
            "action": "BLOCK",
            "risk_score": 87.0,
            "hierarchical_score": 0.87,
            "scores": {
                "attack_probability": 0.902,
                "family_confidence": 0.554,
                "subfamily_confidence": 0.439,
            },
            "is_consistent": True,
            "variance": 0.042,
            "weak_margins_count": 1,
            "margins": {
                "binary": 0.804,
                "family": 0.304,
                "subfamily": 0.239,
            },
            "family": "PI",
            "sub_family": "pi_instruction_override",
            "reason": "Threat score (90.2%) exceeds THREAT threshold (85%) for balanced mode. Family confidence is moderate but consistent with binary prediction. Overall signal quality indicates real threat, not false positive.",
            "why_it_hit": [
                "Detected patterns indicating system role override",
                "Instruction bypass typical of jailbreak attempts",
                "Strong binary classification with high margin",
            ],
        },
    )


def create_mock_fp_likely_prediction() -> L2Prediction:
    """Create a mock false positive likely prediction."""
    return L2Prediction(
        threat_type=L2ThreatType.OBFUSCATED_COMMAND,
        confidence=0.626,
        explanation="Detected 'exploit' keyword in business context - likely false positive.",
        features_used=["exploit_keyword", "collaborative_context"],
        metadata={
            "classification": "FP_LIKELY",
            "action": "ALLOW_WITH_LOG",
            "risk_score": 55.3,
            "hierarchical_score": 0.553,
            "scores": {
                "attack_probability": 0.626,
                "family_confidence": 0.502,
                "subfamily_confidence": 0.343,
            },
            "is_consistent": False,
            "variance": 0.095,
            "weak_margins_count": 2,
            "margins": {
                "binary": 0.252,
                "family": 0.152,
                "subfamily": 0.143,
            },
            "family": "CMD",
            "sub_family": "cmd_code_execution",
            "reason": "All confidence signals weak (hierarchical: 0.553, weak margins: 2/3). Business jargon context detected.",
            "why_it_hit": [
                "Keyword 'exploit' detected in text",
                "Pattern matches command execution signatures",
            ],
        },
    )


def create_mock_review_prediction() -> L2Prediction:
    """Create a mock prediction requiring manual review."""
    return L2Prediction(
        threat_type=L2ThreatType.DATA_EXFIL_PATTERN,
        confidence=0.782,
        explanation="Detected data extraction patterns but context is ambiguous.",
        features_used=["data_extraction", "security_context"],
        metadata={
            "classification": "REVIEW",
            "action": "MANUAL_REVIEW",
            "risk_score": 65.97,
            "hierarchical_score": 0.6597,
            "scores": {
                "attack_probability": 0.782,
                "family_confidence": 0.456,
                "subfamily_confidence": 0.312,
            },
            "is_consistent": False,
            "variance": 0.128,
            "weak_margins_count": 1,
            "margins": {
                "binary": 0.564,
                "family": 0.106,
                "subfamily": 0.062,
            },
            "family": "PII",
            "sub_family": "pii_data_extraction",
            "reason": "Inconsistent confidence levels suggest ambiguous context. Word 'malware' in legitimate security discussion.",
            "why_it_hit": [
                "Data extraction patterns detected",
                "Reference to sensitive information handling",
            ],
        },
    )


def create_mock_l2_result(prediction: L2Prediction) -> L2Result:
    """Create a mock L2Result with a prediction."""
    return L2Result(
        predictions=[prediction],
        confidence=prediction.confidence,
        processing_time_ms=4.2,
        model_version="threat-classifier-v1.0",
        features_extracted={"token_count": 128, "embedding_dim": 768},
        metadata={"model_type": "cascade", "quantization": "int8"},
    )


def test_default_mode():
    """Test default output mode (compact)."""
    console = Console()
    formatter = L2ResultFormatter()

    console.print("\n" + "=" * 80)
    console.print("TEST 1: THREAT DETECTION (Default Mode)", style="bold cyan")
    console.print("=" * 80 + "\n")

    threat_result = create_mock_l2_result(create_mock_threat_prediction())
    formatter.format_predictions(threat_result, console, explain=False)

    console.print("\n" + "=" * 80)
    console.print("TEST 2: FALSE POSITIVE LIKELY (Default Mode)", style="bold cyan")
    console.print("=" * 80 + "\n")

    fp_result = create_mock_l2_result(create_mock_fp_likely_prediction())
    formatter.format_predictions(fp_result, console, explain=False)

    console.print("\n" + "=" * 80)
    console.print("TEST 3: MANUAL REVIEW (Default Mode)", style="bold cyan")
    console.print("=" * 80 + "\n")

    review_result = create_mock_l2_result(create_mock_review_prediction())
    formatter.format_predictions(review_result, console, explain=False)


def test_explain_mode():
    """Test explain output mode (detailed)."""
    console = Console()
    formatter = L2ResultFormatter()

    console.print("\n" + "=" * 80)
    console.print("TEST 4: THREAT DETECTION (Explain Mode)", style="bold cyan")
    console.print("=" * 80 + "\n")

    threat_result = create_mock_l2_result(create_mock_threat_prediction())
    formatter.format_predictions(threat_result, console, explain=True)

    console.print("\n" + "=" * 80)
    console.print("TEST 5: FALSE POSITIVE LIKELY (Explain Mode)", style="bold cyan")
    console.print("=" * 80 + "\n")

    fp_result = create_mock_l2_result(create_mock_fp_likely_prediction())
    formatter.format_predictions(fp_result, console, explain=True)


def main():
    """Run all tests."""
    console = Console()
    console.print("\n" + "=" * 80, style="bold green")
    console.print("CLI OUTPUT FORMATTING TEST SUITE", style="bold green")
    console.print("Testing hierarchical scoring display", style="green")
    console.print("=" * 80 + "\n", style="bold green")

    # Test default mode
    test_default_mode()

    # Test explain mode
    test_explain_mode()

    console.print("\n" + "=" * 80, style="bold green")
    console.print("ALL TESTS COMPLETED", style="bold green")
    console.print("=" * 80 + "\n", style="bold green")


if __name__ == "__main__":
    main()
