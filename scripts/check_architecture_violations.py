#!/usr/bin/env python3
"""
Check for Clean Architecture violations.

This script scans the CLI layer for private attribute access violations
and reports them. Used to validate that Phase 4 fixes were successful.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


def check_file_for_violations(file_path: Path) -> List[Tuple[int, str]]:
    """
    Check a single file for private attribute access violations.

    Args:
        file_path: Path to the file to check

    Returns:
        List of (line_number, line_content) tuples for violations
    """
    violations = []

    with open(file_path, 'r') as f:
        for line_num, line in enumerate(f, start=1):
            # Skip comments and __special__ attributes
            if line.strip().startswith('#'):
                continue

            # Check for private attribute access patterns
            # Look for ._something but exclude .__something__
            private_access_pattern = r'\._(?!_)([a-zA-Z_][a-zA-Z0-9_]*)'

            matches = re.findall(private_access_pattern, line)
            if matches:
                # Additional check: allow explicitly marked OK lines
                if '# OK:' in line or '# ALLOW:' in line:
                    continue

                violations.append((line_num, line.rstrip()))

    return violations


def check_cli_layer() -> bool:
    """
    Check all CLI files for violations.

    Returns:
        True if no violations found, False otherwise
    """
    cli_dir = Path(__file__).parent.parent / 'src' / 'raxe' / 'cli'

    if not cli_dir.exists():
        print(f"ERROR: CLI directory not found: {cli_dir}")
        return False

    cli_files = list(cli_dir.glob('*.py'))
    if not cli_files:
        print(f"ERROR: No Python files found in {cli_dir}")
        return False

    total_violations = 0
    files_with_violations = []

    print("=" * 80)
    print("CLEAN ARCHITECTURE VIOLATION CHECK - CLI LAYER")
    print("=" * 80)
    print()

    for cli_file in sorted(cli_files):
        violations = check_file_for_violations(cli_file)

        if violations:
            total_violations += len(violations)
            files_with_violations.append(cli_file.name)

            print(f"❌ {cli_file.name}: {len(violations)} violation(s) found")
            print("-" * 80)

            for line_num, line_content in violations:
                print(f"  Line {line_num}: {line_content}")

            print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Files checked: {len(cli_files)}")
    print(f"Files with violations: {len(files_with_violations)}")
    print(f"Total violations: {total_violations}")
    print()

    if total_violations == 0:
        print("✅ SUCCESS: No private attribute access violations found!")
        print()
        print("All CLI commands are using the public API correctly.")
        return True
    else:
        print("❌ FAILURE: Private attribute access violations found!")
        print()
        print("The following files have violations:")
        for filename in files_with_violations:
            print(f"  - {filename}")
        print()
        print("Action required:")
        print("1. Replace private attribute access with public API methods")
        print("2. Add public API methods to Raxe client if needed")
        print("3. Re-run this script to verify fixes")
        return False


def check_domain_layer_purity() -> bool:
    """
    Check that domain layer has no I/O imports.

    Returns:
        True if domain layer is pure, False otherwise
    """
    domain_dir = Path(__file__).parent.parent / 'src' / 'raxe' / 'domain'

    if not domain_dir.exists():
        print(f"WARNING: Domain directory not found: {domain_dir}")
        return True  # Not a failure, domain may not exist yet

    forbidden_imports = [
        'sqlite',
        'sqlalchemy',
        'requests',
        'urllib',
        'httpx',
        'logging',  # Domain shouldn't log
        'open(',    # No file I/O
    ]

    violations = []

    for py_file in domain_dir.rglob('*.py'):
        with open(py_file, 'r') as f:
            content = f.read()

            for forbidden in forbidden_imports:
                if forbidden in content:
                    # Check if it's actually an import/usage
                    if f'import {forbidden}' in content or f'from {forbidden}' in content:
                        violations.append(f"{py_file.name}: imports {forbidden}")
                    elif forbidden == 'open(' and 'open(' in content:
                        violations.append(f"{py_file.name}: uses open() for file I/O")

    print()
    print("=" * 80)
    print("DOMAIN LAYER PURITY CHECK")
    print("=" * 80)
    print()

    if violations:
        print("❌ FAILURE: Domain layer contains I/O operations!")
        print()
        for violation in violations:
            print(f"  - {violation}")
        return False
    else:
        print("✅ SUCCESS: Domain layer is pure (no I/O imports)")
        return True


def main():
    """Main entry point."""
    print()
    print("🔍 Running Clean Architecture Compliance Checks...")
    print()

    # Check CLI layer
    cli_clean = check_cli_layer()

    # Check domain layer purity
    domain_clean = check_domain_layer_purity()

    # Overall result
    print()
    print("=" * 80)
    print("OVERALL RESULT")
    print("=" * 80)
    print()

    if cli_clean and domain_clean:
        print("✅ ALL CHECKS PASSED")
        print()
        print("Clean Architecture compliance verified!")
        sys.exit(0)
    else:
        print("❌ SOME CHECKS FAILED")
        print()
        if not cli_clean:
            print("  - CLI layer has private attribute access violations")
        if not domain_clean:
            print("  - Domain layer is not pure (contains I/O)")
        print()
        sys.exit(1)


if __name__ == '__main__':
    main()
