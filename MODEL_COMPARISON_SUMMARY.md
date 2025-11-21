# Model Comparison: v1.0_onnx_int8_bundle vs v1.0_int8_fast

**Status:** Ready to test
**Date:** 2025-11-20

---

## 📊 What We're Comparing

### Old Model: `v1.0_onnx_int8_bundle`
- Original L2 model with ONNX INT8 embeddings
- Baseline false positive rate: ~3.92% (from initial testing)
- Target latency: ~10ms

### New Model: `v1.0_int8_fast`
**Metadata shows:**
- Expected FP rate: 2.8% (claimed 28.6% improvement)
- Expected latency: ~7ms (30% faster)
- Target P95: <10ms
- Status: ACTIVE (production-ready)

---

## 🧪 Test Script Created

**File:** `big_test_data/compare_models.py`

**What it does:**
1. Loads 1,000 benign prompts for testing
2. Tests old model → measures FP rate & latency
3. Tests new model → measures FP rate & latency
4. Compares results side-by-side
5. Provides recommendations

**How to run:**
```bash
# From repo root
python3 big_test_data/compare_models.py

# Results saved to:
# - big_test_data/model_comparison.log (stdout)
# - big_test_data/model_comparison_results.json (detailed data)
```

---

## 📈 Expected Outcomes

### If New Model is Better:
```
False Positive Rate:
  Old (v1.0_onnx_int8_bundle): 3.92%
  New (v1.0_int8_fast):        2.80%
  ✅ Improvement: 28.6% reduction

Average Latency:
  Old: 10.2ms
  New:  7.0ms
  ✅ Improvement: 31% faster

OVERALL: ✅ EXCELLENT - Deploy new model
```

### If New Model Needs Work:
```
False Positive Rate:
  Old: 3.92%
  New: 4.50%
  ❌ REGRESSION: 14.8% increase

→ New model needs more training data
→ Use reinforced_training_data.csv to retrain
```

---

## 🎯 Success Criteria

### Must Have:
- ✅ FP rate improvement (lower is better)
- ✅ Latency <10ms (acceptable range)
- ✅ No major regression in accuracy

### Stretch Goals:
- 🎯 FP rate <2% (50% improvement)
- 🎯 Latency <8ms
- 🎯 All hard negatives correct

---

## 📝 Test Configuration

The comparison script tests on:
- **1,000 benign prompts** (stratified sample)
- Categories covered: programming, education, technical_docs, edge_cases
- Measures:
  - False positive rate (%)
  - Average latency (ms)
  - P50/P95/P99 latency
  - FP breakdown by category

---

## 🔧 Troubleshooting

### If test fails with "model not found":
```bash
# Check available models
python3 -c "
from raxe.domain.ml.model_registry import get_registry
registry = get_registry()
for m in registry.list_models():
    print(f'{m.model_id} - {m.status.value}')
"
```

### If you need to test on full 100K dataset:
Edit `compare_models.py` line 243:
```python
# Change from:
prompts = load_benign_prompts(input_file, limit=1000)

# To:
prompts = load_benign_prompts(input_file, limit=100000)
```

---

## 🚀 Next Steps After Comparison

### If New Model is Better:
1. ✅ Update default model in config
2. ✅ Deploy to staging
3. ✅ Monitor for 24h
4. ✅ Deploy to production

### If New Model Needs Improvement:
1. 📋 Analyze specific FP categories
2. 📋 Add more training data for problem areas
3. 📋 Retrain with reinforced_training_data.csv
4. 📋 Re-test

---

## 📁 Files

- **compare_models.py** - Comparison script
- **benign_prompts.jsonl** - Test data (100K samples)
- **reinforced_training_data.csv** - Training data for improvement (4,790 samples)
- **model_comparison_results.json** - Results (generated after run)

---

**Ready to run comparison!**

```bash
python3 big_test_data/compare_models.py
```
