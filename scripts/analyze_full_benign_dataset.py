#!/usr/bin/env python3
"""Analyze false positive rate on full 100K benign dataset.

This script scans all 100,000 benign prompts to:
1. Calculate overall false positive rate (L1 and L2 separately)
2. Identify which rules/models are triggering false positives
3. Show examples of false positive detections
4. Generate detailed report

Usage:
    python scripts/analyze_full_benign_dataset.py [--limit N]

Options:
    --limit N    Only analyze first N samples (for testing)
"""
import argparse
import json
import time
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Any

from raxe.application.preloader import preload_pipeline
from raxe.infrastructure.config.scan_config import ScanConfig


BENIGN_DATA_FILE = Path(__file__).parent.parent / "data" / "benign_prompts.jsonl"


def load_benign_samples(limit: int | None = None) -> List[Dict[str, Any]]:
    """Load benign samples from dataset.

    Args:
        limit: Maximum number of samples to load (None = all)

    Returns:
        List of benign samples
    """
    samples = []
    with open(BENIGN_DATA_FILE) as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            samples.append(json.loads(line))

    return samples


def main():
    """Analyze false positive rate on full benign dataset."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Analyze false positive rate on benign dataset")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of samples to analyze")
    args = parser.parse_args()

    print("🔍 Analyzing False Positive Rate on Benign Dataset")
    print("=" * 70)

    # Load pipeline
    print("\n📊 Loading scan pipeline...")
    config = ScanConfig(
        enable_l2=True,
        fail_fast_on_critical=False,
        min_confidence_for_skip=1.0,  # Never skip L2
    )
    pipeline, metadata = preload_pipeline(config=config)
    print(f"✓ Pipeline loaded with {len(pipeline.pack_registry.packs)} packs")

    # Load benign samples
    print(f"\n📂 Loading benign samples from: {BENIGN_DATA_FILE}")
    samples = load_benign_samples(limit=args.limit)
    if args.limit:
        print(f"✓ Loaded {len(samples):,} benign samples (limited to {args.limit:,})")
    else:
        print(f"✓ Loaded {len(samples):,} benign samples")

    # Scan all samples
    print(f"\n🔬 Scanning {len(samples):,} samples...")
    print("This may take a few minutes...")

    # L1-specific tracking
    false_positives = []
    false_positive_by_rule = Counter()
    false_positive_by_family = Counter()
    false_positive_by_severity = Counter()
    false_positive_examples = defaultdict(list)

    # L2-specific tracking
    l2_false_positives = []
    l2_false_positive_by_threat_type = Counter()
    l2_false_positive_by_family = Counter()
    l2_false_positive_examples = defaultdict(list)

    start_time = time.time()
    batch_size = 10000

    for i, sample in enumerate(samples):
        # Progress indicator
        if (i + 1) % batch_size == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            remaining = (len(samples) - i - 1) / rate
            print(f"  Progress: {i+1:,}/{len(samples):,} ({(i+1)/len(samples)*100:.1f}%) | "
                  f"Rate: {rate:.0f} scans/sec | ETA: {remaining:.0f}s")

        prompt = sample.get("prompt", "")
        result = pipeline.scan(prompt)

        # Check for L1 false positives (rule-based detections on benign)
        if result.scan_result.l1_result.has_detections:
            false_positives.append({
                "sample_id": sample.get("id", "unknown"),
                "prompt": prompt[:200],  # Truncate for display
                "category": sample.get("category", "unknown"),
                "detections": [
                    {
                        "rule_id": d.rule_id,
                        "severity": d.severity.value,
                        "confidence": d.confidence,
                    }
                    for d in result.scan_result.l1_result.detections
                ]
            })

            # Track L1 statistics
            for detection in result.scan_result.l1_result.detections:
                rule_id = detection.rule_id
                family = rule_id.split('-')[0].upper()
                severity = detection.severity.value

                false_positive_by_rule[rule_id] += 1
                false_positive_by_family[family] += 1
                false_positive_by_severity[severity] += 1

                # Keep examples (max 3 per rule)
                if len(false_positive_examples[rule_id]) < 3:
                    false_positive_examples[rule_id].append(prompt[:150])

        # Check for L2 false positives (ML predictions on benign)
        if result.scan_result.l2_result.has_predictions:
            l2_false_positives.append({
                "sample_id": sample.get("id", "unknown"),
                "prompt": prompt[:200],
                "category": sample.get("category", "unknown"),
                "predictions": [
                    {
                        "threat_type": pred.threat_type.value,
                        "confidence": pred.confidence,
                        "family": pred.metadata.get('family', 'unknown'),
                        "sub_family": pred.metadata.get('sub_family', 'unknown'),
                    }
                    for pred in result.scan_result.l2_result.predictions
                ]
            })

            # Track L2 statistics
            for pred in result.scan_result.l2_result.predictions:
                threat_type = pred.threat_type.value
                family = pred.metadata.get('family', 'UNKNOWN')

                l2_false_positive_by_threat_type[threat_type] += 1
                l2_false_positive_by_family[family] += 1

                # Keep examples (max 3 per threat type)
                if len(l2_false_positive_examples[threat_type]) < 3:
                    l2_false_positive_examples[threat_type].append(prompt[:150])

    total_time = time.time() - start_time

    # Calculate metrics
    l1_fp_count = len(false_positives)
    l1_fp_rate = (l1_fp_count / len(samples)) * 100
    l2_fp_count = len(l2_false_positives)
    l2_fp_rate = (l2_fp_count / len(samples)) * 100
    combined_fp_rate = ((l1_fp_count + l2_fp_count) / len(samples)) * 100
    avg_rate = len(samples) / total_time

    # Print results
    print(f"\n{'=' * 70}")
    print("📊 RESULTS")
    print(f"{'=' * 70}")

    print(f"\n🎯 Overall Metrics:")
    print(f"  Total Samples Scanned: {len(samples):,}")
    print(f"\n  L1 (Rule-Based) False Positives: {l1_fp_count:,}")
    print(f"  L1 False Positive Rate: {l1_fp_rate:.4f}%")
    print(f"\n  L2 (ML-Based) False Positives: {l2_fp_count:,}")
    print(f"  L2 False Positive Rate: {l2_fp_rate:.4f}%")
    print(f"\n  Combined FP Rate: {combined_fp_rate:.4f}%")
    print(f"\n  Scan Rate: {avg_rate:.0f} scans/second")
    print(f"  Total Time: {total_time:.1f} seconds")

    # L1 False Positive Breakdown
    if l1_fp_count > 0:
        print(f"\n⚠️  L1 (RULE-BASED) FALSE POSITIVE BREAKDOWN")
        print(f"\n📋 By Rule (Top 20):")
        for rule_id, count in false_positive_by_rule.most_common(20):
            pct = (count / len(samples)) * 100
            print(f"  {rule_id}: {count:,} ({pct:.4f}%)")

        print(f"\n📂 By Family:")
        for family, count in sorted(false_positive_by_family.items()):
            pct = (count / len(samples)) * 100
            print(f"  {family}: {count:,} ({pct:.4f}%)")

        print(f"\n🎚️  By Severity:")
        for severity in ["critical", "high", "medium", "low", "info"]:
            count = false_positive_by_severity.get(severity, 0)
            if count > 0:
                pct = (count / len(samples)) * 100
                print(f"  {severity.upper()}: {count:,} ({pct:.4f}%)")

        print(f"\n📝 Example L1 False Positives (First 10):")
        for i, fp in enumerate(false_positives[:10]):
            print(f"\n  [{i+1}] ID: {fp['sample_id']} | Category: {fp['category']}")
            print(f"      Prompt: {fp['prompt']}...")
            print(f"      Detections: {', '.join(d['rule_id'] for d in fp['detections'])}")
    else:
        print(f"\n✅ L1 PERFECT! No rule-based false positives detected!")

    # L2 False Positive Breakdown
    if l2_fp_count > 0:
        print(f"\n⚠️  L2 (ML-BASED) FALSE POSITIVE BREAKDOWN")

        print(f"\n📋 By Threat Type:")
        for threat_type, count in l2_false_positive_by_threat_type.most_common():
            pct = (count / len(samples)) * 100
            print(f"  {threat_type}: {count:,} ({pct:.4f}%)")

        print(f"\n📂 By Family:")
        for family, count in sorted(l2_false_positive_by_family.items()):
            pct = (count / len(samples)) * 100
            print(f"  {family}: {count:,} ({pct:.4f}%)")

        print(f"\n📝 Example L2 False Positives (First 10):")
        for i, fp in enumerate(l2_false_positives[:10]):
            print(f"\n  [{i+1}] ID: {fp['sample_id']} | Category: {fp['category']}")
            print(f"      Prompt: {fp['prompt']}...")
            print(f"      Predictions: {', '.join(p['threat_type'] for p in fp['predictions'])}")
            confidences = ', '.join(f"{p['confidence']:.1%}" for p in fp['predictions'])
            print(f"      Confidence: {confidences}")
    else:
        print(f"\n✅ L2 PERFECT! No ML-based false positives detected!")

    if l1_fp_count == 0 and l2_fp_count == 0:
        print(f"\n✅ PERFECT! No false positives detected on {len(samples):,} benign samples!")

    print(f"\n{'=' * 70}")
    print("📊 ASSESSMENT")
    print(f"{'=' * 70}")

    # L1 Assessment
    print(f"\nL1 (Rule-Based) Assessment:")
    if l1_fp_rate < 0.1:
        print(f"  ✅ EXCELLENT: L1 FP rate < 0.1% is production-ready")
    elif l1_fp_rate < 1.0:
        print(f"  ⚠️  ACCEPTABLE: L1 FP rate < 1.0% is acceptable but could be improved")
    else:
        print(f"  ⚠️  WARNING: L1 FP rate >= 1.0% needs investigation")

    # L2 Assessment
    print(f"\nL2 (ML-Based) Assessment:")
    if l2_fp_rate < 0.1:
        print(f"  ✅ EXCELLENT: L2 FP rate < 0.1% is production-ready")
    elif l2_fp_rate < 1.0:
        print(f"  ⚠️  ACCEPTABLE: L2 FP rate < 1.0% is acceptable but could be improved")
    elif l2_fp_rate < 5.0:
        print(f"  ⚠️  WARNING: L2 FP rate < 5.0% needs investigation")
    else:
        print(f"  ❌ CRITICAL: L2 FP rate >= 5.0% requires immediate attention")

    # Combined Assessment
    print(f"\nCombined Assessment:")
    if combined_fp_rate < 0.1:
        print(f"  ✅ EXCELLENT: Combined FP rate < 0.1% is production-ready")
    elif combined_fp_rate < 1.0:
        print(f"  ⚠️  ACCEPTABLE: Combined FP rate < 1.0% is acceptable but could be improved")
    else:
        print(f"  ⚠️  WARNING: Combined FP rate >= 1.0% needs investigation")

    print(f"{'=' * 70}")

    # Save detailed report
    report_file = Path(__file__).parent.parent / "CLAUDE_WORKING_FILES" / "REPORTS" / "full_benign_fp_analysis.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "total_samples": len(samples),
        # L1 metrics
        "l1_false_positives": l1_fp_count,
        "l1_fp_rate_percent": l1_fp_rate,
        "l1_fp_by_rule": dict(false_positive_by_rule.most_common()),
        "l1_fp_by_family": dict(false_positive_by_family),
        "l1_fp_by_severity": dict(false_positive_by_severity),
        "l1_examples": false_positives[:20],
        # L2 metrics
        "l2_false_positives": l2_fp_count,
        "l2_fp_rate_percent": l2_fp_rate,
        "l2_fp_by_threat_type": dict(l2_false_positive_by_threat_type.most_common()),
        "l2_fp_by_family": dict(l2_false_positive_by_family),
        "l2_examples": l2_false_positives[:20],
        # Combined metrics
        "combined_fp_rate_percent": combined_fp_rate,
        "scan_rate_per_sec": avg_rate,
        "total_time_sec": total_time,
    }

    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n💾 Detailed report saved to: {report_file}")


if __name__ == "__main__":
    main()
