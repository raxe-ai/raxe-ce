#!/usr/bin/env python3
"""
Enhanced L2 Model Training Script
RAXE CE v1.1.0

Multi-output model to fix 62.8% FPR issue.
Expected improvement: FPR 62.8% → <5%, F1 66.6% → >85%
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
OUTPUT_DIR = Path("/Users/mh/github-raxe-ai/raxe-ce/models/l2_enhanced_v1.1.0")
BATCH_SIZE = 16  # Smaller for Mac GPU
LEARNING_RATE = 5e-6  # Lower LR for multi-task stability
NUM_EPOCHS = 3
MAX_LENGTH = 128  # Shorter for speed
WEIGHT_DECAY = 0.01
DROPOUT = 0.3
LABEL_SMOOTHING = 0.1
SEED = 42

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
        
        # Handle NaN values in indices (default to benign=7 for family, attack=3 for context)
        import math

        # Family index with NaN handling
        family_idx = item.get('family_idx', 7)
        if isinstance(family_idx, float):
            if math.isnan(family_idx):
                family_idx = 7  # Default to benign
            else:
                family_idx = int(family_idx)

        # Context index with NaN handling
        context_idx = item.get('context_idx', 1)
        if isinstance(context_idx, float):
            if math.isnan(context_idx):
                # Infer from label: malicious=attack, benign=conversational
                context_idx = 3 if item['label'] == 1 else 1
            else:
                context_idx = int(context_idx)

        # Severity with NaN handling
        severity = item.get('severity_score', 0.0)
        if isinstance(severity, float) and math.isnan(severity):
            severity = 0.0

        # Clamp severity to [0, 1] range to prevent NaN loss
        severity = max(0.0, min(1.0, severity))

        return {
            'input_ids': encoding['input_ids'].squeeze(),
            'attention_mask': encoding['attention_mask'].squeeze(),
            'binary_label': torch.tensor(item['label'], dtype=torch.long),
            'family_label': torch.tensor(family_idx, dtype=torch.long),
            'severity_label': torch.tensor(severity, dtype=torch.float),
            'context_label': torch.tensor(context_idx, dtype=torch.long),
            'weight': torch.tensor(item['weight_multiplier'], dtype=torch.float),
        }

def compute_multi_task_loss(outputs, labels, class_weights=None):
    """Multi-task loss with label smoothing and NaN safety checks"""

    # Binary loss (60% weight, primary task)
    binary_loss = F.cross_entropy(
        outputs['binary_logits'],
        labels['binary_label'],
        weight=class_weights,
        label_smoothing=LABEL_SMOOTHING
    )

    # Family loss (20% weight, only for malicious)
    family_mask = labels['binary_label'] == 1
    if family_mask.sum() > 0:
        family_loss = F.cross_entropy(
            outputs['family_logits'][family_mask],
            labels['family_label'][family_mask],
            label_smoothing=LABEL_SMOOTHING
        )
    else:
        family_loss = torch.tensor(0.0, device=outputs['binary_logits'].device)

    # Severity loss (10% weight, MSE with safety)
    # Clamp predictions to [0, 1] to prevent extreme values
    severity_pred = outputs['severity_score'].squeeze().clamp(0.0, 1.0)
    severity_target = labels['severity_label'].clamp(0.0, 1.0)
    severity_loss = F.mse_loss(severity_pred, severity_target)

    # Context loss (10% weight, NEW - forces context understanding)
    context_loss = F.cross_entropy(
        outputs['context_logits'],
        labels['context_label'],
        label_smoothing=LABEL_SMOOTHING
    )

    # Combined weighted loss with NaN check
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

def train_epoch(model, dataloader, optimizer, device, class_weights):
    model.train()
    total_loss = 0
    all_binary_preds = []
    all_binary_labels = []
    
    pbar = tqdm(dataloader, desc="Training")
    for batch in pbar:
        # Move to device
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
        loss, loss_dict = compute_multi_task_loss(outputs, labels, class_weights)
        
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
        
        # Update progress
        pbar.set_postfix({
            'loss': f"{loss.item():.4f}",
            'bin': f"{loss_dict['binary']:.4f}",
            'fam': f"{loss_dict['family']:.4f}",
        })
    
    # Epoch metrics
    avg_loss = total_loss / len(dataloader)
    acc = accuracy_score(all_binary_labels, all_binary_preds)
    
    return avg_loss, acc

def evaluate(model, dataloader, device, class_weights):
    model.eval()
    total_loss = 0
    all_binary_preds = []
    all_binary_labels = []
    all_family_preds = []
    all_family_labels = []
    
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
            loss, _ = compute_multi_task_loss(outputs, labels, class_weights)
            total_loss += loss.item()
            
            # Predictions
            binary_preds = torch.argmax(outputs['binary_logits'], dim=1)
            family_preds = torch.argmax(outputs['family_logits'], dim=1)
            
            all_binary_preds.extend(binary_preds.cpu().numpy())
            all_binary_labels.extend(labels['binary_label'].cpu().numpy())
            all_family_preds.extend(family_preds.cpu().numpy())
            all_family_labels.extend(labels['family_label'].cpu().numpy())
    
    # Metrics
    avg_loss = total_loss / len(dataloader)
    acc = accuracy_score(all_binary_labels, all_binary_preds)
    prec = precision_score(all_binary_labels, all_binary_preds, average='binary', zero_division=0)
    rec = recall_score(all_binary_labels, all_binary_preds, average='binary', zero_division=0)
    f1 = f1_score(all_binary_labels, all_binary_preds, average='binary', zero_division=0)
    
    # Family accuracy (only malicious samples)
    malicious_mask = np.array(all_binary_labels) == 1
    if malicious_mask.sum() > 0:
        family_acc = accuracy_score(
            np.array(all_family_labels)[malicious_mask],
            np.array(all_family_preds)[malicious_mask]
        )
    else:
        family_acc = 0.0
    
    return {
        'loss': avg_loss,
        'accuracy': acc,
        'precision': prec,
        'recall': rec,
        'f1': f1,
        'family_acc': family_acc,
    }

def main():
    print("\n" + "="*60)
    print("ENHANCED L2 MODEL TRAINING")
    print("RAXE CE v1.1.0")
    print("="*60)
    
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
    print(f"Train: {len(train_data)}, Val: {len(val_data)}")
    
    # Tokenizer
    tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")
    
    # Datasets
    train_dataset = ThreatDataset(train_data, tokenizer, MAX_LENGTH)
    val_dataset = ThreatDataset(val_data, tokenizer, MAX_LENGTH)
    
    # Weighted sampler for training
    weights = [item['weight_multiplier'] for item in train_data]
    sampler = WeightedRandomSampler(weights, len(weights), replacement=True)
    
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, sampler=sampler)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)
    
    # Model
    print("\nInitializing enhanced model...")
    model = EnhancedThreatDetector(dropout_rate=DROPOUT)
    model.to(device)
    print(f"Parameters: {model.get_num_parameters():,}")
    
    # Optimizer
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    
    # Class weights (penalize FP more)
    class_weights = torch.tensor([1.0, 0.8], device=device)
    
    # Training loop
    best_f1 = 0
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    for epoch in range(NUM_EPOCHS):
        print(f"\n{'='*60}")
        print(f"Epoch {epoch+1}/{NUM_EPOCHS}")
        print(f"{'='*60}")
        
        train_loss, train_acc = train_epoch(model, train_loader, optimizer, device, class_weights)
        print(f"\nTrain Loss: {train_loss:.4f}, Acc: {train_acc:.4f}")
        
        val_metrics = evaluate(model, val_loader, device, class_weights)
        print(f"Val Loss: {val_metrics['loss']:.4f}")
        print(f"Val Acc: {val_metrics['accuracy']:.4f}, Prec: {val_metrics['precision']:.4f}, Rec: {val_metrics['recall']:.4f}, F1: {val_metrics['f1']:.4f}")
        print(f"Family Acc: {val_metrics['family_acc']:.4f}")
        
        # Save best model
        if val_metrics['f1'] > best_f1:
            best_f1 = val_metrics['f1']
            torch.save(model.state_dict(), OUTPUT_DIR / "pytorch_model.bin")
            tokenizer.save_pretrained(OUTPUT_DIR)
            print(f"✓ Saved best model (F1: {best_f1:.4f})")
    
    print("\n" + "="*60)
    print("TRAINING COMPLETE!")
    print("="*60)
    print(f"Best Val F1: {best_f1:.4f}")
    print(f"Model saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
