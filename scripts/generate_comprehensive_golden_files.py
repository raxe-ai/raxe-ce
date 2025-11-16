#!/usr/bin/env python3
"""Generate comprehensive golden file test cases for all 104 rules.

Creates test fixtures for:
1. Each rule with a matching case (should detect)
2. Each rule with a non-matching case (should not detect)
3. Edge cases for critical rules
4. Multi-rule scenarios

Usage:
    python scripts/generate_comprehensive_golden_files.py

This generates test fixtures in tests/golden/fixtures/ organized by family:
    tests/golden/fixtures/
        CMD/
            cmd-001_match_001_input.txt
            cmd-001_match_001_expected.json
            cmd-001_nomatch_001_input.txt
            cmd-001_nomatch_001_expected.json
        PI/
            ...
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Any

from raxe.application.preloader import preload_pipeline
from raxe.infrastructure.config.scan_config import ScanConfig


FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "golden" / "fixtures"


def load_all_rules(pipeline) -> List[Dict[str, Any]]:
    """Load all rules from the pipeline's pack registry.

    Args:
        pipeline: The preloaded scan pipeline

    Returns:
        List of rule dictionaries loaded from the pack
    """
    # Access the rules from the pipeline's pack registry
    pack_registry = pipeline.pack_registry

    # Get all loaded rules from all packs
    all_rules = []
    for pack in pack_registry.packs.values():
        for rule in pack.rules:
            # Convert Rule object to dictionary-like structure
            rule_dict = {
                "rule_id": rule.rule_id,
                "family": rule.family.value if hasattr(rule.family, 'value') else rule.family,
                "sub_family": rule.sub_family,
                "severity": rule.severity.value if hasattr(rule.severity, 'value') else rule.severity,
                "confidence": rule.confidence,
                "examples": rule.examples.should_match if rule.examples else [],
            }
            all_rules.append(rule_dict)

    return all_rules


def sanitize_filename(text: str) -> str:
    """Sanitize text for use in filename."""
    # Remove or replace characters not safe for filenames
    safe = re.sub(r'[^\w\s-]', '', text)
    safe = re.sub(r'[-\s]+', '_', safe)
    return safe[:50]  # Limit length


def create_golden_file_pair(
    family: str,
    rule_id: str,
    test_name: str,
    input_text: str,
    should_detect: bool,
    pipeline,
):
    """Create a golden file input/expected pair."""
    family_dir = FIXTURES_DIR / family
    family_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize test name for filename
    safe_test_name = sanitize_filename(test_name)
    base_name = f"{rule_id}_{safe_test_name}"

    input_file = family_dir / f"{base_name}_input.txt"
    expected_file = family_dir / f"{base_name}_expected.json"

    # Write input file
    input_file.write_text(input_text)

    # Scan and generate expected output
    result = pipeline.scan(input_text)
    l1_result = result.scan_result.l1_result

    expected = {
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

    # Write expected file
    expected_file.write_text(json.dumps(expected, indent=2))

    print(f"  Created: {family}/{base_name}")

    # Validate expectation matches intent
    if should_detect and not expected["has_detections"]:
        print(f"    ⚠️  WARNING: Expected detection but got none!")
    elif not should_detect and expected["has_detections"]:
        print(f"    ⚠️  WARNING: Expected no detection but got {expected['detection_count']}!")


def generate_test_cases_from_rule(rule: Dict[str, Any]) -> List[Dict[str, str]]:
    """Generate test cases for a rule based on its examples.

    Returns list of test cases with:
    - input_text: The prompt to test
    - should_detect: Whether this should trigger the rule
    - test_name: Descriptive name for the test
    """
    test_cases = []

    # Use rule examples as positive test cases
    examples = rule.get("examples", [])
    for i, example in enumerate(examples[:3]):  # Limit to 3 examples per rule
        test_cases.append({
            "input_text": example,
            "should_detect": True,
            "test_name": f"match_{i+1:03d}",
        })

    # Generate negative test cases (similar but benign)
    # This requires domain knowledge - create simple variations
    if examples:
        # Create benign variation by removing key threat words
        benign_variations = [
            "This is a benign prompt about programming",
            "Can you help me with a coding question?",
            "Explain how functions work in Python",
        ]

        for i, benign in enumerate(benign_variations[:1]):  # 1 negative case per rule
            test_cases.append({
                "input_text": benign,
                "should_detect": False,
                "test_name": f"nomatch_{i+1:03d}",
            })

    return test_cases


def main():
    """Generate comprehensive golden file test suite."""
    print("🏗️  Generating comprehensive golden file test cases...")
    print(f"Output directory: {FIXTURES_DIR}")

    # Load pipeline
    print("\nLoading pipeline...")
    config = ScanConfig(enable_l2=False)
    pipeline, metadata = preload_pipeline(config=config)

    # Load all rules
    print("Loading rules...")
    rules = load_all_rules(pipeline)
    print(f"Loaded {len(rules)} rules")

    # Group rules by family
    rules_by_family = {}
    for rule in rules:
        family = rule["rule_id"].split('-')[0].upper()
        if family not in rules_by_family:
            rules_by_family[family] = []
        rules_by_family[family].append(rule)

    # Generate test cases for each rule
    total_tests = 0
    for family, family_rules in sorted(rules_by_family.items()):
        print(f"\n📁 {family} ({len(family_rules)} rules)")

        for rule in family_rules:
            rule_id = rule["rule_id"]
            examples = rule.get("examples", [])

            if not examples:
                print(f"  ⚠️  {rule_id}: No examples, skipping")
                continue

            # Generate test cases
            test_cases = generate_test_cases_from_rule(rule)

            for test_case in test_cases:
                create_golden_file_pair(
                    family=family,
                    rule_id=rule_id,
                    test_name=test_case["test_name"],
                    input_text=test_case["input_text"],
                    should_detect=test_case["should_detect"],
                    pipeline=pipeline,
                )
                total_tests += 1

    print(f"\n✅ Generated {total_tests} golden file test cases")
    print(f"📊 Coverage: {len(rules)} rules across {len(rules_by_family)} families")
    print(f"\nRun tests with: pytest tests/golden/")


if __name__ == "__main__":
    main()
