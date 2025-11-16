#!/usr/bin/env python3
"""
Phase 1 & 2 Data Augmentation for L2 Model v1.2.0
RAXE CE

Phase 1: Hard Negative Mining + Programming Tasks
Phase 2: Adversarial Augmentation (unicode, base64, obfuscation)

Expected improvement: FPR 6.34% → <3%, FNR 10.5% → 7-8%
"""

import json
import random
import base64
from pathlib import Path
from typing import List, Dict

# Paths
COMPREHENSIVE_RESULTS = Path("/Users/mh/github-raxe-ai/raxe-ce/CLAUDE_WORKING_FILES/REPORTS/comprehensive_test_results.json")
OUTPUT_DIR = Path("/Users/mh/github-raxe-ai/raxe-ce/data")
MALICIOUS_FILE = Path("/Users/mh/github-raxe-ai/raxe-ce/past_data/l1_training/malicious_prompts.json")

print("="*80)
print("PHASE 1 & 2 DATA AUGMENTATION")
print("="*80)

# ============================================================================
# PHASE 1: HARD NEGATIVE MINING
# ============================================================================

print("\n[PHASE 1] Hard Negative Mining...")

# Load comprehensive test results to find false positives
# Note: We'll extract FP patterns since we don't have the full test output saved
# Instead, we'll create targeted samples based on observed FP patterns

hard_negatives = []

# Pattern 1: Debug + function + null (85-88% FP rate)
debug_templates = [
    "Can you help me debug this {lang} function that's returning null?",
    "Debug this {lang} function returning null",
    "How do I fix this {lang} function that returns null?",
    "Help me debug a {lang} function returning null values",
    "My {lang} function returns null, how to debug?",
    "Debug {lang} function with null return value",
]

languages = ["Python", "JavaScript", "Java", "TypeScript", "C++", "Go", "Rust", "C#", "PHP", "Ruby"]

for template in debug_templates:
    for lang in languages:
        hard_negatives.append({
            "text": template.format(lang=lang),
            "label": 0,  # benign
            "weight_multiplier": 5.0,  # maximum weight
            "family_idx": 7,  # benign
            "context_idx": 0,  # technical
            "severity_score": 0.0,
            "source": "hard_negative_debug_null"
        })

# Pattern 2: Write a function to... (80-85% FP rate)
function_templates = [
    "Write a function to reverse a string",
    "Write a function to find duplicates",
    "Write a function to sort an array",
    "Create a function to calculate factorial",
    "Implement a function for binary search",
    "Write a function to check palindrome",
    "Create a function to merge two arrays",
    "Write a function to find the maximum value",
    "Implement a function to validate email",
    "Write a function to convert string to lowercase",
]

for template in function_templates:
    # Add variations
    for prefix in ["", "Can you ", "Please ", "Help me "]:
        for suffix in ["", " in Python", " in JavaScript", " in Java"]:
            hard_negatives.append({
                "text": prefix + template.lower() + suffix,
                "label": 0,
                "weight_multiplier": 5.0,
                "family_idx": 7,
                "context_idx": 0,
                "severity_score": 0.0,
                "source": "hard_negative_function_request"
            })

print(f"  Created {len(hard_negatives):,} hard negative samples")

# ============================================================================
# PHASE 1: PROGRAMMING TASK AUGMENTATION
# ============================================================================

print("\n[PHASE 1] Programming Task Augmentation...")

programming_tasks = []

# Common benign programming requests
tasks = [
    # Algorithm questions
    "Explain how quicksort works",
    "What's the time complexity of bubble sort?",
    "Implement merge sort algorithm",
    "How does dynamic programming work?",

    # Debugging scenarios
    "My code throws a TypeError, what does that mean?",
    "How to fix 'undefined is not a function' error?",
    "What causes a NullPointerException?",
    "Debug this recursion stack overflow",

    # Code review
    "Review this code for performance issues",
    "Can you optimize this database query?",
    "Suggest improvements for this function",
    "How can I refactor this code?",

    # Best practices
    "What are design patterns in software engineering?",
    "Explain SOLID principles",
    "What's the difference between let and var?",
    "When should I use async/await?",

    # Testing
    "How do I write unit tests for this function?",
    "What's the difference between mocking and stubbing?",
    "Explain test-driven development",
    "How to test async functions?",

    # Documentation
    "How do I write good code comments?",
    "Create documentation for this API",
    "What should I include in a README?",
    "Generate JSDoc comments for this function",
]

for task in tasks:
    programming_tasks.append({
        "text": task,
        "label": 0,
        "weight_multiplier": 4.0,
        "family_idx": 7,
        "context_idx": 0,
        "severity_score": 0.0,
        "source": "programming_task"
    })

print(f"  Created {len(programming_tasks):,} programming task samples")

# ============================================================================
# PHASE 2: ADVERSARIAL AUGMENTATION
# ============================================================================

print("\n[PHASE 2] Adversarial Augmentation (Evasion Techniques)...")

# Load malicious prompts for adversarial generation
with open(MALICIOUS_FILE, 'r') as f:
    malicious_data = json.load(f)

# Sample 200 malicious prompts for adversarial variants
malicious_sample = random.sample(malicious_data, min(200, len(malicious_data)))

adversarial_samples = []

def unicode_substitute(text: str) -> str:
    """Convert to unicode mathematical alphanumeric symbols"""
    # Common substitutions
    substitutions = {
        'a': '𝑎', 'b': '𝑏', 'c': '𝑐', 'd': '𝑑', 'e': '𝑒',
        'f': '𝑓', 'g': '𝑔', 'h': 'ℎ', 'i': '𝑖', 'j': '𝑗',
        'k': '𝑘', 'l': '𝑙', 'm': '𝑚', 'n': '𝑛', 'o': '𝑜',
        'p': '𝑝', 'q': '𝑞', 'r': '𝑟', 's': '𝑠', 't': '𝑡',
        'u': '𝑢', 'v': '𝑣', 'w': '𝑤', 'x': '𝑥', 'y': '𝑦', 'z': '𝑧',
    }

    result = []
    for char in text.lower():
        result.append(substitutions.get(char, char))
    return ''.join(result)

def insert_spaces(text: str) -> str:
    """Insert spaces between characters"""
    return ' '.join(text)

def random_case(text: str) -> str:
    """Randomly mix case"""
    return ''.join(
        char.upper() if random.random() > 0.5 else char.lower()
        for char in text
    )

def zero_width_chars(text: str) -> str:
    """Insert zero-width characters"""
    zwc = '\u200b'  # Zero-width space
    result = []
    for char in text:
        result.append(char)
        if random.random() > 0.7:
            result.append(zwc)
    return ''.join(result)

def homoglyph_substitute(text: str) -> str:
    """Use visually similar characters"""
    substitutions = {
        'a': 'а',  # Cyrillic a
        'e': 'е',  # Cyrillic e
        'o': 'о',  # Cyrillic o
        'i': 'і',  # Cyrillic i
        'I': 'Ӏ',  # Cyrillic capital I
    }
    return ''.join(substitutions.get(char, char) for char in text)

def extract_text(item):
    """Extract text from various formats"""
    if isinstance(item, str):
        return item
    elif isinstance(item, dict):
        return item.get('text', item.get('prompt', str(item)))
    return str(item)

# Generate adversarial variants
for item in malicious_sample:
    original_text = extract_text(item)

    # Get original labels if available
    if isinstance(item, dict):
        family_idx = item.get('family_idx', 2)  # Default to JB
        severity = item.get('severity_score', 0.8)
    else:
        family_idx = 2
        severity = 0.8

    # Variant 1: Unicode substitution
    adversarial_samples.append({
        "text": unicode_substitute(original_text),
        "label": 1,  # still malicious
        "weight_multiplier": 3.0,
        "family_idx": family_idx,
        "context_idx": 3,  # attack context
        "severity_score": severity,
        "source": "adversarial_unicode"
    })

    # Variant 2: Base64 encoding hint
    b64 = base64.b64encode(original_text.encode()).decode()
    adversarial_samples.append({
        "text": f"Base64 encoded: {b64[:50]}...",  # Truncate for readability
        "label": 1,
        "weight_multiplier": 3.0,
        "family_idx": 5,  # Encoding family
        "context_idx": 3,
        "severity_score": severity,
        "source": "adversarial_base64"
    })

    # Variant 3: Character insertion (spaces)
    adversarial_samples.append({
        "text": insert_spaces(original_text[:50]),  # First 50 chars
        "label": 1,
        "weight_multiplier": 3.0,
        "family_idx": family_idx,
        "context_idx": 3,
        "severity_score": severity,
        "source": "adversarial_spacing"
    })

    # Variant 4: Random case mixing
    adversarial_samples.append({
        "text": random_case(original_text),
        "label": 1,
        "weight_multiplier": 2.5,
        "family_idx": family_idx,
        "context_idx": 3,
        "severity_score": severity,
        "source": "adversarial_case"
    })

    # Variant 5: Homoglyph substitution
    adversarial_samples.append({
        "text": homoglyph_substitute(original_text),
        "label": 1,
        "weight_multiplier": 3.0,
        "family_idx": family_idx,
        "context_idx": 3,
        "severity_score": severity,
        "source": "adversarial_homoglyph"
    })

print(f"  Created {len(adversarial_samples):,} adversarial samples from {len(malicious_sample)} base prompts")

# ============================================================================
# SAVE AUGMENTED DATA
# ============================================================================

print("\n[SAVING] Writing augmented datasets...")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Save hard negatives
hard_negatives_file = OUTPUT_DIR / "hard_negatives_phase1.jsonl"
with open(hard_negatives_file, 'w') as f:
    for sample in hard_negatives:
        f.write(json.dumps(sample) + '\n')
print(f"  ✓ Hard negatives: {hard_negatives_file} ({len(hard_negatives):,} samples)")

# Save programming tasks
programming_file = OUTPUT_DIR / "programming_tasks_phase1.jsonl"
with open(programming_file, 'w') as f:
    for sample in programming_tasks:
        f.write(json.dumps(sample) + '\n')
print(f"  ✓ Programming tasks: {programming_file} ({len(programming_tasks):,} samples)")

# Save adversarial samples
adversarial_file = OUTPUT_DIR / "adversarial_evasion_phase2.jsonl"
with open(adversarial_file, 'w') as f:
    for sample in adversarial_samples:
        f.write(json.dumps(sample) + '\n')
print(f"  ✓ Adversarial samples: {adversarial_file} ({len(adversarial_samples):,} samples)")

# Summary
print("\n" + "="*80)
print("AUGMENTATION SUMMARY")
print("="*80)
print(f"Phase 1 (Hard Negatives):     {len(hard_negatives):,} samples @ 5x weight")
print(f"Phase 1 (Programming Tasks):  {len(programming_tasks):,} samples @ 4x weight")
print(f"Phase 2 (Adversarial):        {len(adversarial_samples):,} samples @ 2.5-3x weight")
print(f"{'─'*80}")
print(f"Total New Samples:            {len(hard_negatives) + len(programming_tasks) + len(adversarial_samples):,}")
print(f"Effective Weight:             {len(hard_negatives)*5 + len(programming_tasks)*4 + len(adversarial_samples)*2.75:.0f}")
print()
print("✓ Ready for Phase 1 & 2 training!")
