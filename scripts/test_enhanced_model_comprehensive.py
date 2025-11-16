#!/usr/bin/env python3
"""
Comprehensive Test of Enhanced L2 Model v1.1.0
RAXE CE

Tests model on large samples from actual training data:
- 1K, 5K, 10K benign prompts (from 100K available)
- 1K, 5K, 10K malicious prompts
"""

import sys
sys.path.insert(0, '/Users/mh/github-raxe-ai/raxe-ce/src')

import torch
from pathlib import Path
from transformers import DistilBertTokenizer
from raxe.domain.ml.enhanced_detector import EnhancedThreatDetector
import json
import random
from tqdm import tqdm

# Paths
MODEL_PATH = Path("/Users/mh/github-raxe-ai/raxe-ce/models/l2_enhanced_v1.1.0")
BENIGN_FILE = Path("/Users/mh/github-raxe-ai/raxe-ce/past_data/l1_training/benign_prompts.jsonl")
MALICIOUS_FILE = Path("/Users/mh/github-raxe-ai/raxe-ce/past_data/l1_training/malicious_prompts.json")

print("="*80)
print("COMPREHENSIVE ENHANCED MODEL TEST")
print("="*80)

# Load data
print("\nLoading data...")
# Load JSONL format (one JSON per line)
benign_data = []
with open(BENIGN_FILE, 'r') as f:
    for line in f:
        if line.strip():
            benign_data.append(json.loads(line))
print(f"  Benign prompts available: {len(benign_data):,}")

# Load JSON format
with open(MALICIOUS_FILE, 'r') as f:
    malicious_data = json.load(f)
print(f"  Malicious prompts available: {len(malicious_data):,}")

# Device
if torch.backends.mps.is_available():
    device = torch.device('mps')
    print("\nUsing Mac GPU (MPS)")
else:
    device = torch.device('cpu')
    print("\nUsing CPU")

# Load model
print(f"\nLoading enhanced model from: {MODEL_PATH}")
tokenizer = DistilBertTokenizer.from_pretrained(MODEL_PATH)
model = EnhancedThreatDetector()
model.load_state_dict(torch.load(MODEL_PATH / "pytorch_model.bin", map_location=device))
model.to(device)
model.eval()
print(f"Model loaded: {model.get_num_parameters():,} parameters")

def extract_text(item):
    """Extract text from various data formats"""
    if isinstance(item, str):
        return item
    elif isinstance(item, dict):
        return item.get('text', item.get('prompt', str(item)))
    else:
        return str(item)

def test_batch(prompts, label, description):
    """Test a batch of prompts"""
    print(f"\n{'='*80}")
    print(f"Testing {len(prompts):,} {description}")
    print(f"{'='*80}")

    correct = 0
    false_positives = 0
    false_negatives = 0
    total_confidence = 0.0
    high_confidence_errors = []

    for item in tqdm(prompts, desc=description):
        text = extract_text(item)

        # Tokenize
        encoding = tokenizer(
            text,
            padding='max_length',
            truncation=True,
            max_length=128,
            return_tensors='pt'
        )

        input_ids = encoding['input_ids'].to(device)
        attention_mask = encoding['attention_mask'].to(device)

        # Predict
        with torch.no_grad():
            result = model.predict(input_ids, attention_mask)

        binary_pred = result['binary_pred'].item()
        binary_probs = result['binary_probs'][0].cpu().numpy()
        malicious_confidence = binary_probs[1]

        predicted_label = "MALICIOUS" if binary_pred == 1 else "BENIGN"
        is_correct = predicted_label == label

        if is_correct:
            correct += 1
        else:
            if label == "BENIGN":
                false_positives += 1
                if malicious_confidence > 0.8:
                    high_confidence_errors.append({
                        "text": text[:100],
                        "confidence": float(malicious_confidence)
                    })
            else:
                false_negatives += 1
                if malicious_confidence < 0.2:
                    high_confidence_errors.append({
                        "text": text[:100],
                        "confidence": float(malicious_confidence)
                    })

        total_confidence += malicious_confidence

    # Calculate metrics
    total = len(prompts)
    accuracy = correct / total
    avg_confidence = total_confidence / total

    if label == "BENIGN":
        fpr = false_positives / total
        print(f"\n✓ Benign Classification:")
        print(f"  Accuracy: {correct}/{total} ({accuracy:.1%})")
        print(f"  False Positives: {false_positives} ({fpr:.2%})")
        print(f"  Avg Malicious Confidence: {avg_confidence:.1%}")

        if high_confidence_errors:
            print(f"\n⚠️  High-Confidence False Positives (>80%):")
            for err in high_confidence_errors[:5]:
                print(f"    [{err['confidence']:.1%}] {err['text']}...")

        return {
            "type": "benign",
            "total": total,
            "correct": correct,
            "accuracy": accuracy,
            "false_positives": false_positives,
            "fpr": fpr,
            "avg_confidence": avg_confidence,
            "high_confidence_errors": len(high_confidence_errors)
        }
    else:
        fnr = false_negatives / total
        print(f"\n✓ Malicious Detection:")
        print(f"  Accuracy: {correct}/{total} ({accuracy:.1%})")
        print(f"  False Negatives: {false_negatives} ({fnr:.2%})")
        print(f"  Avg Malicious Confidence: {avg_confidence:.1%}")

        if high_confidence_errors:
            print(f"\n⚠️  High-Confidence False Negatives (<20%):")
            for err in high_confidence_errors[:5]:
                print(f"    [{err['confidence']:.1%}] {err['text']}...")

        return {
            "type": "malicious",
            "total": total,
            "correct": correct,
            "accuracy": accuracy,
            "false_negatives": false_negatives,
            "fnr": fnr,
            "avg_confidence": avg_confidence,
            "high_confidence_errors": len(high_confidence_errors)
        }

# Test sizes
test_sizes = [1000, 5000, 10000]

all_results = {}

for size in test_sizes:
    print(f"\n{'#'*80}")
    print(f"# TESTING WITH {size:,} SAMPLES")
    print(f"{'#'*80}")

    # Set seed for reproducibility
    random.seed(42)

    # Sample data
    benign_sample = random.sample(benign_data, min(size, len(benign_data)))
    malicious_sample = random.sample(malicious_data, min(size, len(malicious_data)))

    # Test benign
    benign_results = test_batch(benign_sample, "BENIGN", f"{size:,} benign prompts")

    # Test malicious
    malicious_results = test_batch(malicious_sample, "MALICIOUS", f"{size:,} malicious prompts")

    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY FOR {size:,} SAMPLES")
    print(f"{'='*80}")
    print(f"  Benign FPR:    {benign_results['fpr']:.2%}")
    print(f"  Malicious FNR: {malicious_results['fnr']:.2%}")
    print(f"  Overall Accuracy: {(benign_results['correct'] + malicious_results['correct']) / (size * 2):.1%}")

    all_results[f"{size}"] = {
        "benign": benign_results,
        "malicious": malicious_results
    }

# Final comparison table
print(f"\n{'='*80}")
print(f"COMPREHENSIVE RESULTS COMPARISON")
print(f"{'='*80}")
print(f"\n{'Sample Size':<15} {'Benign FPR':<15} {'Malicious FNR':<15} {'Overall Acc':<15}")
print("-" * 60)

for size in test_sizes:
    results = all_results[f"{size}"]
    benign_fpr = results['benign']['fpr']
    malicious_fnr = results['malicious']['fnr']
    overall_acc = (results['benign']['correct'] + results['malicious']['correct']) / (size * 2)

    print(f"{size:>6,} samples  {benign_fpr:>6.2%}          {malicious_fnr:>6.2%}          {overall_acc:>6.1%}")

# Compare with v1.0
print(f"\n{'='*80}")
print(f"COMPARISON WITH v1.0 BASIC MODEL")
print(f"{'='*80}")
print(f"  v1.0 FPR (test set): 62.8%")
print(f"  v1.1 FPR (1K):       {all_results['1000']['benign']['fpr']:.2%}")
print(f"  v1.1 FPR (5K):       {all_results['5000']['benign']['fpr']:.2%}")
print(f"  v1.1 FPR (10K):      {all_results['10000']['benign']['fpr']:.2%}")
print()
print(f"  v1.0 FNR (test set): 3.4%")
print(f"  v1.1 FNR (1K):       {all_results['1000']['malicious']['fnr']:.2%}")
print(f"  v1.1 FNR (5K):       {all_results['5000']['malicious']['fnr']:.2%}")
print(f"  v1.1 FNR (10K):      {all_results['10000']['malicious']['fnr']:.2%}")

# Check if target met
fpr_10k = all_results['10000']['benign']['fpr']
if fpr_10k < 0.05:
    print(f"\n✅ SUCCESS! FPR on 10K samples: {fpr_10k:.2%} (target: <5%)")
else:
    print(f"\n⚠️  WARNING: FPR on 10K samples: {fpr_10k:.2%} (target: <5%)")

# Save results
output_file = Path("/Users/mh/github-raxe-ai/raxe-ce/CLAUDE_WORKING_FILES/REPORTS/comprehensive_test_results.json")
with open(output_file, 'w') as f:
    json.dump({
        "model_version": "v1.1.0_enhanced",
        "model_path": str(MODEL_PATH),
        "data_sources": {
            "benign": str(BENIGN_FILE),
            "malicious": str(MALICIOUS_FILE),
            "total_benign_available": len(benign_data),
            "total_malicious_available": len(malicious_data),
        },
        "results": all_results,
        "comparison": {
            "v1.0_fpr": 0.628,
            "v1.1_fpr_10k": fpr_10k,
            "improvement": 0.628 - fpr_10k,
        }
    }, f, indent=2)

print(f"\n📊 Detailed results saved to: {output_file}")
