#!/usr/bin/env python3
"""Schema validation CLI tool.

Validates RAXE data structures against JSON schemas.
Can be run standalone or integrated into CI/CD pipeline.

Usage:
    python scripts/validate_schemas.py --all
    python scripts/validate_schemas.py --rule <rule_file>
    python scripts/validate_schemas.py --event <event_json>
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from raxe.infrastructure.schemas.validator import get_validator


def validate_rule_file(rule_path: Path) -> bool:
    """Validate a rule YAML file against schema.

    Args:
        rule_path: Path to rule YAML file

    Returns:
        True if valid, False otherwise
    """
    import yaml

    validator = get_validator()

    with open(rule_path) as f:
        rule_data = yaml.safe_load(f)

    is_valid, errors = validator.validate_rule(rule_data)

    if is_valid:
        print(f"✅ {rule_path.name} is VALID")
        return True
    else:
        print(f"❌ {rule_path.name} is INVALID")
        for error in errors:
            print(f"   - {error}")
        return False


def validate_event_json(event_path: Path) -> bool:
    """Validate a telemetry event JSON file.

    Args:
        event_path: Path to event JSON file

    Returns:
        True if valid, False otherwise
    """
    validator = get_validator()

    with open(event_path) as f:
        event_data = json.load(f)

    is_valid, errors = validator.validate_scan_event(event_data)

    if is_valid:
        print(f"✅ {event_path.name} is VALID")
        return True
    else:
        print(f"❌ {event_path.name} is INVALID")
        for error in errors:
            print(f"   - {error}")
        return False


def validate_all_fixtures() -> bool:
    """Validate all test fixtures against schemas.

    Returns:
        True if all valid, False if any invalid
    """
    validator = get_validator()
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures" / "schemas"

    if not fixtures_dir.exists():
        print(f"❌ Fixtures directory not found: {fixtures_dir}")
        return False

    all_valid = True
    fixture_files = list(fixtures_dir.glob("*.json"))

    print(f"\n📋 Validating {len(fixture_files)} fixture files...\n")

    schema_map = {
        "valid_organization.json": "v1.0.0/identity/organization.json",
        "valid_project.json": "v1.0.0/identity/project.json",
        "valid_scan_config.json": "v1.0.0/config/scan_config.json",
        "valid_usage_metrics.json": "v1.0.0/billing/usage_metrics.json",
    }

    for fixture_path in fixture_files:
        schema_path = schema_map.get(fixture_path.name)
        if not schema_path:
            print(f"⏭️  {fixture_path.name} - No schema mapping")
            continue

        with open(fixture_path) as f:
            data = json.load(f)

        is_valid, errors = validator.validate(data, schema_path, raise_on_error=False)

        if is_valid:
            print(f"✅ {fixture_path.name}")
        else:
            print(f"❌ {fixture_path.name}")
            for error in errors:
                print(f"   - {error}")
            all_valid = False

    return all_valid


def validate_all_schemas() -> bool:
    """Validate that all schema files are valid JSON Schema.

    Returns:
        True if all valid, False if any invalid
    """
    from jsonschema import Draft7Validator

    schemas_dir = Path(__file__).parent.parent / "schemas"
    schema_files = list(schemas_dir.rglob("*.json"))

    print(f"\n📋 Validating {len(schema_files)} schema files...\n")

    all_valid = True

    for schema_path in schema_files:
        try:
            with open(schema_path) as f:
                schema = json.load(f)

            # Validate the schema itself
            Draft7Validator.check_schema(schema)

            print(f"✅ {schema_path.relative_to(schemas_dir)}")

        except Exception as e:
            print(f"❌ {schema_path.relative_to(schemas_dir)}")
            print(f"   - {e}")
            all_valid = False

    return all_valid


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate RAXE data structures against JSON schemas"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all schemas and fixtures",
    )
    parser.add_argument(
        "--rule",
        type=Path,
        help="Validate a single rule YAML file",
    )
    parser.add_argument(
        "--event",
        type=Path,
        help="Validate a single event JSON file",
    )
    parser.add_argument(
        "--fixtures",
        action="store_true",
        help="Validate all test fixtures",
    )
    parser.add_argument(
        "--schemas",
        action="store_true",
        help="Validate all schema files",
    )

    args = parser.parse_args()

    if not any([args.all, args.rule, args.event, args.fixtures, args.schemas]):
        parser.print_help()
        return 1

    success = True

    if args.all or args.schemas:
        print("\n" + "=" * 60)
        print("VALIDATING SCHEMA FILES")
        print("=" * 60)
        success = validate_all_schemas() and success

    if args.all or args.fixtures:
        print("\n" + "=" * 60)
        print("VALIDATING TEST FIXTURES")
        print("=" * 60)
        success = validate_all_fixtures() and success

    if args.rule:
        if not args.rule.exists():
            print(f"❌ Rule file not found: {args.rule}")
            return 1
        success = validate_rule_file(args.rule) and success

    if args.event:
        if not args.event.exists():
            print(f"❌ Event file not found: {args.event}")
            return 1
        success = validate_event_json(args.event) and success

    # Print summary
    print("\n" + "=" * 60)
    if success:
        print("✅ ALL VALIDATIONS PASSED")
        print("=" * 60)
        return 0
    else:
        print("❌ SOME VALIDATIONS FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
