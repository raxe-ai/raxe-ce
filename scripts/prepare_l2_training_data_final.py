#!/usr/bin/env python3
"""
Final Enhanced Training Data Preparation for L2 Model v1.1.0
RAXE CE

This script combines ALL data sources with proper weighting to fix the 62.8% FPR issue:

1. Rule examples (773 @ 3x weight) - Expert-validated production examples
2. Augmented benign (1046 @ 2-4x weight) - Fix false positives
3. Legacy data (80K @ 1x weight) - Volume and coverage
4. Enhanced features: family labels, severity scores, context labels

Output: data/l2_training_final/
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple
from collections import Counter
import random

# Configuration
RULE_EXAMPLES_FILE = Path("/Users/mh/github-raxe-ai/raxe-ce/data/rule_examples.jsonl")
AUGMENTED_BENIGN_FILE = Path("/Users/mh/github-raxe-ai/raxe-ce/data/augmented_benign.jsonl")
ENHANCED_DATA_DIR = Path("/Users/mh/github-raxe-ai/raxe-ce/data/l2_training_enhanced")
OUTPUT_DIR = Path("/Users/mh/github-raxe-ai/raxe-ce/data/l2_training_final")
RANDOM_SEED = 42

# Family mapping
FAMILY_TO_IDX = {
    "CMD": 0,
    "PII": 1,
    "JB": 2,
    "HC": 3,
    "PI": 4,
    "ENC": 5,
    "RAG": 6,
    "benign": 7,
}

# Context mapping
CONTEXT_TO_IDX = {
    "technical": 0,
    "conversational": 1,
    "educational": 2,
    "attack": 3,
}


def load_jsonl(file_path: Path) -> List[Dict]:
    """Load JSONL file"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def add_context_labels(samples: List[Dict]) -> List[Dict]:
    """
    Add context labels to samples that don't have them.
    Context: technical, conversational, educational, attack
    """
    for sample in samples:
        if 'context' in sample and 'context_idx' in sample:
            continue  # Already has context

        # Infer context from other fields
        if sample.get('source') == 'rule_example':
            # Rule examples are attacks
            sample['context'] = 'attack'
            sample['context_idx'] = 3
        elif sample.get('label') == 1:
            # Malicious samples are attacks
            sample['context'] = 'attack'
            sample['context_idx'] = 3
        else:
            # Benign samples - default to conversational
            # (This is conservative - most will be reclassified in augmented set)
            sample['context'] = 'conversational'
            sample['context_idx'] = 1

    return samples


def load_all_data_sources() -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Load all data sources"""
    print("\n" + "="*60)
    print("LOADING DATA SOURCES")
    print("="*60)

    # 1. Rule examples (high priority, from production rules)
    print("\n1. Rule Examples (HIGH PRIORITY)")
    if RULE_EXAMPLES_FILE.exists():
        rule_examples = load_jsonl(RULE_EXAMPLES_FILE)
        rule_examples = add_context_labels(rule_examples)
        print(f"   Loaded: {len(rule_examples)} samples")
        print(f"   Weight: 3.0x average")
        print(f"   Confidence: {sum(s['confidence'] for s in rule_examples)/len(rule_examples):.2f} avg")
    else:
        print(f"   ⚠ Not found, skipping")
        rule_examples = []

    # 2. Augmented benign (critical for FPR fix)
    print("\n2. Augmented Benign (FPR FIX)")
    if AUGMENTED_BENIGN_FILE.exists():
        augmented_benign = load_jsonl(AUGMENTED_BENIGN_FILE)
        print(f"   Loaded: {len(augmented_benign)} samples")
        print(f"   Weight: 2-4x (hard negatives @ 4x)")
        print(f"   Purpose: Fix 62.8% false positive rate")
        print(f"   Breakdown:")
        source_counts = Counter(s['source'] for s in augmented_benign)
        for source, count in sorted(source_counts.items()):
            print(f"     {source}: {count}")
    else:
        print(f"   ⚠ Not found, skipping")
        augmented_benign = []

    # 3. Enhanced legacy data (volume and coverage)
    print("\n3. Enhanced Legacy Data (VOLUME)")
    enhanced_train = load_jsonl(ENHANCED_DATA_DIR / "train.jsonl")
    enhanced_val = load_jsonl(ENHANCED_DATA_DIR / "val.jsonl")
    enhanced_test = load_jsonl(ENHANCED_DATA_DIR / "test.jsonl")

    # Combine and add context
    legacy_data = enhanced_train + enhanced_val + enhanced_test
    legacy_data = add_context_labels(legacy_data)

    print(f"   Loaded: {len(legacy_data)} samples")
    print(f"   Weight: 1.0x")
    print(f"   Distribution:")
    print(f"     Malicious: {sum(1 for s in legacy_data if s['label'] == 1)}")
    print(f"     Benign: {sum(1 for s in legacy_data if s['label'] == 0)}")

    return rule_examples, augmented_benign, legacy_data


def merge_all_datasets(rule_examples: List[Dict],
                       augmented_benign: List[Dict],
                       legacy_data: List[Dict]) -> pd.DataFrame:
    """Merge all datasets with proper weighting"""
    print("\n" + "="*60)
    print("MERGING ALL DATASETS")
    print("="*60)

    # Combine all
    all_samples = rule_examples + augmented_benign + legacy_data

    # Create DataFrame
    df = pd.DataFrame(all_samples)

    print(f"\nCombined dataset:")
    print(f"  Total samples: {len(df)}")

    # Weight distribution
    print(f"\nEffective weight distribution:")
    total_weight = df['weight_multiplier'].sum()
    print(f"  Rule examples:     {df[df['source']=='rule_example']['weight_multiplier'].sum():.0f}")
    print(f"  Hard negatives:    {df[df['source']=='hard_negative']['weight_multiplier'].sum():.0f}")
    print(f"  Augmented tech:    {df[df['source']=='augmented_technical']['weight_multiplier'].sum():.0f}")
    print(f"  Augmented conv:    {df[df['source']=='augmented_conversational']['weight_multiplier'].sum():.0f}")
    print(f"  Augmented edu:     {df[df['source']=='augmented_educational']['weight_multiplier'].sum():.0f}")
    print(f"  Legacy data:       {df[df['source']=='legacy_training']['weight_multiplier'].sum():.0f}")
    print(f"  Total effective:   {total_weight:.0f}")

    # Label distribution
    print(f"\nLabel distribution:")
    label_counts = df['label'].value_counts()
    for label, count in sorted(label_counts.items()):
        pct = count / len(df) * 100
        label_name = "Benign" if label == 0 else "Malicious"
        print(f"  {label_name} ({label}): {count} ({pct:.1f}%)")

    # Context distribution
    print(f"\nContext distribution:")
    context_counts = df['context'].value_counts()
    for context, count in sorted(context_counts.items()):
        pct = count / len(df) * 100
        print(f"  {context}: {count} ({pct:.1f}%)")

    # Family distribution
    print(f"\nFamily distribution:")
    family_counts = df['family'].value_counts()
    for family, count in sorted(family_counts.items(), key=lambda x: -x[1])[:10]:
        pct = count / len(df) * 100
        print(f"  {family}: {count} ({pct:.1f}%)")

    return df


def create_final_splits(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create final train/val/test splits (75%/12.5%/12.5%)"""
    print("\n" + "="*60)
    print("CREATING FINAL SPLITS")
    print("="*60)

    # Shuffle
    df_shuffled = df.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)

    # Calculate sizes
    total = len(df_shuffled)
    train_size = int(total * 0.75)
    val_size = int(total * 0.125)

    # Split
    train_df = df_shuffled[:train_size]
    val_df = df_shuffled[train_size:train_size + val_size]
    test_df = df_shuffled[train_size + val_size:]

    print(f"\nSplit sizes:")
    print(f"  Train: {len(train_df)} samples ({len(train_df)/total*100:.1f}%)")
    print(f"  Val:   {len(val_df)} samples ({len(val_df)/total*100:.1f}%)")
    print(f"  Test:  {len(test_df)} samples ({len(test_df)/total*100:.1f}%)")

    # Validate each split
    for split_name, split_df in [('Train', train_df), ('Val', val_df), ('Test', test_df)]:
        malicious = (split_df['label'] == 1).sum()
        benign = (split_df['label'] == 0).sum()
        mal_pct = malicious / len(split_df) * 100

        print(f"\n{split_name} split:")
        print(f"  Labels: {benign} benign, {malicious} malicious ({mal_pct:.1f}%)")
        print(f"  Families: {split_df['family'].nunique()} unique")
        print(f"  Contexts: {split_df['context'].nunique()} unique")
        print(f"  Avg weight: {split_df['weight_multiplier'].mean():.2f}x")

        # Check for augmented benign in test set
        aug_benign_in_split = split_df[split_df['source'].str.contains('augmented', na=False)].shape[0]
        hard_neg_in_split = split_df[split_df['source'] == 'hard_negative'].shape[0]
        print(f"  Augmented benign: {aug_benign_in_split} samples")
        print(f"  Hard negatives: {hard_neg_in_split} samples (critical for FPR)")

    return train_df, val_df, test_df


def save_datasets(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame):
    """Save final datasets"""
    print("\n" + "="*60)
    print("SAVING FINAL DATASETS")
    print("="*60)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Fields to save
    fields = [
        'text', 'label', 'family', 'family_idx',
        'severity_score', 'context', 'context_idx',
        'weight_multiplier', 'confidence', 'source'
    ]

    # Save each split
    for split_name, split_df in [('train', train_df), ('val', val_df), ('test', test_df)]:
        output_file = OUTPUT_DIR / f"{split_name}.jsonl"

        with open(output_file, 'w', encoding='utf-8') as f:
            for _, row in split_df.iterrows():
                record = {}
                for field in fields:
                    if field in row:
                        value = row[field]
                        # Convert numpy types to native Python
                        if hasattr(value, 'item'):
                            value = value.item()
                        record[field] = value
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        print(f"✓ Saved {split_name}.jsonl ({len(split_df)} samples)")

    # Create metadata
    metadata = {
        'version': '1.1.0',
        'created_at': pd.Timestamp.now().isoformat(),
        'random_seed': RANDOM_SEED,
        'total_samples': len(train_df) + len(val_df) + len(test_df),
        'splits': {
            'train': len(train_df),
            'val': len(val_df),
            'test': len(test_df),
        },
        'data_sources': {
            'rule_examples': {
                'count': 773,
                'weight': 3.0,
                'purpose': 'Expert-validated production examples'
            },
            'augmented_benign': {
                'count': 1046,
                'weight': '2-4x',
                'purpose': 'Fix 62.8% FPR (benign with threat keywords)'
            },
            'legacy_data': {
                'count': 80000,
                'weight': 1.0,
                'purpose': 'Volume and coverage'
            }
        },
        'families': list(FAMILY_TO_IDX.keys()),
        'family_mapping': FAMILY_TO_IDX,
        'contexts': list(CONTEXT_TO_IDX.keys()),
        'context_mapping': CONTEXT_TO_IDX,
        'label_mapping': {
            '0': 'benign',
            '1': 'malicious',
        },
        'features': [
            'binary_classification',
            'family_classification',
            'severity_regression',
            'context_classification',  # NEW
        ],
        'improvements_over_v1_0': [
            'Added 1046 augmented benign samples to fix FPR',
            'Hard negatives (46 @ 4x weight) from actual FP errors',
            'Context labels (technical/conversational/educational/attack)',
            'Multi-task learning targets (binary + family + severity + context)',
            'Weighted sampling (rule examples @ 3x, augmented @ 2-4x)',
        ],
        'expected_performance': {
            'accuracy': '85-90% (vs 100% overfit)',
            'fpr': '<5% (vs 62.8%)',
            'fnr': '10-15% (vs 3.4%)',
            'f1': '>85% (vs 66.6%)',
        }
    }

    with open(OUTPUT_DIR / 'metadata.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved metadata.json")
    print(f"\nOutput directory: {OUTPUT_DIR}")


def main():
    """Main execution"""
    print("\n" + "#"*60)
    print("# FINAL ENHANCED TRAINING DATA PREPARATION")
    print("# L2 Model v1.1.0 - FPR Fix Edition")
    print("#"*60)

    # Load all data sources
    rule_examples, augmented_benign, legacy_data = load_all_data_sources()

    # Merge
    combined_df = merge_all_datasets(rule_examples, augmented_benign, legacy_data)

    # Create splits
    train_df, val_df, test_df = create_final_splits(combined_df)

    # Save
    save_datasets(train_df, val_df, test_df)

    print("\n" + "#"*60)
    print("# FINAL DATA PREPARATION COMPLETE!")
    print("#"*60)
    print(f"\nDataset saved to: {OUTPUT_DIR}")
    print(f"\nKey improvements:")
    print(f"  ✓ Added 1046 augmented benign samples")
    print(f"  ✓ Hard negatives from actual FP errors (4x weight)")
    print(f"  ✓ Context labels for multi-task learning")
    print(f"  ✓ Weighted sampling to prioritize quality")
    print(f"\nExpected impact:")
    print(f"  FPR: 62.8% → <5%")
    print(f"  Accuracy: 100% (overfit) → 85-90% (healthy)")
    print(f"  F1: 66.6% → >85%")
    print(f"\nReady for enhanced multi-output model training!")


if __name__ == "__main__":
    main()
