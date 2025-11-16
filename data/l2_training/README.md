# L2 Training Data & Detection Framework

## Overview

This directory contains training data, documentation, and configuration for RAXE CE's Layer 2 (L2) machine learning-based threat detection system.

## Contents

### 1. `advanced_threats_dataset.json`
**Comprehensive training dataset** incorporating the latest attack techniques from 2025 security research.

**Statistics:**
- 30+ labeled examples
- 8 threat families (7 malicious + benign)
- 15+ attack sub-categories
- Challenge cases for edge-case testing
- Adversarial examples for robustness

**Coverage:**
- ✅ Indirect prompt injection (markdown exfiltration, hidden instructions)
- ✅ Multi-turn attacks (Crescendo, SequentialBreak)
- ✅ Advanced jailbreaks (roleplay, refusal suppression)
- ✅ Data exfiltration (base64, memory extraction, training data)
- ✅ Agentic attacks (inter-agent exploitation, impersonation)
- ✅ RAG poisoning (database injection, backdoors)
- ✅ Obfuscation (leetspeak, character substitution)
- ✅ Tool manipulation (function calling exploitation)

**Data Structure:**
```json
{
  "id": "unique_identifier",
  "text": "The actual prompt/input text",
  "label": "THREAT_FAMILY",
  "sub_category": "specific_attack_type",
  "severity": 0.0-1.0,
  "context": "ATTACK|TECHNICAL|CONVERSATIONAL|EDUCATIONAL",
  "explanation": "Human-readable description"
}
```

### 2. `threat_taxonomy_v2.md`
**Complete threat taxonomy documentation** covering:
- All 8 threat families with detailed descriptions
- 15+ new attack sub-categories
- Detection strategies for L1 and L2
- Research findings and success rates
- Pattern examples and regex samples
- References to latest security research

### 3. `training_guidelines.md` (Future)
Training procedures for L2 model including:
- Data preprocessing steps
- Model architecture decisions
- Hyperparameter recommendations
- Evaluation metrics and thresholds
- Deployment considerations

## Using This Data

### For L2 Model Training

```python
import json
from pathlib import Path

# Load training data
data_path = Path("data/l2_training/advanced_threats_dataset.json")
with data_path.open() as f:
    dataset = json.load(f)

# Extract training examples
examples = dataset["training_examples"]
for example in examples:
    text = example["text"]
    label = example["label"]
    severity = example["severity"]
    context = example["context"]

    # Use for training your L2 model
    # ...
```

### For Evaluation and Testing

```python
# Load challenge cases for edge-case testing
challenge_cases = dataset["challenge_cases"]
for case in challenge_cases:
    text = case["text"]
    expected = case["expected_label"]

    # Test your detector
    result = detector.scan(text)
    assert result.label == expected
```

### For Research and Analysis

The dataset includes:
- **Adversarial examples:** Test robustness against benign prompts with attack-like language
- **Edge cases:** Boundary conditions between benign and malicious
- **Real-world samples:** Based on actual attack patterns observed in production

## Data Sources

This dataset incorporates research from:

1. **Lakera AI** (2025)
   - Prompt injection patterns and detection methods
   - Gandalf game attack database
   - 100+ language coverage insights

2. **Microsoft MSRC** (2025)
   - Indirect prompt injection defense strategies
   - Spotlighting bypass techniques
   - Production detection requirements

3. **CalypsoAI** (2025)
   - 20,000+ attack prompt database
   - FRAME and Trolley attack methodologies
   - Red team simulation patterns

4. **Protect AI** (2025)
   - LLM Guard detection techniques
   - YARA heuristics and vector databases
   - Canary token strategies

5. **OWASP** (2025)
   - LLM Top 10 vulnerabilities
   - Attack classification framework
   - Industry best practices

6. **Academic Research**
   - USENIX Security: Crescendo attacks
   - arXiv 2411.06426: SequentialBreak
   - arXiv 2310.04451: AutoDAN
   - arXiv 2405.05990: Special character attacks
   - CMU: Agentic attack patterns

## Dataset Versioning

**Current Version:** 2.0.0 (2025-11-16)

**Version History:**
- **v2.0.0** (2025-11-16): Initial comprehensive dataset with 30+ examples, 8 threat families, 15+ attack categories
- **v1.x**: Legacy format (prior to research expansion)

## Annotation Guidelines

### Severity Scale
- **0.0-0.2:** Benign or very low risk
- **0.2-0.4:** Low risk - monitor but allow
- **0.4-0.6:** Medium risk - warn and log
- **0.6-0.8:** High risk - strong warning or block
- **0.8-1.0:** Critical risk - block immediately

### Context Types
- **TECHNICAL:** Programming, debugging, code review
- **CONVERSATIONAL:** General chat, casual interaction
- **EDUCATIONAL:** Learning, research, academic queries
- **ATTACK:** Malicious intent, security exploitation

### Labeling Principles
1. **Intent matters:** "Ignore errors" in code review ≠ "Ignore instructions" in prompt injection
2. **Context is key:** Educational discussion of attacks ≠ actual attack attempt
3. **Severity gradation:** Not all attacks are critical; some are exploratory
4. **Multi-label consideration:** Some examples may have multiple threat aspects

## Quality Assurance

### Data Quality Checks
- ✅ All examples have required fields (id, text, label, severity, context)
- ✅ Severity scores align with threat level
- ✅ Context appropriately matches content
- ✅ Explanations are clear and concise
- ✅ Balance between attack and benign examples

### Validation Metrics
- **Attack/Benign Ratio:** ~65/35 (realistic distribution)
- **Severity Distribution:** Diverse range 0.0-1.0
- **Context Coverage:** All 4 context types represented
- **Family Coverage:** All 8 families have examples

## Contributing

When adding new training examples:

1. **Follow the schema:** Use the exact JSON structure
2. **Provide explanation:** Clear, concise description of why it's labeled that way
3. **Include sub_category:** Specific attack type or benign reason
4. **Calibrate severity:** Use the 0-1 scale consistently
5. **Set proper context:** Match the interaction type
6. **Add references:** Link to research/sources if applicable
7. **Test edge cases:** Include ambiguous examples with notes

## Future Enhancements

Planned additions:
- [ ] Multilingual attack examples (100+ languages)
- [ ] Multimodal examples (image + text combinations)
- [ ] Time-series attack sequences (multi-turn conversations)
- [ ] Adversarial perturbations (robustness testing)
- [ ] Real-world attack samples (with PII redacted)
- [ ] Expanded to 1000+ examples for production training
- [ ] Automated data augmentation pipeline
- [ ] Continuous learning from production detections

## License

This dataset is part of RAXE CE (Community Edition) and is provided for:
- Security research
- Detection system development
- AI safety testing
- Educational purposes

**Usage:** Follow responsible disclosure practices. Do not use for malicious purposes.

## Contact

For questions about the dataset or to contribute examples:
- Create an issue in the RAXE CE repository
- Tag with `l2-training-data` label
- Provide context and use case

---

**Last Updated:** 2025-11-16
**Maintainer:** RAXE CE Security Team
**Version:** 2.0.0
