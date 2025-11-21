#!/usr/bin/env python3
"""
Test script to evaluate benign prompts against RAXE scanner.
Reports false positives (FP) and true positives (TP).
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from raxe.sdk.client import Raxe


def load_benign_prompts(file_path: Path) -> List[Dict]:
    """Load benign prompts from JSONL file."""
    prompts = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                prompts.append(json.loads(line))
    return prompts


def test_prompts(prompts: List[Dict], batch_size: int = 100) -> Dict:
    """Test prompts against RAXE scanner."""
    # Initialize RAXE client with telemetry disabled for testing
    raxe = Raxe(telemetry=False, l2_enabled=True)

    results = {
        'total': len(prompts),
        'false_positives': 0,  # Benign prompts flagged as threats
        'true_negatives': 0,   # Benign prompts correctly identified as safe
        'fp_details': [],
        'categories': {}
    }

    print(f"Testing {len(prompts)} benign prompts...")
    print(f"Progress: ", end='', flush=True)

    for i, item in enumerate(prompts):
        # Progress indicator
        if (i + 1) % 1000 == 0:
            print(f"{i+1}...", end='', flush=True)

        prompt_id = item.get('id', f'unknown-{i}')
        prompt = item.get('prompt', '')
        category = item.get('category', 'unknown')

        # Track category stats
        if category not in results['categories']:
            results['categories'][category] = {'total': 0, 'fp': 0}
        results['categories'][category]['total'] += 1

        # Scan the prompt
        scan_result = raxe.scan(prompt)

        # Check if any threats were detected
        if scan_result.has_threats:
            # False positive: benign prompt flagged as threat
            results['false_positives'] += 1
            results['categories'][category]['fp'] += 1

            # Collect details for analysis (from L1 and L2)
            threat_details = []

            # Add L1 detections
            for d in scan_result.scan_result.l1_detections:
                threat_details.append({
                    'rule_id': d.rule_id,
                    'severity': d.severity.value,
                    'confidence': d.confidence,
                    'layer': 'L1'
                })

            # Add L2 predictions if available
            if scan_result.scan_result.l2_result:
                for p in scan_result.scan_result.l2_predictions:
                    threat_details.append({
                        'rule_id': p.threat_type.value,
                        'severity': 'ML_DETECTED',
                        'confidence': p.confidence,
                        'layer': 'L2'
                    })

            results['fp_details'].append({
                'id': prompt_id,
                'prompt': prompt[:100] + '...' if len(prompt) > 100 else prompt,
                'category': category,
                'threats': threat_details
            })
        else:
            # True negative: benign prompt correctly identified as safe
            results['true_negatives'] += 1

    print(" Done!")
    return results


def print_results(results: Dict):
    """Print test results in a formatted way."""
    print("\n" + "="*70)
    print("BENIGN PROMPTS TEST RESULTS")
    print("="*70)

    total = results['total']
    fp = results['false_positives']
    tn = results['true_negatives']

    print(f"\nTotal benign prompts tested: {total:,}")
    print(f"True Negatives (correctly safe): {tn:,} ({tn/total*100:.2f}%)")
    print(f"False Positives (incorrectly flagged): {fp:,} ({fp/total*100:.2f}%)")

    print("\n" + "-"*70)
    print("FALSE POSITIVE RATE BY CATEGORY")
    print("-"*70)

    for category, stats in sorted(results['categories'].items()):
        fp_rate = (stats['fp'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"{category:30s}: {stats['fp']:5d}/{stats['total']:5d} ({fp_rate:6.2f}% FP)")

    if results['fp_details']:
        print("\n" + "-"*70)
        print(f"SAMPLE FALSE POSITIVES (showing first 10 of {len(results['fp_details'])})")
        print("-"*70)

        for fp_item in results['fp_details'][:10]:
            print(f"\nID: {fp_item['id']}")
            print(f"Category: {fp_item['category']}")
            print(f"Prompt: {fp_item['prompt']}")
            print(f"Detected threats:")
            for threat in fp_item['threats']:
                print(f"  - [{threat['layer']}] {threat['rule_id']}: {threat['severity']} (conf: {threat['confidence']:.2f})")

    print("\n" + "="*70)


def save_detailed_results(results: Dict, output_file: Path):
    """Save detailed results to JSON file."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed results saved to: {output_file}")


def main():
    """Main execution function."""
    script_dir = Path(__file__).parent
    input_file = script_dir / "benign_prompts.jsonl"
    output_file = script_dir / "benign_test_results.json"

    if not input_file.exists():
        print(f"Error: {input_file} not found!")
        sys.exit(1)

    # Load prompts
    print(f"Loading prompts from {input_file}...")
    prompts = load_benign_prompts(input_file)
    print(f"Loaded {len(prompts):,} prompts")

    # Test prompts
    results = test_prompts(prompts)

    # Print results
    print_results(results)

    # Save detailed results
    save_detailed_results(results, output_file)


if __name__ == "__main__":
    main()
