"""
Golden file regression tests.

Automatically discovers and runs all golden file test fixtures.
These tests ensure detection logic doesn't change unexpectedly.

When detection logic changes intentionally, update golden files with:
    pytest tests/golden/ --update-golden

Directory structure:
    tests/golden/fixtures/
        CMD/
            cmd-001_match_001_input.txt
            cmd-001_match_001_expected.json
            cmd-001_nomatch_001_input.txt
            cmd-001_nomatch_001_expected.json
        PI/
            pi-001_match_001_input.txt
            pi-001_match_001_expected.json
            ...
"""

import json
from pathlib import Path
from typing import Any

import pytest

from raxe.sdk.client import Raxe

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def discover_golden_files() -> list[dict[str, Any]]:
    """Automatically discover all golden file test cases.

    Searches for all *_input.txt files in fixtures directory and
    pairs them with corresponding *_expected.json files.

    Returns:
        List of test case dictionaries with metadata
    """
    test_cases = []

    if not FIXTURES_DIR.exists():
        return test_cases

    # Find all input files recursively
    for input_file in sorted(FIXTURES_DIR.rglob("*_input.txt")):
        # Expected file should be in same directory
        expected_file = input_file.parent / input_file.name.replace("_input.txt", "_expected.json")

        if expected_file.exists():
            # Extract metadata from path
            family = input_file.parent.name
            test_name = input_file.stem.replace("_input", "")

            test_cases.append(
                {
                    "name": test_name,
                    "family": family,
                    "input_file": input_file,
                    "expected_file": expected_file,
                }
            )

    return test_cases


# Generate test cases for parameterization
_discovered_test_cases = discover_golden_files()


@pytest.mark.parametrize(
    "test_case",
    _discovered_test_cases,
    ids=lambda tc: f"{tc['family']}/{tc['name']}",
)
def test_golden_file(test_case: dict[str, Any], request: pytest.FixtureRequest) -> None:
    """Test a single golden file case.

    Compares actual detection output against expected output.
    If --update-golden flag is set, updates expected files instead of asserting.

    Args:
        test_case: Test case metadata dictionary
        request: pytest fixture request (provides access to config)
    """
    # Check if we're in update mode
    update_golden = request.config.getoption("--update-golden", default=False)

    # Load input and expected output
    input_text = test_case["input_file"].read_text()

    # Run scan
    raxe = Raxe()
    result = raxe.scan(input_text)

    # Build actual output in comparable format
    # result is ScanPipelineResult > scan_result (CombinedScanResult) > l1_result (ScanResult)
    l1_result = result.scan_result.l1_result
    actual = {
        "has_detections": l1_result.has_detections,
        "detection_count": len(l1_result.detections),
        "detections": [
            {
                "rule_id": d.rule_id,
                "severity": d.severity.value,
                "confidence": d.confidence,
            }
            for d in sorted(l1_result.detections, key=lambda x: x.rule_id)
        ],
    }

    # Update mode: write new expected output and skip test
    if update_golden:
        test_case["expected_file"].write_text(json.dumps(actual, indent=2))
        pytest.skip(f"Updated golden file: {test_case['expected_file'].name}")
        return

    # Normal mode: compare against expected output
    expected = json.loads(test_case["expected_file"].read_text())

    # Compare with detailed error message
    if actual != expected:
        # Create readable diff
        error_msg = [
            f"\nGolden file mismatch for: {test_case['name']}",
            f"Family: {test_case['family']}",
            f"Input: {input_text[:100]}{'...' if len(input_text) > 100 else ''}",
            "",
            "Expected:",
            json.dumps(expected, indent=2),
            "",
            "Actual:",
            json.dumps(actual, indent=2),
            "",
            "To update this golden file, run:",
            f"  pytest tests/golden/ --update-golden -k '{test_case['name']}'",
            "",
            "To update all golden files, run:",
            "  pytest tests/golden/ --update-golden",
        ]
        pytest.fail("\n".join(error_msg))


def test_golden_file_count() -> None:
    """Verify we have a reasonable number of golden file test cases.

    This test ensures the golden file generation script is working
    and that we have adequate test coverage.
    """
    test_cases = discover_golden_files()

    # We should have at least some test cases
    # This will scale as more rules are added
    assert len(test_cases) >= 5, (
        f"Expected at least 5 golden file test cases, found {len(test_cases)}. "
        f"Run: python scripts/generate_golden_files.py"
    )


def test_golden_fixtures_structure() -> None:
    """Verify golden file fixtures follow expected structure.

    Each input file should have a corresponding expected file.
    Each expected file should contain valid JSON with required fields.
    """
    test_cases = discover_golden_files()

    if not test_cases:
        pytest.skip("No golden file fixtures found")

    errors = []

    for tc in test_cases:
        # Check input file exists and is not empty
        if not tc["input_file"].exists():
            errors.append(f"Missing input file: {tc['input_file']}")
            continue

        input_content = tc["input_file"].read_text()
        if not input_content.strip():
            errors.append(f"Empty input file: {tc['input_file']}")

        # Check expected file exists and is valid JSON
        if not tc["expected_file"].exists():
            errors.append(f"Missing expected file: {tc['expected_file']}")
            continue

        try:
            expected = json.loads(tc["expected_file"].read_text())
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in {tc['expected_file']}: {e}")
            continue

        # Validate expected structure
        required_fields = ["has_detections", "detection_count", "detections"]
        for field in required_fields:
            if field not in expected:
                errors.append(f"Missing required field '{field}' in {tc['expected_file']}")

        # Validate detection structure
        for detection in expected.get("detections", []):
            detection_fields = ["rule_id", "severity", "confidence"]
            for field in detection_fields:
                if field not in detection:
                    errors.append(f"Missing detection field '{field}' in {tc['expected_file']}")

    if errors:
        pytest.fail("Golden file structure validation failed:\n" + "\n".join(errors))
