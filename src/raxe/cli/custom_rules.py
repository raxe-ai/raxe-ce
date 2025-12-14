"""Custom rules CLI commands.

Commands for creating, validating, and managing custom detection rules.
"""
from pathlib import Path

import click
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from raxe.cli.output import console, display_error, display_success, display_warning
from raxe.domain.rules.custom import CustomRuleBuilder
from raxe.infrastructure.rules.custom_loader import CustomRuleLoader


@click.group(name="custom")
def custom_rules() -> None:
    """Manage custom detection rules.

    Create, validate, and manage user-defined threat detection rules.

    Examples:
      raxe rules custom create
      raxe rules custom validate my_rule.yaml
      raxe rules custom install my_rule.yaml
      raxe rules custom list
    """
    pass


@custom_rules.command("create")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path (default: print to stdout)",
)
@click.option(
    "--interactive/--no-interactive",
    default=True,
    help="Interactive mode (default: interactive)",
)
def create_rule(output: str | None, interactive: bool) -> None:
    """Create a new custom rule interactively.

    Guides you through creating a custom detection rule with validation.

    Examples:
      raxe rules custom create
      raxe rules custom create --output my_rule.yaml
      raxe rules custom create --no-interactive
    """
    if not interactive:
        # Non-interactive: output template
        template = _get_rule_template()
        if output:
            Path(output).write_text(template)
            display_success(f"Rule template created: {output}")
        else:
            console.print("[bold cyan]Rule Template:[/bold cyan]")
            syntax = Syntax(template, "yaml", theme="monokai")
            console.print(syntax)
        return

    # Interactive mode
    console.print(Panel.fit(
        "[bold cyan]Custom Rule Creator[/bold cyan]\n\n"
        "Create a new threat detection rule by answering the prompts below.",
        title="RAXE",
    ))

    try:
        # Collect rule information
        rule_id = click.prompt("Rule ID (e.g., custom-001)", type=str)
        name = click.prompt("Rule name", type=str)
        description = click.prompt("Description", type=str)
        version = click.prompt("Version", default="0.0.1", type=str)

        # Detection configuration
        console.print("\n[bold]Detection Configuration[/bold]")
        layer = click.prompt(
            "Layer",
            type=click.Choice(["L1", "L2"]),
            default="L1",
        )

        pattern = ""
        if layer == "L1":
            pattern = click.prompt("Regex pattern", type=str)

        severity = click.prompt(
            "Severity",
            type=click.Choice(["critical", "high", "medium", "low", "info"]),
            default="medium",
        )

        confidence = click.prompt("Confidence (0.0-1.0)", default=0.9, type=float)
        category = click.prompt("Category", default="CUSTOM", type=str)

        # Optional examples
        console.print("\n[bold]Examples (optional)[/bold]")
        add_examples = click.confirm("Add test examples?", default=True)

        positive_examples = []
        negative_examples = []

        if add_examples:
            console.print("Enter positive examples (should match). Empty line to finish.")
            while True:
                example = click.prompt("Positive example", default="", show_default=False)
                if not example:
                    break
                positive_examples.append(example)

            console.print("Enter negative examples (should NOT match). Empty line to finish.")
            while True:
                example = click.prompt("Negative example", default="", show_default=False)
                if not example:
                    break
                negative_examples.append(example)

        # Build rule dict
        rule_dict = {
            "id": rule_id,
            "name": name,
            "description": description,
            "version": version,
            "author": "user",
            "detection": {
                "layer": layer,
                "severity": severity,
                "confidence": confidence,
                "category": category,
            },
        }

        if layer == "L1":
            rule_dict["detection"]["pattern"] = pattern

        if positive_examples or negative_examples:
            rule_dict["examples"] = {
                "positive": positive_examples,
                "negative": negative_examples,
            }

        rule_dict["metadata"] = {
            "tags": [],
            "references": [],
        }

        # Generate YAML
        import yaml
        yaml_content = yaml.dump(rule_dict, default_flow_style=False, sort_keys=False)

        # Show preview
        console.print("\n[bold cyan]Rule Preview:[/bold cyan]")
        syntax = Syntax(yaml_content, "yaml", theme="monokai")
        console.print(syntax)

        # Validate
        from raxe.domain.rules.custom import CustomRuleValidator
        is_valid, errors = CustomRuleValidator.validate_rule_dict(rule_dict)

        if not is_valid:
            display_error("Rule validation failed", ", ".join(errors))
            return

        # Test examples
        if add_examples:
            try:
                rule = CustomRuleBuilder.from_dict(rule_dict)
                examples_passed, failures = CustomRuleValidator.test_rule_examples(rule)

                if not examples_passed:
                    display_warning(
                        "Example tests failed:\n" + "\n".join(f"  - {f}" for f in failures)
                    )
                    if not click.confirm("Continue anyway?", default=False):
                        return
                else:
                    display_success("All example tests passed!")
            except Exception as e:
                display_error("Example validation failed", str(e))
                if not click.confirm("Continue anyway?", default=False):
                    return

        # Save or print
        if output:
            output_path = Path(output)
            output_path.write_text(yaml_content)
            display_success(f"Rule created: {output_path}")
        else:
            if click.confirm("Save to custom rules directory?", default=True):
                loader = CustomRuleLoader()
                output_path = loader.custom_rules_dir / f"{rule_id}.yaml"
                output_path.write_text(yaml_content)
                display_success(f"Rule saved: {output_path}")

    except click.Abort:
        console.print("\n[yellow]Rule creation cancelled[/yellow]")
    except Exception as e:
        display_error("Rule creation failed", str(e))


@custom_rules.command("validate")
@click.argument("file_path", type=click.Path(exists=True))
def validate_rule(file_path: str) -> None:
    """Validate a custom rule YAML file.

    Checks syntax, structure, pattern validity, and example tests.

    Examples:
      raxe rules custom validate my_rule.yaml
    """
    loader = CustomRuleLoader()

    console.print(f"Validating: [cyan]{file_path}[/cyan]")

    is_valid, errors = loader.validate_file(Path(file_path))

    if is_valid:
        display_success("Rule validation passed!")

        # Try to load and show details
        try:
            rule = loader.load_rule_from_file(Path(file_path))
            console.print(f"\nRule: [bold]{rule.name}[/bold] ({rule.versioned_id})")
            console.print(f"Severity: [bold]{rule.severity.value.upper()}[/bold]")
            console.print(f"Confidence: {rule.confidence:.2f}")

            if rule.patterns:
                console.print(f"Patterns: {len(rule.patterns)}")

            if rule.examples.should_match or rule.examples.should_not_match:
                console.print(
                    f"Examples: {len(rule.examples.should_match)} positive, "
                    f"{len(rule.examples.should_not_match)} negative"
                )
        except Exception as e:
            display_warning(f"Could not load rule details: {e}")
    else:
        display_error("Rule validation failed", "")
        for error in errors:
            console.print(f"  [red]✗[/red] {error}")


@custom_rules.command("install")
@click.argument("file_path", type=click.Path(exists=True))
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing rule",
)
def install_rule(file_path: str, force: bool) -> None:
    """Install a custom rule from a YAML file.

    Validates and copies the rule to the custom rules directory.

    Examples:
      raxe rules custom install my_rule.yaml
      raxe rules custom install my_rule.yaml --force
    """
    loader = CustomRuleLoader()

    # Validate first
    is_valid, errors = loader.validate_file(Path(file_path))
    if not is_valid:
        display_error("Rule validation failed", "")
        for error in errors:
            console.print(f"  [red]✗[/red] {error}")
        return

    try:
        # Load rule
        rule = loader.load_rule_from_file(Path(file_path))

        # Check if already exists
        dest_file = loader.custom_rules_dir / f"{rule.rule_id}.yaml"
        if dest_file.exists() and not force:
            display_error(
                f"Rule {rule.rule_id} already exists",
                f"Use --force to overwrite: {dest_file}"
            )
            return

        # Save to custom rules directory
        saved_path = loader.save_rule_to_file(rule)
        display_success(f"Rule installed: {saved_path}")

        console.print(f"\nRule: [bold]{rule.name}[/bold]")
        console.print(f"ID: {rule.versioned_id}")
        console.print(f"Severity: [bold]{rule.severity.value.upper()}[/bold]")

    except Exception as e:
        display_error("Installation failed", str(e))


@custom_rules.command("uninstall")
@click.argument("rule_id")
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation",
)
def uninstall_rule(rule_id: str, yes: bool) -> None:
    """Uninstall a custom rule.

    Removes the rule from the custom rules directory.

    Examples:
      raxe rules custom uninstall custom-001
      raxe rules custom uninstall custom-001 --yes
    """
    loader = CustomRuleLoader()

    rule_file = loader.custom_rules_dir / f"{rule_id}.yaml"

    if not rule_file.exists():
        display_error(f"Rule not found: {rule_id}", "")
        return

    if not yes:
        if not click.confirm(f"Uninstall rule {rule_id}?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

    if loader.delete_rule(rule_id):
        display_success(f"Rule uninstalled: {rule_id}")
    else:
        display_error("Uninstall failed", "")


@custom_rules.command("list")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed information",
)
def list_custom_rules(verbose: bool) -> None:
    """List all installed custom rules.

    Shows custom rules from ~/.raxe/custom_rules/

    Examples:
      raxe rules custom list
      raxe rules custom list --verbose
    """
    loader = CustomRuleLoader()

    rules_info = loader.list_custom_rules()

    if not rules_info:
        console.print("[yellow]No custom rules installed[/yellow]")
        console.print(f"\nCustom rules directory: {loader.custom_rules_dir}")
        console.print("Create a rule with: [cyan]raxe rules custom create[/cyan]")
        return

    console.print(f"[bold]Custom Rules[/bold] ({len(rules_info)} installed)\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Version")

    if verbose:
        table.add_column("File Path", style="dim")

    for rule_info in rules_info:
        row = [
            rule_info["id"],
            rule_info["name"],
            rule_info["version"],
        ]

        if verbose:
            row.append(rule_info["file_path"])

        table.add_row(*row)

    console.print(table)
    console.print(f"\nDirectory: {loader.custom_rules_dir}")


@custom_rules.command("package")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="custom_rules.tar.gz",
    help="Output archive file",
)
def package_rules(output: str) -> None:
    """Package custom rules for sharing.

    Creates a tar.gz archive of all custom rules.

    Examples:
      raxe rules custom package
      raxe rules custom package --output my_rules.tar.gz
    """
    import tarfile

    loader = CustomRuleLoader()
    rules_info = loader.list_custom_rules()

    if not rules_info:
        display_error("No custom rules to package", "")
        return

    try:
        with tarfile.open(output, "w:gz") as tar:
            for rule_info in rules_info:
                file_path = Path(rule_info["file_path"])
                tar.add(file_path, arcname=file_path.name)

        display_success(f"Packaged {len(rules_info)} rules: {output}")

    except Exception as e:
        display_error("Packaging failed", str(e))


def _get_rule_template() -> str:
    """Get a YAML template for a custom rule."""
    return """# Custom Rule Template
id: custom-001
name: "My Custom Rule"
description: "Detect my specific threat pattern"
version: 1.0.0
author: "your-name"

detection:
  layer: L1  # L1 (regex) or L2 (ML)
  pattern: "your regex pattern here"  # Required for L1
  severity: medium  # critical, high, medium, low, info
  confidence: 0.9  # 0.0 to 1.0
  category: CUSTOM  # PI, JB, PII, SEC, QUAL, CUSTOM

examples:
  positive:
    - "This text should match the rule"
    - "Another example that triggers detection"
  negative:
    - "This text should NOT match"
    - "Safe text example"

metadata:
  tags:
    - custom
    - security
  references:
    - "https://example.com/threat-info"

mitre_attack:
  - T1059  # MITRE ATT&CK technique IDs
"""
