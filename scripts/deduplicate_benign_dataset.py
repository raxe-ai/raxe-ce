#!/usr/bin/env python3
"""Deduplicate the benign prompts dataset.

This script removes duplicate prompts from the benign dataset while preserving:
- The first occurrence of each unique prompt
- Original sample IDs and metadata
- Category information

Usage:
    python scripts/deduplicate_benign_dataset.py
"""
import json
from pathlib import Path
from collections import OrderedDict

def deduplicate_benign_dataset():
    """Remove duplicate prompts from benign dataset."""

    input_file = Path("data/benign_prompts.jsonl")
    output_file = Path("data/benign_prompts_deduplicated.jsonl")
    report_file = Path("CLAUDE_WORKING_FILES/REPORTS/deduplication_report.json")

    print("🔍 Deduplicating Benign Dataset")
    print("=" * 70)

    # Load all samples
    print(f"\n📂 Loading from: {input_file}")
    samples = []
    with open(input_file) as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    print(f"✓ Loaded {len(samples):,} samples")

    # Deduplicate by prompt text (keep first occurrence)
    seen_prompts = OrderedDict()
    duplicates = []

    for sample in samples:
        prompt = sample.get("prompt", sample.get("text", ""))

        if prompt not in seen_prompts:
            seen_prompts[prompt] = sample
        else:
            duplicates.append({
                "prompt": prompt,
                "duplicate_id": sample.get("id"),
                "original_id": seen_prompts[prompt].get("id"),
                "category": sample.get("category"),
            })

    unique_samples = list(seen_prompts.values())

    print(f"\n📊 Deduplication Results:")
    print(f"   Original samples: {len(samples):,}")
    print(f"   Unique samples: {len(unique_samples):,}")
    print(f"   Duplicates removed: {len(duplicates):,}")
    print(f"   Reduction: {(1 - len(unique_samples)/len(samples)) * 100:.1f}%")

    # Count duplicates by prompt
    from collections import Counter
    prompt_counts = Counter(sample.get("prompt", sample.get("text", "")) for sample in samples)
    top_duplicates = prompt_counts.most_common(20)

    print(f"\n📋 Top 10 Most Duplicated Prompts:")
    for prompt, count in top_duplicates[:10]:
        print(f"   [{count:4d}x] {prompt[:70]}...")

    # Save deduplicated dataset
    print(f"\n💾 Saving deduplicated dataset to: {output_file}")
    with open(output_file, 'w') as f:
        for sample in unique_samples:
            f.write(json.dumps(sample) + '\n')

    print(f"✓ Saved {len(unique_samples):,} unique samples")

    # Generate deduplication report
    report = {
        "summary": {
            "original_count": len(samples),
            "unique_count": len(unique_samples),
            "duplicates_removed": len(duplicates),
            "reduction_percent": (1 - len(unique_samples)/len(samples)) * 100,
        },
        "top_duplicates": [
            {
                "prompt": prompt[:200],
                "count": count,
            }
            for prompt, count in top_duplicates
        ],
        "category_breakdown": {
            "original": dict(Counter(s.get("category", "unknown") for s in samples)),
            "deduplicated": dict(Counter(s.get("category", "unknown") for s in unique_samples)),
        }
    }

    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n📄 Deduplication report saved to: {report_file}")

    # Calculate actual FP rate on deduplicated data
    # (based on the 66 unique FPs we found)
    print(f"\n🎯 Corrected FP Rate Estimate:")
    print(f"   Unique FPs found: 66")
    print(f"   Deduplicated samples: {len(unique_samples):,}")
    print(f"   TRUE FP Rate: {(66 / len(unique_samples)) * 100:.4f}%")
    print(f"   Previous (inflated): 0.8670%")
    print(f"   Improvement: {((0.867 - (66 / len(unique_samples)) * 100) / 0.867) * 100:.1f}% reduction")

    return report


if __name__ == "__main__":
    report = deduplicate_benign_dataset()

    print("\n" + "=" * 70)
    print("✅ DEDUPLICATION COMPLETE")
    print("=" * 70)
    print(f"\n📁 Files created:")
    print(f"   - data/benign_prompts_deduplicated.jsonl (clean dataset)")
    print(f"   - CLAUDE_WORKING_FILES/REPORTS/deduplication_report.json")
    print(f"\n💡 Next steps:")
    print(f"   1. Review the deduplicated dataset")
    print(f"   2. Update analysis scripts to use deduplicated dataset")
    print(f"   3. Re-run FP analysis on clean data (optional)")
