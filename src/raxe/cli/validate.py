"""CLI command for validating rule submissions.

Provides the 'raxe validate-rule' command for community rule authors.
"""
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from raxe.domain.rules.validator import RuleValidator

console = Console()


@click.command("validate-rule")
@click.argument("rule_path", type=click.Path(exists=True), required=True)
@click.option(
    "--strict",
    is_flag=True,
    help="Treat warnings as errors",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON",
)
def validate_rule_command(rule_path: str, strict: bool, output_json: bool) -> None:
    """Validate a rule file for submission.

    \b
    This command performs comprehensive validation including:
    - YAML syntax checking
    - Schema compliance verification
    - Pattern compilation and safety checks
    - Catastrophic backtracking detection
    - Explainability requirements
    - Test example validation
    - Best practices checking

    \b
    Examples:
        raxe validate-rule my-rule.yaml
        raxe validate-rule my-rule.yaml --strict
        raxe validate-rule my-rule.yaml --json

    \b
    Exit codes:
        0 = Validation passed
        1 = Validation failed (errors found)
        2 = Warnings found (only with --strict)
    """
    validator = RuleValidator()
    result = validator.validate_file(rule_path)

    if output_json:
        _output_json(result, rule_path)
    else:
        _output_human(result, rule_path)

    # Determine exit code
    if result.has_errors:
        raise SystemExit(1)
    elif strict and result.warnings_count > 0:
        raise SystemExit(2)
    else:
        raise SystemExit(0)


def _output_human(result, rule_path: str) -> None:
    """Output human-readable validation results.

    Args:
        result: ValidationResult object
        rule_path: Path to the validated rule file
    """
    console.print()

    # Header
    if result.valid:
        header_style = "bold green"
        header_text = "✓ VALIDATION PASSED"
    else:
        header_style = "bold red"
        header_text = "✗ VALIDATION FAILED"

    console.print(Panel(
        f"[{header_style}]{header_text}[/{header_style}]\n"
        f"Rule: [cyan]{Path(rule_path).name}[/cyan]"
        + (f"\nID: [cyan]{result.rule_id}[/cyan]" if result.rule_id else ""),
        title="Rule Validation",
        border_style=header_style,
    ))

    # Summary
    if result.issues:
        summary_parts = []
        if result.errors_count > 0:
            summary_parts.append(f"[red]{result.errors_count} error(s)[/red]")
        if result.warnings_count > 0:
            summary_parts.append(f"[yellow]{result.warnings_count} warning(s)[/yellow]")

        info_count = len([i for i in result.issues if i.severity == 'info'])
        if info_count > 0:
            summary_parts.append(f"[blue]{info_count} info[/blue]")

        console.print(f"\n{' • '.join(summary_parts)}\n")

        # Issues table
        table = Table(show_header=True, header_style="bold", expand=True)
        table.add_column("Severity", style="bold", width=10)
        table.add_column("Field", style="cyan", width=30)
        table.add_column("Issue", width=50)

        for issue in result.issues:
            severity_style = _get_severity_style(issue.severity)
            severity_text = issue.severity.upper()

            table.add_row(
                f"[{severity_style}]{severity_text}[/{severity_style}]",
                issue.field,
                issue.message,
            )

        console.print(table)

        # Suggestions
        has_suggestions = any(issue.suggestion for issue in result.issues)
        if has_suggestions:
            console.print("\n[bold]💡 Suggestions:[/bold]\n")
            for i, issue in enumerate(result.issues, 1):
                if issue.suggestion:
                    severity_style = _get_severity_style(issue.severity)
                    console.print(
                        f"  [{severity_style}]{i}.[/{severity_style}] "
                        f"[cyan]{issue.field}:[/cyan] {issue.suggestion}"
                    )
    else:
        console.print("[green]No issues found! ✨[/green]\n")

    # Next steps
    if result.valid:
        console.print(Panel(
            "[green]✓[/green] Your rule is ready for submission!\n\n"
            "[bold]Next steps:[/bold]\n"
            "1. Review the validation results above\n"
            "2. Read CONTRIBUTING_RULES.md for submission guidelines\n"
            "3. Submit a pull request with label 'new-rule'\n"
            "4. Our team will review your contribution\n\n"
            "[dim]Thank you for contributing to RAXE! 🎉[/dim]",
            title="Ready to Submit",
            border_style="green",
        ))
    else:
        console.print(Panel(
            "[red]✗[/red] Please fix the errors above before submitting.\n\n"
            "[bold]Tips:[/bold]\n"
            "• Fix all ERROR-level issues first\n"
            "• Address WARNING-level issues for better quality\n"
            "• Review INFO suggestions for best practices\n"
            "• Run validation again after fixes\n\n"
            "[dim]Need help? See CONTRIBUTING_RULES.md or open a discussion.[/dim]",
            title="Action Required",
            border_style="red",
        ))

    console.print()


def _output_json(result, rule_path: str) -> None:
    """Output validation results as JSON.

    Args:
        result: ValidationResult object
        rule_path: Path to the validated rule file
    """
    import json

    output = {
        "valid": result.valid,
        "rule_path": str(rule_path),
        "rule_id": result.rule_id,
        "summary": {
            "errors": result.errors_count,
            "warnings": result.warnings_count,
            "info": len([i for i in result.issues if i.severity == 'info']),
        },
        "issues": [
            {
                "severity": issue.severity,
                "field": issue.field,
                "message": issue.message,
                "suggestion": issue.suggestion,
            }
            for issue in result.issues
        ],
    }

    console.print(json.dumps(output, indent=2))


def _get_severity_style(severity: str) -> str:
    """Get rich style for severity level.

    Args:
        severity: Severity level (error, warning, info)

    Returns:
        Rich style string
    """
    styles = {
        'error': 'red',
        'warning': 'yellow',
        'info': 'blue',
    }
    return styles.get(severity, 'white')
