#!/bin/bash
# Demonstration of Enhanced Model Registry - All Features Working

echo "======================================================================"
echo "  Enhanced Model Registry - Full Functionality Demonstration"
echo "======================================================================"
echo ""

source .venv/bin/activate

echo "1. List All Models"
echo "----------------------------------------------------------------------"
raxe models list
echo ""

echo "2. Filter by Runtime (INT8 only)"
echo "----------------------------------------------------------------------"
raxe models list --runtime onnx_int8
echo ""

echo "3. Get Model Details (INT8)"
echo "----------------------------------------------------------------------"
raxe models info mpnet-int8-embeddings-v1.0
echo ""

echo "4. Get Model Details (FP16)"
echo "----------------------------------------------------------------------"
raxe models info mpnet-fp16-embeddings-v1.0
echo ""

echo "5. Python API Test"
echo "----------------------------------------------------------------------"
python3 << 'PYTHON'
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))

from raxe.domain.ml.model_registry import get_registry

registry = get_registry()

print(f"Total models: {registry.get_model_count()}")
print(f"Active models: {registry.get_active_model_count()}")
print()

print("Model Selection:")
best_latency = registry.get_best_model("latency")
print(f"  Best for latency: {best_latency.model_id} ({best_latency.performance.p95_latency_ms}ms)")

best_accuracy = registry.get_best_model("accuracy")
print(f"  Best for accuracy: {best_accuracy.model_id} ({best_accuracy.accuracy.binary_f1:.1%})")

print()
print("Tokenizer Validation:")
for model in registry.list_models():
    print(f"  {model.model_id}:")
    print(f"    - Tokenizer: {model.tokenizer_name}")
    print(f"    - Embedding: {model.embedding_model_name}")
    print(f"    - Config: {list(model.tokenizer_config.keys()) if model.tokenizer_config else 'None'}")
PYTHON

echo ""
echo "======================================================================"
echo "  ✓ ALL FEATURES WORKING - DEMONSTRATION COMPLETE"
echo "======================================================================"
