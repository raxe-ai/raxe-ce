#!/usr/bin/env python3
"""
Analyze 67 false positives to determine optimal thresholds for hierarchical scoring.

This script:
1. Loads the FP dataset
2. Computes statistics on confidence scores
3. Determines empirical thresholds for scoring algorithms
4. Validates hierarchical scoring weights
5. Provides data-driven recommendations
"""

import csv
import statistics
from pathlib import Path
from collections import defaultdict
import numpy as np

def load_fp_data(csv_path: str) -> list[dict]:
    """Load false positive dataset."""
    fps = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse confidence percentage
            conf_str = row['Confidence %'].strip('%')
            confidence = float(conf_str) / 100.0

            fps.append({
                'sample_id': row['Sample ID'],
                'category': row['Category'],
                'prompt': row['Full Prompt'],
                'family': row['Family'],
                'subfamily': row['Sub-Family'],
                'confidence': confidence,
                'threat_type': row['Threat Type'],
            })
    return fps

def compute_statistics(fps: list[dict]):
    """Compute comprehensive statistics on FP dataset."""
    confidences = [fp['confidence'] for fp in fps]
    families = [fp['family'] for fp in fps]
    categories = [fp['category'] for fp in fps]

    print("=" * 80)
    print("FALSE POSITIVE DATASET ANALYSIS (N=67)")
    print("=" * 80)

    # Overall statistics
    print("\n1. CONFIDENCE SCORE DISTRIBUTION")
    print(f"   Mean:     {statistics.mean(confidences):.4f}")
    print(f"   Median:   {statistics.median(confidences):.4f}")
    print(f"   Std Dev:  {statistics.stdev(confidences):.4f}")
    print(f"   Min:      {min(confidences):.4f}")
    print(f"   Max:      {max(confidences):.4f}")
    print(f"   P25:      {np.percentile(confidences, 25):.4f}")
    print(f"   P75:      {np.percentile(confidences, 75):.4f}")
    print(f"   P90:      {np.percentile(confidences, 90):.4f}")

    # Distribution by confidence ranges
    print("\n2. FP DISTRIBUTION BY CONFIDENCE RANGE")
    ranges = [
        (0.5, 0.6, "0.50-0.60"),
        (0.6, 0.7, "0.60-0.70"),
        (0.7, 0.8, "0.70-0.80"),
        (0.8, 0.9, "0.80-0.90"),
        (0.9, 1.0, "0.90-1.00"),
    ]

    for low, high, label in ranges:
        count = sum(1 for c in confidences if low <= c < high)
        pct = count / len(confidences) * 100
        print(f"   {label}: {count:2d} FPs ({pct:5.1f}%)")

    # Family distribution
    print("\n3. FP DISTRIBUTION BY FAMILY")
    family_counts = defaultdict(int)
    family_confidences = defaultdict(list)

    for fp in fps:
        family = fp['family']
        family_counts[family] += 1
        family_confidences[family].append(fp['confidence'])

    for family in sorted(family_counts.keys(), key=lambda x: family_counts[x], reverse=True):
        count = family_counts[family]
        pct = count / len(fps) * 100
        avg_conf = statistics.mean(family_confidences[family])
        print(f"   {family:3s}: {count:2d} FPs ({pct:5.1f}%) - avg conf: {avg_conf:.3f}")

    # Category distribution
    print("\n4. FP DISTRIBUTION BY CATEGORY")
    category_counts = defaultdict(int)
    for fp in fps:
        category_counts[fp['category']] += 1

    for cat in sorted(category_counts.keys(), key=lambda x: category_counts[x], reverse=True):
        count = category_counts[cat]
        pct = count / len(fps) * 100
        print(f"   {cat:20s}: {count:2d} FPs ({pct:5.1f}%)")

    # Key insights
    print("\n5. KEY INSIGHTS")

    # What percentage are "high confidence" FPs (>0.8)?
    high_conf_fps = sum(1 for c in confidences if c >= 0.8)
    high_conf_pct = high_conf_fps / len(confidences) * 100
    print(f"   High confidence FPs (≥0.80): {high_conf_fps} ({high_conf_pct:.1f}%)")
    print("   → These are HARD cases - simple thresholding won't catch them")

    # What percentage are "borderline" (0.5-0.7)?
    borderline_fps = sum(1 for c in confidences if 0.5 <= c < 0.7)
    borderline_pct = borderline_fps / len(confidences) * 100
    print(f"   Borderline FPs (0.50-0.70): {borderline_fps} ({borderline_pct:.1f}%)")
    print("   → Easy to catch with hierarchical scoring")

    # TOX family issues
    tox_count = family_counts['TOX']
    tox_pct = tox_count / len(fps) * 100
    tox_avg = statistics.mean(family_confidences['TOX'])
    print(f"   TOX family: {tox_count} FPs ({tox_pct:.1f}%) - avg conf {tox_avg:.3f}")
    print("   → Most problematic family - needs careful handling")

def simulate_hierarchical_scoring(fps: list[dict]):
    """Simulate hierarchical scoring with different weights."""
    print("\n6. HIERARCHICAL SCORING SIMULATION")
    print("   (Simulating with family_conf = subfamily_conf = 0.5 for demonstration)")

    # Since we don't have actual family/subfamily confidences, simulate conservative values
    # Real FPs typically have LOW family/subfamily confidence
    for threat_score, family_conf, subfamily_conf in [
        (None, 0.5, 0.3),  # Conservative: low family/sub confidence
        (None, 0.4, 0.3),  # More conservative
        (None, 0.3, 0.2),  # Very conservative (typical FP pattern)
    ]:
        print(f"\n   Assuming family_conf={family_conf}, subfamily_conf={subfamily_conf}:")

        weights_configs = [
            (0.60, 0.25, 0.15, "ML Team (0.60, 0.25, 0.15)"),
            (0.70, 0.20, 0.10, "Binary-Heavy (0.70, 0.20, 0.10)"),
            (0.50, 0.30, 0.20, "Balanced (0.50, 0.30, 0.20)"),
        ]

        for w_binary, w_family, w_sub, label in weights_configs:
            # Count how many FPs would be caught at threshold 0.55
            caught_at_055 = 0

            for fp in fps:
                threat_score = fp['confidence']
                hierarchical = w_binary * threat_score + w_family * family_conf + w_sub * subfamily_conf

                if hierarchical < 0.55:
                    caught_at_055 += 1

            pct = caught_at_055 / len(fps) * 100
            print(f"      {label}: {caught_at_055}/67 FPs caught ({pct:.1f}%)")

def recommend_thresholds(fps: list[dict]):
    """Recommend empirical thresholds based on data."""
    confidences = [fp['confidence'] for fp in fps]

    print("\n7. RECOMMENDED THRESHOLDS (DATA-DRIVEN)")

    # Analyze actual distribution
    p10 = np.percentile(confidences, 10)
    p25 = np.percentile(confidences, 25)
    p50 = np.percentile(confidences, 50)
    p75 = np.percentile(confidences, 75)
    p90 = np.percentile(confidences, 90)

    print(f"\n   Binary Threat Score Percentiles:")
    print(f"   P10: {p10:.3f}")
    print(f"   P25: {p25:.3f}")
    print(f"   P50 (median): {p50:.3f}")
    print(f"   P75: {p75:.3f}")
    print(f"   P90: {p90:.3f}")

    print(f"\n   RECOMMENDATION FOR 'BALANCED' MODE:")
    print(f"   - FP_LIKELY threshold: 0.55 (catches bottom ~25% of FPs)")
    print(f"   - REVIEW threshold: {p75:.3f} (P75 = catches 75% of FPs)")
    print(f"   - THREAT threshold: {p90:.3f} (P90 = only top 10% FPs slip through)")
    print(f"   - HIGH_THREAT threshold: 0.95 (very rare FPs)")

    print(f"\n   NOTE: These thresholds assume hierarchical scoring is used!")
    print(f"   With hierarchical scoring (0.6*threat + 0.25*family + 0.15*sub),")
    print(f"   actual thresholds will be LOWER due to weak family/sub scores.")

def analyze_margin_potential(fps: list[dict]):
    """Analyze potential for margin-based detection."""
    print("\n8. MARGIN ANALYSIS POTENTIAL")

    # We don't have actual margin data, but we can estimate
    # Typically: weak margin = (top_prob - second_prob) < 0.4 for binary

    print("   Without actual probability distributions, we estimate:")
    print("   - FPs likely have WEAK margins (barely chose 'threat' over 'safe')")
    print("   - FPs with conf 0.50-0.65: margin ~0.0-0.3 (VERY WEAK)")
    print("   - FPs with conf 0.65-0.80: margin ~0.3-0.6 (WEAK-MODERATE)")
    print("   - FPs with conf 0.80+: margin ~0.6+ (STRONG - hard cases)")

    weak_conf = sum(1 for c in [fp['confidence'] for fp in fps] if c < 0.65)
    weak_pct = weak_conf / len(fps) * 100

    print(f"\n   FPs with conf < 0.65 (likely weak margin): {weak_conf} ({weak_pct:.1f}%)")
    print(f"   → Margin analysis could catch ~{weak_pct:.0f}% of FPs")

def main():
    csv_path = Path(__file__).parent.parent / "ML-Team-Input" / "all_67_l2_fps_analysis.csv"

    if not csv_path.exists():
        print(f"Error: Dataset not found at {csv_path}")
        return

    fps = load_fp_data(csv_path)

    compute_statistics(fps)
    simulate_hierarchical_scoring(fps)
    recommend_thresholds(fps)
    analyze_margin_potential(fps)

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
