"""Performance profiling CLI commands.

Commands for profiling scan performance and identifying bottlenecks.
"""
import click
from rich.table import Table
from rich.tree import Tree

from raxe.cli.output import console, display_error
from raxe.sdk.client import Raxe
from raxe.utils.profiler import ScanProfiler


@click.command(name="profile")
@click.argument("text")
@click.option(
    "--l2/--no-l2",
    default=True,
    help="Include L2 profiling (default: True)",
)
@click.option(
    "--format",
    type=click.Choice(["tree", "table", "json"]),
    default="tree",
    help="Output format (default: tree)",
)
def profile_command(text: str, l2: bool, output_format: str) -> None:
    """Profile scan performance.

    Provides detailed performance breakdown including:
    - Total time
    - L1 time (per rule)
    - L2 time (if enabled)
    - Cache hit/miss
    - Bottleneck identification
    - Optimization recommendations

    Examples:
      raxe profile "test prompt"
      raxe profile "Ignore previous instructions" --no-l2
      raxe profile "test" --format table
    """
    from raxe.cli.branding import print_logo

    # Show compact logo for text output
    if format in ("tree", "table"):
        print_logo(console, compact=True)
        console.print()

    try:
        raxe = Raxe()
    except Exception as e:
        display_error("Failed to initialize RAXE", str(e))
        raise click.Abort() from e

    try:
        # Get components using public API
        components = raxe.get_profiling_components()
        executor = components['executor']
        l2_detector = components['l2_detector'] if l2 else None
        rules = components['rules']

        # Create profiler
        profiler = ScanProfiler(
            rule_executor=executor,
            l2_detector=l2_detector,
        )

        # Profile scan
        with console.status("[cyan]Profiling scan..."):
            profile = profiler.profile_scan(text, rules, include_l2=l2)

        # Display results
        if output_format == "json":
            _display_json(profile)
        elif output_format == "table":
            _display_table(profile)
        else:  # tree
            _display_tree(profile)

    except Exception as e:
        display_error("Profiling failed", str(e))
        raise click.Abort() from e


def _display_tree(profile) -> None:
    """Display profile as a tree."""
    console.print("\n[bold cyan]Scan Profile[/bold cyan]\n")

    # Build tree
    tree = Tree(f"[bold]Total Time:[/bold] {profile.total_time_ms:.2f}ms")

    # L1 branch
    l1_node = tree.add(
        f"[cyan]L1 Detection[/cyan] ({profile.l1_profile.total_time_ms:.2f}ms, "
        f"{profile.l1_percentage:.1f}%)"
    )

    # Show top slow rules
    for rule_profile in profile.l1_profile.slowest_rules[:5]:
        status = "[green]✓[/green]" if rule_profile.matched else "[dim]✗[/dim]"
        cache = "[green]HIT[/green]" if rule_profile.cache_hit else "[red]MISS[/red]"
        l1_node.add(
            f"{status} Rule {rule_profile.rule_id}: {rule_profile.execution_time_ms:.3f}ms "
            f"(cache: {cache})"
        )

    # Cache stats
    l1_node.add(
        f"[dim]Cache:[/dim] {profile.l1_profile.cache_hits} hits, "
        f"{profile.l1_profile.cache_misses} misses "
        f"({profile.l1_profile.cache_hit_rate * 100:.1f}% hit rate)"
    )

    # L2 branch (if present)
    if profile.l2_profile:
        l2_node = tree.add(
            f"[magenta]L2 Detection[/magenta] ({profile.l2_profile.total_time_ms:.2f}ms, "
            f"{profile.l2_percentage:.1f}%)"
        )
        l2_node.add("[dim]Model inference: Full scan[/dim]")

    # Overhead
    tree.add(
        f"[yellow]Pipeline Overhead[/yellow] ({profile.overhead_ms:.2f}ms, "
        f"{profile.overhead_percentage:.1f}%)"
    )

    console.print(tree)

    # Bottlenecks
    bottlenecks = profile.identify_bottlenecks()
    if bottlenecks:
        console.print("\n[bold red]Bottlenecks[/bold red]")
        for bottleneck in bottlenecks:
            console.print(f"  [red]⚠[/red]  {bottleneck}")

    # Recommendations
    recommendations = profile.get_recommendations()
    if recommendations:
        console.print("\n[bold green]Recommendations[/bold green]")
        for rec in recommendations:
            console.print(f"  [green]💡[/green] {rec}")

    console.print()


def _display_table(profile) -> None:
    """Display profile as a table."""
    console.print("\n[bold cyan]Scan Performance Profile[/bold cyan]\n")

    # Summary table
    summary = Table(show_header=True, header_style="bold cyan")
    summary.add_column("Metric")
    summary.add_column("Value", justify="right")
    summary.add_column("Percentage", justify="right")

    summary.add_row(
        "Total Time",
        f"{profile.total_time_ms:.2f}ms",
        "100.0%",
    )
    summary.add_row(
        "L1 Detection",
        f"{profile.l1_profile.total_time_ms:.2f}ms",
        f"{profile.l1_percentage:.1f}%",
    )

    if profile.l2_profile:
        summary.add_row(
            "L2 Detection",
            f"{profile.l2_profile.total_time_ms:.2f}ms",
            f"{profile.l2_percentage:.1f}%",
        )

    summary.add_row(
        "Overhead",
        f"{profile.overhead_ms:.2f}ms",
        f"{profile.overhead_percentage:.1f}%",
    )

    console.print(summary)

    # L1 rules table
    if profile.l1_profile.rule_profiles:
        console.print("\n[bold]L1 Rules (Top 10 Slowest)[/bold]\n")

        rules_table = Table(show_header=True, header_style="bold cyan")
        rules_table.add_column("Rule ID")
        rules_table.add_column("Time (ms)", justify="right")
        rules_table.add_column("Matched")
        rules_table.add_column("Cache")

        for rule_profile in profile.l1_profile.slowest_rules[:10]:
            rules_table.add_row(
                rule_profile.rule_id,
                f"{rule_profile.execution_time_ms:.3f}",
                "[green]Yes[/green]" if rule_profile.matched else "[dim]No[/dim]",
                "[green]HIT[/green]" if rule_profile.cache_hit else "[red]MISS[/red]",
            )

        console.print(rules_table)

    # Bottlenecks and recommendations
    bottlenecks = profile.identify_bottlenecks()
    recommendations = profile.get_recommendations()

    if bottlenecks or recommendations:
        console.print()

    if bottlenecks:
        console.print("[bold red]Bottlenecks:[/bold red]")
        for b in bottlenecks:
            console.print(f"  [red]⚠[/red]  {b}")

    if recommendations:
        console.print("\n[bold green]Recommendations:[/bold green]")
        for r in recommendations:
            console.print(f"  [green]💡[/green] {r}")

    console.print()


def _display_json(profile) -> None:
    """Display profile as JSON."""
    import json

    data = {
        "total_time_ms": profile.total_time_ms,
        "text_length": profile.text_length,
        "timestamp": profile.timestamp,
        "layers": {
            "l1": {
                "total_time_ms": profile.l1_profile.total_time_ms,
                "percentage": profile.l1_percentage,
                "cache_hits": profile.l1_profile.cache_hits,
                "cache_misses": profile.l1_profile.cache_misses,
                "cache_hit_rate": profile.l1_profile.cache_hit_rate,
                "slowest_rules": [
                    {
                        "rule_id": r.rule_id,
                        "time_ms": r.execution_time_ms,
                        "matched": r.matched,
                        "cache_hit": r.cache_hit,
                    }
                    for r in profile.l1_profile.slowest_rules
                ],
            },
        },
        "overhead_ms": profile.overhead_ms,
        "overhead_percentage": profile.overhead_percentage,
        "bottlenecks": profile.identify_bottlenecks(),
        "recommendations": profile.get_recommendations(),
    }

    if profile.l2_profile:
        data["layers"]["l2"] = {
            "total_time_ms": profile.l2_profile.total_time_ms,
            "percentage": profile.l2_percentage,
        }

    console.print_json(json.dumps(data, indent=2))
