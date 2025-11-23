#!/usr/bin/env python3
"""
Generate golden file test fixtures from rule examples.

Reads all rules in registry/core/v1.0.0/rules/ and extracts
should_match/should_not_match examples into golden test fixtures.

This script creates:
- Input files (*_input.txt) containing test prompts
- Expected output files (*_expected.json) containing expected detection results

Usage:
    python scripts/generate_golden_files.py
    python scripts/generate_golden_files.py --output-dir tests/golden/fixtures_v2
    python scripts/generate_golden_files.py --dry-run  # Preview only
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


def extract_examples_from_rule(rule_path: Path) -> list[tuple[str, dict[str, Any]]]:
    """Extract test examples from a single rule file.

    Args:
        rule_path: Path to the rule YAML file

    Returns:
        List of (fixture_name, fixture_data) tuples
    """
    with open(rule_path) as f:
        rule = yaml.safe_load(f)

    fixtures = []

    # Validate required fields
    if "examples" not in rule:
        print(f"Warning: No examples found in {rule_path.name}", file=sys.stderr)
        return fixtures

    examples = rule["examples"]
    rule_id = rule["rule_id"]
    family = rule["family"]
    severity = rule["severity"]

    # Extract positive examples (should detect)
    should_match = examples.get("should_match", [])
    for i, text in enumerate(should_match, start=1):
        fixture = {
            "input": text,
            "expected": {
                "has_detections": True,
                "detection_count": 1,
                "detections": [
                    {
                        "rule_id": rule_id,
                        "family": family,
                        "severity": severity,
                    }
                ],
            },
        }
        fixture_name = f"{rule_id}_match_{i:03d}"
        fixtures.append((fixture_name, fixture))

    # Extract negative examples (should NOT detect)
    should_not_match = examples.get("should_not_match", [])
    for i, text in enumerate(should_not_match, start=1):
        fixture = {
            "input": text,
            "expected": {
                "has_detections": False,
                "detection_count": 0,
                "detections": [],
            },
        }
        fixture_name = f"{rule_id}_nomatch_{i:03d}"
        fixtures.append((fixture_name, fixture))

    return fixtures


def generate_all_golden_files(
    rulepack_dir: Path, output_dir: Path, dry_run: bool = False
) -> dict[str, int]:
    """Generate golden files from all rules in the rulepack.

    Args:
        rulepack_dir: Directory containing rule files organized by family
        output_dir: Directory to write golden file fixtures
        dry_run: If True, only preview changes without writing files

    Returns:
        Dictionary with statistics: {family: fixture_count}
    """
    stats: dict[str, int] = {}
    total_fixtures = 0

    if not rulepack_dir.exists():
        print(f"Error: Rulepack directory not found: {rulepack_dir}", file=sys.stderr)
        return stats

    # Find all family directories
    family_dirs = [d for d in rulepack_dir.iterdir() if d.is_dir() and d.name != "__pycache__"]

    if not family_dirs:
        print(f"Warning: No family directories found in {rulepack_dir}", file=sys.stderr)
        return stats

    print(f"Processing {len(family_dirs)} rule families from {rulepack_dir}")
    print()

    for family_dir in sorted(family_dirs):
        family_name = family_dir.name
        family_fixtures = 0

        # Create output directory for this family
        family_output = output_dir / family_name
        if not dry_run:
            family_output.mkdir(parents=True, exist_ok=True)

        # Process each rule file
        rule_files = list(family_dir.glob("*.yaml"))
        if not rule_files:
            print(f"Warning: No rule files found in {family_dir.name}/", file=sys.stderr)
            continue

        print(f"Family: {family_name} ({len(rule_files)} rules)")

        for rule_file in sorted(rule_files):
            try:
                fixtures = extract_examples_from_rule(rule_file)

                # Write each fixture
                for fixture_name, fixture_data in fixtures:
                    # Write input file
                    input_file = family_output / f"{fixture_name}_input.txt"
                    expected_file = family_output / f"{fixture_name}_expected.json"

                    if dry_run:
                        print(f"  [DRY RUN] Would create: {input_file.name}")
                    else:
                        input_file.write_text(fixture_data["input"])
                        expected_file.write_text(
                            json.dumps(fixture_data["expected"], indent=2)
                        )

                    family_fixtures += 1
                    total_fixtures += 1

                print(f"  {rule_file.name}: {len(fixtures)} fixtures")

            except Exception as e:
                print(
                    f"Error processing {rule_file.name}: {e}",
                    file=sys.stderr,
                )
                continue

        stats[family_name] = family_fixtures
        print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for family, count in sorted(stats.items()):
        print(f"{family:20s}: {count:4d} fixtures")
    print("-" * 60)
    print(f"{'TOTAL':20s}: {total_fixtures:4d} fixtures")
    print()

    if dry_run:
        print("[DRY RUN] No files were created. Run without --dry-run to generate.")
    else:
        print(f"Golden files written to: {output_dir}")

    return stats


def main() -> int:
    """Main entry point for the script.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Generate golden file test fixtures from rule examples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate fixtures from default registry
  python scripts/generate_golden_files.py

  # Preview what would be generated
  python scripts/generate_golden_files.py --dry-run

  # Generate to custom output directory
  python scripts/generate_golden_files.py --output-dir tests/golden/fixtures_v2

  # Use different rulepack version
  python scripts/generate_golden_files.py --rulepack registry/core/v1.1.0/rules
        """,
    )

    parser.add_argument(
        "--rulepack",
        type=Path,
        default=Path("registry/core/v1.0.0/rules"),
        help="Path to rulepack directory (default: registry/core/v1.0.0/rules)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tests/golden/fixtures"),
        help="Output directory for fixtures (default: tests/golden/fixtures)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files",
    )

    args = parser.parse_args()

    # Resolve paths
    rulepack_dir = args.rulepack.resolve()
    output_dir = args.output_dir.resolve()

    print("Golden File Generator")
    print("=" * 60)
    print(f"Rulepack directory: {rulepack_dir}")
    print(f"Output directory:   {output_dir}")
    print(f"Mode:               {'DRY RUN' if args.dry_run else 'WRITE'}")
    print()

    # Generate fixtures
    stats = generate_all_golden_files(rulepack_dir, output_dir, dry_run=args.dry_run)

    # Return success if we generated at least one fixture
    if sum(stats.values()) > 0:
        return 0
    else:
        print("Error: No fixtures were generated", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
