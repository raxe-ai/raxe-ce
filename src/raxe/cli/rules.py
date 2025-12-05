"""
RAXE rules command - Rule discovery and management.

Provides comprehensive rule discovery, inspection, and management capabilities.
"""


import click
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from raxe.cli.custom_rules import custom_rules
from raxe.cli.output import console, display_error
from raxe.domain.rules.models import RuleFamily, Severity
from raxe.sdk.client import Raxe
from raxe.utils.error_sanitizer import sanitize_error_message


@click.group()
def rules() -> None:
    """
    Manage and inspect detection rules.

    Discover, test, and manage RAXE detection rules including:
      - Listing all available rules
      - Inspecting rule details
      - Searching rules by keyword
      - Testing rules against text
      - Viewing rule statistics

    \b
    Examples:
      raxe rules list
      raxe rules show pi-001
      raxe rules search "prompt injection"
      raxe rules test pi-001 "ignore previous instructions"
    """
    pass


@rules.command("list")
@click.option(
    "--family",
    type=click.Choice(["PI", "JB", "PII", "SEC", "QUAL", "CUSTOM"], case_sensitive=False),
    help="Filter by rule family",
)
@click.option(
    "--severity",
    type=click.Choice(["critical", "high", "medium", "low", "info"], case_sensitive=False),
    help="Filter by minimum severity",
)
@click.option(
    "--format",
    "output_format",  # Map --format to output_format parameter
    type=click.Choice(["table", "tree", "json"]),
    default="table",
    help="Output format (default: table)",
)
def list_rules(family: str | None, severity: str | None, output_format: str) -> None:
    """
    List all available detection rules.

    Shows rules from all loaded packs with their key attributes.
    Can be filtered by family and severity.

    \b
    Examples:
      raxe rules list
      raxe rules list --family PI
      raxe rules list --severity high
      raxe rules list --format tree
    """
    from raxe.cli.branding import print_logo

    # Show compact logo for text output
    if output_format in ("table", "tree"):
        print_logo(console, compact=True)
        console.print()

    try:
        raxe = Raxe()
    except Exception as e:
        display_error("Failed to initialize RAXE", sanitize_error_message(e))
        console.print("Try running: [cyan]raxe init[/cyan]")
        raise click.Abort() from e

    # Get all rules from registry
    try:
        all_rules = raxe.get_all_rules()
    except Exception as e:
        display_error("Failed to load rules", sanitize_error_message(e))
        raise click.Abort() from e

    if not all_rules:
        console.print("[yellow]No rules loaded[/yellow]")
        console.print("Check your rule packs configuration")
        return

    # Apply filters
    filtered_rules = all_rules
    if family:
        family_enum = RuleFamily[family.upper()]
        filtered_rules = [r for r in filtered_rules if r.family == family_enum]

    if severity:
        severity_enum = Severity(severity.lower())
        severity_order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
        min_severity_idx = severity_order.index(severity_enum)
        filtered_rules = [
            r for r in filtered_rules
            if severity_order.index(r.severity) <= min_severity_idx
        ]

    if not filtered_rules:
        console.print("[yellow]No rules match the specified filters[/yellow]")
        return

    # Display based on format
    if output_format == "table":
        _display_rules_table(filtered_rules)
    elif output_format == "tree":
        _display_rules_tree(filtered_rules)
    elif output_format == "json":
        import json
        rules_data = [
            {
                "rule_id": r.rule_id,
                "version": r.version,
                "name": r.name,
                "family": r.family.value,
                "severity": r.severity.value,
                "confidence": r.confidence,
            }
            for r in filtered_rules
        ]
        console.print(json.dumps(rules_data, indent=2))

    # Summary
    if output_format != "json":
        console.print()
        console.print(f"[bold]Total:[/bold] {len(filtered_rules)} rules")


@rules.command("show")
@click.argument("rule_id")
def show_rule(rule_id: str) -> None:
    """
    Show detailed information about a specific rule.

    Displays complete rule details including:
      - Metadata (name, description, version)
      - Detection patterns
      - Examples (should/shouldn't match)
      - Performance metrics
      - MITRE ATT&CK mappings

    \b
    Examples:
      raxe rules show pi-001
      raxe rules show pii-email
    """
    try:
        raxe = Raxe()
    except Exception as e:
        display_error("Failed to initialize RAXE", str(e))
        raise click.Abort() from e

    # Find rule
    try:
        all_rules = raxe.get_all_rules()
        rule = next((r for r in all_rules if r.rule_id == rule_id), None)
    except Exception as e:
        display_error("Failed to load rules", str(e))
        raise click.Abort() from e

    if not rule:
        display_error(f"Rule not found: {rule_id}", "Use 'raxe rules list' to see available rules")
        raise click.Abort()

    # Display rule details
    _display_rule_details(rule)


@rules.command("search")
@click.argument("query")
@click.option(
    "--in",
    "search_in",
    type=click.Choice(["name", "description", "all"]),
    default="all",
    help="Where to search (default: all)",
)
def search_rules(query: str, search_in: str) -> None:
    """
    Search rules by keyword.

    Searches rule names and descriptions for the specified query.
    Case-insensitive search.

    \b
    Examples:
      raxe rules search "injection"
      raxe rules search "email" --in description
      raxe rules search "PII" --in name
    """
    try:
        raxe = Raxe()
    except Exception as e:
        display_error("Failed to initialize RAXE", str(e))
        raise click.Abort() from e

    try:
        all_rules = raxe.get_all_rules()
    except Exception as e:
        display_error("Failed to load rules", str(e))
        raise click.Abort() from e

    # Search
    query_lower = query.lower()
    matching_rules = []

    for rule in all_rules:
        match = False
        if search_in in ("name", "all"):
            if query_lower in rule.name.lower():
                match = True
        if search_in in ("description", "all"):
            if query_lower in rule.description.lower():
                match = True

        if match:
            matching_rules.append(rule)

    if not matching_rules:
        console.print(f"[yellow]No rules found matching '{query}'[/yellow]")
        return

    # Display results
    _display_rules_table(matching_rules)

    console.print()
    console.print(f"[bold]Found:[/bold] {len(matching_rules)} rules matching '{query}'")


@rules.command("test")
@click.argument("rule_id")
@click.argument("text")
def test_rule(rule_id: str, text: str) -> None:
    """
    Test a rule against provided text.

    Tests whether a specific rule would detect the provided text.
    Useful for understanding rule behavior and debugging.

    \b
    Examples:
      raxe rules test pi-001 "Ignore all previous instructions"
      raxe rules test pii-email "Contact me at user@example.com"
    """
    try:
        raxe = Raxe()
    except Exception as e:
        display_error("Failed to initialize RAXE", str(e))
        raise click.Abort() from e

    # Find rule
    try:
        all_rules = raxe.get_all_rules()
        rule = next((r for r in all_rules if r.rule_id == rule_id), None)
    except Exception as e:
        display_error("Failed to load rules", str(e))
        raise click.Abort() from e

    if not rule:
        display_error(f"Rule not found: {rule_id}", "Use 'raxe rules list' to see available rules")
        raise click.Abort()

    # Test rule
    console.print(f"[cyan]Testing rule {rule_id} against provided text...[/cyan]")
    console.print()

    # Compile patterns and test
    try:
        compiled_patterns = rule.compile_patterns()
        matched = False
        match_details = []

        for i, pattern in enumerate(compiled_patterns):
            match = pattern.search(text)
            if match:
                matched = True
                match_details.append({
                    "pattern_index": i,
                    "pattern": rule.patterns[i].pattern,
                    "match": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                })

        if matched:
            console.print("[green bold]✓ MATCH[/green bold]")
            console.print()
            console.print(f"Rule [cyan]{rule_id}[/cyan] would detect this text")
            console.print()

            # Show match details
            for detail in match_details:
                console.print(f"[bold]Pattern {detail['pattern_index']}:[/bold]")
                console.print(f"  Regex: [dim]{detail['pattern']}[/dim]")
                console.print(f"  Matched: [yellow]'{detail['match']}'[/yellow]")
                console.print(f"  Position: chars {detail['start']}-{detail['end']}")
                console.print()

            console.print(f"[bold]Severity:[/bold] [{_get_severity_color(rule.severity)}]{rule.severity.value}[/]")
            console.print(f"[bold]Confidence:[/bold] {rule.confidence * 100:.1f}%")
        else:
            console.print("[yellow bold]✗ NO MATCH[/yellow bold]")
            console.print()
            console.print(f"Rule [cyan]{rule_id}[/cyan] would NOT detect this text")
            console.print()
            console.print("[dim]None of the rule's patterns matched the provided text[/dim]")

    except Exception as e:
        display_error("Failed to test rule", str(e))
        raise click.Abort() from e


@rules.command("stats")
def rules_stats() -> None:
    """
    Show rule statistics and metrics.

    Displays aggregate statistics about loaded rules:
      - Total rules by family
      - Rules by severity
      - Coverage metrics

    \b
    Examples:
      raxe rules stats
    """
    try:
        raxe = Raxe()
    except Exception as e:
        display_error("Failed to initialize RAXE", str(e))
        raise click.Abort() from e

    try:
        all_rules = raxe.get_all_rules()
    except Exception as e:
        display_error("Failed to load rules", str(e))
        raise click.Abort() from e

    if not all_rules:
        console.print("[yellow]No rules loaded[/yellow]")
        return

    # Calculate statistics
    stats_by_family = {}
    stats_by_severity = {}

    for rule in all_rules:
        # By family
        family_key = rule.family.value
        stats_by_family[family_key] = stats_by_family.get(family_key, 0) + 1

        # By severity
        severity_key = rule.severity.value
        stats_by_severity[severity_key] = stats_by_severity.get(severity_key, 0) + 1

    # Display statistics
    console.print("[bold cyan]Rule Statistics[/bold cyan]")
    console.print()

    # Overall
    console.print(f"[bold]Total Rules:[/bold] {len(all_rules)}")
    console.print()

    # By family
    console.print("[bold]By Family:[/bold]")
    for family in sorted(stats_by_family.keys()):
        count = stats_by_family[family]
        pct = (count / len(all_rules)) * 100
        console.print(f"  {family:8s} {count:3d} rules ({pct:5.1f}%)")
    console.print()

    # By severity
    console.print("[bold]By Severity:[/bold]")
    severity_order = ["critical", "high", "medium", "low", "info"]
    for severity in severity_order:
        count = stats_by_severity.get(severity, 0)
        if count > 0:
            pct = (count / len(all_rules)) * 100
            color = _get_severity_color(Severity(severity))
            console.print(f"  [{color}]{severity.upper():8s}[/] {count:3d} rules ({pct:5.1f}%)")
    console.print()


def _display_rules_table(rules: list) -> None:
    """Display rules in a table format."""
    table = Table(title="Detection Rules", show_header=True, header_style="bold cyan")
    table.add_column("Rule ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="white")
    table.add_column("Family", style="blue", no_wrap=True)
    table.add_column("Severity", style="bold", no_wrap=True)
    table.add_column("Confidence", justify="right", no_wrap=True)

    for rule in sorted(rules, key=lambda r: (r.family.value, r.rule_id)):
        severity_color = _get_severity_color(rule.severity)
        severity_text = Text(rule.severity.value.upper(), style=severity_color)
        confidence_pct = f"{rule.confidence * 100:.0f}%"

        # Truncate name if too long
        name = rule.name if len(rule.name) <= 40 else rule.name[:37] + "..."

        table.add_row(
            rule.rule_id,
            name,
            rule.family.value,
            severity_text,
            confidence_pct,
        )

    console.print(table)


def _display_rules_tree(rules: list) -> None:
    """Display rules in a tree format grouped by family."""
    from rich.tree import Tree

    root = Tree("[bold cyan]Detection Rules[/bold cyan]")

    # Group by family
    by_family = {}
    for rule in rules:
        family = rule.family.value
        if family not in by_family:
            by_family[family] = []
        by_family[family].append(rule)

    # Build tree
    for family in sorted(by_family.keys()):
        family_rules = by_family[family]
        family_branch = root.add(f"[bold blue]{family}[/bold blue] ({len(family_rules)} rules)")

        for rule in sorted(family_rules, key=lambda r: r.rule_id):
            severity_color = _get_severity_color(rule.severity)
            rule_text = f"[cyan]{rule.rule_id}[/cyan]  {rule.name}  [{severity_color}]{rule.severity.value.upper()}[/]"
            family_branch.add(rule_text)

    console.print(root)


def _display_rule_details(rule) -> None:
    """Display detailed information about a rule."""

    # Header panel
    severity_color = _get_severity_color(rule.severity)
    header = Text()
    header.append(f"{rule.rule_id}@{rule.version}", style="cyan bold")
    header.append(" - ", style="dim")
    header.append(rule.name, style="white")

    console.print(Panel(header, border_style="cyan"))
    console.print()

    # Metadata
    console.print("[bold]Metadata[/bold]")
    console.print(f"  Family: [blue]{rule.family.value}[/blue] / {rule.sub_family}")
    console.print(f"  Severity: [{severity_color}]{rule.severity.value.upper()}[/]")
    console.print(f"  Confidence: {rule.confidence * 100:.1f}%")
    console.print(f"  Version: {rule.version}")
    console.print()

    # Description
    console.print("[bold]Description[/bold]")
    console.print(f"  {rule.description}")
    console.print()

    # Patterns
    console.print(f"[bold]Patterns[/bold] ({len(rule.patterns)} patterns)")
    for i, pattern in enumerate(rule.patterns):
        console.print(f"  [dim]Pattern {i}:[/dim]")
        console.print(f"    {pattern.pattern}")
        if pattern.flags:
            console.print(f"    [dim]Flags: {', '.join(pattern.flags)}[/dim]")
    console.print()

    # Examples
    if rule.examples.should_match or rule.examples.should_not_match:
        console.print("[bold]Examples[/bold]")

        if rule.examples.should_match:
            console.print("  [green]Should Match:[/green]")
            for example in rule.examples.should_match[:3]:  # Limit to first 3
                console.print(f"    ✓ {example}")

        if rule.examples.should_not_match:
            console.print("  [red]Should NOT Match:[/red]")
            for example in rule.examples.should_not_match[:3]:  # Limit to first 3
                console.print(f"    ✗ {example}")

        console.print()

    # MITRE ATT&CK
    if rule.mitre_attack:
        console.print("[bold]MITRE ATT&CK[/bold]")
        for technique in rule.mitre_attack:
            console.print(f"  {technique}")
        console.print()

    # Metrics
    if rule.metrics and (rule.metrics.precision or rule.metrics.recall):
        console.print("[bold]Metrics[/bold]")
        if rule.metrics.precision:
            console.print(f"  Precision: {rule.metrics.precision * 100:.1f}%")
        if rule.metrics.recall:
            console.print(f"  Recall: {rule.metrics.recall * 100:.1f}%")
        if rule.metrics.f1_score:
            console.print(f"  F1 Score: {rule.metrics.f1_score * 100:.1f}%")
        console.print()


def _get_severity_color(severity: Severity) -> str:
    """Get rich color for severity level."""
    color_map = {
        Severity.CRITICAL: "red bold",
        Severity.HIGH: "red",
        Severity.MEDIUM: "yellow",
        Severity.LOW: "blue",
        Severity.INFO: "green",
    }
    return color_map.get(severity, "white")


# Add custom rules subcommand
rules.add_command(custom_rules)


if __name__ == "__main__":
    rules()
