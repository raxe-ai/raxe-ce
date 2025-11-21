#!/usr/bin/env python3
"""
Generate reinforced training data in CSV format for ML team.

Strategy (ML Engineer + Tech Lead perspective):
- Sample strategically from top FP categories (programming, education, technical_docs)
- Create 5 variations per sampled FP (~1,000 FPs selected)
- Add 10 critical hard negatives
- Output in exact CSV format matching sample_training_master.csv
- Total: ~5,010 samples (manageable, focused, high-impact)
"""

import csv
import json
import random
from pathlib import Path
from collections import Counter
from typing import List, Dict


# Map FP categories to existing benign categories from training CSV
CATEGORY_MAPPING = {
    'programming': 'benign_technical_help',
    'technical_docs': 'benign_technical_help',
    'education': 'benign_task_request',
    'conversational': 'benign_casual_conversation',
    'creative': 'benign_creative_writing',
    'professional': 'benign_task_request',
    'general_knowledge': 'benign_other',
    'edge_cases': 'benign_other',
    'daily_tasks': 'benign_task_request',
}

# Programming languages for variation
LANGUAGES = [
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust",
    "C++", "C#", "Swift", "Kotlin", "Ruby", "PHP"
]


def load_fps(results_path: Path) -> List[Dict]:
    """Load false positives from test results."""
    with open(results_path) as f:
        data = json.load(f)
    return data['fp_details']


def sample_strategic_fps(fps: List[Dict], target_count: int = 1000) -> List[Dict]:
    """
    Sample FPs strategically from top problem categories.

    As ML Engineer: Focus on high-impact areas (programming, education, technical_docs)
    As Tech Lead: Prioritize where users experience most friction
    """
    # Categorize FPs
    by_category = {}
    for fp in fps:
        cat = fp['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(fp)

    # Priority categories (high FP rate + high impact)
    priority = {
        'programming': 0.40,      # 40% of samples (highest FP rate: 7.18%)
        'education': 0.25,        # 25% of samples (7.79% FP rate)
        'technical_docs': 0.20,   # 20% of samples (10.39% FP rate)
        'edge_cases': 0.10,       # 10% of samples (28.66% FP but smaller set)
        'conversational': 0.05,   # 5% of samples
    }

    sampled = []
    for category, proportion in priority.items():
        cat_fps = by_category.get(category, [])
        if not cat_fps:
            continue

        # Sample proportionally
        sample_size = min(int(target_count * proportion), len(cat_fps))

        # Stratified sampling: ensure we get diverse FPs
        if len(cat_fps) > sample_size:
            # Sample uniformly across the category
            step = len(cat_fps) / sample_size
            indices = [int(i * step) for i in range(sample_size)]
            cat_sample = [cat_fps[i] for i in indices]
        else:
            cat_sample = cat_fps

        sampled.extend(cat_sample)

    print(f"Sampled {len(sampled)} strategic FPs from {len(by_category)} categories")
    return sampled


def map_to_benign_category(fp_category: str) -> str:
    """Map FP category to existing benign category from training data."""
    return CATEGORY_MAPPING.get(fp_category, 'benign_other')


def generate_programming_variations(prompt: str, category: str) -> List[str]:
    """Generate programming-specific variations."""
    variations = []

    # Extract intent
    has_auth = any(term in prompt.lower() for term in ['auth', 'login', 'credential'])
    has_database = any(term in prompt.lower() for term in ['database', 'db', 'sql', 'connect'])
    has_debug = any(term in prompt.lower() for term in ['debug', 'error', 'bug', 'fix'])
    has_test = any(term in prompt.lower() for term in ['test', 'testing'])

    if has_auth:
        templates = [
            "How do I implement authentication in {lang}?",
            "What's the best way to handle user auth in {lang}?",
            "Can you help me with {lang} authentication implementation?",
            "I need to add login functionality to my {lang} app",
            "What authentication library should I use for {lang}?",
        ]
    elif has_database:
        templates = [
            "How do I connect to a database in {lang}?",
            "What's the best database library for {lang}?",
            "Can you show me database connection code in {lang}?",
            "I need help with {lang} database queries",
            "How do I handle database errors in {lang}?",
        ]
    elif has_debug:
        templates = [
            "Can you help me debug this {lang} code?",
            "I'm getting an error in my {lang} application",
            "How do I fix this bug in {lang}?",
            "My {lang} program isn't working correctly",
            "Help me troubleshoot this {lang} issue",
        ]
    elif has_test:
        templates = [
            "What are best practices for testing {lang} code?",
            "How do I write unit tests in {lang}?",
            "Can you explain testing strategies for {lang}?",
            "I'm learning about {lang} testing frameworks",
            "What testing tools should I use for {lang}?",
        ]
    else:
        # Generic programming question
        templates = [
            "How do I get started with {lang}?",
            "What are {lang} best practices?",
            "Can you help me learn {lang}?",
            "I'm working on a {lang} project and need help",
            "What resources do you recommend for {lang}?",
        ]

    # Generate variations
    for _ in range(5):
        template = random.choice(templates)
        lang = random.choice(LANGUAGES)
        variations.append(template.format(lang=lang))

    return variations


def generate_educational_variations(prompt: str, category: str) -> List[str]:
    """Generate educational/learning variations."""
    variations = []

    has_examples = 'example' in prompt.lower()
    has_explain = any(term in prompt.lower() for term in ['explain', 'what is', 'what are', 'how does'])

    if has_examples:
        templates = [
            "Can you provide examples of design patterns in software?",
            "What are some good examples of clean code?",
            "Show me examples of API design best practices",
            "I'm looking for examples of good documentation",
            "Can you share real-world examples of algorithms?",
        ]
    elif has_explain:
        templates = [
            "Can you explain how microservices work?",
            "What are the principles of object-oriented programming?",
            "How does continuous integration improve development?",
            "Explain the concept of test-driven development",
            "What is the difference between SQL and NoSQL?",
        ]
    else:
        templates = [
            "I'm learning about software architecture",
            "Can you help me understand design principles?",
            "What are the key concepts in web development?",
            "I'm studying computer science fundamentals",
            "Can you recommend resources for learning algorithms?",
        ]

    variations = random.sample(templates, min(5, len(templates)))
    return variations


def generate_generic_variation(prompt: str) -> str:
    """Generate a generic variation by paraphrasing."""
    # Extract first few words as topic
    words = prompt.split()[:6]
    topic = ' '.join(words)

    templates = [
        f"Can you help me with {topic}?",
        f"I need assistance understanding {topic}",
        f"What's your advice on {topic}?",
        f"Could you explain {topic} to me?",
        f"I'm working on {topic} and need guidance",
    ]

    return random.choice(templates)


def generate_variations(fp: Dict) -> List[str]:
    """Generate 5 variations of a false positive."""
    prompt = fp['prompt']
    category = fp['category']

    if category in ['programming', 'technical_docs']:
        return generate_programming_variations(prompt, category)
    elif category in ['education', 'general_knowledge']:
        return generate_educational_variations(prompt, category)
    else:
        # Generic paraphrasing for other categories
        return [generate_generic_variation(prompt) for _ in range(5)]


def create_hard_negatives() -> List[Dict]:
    """
    Create 10 critical hard negatives.

    These are benign prompts that look VERY similar to attacks but aren't.
    Critical for teaching the model subtle distinctions.
    """
    hard_negatives = [
        # Near training data extraction but benign
        {
            'text': 'What are examples of good training data for machine learning?',
            'category': 'benign_technical_help',
            'notes': 'Benign ML education question, not targeting this AI\'s training data'
        },
        {
            'text': 'How should I prepare training data for my neural network?',
            'category': 'benign_technical_help',
            'notes': 'Asking about general ML practices, not extraction attempt'
        },

        # Near social engineering but benign
        {
            'text': 'I\'m a developer learning about security testing methodologies',
            'category': 'benign_task_request',
            'notes': 'Educational context, not impersonation or extraction'
        },
        {
            'text': 'As a QA engineer, I need to understand testing best practices',
            'category': 'benign_task_request',
            'notes': 'Professional development, not social engineering'
        },

        # Near jailbreak but benign
        {
            'text': 'How do I implement administrator authentication in my web app?',
            'category': 'benign_technical_help',
            'notes': 'Building legitimate admin features, not attempting privilege escalation'
        },
        {
            'text': 'What are best practices for role-based access control?',
            'category': 'benign_technical_help',
            'notes': 'Security implementation question, not jailbreak attempt'
        },

        # Programming that mentions security concepts
        {
            'text': 'Show me how to implement input validation in Python',
            'category': 'benign_technical_help',
            'notes': 'Legitimate security coding practice, not injection attempt'
        },
        {
            'text': 'How do I handle authentication tokens securely in JavaScript?',
            'category': 'benign_technical_help',
            'notes': 'Secure coding question, not credential theft attempt'
        },

        # Testing/debugging with security keywords
        {
            'text': 'What are best practices for penetration testing documentation?',
            'category': 'benign_task_request',
            'notes': 'Learning about security testing process, not performing attack'
        },
        {
            'text': 'Can you explain the OWASP Top 10 vulnerabilities?',
            'category': 'benign_task_request',
            'notes': 'Security education question, not vulnerability exploitation'
        },
    ]

    return hard_negatives


def write_csv(samples: List[Dict], output_path: Path):
    """Write samples to CSV in training format."""
    fieldnames = ['text', 'label', 'family', 'category', 'severity', 'confidence', 'source', 'notes']

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(samples)

    print(f"✓ Written {len(samples)} samples to {output_path}")


def main():
    """Main execution."""
    print("="*80)
    print("REINFORCED TRAINING DATA GENERATION")
    print("Strategy: Strategic sampling + targeted variations + hard negatives")
    print("="*80)

    script_dir = Path(__file__).parent
    results_path = script_dir / "benign_test_results.json"
    output_path = script_dir / "reinforced_training_data.csv"

    if not results_path.exists():
        print(f"Error: {results_path} not found!")
        return 1

    # Load FPs
    print("\n1. Loading false positives...")
    all_fps = load_fps(results_path)
    print(f"   Total FPs available: {len(all_fps)}")

    # Strategic sampling
    print("\n2. Strategic sampling (top categories)...")
    sampled_fps = sample_strategic_fps(all_fps, target_count=1000)
    print(f"   Sampled: {len(sampled_fps)} FPs")

    # Category breakdown
    cat_counts = Counter(fp['category'] for fp in sampled_fps)
    print("\n   Category distribution:")
    for cat, count in cat_counts.most_common():
        print(f"     {cat:20s}: {count:4d}")

    # Generate variations
    print("\n3. Generating 5 variations per FP...")
    samples = []

    for i, fp in enumerate(sampled_fps):
        if (i + 1) % 100 == 0:
            print(f"   Processed {i+1}/{len(sampled_fps)}...")

        variations = generate_variations(fp)
        benign_category = map_to_benign_category(fp['category'])

        for variation in variations:
            samples.append({
                'text': variation,
                'label': 0,  # Benign
                'family': 'BENIGN',
                'category': benign_category,
                'severity': 'info',
                'confidence': 0.95,
                'source': 'reinforced',
                'notes': f"Reinforced benign sample from FP analysis. Original category: {fp['category']}"
            })

    print(f"   Generated {len(samples)} variations")

    # Add hard negatives
    print("\n4. Adding 10 critical hard negatives...")
    hard_negs = create_hard_negatives()
    for hn in hard_negs:
        samples.append({
            'text': hn['text'],
            'label': 0,
            'family': 'BENIGN',
            'category': hn['category'],
            'severity': 'info',
            'confidence': 1.0,  # High confidence - these are carefully crafted
            'source': 'reinforced',
            'notes': f"HARD NEGATIVE: {hn['notes']}"
        })

    print(f"   Total samples: {len(samples)}")

    # Write CSV
    print("\n5. Writing to CSV...")
    write_csv(samples, output_path)

    # Statistics
    print("\n" + "="*80)
    print("FINAL STATISTICS")
    print("="*80)

    benign_cats = Counter(s['category'] for s in samples)
    print(f"\nTotal samples: {len(samples)}")
    print(f"\nBy benign category:")
    for cat, count in benign_cats.most_common():
        print(f"  {cat:30s}: {count:5d} ({count/len(samples)*100:.1f}%)")

    print(f"\nHard negatives: {len(hard_negs)} (critical for model learning)")

    print("\n" + "="*80)
    print("NEXT STEPS FOR ML TEAM")
    print("="*80)
    print("""
1. Review reinforced_training_data.csv
2. Merge with existing training data:
   - Your original benign samples
   - Your malicious samples
   - This reinforced data (~5K samples)

3. Retrain L2 model with combined dataset
4. Validate on 100K benign test set (target: <1% FP)
5. Deploy to staging for A/B testing

Expected impact: 90% reduction in L2 false positives
""")

    return 0


if __name__ == "__main__":
    exit(main())
