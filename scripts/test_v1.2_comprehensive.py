#!/usr/bin/env python3
"""
Comprehensive Test of L2 Model v1.2.0 (Focal Loss + Augmentation)
RAXE CE

Tests model on 10K samples to validate improvements over v1.1.0:
- Expected FPR: 6.34% → <3%
- Expected FNR: 10.5% → 7-8%
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
MODEL_V12_PATH = Path("/Users/mh/github-raxe-ai/raxe-ce/models/l2_enhanced_v1.2.0")
MODEL_V11_PATH = Path("/Users/mh/github-raxe-ai/raxe-ce/models/l2_enhanced_v1.1.0")
BENIGN_FILE = Path("/Users/mh/github-raxe-ai/raxe-ce/past_data/l1_training/benign_prompts.jsonl")
MALICIOUS_FILE = Path("/Users/mh/github-raxe-ai/raxe-ce/past_data/l1_training/malicious_prompts.json")

print("="*80)
print("MODEL v1.2.0 COMPREHENSIVE TEST")
print("="*80)

# Load data
print("\nLoading data...")
benign_data = []
with open(BENIGN_FILE, 'r') as f:
    for line in f:
        if line.strip():
            benign_data.append(json.loads(line))

with open(MALICIOUS_FILE, 'r') as f:
    malicious_data = json.load(f)

print(f"  Benign prompts available: {len(benign_data):,}")
print(f"  Malicious prompts available: {len(malicious_data):,}")

# Device
if torch.backends.mps.is_available():
    device = torch.device('mps')
    print("\nUsing Mac GPU (MPS)")
else:
    device = torch.device('cpu')
    print("\nUsing CPU")

# Load v1.2.0 model
print(f"\nLoading v1.2.0 model from: {MODEL_V12_PATH}")
tokenizer = DistilBertTokenizer.from_pretrained(MODEL_V12_PATH)
model_v12 = EnhancedThreatDetector()
model_v12.load_state_dict(torch.load(MODEL_V12_PATH / "pytorch_model.bin", map_location=device))
model_v12.to(device)
model_v12.eval()
print(f"v1.2.0 loaded: {model_v12.get_num_parameters():,} parameters")

def extract_text(item):
    """Extract text from various data formats"""
    if isinstance(item, str):
        return item
    elif isinstance(item, dict):
        return item.get('text', item.get('prompt', str(item)))
    else:
        return str(item)

def test_batch(prompts, label, description, model):
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
            print(f"\n⚠️  High-Confidence False Positives (>80%): {len(high_confidence_errors)}")
            for err in high_confidence_errors[:3]:
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
            print(f"\n⚠️  High-Confidence False Negatives (<20%): {len(high_confidence_errors)}")
            for err in high_confidence_errors[:3]:
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

# Test on 10K samples
print(f"\n{'#'*80}")
print(f"# TESTING v1.2.0 ON 10,000 SAMPLES")
print(f"{'#'*80}")

random.seed(42)
test_size = 10000

benign_sample = random.sample(benign_data, min(test_size, len(benign_data)))
malicious_sample = random.sample(malicious_data, min(1000, len(malicious_data)))

# Test benign
benign_results = test_batch(benign_sample, "BENIGN", f"{test_size:,} benign prompts", model_v12)

# Test malicious
malicious_results = test_batch(malicious_sample, "MALICIOUS", f"1,000 malicious prompts", model_v12)

# Summary
print(f"\n{'='*80}")
print(f"v1.2.0 RESULTS SUMMARY (10K BENIGN + 1K MALICIOUS)")
print(f"{'='*80}")
print(f"  Benign FPR:       {benign_results['fpr']:.2%}")
print(f"  Malicious FNR:    {malicious_results['fnr']:.2%}")
print(f"  Overall Accuracy: {(benign_results['correct'] + malicious_results['correct']) / (test_size + 1000):.1%}")

# Comparison with v1.1.0
print(f"\n{'='*80}")
print(f"COMPARISON: v1.1.0 vs v1.2.0")
print(f"{'='*80}")
print(f"  v1.1 FPR: 6.34%  →  v1.2 FPR: {benign_results['fpr']:.2%}")
print(f"  v1.1 FNR: 10.50% →  v1.2 FNR: {malicious_results['fnr']:.2%}")

# Check targets
fpr_target_met = benign_results['fpr'] < 0.03
fnr_target_met = malicious_results['fnr'] < 0.09

print(f"\n{'='*80}")
print("TARGET VALIDATION")
print(f"{'='*80}")
if fpr_target_met:
    print(f"✅ FPR Target MET: {benign_results['fpr']:.2%} < 3%")
else:
    print(f"⚠️  FPR Target MISSED: {benign_results['fpr']:.2%} (target: <3%)")

if fnr_target_met:
    print(f"✅ FNR Target MET: {malicious_results['fnr']:.2%} < 9%")
else:
    print(f"⚠️  FNR Target MISSED: {malicious_results['fnr']:.2%} (target: <9%)")

# Calculate improvements
fpr_improvement = 0.0634 - benign_results['fpr']
fnr_improvement = 0.105 - malicious_results['fnr']

print(f"\n{'='*80}")
print("IMPROVEMENTS")
print(f"{'='*80}")
print(f"  FPR Improvement: {fpr_improvement:.2%} reduction")
print(f"  FNR Improvement: {fnr_improvement:.2%} reduction" if fnr_improvement > 0 else f"  FNR Change: {fnr_improvement:.2%}")

# Save results
output_file = Path("/Users/mh/github-raxe-ai/raxe-ce/CLAUDE_WORKING_FILES/REPORTS/v1.2_comprehensive_test_results.json")
with open(output_file, 'w') as f:
    json.dump({
        "model_version": "v1.2.0_focal_loss",
        "model_path": str(MODEL_V12_PATH),
        "benign_results": benign_results,
        "malicious_results": malicious_results,
        "comparison": {
            "v1.1_fpr": 0.0634,
            "v1.2_fpr": benign_results['fpr'],
            "fpr_improvement": fpr_improvement,
            "v1.1_fnr": 0.105,
            "v1.2_fnr": malicious_results['fnr'],
            "fnr_improvement": fnr_improvement,
        },
        "targets": {
            "fpr_target": 0.03,
            "fpr_met": fpr_target_met,
            "fnr_target": 0.09,
            "fnr_met": fnr_target_met,
        }
    }, f, indent=2)

print(f"\n📊 Detailed results saved to: {output_file}")
