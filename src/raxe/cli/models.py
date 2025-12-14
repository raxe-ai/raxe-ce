"""CLI commands for L2 model management.

Provides commands to list, inspect, test, and compare L2 models.
"""
import click
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from raxe.cli.output import console


@click.group()
def models():
    """Manage L2 models (list, test, compare)."""
    pass


@models.command("list")
@click.option(
    "--status",
    type=click.Choice(["active", "experimental", "deprecated", "all"]),
    default="all",
    help="Filter by model status",
)
@click.option(
    "--runtime",
    type=click.Choice(["pytorch", "onnx", "onnx_int8", "all"]),
    default="all",
    help="Filter by runtime type",
)
def list_models(status: str, runtime: str):
    """List all available L2 models.

    Shows model name, variant, performance metrics, and status.

    \b
    Examples:
      raxe models list
      raxe models list --status active
      raxe models list --runtime onnx_int8
    """
    from raxe.domain.ml.model_metadata import ModelStatus
    from raxe.domain.ml.model_registry import get_registry

    # Get registry
    registry = get_registry()

    # Filter models
    status_filter = None if status == "all" else ModelStatus(status)
    runtime_filter = None if runtime == "all" else runtime

    models_list = registry.list_models(status=status_filter, runtime=runtime_filter)

    if not models_list:
        console.print("[yellow]No models found matching criteria[/yellow]")
        console.print()
        console.print(f"Models directory: {registry.models_dir}")
        console.print("Add .raxe model files to this directory to get started.")
        return

    # Create table
    table = Table(title=f"Available L2 Models ({len(models_list)})")
    table.add_column("Model ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="white")
    table.add_column("Variant", style="magenta")
    table.add_column("P95 Latency", justify="right", style="yellow")
    table.add_column("Accuracy", justify="right", style="green")
    table.add_column("Status", justify="center")

    # Add rows
    for model in models_list:
        # Format latency
        if model.performance.p95_latency_ms:
            latency_str = f"{model.performance.p95_latency_ms:.1f}ms"
            # Add emoji for fast models
            if model.performance.p95_latency_ms < 10:
                latency_str += " ⚡⚡"
            elif model.performance.p95_latency_ms < 20:
                latency_str += " ⚡"
        else:
            latency_str = "unknown"

        # Format accuracy
        if model.accuracy and model.accuracy.binary_f1:
            accuracy_str = f"{model.accuracy.binary_f1*100:.1f}%"
            # Add emoji for high accuracy
            if model.accuracy.binary_f1 > 0.92:
                accuracy_str += " 🎯"
        else:
            accuracy_str = "unknown"

        # Format status
        status_emoji = {
            "active": "✅",
            "experimental": "🧪",
            "deprecated": "⚠️",
        }
        status_str = f"{model.status.value} {status_emoji.get(model.status.value, '')}"

        table.add_row(
            model.model_id,
            model.name,
            model.variant,
            latency_str,
            accuracy_str,
            status_str,
        )

    console.print()
    console.print(table)
    console.print()

    # Show legend
    console.print("[dim]Legend: ⚡ = Fast (<20ms)  ⚡⚡ = Ultra-fast (<10ms)  🎯 = High accuracy (>92%)[/dim]")
    console.print()

    # Show summary
    active_count = len([m for m in models_list if m.is_active])
    experimental_count = len([m for m in models_list if m.is_experimental])

    console.print(f"[dim]Total: {len(models_list)} models  |  Active: {active_count}  |  Experimental: {experimental_count}[/dim]")
    console.print()


@models.command("info")
@click.argument("model_id")
def model_info(model_id: str):
    """Show detailed information about a specific model.

    \b
    Examples:
      raxe models info v1.0_onnx_int8
      raxe models info v1.1_distilled
    """
    from raxe.domain.ml.model_registry import get_registry

    # Get registry
    registry = get_registry()

    # Get model
    model = registry.get_model(model_id)

    if not model:
        console.print(f"[red]Model not found: {model_id}[/red]")
        console.print()
        console.print("Available models:")
        for m in registry.list_models():
            console.print(f"  • {m.model_id}")
        return

    # Build info panel
    info = Text()

    # Basic info
    info.append(f"{model.name}\n", style="bold cyan")
    info.append(f"Version: {model.version}  |  Variant: {model.variant}\n", style="dim")
    info.append(f"\n{model.description}\n\n", style="white")

    # Status
    status_color = {
        "active": "green",
        "experimental": "yellow",
        "deprecated": "red",
    }
    info.append("Status: ", style="bold")
    info.append(f"{model.status.value.upper()}", style=status_color.get(model.status.value, "white"))
    info.append("\n\n")

    # Performance
    info.append("Performance Metrics:\n", style="bold yellow")
    if model.performance.p50_latency_ms:
        info.append(f"  P50 Latency: {model.performance.p50_latency_ms:.1f}ms\n")
    if model.performance.p95_latency_ms:
        info.append(f"  P95 Latency: {model.performance.p95_latency_ms:.1f}ms\n")
    if model.performance.p99_latency_ms:
        info.append(f"  P99 Latency: {model.performance.p99_latency_ms:.1f}ms\n")
    if model.performance.throughput_per_sec:
        info.append(f"  Throughput: {model.performance.throughput_per_sec} req/sec\n")
    if model.performance.memory_mb:
        info.append(f"  Memory: {model.performance.memory_mb} MB\n")
    info.append("\n")

    # Accuracy
    if model.accuracy:
        info.append("Accuracy Metrics:\n", style="bold green")
        if model.accuracy.binary_f1:
            info.append(f"  Binary F1: {model.accuracy.binary_f1*100:.1f}%\n")
        if model.accuracy.family_f1:
            info.append(f"  Family F1: {model.accuracy.family_f1*100:.1f}%\n")
        if model.accuracy.subfamily_f1:
            info.append(f"  Subfamily F1: {model.accuracy.subfamily_f1*100:.1f}%\n")
        if model.accuracy.false_positive_rate:
            info.append(f"  False Positive Rate: {model.accuracy.false_positive_rate*100:.2f}%\n")
        if model.accuracy.false_negative_rate:
            info.append(f"  False Negative Rate: {model.accuracy.false_negative_rate*100:.2f}%\n")
        info.append("\n")

    # Requirements
    info.append("Requirements:\n", style="bold blue")
    info.append(f"  Runtime: {model.runtime_type}\n")
    info.append(f"  GPU Required: {'Yes' if model.requirements.requires_gpu else 'No'}\n")
    if model.requirements.min_runtime_version:
        info.append(f"  Min Runtime Version: {model.requirements.min_runtime_version}\n")
    info.append("\n")

    # File info
    info.append("File Information:\n", style="bold")
    info.append(f"  Filename: {model.file_info.filename}\n")
    info.append(f"  Size: {model.file_info.size_mb:.1f} MB\n")
    if model.file_path:
        info.append(f"  Path: {model.file_path}\n")

    # Tags
    if model.tags:
        info.append("\n")
        info.append("Tags: ", style="bold")
        info.append(", ".join(model.tags), style="dim")
        info.append("\n")

    # Recommendations
    if model.recommended_for:
        info.append("\n")
        info.append("Recommended for:\n", style="bold green")
        for rec in model.recommended_for:
            info.append(f"  ✓ {rec}\n", style="green")

    if model.not_recommended_for:
        info.append("\n")
        info.append("Not recommended for:\n", style="bold red")
        for rec in model.not_recommended_for:
            info.append(f"  ✗ {rec}\n", style="red")

    console.print()
    console.print(Panel(info, border_style="cyan", padding=(1, 2)))
    console.print()


@models.command("set-default")
@click.argument("model_id")
def set_default(model_id: str):
    """Set default L2 model for scanning.

    Updates the config file to use the specified model by default.

    \b
    Examples:
      raxe models set-default v1.0_onnx_int8
    """
    from pathlib import Path

    import yaml

    from raxe.domain.ml.model_registry import get_registry

    # Get registry
    registry = get_registry()

    # Verify model exists
    model = registry.get_model(model_id)
    if not model:
        console.print(f"[red]Model not found: {model_id}[/red]")
        return

    # Update config file
    config_file = Path.home() / ".raxe" / "config.yaml"

    if not config_file.exists():
        console.print("[yellow]Config file not found. Run 'raxe init' first.[/yellow]")
        return

    # Load existing config
    with open(config_file) as f:
        config = yaml.safe_load(f) or {}

    # Update L2 model setting
    if "l2_model" not in config:
        config["l2_model"] = {}

    config["l2_model"]["model_id"] = model_id
    config["l2_model"]["selection"] = "explicit"

    # Save config
    with open(config_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    console.print()
    console.print(f"[green]✅ Default L2 model set to: {model_id}[/green]")
    console.print(f"[dim]Updated: {config_file}[/dim]")
    console.print()
    console.print(f"[cyan]Model: {model.name}[/cyan]")
    console.print(f"[dim]P95 Latency: {model.performance.p95_latency_ms:.1f}ms[/dim]")
    console.print()


@models.command("compare")
@click.argument("model_ids", nargs=-1, required=False)
def compare_models(model_ids: tuple[str, ...]):
    """Compare multiple models side-by-side.

    \b
    Examples:
      raxe models compare v1.0_bundle v1.0_onnx_int8
      raxe models compare  # Compares all active models
    """
    from raxe.domain.ml.model_registry import get_registry

    # Get registry
    registry = get_registry()

    # Get models to compare
    if model_ids:
        models_dict = {}
        for model_id in model_ids:
            model = registry.get_model(model_id)
            if model:
                models_dict[model_id] = model
            else:
                console.print(f"[yellow]Warning: Model not found: {model_id}[/yellow]")
    else:
        # Compare all active models
        models_dict = registry.compare_models()

    if not models_dict:
        console.print("[yellow]No models to compare[/yellow]")
        return

    # Create comparison table
    table = Table(title=f"Model Comparison ({len(models_dict)} models)")
    table.add_column("Model ID", style="cyan", no_wrap=True)
    table.add_column("Variant", style="magenta")
    table.add_column("P95 Latency", justify="right", style="yellow")
    table.add_column("Accuracy (F1)", justify="right", style="green")
    table.add_column("Memory (MB)", justify="right", style="blue")
    table.add_column("Status", justify="center")

    # Add rows
    for model_id, model in models_dict.items():
        # Latency
        latency = model.performance.p95_latency_ms or 0
        latency_str = f"{latency:.1f}ms" if latency else "unknown"

        # Accuracy
        accuracy = model.accuracy.binary_f1 if model.accuracy else None
        accuracy_str = f"{accuracy*100:.1f}%" if accuracy else "unknown"

        # Memory
        memory = model.performance.memory_mb or 0
        memory_str = f"{memory}" if memory else "unknown"

        # Status
        status_emoji = {"active": "✅", "experimental": "🧪", "deprecated": "⚠️"}
        status_str = status_emoji.get(model.status.value, "")

        table.add_row(
            model_id,
            model.variant,
            latency_str,
            accuracy_str,
            memory_str,
            status_str,
        )

    console.print()
    console.print(table)
    console.print()

    # Find best models
    best_latency = min(models_dict.values(), key=lambda m: m.performance.p95_latency_ms or 999)
    best_accuracy = max(
        [m for m in models_dict.values() if m.accuracy and m.accuracy.binary_f1],
        key=lambda m: m.accuracy.binary_f1,
        default=None
    )

    console.print("[bold]Recommendations:[/bold]")
    console.print(f"  ⚡ Fastest: [cyan]{best_latency.model_id}[/cyan] ({best_latency.performance.p95_latency_ms:.1f}ms)")
    if best_accuracy:
        console.print(f"  🎯 Most Accurate: [cyan]{best_accuracy.model_id}[/cyan] ({best_accuracy.accuracy.binary_f1*100:.1f}%)")
    console.print()


@models.command("download")
@click.argument("model_name", required=False, default=None)
@click.option(
    "--all",
    "download_all",
    is_flag=True,
    help="Download all available models",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force re-download even if model exists",
)
def download_model_cmd(model_name: str | None, download_all: bool, force: bool):
    """Download ML model for L2 detection.

    The ML model is too large for PyPI (~329MB) so it's downloaded on-demand.
    Downloads to ~/.raxe/models/ and persists across package upgrades.

    \b
    Examples:
      raxe models download         # Download the Gemma Compact model
      raxe models download --force # Re-download existing model
    """
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        TextColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )

    from raxe.infrastructure.ml.model_downloader import (
        DEFAULT_MODEL,
        MODEL_REGISTRY,
        download_model,
        get_available_models,
        is_model_installed,
    )

    console.print()
    console.print("[bold cyan]RAXE ML Model Download[/bold cyan]")
    console.print()

    # Show available models
    available = get_available_models()

    if not model_name and not download_all:
        # Show what's available and download default
        console.print("[bold]Available Models:[/bold]")
        console.print()

        for model in available:
            status = "[green]✓ Installed[/green]" if model["installed"] else "[yellow]Not installed[/yellow]"
            default_tag = " [cyan](default)[/cyan]" if model["is_default"] else ""
            console.print(f"  • [cyan]{model['id']}[/cyan]{default_tag}")
            console.print(f"    {model['description']}")
            console.print(f"    Status: {status}")
            console.print()

        # Download default model
        model_name = DEFAULT_MODEL
        console.print(f"[bold]Downloading default model:[/bold] {model_name}")
        console.print()

    # Determine which models to download
    if download_all:
        models_to_download = list(MODEL_REGISTRY.keys())
    else:
        if model_name not in MODEL_REGISTRY:
            console.print(f"[red]Unknown model: {model_name}[/red]")
            console.print()
            console.print("Available models:")
            for m in MODEL_REGISTRY:
                console.print(f"  • {m}")
            return

        models_to_download = [model_name]

    # Download each model
    for model_id in models_to_download:
        metadata = MODEL_REGISTRY[model_id]

        # Check if already installed
        if is_model_installed(model_id) and not force:
            console.print(f"[green]✓[/green] {metadata['name']} already installed")
            continue

        console.print(f"[bold]Downloading:[/bold] {metadata['name']} (~{metadata['size_mb']}MB)")

        # Create progress bar
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Downloading {model_id}...", total=metadata["size_mb"] * 1024 * 1024)

            def update_progress(downloaded: int, total: int) -> None:
                if total > 0:
                    progress.update(task, completed=downloaded, total=total)
                else:
                    progress.update(task, completed=downloaded)

            try:
                model_path = download_model(model_id, progress_callback=update_progress, force=force)
                console.print(f"[green]✓[/green] Installed to: {model_path}")
                console.print()
            except Exception as e:
                console.print(f"[red]✗[/red] Download failed: {e}")
                console.print()
                console.print("[dim]Check your internet connection and try again.[/dim]")
                return

    console.print()
    console.print("[bold green]Download complete![/bold green]")
    console.print()

    # Check if ML dependencies are installed
    try:
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        ml_ready = True
    except ImportError:
        ml_ready = False

    if ml_ready:
        console.print("Next steps:")
        console.print("  • Run [cyan]raxe scan \"test prompt\"[/cyan] to use L2 detection")
        console.print("  • Run [cyan]raxe models list[/cyan] to see installed models")
    else:
        console.print("[yellow]ML dependencies not installed.[/yellow]")
        console.print()
        console.print("To enable L2 ML detection, install the ml extras:")
        console.print("  [cyan]pip install 'raxe[ml]'[/cyan]")
        console.print()
        console.print("L1 rule-based detection (460+ rules) works without ML dependencies.")

    console.print()


@models.command("status")
def model_status():
    """Show ML model installation status.

    Quick check of which models are installed and ready to use.

    \b
    Examples:
      raxe models status
    """
    from raxe.infrastructure.ml.model_downloader import (
        get_available_models,
        get_models_directory,
        get_package_models_directory,
    )

    console.print()
    console.print("[bold cyan]ML Model Status[/bold cyan]")
    console.print()

    available = get_available_models()
    installed_count = sum(1 for m in available if m["installed"])

    # Show installation status
    table = Table(show_header=True, header_style="bold")
    table.add_column("Model", style="cyan")
    table.add_column("Size", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Notes")

    for model in available:
        status = "[green]✓ Ready[/green]" if model["installed"] else "[yellow]Not installed[/yellow]"
        notes = "Default" if model["is_default"] else ""
        table.add_row(
            model["id"],
            f"{model['size_mb']}MB",
            status,
            notes,
        )

    console.print(table)
    console.print()

    # Show summary
    console.print(f"[bold]Summary:[/bold] {installed_count}/{len(available)} models installed")
    console.print()

    if installed_count == 0:
        console.print("[yellow]No ML models installed. L2 detection using stub fallback.[/yellow]")
        console.print()
        console.print("To enable full L2 ML detection, run:")
        console.print("  [cyan]raxe models download[/cyan]")
        console.print()
    elif installed_count < len(available):
        console.print("To download remaining models:")
        console.print("  [cyan]raxe models download --all[/cyan]")
        console.print()

    # Show directories
    console.print("[dim]Model directories:[/dim]")
    console.print(f"  [dim]User: {get_models_directory()}[/dim]")
    console.print(f"  [dim]Package: {get_package_models_directory()}[/dim]")
    console.print()
