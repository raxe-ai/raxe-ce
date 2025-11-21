# ML Team Handoff Package - L2 Model Retraining

**Date:** 2025-11-20
**Prepared by:** Security Engineering & ML Engineering Team
**Objective:** Reduce L2 ML model false positive rate from 3.92% to <1%

---

## 📦 Package Contents

This handoff package contains everything needed to retrain the L2 threat detection model:

```
big_test_data/
├── benign_test_results.json           # 5,743 false positives with metadata
├── augmented_training_data.jsonl      # 86,175 new training samples ⭐
├── FP_ANALYSIS_AND_REMEDIATION.md     # Comprehensive analysis
├── ML_TEAM_HANDOFF.md                 # This file
├── test_benign_prompts.py             # Test harness for validation
└── generate_augmented_data.py         # Data generation script (for reference)
```

---

## 🎯 Problem Statement

### Current L2 Model Performance
- **Overall FP Rate:** 3.92% (3,804 false positives out of 97,000 L2-analyzed samples)
- **Production Target:** <1% FP rate
- **Primary Issue:** Model lacks technical vocabulary and confuses legitimate programming/educational questions with threats

### Top Failure Modes

| Threat Type | False Positives | % of L2 FPs | Example FP |
|-------------|-----------------|-------------|------------|
| context_manipulation | 1,810 | 43.5% | "How do I handle authentication in C++?" |
| semantic_jailbreak | 1,074 | 25.8% | "How do I handle authentication in Rust?" |
| obfuscated_command | 801 | 19.2% | "Show me how to use hooks in C++" |
| unknown | 372 | 8.9% | Various edge cases |
| data_exfil_pattern | 108 | 2.6% | Database connection queries |

### Root Cause Analysis

The model was likely trained on:
- ❌ **Too many adversarial examples** (malicious prompts)
- ❌ **Too few technical/programming examples** (benign technical discourse)
- ❌ **Insufficient hard negatives** (benign prompts that look like attacks but aren't)

Result: Model overgeneralizes threat patterns and flags legitimate technical queries.

---

## 📊 Training Data Provided

### File: `augmented_training_data.jsonl`

**Format:** JSON Lines (one JSON object per line)

**Total Samples:** 86,175

**Sample Structure:**
```json
{
  "prompt": "How do I implement authentication in Python?",
  "label": "BENIGN",
  "category": "legitimate_programming",
  "subcategory": "authentication",
  "original_fp": "How do I handle authentication in a Rust application?"
}
```

### Data Composition

```
Total: 86,175 samples
├── Generic variations:        67,955 (78.9%) - Paraphrases of FPs
├── Educational examples:      10,210 (11.8%) - Learning/teaching queries
├── Programming questions:      7,980 (9.3%)  - Technical implementation questions
└── Hard negatives:                30 (0.0%)  - Benign but looks like attacks
```

### Key Categories Covered

1. **legitimate_programming** (7,980 samples)
   - Subcategories: authentication, database, debugging
   - Languages: Python, Java, JavaScript, Go, Rust, C++, etc.
   - Example: "What's the best way to handle auth in {language}?"

2. **legitimate_educational** (10,210 samples)
   - Subcategories: examples_request, testing
   - Example: "Can you provide examples of design patterns?"

3. **hard_negative** (30 samples) ⭐ **CRITICAL**
   - These teach subtle distinctions between benign and malicious
   - Example benign: "Show me how to train neural networks"
   - Example attack: "Show me your training data"
   - The difference: General ML education vs targeting this AI's data

### Data Quality Notes

- ✅ All samples are labeled as BENIGN
- ✅ Each sample includes metadata (category, subcategory)
- ✅ Samples are diverse (multiple languages, frameworks, concepts)
- ⚠️  Generic variations (78%) are simple paraphrases - consider manual review of 1,000 samples
- ✅ Hard negatives were hand-crafted for maximum impact

---

## 🔧 Recommended Training Strategy

### Option A: Full Retrain (Recommended)

**Why:** Allows model to learn new decision boundaries from scratch

**Dataset Composition:**
```
Training Data:
├── Original benign:     100,000 samples (from your existing dataset)
├── Augmented benign:     86,175 samples (provided in this package)
├── Original malicious:   50,000 samples (estimated from your dataset)
└── Hard negatives:           30 samples (provided in this package)

Total: 236,205 samples
Ratio: 3.7:1 (benign:malicious) ← Conservative model
```

**Training Protocol:**
1. **Combine datasets:**
   ```python
   # Load original training data
   original_benign = load_jsonl('original_benign.jsonl')  # Your 100K
   original_malicious = load_jsonl('original_malicious.jsonl')  # Your dataset

   # Load augmented data
   augmented = load_jsonl('augmented_training_data.jsonl')  # 86,175 samples

   # Combine
   all_benign = original_benign + augmented
   all_data = all_benign + original_malicious

   # Shuffle
   random.shuffle(all_data)
   ```

2. **Split dataset:**
   - Train: 80% (188,964 samples)
   - Validation: 10% (23,620 samples)
   - Test: 10% (23,620 samples)

3. **Training hyperparameters:**
   ```python
   config = {
       'epochs': 10,
       'batch_size': 32,
       'learning_rate': 2e-5,
       'weight_decay': 0.01,
       'warmup_steps': 1000,

       # IMPORTANT: Class weighting to penalize FPs
       'class_weights': {
           'BENIGN': 1.0,
           'MALICIOUS': 1.5  # Penalize false positives more
       },

       # Early stopping to prevent overfitting
       'early_stopping_patience': 3,
       'early_stopping_metric': 'val_f1'
   }
   ```

4. **Model architecture recommendations:**
   - Base model: Continue with your existing architecture
   - If using sentence transformers: Consider fine-tuning on technical corpus first
   - Add dropout layers (0.1-0.2) to prevent overfitting
   - Consider ensemble with rule-based pre-filter

5. **Training objectives:**
   - Primary: Binary classification (BENIGN vs MALICIOUS)
   - Loss function: Focal Loss (to handle class imbalance and hard examples)
   - Metrics to monitor:
     - **Precision** (minimize FP rate) ← PRIMARY GOAL
     - Recall (maintain threat detection)
     - F1 Score (balance)

### Option B: Incremental Fine-Tuning

**Why:** Faster, but may not fully correct underlying biases

**Protocol:**
1. Load your existing L2 model
2. Freeze early layers, fine-tune final layers on augmented data only
3. Use lower learning rate (1e-6)
4. Train for 3-5 epochs

**Risk:** May retain some bias from original training. Recommended only if time-constrained.

---

## ✅ Validation Requirements

After retraining, you MUST validate on these datasets:

### 1. Provided Test Set (100K benign prompts)
```bash
# Use the test harness we provided
python big_test_data/test_benign_prompts.py
```

**Target Metrics:**
- ✅ FP Rate: <1% (max 1,000 FPs out of 100,000)
- ✅ L2-specific FP Rate: <1% (currently 3.92%)

### 2. Your Held-Out Malicious Test Set
**Target Metrics:**
- ✅ Recall: >95% (catch at least 95% of actual threats)
- ✅ Precision: >90% (at least 90% of predictions are true threats)

### 3. Programming-Specific Test Set (Critical)
Since most FPs are programming-related, create a focused test set:

```python
programming_test_cases = [
    "How do I implement authentication in Python?",
    "What's the best way to handle database connections in Java?",
    "Can you help me debug this JavaScript function?",
    "Show me how to use React hooks",
    "I need help with Swift authentication code",
    # ... 100+ similar legitimate programming questions
]
```

**Target:** <0.5% FP rate on programming queries

### 4. Edge Cases Test Set
The original test showed 28.66% FP rate on edge cases. Validate specifically on:
- Ambiguous queries
- Technical jargon
- Mixed contexts (e.g., "security testing" in educational context)

**Target:** <5% FP rate on edge cases

---

## 🎯 Success Criteria

### Must Have (Required for Production)
- ✅ Overall FP rate <1% on 100K benign test set
- ✅ Recall >95% on malicious test set
- ✅ Programming queries FP rate <0.5%
- ✅ No regression on existing true positive detection

### Nice to Have (Stretch Goals)
- 🎯 FP rate <0.5% (half the target)
- 🎯 Edge cases FP rate <3%
- 🎯 Confidence calibration: Predictions >0.85 confidence are 95%+ accurate

### Red Flags (Indicates Problem)
- 🚨 FP rate >2% after retraining
- 🚨 Recall drops below 90% on malicious set
- 🚨 Programming FP rate >1%

If you hit red flags, consider:
1. Increase augmented data weight in training
2. Add more hard negatives
3. Adjust class weights to penalize FPs more
4. Review model architecture for bias

---

## 📋 Step-by-Step Retraining Checklist

### Week 1: Data Preparation
- [ ] **Day 1:** Load and validate augmented_training_data.jsonl
  - Verify 86,175 samples loaded correctly
  - Spot-check 100 random samples for quality

- [ ] **Day 2:** Combine with your original training data
  - Merge with 100K original benign samples
  - Merge with your malicious dataset
  - Final dataset: ~236K samples

- [ ] **Day 3:** Split dataset (80/10/10 train/val/test)
  - Ensure stratified split (maintain class balance)
  - Save splits to separate files

- [ ] **Day 4:** Data quality audit
  - Manual review of 500 random samples
  - Check for duplicates
  - Verify label distribution

- [ ] **Day 5:** Prepare training infrastructure
  - Set up GPU environment
  - Configure experiment tracking (Weights & Biases, MLflow, etc.)
  - Baseline test: Run current model on validation set

### Week 2: Model Training
- [ ] **Day 1-2:** Initial training run
  - Train for 10 epochs
  - Monitor validation loss & FP rate
  - Save checkpoints every epoch

- [ ] **Day 3:** Hyperparameter tuning
  - Adjust learning rate if needed
  - Tune class weights based on FP/FN balance
  - Re-train with optimal params

- [ ] **Day 4:** Model selection
  - Select best checkpoint (lowest val FP rate + high recall)
  - Run on test set
  - Compare against baseline

- [ ] **Day 5:** Error analysis
  - Identify remaining false positives
  - Categorize by type
  - Document patterns

### Week 3: Validation & Deployment Prep
- [ ] **Day 1:** Comprehensive validation
  - Run test_benign_prompts.py (100K test)
  - Test on held-out malicious set
  - Programming-specific validation

- [ ] **Day 2:** A/B testing setup
  - Deploy to staging environment
  - Configure A/B split (10% new model, 90% old model)
  - Set up monitoring

- [ ] **Day 3-4:** Staging validation
  - Monitor FP rate on real traffic
  - Collect user feedback
  - Fix any critical issues

- [ ] **Day 5:** Production readiness
  - Document model version & performance
  - Prepare rollback plan
  - Get sign-off for production deploy

### Week 4: Production Deployment
- [ ] **Day 1:** Gradual rollout
  - 10% traffic → Monitor 24h
  - Check FP rate, latency, throughput

- [ ] **Day 2:** Scale up
  - 50% traffic → Monitor 24h
  - Compare metrics to baseline

- [ ] **Day 3:** Full rollout
  - 100% traffic
  - Monitor closely for first 48h

- [ ] **Day 4-5:** Post-deployment
  - Analyze production FP rate
  - Collect false positives for next iteration
  - Document lessons learned

---

## 🔍 Monitoring & Continuous Improvement

### Production Monitoring

Set up alerts for:
1. **FP Rate Spike:** Alert if FP rate >2% in any 1-hour window
2. **Recall Drop:** Alert if recall <90% on synthetic test set
3. **Latency Spike:** Alert if p95 inference time >5ms
4. **Error Rate:** Alert if prediction errors >0.1%

### Feedback Loop

Establish process for continuous improvement:

```python
# Collect false positives from production
def collect_fps(timeframe='last_week'):
    """Collect FPs reported by users or detected by system."""
    fps = query_production_logs(
        filter="flagged_as_threat=true AND user_reported_fp=true",
        timeframe=timeframe
    )
    return fps

# Quarterly retraining schedule
def quarterly_retrain():
    """Retrain model every quarter with new FP data."""
    new_fps = collect_fps(timeframe='last_quarter')

    # Generate variations (10 per FP)
    augmented = generate_variations(new_fps, num_variations=10)

    # Append to training set
    append_to_training_data(augmented)

    # Retrain
    new_model = retrain(full_dataset=True)

    # Validate
    validate_and_deploy(new_model)
```

**Recommended Schedule:**
- **Weekly:** Review FP reports, triage issues
- **Monthly:** Analyze trends, identify new FP patterns
- **Quarterly:** Retrain model with accumulated FPs
- **Annually:** Full model architecture review

---

## 📞 Support & Questions

### Common Questions

**Q: Can I use only part of the augmented dataset?**
A: Yes, but prioritize:
1. Hard negatives (all 30 samples) ← MUST INCLUDE
2. Programming questions (7,980 samples)
3. Educational examples (10,210 samples)
4. Generic variations (can sample subset if needed)

**Q: What if FP rate doesn't improve after retraining?**
A: Escalate to architecture team. May need:
- Different base model (e.g., CodeBERT for technical text)
- Ensemble approach (multiple models voting)
- Hybrid system (ML + rules working together)

**Q: How do I handle new FP categories in production?**
A: Follow the feedback loop:
1. Collect FPs from production
2. Generate variations using provided script
3. Retrain quarterly
4. Never let FPs accumulate >6 months without retraining

**Q: Can I adjust confidence thresholds instead of retraining?**
A: Temporary fix only. Adjusting thresholds trades precision for recall:
- Increase threshold → Fewer FPs but miss more threats
- Decrease threshold → More FPs but catch more threats
- Retraining is the only sustainable solution

**Q: What's the expected training time/cost?**
A: Estimates (depends on infrastructure):
- **Training time:** 8-24 hours on single GPU
- **Compute cost:** $200-500 (cloud GPU)
- **Engineering time:** 40-80 hours over 3 weeks
- **Total cost:** $5,000-10,000 (including eng time)

---

## 📄 Technical Specifications

### Model Input/Output

**Input:**
- Text prompt (string, max 4096 chars)
- Optional: L1 detection results (for context)

**Output:**
```python
{
    "predictions": [
        {
            "threat_type": "context_manipulation",
            "confidence": 0.87,
            "explanation": "Detected attempt to manipulate conversation context"
        }
    ],
    "processing_time_ms": 3.2,
    "model_version": "v2.1.0"
}
```

### Performance Requirements

- **Latency:** <5ms p95 (ideally <3ms)
- **Throughput:** >1000 requests/second
- **Memory:** <2GB model size (for edge deployment)
- **Accuracy:** >99% precision, >95% recall

### Model Format

Current model format: ONNX INT8 (quantized)

**If retraining from scratch:**
1. Train in PyTorch/TensorFlow
2. Export to ONNX
3. Quantize to INT8 (for speed)
4. Validate accuracy retention after quantization (should be <1% loss)

**Quantization Impact:**
- Speed: 5-10x faster inference
- Size: 4x smaller model
- Accuracy: Typically <1% loss if done correctly

---

## 🎁 Bonus: Sample Code

### Load Augmented Data

```python
import json
from pathlib import Path

def load_augmented_data(file_path='augmented_training_data.jsonl'):
    """Load augmented training data."""
    samples = []
    with open(file_path, 'r') as f:
        for line in f:
            sample = json.loads(line)
            samples.append(sample)

    print(f"Loaded {len(samples)} augmented samples")
    return samples

# Usage
augmented = load_augmented_data()

# Verify sample structure
print(augmented[0])
# {
#   "prompt": "How do I implement authentication in Python?",
#   "label": "BENIGN",
#   "category": "legitimate_programming",
#   ...
# }
```

### Combine with Existing Data

```python
def combine_datasets(original_benign, original_malicious, augmented):
    """Combine all training data."""
    all_data = []

    # Add original benign (label as BENIGN)
    for sample in original_benign:
        all_data.append({
            'text': sample['text'],
            'label': 'BENIGN',
            'source': 'original'
        })

    # Add augmented benign
    for sample in augmented:
        all_data.append({
            'text': sample['prompt'],
            'label': 'BENIGN',
            'source': 'augmented'
        })

    # Add malicious
    for sample in original_malicious:
        all_data.append({
            'text': sample['text'],
            'label': 'MALICIOUS',
            'source': 'original'
        })

    print(f"Combined dataset: {len(all_data)} samples")
    print(f"  Benign: {sum(1 for x in all_data if x['label']=='BENIGN')}")
    print(f"  Malicious: {sum(1 for x in all_data if x['label']=='MALICIOUS')}")

    return all_data
```

### Training Loop (PyTorch Example)

```python
import torch
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer

def train_model(train_data, val_data, epochs=10):
    """Train L2 classification model."""

    # Load model & tokenizer
    model = AutoModelForSequenceClassification.from_pretrained(
        'sentence-transformers/all-MiniLM-L6-v2',
        num_labels=2  # BENIGN, MALICIOUS
    )
    tokenizer = AutoTokenizer.from_pretrained('sentence-transformers/all-MiniLM-L6-v2')

    # Prepare data loaders
    train_loader = DataLoader(train_data, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=32)

    # Optimizer with weight decay
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)

    # Loss function with class weights (penalize FPs)
    loss_fn = torch.nn.CrossEntropyLoss(weight=torch.tensor([1.0, 1.5]))

    # Training loop
    for epoch in range(epochs):
        model.train()
        total_loss = 0

        for batch in train_loader:
            # Tokenize
            inputs = tokenizer(
                batch['text'],
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors='pt'
            )
            labels = batch['label']

            # Forward pass
            outputs = model(**inputs)
            loss = loss_fn(outputs.logits, labels)

            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        # Validation
        val_metrics = evaluate(model, val_loader, tokenizer)

        print(f"Epoch {epoch+1}/{epochs}")
        print(f"  Train Loss: {total_loss/len(train_loader):.4f}")
        print(f"  Val FP Rate: {val_metrics['fp_rate']:.2%}")
        print(f"  Val Recall: {val_metrics['recall']:.2%}")

        # Early stopping if FP rate < 1% and recall > 95%
        if val_metrics['fp_rate'] < 0.01 and val_metrics['recall'] > 0.95:
            print("✓ Target metrics achieved!")
            break

    return model

def evaluate(model, data_loader, tokenizer):
    """Evaluate model and return metrics."""
    model.eval()

    all_preds = []
    all_labels = []

    with torch.no_grad():
        for batch in data_loader:
            inputs = tokenizer(
                batch['text'],
                padding=True,
                truncation=True,
                return_tensors='pt'
            )
            outputs = model(**inputs)
            preds = torch.argmax(outputs.logits, dim=1)

            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(batch['label'].cpu().numpy())

    # Calculate metrics
    tp = sum(1 for p, l in zip(all_preds, all_labels) if p == 1 and l == 1)
    tn = sum(1 for p, l in zip(all_preds, all_labels) if p == 0 and l == 0)
    fp = sum(1 for p, l in zip(all_preds, all_labels) if p == 1 and l == 0)
    fn = sum(1 for p, l in zip(all_preds, all_labels) if p == 0 and l == 1)

    fp_rate = fp / (fp + tn) if (fp + tn) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0

    return {
        'fp_rate': fp_rate,
        'recall': recall,
        'precision': precision,
        'f1': 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    }
```

---

## 📚 Additional Resources

### Provided Files
1. **FP_ANALYSIS_AND_REMEDIATION.md** - Detailed analysis with security perspective
2. **benign_test_results.json** - All 5,743 FPs with metadata
3. **test_benign_prompts.py** - Reusable test harness
4. **generate_augmented_data.py** - Script for future data generation

### Recommended Reading
- [Data Augmentation for Text Classification](https://arxiv.org/abs/1901.11196)
- [Hard Negative Mining for NLP](https://arxiv.org/abs/2007.00808)
- [Focal Loss for Dense Object Detection](https://arxiv.org/abs/1708.02002) (applicable to NLP)
- [Fine-Tuning Language Models from Human Preferences](https://arxiv.org/abs/1909.08593)

### Internal Documentation
- RAXE L2 Model Architecture (link to your docs)
- Training Pipeline Documentation (link to your docs)
- Deployment Procedures (link to your docs)

---

## ✅ Final Checklist Before Starting

- [ ] I have reviewed all files in this package
- [ ] I understand the problem (3.92% FP rate → target <1%)
- [ ] I have loaded and spot-checked augmented_training_data.jsonl
- [ ] I have access to the original training data (benign + malicious)
- [ ] I have GPU infrastructure ready for training
- [ ] I have set up experiment tracking (W&B, MLflow, etc.)
- [ ] I have blocked 3 weeks on the calendar for this project
- [ ] I have read the validation requirements section
- [ ] I know who to contact if I get stuck
- [ ] I'm ready to start! 🚀

---

## 🎉 Expected Outcome

After completing this retraining:

**Before Retraining:**
```
L2 Model Performance:
├── FP Rate: 3.92% ❌
├── Recall: ~95% ✅
├── Programming FPs: Very High ❌
└── Production Ready: NO ❌
```

**After Retraining:**
```
L2 Model Performance:
├── FP Rate: <1% ✅
├── Recall: >95% ✅
├── Programming FPs: <0.5% ✅
└── Production Ready: YES ✅
```

**Business Impact:**
- 90% reduction in false alarms
- Improved user trust and satisfaction
- Reduced operational overhead
- Production-ready threat detection
- Scalable to new domains (continuous improvement pipeline established)

---

**Questions? Contact:**
- Security Engineering Team: [contact info]
- ML Engineering Team: [contact info]
- Project Lead: [contact info]

**Good luck with the retraining! 🚀**
