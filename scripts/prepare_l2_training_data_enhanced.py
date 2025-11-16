#!/usr/bin/env python3
"""
Enhanced Data Preparation Script for L2 Multi-Output Model
RAXE CE v1.1.0

This script:
1. Loads rule examples (HIGH priority, 3x weight)
2. Loads legacy data (MEDIUM priority, 1x weight)
3. Merges with weighted sampling
4. Adds family labels, severity scores
5. Creates train/val/test splits
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter
import hashlib

# Configuration
RULE_EXAMPLES_FILE = Path("/Users/mh/github-raxe-ai/raxe-ce/data/rule_examples.jsonl")
BASE_DATA_DIR = Path("/Users/mh/github-raxe-ai/raxe-ce/past_data/l2_training/base_data")
OUTPUT_DIR = Path("/Users/mh/github-raxe-ai/raxe-ce/data/l2_training_enhanced")
RANDOM_SEED = 42

LEGACY_DATASETS = {
    "CMD": "cmd_training_dataset_20k",
    "PII": "pii_training_dataset_20k",
    "JB": "jb_training_dataset_20k",
    "HC": "hc_training_dataset_20k_xx",
}

# Family mapping for model (index-based)
FAMILY_TO_IDX = {
    "CMD": 0,
    "PII": 1,
    "JB": 2,
    "HC": 3,
    "PI": 4,   # Prompt Injection
    "ENC": 5,  # Encoding
    "RAG": 6,  # RAG attacks
    "benign": 7  # For benign samples
}

# Severity mapping to numerical scores
SEVERITY_TO_SCORE = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.5,
    "low": 0.25,
    "info": 0.0  # For benign samples
}


def load_jsonl(file_path: Path) -> List[Dict]:
    """Load JSONL file."""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def load_rule_examples() -> List[Dict]:
    """Load high-quality rule examples with metadata."""
    print("\n" + "="*60)
    print("LOADING RULE EXAMPLES (HIGH PRIORITY)")
    print("="*60)

    if not RULE_EXAMPLES_FILE.exists():
        print(f"⚠ Rule examples not found at {RULE_EXAMPLES_FILE}")
        print("  Run: python3 scripts/extract_rule_examples.py")
        return []

    examples = load_jsonl(RULE_EXAMPLES_FILE)

    print(f"Loaded: {len(examples)} examples")
    print(f"Weight multiplier: 3.0x")
    print(f"Avg confidence: {sum(e['confidence'] for e in examples)/len(examples):.2f}")

    # Add family indices and severity scores
    for sample in examples:
        sample['family_idx'] = FAMILY_TO_IDX.get(sample['family'], 7)
        sample['severity_score'] = SEVERITY_TO_SCORE.get(sample.get('severity', 'info'), 0.0)
        # Ensure weight is set
        if 'weight_multiplier' not in sample:
            sample['weight_multiplier'] = 3.0

    return examples


def load_legacy_data() -> List[Dict]:
    """Load legacy training data."""
    print("\n" + "="*60)
    print("LOADING LEGACY DATA (MEDIUM PRIORITY)")
    print("="*60)

    all_data = []

    for family, dataset_name in LEGACY_DATASETS.items():
        dataset_dir = BASE_DATA_DIR / dataset_name

        # Load all splits
        train_data = load_jsonl(dataset_dir / "train.jsonl")
        val_data = load_jsonl(dataset_dir / "val.jsonl")
        test_data = load_jsonl(dataset_dir / "test.jsonl")

        combined = train_data + val_data + test_data

        print(f"{family}: {len(combined)} samples")

        # Add metadata
        for sample in combined:
            sample['family'] = family
            sample['family_idx'] = FAMILY_TO_IDX.get(family, 7)
            sample['source'] = 'legacy_training'
            sample['weight_multiplier'] = 1.0  # Base weight
            sample['confidence'] = 0.75  # Assumed medium confidence

            # Infer severity from label (malicious = high, benign = info)
            sample['severity'] = 'high' if sample['label'] == 1 else 'info'
            sample['severity_score'] = 0.75 if sample['label'] == 1 else 0.0

        all_data.extend(combined)

    print(f"\nTotal legacy samples: {len(all_data)}")
    print(f"Weight multiplier: 1.0x")

    return all_data


def merge_datasets(rule_examples: List[Dict], legacy_data: List[Dict]) -> pd.DataFrame:
    """Merge all datasets with proper weighting."""
    print("\n" + "="*60)
    print("MERGING DATASETS")
    print("="*60)

    all_samples = rule_examples + legacy_data

    # Create DataFrame
    df = pd.DataFrame(all_samples)

    print(f"\nCombined dataset:")
    print(f"  Total samples: {len(df)}")

    # Source distribution
    print(f"\nSamples by source:")
    print(df['source'].value_counts())

    # Family distribution
    print(f"\nSamples by family:")
    print(df['family'].value_counts())

    # Label distribution
    print(f"\nLabel distribution:")
    label_counts = df['label'].value_counts()
    for label, count in sorted(label_counts.items()):
        pct = count / len(df) * 100
        label_name = "Benign" if label == 0 else "Malicious"
        print(f"  {label_name} ({label}): {count} ({pct:.1f}%)")

    # Weight distribution
    print(f"\nEffective weight distribution:")
    total_weight = df['weight_multiplier'].sum()
    print(f"  Rule examples: {df[df['source']=='rule_example']['weight_multiplier'].sum():.0f}")
    print(f"  Legacy data: {df[df['source']=='legacy_training']['weight_multiplier'].sum():.0f}")
    print(f"  Total effective weight: {total_weight:.0f}")

    return df


def create_final_splits(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create final train/val/test splits (75%/12.5%/12.5%)."""
    print("\n" + "="*60)
    print("CREATING FINAL SPLITS")
    print("="*60)

    # Shuffle dataset
    df_shuffled = df.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)

    # Calculate split sizes
    total = len(df_shuffled)
    train_size = int(total * 0.75)
    val_size = int(total * 0.125)

    # Split
    train_df = df_shuffled[:train_size]
    val_df = df_shuffled[train_size:train_size + val_size]
    test_df = df_shuffled[train_size + val_size:]

    print(f"\nSplit sizes:")
    print(f"  Train: {len(train_df)} samples ({len(train_df)/total*100:.1f}%)")
    print(f"  Val: {len(val_df)} samples ({len(val_df)/total*100:.1f}%)")
    print(f"  Test: {len(test_df)} samples ({len(test_df)/total*100:.1f}%)")

    # Validate balance
    for split_name, split_df in [('Train', train_df), ('Val', val_df), ('Test', test_df)]:
        malicious_pct = (split_df['label'] == 1).sum() / len(split_df) * 100
        print(f"\n{split_name} split:")
        print(f"  Labels: {(split_df['label'] == 0).sum()} benign, {(split_df['label'] == 1).sum()} malicious ({malicious_pct:.1f}%)")
        print(f"  Families: {split_df['family'].nunique()} unique")
        print(f"  Avg weight: {split_df['weight_multiplier'].mean():.2f}x")

    return train_df, val_df, test_df


def save_datasets(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame):
    """Save datasets to JSONL files."""
    print("\n" + "="*60)
    print("SAVING DATASETS")
    print("="*60)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Fields to save
    fields = [
        'text', 'label', 'family', 'family_idx', 'severity_score',
        'weight_multiplier', 'confidence', 'source'
    ]

    # Save each split
    for split_name, split_df in [('train', train_df), ('val', val_df), ('test', test_df)]:
        output_file = OUTPUT_DIR / f"{split_name}.jsonl"

        with open(output_file, 'w', encoding='utf-8') as f:
            for _, row in split_df.iterrows():
                record = {field: row.get(field) for field in fields if field in row}
                # Convert numpy types to native Python
                for key, value in record.items():
                    if hasattr(value, 'item'):
                        record[key] = value.item()
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
        'families': list(FAMILY_TO_IDX.keys()),
        'family_mapping': FAMILY_TO_IDX,
        'severity_mapping': SEVERITY_TO_SCORE,
        'label_mapping': {
            '0': 'benign',
            '1': 'malicious',
        },
        'features': [
            'binary_classification',  # malicious/benign
            'family_classification',  # which threat family
            'severity_regression',     # how severe (0-1)
        ],
        'description': 'Enhanced L2 training dataset with family labels and severity scores',
        'enhancements': [
            'Rule examples included (773 samples @ 3x weight)',
            'Family classification labels',
            'Severity regression scores',
            'Weighted sampling support',
        ]
    }

    with open(OUTPUT_DIR / 'metadata.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved metadata.json")
    print(f"\nOutput directory: {OUTPUT_DIR}")


def main():
    """Main execution function."""
    print("\n" + "#"*60)
    print("# L2 ENHANCED MODEL - DATA PREPARATION")
    print("# RAXE CE v1.1.0")
    print("#"*60)

    # Step 1: Load rule examples
    rule_examples = load_rule_examples()

    # Step 2: Load legacy data
    legacy_data = load_legacy_data()

    # Step 3: Merge datasets
    combined_df = merge_datasets(rule_examples, legacy_data)

    # Step 4: Create final splits
    train_df, val_df, test_df = create_final_splits(combined_df)

    # Step 5: Save datasets
    save_datasets(train_df, val_df, test_df)

    print("\n" + "#"*60)
    print("# DATA PREPARATION COMPLETE!")
    print("#"*60)
    print(f"\nEnhanced datasets saved to: {OUTPUT_DIR}")
    print(f"\nFeatures:")
    print(f"  ✓ Binary classification (malicious/benign)")
    print(f"  ✓ Family classification (7 families)")
    print(f"  ✓ Severity regression (0-1 score)")
    print(f"  ✓ Weighted sampling (rule examples @ 3x)")
    print(f"\nReady for enhanced multi-output model training!")


if __name__ == "__main__":
    main()
