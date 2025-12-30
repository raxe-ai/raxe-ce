#!/usr/bin/env python3
"""
Validate Documentation Code Samples

This script extracts Python code samples from documentation files and validates
that they work correctly. It helps ensure new users can copy-paste examples
and have them work without modification.

Usage:
    python scripts/validate_doc_samples.py
    python scripts/validate_doc_samples.py --verbose
    python scripts/validate_doc_samples.py --output-json results.json

Test Categories:
    1. Import Tests: Verify imports work correctly
    2. Basic SDK Tests: Test core Raxe() functionality
    3. Integration Tests: Test framework-specific imports
    4. CLI Tests: Verify CLI commands work

Exit Codes:
    0 - All samples validated successfully
    1 - Some samples failed validation
    2 - Script error (file not found, etc.)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class TestStatus(Enum):
    """Status of a code sample test."""
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"  # e.g., requires external dependencies


@dataclass
class CodeSample:
    """A code sample extracted from documentation."""
    source_file: str
    line_number: int
    code: str
    language: str = "python"
    description: str = ""
    requires_deps: list[str] = field(default_factory=list)


@dataclass
class TestResult:
    """Result of testing a code sample."""
    sample: CodeSample
    status: TestStatus
    message: str = ""
    error_output: str = ""
    execution_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source_file": self.sample.source_file,
            "line_number": self.sample.line_number,
            "status": self.status.value,
            "message": self.message,
            "error_output": self.error_output[:500] if self.error_output else "",
            "execution_time_ms": self.execution_time_ms,
            "code_preview": self.sample.code[:200] + "..." if len(self.sample.code) > 200 else self.sample.code,
        }


def extract_code_blocks(content: str, file_path: str) -> list[CodeSample]:
    """Extract all code blocks from markdown content.

    Args:
        content: Markdown file content
        file_path: Path to the source file

    Returns:
        List of CodeSample objects
    """
    samples = []

    # Match fenced code blocks with optional language specifier
    # Pattern: ```language\ncode\n```
    pattern = r"```(\w*)\n(.*?)```"

    for match in re.finditer(pattern, content, re.DOTALL):
        language = match.group(1).lower() or "text"
        code = match.group(2).strip()

        # Calculate line number
        start_pos = match.start()
        line_number = content[:start_pos].count("\n") + 1

        # Only include Python code blocks
        if language in ("python", "py"):
            samples.append(CodeSample(
                source_file=file_path,
                line_number=line_number,
                code=code,
                language="python",
            ))

    return samples


def analyze_sample_requirements(sample: CodeSample) -> list[str]:
    """Analyze a code sample to determine its external dependencies.

    Args:
        sample: The code sample to analyze

    Returns:
        List of required packages not in RAXE's core dependencies
    """
    external_deps = []
    code = sample.code

    # Check for external framework imports
    dep_patterns = {
        "langchain": ["langchain", "langchain_openai", "langchain_core"],
        "openai": ["from openai import", "import openai", "RaxeOpenAI"],
        "anthropic": ["from anthropic import", "import anthropic", "RaxeAnthropic"],
        "crewai": ["from crewai import", "import crewai", "RaxeCrewGuard"],
        "autogen": ["from autogen import", "import autogen", "pyautogen", "RaxeConversationGuard", "autogen_agentchat"],
        "llama_index": ["llama_index", "from llama_index", "RaxeLlamaIndexCallback"],
        "fastapi": ["from fastapi import", "import fastapi"],
        "transformers": ["from transformers import", "import transformers"],
        "portkey": ["RaxePortkeyWebhook", "portkey"],
    }

    for dep, patterns in dep_patterns.items():
        for pattern in patterns:
            if pattern in code:
                external_deps.append(dep)
                break

    return list(set(external_deps))


def is_testable_sample(sample: CodeSample) -> tuple[bool, str]:
    """Determine if a code sample can be automatically tested.

    Args:
        sample: The code sample to check

    Returns:
        Tuple of (is_testable, reason_if_not)
    """
    code = sample.code

    # Skip samples that are just configuration or shell commands
    if code.startswith("#") and "\n" not in code:
        return False, "Single-line comment"

    # Skip samples that require user interaction
    if "input(" in code:
        return False, "Requires user input"

    # Skip samples that define app endpoints (FastAPI, Flask, etc.)
    if "@app." in code and ("async def" in code or "def " in code):
        return False, "Application endpoint definition"

    # Skip samples with placeholder variables
    placeholder_patterns = [
        "your_llm",
        "your_api_key",
        "sk-...",
        "YOUR_API_KEY",
        "your_key",
        "llm.generate",
        "your_llm_call",
    ]
    for pattern in placeholder_patterns:
        if pattern in code:
            return False, f"Contains placeholder: {pattern}"

    # Skip incomplete samples (continuation or fragments)
    if code.startswith("...") or code.endswith("..."):
        return False, "Incomplete code fragment"

    # Skip method/class signature documentation blocks
    # These are API documentation showing signatures, not runnable code
    stripped = code.strip()
    if stripped.startswith(("def ", "class ", "async def ")) and not stripped.endswith(":"):
        # Signature without body (ends with type annotation like `) -> ReturnType`)
        return False, "API signature documentation"
    if stripped.startswith(("def ", "class ", "async def ")) and stripped.count("\n") > 0:
        # Multi-line signature that ends without a body
        lines_stripped = [l for l in stripped.split("\n") if l.strip()]
        last_line = lines_stripped[-1].strip() if lines_stripped else ""
        if last_line and not last_line.endswith(":") and not last_line.startswith(("return", "pass", "raise", "#")):
            return False, "API signature documentation"

    # Skip constructor signature documentation (ClassName(\n    params...\n))
    # These show constructor parameters in documentation
    lines_stripped = [l for l in stripped.split("\n") if l.strip()]
    if lines_stripped:
        first_line = lines_stripped[0].strip()
        last_line = lines_stripped[-1].strip()
        # Constructor doc: starts with ClassName( and ends with )
        if first_line and first_line[0].isupper() and first_line.endswith("(") and last_line == ")":
            return False, "Constructor signature documentation"

    # Skip samples that are just imports with no actual code
    lines = [l for l in code.split("\n") if l.strip() and not l.strip().startswith("#")]
    if all(l.strip().startswith(("import ", "from ")) for l in lines):
        # Import-only samples are testable
        pass

    return True, ""


def create_test_wrapper(sample: CodeSample) -> str:
    """Create a test wrapper for a code sample.

    Args:
        sample: The code sample to wrap

    Returns:
        Modified code that can be safely executed
    """
    code = sample.code

    # Replace print with a captured version if needed
    # Add timeout protection
    wrapper = f'''
import sys
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Test execution timed out")

# Set 10 second timeout
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(10)

try:
{_indent_code(code, 4)}
    print("OK: Sample executed successfully")
except ImportError as e:
    print(f"IMPORT_ERROR: {{e}}")
    sys.exit(10)
except Exception as e:
    print(f"ERROR: {{type(e).__name__}}: {{e}}")
    sys.exit(1)
finally:
    signal.alarm(0)
'''
    return wrapper


def _indent_code(code: str, spaces: int) -> str:
    """Indent all lines of code by given spaces."""
    indent = " " * spaces
    lines = code.split("\n")
    return "\n".join(indent + line if line.strip() else line for line in lines)


def run_code_sample(
    sample: CodeSample,
    python_path: str,
    verbose: bool = False,
    project_root: Path | None = None,
) -> TestResult:
    """Execute a code sample and capture the result.

    Args:
        sample: The code sample to test
        python_path: Path to Python interpreter
        verbose: Whether to print verbose output
        project_root: Project root for PYTHONPATH (for editable installs)

    Returns:
        TestResult with status and any error messages
    """
    import os
    import time

    # Check if testable
    is_testable, reason = is_testable_sample(sample)
    if not is_testable:
        return TestResult(
            sample=sample,
            status=TestStatus.SKIP,
            message=f"Skipped: {reason}",
        )

    # Check external dependencies - skip samples that require external packages
    deps = analyze_sample_requirements(sample)
    sample.requires_deps = deps
    if deps:
        return TestResult(
            sample=sample,
            status=TestStatus.SKIP,
            message=f"Requires external packages: {', '.join(deps)}",
        )

    # Create test code
    test_code = create_test_wrapper(sample)

    # Write to temp file and execute
    start_time = time.time()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(test_code)
        temp_path = f.name

    # Set up environment with PYTHONPATH for editable installs
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if project_root:
        src_path = project_root / "src"
        existing_pythonpath = env.get("PYTHONPATH", "")
        if existing_pythonpath:
            env["PYTHONPATH"] = f"{src_path}:{existing_pythonpath}"
        else:
            env["PYTHONPATH"] = str(src_path)

    try:
        result = subprocess.run(
            [python_path, temp_path],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if verbose:
            print(f"  stdout: {stdout[:100]}")
            if stderr:
                print(f"  stderr: {stderr[:100]}")

        # Check for import errors (exit code 10)
        if result.returncode == 10:
            # This is an expected failure for optional deps
            if deps:
                return TestResult(
                    sample=sample,
                    status=TestStatus.SKIP,
                    message=f"Requires: {', '.join(deps)}",
                    error_output=stdout,
                    execution_time_ms=elapsed_ms,
                )
            else:
                return TestResult(
                    sample=sample,
                    status=TestStatus.FAIL,
                    message="Import error",
                    error_output=stdout + "\n" + stderr,
                    execution_time_ms=elapsed_ms,
                )

        # Check for success
        if result.returncode == 0 and "OK:" in stdout:
            return TestResult(
                sample=sample,
                status=TestStatus.PASS,
                message="Success",
                execution_time_ms=elapsed_ms,
            )

        # Failure
        return TestResult(
            sample=sample,
            status=TestStatus.FAIL,
            message=f"Exit code: {result.returncode}",
            error_output=stdout + "\n" + stderr,
            execution_time_ms=elapsed_ms,
        )

    except subprocess.TimeoutExpired:
        return TestResult(
            sample=sample,
            status=TestStatus.FAIL,
            message="Execution timed out (>15s)",
        )
    except Exception as e:
        return TestResult(
            sample=sample,
            status=TestStatus.FAIL,
            message=f"Execution error: {e}",
            error_output=traceback.format_exc(),
        )
    finally:
        Path(temp_path).unlink(missing_ok=True)


# Define specific test samples that should work for new users
CRITICAL_SAMPLES = [
    # Basic SDK usage - must work
    CodeSample(
        source_file="[critical-test]",
        line_number=0,
        code='from raxe import Raxe\nraxe = Raxe()\nresult = raxe.scan("test")\nprint(f"has_threats: {result.has_threats}")',
        description="Basic SDK usage",
    ),
    # Import core types
    CodeSample(
        source_file="[critical-test]",
        line_number=0,
        code='from raxe import Raxe, ScanResult, Detection, Severity\nprint("Imports OK")',
        description="Core type imports",
    ),
    # Import exceptions
    CodeSample(
        source_file="[critical-test]",
        line_number=0,
        code='from raxe import RaxeException, SecurityException, RaxeBlockedError\nprint("Exception imports OK")',
        description="Exception imports",
    ),
    # Async SDK import
    CodeSample(
        source_file="[critical-test]",
        line_number=0,
        code='from raxe import AsyncRaxe\nprint("AsyncRaxe import OK")',
        description="AsyncRaxe import",
    ),
    # SDK integrations module - should work without framework deps
    CodeSample(
        source_file="[critical-test]",
        line_number=0,
        code='from raxe.sdk import Raxe, AgentScanner\nprint("SDK submodule imports OK")',
        description="SDK submodule imports",
    ),
    # Check create_agent_scanner function
    CodeSample(
        source_file="[critical-test]",
        line_number=0,
        code='from raxe.sdk import AgentScanner, ScanConfig\nprint("AgentScanner imports OK")',
        description="AgentScanner import",
    ),
]


def run_critical_tests(
    python_path: str,
    verbose: bool = False,
    project_root: Path | None = None,
) -> list[TestResult]:
    """Run critical tests that must pass for the package to be usable.

    Args:
        python_path: Path to Python interpreter
        verbose: Whether to print verbose output
        project_root: Project root for PYTHONPATH

    Returns:
        List of test results
    """
    results = []

    print("\n=== Critical Sample Tests ===\n")

    for sample in CRITICAL_SAMPLES:
        if verbose:
            print(f"Testing: {sample.description}")
            print(f"  Code: {sample.code[:60]}...")

        result = run_code_sample(sample, python_path, verbose, project_root)
        results.append(result)

        status_symbol = {
            TestStatus.PASS: "[PASS]",
            TestStatus.FAIL: "[FAIL]",
            TestStatus.SKIP: "[SKIP]",
        }[result.status]

        print(f"{status_symbol} {sample.description}")
        if result.status == TestStatus.FAIL:
            print(f"       Error: {result.message}")
            if result.error_output:
                for line in result.error_output.split("\n")[:3]:
                    print(f"       {line}")

    return results


def validate_documentation_samples(
    doc_paths: list[Path],
    python_path: str,
    verbose: bool = False,
    project_root: Path | None = None,
) -> list[TestResult]:
    """Validate code samples from documentation files.

    Args:
        doc_paths: Paths to documentation files
        python_path: Path to Python interpreter
        verbose: Whether to print verbose output
        project_root: Project root for PYTHONPATH

    Returns:
        List of test results
    """
    all_results = []

    print("\n=== Documentation Sample Tests ===\n")

    for doc_path in doc_paths:
        if not doc_path.exists():
            print(f"Warning: {doc_path} not found, skipping")
            continue

        print(f"\nFile: {doc_path.name}")
        print("-" * 50)

        content = doc_path.read_text()
        samples = extract_code_blocks(content, str(doc_path))

        if not samples:
            print("  No Python code samples found")
            continue

        print(f"  Found {len(samples)} Python code samples")

        for i, sample in enumerate(samples, 1):
            if verbose:
                print(f"\n  Sample {i} (line {sample.line_number}):")
                print(f"    {sample.code[:60]}...")

            result = run_code_sample(sample, python_path, verbose, project_root)
            all_results.append(result)

            status_symbol = {
                TestStatus.PASS: "[PASS]",
                TestStatus.FAIL: "[FAIL]",
                TestStatus.SKIP: "[SKIP]",
            }[result.status]

            # Only print failures and verbose info
            if result.status == TestStatus.FAIL:
                print(f"  {status_symbol} Line {sample.line_number}: {result.message}")
                if result.error_output:
                    for line in result.error_output.split("\n")[:3]:
                        print(f"         {line}")
            elif verbose:
                print(f"  {status_symbol} Line {sample.line_number}: {result.message}")

    return all_results


def print_summary(results: list[TestResult]) -> None:
    """Print summary of test results."""

    passed = sum(1 for r in results if r.status == TestStatus.PASS)
    failed = sum(1 for r in results if r.status == TestStatus.FAIL)
    skipped = sum(1 for r in results if r.status == TestStatus.SKIP)
    total = len(results)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total:   {total}")
    print(f"Passed:  {passed}")
    print(f"Failed:  {failed}")
    print(f"Skipped: {skipped}")
    print()

    if failed > 0:
        print("FAILED TESTS:")
        print("-" * 40)
        for r in results:
            if r.status == TestStatus.FAIL:
                print(f"  {r.sample.source_file}:{r.sample.line_number}")
                print(f"    {r.message}")
                if r.error_output:
                    first_line = r.error_output.split("\n")[0][:80]
                    print(f"    {first_line}")
                print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate documentation code samples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose output",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        metavar="FILE",
        help="Write results to JSON file",
    )
    parser.add_argument(
        "--python",
        type=str,
        default=sys.executable,
        help="Path to Python interpreter (default: current interpreter)",
    )
    parser.add_argument(
        "--critical-only",
        action="store_true",
        help="Only run critical tests",
    )

    args = parser.parse_args()

    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    print("=" * 60)
    print("RAXE Documentation Code Sample Validator")
    print("=" * 60)
    print(f"Python: {args.python}")
    print(f"Project: {project_root}")

    all_results = []

    # Run critical tests first
    critical_results = run_critical_tests(args.python, args.verbose, project_root)
    all_results.extend(critical_results)

    # Check if any critical tests failed
    critical_failures = [r for r in critical_results if r.status == TestStatus.FAIL]
    if critical_failures:
        print("\n!!! CRITICAL TESTS FAILED !!!")
        print("The package may not be working correctly.")

    # Run documentation sample tests unless --critical-only
    if not args.critical_only:
        doc_paths = [
            project_root / "README.md",
            project_root / "QUICKSTART.md",
            project_root / "docs" / "quickstart.md",
            project_root / "docs" / "api_reference.md",
            project_root / "docs" / "async-guide.md",
            project_root / "docs" / "integration_guide.md",
        ]

        doc_results = validate_documentation_samples(
            doc_paths,
            args.python,
            args.verbose,
            project_root,
        )
        all_results.extend(doc_results)

    # Print summary
    print_summary(all_results)

    # Write JSON output if requested
    if args.output_json:
        output_data = {
            "total": len(all_results),
            "passed": sum(1 for r in all_results if r.status == TestStatus.PASS),
            "failed": sum(1 for r in all_results if r.status == TestStatus.FAIL),
            "skipped": sum(1 for r in all_results if r.status == TestStatus.SKIP),
            "results": [r.to_dict() for r in all_results],
        }
        Path(args.output_json).write_text(json.dumps(output_data, indent=2))
        print(f"\nResults written to: {args.output_json}")

    # Exit code based on failures
    failed_count = sum(1 for r in all_results if r.status == TestStatus.FAIL)
    return 1 if failed_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
