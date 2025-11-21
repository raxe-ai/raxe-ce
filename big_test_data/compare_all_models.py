#!/usr/bin/env python3
"""
Compare all available L2 models on benign dataset.

Tests all active models to find the best performer.
"""

import json
import sys
import time
import os
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
        print(f"❌ Model '{model_id}' not found!")
        return None

    print(f"Name: {model_meta.name}")
    print(f"Variant: {model_meta.variant}")
    if model_meta.accuracy and model_meta.accuracy.false_positive_rate is not None:
        print(f"Expected FP rate: {model_meta.accuracy.false_positive_rate:.2%}")
    if model_meta.performance:
        print(f"Target latency: {model_meta.performance.target_latency_ms}ms")

    # Set model via environment variable
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
                'prompt': prompt[:80] + '...' if len(prompt) > 80 else prompt,
                'category': category,
                'l2_predictions': l2_preds
            })
        else:
            results['true_negatives'] += 1

    total_time = time.time() - start_time

    print(" Done!")
    print(f"Completed in {total_time:.1f}s")

    # Calculate stats
    results['fp_rate'] = (results['false_positives'] / results['total']) * 100
    results['latency_avg'] = sum(results['latencies']) / len(results['latencies'])
    results['latency_p50'] = sorted(results['latencies'])[len(results['latencies']) // 2]
    results['latency_p95'] = sorted(results['latencies'])[int(len(results['latencies']) * 0.95)]
    results['latency_p99'] = sorted(results['latencies'])[int(len(results['latencies']) * 0.99)]

    return results


def print_compact_results(results: Dict):
    """Print compact results."""
    print(f"\nAccuracy: {results['true_negatives']}/{results['total']} correct ({results['true_negatives']/results['total']*100:.2f}%)")
    print(f"FP Rate: {results['fp_rate']:.2f}% ({results['false_positives']} false positives)")
    print(f"Latency: {results['latency_avg']:.2f}ms avg, {results['latency_p95']:.2f}ms p95, {results['latency_p99']:.2f}ms p99")


def compare_all_results(all_results: list[Dict]):
    """Compare all models side-by-side."""
    print(f"\n{'='*80}")
    print(f"ALL MODELS COMPARISON")
    print(f"{'='*80}")

    # Sort by FP rate (lower is better)
    sorted_results = sorted(all_results, key=lambda x: x['fp_rate'])

    print(f"\n{'Model':<30s} {'FP Rate':>10s} {'Avg Lat':>10s} {'P95 Lat':>10s} {'Ranking':>10s}")
    print(f"{'-'*30} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")

    for i, result in enumerate(sorted_results, 1):
        model_id = result['model_id']
        fp_rate = result['fp_rate']
        avg_lat = result['latency_avg']
        p95_lat = result['latency_p95']

        # Ranking indicator
        if i == 1:
            rank = "🥇 BEST"
        elif i == 2:
            rank = "🥈 2nd"
        elif i == 3:
            rank = "🥉 3rd"
        else:
            rank = f"#{i}"

        print(f"{model_id:<30s} {fp_rate:>9.2f}% {avg_lat:>9.2f}ms {p95_lat:>9.2f}ms {rank:>10s}")

    # Best model analysis
    best = sorted_results[0]
    print(f"\n{'='*80}")
    print(f"BEST MODEL: {best['model_id']}")
    print(f"{'='*80}")
    print(f"FP Rate: {best['fp_rate']:.2f}%")
    print(f"Avg Latency: {best['latency_avg']:.2f}ms")
    print(f"P95 Latency: {best['latency_p95']:.2f}ms")
    print(f"P99 Latency: {best['latency_p99']:.2f}ms")

    if best['fp_rate'] < 1.0:
        print(f"✅ Meets production target (<1% FP rate)")
    elif best['fp_rate'] < 2.0:
        print(f"⚠️  Close to target, consider additional tuning")
    else:
        print(f"❌ Needs more training to meet <1% FP target")

    if best['latency_avg'] < 10:
        print(f"✅ Meets latency target (<10ms)")
    elif best['latency_avg'] < 20:
        print(f"⚠️  Latency acceptable but could be optimized")
    else:
        print(f"❌ Latency high, needs optimization")

    # Show FP rate differences
    if len(sorted_results) > 1:
        print(f"\n{'='*80}")
        print(f"FP RATE COMPARISON (vs worst)")
        print(f"{'='*80}")

        worst_fp = sorted_results[-1]['fp_rate']
        for result in sorted_results:
            improvement = ((worst_fp - result['fp_rate']) / worst_fp * 100) if worst_fp > 0 else 0
            print(f"{result['model_id']:<30s}: {result['fp_rate']:>6.2f}% ({improvement:>6.1f}% better than worst)")


def main():
    """Main execution."""
    script_dir = Path(__file__).parent
    input_file = script_dir / "benign_prompts.jsonl"

    if not input_file.exists():
        print(f"Error: {input_file} not found!")
        return 1

    # Load test samples
    print("Loading test prompts...")
    prompts = load_benign_prompts(input_file, limit=1000)
    print(f"Loaded {len(prompts):,} prompts for testing")

    # Get all active models
    registry = get_registry()
    available_models = registry.list_models()

    print(f"\n{' Available Models ':-^80}")
    for model in available_models:
        print(f"  - {model.model_id:30s} ({model.status.value})")

    # Test these specific models
    models_to_test = [
        "v1.0_onnx_int8_bundle",  # Original
        "v1.0_int8_fast",          # New INT8
        "v1.0_fp16",               # FP16 (potentially better accuracy)
    ]

    # Verify all models exist
    models_to_test = [m for m in models_to_test if registry.has_model(m)]

    if not models_to_test:
        print("\n❌ No models available for testing!")
        return 1

    print(f"\n{' Testing {len(models_to_test)} Models ':-^80}")
    all_results = []

    for model_id in models_to_test:
        result = test_model(model_id, prompts)
        if result:
            print_compact_results(result)
            all_results.append(result)

    # Compare all
    if len(all_results) > 1:
        compare_all_results(all_results)

    # Save results
    output_file = script_dir / "all_models_comparison.json"
    with open(output_file, 'w') as f:
        json.dump({
            'models_tested': len(all_results),
            'test_size': len(prompts),
            'results': all_results
        }, f, indent=2)

    print(f"\n✓ Results saved to: {output_file}")

    return 0


if __name__ == "__main__":
    exit(main())
