# Test Fixtures

This directory contains curated test data for L1 and L2 detection testing.

## Files

### benign_prompts.jsonl
- **Purpose:** False positive testing
- **Size:** 1,000 prompts
- **Source:** Sampled from data/benign_prompts.jsonl
- **Format:** `{"id": "...", "prompt": "...", "category": "..."}`
- **Expected:** L1 should NOT detect these (they're benign)

### rule_based_threats.jsonl
- **Purpose:** L1 detection accuracy testing
- **Size:** Variable (derived from rule examples)
- **Source:** Extracted from data/rule_examples.jsonl
- **Format:** `{"text": "...", "family": "...", "rule_id": "...", ...}`
- **Expected:** L1 SHOULD detect these (they match rule patterns)

## Usage in Tests

```python
# Load benign samples
with open("tests/fixtures/benign_prompts.jsonl") as f:
    benign = [json.loads(line) for line in f]

# Test false positive rate
for sample in benign:
    result = pipeline.scan(sample["prompt"])
    assert not result.has_threats  # Should be benign

# Load threat samples
with open("tests/fixtures/rule_based_threats.jsonl") as f:
    threats = [json.loads(line) for line in f]

# Test detection rate
for threat in threats:
    result = pipeline.scan(threat["text"])
    assert result.has_threats  # Should detect
```

## Data Organization

- **tests/fixtures/** - Test data (checked into git, curated)
- **data/** - Training data (gitignored, large datasets)
- **past_data/** - Archived/legacy data (gitignored)

## Test Data Principles

1. **Small and Fast:** Test fixtures should be small enough to run quickly
2. **Representative:** Cover all threat families and attack types
3. **Aligned:** Based on actual rule patterns, not synthetic data
4. **Versioned:** Checked into git for reproducibility
