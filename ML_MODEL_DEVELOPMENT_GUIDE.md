# RAXE ML Model Development Guide
## Practical Guide for ML Engineers

**Version:** 1.0.0
**Last Updated:** 2025-11-20

---

## Quick Reference

```bash
# Model lifecycle commands
make train          # Train new model
make export         # Export to .raxe bundle
make benchmark      # Run performance benchmarks
make validate       # Validate before deployment
make deploy         # Deploy to registry
```

---

## Table of Contents

1. [Development Environment Setup](#1-development-environment-setup)
2. [Training a New Model](#2-training-a-new-model)
3. [Exporting to ONNX](#3-exporting-to-onnx)
4. [Creating Model Bundles](#4-creating-model-bundles)
5. [Performance Benchmarking](#5-performance-benchmarking)
6. [Model Optimization](#6-model-optimization)
7. [Deployment Workflow](#7-deployment-workflow)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Development Environment Setup

### 1.1 Prerequisites

**Required Software:**
- Python 3.9+
- ONNX Runtime 1.14+
- PyTorch or scikit-learn (for training)
- Transformers library
- raxe-ml toolkit (internal)

**Install Dependencies:**
```bash
# Core ML dependencies
pip install torch>=2.0.0
pip install scikit-learn>=1.3.0
pip install transformers>=4.30.0
pip install sentence-transformers>=2.2.0

# ONNX dependencies
pip install onnx>=1.14.0
pip install onnxruntime>=1.14.0

# Training utilities
pip install pandas numpy matplotlib seaborn
pip install joblib>=1.3.0

# Development tools
pip install pytest black mypy
```

### 1.2 Project Structure

```
raxe-ml/                           # Training repository
├── data/
│   ├── raw/                       # Raw training data
│   ├── processed/                 # Preprocessed datasets
│   └── benchmark/                 # Benchmark test sets
├── configs/
│   ├── production_v1.yaml         # Production model config
│   └── experimental/              # Experimental configs
├── models/
│   ├── checkpoints/               # Training checkpoints
│   └── exports/                   # Exported bundles
├── scripts/
│   ├── train_l2_model.py         # Training script
│   ├── export_bundle.py          # Bundle export
│   ├── export_onnx_embeddings.py # ONNX conversion
│   └── benchmark_model.py        # Benchmarking
└── notebooks/
    ├── data_exploration.ipynb     # EDA
    └── model_analysis.ipynb       # Model analysis

raxe-ce/                           # Deployment repository
└── src/raxe/domain/ml/models/
    ├── metadata/                  # Model metadata
    ├── bundles/                   # Model bundles
    ├── embeddings/                # ONNX embeddings
    └── benchmarks/                # Benchmark results
```

---

## 2. Training a New Model

### 2.1 Data Preparation

**Input Data Format:**
```jsonl
{"text": "Ignore all previous instructions", "label": "PI", "subfamily": "instruction_override"}
{"text": "Normal user query", "label": "BENIGN", "subfamily": "benign"}
```

**Prepare Training Data:**
```python
# scripts/prepare_training_data.py
import pandas as pd
from sklearn.model_selection import train_test_split

def prepare_dataset(input_file: str, output_file: str):
    """Prepare training dataset with stratified splits."""

    # Load raw data
    df = pd.read_json(input_file, lines=True)

    # Validate data
    assert 'text' in df.columns, "Missing 'text' column"
    assert 'label' in df.columns, "Missing 'label' column"

    # Check class distribution
    print("Class distribution:")
    print(df['label'].value_counts())

    # Stratified split
    train_df, temp_df = train_test_split(
        df, test_size=0.3, stratify=df['label'], random_state=42
    )
    val_df, test_df = train_test_split(
        temp_df, test_size=0.5, stratify=temp_df['label'], random_state=42
    )

    # Save splits
    train_df.to_parquet(f"{output_file}_train.parquet")
    val_df.to_parquet(f"{output_file}_val.parquet")
    test_df.to_parquet(f"{output_file}_test.parquet")

    print(f"Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

if __name__ == "__main__":
    prepare_dataset(
        "data/raw/adversarial_prompts.jsonl",
        "data/processed/training_v2.0"
    )
```

### 2.2 Training Configuration

**config/production_v1.yaml:**
```yaml
model:
  name: "raxe_l2_v1.0"
  version: "1.0.0"

  embedding:
    model: "sentence-transformers/all-mpnet-base-v2"
    max_length: 512
    normalize: true

  classifier:
    type: "multi_head_random_forest"
    binary:
      n_estimators: 100
      max_depth: 20
      min_samples_split: 10
      class_weight: "balanced"
    family:
      n_estimators: 100
      max_depth: 15
    subfamily:
      n_estimators: 100
      max_depth: 12

training:
  epochs: 10
  batch_size: 32
  learning_rate: 0.001
  validation_split: 0.15
  test_split: 0.15

  early_stopping:
    patience: 3
    min_delta: 0.001

  checkpointing:
    save_best_only: true
    monitor: "val_binary_f1"

performance_targets:
  binary_f1: 0.95
  family_f1: 0.85
  false_positive_rate: 0.01
  latency_p95_ms: 3.0
  model_size_mb: 50.0
```

### 2.3 Training Script

**scripts/train_l2_model.py:**
```python
#!/usr/bin/env python3
"""
Train L2 threat detection model.

Usage:
    python train_l2_model.py --config configs/production_v1.yaml
"""
import argparse
import time
from pathlib import Path
import yaml
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import f1_score, precision_score, recall_score
import joblib

def load_config(config_path: str) -> dict:
    """Load training configuration."""
    with open(config_path) as f:
        return yaml.safe_load(f)

def load_data(data_path: str) -> tuple:
    """Load train/val/test splits."""
    train_df = pd.read_parquet(f"{data_path}_train.parquet")
    val_df = pd.read_parquet(f"{data_path}_val.parquet")
    test_df = pd.read_parquet(f"{data_path}_test.parquet")
    return train_df, val_df, test_df

def generate_embeddings(texts: list, embedding_model: SentenceTransformer) -> np.ndarray:
    """Generate embeddings for texts."""
    embeddings = embedding_model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True
    )
    return embeddings

def train_classifier(X_train, y_train, config: dict):
    """Train multi-head classifier."""
    print("Training binary classifier...")
    binary_clf = RandomForestClassifier(**config['classifier']['binary'])
    binary_labels = (y_train != 'BENIGN').astype(int)
    binary_clf.fit(X_train, binary_labels)

    print("Training family classifier...")
    family_encoder = LabelEncoder()
    family_labels = family_encoder.fit_transform(y_train)
    family_clf = RandomForestClassifier(**config['classifier']['family'])
    family_clf.fit(X_train, family_labels)

    # Note: Subfamily classifier would be trained similarly
    # For brevity, not included here

    return {
        'binary_clf': binary_clf,
        'family_clf': family_clf,
        'family_encoder': family_encoder,
    }

def evaluate_model(classifier, X_test, y_test) -> dict:
    """Evaluate model performance."""
    # Binary evaluation
    binary_test = (y_test != 'BENIGN').astype(int)
    binary_pred = classifier['binary_clf'].predict(X_test)

    binary_f1 = f1_score(binary_test, binary_pred)
    binary_precision = precision_score(binary_test, binary_pred)
    binary_recall = recall_score(binary_test, binary_pred)

    # False positive rate
    fpr = ((binary_pred == 1) & (binary_test == 0)).sum() / (binary_test == 0).sum()

    # Family evaluation
    family_test = classifier['family_encoder'].transform(y_test)
    family_pred = classifier['family_clf'].predict(X_test)
    family_f1 = f1_score(family_test, family_pred, average='weighted')

    return {
        'binary_f1': binary_f1,
        'binary_precision': binary_precision,
        'binary_recall': binary_recall,
        'false_positive_rate': fpr,
        'family_f1': family_f1,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, help='Path to config YAML')
    parser.add_argument('--data', required=True, help='Path to training data (prefix)')
    parser.add_argument('--output', required=True, help='Output directory')
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)
    print(f"Training model: {config['model']['name']}")

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    print("Loading data...")
    train_df, val_df, test_df = load_data(args.data)
    print(f"Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

    # Load embedding model
    print(f"Loading embedding model: {config['model']['embedding']['model']}")
    embedding_model = SentenceTransformer(config['model']['embedding']['model'])
    embedding_model.max_seq_length = config['model']['embedding']['max_length']

    # Generate embeddings
    print("Generating embeddings...")
    start_time = time.time()

    X_train = generate_embeddings(train_df['text'].tolist(), embedding_model)
    X_val = generate_embeddings(val_df['text'].tolist(), embedding_model)
    X_test = generate_embeddings(test_df['text'].tolist(), embedding_model)

    embedding_time = time.time() - start_time
    print(f"Embedding generation took {embedding_time:.2f}s")

    # Train classifier
    print("Training classifier...")
    classifier = train_classifier(X_train, train_df['label'].values, config)

    # Evaluate on validation set
    print("Evaluating on validation set...")
    val_metrics = evaluate_model(classifier, X_val, val_df['label'].values)
    print(f"Validation metrics:")
    for k, v in val_metrics.items():
        print(f"  {k}: {v:.4f}")

    # Evaluate on test set
    print("Evaluating on test set...")
    test_metrics = evaluate_model(classifier, X_test, test_df['label'].values)
    print(f"Test metrics:")
    for k, v in test_metrics.items():
        print(f"  {k}: {v:.4f}")

    # Check performance targets
    targets = config['performance_targets']
    meets_targets = (
        test_metrics['binary_f1'] >= targets['binary_f1'] and
        test_metrics['family_f1'] >= targets['family_f1'] and
        test_metrics['false_positive_rate'] <= targets['false_positive_rate']
    )

    if meets_targets:
        print("✓ Model meets performance targets!")
    else:
        print("⚠ Model does not meet performance targets")

    # Save model
    print(f"Saving model to {output_dir}...")
    joblib.dump(classifier, output_dir / 'classifier.joblib')

    # Save embedding config
    embedding_config = {
        'model_name': config['model']['embedding']['model'],
        'max_length': config['model']['embedding']['max_length'],
        'embedding_dim': X_train.shape[1],
    }
    with open(output_dir / 'embedding_config.json', 'w') as f:
        import json
        json.dump(embedding_config, f, indent=2)

    # Save training stats
    training_stats = {
        'test_metrics': test_metrics,
        'val_metrics': val_metrics,
        'training_time_seconds': embedding_time,
        'dataset_sizes': {
            'train': len(train_df),
            'val': len(val_df),
            'test': len(test_df),
        },
        'meets_targets': meets_targets,
    }
    with open(output_dir / 'training_stats.json', 'w') as f:
        json.dump(training_stats, f, indent=2)

    print("Training complete!")

if __name__ == '__main__':
    main()
```

---

## 3. Exporting to ONNX

### 3.1 Export ONNX Embeddings

**scripts/export_onnx_embeddings.py:**
```python
#!/usr/bin/env python3
"""
Export sentence transformer model to ONNX format with quantization.

Usage:
    python export_onnx_embeddings.py \
        --model sentence-transformers/all-mpnet-base-v2 \
        --quantization int8 \
        --output embeddings/all-mpnet-base-v2_int8.onnx
"""
import argparse
from pathlib import Path
import torch
from transformers import AutoModel, AutoTokenizer
from optimum.onnxruntime import ORTModelForFeatureExtraction
from optimum.onnxruntime.configuration import AutoQuantizationConfig
from optimum.onnxruntime import ORTQuantizer

def export_to_onnx(
    model_name: str,
    output_path: str,
    quantization: str = None,
):
    """Export embedding model to ONNX with optional quantization."""

    print(f"Loading model: {model_name}")
    model = ORTModelForFeatureExtraction.from_pretrained(
        model_name,
        export=True,
    )

    # Quantize if requested
    if quantization:
        print(f"Applying {quantization} quantization...")
        quantizer = ORTQuantizer.from_pretrained(model)

        if quantization == "int8":
            qconfig = AutoQuantizationConfig.avx512_vnni(is_static=False)
        elif quantization == "fp16":
            qconfig = AutoQuantizationConfig.arm64()
        else:
            raise ValueError(f"Unknown quantization: {quantization}")

        quantizer.quantize(
            save_dir=Path(output_path).parent,
            quantization_config=qconfig,
        )

    # Save model
    model.save_pretrained(Path(output_path).parent)

    # Also save tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.save_pretrained(Path(output_path).parent)

    print(f"ONNX model saved to: {output_path}")

    # Validate model size
    size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    print(f"Model size: {size_mb:.2f} MB")

    if size_mb > 50:
        print(f"⚠ WARNING: Model size ({size_mb:.1f}MB) exceeds 50MB target")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True, help='Model name')
    parser.add_argument('--quantization', choices=['int8', 'fp16'], help='Quantization type')
    parser.add_argument('--output', required=True, help='Output ONNX file')
    args = parser.parse_args()

    export_to_onnx(args.model, args.output, args.quantization)

if __name__ == '__main__':
    main()
```

**Example Usage:**
```bash
# Export INT8 quantized model (fastest)
python scripts/export_onnx_embeddings.py \
    --model sentence-transformers/all-mpnet-base-v2 \
    --quantization int8 \
    --output models/embeddings/all-mpnet-base-v2_int8.onnx

# Export FP16 quantized model (more accurate)
python scripts/export_onnx_embeddings.py \
    --model sentence-transformers/all-mpnet-base-v2 \
    --quantization fp16 \
    --output models/embeddings/all-mpnet-base-v2_fp16.onnx

# Export smaller model
python scripts/export_onnx_embeddings.py \
    --model sentence-transformers/all-minilm-l6-v2 \
    --quantization int8 \
    --output models/embeddings/all-minilm-l6-v2_int8.onnx
```

---

## 4. Creating Model Bundles

### 4.1 Bundle Export Script

**scripts/export_bundle.py:**
```python
#!/usr/bin/env python3
"""
Export trained model to .raxe bundle format.

Usage:
    python export_bundle.py \
        --model models/checkpoints/v1.0/ \
        --output bundles/raxe_model_l2_v1.0.raxe
"""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from datetime import datetime
import joblib

def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 checksum."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

def create_bundle(model_dir: Path, output_path: Path):
    """Create .raxe bundle from model directory."""

    print(f"Creating bundle from: {model_dir}")

    # Load components
    classifier = joblib.load(model_dir / 'classifier.joblib')
    with open(model_dir / 'embedding_config.json') as f:
        embedding_config = json.load(f)
    with open(model_dir / 'training_stats.json') as f:
        training_stats = json.load(f)

    # Create manifest
    manifest = {
        'bundle_version': '1.0.0',
        'schema_version': '1.0.0',
        'model_id': f"raxe_l2_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        'created_at': datetime.now().isoformat(),
        'metadata': {
            'author': 'raxe-ml',
            'description': 'L2 threat detection model',
        },
        'architecture': {
            'type': 'multi_head_random_forest',
            'embedding_model': embedding_config['model_name'],
        },
        'training': {
            'metrics': training_stats['test_metrics'],
        },
        'capabilities': {
            'families': ['PI', 'JB', 'CMD', 'PII', 'ENC', 'RAG'],
            'num_subfamilies': 47,
        },
        'output_schema_ref': 'schema.json',
        'checksums': {},
    }

    # Create temporary directory for bundle contents
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Save components
        joblib.dump(classifier, tmpdir / 'classifier.joblib')

        # Save configs
        with open(tmpdir / 'embedding_config.json', 'w') as f:
            json.dump(embedding_config, f, indent=2)

        with open(tmpdir / 'training_stats.json', 'w') as f:
            json.dump(training_stats, f, indent=2)

        # Create placeholder files (would be populated in real implementation)
        with open(tmpdir / 'keyword_triggers.json', 'w') as f:
            json.dump({}, f)

        joblib.dump({}, tmpdir / 'attack_clusters.joblib')

        with open(tmpdir / 'schema.json', 'w') as f:
            json.dump({
                'version': '1.0.0',
                'fields': ['is_attack', 'family', 'sub_family', 'scores']
            }, f, indent=2)

        # Compute checksums
        for file_name in ['classifier.joblib', 'embedding_config.json', 'training_stats.json',
                          'keyword_triggers.json', 'attack_clusters.joblib', 'schema.json']:
            file_path = tmpdir / file_name
            manifest['checksums'][file_name] = compute_sha256(file_path)

        # Save manifest
        with open(tmpdir / 'manifest.json', 'w') as f:
            json.dump(manifest, f, indent=2)

        # Create ZIP bundle
        print(f"Creating bundle: {output_path}")
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in tmpdir.glob('*'):
                zf.write(file_path, file_path.name)

    # Validate bundle size
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Bundle size: {size_mb:.2f} MB")

    if size_mb > 10:
        print(f"⚠ WARNING: Bundle size ({size_mb:.1f}MB) exceeds 10MB target")

    print("✓ Bundle created successfully")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True, help='Model directory')
    parser.add_argument('--output', required=True, help='Output .raxe file')
    args = parser.parse_args()

    model_dir = Path(args.model)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    create_bundle(model_dir, output_path)

if __name__ == '__main__':
    main()
```

---

## 5. Performance Benchmarking

### 5.1 Benchmark Script

**scripts/benchmark_model.py:**
```python
#!/usr/bin/env python3
"""
Benchmark model performance (latency, accuracy, throughput).

Usage:
    python benchmark_model.py \
        --model-id v1.0_onnx_int8 \
        --test-data data/benchmark/test_set.jsonl \
        --output benchmarks/v1.0_onnx_int8_benchmark.json
"""
import argparse
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd

# Add raxe-ce to path (if running from raxe-ml)
import sys
sys.path.insert(0, '/path/to/raxe-ce/src')

from raxe.domain.ml.model_registry import ModelRegistry
from raxe.domain.engine.executor import ScanResult as L1ScanResult

def create_mock_l1_results():
    """Create mock L1 results for testing."""
    return L1ScanResult(
        has_detections=False,
        detection_count=0,
        detections=[],
        execution_time_ms=1.0,
    )

def benchmark_latency(detector, test_texts: list, iterations: int = 1000):
    """Benchmark model latency."""
    l1_results = create_mock_l1_results()

    # Warm-up
    print("Warming up...")
    for _ in range(10):
        detector.analyze(test_texts[0], l1_results)

    # Measure latency
    print(f"Benchmarking latency ({iterations} iterations)...")
    latencies = []

    for i in range(iterations):
        text = test_texts[i % len(test_texts)]
        start = time.perf_counter()
        result = detector.analyze(text, l1_results)
        latency_ms = (time.perf_counter() - start) * 1000
        latencies.append(latency_ms)

        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{iterations} completed")

    latencies = np.array(latencies)

    return {
        'mean_ms': float(np.mean(latencies)),
        'p50_ms': float(np.percentile(latencies, 50)),
        'p95_ms': float(np.percentile(latencies, 95)),
        'p99_ms': float(np.percentile(latencies, 99)),
        'max_ms': float(np.max(latencies)),
        'min_ms': float(np.min(latencies)),
        'std_ms': float(np.std(latencies)),
    }

def benchmark_accuracy(detector, test_df: pd.DataFrame):
    """Benchmark model accuracy."""
    l1_results = create_mock_l1_results()

    predictions = []
    ground_truth = []

    print(f"Evaluating accuracy on {len(test_df)} samples...")

    for idx, row in test_df.iterrows():
        result = detector.analyze(row['text'], l1_results)

        # Extract prediction
        if result.has_predictions:
            pred = result.predictions[0]
            predictions.append(1)  # Attack
        else:
            predictions.append(0)  # Benign

        # Ground truth
        ground_truth.append(0 if row['label'] == 'BENIGN' else 1)

        if (idx + 1) % 100 == 0:
            print(f"  {idx+1}/{len(test_df)} completed")

    predictions = np.array(predictions)
    ground_truth = np.array(ground_truth)

    # Calculate metrics
    from sklearn.metrics import f1_score, precision_score, recall_score

    tp = ((predictions == 1) & (ground_truth == 1)).sum()
    fp = ((predictions == 1) & (ground_truth == 0)).sum()
    tn = ((predictions == 0) & (ground_truth == 0)).sum()
    fn = ((predictions == 0) & (ground_truth == 1)).sum()

    return {
        'binary_f1': float(f1_score(ground_truth, predictions)),
        'precision': float(precision_score(ground_truth, predictions)),
        'recall': float(recall_score(ground_truth, predictions)),
        'false_positive_rate': float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0,
        'false_negative_rate': float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0,
        'confusion_matrix': {
            'tp': int(tp),
            'fp': int(fp),
            'tn': int(tn),
            'fn': int(fn),
        }
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-id', required=True, help='Model ID')
    parser.add_argument('--test-data', required=True, help='Test data file')
    parser.add_argument('--output', required=True, help='Output JSON file')
    parser.add_argument('--iterations', type=int, default=1000, help='Latency iterations')
    args = parser.parse_args()

    # Load test data
    print(f"Loading test data: {args.test_data}")
    test_df = pd.read_json(args.test_data, lines=True)
    test_texts = test_df['text'].tolist()

    # Load model
    print(f"Loading model: {args.model_id}")
    registry = ModelRegistry()
    detector = registry.create_detector(args.model_id)

    # Benchmark latency
    latency_results = benchmark_latency(detector, test_texts, args.iterations)
    print(f"Latency results:")
    print(f"  P50: {latency_results['p50_ms']:.2f}ms")
    print(f"  P95: {latency_results['p95_ms']:.2f}ms")
    print(f"  P99: {latency_results['p99_ms']:.2f}ms")

    # Benchmark accuracy
    accuracy_results = benchmark_accuracy(detector, test_df)
    print(f"Accuracy results:")
    print(f"  F1: {accuracy_results['binary_f1']:.4f}")
    print(f"  Precision: {accuracy_results['precision']:.4f}")
    print(f"  Recall: {accuracy_results['recall']:.4f}")
    print(f"  FPR: {accuracy_results['false_positive_rate']:.4f}")

    # Combine results
    benchmark_results = {
        'model_id': args.model_id,
        'timestamp': time.time(),
        'test_set_size': len(test_df),
        'latency': latency_results,
        'accuracy': accuracy_results,
        'model_info': detector.model_info,
    }

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(benchmark_results, f, indent=2)

    print(f"✓ Benchmark results saved to: {output_path}")

    # Check performance targets
    meets_latency = latency_results['p95_ms'] < 3.0
    meets_accuracy = accuracy_results['binary_f1'] >= 0.95
    meets_fpr = accuracy_results['false_positive_rate'] <= 0.01

    print("\nPerformance Targets:")
    print(f"  P95 < 3ms: {'✓' if meets_latency else '✗'} ({latency_results['p95_ms']:.2f}ms)")
    print(f"  F1 >= 0.95: {'✓' if meets_accuracy else '✗'} ({accuracy_results['binary_f1']:.4f})")
    print(f"  FPR <= 0.01: {'✓' if meets_fpr else '✗'} ({accuracy_results['false_positive_rate']:.4f})")

    if meets_latency and meets_accuracy and meets_fpr:
        print("\n✓ Model meets all performance targets!")
    else:
        print("\n⚠ Model does not meet performance targets")

if __name__ == '__main__':
    main()
```

---

## 6. Model Optimization

### 6.1 Optimization Checklist

**To meet <3ms P95 latency and <50MB size:**

- [ ] **Embedding Model Optimization**
  - [ ] Use smaller model (MiniLM-L6 instead of MPNet)
  - [ ] Apply INT8 quantization
  - [ ] Reduce max sequence length (512 → 256)
  - [ ] Consider attention head pruning

- [ ] **Classifier Optimization**
  - [ ] Reduce ensemble size (100 → 50 trees)
  - [ ] Limit tree depth (20 → 12)
  - [ ] Quantize decision thresholds
  - [ ] Remove redundant features

- [ ] **Bundle Optimization**
  - [ ] Compress JSON files (gzip)
  - [ ] Remove unnecessary metadata
  - [ ] Optimize joblib serialization
  - [ ] Strip debugging info

---

## 7. Deployment Workflow

### 7.1 Complete Deployment Checklist

**Pre-deployment:**
- [ ] Model trained and validated
- [ ] Bundle created and validated
- [ ] ONNX embeddings exported
- [ ] Benchmarks completed
- [ ] Performance targets met
- [ ] Metadata JSON created
- [ ] Documentation complete

**Deployment:**
```bash
# 1. Copy files to raxe-ce
cp bundles/raxe_model_l2_v1.0.raxe \
   /path/to/raxe-ce/src/raxe/domain/ml/models/bundles/

cp embeddings/all-mpnet-base-v2_int8.onnx \
   /path/to/raxe-ce/src/raxe/domain/ml/models/embeddings/

cp metadata/v1.0_onnx_int8.json \
   /path/to/raxe-ce/src/raxe/domain/ml/models/metadata/

# 2. Verify registry discovers model
cd /path/to/raxe-ce
python -c "
from raxe.domain.ml.model_registry import ModelRegistry
registry = ModelRegistry()
print('Models:', [m.model_id for m in registry.list_models()])
"

# 3. Run integration tests
pytest tests/integration/test_l2_detector.py

# 4. Update CHANGELOG
echo "v1.0_onnx_int8 - Production L2 detector" >> CHANGELOG.md
```

---

## 8. Troubleshooting

### 8.1 Common Issues

**Issue: Model size exceeds 50MB**
```
Solution:
1. Use smaller embedding model (MiniLM vs MPNet)
2. Apply more aggressive quantization (INT4)
3. Reduce classifier complexity
4. Compress bundle contents
```

**Issue: Latency exceeds 3ms**
```
Solution:
1. Profile inference bottlenecks
2. Optimize embedding generation (use ONNX)
3. Reduce max sequence length
4. Simplify classifier (fewer trees)
5. Use batch inference
```

**Issue: Accuracy below 0.95 F1**
```
Solution:
1. Collect more training data
2. Use hard negative mining
3. Tune classification thresholds
4. Ensemble multiple models
5. Use larger embedding model
```

**Issue: High false positive rate**
```
Solution:
1. Adjust confidence threshold
2. Use class weights in training
3. Collect more benign examples
4. Calibrate probability estimates
```

---

## Quick Start Example

**Train → Export → Deploy in 5 minutes:**

```bash
# 1. Train model
python scripts/train_l2_model.py \
    --config configs/production_v1.yaml \
    --data data/processed/training_v2.0 \
    --output models/checkpoints/v1.0

# 2. Export bundle
python scripts/export_bundle.py \
    --model models/checkpoints/v1.0 \
    --output bundles/raxe_model_l2_v1.0.raxe

# 3. Export ONNX embeddings
python scripts/export_onnx_embeddings.py \
    --model sentence-transformers/all-mpnet-base-v2 \
    --quantization int8 \
    --output embeddings/all-mpnet-base-v2_int8.onnx

# 4. Benchmark
python scripts/benchmark_model.py \
    --model-id v1.0_onnx_int8 \
    --test-data data/benchmark/test_set.jsonl \
    --output benchmarks/v1.0_onnx_int8_benchmark.json

# 5. Deploy
./deploy.sh v1.0_onnx_int8
```

That's it! Your model is now in the registry and ready to use.
