"""
Performance profiling CLI commands.

This module provides CLI commands for profiling RAXE performance:
- raxe profile: Profile scan performance
- raxe benchmark: Run performance benchmarks
- raxe metrics-server: Start Prometheus metrics server
"""

import time

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from raxe.monitoring.profiler import MemoryProfiler, PerformanceProfiler
from raxe.monitoring.server import MetricsServer, get_metrics_text

console = Console()


@click.command()
@click.argument("prompt")
@click.option(
    "--iterations",
    "-n",
    default=100,
    help="Number of iterations to run",
    show_default=True,
)
@click.option(
    "--output",
    "-o",
    help="Save profile to file (for snakeviz visualization)",
)
@click.option(
    "--memory",
    is_flag=True,
    help="Include memory profiling (requires memory_profiler)",
)
def profile(prompt: str, iterations: int, output: str, memory: bool):
    """
    Profile scan performance.

    This command profiles the scan operation to identify performance
    bottlenecks. It runs multiple iterations and provides detailed
    statistics on function execution times.

    Example:
        raxe profile "test prompt" --iterations 100
        raxe profile "test" -n 1000 -o scan.prof

    The output file can be visualized with snakeviz:
        pip install snakeviz
        snakeviz scan.prof
    """
    profiler = PerformanceProfiler()

    with console.status(f"[bold green]Profiling {iterations} scans..."):
        if output:
            # Save to file for visualization
            profiler.profile_to_file(prompt, output, iterations)
            console.print(f"\n[green]✓[/green] Profile saved to [cyan]{output}[/cyan]")
        else:
            # Run profile and display results
            result = profiler.profile_scan(prompt, iterations)

            # Display results
            console.print("\n" + "=" * 60)
            console.print("[bold cyan]Performance Profile Results[/bold cyan]")
            console.print("=" * 60)

            # Create metrics table
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Total Time", f"{result.total_time:.4f}s")
            table.add_row("Iterations", str(result.iterations))
            table.add_row("Avg per Scan", f"{result.avg_time * 1000:.2f}ms")
            table.add_row(
                "Scans per Second", f"{1 / result.avg_time:.1f} scans/sec"
            )

            console.print(table)

            # Show top functions
            console.print("\n[bold]Top Functions by Cumulative Time:[/bold]")
            console.print(result.stats_report)

    # Memory profiling if requested
    if memory:
        mem_profiler = MemoryProfiler()
        if not mem_profiler.available:
            console.print(
                "\n[yellow]⚠[/yellow]  Memory profiling requires memory_profiler:"
            )
            console.print("   pip install memory_profiler")
        else:
            from raxe.application.scan_pipeline import scan_prompt

            with console.status("[bold green]Profiling memory usage..."):
                mem_report = mem_profiler.profile_memory(scan_prompt, prompt)

            if mem_report:
                console.print("\n" + mem_report)


@click.command()
@click.option(
    "--prompts",
    "-p",
    multiple=True,
    help="Prompts to benchmark (can specify multiple)",
)
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    help="File with prompts (one per line)",
)
@click.option(
    "--iterations",
    "-n",
    default=100,
    help="Number of iterations",
    show_default=True,
)
@click.option(
    "--warmup",
    default=10,
    help="Number of warmup iterations",
    show_default=True,
)
def benchmark(prompts: tuple[str], file: str, iterations: int, warmup: int):
    """
    Run performance benchmarks.

    Benchmark scan throughput with multiple prompts to measure
    real-world performance characteristics.

    Example:
        raxe benchmark -p "test 1" -p "test 2" -n 100
        raxe benchmark -f prompts.txt -n 1000
    """
    # Load prompts
    prompt_list = list(prompts) if prompts else []

    if file:
        with open(file) as f:
            prompt_list.extend(line.strip() for line in f if line.strip())

    if not prompt_list:
        console.print("[red]Error:[/red] No prompts specified")
        console.print("Use --prompts or --file to specify prompts to benchmark")
        raise click.Abort()

    console.print(f"\n[bold]Benchmarking with {len(prompt_list)} prompts...[/bold]")

    profiler = PerformanceProfiler()

    with console.status("[bold green]Running benchmark..."):
        results = profiler.benchmark_throughput(
            prompt_list, warmup=warmup, iterations=iterations
        )

    # Display results
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]Benchmark Results[/bold cyan]")
    console.print("=" * 60 + "\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Scans", f"{results['total_scans']:,}")
    table.add_row("Total Time", f"{results['total_time']:.2f}s")
    table.add_row("Prompts Tested", str(results["prompts_tested"]))
    table.add_row("Iterations", str(results["iterations"]))
    table.add_row(
        "Throughput", f"{results['scans_per_second']:.1f} scans/sec"
    )
    table.add_row("Avg Latency", f"{results['avg_time_ms']:.2f}ms")

    console.print(table)

    # Performance assessment
    if results["avg_time_ms"] < 10:
        status = "[green]Excellent[/green]"
        emoji = "✓"
    elif results["avg_time_ms"] < 50:
        status = "[yellow]Good[/yellow]"
        emoji = "✓"
    else:
        status = "[red]Needs Optimization[/red]"
        emoji = "⚠"

    console.print(f"\n{emoji} Performance: {status}")

    if results["avg_time_ms"] > 50:
        console.print(
            "\n[yellow]Tip:[/yellow] Consider optimizing rules or reducing detection layers"
        )


@click.command()
@click.option(
    "--port",
    "-p",
    default=9090,
    help="Port for metrics server",
    show_default=True,
)
@click.option(
    "--host",
    "-h",
    default="",
    help="Host to bind to (empty = all interfaces)",
    show_default=True,
)
def metrics_server(port: int, host: str):
    """
    Start Prometheus metrics server.

    Exposes RAXE metrics at /metrics endpoint for Prometheus scraping.
    This is useful for monitoring RAXE performance in production.

    Example:
        raxe metrics-server --port 9090

    Metrics will be available at:
        http://localhost:9090/metrics

    Press Ctrl+C to stop the server.
    """
    console.print("[bold]Starting Prometheus Metrics Server[/bold]\n")

    server = MetricsServer(port=port, host=host)

    try:
        server.start()

        console.print(f"[green]✓[/green] Server started on port {port}")
        console.print(f"\nMetrics available at: [cyan]{server.url}[/cyan]")
        console.print("\nExample Prometheus scrape config:")

        config = f"""
  - job_name: 'raxe'
    static_configs:
      - targets: ['localhost:{port}']
"""
        console.print(Panel(config, title="prometheus.yml", border_style="blue"))

        console.print("\n[yellow]Press Ctrl+C to stop[/yellow]\n")

        # Keep running
        while server.is_running:
            time.sleep(1)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Stopping server...[/yellow]")
        server.stop()
        console.print("[green]✓[/green] Server stopped")


@click.command()
@click.option(
    "--format",
    "-f",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def metrics_dump(format: str):
    """
    Dump current metrics to stdout.

    This command outputs the current state of all RAXE metrics
    without starting a server. Useful for debugging or one-time checks.

    Example:
        raxe metrics-dump
        raxe metrics-dump --format json
    """
    if format == "text":
        metrics_text = get_metrics_text()
        console.print(metrics_text)
    else:
        # JSON format would require parsing prometheus metrics
        # For now, just output text
        console.print("[yellow]JSON format not yet implemented[/yellow]")
        console.print("Outputting Prometheus text format:\n")
        metrics_text = get_metrics_text()
        console.print(metrics_text)
