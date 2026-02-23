#!/usr/bin/env python3
"""Build pre-compiled rule cache for fast startup.

Generates a JSON cache file from all YAML rule files and a pickle
file of compiled regex patterns so that startup doesn't need to
parse 500+ YAML files or compile 1200+ regex patterns.

Usage:
    python scripts/build_rule_cache.py
    python scripts/build_rule_cache.py --pack-dir src/raxe/packs/core/v1.0.0

The generated cache files are committed to the repo and ship with
the PyPI package, giving all users zero cold-start penalty.

Note: Pickle is used for compiled regex patterns because regex.Pattern
objects are not JSON-serializable. The pickle files are generated from
our own trusted rule data and never from untrusted sources.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add src to path so script works without installation
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import click
from rich.console import Console

from raxe.domain.engine.matcher import PatternMatcher
from raxe.infrastructure.packs.cache import (
    CACHE_FILENAME,
    PATTERNS_CACHE_FILENAME,
    _compute_manifest_hash,
    write_cache,
    write_patterns_cache,
)
from raxe.infrastructure.packs.loader import PackLoader

console = Console()


@click.command()
@click.option(
    "--pack-dir",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Pack directory (default: src/raxe/packs/core/v1.0.0)",
)
def main(pack_dir: Path | None) -> None:
    """Build pre-compiled rule cache from YAML files."""
    if pack_dir is None:
        pack_dir = Path(__file__).parent.parent / "src" / "raxe" / "packs" / "core" / "v1.0.0"

    manifest_path = pack_dir / "pack.yaml"
    if not manifest_path.exists():
        console.print(f"[red]Error:[/red] No pack.yaml found in {pack_dir}")
        sys.exit(1)

    console.print(f"[bold]Building rule cache from {pack_dir}[/bold]")
    console.print()

    # Load all rules via YAML (slow but one-time)
    loader = PackLoader(strict=True)

    start = time.perf_counter()
    pack = loader.load_pack(pack_dir)
    load_ms = (time.perf_counter() - start) * 1000

    console.print(f"  Loaded {len(pack.rules)} rules from YAML in {load_ms:.0f}ms")

    # Write rules cache file next to pack.yaml (bundled cache)
    manifest_hash = _compute_manifest_hash(manifest_path)
    cache_path = pack_dir / CACHE_FILENAME

    write_cache(
        pack.rules,
        manifest_hash,
        cache_path,
        pack_id=pack.manifest.versioned_id,
    )

    size_kb = cache_path.stat().st_size / 1024
    console.print(f"  Rules cache written: {cache_path} ({size_kb:.0f} KB)")

    # Compile all regex patterns and write patterns cache
    console.print("  Compiling regex patterns...")
    matcher = PatternMatcher()
    compile_start = time.perf_counter()
    compile_errors = 0

    for rule in pack.rules:
        for pattern in rule.patterns:
            try:
                matcher.compile_pattern(pattern)
            except ValueError:
                compile_errors += 1

    compile_ms = (time.perf_counter() - compile_start) * 1000
    msg = f"  Compiled {matcher.cache_size} patterns in {compile_ms:.0f}ms"
    if compile_errors:
        msg += f" ({compile_errors} skipped due to errors)"
    console.print(msg)

    patterns_path = pack_dir / PATTERNS_CACHE_FILENAME
    write_patterns_cache(
        matcher._compiled_cache,
        manifest_hash,
        patterns_path,
    )

    patterns_size_kb = patterns_path.stat().st_size / 1024
    console.print(f"  Patterns cache written: {patterns_path} ({patterns_size_kb:.0f} KB)")

    console.print()
    console.print("[green]Done![/green] Both caches will be used on next startup.")


if __name__ == "__main__":
    main()
