#!/usr/bin/env python3
"""
Extract high-quality training samples from production rules.

This script extracts examples from YAML rules in /rulepacks/core_v1.1.0/
and creates weighted training samples with full metadata.

Output: data/rule_examples.jsonl

Each sample includes:
- text: The example text
- label: 1 (malicious) or 0 (benign)
- family: Threat family (CMD, PI, JB, PII, etc.)
- sub_family: Specific sub-category
- rule_id: Source rule ID
- confidence: Rule confidence score (0.90-0.99)
- source: "rule_example"
- weight_multiplier: 3.0 (higher priority than legacy data)
- severity: critical, high, medium, low
"""

import yaml
from pathlib import Path
from typing import List, Dict
import json
from collections import Counter


def extract_rule_examples(rule_path: Path) -> List[Dict]:
    """Extract examples from a single rule file."""
    with open(rule_path) as f:
        rule = yaml.safe_load(f)

    samples = []

    # Positive examples (should_match = malicious)
    for text in rule['examples'].get('should_match', []):
        samples.append({
            'text': text,
            'label': 1,  # Malicious
            'family': rule['family'],
            'sub_family': rule.get('sub_family', ''),
            'rule_id': rule['rule_id'],
            'confidence': rule['confidence'],
            'source': 'rule_example',
            'weight_multiplier': 3.0,  # Higher weight for expert examples
            'severity': rule['severity'],
        })

    # Negative examples (should_not_match = benign)
    for text in rule['examples'].get('should_not_match', []):
        samples.append({
            'text': text,
            'label': 0,  # Benign
            'family': rule['family'],  # Still tag with family for context
            'sub_family': rule.get('sub_family', ''),
            'rule_id': rule['rule_id'],
            'confidence': rule['confidence'],
            'source': 'rule_example',
            'weight_multiplier': 3.0,  # Negatives are equally important!
            'severity': 'info',  # Benign samples get 'info' severity
        })

    return samples


def main():
    """Extract all rule examples from production rulepacks."""
    rulepacks_dir = Path(__file__).parent.parent / "rulepacks" / "core_v1.1.0"
    output_file = Path(__file__).parent.parent / "data" / "rule_examples.jsonl"

    print("\n" + "="*60)
    print("EXTRACTING RULE EXAMPLES")
    print("="*60)
    print(f"\nSource: {rulepacks_dir}")
    print(f"Output: {output_file}")

    all_samples = []
    rule_count = 0
    errors = []

    # Iterate through all rule families
    for family_dir in sorted(rulepacks_dir.iterdir()):
        if not family_dir.is_dir():
            continue

        print(f"\nProcessing {family_dir.name.upper()} rules...")

        for rule_file in sorted(family_dir.glob("*.yaml")):
            try:
                samples = extract_rule_examples(rule_file)
                all_samples.extend(samples)
                rule_count += 1

                pos = sum(1 for s in samples if s['label'] == 1)
                neg = sum(1 for s in samples if s['label'] == 0)
                print(f"  ✓ {rule_file.name}: {len(samples)} examples ({pos} pos, {neg} neg)")

            except Exception as e:
                errors.append((rule_file.name, str(e)))
                print(f"  ✗ {rule_file.name}: {e}")

    # Create output directory
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save to JSONL
    with open(output_file, 'w', encoding='utf-8') as f:
        for sample in all_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')

    # Statistics
    print("\n" + "="*60)
    print("EXTRACTION COMPLETE")
    print("="*60)
    print(f"\nRules processed: {rule_count}")
    print(f"Total examples extracted: {len(all_samples)}")
    print(f"Output: {output_file}")

    # Label distribution
    print("\n" + "-"*60)
    print("Label Distribution:")
    print("-"*60)
    label_counts = Counter(s['label'] for s in all_samples)
    for label, count in sorted(label_counts.items()):
        label_name = "Benign" if label == 0 else "Malicious"
        pct = count / len(all_samples) * 100
        print(f"  {label_name} ({label}): {count} ({pct:.1f}%)")

    # Family distribution
    print("\n" + "-"*60)
    print("Family Distribution:")
    print("-"*60)
    family_counts = Counter(s['family'] for s in all_samples)
    for family, count in sorted(family_counts.items()):
        pct = count / len(all_samples) * 100
        print(f"  {family}: {count} ({pct:.1f}%)")

    # Severity distribution (malicious only)
    print("\n" + "-"*60)
    print("Severity Distribution (Malicious Samples):")
    print("-"*60)
    malicious = [s for s in all_samples if s['label'] == 1]
    severity_counts = Counter(s['severity'] for s in malicious)
    for severity, count in sorted(severity_counts.items(),
                                   key=lambda x: {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}.get(x[0], 4)):
        pct = count / len(malicious) * 100 if malicious else 0
        print(f"  {severity}: {count} ({pct:.1f}%)")

    # Confidence distribution
    print("\n" + "-"*60)
    print("Confidence Distribution:")
    print("-"*60)
    confidences = [s['confidence'] for s in all_samples]
    print(f"  Min: {min(confidences):.2f}")
    print(f"  Max: {max(confidences):.2f}")
    print(f"  Mean: {sum(confidences)/len(confidences):.2f}")

    # Weight summary
    print("\n" + "-"*60)
    print("Weight Summary:")
    print("-"*60)
    total_weight = sum(s['weight_multiplier'] for s in all_samples)
    print(f"  All samples: weight_multiplier = 3.0")
    print(f"  Total effective weight: {total_weight}")
    print(f"  Equivalent to: {total_weight} legacy samples")

    # Errors
    if errors:
        print("\n" + "-"*60)
        print(f"Errors ({len(errors)}):")
        print("-"*60)
        for filename, error in errors:
            print(f"  ✗ {filename}: {error}")

    print("\n" + "="*60)
    print("✓ Rule examples ready for training!")
    print("="*60)
    print(f"\nNext steps:")
    print(f"  1. Review: cat {output_file} | head -20 | jq .")
    print(f"  2. Merge with legacy data using prepare_l2_training_data.py")
    print(f"  3. Train with weighted samples for better quality")


if __name__ == "__main__":
    main()
