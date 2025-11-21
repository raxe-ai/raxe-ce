#!/usr/bin/env python3
"""
Compare two L2 models on benign dataset.

Tests old model vs new v1.0_int8_fast model to measure improvement.
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from raxe.domain.ml.model_registry import get_registry
from raxe.sdk.client import Raxe


def load_benign_prompts(file_path: Path, limit: int = 1000) -> list[Dict]:
    """Load benign prompts (sample for faster comparison)."""
    prompts = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                prompts.append(json.loads(line))
            if len(prompts) >= limit:
                break
    return prompts


def test_model(model_id: str, prompts: list[Dict]) -> Dict:
    """Test a specific model on prompts."""
    print(f"\n{'='*80}")
    print(f"Testing Model: {model_id}")
    print(f"{'='*80}")

    # Get model info
    registry = get_registry()
    model_meta = registry.get_model(model_id)

    if not model_meta:
        print(f"❌ Model '{model_id}' not found in registry!")
        print(f"Available models: {[m.model_id for m in registry.list_models()]}")
        return None

    print(f"Name: {model_meta.name}")
    print(f"Variant: {model_meta.variant}")
    print(f"Status: {model_meta.status.value}")
    if model_meta.accuracy and model_meta.accuracy.false_positive_rate is not None:
        print(f"Expected FP rate: {model_meta.accuracy.false_positive_rate:.2%}")
    if model_meta.performance:
        print(f"Target latency: {model_meta.performance.target_latency_ms}ms")

    # Create Raxe instance with specific model
    # TODO: Need to add model_id parameter to Raxe.__init__
    # For now, we'll test by setting environment variable
    import os
    os.environ['RAXE_L2_MODEL'] = model_id

    raxe = Raxe(telemetry=False, l2_enabled=True)

    results = {
        'model_id': model_id,
        'total': len(prompts),
        'false_positives': 0,
        'true_negatives': 0,
        'fp_details': [],
        'latencies': [],
        'categories': {}
    }

    print(f"\nScanning {len(prompts)} prompts...")
    print(f"Progress: ", end='', flush=True)

    start_time = time.time()

    for i, item in enumerate(prompts):
        if (i + 1) % 100 == 0:
            print(f"{i+1}...", end='', flush=True)

        prompt = item.get('prompt', '')
        category = item.get('category', 'unknown')

        # Track category stats
        if category not in results['categories']:
            results['categories'][category] = {'total': 0, 'fp': 0}
        results['categories'][category]['total'] += 1

        # Scan with timing
        scan_start = time.time()
        scan_result = raxe.scan(prompt)
        scan_duration = (time.time() - scan_start) * 1000  # ms

        results['latencies'].append(scan_duration)

        # Check for threats
        if scan_result.has_threats:
            results['false_positives'] += 1
            results['categories'][category]['fp'] += 1

            # Get L2 predictions
            l2_preds = []
            if scan_result.scan_result.l2_result:
                for p in scan_result.scan_result.l2_predictions:
                    l2_preds.append({
                        'threat_type': p.threat_type.value,
                        'confidence': p.confidence
                    })

            results['fp_details'].append({
                'id': item.get('id', f'sample-{i}'),
                'prompt': prompt[:100] + '...' if len(prompt) > 100 else prompt,
                'category': category,
                'l2_predictions': l2_preds
            })
        else:
            results['true_negatives'] += 1

    total_time = time.time() - start_time

    print(" Done!")
    print(f"\nCompleted in {total_time:.1f}s")

    # Calculate stats
    results['fp_rate'] = (results['false_positives'] / results['total']) * 100
    results['latency_avg'] = sum(results['latencies']) / len(results['latencies'])
    results['latency_p50'] = sorted(results['latencies'])[len(results['latencies']) // 2]
    results['latency_p95'] = sorted(results['latencies'])[int(len(results['latencies']) * 0.95)]
    results['latency_p99'] = sorted(results['latencies'])[int(len(results['latencies']) * 0.99)]

    return results


def print_results(results: Dict):
    """Print test results."""
    print(f"\n{'='*80}")
    print(f"RESULTS: {results['model_id']}")
    print(f"{'='*80}")

    print(f"\nAccuracy:")
    print(f"  Total samples: {results['total']:,}")
    print(f"  True Negatives (correct): {results['true_negatives']:,} ({results['true_negatives']/results['total']*100:.2f}%)")
    print(f"  False Positives (errors): {results['false_positives']:,} ({results['fp_rate']:.2f}%)")

    print(f"\nPerformance:")
    print(f"  Avg latency: {results['latency_avg']:.2f}ms")
    print(f"  P50 latency: {results['latency_p50']:.2f}ms")
    print(f"  P95 latency: {results['latency_p95']:.2f}ms")
    print(f"  P99 latency: {results['latency_p99']:.2f}ms")

    print(f"\nFP Rate by Category:")
    for cat, stats in sorted(results['categories'].items(), key=lambda x: x[1]['fp'], reverse=True)[:5]:
        if stats['total'] > 0:
            fp_rate = (stats['fp'] / stats['total']) * 100
            print(f"  {cat:30s}: {stats['fp']:4d}/{stats['total']:4d} ({fp_rate:5.2f}%)")


def compare_results(old_results: Dict, new_results: Dict):
    """Compare old vs new model results."""
    print(f"\n{'='*80}")
    print(f"COMPARISON: {old_results['model_id']} vs {new_results['model_id']}")
    print(f"{'='*80}")

    # FP Rate comparison
    old_fp = old_results['fp_rate']
    new_fp = new_results['fp_rate']
    fp_improvement = ((old_fp - new_fp) / old_fp) * 100 if old_fp > 0 else 0

    print(f"\nFalse Positive Rate:")
    print(f"  Old ({old_results['model_id']:20s}): {old_fp:5.2f}%")
    print(f"  New ({new_results['model_id']:20s}): {new_fp:5.2f}%")

    if fp_improvement > 0:
        print(f"  ✅ Improvement: {fp_improvement:.1f}% reduction (better)")
    elif fp_improvement < 0:
        print(f"  ❌ Regression: {abs(fp_improvement):.1f}% increase (worse)")
    else:
        print(f"  ➖ No change")

    # Latency comparison
    old_lat = old_results['latency_avg']
    new_lat = new_results['latency_avg']
    lat_improvement = ((old_lat - new_lat) / old_lat) * 100 if old_lat > 0 else 0

    print(f"\nAverage Latency:")
    print(f"  Old ({old_results['model_id']:20s}): {old_lat:5.2f}ms")
    print(f"  New ({new_results['model_id']:20s}): {new_lat:5.2f}ms")

    if lat_improvement > 0:
        print(f"  ✅ Improvement: {lat_improvement:.1f}% faster")
    elif lat_improvement < 0:
        print(f"  ⚠️  Slower: {abs(lat_improvement):.1f}% slower")
    else:
        print(f"  ➖ No change")

    # Overall assessment
    print(f"\n{'='*80}")
    print(f"OVERALL ASSESSMENT")
    print(f"{'='*80}")

    if fp_improvement > 50 and lat_improvement > -10:
        print("✅ EXCELLENT: Significant FP reduction with acceptable latency")
    elif fp_improvement > 20 and lat_improvement > -20:
        print("✅ GOOD: Meaningful FP reduction")
    elif fp_improvement > 0:
        print("✅ POSITIVE: Some FP reduction")
    elif fp_improvement < -10:
        print("❌ REGRESSION: FP rate increased, model may need retraining")
    else:
        print("➖ NEUTRAL: No significant change")

    # Recommendations
    print(f"\nRecommendations:")
    if new_fp < 1.0:
        print("  ✅ New model meets production target (<1% FP rate)")
    elif new_fp < 2.0:
        print("  ⚠️  New model close to target, consider additional tuning")
    else:
        print("  ❌ New model needs more training to meet <1% FP target")

    if new_lat < 10:
        print("  ✅ Latency meets target (<10ms)")
    elif new_lat < 20:
        print("  ⚠️  Latency acceptable but could be optimized")
    else:
        print("  ❌ Latency high, may need optimization")


def main():
    """Main execution."""
    script_dir = Path(__file__).parent
    input_file = script_dir / "benign_prompts.jsonl"

    if not input_file.exists():
        print(f"Error: {input_file} not found!")
        return 1

    # Load test samples (use subset for faster comparison)
    print("Loading test prompts...")
    prompts = load_benign_prompts(input_file, limit=1000)
    print(f"Loaded {len(prompts):,} prompts for testing")

    # Check available models
    registry = get_registry()
    available_models = registry.list_models()

    print(f"\n{' Available Models ':-^80}")
    for model in available_models:
        print(f"  - {model.model_id:30s} ({model.status.value})")

    # Determine old model (the one currently in use)
    # Assume v1.0_onnx_int8_bundle is the old one
    old_model_id = "v1.0_onnx_int8_bundle"
    new_model_id = "v1.0_int8_fast"

    # Verify models exist
    if not registry.has_model(old_model_id):
        print(f"\n❌ Old model '{old_model_id}' not found!")
        # Try to find any model as baseline
        if available_models:
            old_model_id = available_models[0].model_id
            print(f"Using '{old_model_id}' as baseline instead")
        else:
            print("No models available for comparison!")
            return 1

    if not registry.has_model(new_model_id):
        print(f"\n❌ New model '{new_model_id}' not found!")
        print(f"Please ensure model metadata exists at: src/raxe/domain/ml/models/metadata/{new_model_id}.json")
        return 1

    # Test old model
    old_results = test_model(old_model_id, prompts)
    if not old_results:
        return 1

    print_results(old_results)

    # Test new model
    new_results = test_model(new_model_id, prompts)
    if not new_results:
        return 1

    print_results(new_results)

    # Compare
    compare_results(old_results, new_results)

    # Save detailed results
    output_file = script_dir / "model_comparison_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            'old_model': old_results,
            'new_model': new_results,
            'comparison': {
                'fp_improvement_pct': ((old_results['fp_rate'] - new_results['fp_rate']) / old_results['fp_rate'] * 100) if old_results['fp_rate'] > 0 else 0,
                'latency_improvement_pct': ((old_results['latency_avg'] - new_results['latency_avg']) / old_results['latency_avg'] * 100) if old_results['latency_avg'] > 0 else 0,
            }
        }, f, indent=2)

    print(f"\n✓ Detailed results saved to: {output_file}")

    return 0


if __name__ == "__main__":
    exit(main())
