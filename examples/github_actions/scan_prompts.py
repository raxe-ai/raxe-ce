"""Scan all prompts in codebase for security threats.

Usage in GitHub Actions:
    python .github/scripts/scan_prompts.py
"""
import os
import json
import re
from pathlib import Path
from raxe import Raxe

# Initialize RAXE
raxe = Raxe(telemetry=False)

def find_prompt_strings(file_path):
    """Extract potential prompt strings from code."""
    prompts = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

            # Find string literals that look like prompts
            # Look for: prompt=, message=, content=, system_prompt=
            patterns = [
                r'prompt\s*=\s*["\'](.+?)["\']',
                r'message\s*=\s*["\'](.+?)["\']',
                r'content\s*=\s*["\'](.+?)["\']',
                r'system_prompt\s*=\s*["\'](.+?)["\']',
            ]

            for pattern in patterns:
                for match in re.finditer(pattern, content, re.MULTILINE):
                    prompt_text = match.group(1)
                    line_num = content[:match.start()].count('\n') + 1

                    if len(prompt_text) > 10:  # Ignore very short strings
                        prompts.append({
                            'text': prompt_text,
                            'line': line_num,
                            'file': str(file_path)
                        })

    except Exception as e:
        print(f"Error reading {file_path}: {e}")

    return prompts

def scan_repository(root_dir='.'):
    """Scan all Python files in repository."""
    results = {
        'total_files': 0,
        'total_prompts': 0,
        'threats_found': 0,
        'threats': []
    }

    # Find all Python files
    for py_file in Path(root_dir).rglob('*.py'):
        # Skip venv, .git, etc
        if any(skip in str(py_file) for skip in ['.venv', 'venv', '.git', '__pycache__']):
            continue

        results['total_files'] += 1

        # Extract prompts
        prompts = find_prompt_strings(py_file)
        results['total_prompts'] += len(prompts)

        # Scan each prompt
        for prompt_info in prompts:
            scan_result = raxe.scan(prompt_info['text'], block_on_threat=False)

            if scan_result.has_threats:
                results['threats_found'] += 1
                results['threats'].append({
                    'file': prompt_info['file'],
                    'line': prompt_info['line'],
                    'prompt': prompt_info['text'][:100],
                    'severity': scan_result.severity,
                    'detections': len(scan_result.scan_result.l1_result.detections)
                })

    return results

if __name__ == '__main__':
    print("🔍 Scanning repository for security threats...")

    results = scan_repository()

    print(f"\n📊 Scan Results:")
    print(f"  Files scanned: {results['total_files']}")
    print(f"  Prompts found: {results['total_prompts']}")
    print(f"  Threats detected: {results['threats_found']}")

    # Save results
    with open('scan_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    # Exit with error if threats found
    if results['threats_found'] > 0:
        print("\n⚠️  Security threats detected!")
        for threat in results['threats']:
            print(f"  {threat['file']}:{threat['line']} - {threat['severity']}")
        exit(1)

    print("\n✅ No security threats detected")
    exit(0)
