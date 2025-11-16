#!/usr/bin/env python3
"""
Training Script for L2 Unified Model
RAXE CE v1.0.0

Trains a DistilBERT-based binary classifier to detect malicious prompts
across all threat families (CMD, PII, JB, HC).

Target Performance:
- Accuracy: >85%
- Precision: >0.88
- Recall: >0.82
- F1 Score: >0.85
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime

import torch
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, roc_auc_score, roc_curve
)
from transformers import (
    DistilBertTokenizer,
    DistilBertForSequenceClassification,
    Trainer,
    TrainingArguments,
    EarlyStoppingCallback,
)
from datasets import Dataset
from tqdm import tqdm


# Configuration
@dataclass
class Config:
    # Paths
    data_dir: Path = Path("/Users/mh/github-raxe-ai/raxe-ce/data/l2_training_final")
    output_dir: Path = Path("/Users/mh/github-raxe-ai/raxe-ce/models/l2_unified_v1.0.0")

    # Model
    model_name: str = "distilbert-base-uncased"
    num_labels: int = 2
    max_length: int = 512

    # Training
    learning_rate: float = 2e-5
    batch_size: int = 32
    num_epochs: int = 3
    warmup_steps: int = 500
    weight_decay: float = 0.01
    fp16: bool = False  # Set to True if GPU available

    # Early stopping
    early_stopping_patience: int = 2
    early_stopping_threshold: float = 0.01

    # Random seed for reproducibility
    seed: int = 42

    # Evaluation
    eval_steps: int = 500
    save_steps: int = 1000
    logging_steps: int = 100


def set_seed(seed: int):
    """Set random seed for reproducibility."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if torch.backends.mps.is_available():
        # MPS uses the same seed as CPU
        torch.mps.manual_seed(seed)


def load_jsonl(file_path: Path) -> List[Dict]:
    """Load JSONL file."""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def prepare_datasets(config: Config) -> Tuple[Dataset, Dataset, Dataset]:
    """Load and prepare datasets for training."""
    print("\n" + "="*60)
    print("PREPARING DATASETS")
    print("="*60)

    # Load data
    train_data = load_jsonl(config.data_dir / "train.jsonl")
    val_data = load_jsonl(config.data_dir / "val.jsonl")
    test_data = load_jsonl(config.data_dir / "test.jsonl")

    print(f"Train: {len(train_data)} samples")
    print(f"Val: {len(val_data)} samples")
    print(f"Test: {len(test_data)} samples")

    # Convert to HuggingFace Dataset
    train_dataset = Dataset.from_dict({
        'text': [item['text'] for item in train_data],
        'label': [item['label'] for item in train_data],
        'family': [item['family'] for item in train_data],
    })

    val_dataset = Dataset.from_dict({
        'text': [item['text'] for item in val_data],
        'label': [item['label'] for item in val_data],
        'family': [item['family'] for item in val_data],
    })

    test_dataset = Dataset.from_dict({
        'text': [item['text'] for item in test_data],
        'label': [item['label'] for item in test_data],
        'family': [item['family'] for item in test_data],
    })

    return train_dataset, val_dataset, test_dataset


def tokenize_datasets(
    train_dataset: Dataset,
    val_dataset: Dataset,
    test_dataset: Dataset,
    tokenizer: DistilBertTokenizer,
    config: Config
) -> Tuple[Dataset, Dataset, Dataset]:
    """Tokenize all datasets."""
    print("\n" + "="*60)
    print("TOKENIZING DATASETS")
    print("="*60)

    def tokenize_function(examples):
        return tokenizer(
            examples['text'],
            padding='max_length',
            truncation=True,
            max_length=config.max_length,
            return_tensors=None
        )

    # Tokenize
    train_tokenized = train_dataset.map(tokenize_function, batched=True)
    val_tokenized = val_dataset.map(tokenize_function, batched=True)
    test_tokenized = test_dataset.map(tokenize_function, batched=True)

    # Set format for PyTorch
    train_tokenized.set_format('torch', columns=['input_ids', 'attention_mask', 'label'])
    val_tokenized.set_format('torch', columns=['input_ids', 'attention_mask', 'label'])
    test_tokenized.set_format('torch', columns=['input_ids', 'attention_mask', 'label'])

    print("✓ Tokenization complete")

    return train_tokenized, val_tokenized, test_tokenized


def compute_metrics(pred):
    """Compute evaluation metrics."""
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)

    accuracy = accuracy_score(labels, preds)
    precision = precision_score(labels, preds, average='binary')
    recall = recall_score(labels, preds, average='binary')
    f1 = f1_score(labels, preds, average='binary')

    return {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
    }


def train_model(
    train_dataset: Dataset,
    val_dataset: Dataset,
    tokenizer: DistilBertTokenizer,
    config: Config
) -> Tuple[DistilBertForSequenceClassification, Dict]:
    """Train the DistilBERT model."""
    print("\n" + "="*60)
    print("TRAINING MODEL")
    print("="*60)

    # Initialize model
    model = DistilBertForSequenceClassification.from_pretrained(
        config.model_name,
        num_labels=config.num_labels,
    )

    # Training arguments
    training_args = TrainingArguments(
        output_dir=str(config.output_dir / "checkpoints"),
        num_train_epochs=config.num_epochs,
        per_device_train_batch_size=config.batch_size,
        per_device_eval_batch_size=config.batch_size,
        learning_rate=config.learning_rate,
        warmup_steps=config.warmup_steps,
        weight_decay=config.weight_decay,
        eval_strategy="steps",
        eval_steps=config.eval_steps,
        save_strategy="steps",
        save_steps=config.save_steps,
        logging_steps=config.logging_steps,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        fp16=config.fp16,
        seed=config.seed,
        report_to="none",  # Disable wandb/tensorboard
    )

    # Initialize Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[
            EarlyStoppingCallback(
                early_stopping_patience=config.early_stopping_patience,
                early_stopping_threshold=config.early_stopping_threshold,
            )
        ],
    )

    # Train
    print("\nStarting training...")
    start_time = time.time()
    train_result = trainer.train()
    training_time = time.time() - start_time

    print(f"\n✓ Training complete in {training_time/60:.2f} minutes")

    # Save model
    trainer.save_model(str(config.output_dir))
    tokenizer.save_pretrained(str(config.output_dir))

    print(f"✓ Model saved to {config.output_dir}")

    # Training stats
    training_stats = {
        'training_time_seconds': training_time,
        'training_time_minutes': training_time / 60,
        'total_steps': train_result.global_step,
        'train_loss': train_result.training_loss,
    }

    return model, training_stats


def evaluate_model(
    model: DistilBertForSequenceClassification,
    test_dataset: Dataset,
    tokenizer: DistilBertTokenizer,
    config: Config
) -> Dict:
    """Evaluate model on test set."""
    print("\n" + "="*60)
    print("EVALUATING MODEL ON TEST SET")
    print("="*60)

    model.eval()
    # Use same device detection as main
    if torch.cuda.is_available():
        device = torch.device('cuda')
    elif torch.backends.mps.is_available():
        device = torch.device('mps')
    else:
        device = torch.device('cpu')
    model.to(device)

    all_labels = []
    all_preds = []
    all_probs = []

    # Evaluate
    with torch.no_grad():
        for i in tqdm(range(0, len(test_dataset), config.batch_size), desc="Evaluating"):
            batch = test_dataset[i:i+config.batch_size]

            inputs = {
                'input_ids': batch['input_ids'].to(device),
                'attention_mask': batch['attention_mask'].to(device),
            }

            outputs = model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)
            preds = torch.argmax(logits, dim=-1)

            all_labels.extend(batch['label'].cpu().numpy())
            all_preds.extend(preds.cpu().numpy())
            all_probs.extend(probs[:, 1].cpu().numpy())  # Probability of malicious class

    # Calculate metrics
    accuracy = accuracy_score(all_labels, all_preds)
    precision = precision_score(all_labels, all_preds, average='binary')
    recall = recall_score(all_labels, all_preds, average='binary')
    f1 = f1_score(all_labels, all_preds, average='binary')
    auc_roc = roc_auc_score(all_labels, all_probs)

    print("\n" + "="*60)
    print("TEST SET RESULTS")
    print("="*60)
    print(f"Accuracy:  {accuracy:.4f} ({accuracy*100:.2f}%)")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print(f"AUC-ROC:   {auc_roc:.4f}")

    # Check targets
    print("\n" + "="*60)
    print("TARGET VALIDATION")
    print("="*60)
    target_met = {
        'accuracy': accuracy >= 0.85,
        'precision': precision >= 0.88,
        'recall': recall >= 0.82,
        'f1': f1 >= 0.85,
    }

    for metric, met in target_met.items():
        status = "✓ PASS" if met else "✗ FAIL"
        print(f"{metric.capitalize()}: {status}")

    all_targets_met = all(target_met.values())
    print(f"\nOverall: {'✓ ALL TARGETS MET' if all_targets_met else '✗ SOME TARGETS NOT MET'}")

    # Classification report
    print("\n" + "="*60)
    print("CLASSIFICATION REPORT")
    print("="*60)
    print(classification_report(
        all_labels, all_preds,
        target_names=['Benign', 'Malicious'],
        digits=4
    ))

    # Confusion matrix
    cm = confusion_matrix(all_labels, all_preds)

    return {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'auc_roc': auc_roc,
        'confusion_matrix': cm.tolist(),
        'all_labels': all_labels,
        'all_preds': all_preds,
        'all_probs': all_probs,
        'targets_met': target_met,
        'all_targets_met': all_targets_met,
    }


def evaluate_per_family(
    model: DistilBertForSequenceClassification,
    test_dataset: Dataset,
    config: Config
) -> Dict:
    """Evaluate model performance per threat family."""
    print("\n" + "="*60)
    print("PER-FAMILY PERFORMANCE")
    print("="*60)

    model.eval()
    # Use same device detection as main
    if torch.cuda.is_available():
        device = torch.device('cuda')
    elif torch.backends.mps.is_available():
        device = torch.device('mps')
    else:
        device = torch.device('cpu')
    model.to(device)

    # Get predictions for all test samples
    all_labels = []
    all_preds = []
    all_families = []

    with torch.no_grad():
        for i in range(0, len(test_dataset), config.batch_size):
            batch = test_dataset[i:i+config.batch_size]

            inputs = {
                'input_ids': batch['input_ids'].to(device),
                'attention_mask': batch['attention_mask'].to(device),
            }

            outputs = model(**inputs)
            logits = outputs.logits
            preds = torch.argmax(logits, dim=-1)

            all_labels.extend(batch['label'].cpu().numpy())
            all_preds.extend(preds.cpu().numpy())
            # Get family strings from original dataset
            for j in range(len(batch['label'])):
                idx = i + j
                all_families.append(test_dataset[idx]['family'])

    # Calculate metrics per family
    family_results = {}
    families = ['CMD', 'PII', 'JB', 'HC']

    for family in families:
        # Get indices for this family
        family_indices = [i for i, f in enumerate(all_families) if f == family]

        if not family_indices:
            continue

        # Get labels and predictions for this family
        family_labels = [all_labels[i] for i in family_indices]
        family_preds = [all_preds[i] for i in family_indices]

        # Calculate metrics
        accuracy = accuracy_score(family_labels, family_preds)
        precision = precision_score(family_labels, family_preds, average='binary', zero_division=0)
        recall = recall_score(family_labels, family_preds, average='binary', zero_division=0)
        f1 = f1_score(family_labels, family_preds, average='binary', zero_division=0)

        family_results[family] = {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'num_samples': len(family_indices),
        }

        print(f"\n{family}:")
        print(f"  Samples:   {len(family_indices)}")
        print(f"  Accuracy:  {accuracy:.4f} ({accuracy*100:.2f}%)")
        print(f"  Precision: {precision:.4f}")
        print(f"  Recall:    {recall:.4f}")
        print(f"  F1 Score:  {f1:.4f}")

    return family_results


def plot_confusion_matrix(cm: np.ndarray, output_path: Path):
    """Plot and save confusion matrix."""
    plt.figure(figsize=(8, 6))
    sns.heatmap(
        cm, annot=True, fmt='d', cmap='Blues',
        xticklabels=['Benign', 'Malicious'],
        yticklabels=['Benign', 'Malicious'],
    )
    plt.title('Confusion Matrix - L2 Unified Model')
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Confusion matrix saved to {output_path}")


def plot_roc_curve(labels: List[int], probs: List[float], output_path: Path):
    """Plot and save ROC curve."""
    fpr, tpr, thresholds = roc_curve(labels, probs)
    auc = roc_auc_score(labels, probs)

    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, linewidth=2, label=f'ROC Curve (AUC = {auc:.4f})')
    plt.plot([0, 1], [0, 1], 'k--', linewidth=1, label='Random Classifier')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC Curve - L2 Unified Model')
    plt.legend(loc='lower right')
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ ROC curve saved to {output_path}")


def save_training_report(
    config: Config,
    training_stats: Dict,
    eval_results: Dict,
    family_results: Dict
):
    """Save comprehensive training report."""
    report_path = config.output_dir / "training_report.md"

    with open(report_path, 'w') as f:
        f.write("# L2 Unified Model Training Report\n\n")
        f.write("**RAXE CE v1.0.0**\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("## Model Specifications\n\n")
        f.write(f"- **Architecture:** {config.model_name}\n")
        f.write(f"- **Task:** Binary sequence classification (malicious vs benign)\n")
        f.write(f"- **Training samples:** 60,000\n")
        f.write(f"- **Validation samples:** 10,000\n")
        f.write(f"- **Test samples:** 10,000\n")
        f.write(f"- **Threat families:** CMD, PII, JB, HC\n\n")

        f.write("## Training Configuration\n\n")
        f.write(f"- **Learning rate:** {config.learning_rate}\n")
        f.write(f"- **Batch size:** {config.batch_size}\n")
        f.write(f"- **Epochs:** {config.num_epochs}\n")
        f.write(f"- **Warmup steps:** {config.warmup_steps}\n")
        f.write(f"- **Weight decay:** {config.weight_decay}\n")
        f.write(f"- **Max sequence length:** {config.max_length}\n")
        f.write(f"- **Random seed:** {config.seed}\n\n")

        f.write("## Training Results\n\n")
        f.write(f"- **Training time:** {training_stats['training_time_minutes']:.2f} minutes\n")
        f.write(f"- **Total steps:** {training_stats['total_steps']}\n")
        f.write(f"- **Final training loss:** {training_stats['train_loss']:.4f}\n\n")

        f.write("## Test Set Performance\n\n")
        f.write(f"- **Accuracy:** {eval_results['accuracy']:.4f} ({eval_results['accuracy']*100:.2f}%)\n")
        f.write(f"- **Precision:** {eval_results['precision']:.4f}\n")
        f.write(f"- **Recall:** {eval_results['recall']:.4f}\n")
        f.write(f"- **F1 Score:** {eval_results['f1']:.4f}\n")
        f.write(f"- **AUC-ROC:** {eval_results['auc_roc']:.4f}\n\n")

        f.write("### Target Validation\n\n")
        for metric, met in eval_results['targets_met'].items():
            status = "✓ PASS" if met else "✗ FAIL"
            f.write(f"- {metric.capitalize()}: {status}\n")
        f.write(f"\n**Overall:** {'✓ ALL TARGETS MET' if eval_results['all_targets_met'] else '✗ SOME TARGETS NOT MET'}\n\n")

        f.write("## Per-Family Performance\n\n")
        for family, results in family_results.items():
            f.write(f"### {family}\n\n")
            f.write(f"- **Samples:** {results['num_samples']}\n")
            f.write(f"- **Accuracy:** {results['accuracy']:.4f} ({results['accuracy']*100:.2f}%)\n")
            f.write(f"- **Precision:** {results['precision']:.4f}\n")
            f.write(f"- **Recall:** {results['recall']:.4f}\n")
            f.write(f"- **F1 Score:** {results['f1']:.4f}\n\n")

        f.write("## Confusion Matrix\n\n")
        cm = eval_results['confusion_matrix']
        f.write("```\n")
        f.write("               Predicted\n")
        f.write("             Benign  Malicious\n")
        f.write(f"True Benign    {cm[0][0]:5d}  {cm[0][1]:5d}\n")
        f.write(f"     Malicious {cm[1][0]:5d}  {cm[1][1]:5d}\n")
        f.write("```\n\n")

        f.write("## Model Files\n\n")
        f.write("- `pytorch_model.bin` - PyTorch model weights\n")
        f.write("- `config.json` - Model configuration\n")
        f.write("- `vocab.txt` - Tokenizer vocabulary\n")
        f.write("- `tokenizer_config.json` - Tokenizer configuration\n")
        f.write("- `confusion_matrix.png` - Confusion matrix visualization\n")
        f.write("- `roc_curve.png` - ROC curve visualization\n")
        f.write("- `training_report.md` - This report\n\n")

        f.write("## Next Steps\n\n")
        f.write("1. Convert model to ONNX format\n")
        f.write("2. Optimize for CPU inference (<1ms latency)\n")
        f.write("3. Benchmark inference performance\n")
        f.write("4. Integrate with RAXE CE scanner\n\n")

    print(f"✓ Training report saved to {report_path}")


def main():
    """Main training workflow."""
    print("\n" + "#"*60)
    print("# L2 UNIFIED MODEL TRAINING")
    print("# RAXE CE v1.0.0")
    print("#"*60)

    # Initialize config
    config = Config()

    # Create output directory
    config.output_dir.mkdir(parents=True, exist_ok=True)

    # Set seed
    set_seed(config.seed)

    # Check for GPU (CUDA or MPS for Mac)
    if torch.cuda.is_available():
        device = torch.device('cuda')
        print(f"\nUsing device: {device}")
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        config.fp16 = True  # Enable mixed precision on CUDA
    elif torch.backends.mps.is_available():
        device = torch.device('mps')
        print(f"\nUsing device: {device} (Apple Metal Performance Shaders)")
        print("GPU acceleration enabled on Mac")
        # Note: fp16 not fully supported on MPS yet, keeping it disabled
    else:
        device = torch.device('cpu')
        print(f"\nUsing device: {device}")

    # Prepare datasets
    train_dataset, val_dataset, test_dataset = prepare_datasets(config)

    # Initialize tokenizer
    print("\nLoading tokenizer...")
    tokenizer = DistilBertTokenizer.from_pretrained(config.model_name)

    # Tokenize datasets
    train_tokenized, val_tokenized, test_tokenized = tokenize_datasets(
        train_dataset, val_dataset, test_dataset, tokenizer, config
    )

    # Train model
    model, training_stats = train_model(train_tokenized, val_tokenized, tokenizer, config)

    # Evaluate on test set
    eval_results = evaluate_model(model, test_tokenized, tokenizer, config)

    # Evaluate per family
    family_results = evaluate_per_family(model, test_tokenized, config)

    # Plot confusion matrix
    cm = np.array(eval_results['confusion_matrix'])
    plot_confusion_matrix(cm, config.output_dir / "confusion_matrix.png")

    # Plot ROC curve
    plot_roc_curve(
        eval_results['all_labels'],
        eval_results['all_probs'],
        config.output_dir / "roc_curve.png"
    )

    # Save training report
    save_training_report(config, training_stats, eval_results, family_results)

    # Save evaluation results as JSON
    results_json = {
        'model_version': '1.0.0',
        'created_at': datetime.now().isoformat(),
        'training_stats': training_stats,
        'test_metrics': {
            'accuracy': eval_results['accuracy'],
            'precision': eval_results['precision'],
            'recall': eval_results['recall'],
            'f1': eval_results['f1'],
            'auc_roc': eval_results['auc_roc'],
        },
        'confusion_matrix': eval_results['confusion_matrix'],
        'targets_met': eval_results['targets_met'],
        'all_targets_met': eval_results['all_targets_met'],
        'family_results': family_results,
    }

    with open(config.output_dir / "evaluation_results.json", 'w') as f:
        json.dump(results_json, f, indent=2)

    print("\n" + "#"*60)
    print("# TRAINING COMPLETE!")
    print("#"*60)
    print(f"\nModel saved to: {config.output_dir}")
    print(f"\nTest Accuracy: {eval_results['accuracy']*100:.2f}%")
    print(f"F1 Score: {eval_results['f1']:.4f}")
    print(f"\nAll files saved to: {config.output_dir}")


if __name__ == "__main__":
    main()
