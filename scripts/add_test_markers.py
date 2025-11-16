#!/usr/bin/env python3
"""Add proper pytest markers to test files.

Scans all test files and adds appropriate markers:
- @pytest.mark.slow - for tests taking >1 second
- @pytest.mark.integration - for integration tests
- @pytest.mark.performance - for performance/benchmark tests
- @pytest.mark.security - for security tests
- @pytest.mark.e2e - for end-to-end tests

Usage:
    python scripts/add_test_markers.py [--dry-run]
"""
import argparse
import re
from pathlib import Path
from typing import Set


TESTS_DIR = Path(__file__).parent.parent / "tests"


MARKER_RULES = {
    # Performance markers
    "performance": {
        "paths": ["tests/performance/"],
        "patterns": [
            r"def test_.*latency",
            r"def test_.*throughput",
            r"def test_.*benchmark",
            r"def test_.*performance",
            r"benchmark\(",
        ],
    },
    # Slow markers
    "slow": {
        "patterns": [
            r"for.*range\(10000",  # Large iterations
            r"for.*range\(100000",
            r"time\.sleep\([1-9]",  # Sleep >1 second
            r"@pytest\.mark\.slow",  # Already marked
            r"def test_.*memory_leak",
            r"def test_.*large",
        ],
    },
    # Integration markers
    "integration": {
        "paths": ["tests/integration/"],
        "patterns": [
            r"preload_pipeline",
            r"from raxe\.application",
            r"def test_.*e2e",
            r"def test_.*integration",
        ],
    },
    # Security markers
    "security": {
        "paths": ["tests/security/"],
        "patterns": [
            r"def test_.*pii",
            r"def test_.*leak",
            r"def test_.*secret",
            r"def test_.*security",
        ],
    },
    # E2E markers
    "e2e": {
        "paths": ["tests/e2e/"],
        "patterns": [
            r"def test_.*journey",
            r"def test_.*workflow",
        ],
    },
}


def should_add_marker(file_path: Path, content: str, marker: str) -> bool:
    """Determine if marker should be added to file."""
    rules = MARKER_RULES.get(marker, {})

    # Check path-based rules
    for path_pattern in rules.get("paths", []):
        if path_pattern in str(file_path):
            return True

    # Check content-based rules
    for pattern in rules.get("patterns", []):
        if re.search(pattern, content, re.IGNORECASE):
            return True

    return False


def extract_existing_markers(content: str) -> Set[str]:
    """Extract existing markers from file."""
    markers = set()
    for match in re.finditer(r"@pytest\.mark\.(\w+)", content):
        markers.add(match.group(1))
    return markers


def add_markers_to_file(file_path: Path, dry_run: bool = False) -> bool:
    """Add appropriate markers to a test file."""
    content = file_path.read_text()

    # Check if file already has pytest import
    has_pytest_import = "import pytest" in content

    # Determine which markers should be added
    markers_to_add = set()
    for marker in MARKER_RULES.keys():
        if should_add_marker(file_path, content, marker):
            markers_to_add.add(marker)

    # Remove markers that are already present
    existing_markers = extract_existing_markers(content)
    new_markers = markers_to_add - existing_markers

    if not new_markers:
        return False  # No changes needed

    print(f"📝 {file_path.relative_to(TESTS_DIR)}")
    print(f"   Adding markers: {', '.join(sorted(new_markers))}")

    if dry_run:
        return False

    # Add pytest import if needed
    if not has_pytest_import and new_markers:
        # Find first import line
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                # Insert after docstring but before other imports
                lines.insert(i, 'import pytest')
                content = '\n'.join(lines)
                break

    # Add class-level markers if file has test classes
    class_pattern = r"^class (Test\w+):"
    for match in re.finditer(class_pattern, content, re.MULTILINE):
        class_name = match.group(1)
        class_line = match.group(0)

        # Check if class already has markers
        class_start = match.start()
        prev_lines = content[:class_start].split('\n')[-5:]  # Look at 5 lines before
        has_marker = any('@pytest.mark' in line for line in prev_lines)

        if not has_marker and new_markers:
            # Add markers before class
            marker_decorators = '\n'.join([f"@pytest.mark.{m}" for m in sorted(new_markers)])
            content = content[:class_start] + marker_decorators + '\n' + content[class_start:]

    # Write updated content
    file_path.write_text(content)
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Add pytest markers to test files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without modifying files")
    args = parser.parse_args()

    print("🔍 Scanning test files for marker additions...\n")

    # Find all test files
    test_files = list(TESTS_DIR.rglob("test_*.py"))

    modified_count = 0
    for test_file in sorted(test_files):
        if add_markers_to_file(test_file, dry_run=args.dry_run):
            modified_count += 1

    print(f"\n✅ {'Would modify' if args.dry_run else 'Modified'} {modified_count}/{len(test_files)} test files")

    if args.dry_run:
        print("\nRun without --dry-run to apply changes")


if __name__ == "__main__":
    main()
