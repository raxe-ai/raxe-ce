#!/usr/bin/env python3
"""Fix empty mitre_attack fields in YAML rule files."""

import re
from pathlib import Path

def fix_empty_mitre_attack(file_path: Path) -> bool:
    """
    Fix empty mitre_attack field in a YAML file.

    Returns True if file was modified, False otherwise.
    """
    content = file_path.read_text()

    # Pattern: mitre_attack: followed by newline and NON-list content
    # We want to match "mitre_attack:\nmetadata:" but not "mitre_attack:\n- T1234"
    pattern = r'^mitre_attack:\s*\n(?![\s]*-)'
    replacement = 'mitre_attack: []\n'

    new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    if new_content != content:
        file_path.write_text(new_content)
        return True
    return False

def main():
    """Fix all HC rules with empty mitre_attack."""
    rules_dir = Path('src/raxe/packs/core/v1.0.0/rules/hc')

    if not rules_dir.exists():
        print(f"Error: {rules_dir} does not exist")
        return

    fixed_count = 0
    for rule_file in sorted(rules_dir.glob('hc-*.yaml')):
        if fix_empty_mitre_attack(rule_file):
            print(f"Fixed: {rule_file.name}")
            fixed_count += 1

    print(f"\nTotal fixed: {fixed_count} files")

if __name__ == '__main__':
    main()
