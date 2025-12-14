"""Unified download progress for ML model downloads.

Provides consistent progress feedback across all entry points:
- CLI: Rich progress bars with speed and ETA
- SDK: Simple stderr output (non-intrusive)
- CI/CD: Timestamped log lines

This module ensures users always know what's happening during
the ~107MB model download, regardless of how they're using RAXE.
"""
from __future__ import annotations

import os
import sys
import time
from abc import ABC, abstractmethod
from typing import Callable


class DownloadProgress(ABC):
    """Abstract base for download progress indicators."""

    @abstractmethod
    def start(self, model_name: str, total_bytes: int) -> None:
        """Start download progress.

        Args:
            model_name: Human-readable model name
            total_bytes: Expected total size in bytes
        """
        pass

    @abstractmethod
    def update(self, downloaded_bytes: int, total_bytes: int) -> None:
        """Update download progress.

        Args:
            downloaded_bytes: Bytes downloaded so far
            total_bytes: Expected total size
        """
        pass

    @abstractmethod
    def complete(self) -> None:
        """Mark download as complete."""
        pass

    @abstractmethod
    def error(self, message: str) -> None:
        """Report download error.

        Args:
            message: Error description
        """
        pass

    def get_callback(self) -> Callable[[int, int], None]:
        """Get a callback function for use with download functions.

        Returns:
            Callback that calls self.update(downloaded, total)
        """
        return lambda downloaded, total: self.update(downloaded, total)


class RichDownloadProgress(DownloadProgress):
    """Rich progress bar for interactive terminals.

    Features:
    - Visual progress bar
    - Download speed (MB/s)
    - ETA (time remaining)
    - Total size display
    """

    def __init__(self):
        self._progress = None
        self._task = None
        self._model_name = ""

    def start(self, model_name: str, total_bytes: int) -> None:
        """Start Rich progress display."""
        from rich.console import Console
        from rich.progress import (
            BarColumn,
            DownloadColumn,
            Progress,
            SpinnerColumn,
            TextColumn,
            TimeRemainingColumn,
            TransferSpeedColumn,
        )

        self._model_name = model_name
        self._console = Console(stderr=True)

        # Print header
        self._console.print()
        self._console.print(
            f"[bold cyan]Downloading ML model:[/bold cyan] {model_name}"
        )

        # Create progress bar
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=self._console,
            transient=False,  # Keep visible after completion
        )
        self._progress.start()
        self._task = self._progress.add_task(
            "Downloading...",
            total=total_bytes,
        )

    def update(self, downloaded_bytes: int, total_bytes: int) -> None:
        """Update Rich progress bar."""
        if self._progress and self._task is not None:
            self._progress.update(
                self._task,
                completed=downloaded_bytes,
                total=total_bytes,
            )

    def complete(self) -> None:
        """Complete and stop Rich progress."""
        if self._progress:
            self._progress.stop()
            self._console.print(
                "[bold green]Download complete![/bold green]"
            )
            self._console.print()

    def error(self, message: str) -> None:
        """Show error in Rich format."""
        if self._progress:
            self._progress.stop()
        from rich.console import Console
        console = Console(stderr=True)
        console.print()
        console.print(f"[bold red]Download failed:[/bold red] {message}")
        console.print()
        console.print("[dim]L1 detection (460+ rules) will still work.[/dim]")
        console.print("[dim]Run 'raxe models download' to retry.[/dim]")
        console.print()


class SimpleDownloadProgress(DownloadProgress):
    """Simple text progress for CI/CD and non-TTY environments.

    Features:
    - Timestamped log lines
    - Periodic percentage updates (every 10%)
    - Machine-parseable format
    """

    def __init__(self):
        self._model_name = ""
        self._last_percent = -10  # Track last reported percentage
        self._start_time = 0.0

    def start(self, model_name: str, total_bytes: int) -> None:
        """Print start message with timestamp."""
        self._model_name = model_name
        self._start_time = time.time()
        size_mb = total_bytes / (1024 * 1024)
        self._log(f"Downloading ML model: {model_name} ({size_mb:.0f}MB)")

    def update(self, downloaded_bytes: int, total_bytes: int) -> None:
        """Print progress at 10% intervals."""
        if total_bytes <= 0:
            return

        percent = int((downloaded_bytes / total_bytes) * 100)

        # Report every 10%
        if percent >= self._last_percent + 10:
            self._last_percent = (percent // 10) * 10
            downloaded_mb = downloaded_bytes / (1024 * 1024)
            total_mb = total_bytes / (1024 * 1024)
            self._log(f"Progress: {self._last_percent}% ({downloaded_mb:.1f}/{total_mb:.1f}MB)")

    def complete(self) -> None:
        """Print completion message with duration."""
        duration = time.time() - self._start_time
        self._log(f"Download complete ({duration:.1f}s)")

    def error(self, message: str) -> None:
        """Print error message."""
        self._log(f"Download failed: {message}")
        self._log("L1 detection (460+ rules) will still work.")
        self._log("Run 'raxe models download' to retry.")

    def _log(self, message: str) -> None:
        """Print timestamped message to stderr."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}", file=sys.stderr)


class MinimalDownloadProgress(DownloadProgress):
    """Minimal progress for SDK - single line updates.

    Shows progress without being too verbose, suitable for
    SDK usage where users may not expect CLI-style output.

    Features:
    - Single line with carriage return
    - Shows percentage, speed estimate
    - Non-intrusive stderr output
    """

    def __init__(self):
        self._model_name = ""
        self._start_time = 0.0
        self._last_update = 0.0
        self._total_bytes = 0

    def start(self, model_name: str, total_bytes: int) -> None:
        """Print start message."""
        self._model_name = model_name
        self._total_bytes = total_bytes
        self._start_time = time.time()
        self._last_update = self._start_time
        size_mb = total_bytes / (1024 * 1024)
        print(
            f"\n[RAXE] Downloading ML model (~{size_mb:.0f}MB)...",
            file=sys.stderr,
        )

    def update(self, downloaded_bytes: int, total_bytes: int) -> None:
        """Update single-line progress."""
        if total_bytes <= 0:
            return

        # Throttle updates to every 0.5 seconds
        now = time.time()
        if now - self._last_update < 0.5:
            return
        self._last_update = now

        percent = (downloaded_bytes / total_bytes) * 100
        downloaded_mb = downloaded_bytes / (1024 * 1024)
        total_mb = total_bytes / (1024 * 1024)

        # Calculate speed
        elapsed = now - self._start_time
        if elapsed > 0:
            speed_mbps = (downloaded_bytes / (1024 * 1024)) / elapsed
            eta_seconds = (total_bytes - downloaded_bytes) / (downloaded_bytes / elapsed) if downloaded_bytes > 0 else 0
            eta_str = f"{eta_seconds:.0f}s" if eta_seconds < 60 else f"{eta_seconds/60:.1f}m"
            speed_str = f"{speed_mbps:.1f}MB/s"
        else:
            speed_str = "---"
            eta_str = "---"

        # Single line update with carriage return
        print(
            f"\r[RAXE] Progress: {percent:.0f}% ({downloaded_mb:.1f}/{total_mb:.1f}MB) | {speed_str} | ETA: {eta_str}   ",
            end="",
            file=sys.stderr,
        )

    def complete(self) -> None:
        """Print completion message."""
        duration = time.time() - self._start_time
        print(file=sys.stderr)  # New line after progress
        print(
            f"[RAXE] Model downloaded successfully ({duration:.1f}s)",
            file=sys.stderr,
        )

    def error(self, message: str) -> None:
        """Print error message."""
        print(file=sys.stderr)  # New line after progress
        print(f"[RAXE] Download failed: {message}", file=sys.stderr)
        print("[RAXE] L1 detection (460+ rules) will still work.", file=sys.stderr)
        print("[RAXE] Run 'raxe models download' to retry.", file=sys.stderr)


class QuietDownloadProgress(DownloadProgress):
    """Silent progress - only errors shown.

    Used when --quiet flag is set or RAXE_QUIET=1.
    """

    def start(self, model_name: str, total_bytes: int) -> None:
        pass

    def update(self, downloaded_bytes: int, total_bytes: int) -> None:
        pass

    def complete(self) -> None:
        pass

    def error(self, message: str) -> None:
        # Errors must always be shown
        print(f"[RAXE] Download failed: {message}", file=sys.stderr)


def detect_download_progress_mode() -> str:
    """Detect appropriate download progress mode.

    Returns:
        Mode string: "rich", "simple", "minimal", or "quiet"

    Detection priority:
        1. RAXE_QUIET → quiet
        2. Non-TTY (CI/CD) → simple
        3. RAXE_SIMPLE_PROGRESS → simple
        4. SDK context (no CLI) → minimal
        5. Default → rich
    """
    # Quiet mode
    if os.getenv("RAXE_QUIET"):
        return "quiet"

    # Non-TTY environments (CI/CD, pipes)
    if not sys.stderr.isatty():
        return "simple"

    # Explicit simple mode
    if os.getenv("RAXE_SIMPLE_PROGRESS"):
        return "simple"

    # Dumb terminal
    term = os.getenv("TERM", "")
    if term in ("dumb", ""):
        return "simple"

    # Default to rich for interactive terminals
    return "rich"


def create_download_progress(
    mode: str | None = None,
    force_mode: str | None = None,
) -> DownloadProgress:
    """Create appropriate download progress indicator.

    Args:
        mode: Progress mode override (rich, simple, minimal, quiet)
        force_mode: Force a specific mode regardless of detection

    Returns:
        DownloadProgress instance for the detected/specified mode
    """
    # Use forced mode if specified
    if force_mode:
        mode = force_mode
    elif mode is None:
        mode = detect_download_progress_mode()

    if mode == "rich":
        return RichDownloadProgress()
    elif mode == "simple":
        return SimpleDownloadProgress()
    elif mode == "minimal":
        return MinimalDownloadProgress()
    elif mode == "quiet":
        return QuietDownloadProgress()
    else:
        # Safe fallback
        return SimpleDownloadProgress()


def download_with_progress(
    url: str,
    dest_path: str,
    model_name: str = "ML Model",
    expected_size_bytes: int = 0,
    progress: DownloadProgress | None = None,
) -> None:
    """Download a file with progress feedback.

    This is the unified download function used by all entry points.

    Args:
        url: URL to download from
        dest_path: Local path to save file
        model_name: Human-readable name for progress display
        expected_size_bytes: Expected file size (for progress bar)
        progress: Optional progress indicator (auto-detected if not provided)

    Raises:
        RuntimeError: If download fails
    """
    from pathlib import Path
    from urllib.error import HTTPError, URLError
    from urllib.request import urlopen

    # Auto-detect progress mode if not provided
    if progress is None:
        progress = create_download_progress()

    try:
        with urlopen(url, timeout=60) as response:
            total_size = int(response.headers.get("Content-Length", expected_size_bytes))

            # Start progress
            progress.start(model_name, total_size)

            downloaded = 0
            chunk_size = 8192

            with open(dest_path, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)
                    progress.update(downloaded, total_size)

            progress.complete()

    except HTTPError as e:
        error_msg = f"HTTP error: {e.code} {e.reason}"
        progress.error(error_msg)
        # Clean up partial download
        Path(dest_path).unlink(missing_ok=True)
        raise RuntimeError(error_msg) from e

    except URLError as e:
        error_msg = f"Network error: {e.reason}"
        progress.error(error_msg)
        Path(dest_path).unlink(missing_ok=True)
        raise RuntimeError(error_msg) from e

    except Exception as e:
        error_msg = f"Download failed: {e}"
        progress.error(error_msg)
        Path(dest_path).unlink(missing_ok=True)
        raise RuntimeError(error_msg) from e
