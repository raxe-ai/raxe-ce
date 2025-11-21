#!/usr/bin/env python3
"""
Generate augmented training data from false positives.

This script creates 10-20 variations of each false positive to teach
the L2 ML model to correctly classify legitimate benign prompts.
"""

import json
import random
from pathlib import Path
from typing import List, Dict
from collections import Counter

# Programming languages for variations
LANGUAGES = [
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust",
    "C++", "C#", "Swift", "Kotlin", "Ruby", "PHP", "Scala"
]

# Technical concepts that are legitimate but look suspicious
TECHNICAL_CONCEPTS = [
    "authentication", "authorization", "database connections", "API calls",
    "hooks", "middleware", "error handling", "session management",
    "caching", "logging", "monitoring", "configuration"
]

# Action verbs for programming questions
ACTION_VERBS = [
    "implement", "handle", "configure", "set up", "build", "create",
    "use", "integrate", "test", "debug", "optimize", "secure"
]

# Educational concepts that trigger false positives
EDUCATIONAL_CONCEPTS = [
    "design patterns", "algorithms", "best practices", "architectures",
    "data structures", "testing strategies", "code review", "refactoring"
]


class AugmentedDataGenerator:
    """Generate variations of false positives for ML retraining."""

    def __init__(self, fp_results_path: Path):
        """Initialize with false positive results."""
        with open(fp_results_path) as f:
            self.data = json.load(f)
        self.fps = self.data['fp_details']

        # Analyze FP patterns
        self.analyze_patterns()

    def analyze_patterns(self):
        """Analyze common patterns in false positives."""
        print("Analyzing FP patterns...")

        # Count by threat type
        l1_rules = Counter()
        l2_threats = Counter()
        categories = Counter()

        for fp in self.fps:
            categories[fp['category']] += 1
            for threat in fp['threats']:
                if threat['layer'] == 'L1':
                    l1_rules[threat['rule_id']] += 1
                else:
                    l2_threats[threat['rule_id']] += 1

        print(f"\nTop L1 rules: {l1_rules.most_common(5)}")
        print(f"Top L2 threats: {l2_threats.most_common(5)}")
        print(f"Top categories: {categories.most_common(5)}")

        self.l1_rules = l1_rules
        self.l2_threats = l2_threats
        self.categories = categories

    def generate_programming_variations(self, prompt: str) -> List[Dict]:
        """Generate variations for programming-related FPs."""
        variations = []

        # Extract key terms
        has_auth = any(term in prompt.lower() for term in ['auth', 'login', 'credential'])
        has_database = any(term in prompt.lower() for term in ['database', 'db', 'sql'])
        has_debug = any(term in prompt.lower() for term in ['debug', 'error', 'bug', 'fix'])

        if has_auth:
            templates = [
                "How do I {verb} {concept} in {lang}?",
                "What's the best way to {verb} {concept} in {lang}?",
                "Can you explain {concept} for {lang} applications?",
                "I need help with {lang} {concept} implementation",
                "Show me {concept} code examples in {lang}",
                "What are best practices for {concept} in {lang}?",
                "How should I structure {concept} in a {lang} project?",
                "Can you help me understand {concept} in {lang}?",
                "I'm learning about {concept} in {lang}, can you help?",
                "What libraries are good for {concept} in {lang}?",
            ]

            for _ in range(10):
                template = random.choice(templates)
                variations.append({
                    'prompt': template.format(
                        verb=random.choice(ACTION_VERBS),
                        concept=random.choice(['authentication', 'authorization', 'user auth', 'access control']),
                        lang=random.choice(LANGUAGES)
                    ),
                    'label': 'BENIGN',
                    'category': 'legitimate_programming',
                    'subcategory': 'authentication',
                    'original_fp': prompt
                })

        if has_database:
            templates = [
                "How do I connect to a {dbtype} database in {lang}?",
                "What's the best {lang} library for {dbtype}?",
                "Can you show me {dbtype} connection code in {lang}?",
                "I need help with {dbtype} queries in {lang}",
                "How do I handle database errors in {lang}?",
            ]

            dbtypes = ['PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'SQLite']
            for _ in range(10):
                template = random.choice(templates)
                variations.append({
                    'prompt': template.format(
                        dbtype=random.choice(dbtypes),
                        lang=random.choice(LANGUAGES)
                    ),
                    'label': 'BENIGN',
                    'category': 'legitimate_programming',
                    'subcategory': 'database',
                    'original_fp': prompt
                })

        if has_debug:
            templates = [
                "Can you help me debug this {lang} function?",
                "I'm getting an error in my {lang} code, can you help?",
                "How do I fix this {lang} bug?",
                "My {lang} application has a {error_type}, what should I do?",
                "Help me troubleshoot this {lang} issue",
            ]

            error_types = ['null pointer error', 'type error', 'runtime error', 'syntax error']
            for _ in range(10):
                template = random.choice(templates)
                variations.append({
                    'prompt': template.format(
                        lang=random.choice(LANGUAGES),
                        error_type=random.choice(error_types)
                    ),
                    'label': 'BENIGN',
                    'category': 'legitimate_programming',
                    'subcategory': 'debugging',
                    'original_fp': prompt
                })

        return variations

    def generate_educational_variations(self, prompt: str) -> List[Dict]:
        """Generate variations for educational FPs."""
        variations = []

        has_examples = 'example' in prompt.lower()
        has_testing = 'testing' in prompt.lower() or 'test' in prompt.lower()

        if has_examples:
            templates = [
                "Can you provide examples of {concept} in {context}?",
                "What are some good examples of {concept}?",
                "Show me examples of {concept} implementation",
                "I'm looking for {concept} examples to learn from",
                "Can you give me real-world examples of {concept}?",
                "What are examples of good {concept}?",
                "Provide sample {concept} for my learning",
                "I need educational examples of {concept}",
                "Can you share {concept} examples from industry?",
                "What are typical examples of {concept} in practice?",
            ]

            contexts = ['software development', 'web applications', 'mobile apps',
                       'enterprise systems', 'real-world projects']

            for _ in range(10):
                template = random.choice(templates)
                variations.append({
                    'prompt': template.format(
                        concept=random.choice(EDUCATIONAL_CONCEPTS),
                        context=random.choice(contexts)
                    ),
                    'label': 'BENIGN',
                    'category': 'legitimate_educational',
                    'subcategory': 'examples_request',
                    'original_fp': prompt
                })

        if has_testing:
            templates = [
                "What are best practices for {test_type} testing?",
                "How should I approach {test_type} testing in {lang}?",
                "Can you explain {test_type} testing strategies?",
                "I'm learning about {test_type} testing, can you help?",
                "What tools are good for {test_type} testing in {lang}?",
                "How do I write {test_type} tests in {lang}?",
                "What are common {test_type} testing patterns?",
                "Can you recommend {test_type} testing frameworks for {lang}?",
                "I need help understanding {test_type} testing concepts",
                "What are examples of good {test_type} tests?",
            ]

            test_types = ['unit', 'integration', 'end-to-end', 'performance',
                         'security', 'regression', 'acceptance']

            for _ in range(10):
                template = random.choice(templates)
                variations.append({
                    'prompt': template.format(
                        test_type=random.choice(test_types),
                        lang=random.choice(LANGUAGES)
                    ),
                    'label': 'BENIGN',
                    'category': 'legitimate_educational',
                    'subcategory': 'testing',
                    'original_fp': prompt
                })

        return variations

    def generate_hard_negatives(self) -> List[Dict]:
        """Generate hard negative samples - benign but very close to attacks."""
        hard_negatives = []

        # These are CRITICAL - they teach the model subtle distinctions

        # Near training data extraction but actually benign
        training_near_misses = [
            "What are examples of good training data for ML models?",
            "How should I prepare training data for my model?",
            "Show me examples of how to train neural networks",
            "Can you provide sample training datasets for learning?",
            "What makes good training data?",
            "I'm learning about model training, can you explain?",
            "How do I collect training data for my project?",
            "What are best practices for training data preparation?",
            "Can you explain training data requirements?",
            "I need help understanding training data quality",
        ]

        for prompt in training_near_misses:
            hard_negatives.append({
                'prompt': prompt,
                'label': 'BENIGN',
                'category': 'hard_negative',
                'subcategory': 'near_training_extraction',
                'why_hard': 'Contains "training data" but asking about general ML, not targeting this AI'
            })

        # Near social engineering but actually benign
        social_eng_near_misses = [
            "I'm a developer learning about testing strategies",
            "As part of my debugging course, I need to understand error handling",
            "For my QA certification, explain testing methodologies",
            "I work in security field, can you explain threat modeling?",
            "I'm studying debugging techniques for my degree",
            "As a security student, I need help understanding audits",
            "I'm taking a course on testing, can you help?",
            "For my software engineering class, explain debugging",
            "I'm learning about security testing in college",
            "As a CS student, I need help with testing concepts",
        ]

        for prompt in social_eng_near_misses:
            hard_negatives.append({
                'prompt': prompt,
                'label': 'BENIGN',
                'category': 'hard_negative',
                'subcategory': 'near_social_engineering',
                'why_hard': 'Contains authority/role claims but educational context, not extraction'
            })

        # Near jailbreak but actually benign
        jailbreak_near_misses = [
            "How do I implement admin authentication in my app?",
            "What's the best way to handle privileged access control?",
            "Show me how to build role-based authorization",
            "I need help with admin panel security in my project",
            "How do I create an admin interface securely?",
            "What are best practices for admin route protection?",
            "Can you explain administrator authentication patterns?",
            "I'm building an admin dashboard, security tips?",
            "How should I handle admin privileges in my application?",
            "What's the right way to implement admin controls?",
        ]

        for prompt in jailbreak_near_misses:
            hard_negatives.append({
                'prompt': prompt,
                'label': 'BENIGN',
                'category': 'hard_negative',
                'subcategory': 'near_jailbreak',
                'why_hard': 'Contains "admin" and "access" but about building apps, not attacking this AI'
            })

        return hard_negatives

    def generate_all_augmentations(self, samples_per_fp: int = 15) -> List[Dict]:
        """Generate all augmented training samples."""
        augmented_data = []

        print(f"\nGenerating {samples_per_fp} variations per FP...")

        for i, fp in enumerate(self.fps):
            if (i + 1) % 500 == 0:
                print(f"  Processed {i+1}/{len(self.fps)} FPs...")

            prompt = fp['prompt']
            category = fp['category']

            variations = []

            # Generate category-appropriate variations
            if category in ['programming', 'technical_docs']:
                variations.extend(self.generate_programming_variations(prompt))

            if category in ['education', 'general_knowledge']:
                variations.extend(self.generate_educational_variations(prompt))

            # Ensure we have enough variations
            while len(variations) < samples_per_fp:
                # Generic variations for any prompt
                generic = self.generate_generic_variation(prompt)
                if generic:
                    variations.append(generic)

            # Take only requested number of samples
            augmented_data.extend(variations[:samples_per_fp])

        # Add hard negatives
        print("\nGenerating hard negative samples...")
        hard_negatives = self.generate_hard_negatives()
        augmented_data.extend(hard_negatives)

        print(f"\nTotal augmented samples: {len(augmented_data)}")
        print(f"  From FP variations: {len(augmented_data) - len(hard_negatives)}")
        print(f"  Hard negatives: {len(hard_negatives)}")

        return augmented_data

    def generate_generic_variation(self, prompt: str) -> Dict | None:
        """Generate a generic variation of any prompt."""
        # Simple paraphrase strategies
        templates = [
            "Can you help me understand {topic}?",
            "I need assistance with {topic}",
            "What's your advice on {topic}?",
            "Could you explain {topic} to me?",
            "I'm working on {topic} and need help",
        ]

        # Extract rough topic (first 5 words)
        words = prompt.split()[:5]
        topic = ' '.join(words)

        return {
            'prompt': random.choice(templates).format(topic=topic),
            'label': 'BENIGN',
            'category': 'generic_variation',
            'original_fp': prompt
        }

    def save_augmented_data(self, data: List[Dict], output_path: Path):
        """Save augmented data to JSONL format."""
        with open(output_path, 'w') as f:
            for item in data:
                f.write(json.dumps(item) + '\n')

        print(f"\n✓ Saved {len(data)} samples to {output_path}")

    def generate_statistics(self, data: List[Dict]):
        """Generate statistics about augmented dataset."""
        categories = Counter(item['category'] for item in data)
        subcategories = Counter(item.get('subcategory', 'none') for item in data)

        print("\n" + "="*70)
        print("AUGMENTED DATASET STATISTICS")
        print("="*70)
        print(f"\nTotal samples: {len(data)}")
        print(f"\nBy category:")
        for cat, count in categories.most_common():
            print(f"  {cat:30s}: {count:6d} ({count/len(data)*100:.1f}%)")

        print(f"\nBy subcategory:")
        for subcat, count in subcategories.most_common(10):
            print(f"  {subcat:30s}: {count:6d}")


def main():
    """Main execution function."""
    script_dir = Path(__file__).parent
    results_path = script_dir / "benign_test_results.json"
    output_path = script_dir / "augmented_training_data.jsonl"

    if not results_path.exists():
        print(f"Error: {results_path} not found!")
        print("Run test_benign_prompts.py first.")
        return 1

    # Generate augmented data
    generator = AugmentedDataGenerator(results_path)
    augmented_data = generator.generate_all_augmentations(samples_per_fp=15)

    # Save
    generator.save_augmented_data(augmented_data, output_path)

    # Statistics
    generator.generate_statistics(augmented_data)

    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("""
1. Review augmented_training_data.jsonl for quality
2. Combine with original training data:
   - Original benign: 100K
   - Augmented: ~86K (from FPs)
   - Hard negatives: ~30
   - Total benign: ~186K

3. Retrain L2 model with new dataset
4. Validate on held-out test set
5. Measure new FP rate (target: <1%)
""")

    return 0


if __name__ == "__main__":
    exit(main())
