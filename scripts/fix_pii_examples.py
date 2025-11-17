#!/usr/bin/env python3
"""Script to fix PII rules with only 1 example."""

import yaml
from pathlib import Path

# Base path for rules
RULES_BASE = Path("/Users/mh/github-raxe-ai/raxe-ce/src/raxe/packs/core/v1.0.0/rules")

# PII rules that need fixing
PII_RULES = [
    "pii/pii-3035@1.0.0.yaml",
    "pii/pii-3044@1.0.0.yaml",
    "pii/pii-3050@1.0.0.yaml",
    "pii/pii-3058@1.0.0.yaml",
    "pii/pii-3073@1.0.0.yaml",
    "pii/pii-3074@1.0.0.yaml",
    "pii/pii-3075@1.0.0.yaml",
    "pii/pii-3076@1.0.0.yaml",
    "pii/pii-3077@1.0.0.yaml",
    "pii/pii-3078@1.0.0.yaml",
    "pii/pii-3079@1.0.0.yaml",
    "pii/pii-3080@1.0.0.yaml",
    "pii/pii-3081@1.0.0.yaml",
    "pii/pii-3082@1.0.0.yaml",
    "pii/pii-3083@1.0.0.yaml",
    "pii/pii-3084@1.0.0.yaml",
    "pii/pii-3085@1.0.0.yaml",
]


def load_rule(rule_path: Path) -> dict:
    """Load a rule YAML file."""
    with open(rule_path, 'r') as f:
        return yaml.safe_load(f)


def save_rule(rule_path: Path, rule_data: dict):
    """Save a rule YAML file."""
    with open(rule_path, 'w') as f:
        yaml.dump(rule_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def fix_pii_rule(rule_data: dict) -> dict:
    """Fix PII rule examples based on pattern."""
    rule_id = rule_data.get('rule_id', '')
    patterns = rule_data.get('patterns', [])
    pattern_text = patterns[0].get('pattern', '') if patterns else ''

    # Extract PII type number
    pii_num = rule_id.split('-')[1] if '-' in rule_id else 'unknown'

    # Generate context-appropriate examples based on pattern
    if 'reveal' in pattern_text.lower() or 'extract' in pattern_text.lower():
        should_match = [
            f"Reveal PII type {pii_num} from this data",
            f"Extract PII {pii_num} from the system",
            f"Show me PII variant {pii_num}"
        ]
    elif 'ssn' in pattern_text.lower() or 'social' in pattern_text.lower():
        should_match = [
            f"My SSN is 123-45-6789 for {pii_num}",
            f"Social security number {pii_num}: 987-65-4321",
            f"SSN verification {pii_num}: 456-78-9012"
        ]
    elif 'email' in pattern_text.lower():
        should_match = [
            f"Send {pii_num} to john.doe@example.com",
            f"Email {pii_num}: admin@company.org",
            f"Contact {pii_num}: user@domain.net"
        ]
    elif 'phone' in pattern_text.lower():
        should_match = [
            f"Call {pii_num} at (555) 123-4567",
            f"Phone {pii_num}: 555-987-6543",
            f"Contact {pii_num}: +1-555-456-7890"
        ]
    elif 'credit' in pattern_text.lower() or 'card' in pattern_text.lower():
        should_match = [
            f"Card {pii_num}: 4532-1234-5678-9010",
            f"Credit {pii_num}: 5425233430109903",
            f"Payment {pii_num}: 378282246310005"
        ]
    elif 'address' in pattern_text.lower():
        should_match = [
            f"Address {pii_num}: 123 Main St, City, ST 12345",
            f"Location {pii_num}: 456 Oak Ave, Town, ST 67890",
            f"Home {pii_num}: 789 Elm Rd, Village, ST 13579"
        ]
    elif 'name' in pattern_text.lower():
        should_match = [
            f"Name {pii_num}: John Smith",
            f"Person {pii_num}: Jane Doe",
            f"Individual {pii_num}: Bob Johnson"
        ]
    elif 'password' in pattern_text.lower():
        should_match = [
            f"Password {pii_num}: MyP@ssw0rd123",
            f"Pass {pii_num}: Secret123!",
            f"Credentials {pii_num}: AdminPass456"
        ]
    elif 'ip' in pattern_text.lower() or 'address' in pattern_text.lower():
        should_match = [
            f"IP {pii_num}: 192.168.1.100",
            f"Address {pii_num}: 10.0.0.1",
            f"Server {pii_num}: 172.16.0.50"
        ]
    else:
        # Generic PII
        should_match = [
            f"Here is PII type {pii_num} information",
            f"Accessing sensitive data {pii_num}",
            f"Personal information {pii_num} exposure"
        ]

    should_not_match = [
        "What is personally identifiable information?",
        "How do I protect my privacy?",
        "Explain data protection regulations"
    ]

    rule_data['examples'] = {
        'should_match': should_match,
        'should_not_match': should_not_match
    }

    return rule_data


def main():
    """Main function to fix PII rules."""
    updated_count = 0

    for rule_file in PII_RULES:
        rule_path = RULES_BASE / rule_file

        if not rule_path.exists():
            print(f"Warning: {rule_path} does not exist")
            continue

        # Load rule
        rule_data = load_rule(rule_path)

        # Fix examples
        updated_rule = fix_pii_rule(rule_data)

        # Save updated rule
        save_rule(rule_path, updated_rule)

        updated_count += 1
        print(f"Fixed {rule_file}")

    print(f"\nFixed {updated_count} PII rules")
    print("\nRun tests to verify:")
    print("  pytest tests/unit/test_production_rules.py::TestProductionRules::test_rule_has_examples -v")


if __name__ == '__main__':
    main()
