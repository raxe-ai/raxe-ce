#!/usr/bin/env python3
"""
Data Preparation Script for L2 Unified Model Training
RAXE CE v1.0.0

This script:
1. Loads all 4 datasets (CMD, PII, JB, HC)
2. Validates data quality
3. Combines into unified training set
4. Creates final train/val/test splits
5. Generates metadata and statistics
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter
import hashlib


# Configuration
BASE_DATA_DIR = Path("/Users/mh/github-raxe-ai/raxe-ce/past_data/l2_training/base_data")
OUTPUT_DIR = Path("/Users/mh/github-raxe-ai/raxe-ce/data/l2_training_final")
RANDOM_SEED = 42

DATASETS = {
    "CMD": "cmd_training_dataset_20k",
    "PII": "pii_training_dataset_20k",
    "JB": "jb_training_dataset_20k",
    "HC": "hc_training_dataset_20k_xx",
}


def load_jsonl(file_path: Path) -> List[Dict]:
    """Load JSONL file and return list of dictionaries."""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def validate_dataset(data: List[Dict], family: str) -> Dict:
    """Validate dataset structure and quality."""
    print(f"\n{'='*60}")
    print(f"Validating {family} dataset...")
    print(f"{'='*60}")

    stats = {
        'total_samples': len(data),
        'missing_fields': 0,
        'invalid_labels': 0,
        'empty_texts': 0,
        'label_distribution': Counter(),
        'text_length_stats': [],
        'duplicates': 0,
    }

    seen_texts = set()

    for idx, sample in enumerate(data):
        # Check required fields
        if 'text' not in sample or 'label' not in sample:
            stats['missing_fields'] += 1
            continue

        # Check label validity
        if sample['label'] not in [0, 1]:
            stats['invalid_labels'] += 1
            continue

        # Check empty text
        if not sample['text'] or not sample['text'].strip():
            stats['empty_texts'] += 1
            continue

        # Track label distribution
        stats['label_distribution'][sample['label']] += 1

        # Track text length
        stats['text_length_stats'].append(len(sample['text']))

        # Check duplicates
        text_hash = hashlib.md5(sample['text'].encode()).hexdigest()
        if text_hash in seen_texts:
            stats['duplicates'] += 1
        else:
            seen_texts.add(text_hash)

    # Calculate text length statistics
    if stats['text_length_stats']:
        stats['min_length'] = min(stats['text_length_stats'])
        stats['max_length'] = max(stats['text_length_stats'])
        stats['mean_length'] = sum(stats['text_length_stats']) / len(stats['text_length_stats'])
        stats['median_length'] = sorted(stats['text_length_stats'])[len(stats['text_length_stats']) // 2]

    # Print validation results
    print(f"Total samples: {stats['total_samples']}")
    print(f"Missing fields: {stats['missing_fields']}")
    print(f"Invalid labels: {stats['invalid_labels']}")
    print(f"Empty texts: {stats['empty_texts']}")
    print(f"Duplicates: {stats['duplicates']}")
    print(f"Label distribution:")
    for label, count in sorted(stats['label_distribution'].items()):
        pct = count / stats['total_samples'] * 100
        label_name = "benign" if label == 0 else "malicious"
        print(f"  {label_name} ({label}): {count} ({pct:.1f}%)")
    print(f"Text length stats:")
    print(f"  Min: {stats.get('min_length', 0)}")
    print(f"  Max: {stats.get('max_length', 0)}")
    print(f"  Mean: {stats.get('mean_length', 0):.1f}")
    print(f"  Median: {stats.get('median_length', 0)}")

    # Check balance
    if len(stats['label_distribution']) == 2:
        malicious_pct = stats['label_distribution'][1] / stats['total_samples'] * 100
        if 45 <= malicious_pct <= 55:
            print(f"✓ Dataset is balanced ({malicious_pct:.1f}% malicious)")
        else:
            print(f"⚠ Dataset imbalance detected ({malicious_pct:.1f}% malicious)")

    return stats


def load_and_validate_all_datasets() -> Tuple[Dict[str, Dict], Dict[str, Dict]]:
    """Load and validate all datasets."""
    print("\n" + "="*60)
    print("LOADING ALL DATASETS")
    print("="*60)

    all_data = {}
    all_stats = {}

    for family, dataset_name in DATASETS.items():
        dataset_dir = BASE_DATA_DIR / dataset_name

        # Load train, val, test
        train_data = load_jsonl(dataset_dir / "train.jsonl")
        val_data = load_jsonl(dataset_dir / "val.jsonl")
        test_data = load_jsonl(dataset_dir / "test.jsonl")

        print(f"\n{family} dataset loaded:")
        print(f"  Train: {len(train_data)} samples")
        print(f"  Val: {len(val_data)} samples")
        print(f"  Test: {len(test_data)} samples")
        print(f"  Total: {len(train_data) + len(val_data) + len(test_data)} samples")

        # Combine all splits for validation
        combined = train_data + val_data + test_data

        # Validate
        stats = validate_dataset(combined, family)

        # Store
        all_data[family] = {
            'train': train_data,
            'val': val_data,
            'test': test_data,
            'combined': combined,
        }
        all_stats[family] = stats

    return all_data, all_stats


def combine_datasets(all_data: Dict[str, Dict]) -> pd.DataFrame:
    """Combine all datasets into one unified dataset."""
    print("\n" + "="*60)
    print("COMBINING DATASETS")
    print("="*60)

    combined_records = []

    for family in DATASETS.keys():
        # Get all data for this family
        family_data = all_data[family]['combined']

        # Add family label to each record
        for sample in family_data:
            record = {
                'text': sample['text'],
                'label': sample['label'],
                'family': family,
            }
            combined_records.append(record)

    # Create DataFrame
    df = pd.DataFrame(combined_records)

    print(f"\nCombined dataset created:")
    print(f"  Total samples: {len(df)}")
    print(f"\nFamily distribution:")
    print(df['family'].value_counts())
    print(f"\nLabel distribution:")
    print(df['label'].value_counts())
    print(f"\nCross-tabulation (Family × Label):")
    print(pd.crosstab(df['family'], df['label'], margins=True))

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

    # Validate balance in each split
    for split_name, split_df in [('Train', train_df), ('Val', val_df), ('Test', test_df)]:
        malicious_pct = (split_df['label'] == 1).sum() / len(split_df) * 100
        print(f"\n{split_name} split label distribution:")
        print(f"  Benign (0): {(split_df['label'] == 0).sum()} ({100-malicious_pct:.1f}%)")
        print(f"  Malicious (1): {(split_df['label'] == 1).sum()} ({malicious_pct:.1f}%)")

        print(f"\n{split_name} split family distribution:")
        print(split_df['family'].value_counts())

    return train_df, val_df, test_df


def save_datasets(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame):
    """Save datasets to JSONL files."""
    print("\n" + "="*60)
    print("SAVING DATASETS")
    print("="*60)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save each split
    for split_name, split_df in [('train', train_df), ('val', val_df), ('test', test_df)]:
        output_file = OUTPUT_DIR / f"{split_name}.jsonl"

        with open(output_file, 'w', encoding='utf-8') as f:
            for _, row in split_df.iterrows():
                record = {
                    'text': row['text'],
                    'label': int(row['label']),
                    'family': row['family'],
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        print(f"✓ Saved {split_name}.jsonl ({len(split_df)} samples)")

    # Create metadata
    metadata = {
        'version': '1.0.0',
        'created_at': pd.Timestamp.now().isoformat(),
        'random_seed': RANDOM_SEED,
        'total_samples': len(train_df) + len(val_df) + len(test_df),
        'splits': {
            'train': len(train_df),
            'val': len(val_df),
            'test': len(test_df),
        },
        'families': list(DATASETS.keys()),
        'label_mapping': {
            '0': 'benign',
            '1': 'malicious',
        },
        'description': 'Unified L2 training dataset combining CMD, PII, JB, and HC threat families',
    }

    with open(OUTPUT_DIR / 'metadata.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved metadata.json")
    print(f"\nOutput directory: {OUTPUT_DIR}")


def generate_sample_preview(train_df: pd.DataFrame):
    """Generate sample preview file."""
    print("\n" + "="*60)
    print("GENERATING SAMPLE PREVIEW")
    print("="*60)

    # Sample 5 examples from each family (both malicious and benign)
    preview_samples = []

    for family in DATASETS.keys():
        family_df = train_df[train_df['family'] == family]

        # Sample malicious
        malicious_samples = family_df[family_df['label'] == 1].head(3)
        for _, row in malicious_samples.iterrows():
            preview_samples.append({
                'text': row['text'][:200] + '...' if len(row['text']) > 200 else row['text'],
                'label': int(row['label']),
                'family': row['family'],
            })

        # Sample benign
        benign_samples = family_df[family_df['label'] == 0].head(2)
        for _, row in benign_samples.iterrows():
            preview_samples.append({
                'text': row['text'][:200] + '...' if len(row['text']) > 200 else row['text'],
                'label': int(row['label']),
                'family': row['family'],
            })

    # Save preview
    with open(OUTPUT_DIR / 'preview.jsonl', 'w', encoding='utf-8') as f:
        for sample in preview_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')

    print(f"✓ Saved preview.jsonl ({len(preview_samples)} samples)")


def main():
    """Main execution function."""
    print("\n" + "#"*60)
    print("# L2 UNIFIED MODEL - DATA PREPARATION")
    print("# RAXE CE v1.0.0")
    print("#"*60)

    # Step 1: Load and validate all datasets
    all_data, all_stats = load_and_validate_all_datasets()

    # Step 2: Combine datasets
    combined_df = combine_datasets(all_data)

    # Step 3: Create final splits
    train_df, val_df, test_df = create_final_splits(combined_df)

    # Step 4: Save datasets
    save_datasets(train_df, val_df, test_df)

    # Step 5: Generate preview
    generate_sample_preview(train_df)

    print("\n" + "#"*60)
    print("# DATA PREPARATION COMPLETE!")
    print("#"*60)
    print(f"\nFinal datasets saved to: {OUTPUT_DIR}")
    print(f"\nReady for training with:")
    print(f"  - Train: {len(train_df)} samples")
    print(f"  - Val: {len(val_df)} samples")
    print(f"  - Test: {len(test_df)} samples")
    print(f"  - Total: {len(train_df) + len(val_df) + len(test_df)} samples")


if __name__ == "__main__":
    main()
