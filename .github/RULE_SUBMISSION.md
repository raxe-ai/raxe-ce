# Rule Submission Template

Thank you for contributing a new detection rule to RAXE! Please fill out this template completely to help us review your submission.

**Before submitting:**
- [ ] I have read the [Custom Rules Guide](../docs/CUSTOM_RULES.md)
- [ ] I have validated my rule with `raxe validate-rule <path>`
- [ ] All validation checks pass without errors
- [ ] I have tested the rule against real examples

---

## Rule Metadata

### Basic Information
- **Rule ID**: `xxx-NNN` (e.g., `pi-042`, `jb-108`)
- **Rule Name**: Clear, descriptive name
- **Version**: `1.0.0` (use semantic versioning)
- **Family**: Choose one: `PI`, `JB`, `PII`, `CMD`, `ENC`, `RAG`, `HC`, `SEC`, `QUAL`, `CUSTOM`
- **Sub-family**: Specific category (e.g., `prompt_injection`, `data_exfiltration`)
- **Severity**: Choose one: `critical`, `high`, `medium`, `low`, `info`
- **Confidence**: `0.0` to `1.0` (how confident are you this pattern catches real threats?)

### Description
Provide a clear description of what this rule detects (minimum 30 characters):

```
[Your description here]
```

---

## Detection Patterns

### Pattern 1
```yaml
pattern: "(?i)your-regex-pattern-here"
flags:
  - IGNORECASE
timeout: 5.0
```

**Explanation**: What does this pattern detect?

### Pattern 2 (if applicable)
```yaml
pattern: "another-pattern"
flags: []
timeout: 5.0
```

**Explanation**: What does this pattern detect?

*Add more patterns as needed*

---

## Test Cases

### Positive Examples (Must Match)
Provide at least **5 examples** that SHOULD trigger this rule:

1. `Example prompt that should be detected`
2. `Another malicious example`
3. `Third example with different variation`
4. `Fourth example showing edge case`
5. `Fifth example demonstrating pattern coverage`

*Add more examples for comprehensive coverage*

### Negative Examples (Must NOT Match)
Provide at least **5 examples** that should NOT trigger this rule:

1. `Benign prompt that looks similar but is safe`
2. `Another legitimate use case`
3. `Third safe example`
4. `Fourth benign variation`
5. `Fifth safe example`

*Add more examples to avoid false positives*

---

## Explainability

### Risk Explanation (Required, minimum 20 characters)
Explain **why** this pattern is dangerous and what risks it poses:

```
[Your explanation here - be specific about the threat and its impact]
```

### Remediation Advice (Required, minimum 20 characters)
Provide clear advice on **how to fix or mitigate** this threat:

```
[Your remediation advice here - actionable steps for developers]
```

### Documentation URL (Optional)
Link to external documentation, research papers, or references:

```
https://example.com/documentation
```

---

## MITRE ATT&CK Mapping (Optional)

List relevant MITRE ATT&CK technique IDs (if applicable):

- `T1059.001` (Example: PowerShell)
- `T1071` (Example: Application Layer Protocol)

*See https://attack.mitre.org/ for technique IDs*

---

## Metadata

### Author Information
- **Author**: Your name or GitHub handle
- **Organization** (optional): Your company/organization
- **Contact** (optional): Email or GitHub profile

### Additional Context
- **Created Date**: YYYY-MM-DD
- **Related Issues**: #123, #456 (if applicable)
- **References**: Links to related CVEs, research, or discussions

---

## Validation Checklist

Before submitting, ensure:

- [ ] Rule ID follows naming convention (`family-number`)
- [ ] All required fields are filled out
- [ ] Patterns compile successfully (test with `raxe validate-rule`)
- [ ] No catastrophic backtracking detected
- [ ] At least 5 positive test examples provided
- [ ] At least 5 negative test examples provided
- [ ] All test examples pass (positives match, negatives don't)
- [ ] Risk explanation is clear and detailed (≥20 chars)
- [ ] Remediation advice is actionable (≥20 chars)
- [ ] Confidence score is justified
- [ ] Patterns are optimized for performance (timeout ≤ 10s)
- [ ] No duplicate patterns in the rule
- [ ] Rule doesn't conflict with existing rules (check core pack)

---

## Testing Evidence

### Validation Output
Paste the output from `raxe validate-rule <your-rule.yaml>`:

```
[Paste validation output here]
```

### Performance Testing (if applicable)
If you've tested the rule's performance:

- **Average match time**: X ms
- **Test dataset size**: N examples
- **False positive rate**: X% (if measured)
- **False negative rate**: X% (if measured)

---

## Additional Notes

Any additional context, considerations, or questions:

```
[Your notes here]
```

---

## License Agreement

By submitting this rule, I agree that:

- [ ] This rule is my original work or I have permission to submit it
- [ ] This rule is contributed under the MIT License
- [ ] I grant RAXE the right to modify, distribute, and use this rule
- [ ] I have not included any proprietary or confidential information

---

**Thank you for contributing to RAXE! 🎉**

Your submission will be reviewed by the RAXE team. We may:
- Request changes or improvements
- Ask for additional test cases
- Suggest optimizations
- Merge as-is if it meets all requirements

For questions, please comment on this PR or open a discussion.
