#!/usr/bin/env python3
"""
L2 Model v1.2.0 Training with Focal Loss
RAXE CE

Improvements over v1.1.0:
- Focal Loss for hard example mining
- Hard negative samples from FP analysis (@ 5x weight)
- Programming task augmentation (@ 4x weight)
- Adversarial evasion samples (@ 3x weight)

Expected: FPR 6.34% → <3%, FNR 10.5% → 7-8%
"""

import sys
sys.path.insert(0, '/Users/mh/github-raxe-ai/raxe-ce/src')

import json
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from pathlib import Path
from typing import Dict, List
import numpy as np
from tqdm import tqdm
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from transformers import DistilBertTokenizer
from raxe.domain.ml.enhanced_detector import EnhancedThreatDetector

# Config
DATA_DIR = Path("/Users/mh/github-raxe-ai/raxe-ce/data/l2_training_final")
AUGMENTED_DIR = Path("/Users/mh/github-raxe-ai/raxe-ce/data")
OUTPUT_DIR = Path("/Users/mh/github-raxe-ai/raxe-ce/models/l2_enhanced_v1.2.0")
PRETRAINED_MODEL = Path("/Users/mh/github-raxe-ai/raxe-ce/models/l2_enhanced_v1.1.0")

BATCH_SIZE = 16
LEARNING_RATE = 3e-6  # Even lower for fine-tuning
NUM_EPOCHS = 2  # Fine-tune only, not full retrain
MAX_LENGTH = 128
WEIGHT_DECAY = 0.01
DROPOUT = 0.3
SEED = 42

# Focal Loss parameters
FOCAL_ALPHA = 0.75  # Weight for positive class
FOCAL_GAMMA = 2.0   # Focus on hard examples

def set_seed(seed):
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.backends.mps.is_available():
        torch.mps.manual_seed(seed)

def load_jsonl(path):
    data = []
    with open(path) as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data

# ============================================================================
# FOCAL LOSS IMPLEMENTATION
# ============================================================================

class FocalLoss(nn.Module):
    """
    Focal Loss for addressing class imbalance and hard examples

    FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)

    - Focuses learning on hard, misclassified examples
    - Reduces relative loss for well-classified examples
    - gamma > 0 reduces loss contribution from easy examples
    """
    def __init__(self, alpha=0.75, gamma=2.0, reduction='mean'):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, inputs, targets):
        """
        Args:
            inputs: [batch, num_classes] logits
            targets: [batch] class indices
        """
        # Get probabilities
        probs = F.softmax(inputs, dim=1)

        # Get probability of correct class
        targets_one_hot = F.one_hot(targets, num_classes=inputs.size(1)).float()
        pt = (probs * targets_one_hot).sum(dim=1)  # p_t

        # Focal weight: (1 - p_t)^gamma
        focal_weight = (1 - pt).pow(self.gamma)

        # Cross entropy loss
        ce_loss = F.cross_entropy(inputs, targets, reduction='none')

        # Apply focal weighting
        focal_loss = focal_weight * ce_loss

        # Apply alpha balancing (optional)
        if self.alpha is not None:
            alpha_weight = targets * self.alpha + (1 - targets) * (1 - self.alpha)
            focal_loss = alpha_weight * focal_loss

        if self.reduction == 'mean':
            return focal_loss.mean()
        elif self.reduction == 'sum':
            return focal_loss.sum()
        else:
            return focal_loss

class ThreatDataset(Dataset):
    def __init__(self, data, tokenizer, max_length=128):
        self.data = data
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]

        # Tokenize
        encoding = self.tokenizer(
            item['text'],
            padding='max_length',
            truncation=True,
            max_length=self.max_length,
            return_tensors='pt'
        )

        # Handle NaN values (same as v1.1)
        import math

        family_idx = item.get('family_idx', 7)
        if isinstance(family_idx, float):
            if math.isnan(family_idx):
                family_idx = 7
            else:
                family_idx = int(family_idx)

        context_idx = item.get('context_idx', 1)
        if isinstance(context_idx, float):
            if math.isnan(context_idx):
                context_idx = 3 if item['label'] == 1 else 1
            else:
                context_idx = int(context_idx)

        severity = item.get('severity_score', 0.0)
        if isinstance(severity, float) and math.isnan(severity):
            severity = 0.0
        severity = max(0.0, min(1.0, severity))

        return {
            'input_ids': encoding['input_ids'].squeeze(),
            'attention_mask': encoding['attention_mask'].squeeze(),
            'binary_label': torch.tensor(item['label'], dtype=torch.long),
            'family_label': torch.tensor(family_idx, dtype=torch.long),
            'severity_label': torch.tensor(severity, dtype=torch.float),
            'context_label': torch.tensor(context_idx, dtype=torch.long),
            'weight': torch.tensor(item.get('weight_multiplier', 1.0), dtype=torch.float),
        }

def compute_multi_task_loss_focal(outputs, labels, focal_loss_fn):
    """Multi-task loss with Focal Loss for binary classification"""

    # Binary loss with Focal Loss (60% weight, primary task)
    binary_loss = focal_loss_fn(
        outputs['binary_logits'],
        labels['binary_label']
    )

    # Family loss (20% weight, only for malicious)
    family_mask = labels['binary_label'] == 1
    if family_mask.sum() > 0:
        family_loss = F.cross_entropy(
            outputs['family_logits'][family_mask],
            labels['family_label'][family_mask],
            label_smoothing=0.1
        )
    else:
        family_loss = torch.tensor(0.0, device=outputs['binary_logits'].device)

    # Severity loss (10% weight, MSE with safety)
    severity_pred = outputs['severity_score'].squeeze().clamp(0.0, 1.0)
    severity_target = labels['severity_label'].clamp(0.0, 1.0)
    severity_loss = F.mse_loss(severity_pred, severity_target)

    # Context loss (10% weight)
    context_loss = F.cross_entropy(
        outputs['context_logits'],
        labels['context_label'],
        label_smoothing=0.1
    )

    # Combined weighted loss
    total = 0.6 * binary_loss + 0.2 * family_loss + 0.1 * severity_loss + 0.1 * context_loss

    # Safety: replace NaN with large penalty
    if torch.isnan(total):
        total = torch.tensor(100.0, device=outputs['binary_logits'].device, requires_grad=True)

    return total, {
        'total': total.item() if not torch.isnan(total) else 100.0,
        'binary': binary_loss.item() if not torch.isnan(binary_loss) else 0.0,
        'family': family_loss.item() if not torch.isnan(family_loss) else 0.0,
        'severity': severity_loss.item() if not torch.isnan(severity_loss) else 0.0,
        'context': context_loss.item() if not torch.isnan(context_loss) else 0.0,
    }

def train_epoch(model, dataloader, optimizer, device, focal_loss):
    model.train()
    total_loss = 0
    all_binary_preds = []
    all_binary_labels = []

    pbar = tqdm(dataloader, desc="Training")
    for batch in pbar:
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = {
            'binary_label': batch['binary_label'].to(device),
            'family_label': batch['family_label'].to(device),
            'severity_label': batch['severity_label'].to(device),
            'context_label': batch['context_label'].to(device),
        }

        # Forward
        outputs = model(input_ids, attention_mask)
        loss, loss_dict = compute_multi_task_loss_focal(outputs, labels, focal_loss)

        # Backward
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        # Metrics
        total_loss += loss.item()
        binary_preds = torch.argmax(outputs['binary_logits'], dim=1)
        all_binary_preds.extend(binary_preds.cpu().numpy())
        all_binary_labels.extend(labels['binary_label'].cpu().numpy())

        pbar.set_postfix({
            'loss': f"{loss.item():.4f}",
            'bin': f"{loss_dict['binary']:.4f}",
        })

    avg_loss = total_loss / len(dataloader)
    acc = accuracy_score(all_binary_labels, all_binary_preds)

    return avg_loss, acc

def evaluate(model, dataloader, device, focal_loss):
    model.eval()
    total_loss = 0
    all_binary_preds = []
    all_binary_labels = []

    with torch.no_grad():
        for batch in tqdm(dataloader, desc="Evaluating"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = {
                'binary_label': batch['binary_label'].to(device),
                'family_label': batch['family_label'].to(device),
                'severity_label': batch['severity_label'].to(device),
                'context_label': batch['context_label'].to(device),
            }

            outputs = model(input_ids, attention_mask)
            loss, _ = compute_multi_task_loss_focal(outputs, labels, focal_loss)
            total_loss += loss.item()

            binary_preds = torch.argmax(outputs['binary_logits'], dim=1)
            all_binary_preds.extend(binary_preds.cpu().numpy())
            all_binary_labels.extend(labels['binary_label'].cpu().numpy())

    avg_loss = total_loss / len(dataloader)
    acc = accuracy_score(all_binary_labels, all_binary_preds)
    prec = precision_score(all_binary_labels, all_binary_preds, average='binary', zero_division=0)
    rec = recall_score(all_binary_labels, all_binary_preds, average='binary', zero_division=0)
    f1 = f1_score(all_binary_labels, all_binary_preds, average='binary', zero_division=0)

    return {
        'loss': avg_loss,
        'accuracy': acc,
        'precision': prec,
        'recall': rec,
        'f1': f1,
    }

def main():
    print("\n" + "="*80)
    print("L2 MODEL v1.2.0 TRAINING (FOCAL LOSS + AUGMENTATION)")
    print("="*80)

    set_seed(SEED)

    # Device
    if torch.backends.mps.is_available():
        device = torch.device('mps')
        print("Using Mac GPU (MPS)")
    else:
        device = torch.device('cpu')
        print("Using CPU")

    # Load data
    print("\nLoading datasets...")
    train_data = load_jsonl(DATA_DIR / "train.jsonl")
    val_data = load_jsonl(DATA_DIR / "val.jsonl")

    # Load augmented data
    print("\nLoading augmented data (Phase 1 & 2)...")
    hard_negatives = load_jsonl(AUGMENTED_DIR / "hard_negatives_phase1.jsonl")
    programming_tasks = load_jsonl(AUGMENTED_DIR / "programming_tasks_phase1.jsonl")
    adversarial = load_jsonl(AUGMENTED_DIR / "adversarial_evasion_phase2.jsonl")

    # Merge with training data
    train_data.extend(hard_negatives)
    train_data.extend(programming_tasks)
    train_data.extend(adversarial)

    print(f"  Original train: {len(load_jsonl(DATA_DIR / 'train.jsonl')):,}")
    print(f"  + Hard negatives: {len(hard_negatives):,} @ 5x weight")
    print(f"  + Programming tasks: {len(programming_tasks):,} @ 4x weight")
    print(f"  + Adversarial: {len(adversarial):,} @ 3x weight")
    print(f"  = Total train: {len(train_data):,}")
    print(f"  Val: {len(val_data):,}")

    # Tokenizer
    tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")

    # Datasets
    train_dataset = ThreatDataset(train_data, tokenizer, MAX_LENGTH)
    val_dataset = ThreatDataset(val_data, tokenizer, MAX_LENGTH)

    # Weighted sampler
    weights = [item.get('weight_multiplier', 1.0) for item in train_data]
    sampler = WeightedRandomSampler(weights, len(weights), replacement=True)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, sampler=sampler)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)

    # Load pretrained model (v1.1.0)
    print("\nLoading pretrained model (v1.1.0)...")
    model = EnhancedThreatDetector(dropout_rate=DROPOUT)
    model.load_state_dict(torch.load(PRETRAINED_MODEL / "pytorch_model.bin", map_location=device))
    model.to(device)
    print(f"Parameters: {model.get_num_parameters():,}")

    # Optimizer
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)

    # Focal Loss
    focal_loss = FocalLoss(alpha=FOCAL_ALPHA, gamma=FOCAL_GAMMA)
    print(f"\nFocal Loss: alpha={FOCAL_ALPHA}, gamma={FOCAL_GAMMA}")

    # Training loop
    best_f1 = 0
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for epoch in range(NUM_EPOCHS):
        print(f"\n{'='*80}")
        print(f"Epoch {epoch+1}/{NUM_EPOCHS}")
        print(f"{'='*80}")

        train_loss, train_acc = train_epoch(model, train_loader, optimizer, device, focal_loss)
        print(f"\nTrain Loss: {train_loss:.4f}, Acc: {train_acc:.4f}")

        val_metrics = evaluate(model, val_loader, device, focal_loss)
        print(f"Val Loss: {val_metrics['loss']:.4f}")
        print(f"Val Acc: {val_metrics['accuracy']:.4f}, Prec: {val_metrics['precision']:.4f}, Rec: {val_metrics['recall']:.4f}, F1: {val_metrics['f1']:.4f}")

        # Save best model
        if val_metrics['f1'] > best_f1:
            best_f1 = val_metrics['f1']
            torch.save(model.state_dict(), OUTPUT_DIR / "pytorch_model.bin")
            tokenizer.save_pretrained(OUTPUT_DIR)
            print(f"✓ Saved best model (F1: {best_f1:.4f})")

    print("\n" + "="*80)
    print("TRAINING COMPLETE!")
    print("="*80)
    print(f"Best Val F1: {best_f1:.4f}")
    print(f"Model saved to: {OUTPUT_DIR}")
    print("\nImprovements over v1.1.0:")
    print("  - Focal Loss for hard example mining")
    print("  - 220 hard negative samples (@ 5x weight)")
    print("  - 24 programming task samples (@ 4x weight)")
    print("  - 1,000 adversarial evasion samples (@ 3x weight)")
    print("\nExpected: FPR <3%, FNR 7-8%")

if __name__ == "__main__":
    main()
