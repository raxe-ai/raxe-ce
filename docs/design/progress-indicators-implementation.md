# RAXE CLI Progress Indicators - Implementation Guide

**Document Version:** 1.0
**Date:** 2025-11-20
**For:** frontend-dev
**Status:** Ready to Implement

This guide provides step-by-step instructions for implementing the progress indicator system.

---

## Quick Start

**Estimated Implementation Time:** 4-6 hours

**Files to Create:**
1. `/src/raxe/cli/progress.py` - Progress indicator classes (new)
2. `/src/raxe/cli/progress_context.py` - Context detection (new)

**Files to Modify:**
3. `/src/raxe/cli/main.py` - CLI scan command integration
4. `/src/raxe/sdk/client.py` - Add progress callback support
5. `/src/raxe/application/preloader.py` - Add progress updates

**Testing:**
6. `/tests/cli/test_progress.py` - Unit tests (new)
7. `/tests/cli/test_scan_progress.py` - Integration tests (new)

---

## Phase 1: Core Progress Component (2 hours)

### Step 1.1: Create Progress Base Class

**File:** `/src/raxe/cli/progress.py`

```python
"""Progress indicators for RAXE initialization."""

from abc import ABC, abstractmethod
from typing import Literal

ComponentStatus = Literal["loading", "complete", "error"]


class ProgressIndicator(ABC):
    """Abstract base for progress indicators.

    All progress implementations must inherit from this class
    and implement the required methods.
    """

    @abstractmethod
    def start(self, message: str) -> None:
        """Start showing progress.

        Args:
            message: Main progress message (e.g., "Initializing RAXE...")
        """
        pass

    @abstractmethod
    def update_component(
        self,
        name: str,
        status: ComponentStatus,
        duration_ms: float
    ) -> None:
        """Update status of a component.

        Args:
            name: Component identifier (rules, ml_model, warmup)
            status: Current status (loading, complete, error)
            duration_ms: Time taken in milliseconds (0 if loading)
        """
        pass

    @abstractmethod
    def complete(self, total_duration_ms: float) -> None:
        """Mark initialization as complete.

        Args:
            total_duration_ms: Total initialization time
        """
        pass

    @abstractmethod
    def error(self, component: str, message: str) -> None:
        """Report component failure.

        Args:
            component: Component that failed
            message: Error message
        """
        pass


class NullProgress(ProgressIndicator):
    """No-op progress for when no callback provided.

    Used internally when SDK is used without CLI progress.
    """

    def start(self, message: str) -> None:
        pass

    def update_component(
        self,
        name: str,
        status: ComponentStatus,
        duration_ms: float
    ) -> None:
        pass

    def complete(self, total_duration_ms: float) -> None:
        pass

    def error(self, component: str, message: str) -> None:
        pass
```

**Testing:**
```python
# tests/cli/test_progress.py
def test_null_progress_no_output():
    """Test NullProgress produces no output."""
    progress = NullProgress()
    progress.start("test")
    progress.update_component("test", "complete", 100)
    progress.complete(100)
    # Should not crash, should not output anything
```

---

### Step 1.2: Implement Interactive Progress

**Add to:** `/src/raxe/cli/progress.py`

```python
import time
import sys
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text


class InteractiveProgress(ProgressIndicator):
    """Rich progress for interactive terminals.

    Features:
    - Live-updating spinners
    - Color-coded status
    - Transient display (clears after completion)
    """

    # Component display configuration
    COMPONENT_LABELS = {
        "rules": {
            "loading": "Loading detection rules",
            "complete": "Loaded {count} rules",
        },
        "ml_model": {
            "loading": "Loading ML model",
            "complete": "Loaded ML model",
        },
        "warmup": {
            "loading": "Warming up components",
            "complete": "Components ready",
        }
    }

    def __init__(self):
        self.console = Console()
        self.components = {}
        self.live = None
        self.start_time = None
        self.main_message = ""
        self.rules_count = 0  # Track for display

    def start(self, message: str) -> None:
        """Start showing progress with live updates."""
        self.start_time = time.time()
        self.main_message = message

        # Initialize components in order
        self.components = {
            "rules": {"status": "loading", "duration_ms": 0},
            "ml_model": {"status": "loading", "duration_ms": 0},
            "warmup": {"status": "loading", "duration_ms": 0},
        }

        # Start live display (transient=True makes it disappear after stop)
        self.live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=10,  # 10 FPS for smooth spinner
            transient=True
        )
        self.live.start()

    def update_component(
        self,
        name: str,
        status: ComponentStatus,
        duration_ms: float,
        metadata: dict = None
    ) -> None:
        """Update component status with live refresh."""
        if name not in self.components:
            return

        self.components[name]["status"] = status
        self.components[name]["duration_ms"] = duration_ms

        # Store metadata for display (e.g., rules count)
        if metadata:
            if name == "rules" and "count" in metadata:
                self.rules_count = metadata["count"]

        if self.live:
            self.live.update(self._render())

    def complete(self, total_duration_ms: float) -> None:
        """Show completion and clear after delay."""
        if not self.live:
            return

        # Update to completion state
        final_render = self._render_complete(total_duration_ms)
        self.live.update(final_render)

        # Wait for user to read (500ms)
        time.sleep(0.5)

        # Stop live display (transient will auto-clear)
        self.live.stop()

    def error(self, component: str, message: str) -> None:
        """Show error panel."""
        if self.live:
            self.live.stop()

        error_text = Text()
        error_text.append("✗ ", style="red bold")
        error_text.append(f"Initialization failed: {component}\n", style="red")
        error_text.append(message, style="dim")

        self.console.print(Panel(error_text, border_style="red"))

    def _render(self) -> Panel:
        """Render current progress state."""
        content = Text()

        # Header
        content.append("🔧 ", style="cyan")
        content.append(self.main_message, style="cyan bold")
        content.append("\n")

        # Component status lines
        for name, data in self.components.items():
            content.append("  ")  # Indent

            if data["status"] == "loading":
                content.append("⏳ ", style="cyan")
                label = self._get_label(name, "loading")
                content.append(label, style="white")
                content.append("...\n")

            elif data["status"] == "complete":
                content.append("✓ ", style="green")
                label = self._get_label(name, "complete")
                content.append(label, style="green")
                content.append(
                    f" ({data['duration_ms']:.0f}ms)",
                    style="dim white"
                )
                content.append("\n")

            elif data["status"] == "error":
                content.append("✗ ", style="red")
                label = self._get_label(name, "error")
                content.append(label, style="red")
                content.append("\n")

        return Panel(content, border_style="cyan", padding=(0, 1))

    def _render_complete(self, total_ms: float) -> Panel:
        """Render completion state."""
        content = Text()
        content.append("✓ ", style="green bold")
        content.append("Ready to scan", style="green bold")
        content.append(
            f" (Total: {total_ms:.0f}ms, one-time)",
            style="dim white"
        )

        return Panel(content, border_style="green", padding=(0, 1))

    def _get_label(self, name: str, status: str) -> str:
        """Get human-readable label for component."""
        labels = self.COMPONENT_LABELS.get(name, {})
        label_template = labels.get(status, name)

        # Format with variables (e.g., rules count)
        if name == "rules" and status == "complete":
            return label_template.format(count=self.rules_count)

        return label_template
```

**Testing:**
```python
def test_interactive_progress_displays():
    """Test interactive progress shows correctly."""
    progress = InteractiveProgress()
    progress.start("Test initialization")

    # Update components
    progress.update_component("rules", "complete", 100, {"count": 460})
    progress.update_component("ml_model", "complete", 1000)

    # Should complete without error
    progress.complete(1100)
```

---

### Step 1.3: Implement Simple Progress (CI/CD)

**Add to:** `/src/raxe/cli/progress.py`

```python
class SimpleProgress(ProgressIndicator):
    """Plain text progress for CI/CD environments.

    Features:
    - No ANSI codes
    - Timestamped messages
    - Minimal output
    - Log-parser friendly
    """

    def __init__(self):
        self.start_time = None

    def start(self, message: str) -> None:
        """Print start message with timestamp."""
        self._log(message)

    def update_component(
        self,
        name: str,
        status: ComponentStatus,
        duration_ms: float,
        metadata: dict = None
    ) -> None:
        """Print component completion (skip loading state)."""
        if status == "complete":
            label = self._get_label(name, metadata)
            self._log(f"{label} ({duration_ms:.0f}ms)")

    def complete(self, total_duration_ms: float) -> None:
        """Print completion message."""
        self._log(
            f"Initialization complete ({total_duration_ms:.0f}ms, one-time)"
        )

    def error(self, component: str, message: str) -> None:
        """Print error message."""
        self._log(f"ERROR: {component} - {message}")

    def _log(self, message: str) -> None:
        """Print timestamped message to stderr."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}", file=sys.stderr)

    def _get_label(self, name: str, metadata: dict = None) -> str:
        """Get simple label for component."""
        labels = {
            "rules": "Loaded detection rules",
            "ml_model": "Loaded ML model",
            "warmup": "Components ready",
        }

        label = labels.get(name, name)

        # Add count for rules
        if name == "rules" and metadata and "count" in metadata:
            label = f"Loaded {metadata['count']} rules"

        return label
```

**Testing:**
```python
def test_simple_progress_no_ansi():
    """Test simple progress has no ANSI codes."""
    import io

    captured = io.StringIO()
    sys.stderr = captured

    progress = SimpleProgress()
    progress.start("Test")
    progress.update_component("rules", "complete", 100)

    output = captured.getvalue()
    assert "\x1b[" not in output  # No ANSI escape codes
    assert "[" in output  # Has timestamps
```

---

### Step 1.4: Implement Quiet Progress

**Add to:** `/src/raxe/cli/progress.py`

```python
class QuietProgress(ProgressIndicator):
    """Silent progress for --quiet mode.

    Only errors are shown (can't suppress errors).
    """

    def start(self, message: str) -> None:
        pass

    def update_component(
        self,
        name: str,
        status: ComponentStatus,
        duration_ms: float,
        metadata: dict = None
    ) -> None:
        pass

    def complete(self, total_duration_ms: float) -> None:
        pass

    def error(self, component: str, message: str) -> None:
        # Errors must always be shown
        print(f"ERROR: {component} - {message}", file=sys.stderr)
```

---

### Step 1.5: Create Factory Function

**Add to:** `/src/raxe/cli/progress.py`

```python
def create_progress_indicator(mode: str) -> ProgressIndicator:
    """Factory function to create appropriate progress indicator.

    Args:
        mode: Progress mode (interactive, simple, quiet)

    Returns:
        Appropriate ProgressIndicator instance
    """
    if mode == "interactive":
        return InteractiveProgress()
    elif mode == "simple":
        return SimpleProgress()
    elif mode == "quiet":
        return QuietProgress()
    else:
        # Safe default for unknown modes
        return SimpleProgress()
```

---

## Phase 2: Context Detection (1 hour)

### Step 2.1: Create Context Detection Module

**File:** `/src/raxe/cli/progress_context.py`

```python
"""Terminal context detection for progress indicators."""

import sys
import os


def detect_progress_mode(
    quiet: bool = False,
    verbose: bool = False,
    no_color: bool = False
) -> str:
    """Detect appropriate progress mode based on terminal context.

    Args:
        quiet: --quiet flag set
        verbose: --verbose flag set
        no_color: --no-color flag set

    Returns:
        Progress mode: "interactive", "simple", or "quiet"

    Priority:
        1. Explicit --quiet flag → quiet
        2. Non-TTY environment → simple
        3. Dumb terminal → simple
        4. NO_COLOR environment → simple
        5. Default → interactive
    """

    # Priority 1: Explicit quiet flag
    if quiet or os.getenv('RAXE_QUIET'):
        return 'quiet'

    # Priority 2: Check if stdout is a TTY
    if not sys.stdout.isatty():
        return 'simple'  # CI/CD, pipe, redirect

    # Priority 3: Check for dumb terminal
    term = os.getenv('TERM', '')
    if term in ('dumb', ''):
        return 'simple'

    # Priority 4: Check for NO_COLOR or --no-color
    if no_color or os.getenv('NO_COLOR') or os.getenv('RAXE_NO_COLOR'):
        return 'simple'

    # Priority 5: Check for explicit simple mode
    if os.getenv('RAXE_SIMPLE_PROGRESS'):
        return 'simple'

    # Default: Full interactive progress
    return 'interactive'


def supports_unicode() -> bool:
    """Check if terminal supports Unicode icons.

    Returns:
        True if Unicode supported, False for ASCII fallback
    """
    # Check for ASCII-only mode
    if os.getenv('RAXE_ASCII_ONLY'):
        return False

    # Check encoding
    encoding = sys.stdout.encoding or ''
    if 'utf' in encoding.lower():
        return True

    # Windows CMD often doesn't support Unicode
    if sys.platform == 'win32' and os.getenv('TERM') != 'xterm':
        return False

    return True


def supports_animation() -> bool:
    """Check if terminal supports animations.

    Returns:
        True if animations supported, False for static icons
    """
    # Check for explicit no-animation flag
    if os.getenv('RAXE_NO_ANIMATION'):
        return False

    # Check for accessibility mode
    if os.getenv('RAXE_ACCESSIBLE_MODE'):
        return False

    # Non-TTY doesn't support animation
    if not sys.stdout.isatty():
        return False

    return True
```

**Testing:**
```python
def test_detect_progress_quiet_flag():
    """Test --quiet flag forces quiet mode."""
    mode = detect_progress_mode(quiet=True)
    assert mode == "quiet"

def test_detect_progress_non_tty():
    """Test non-TTY forces simple mode."""
    # Mock isatty
    original = sys.stdout.isatty
    sys.stdout.isatty = lambda: False

    mode = detect_progress_mode()
    assert mode == "simple"

    sys.stdout.isatty = original

def test_detect_progress_interactive():
    """Test TTY with color support uses interactive."""
    mode = detect_progress_mode(quiet=False, no_color=False)
    # Should be interactive if TTY available
    assert mode in ("interactive", "simple")
```

---

## Phase 3: Integration (2 hours)

### Step 3.1: Integrate into CLI Main

**File:** `/src/raxe/cli/main.py`

**Find the `scan` command function (around line 247) and modify:**

```python
@cli.command()
@click.argument("text", required=False)
# ... other options ...
@click.pass_context
def scan(
    ctx,
    text: str | None,
    stdin: bool,
    format: str,
    # ... other params ...
):
    """Scan text for security threats."""

    # Check if quiet mode is enabled
    quiet = ctx.obj.get("quiet", False)
    verbose = ctx.obj.get("verbose", False)
    no_color = ctx.obj.get("no_color", False)

    # Override format to JSON if quiet mode
    if quiet and format == "text":
        format = "json"

    # Show compact logo (for visual consistency)
    from raxe.cli.branding import print_logo
    if format == "text" and not quiet:
        print_logo(console, compact=True)
        console.print()

    # Get text from argument or stdin
    if stdin:
        text = sys.stdin.read()
    elif not text:
        display_error("No text provided", "Provide text as argument or use --stdin")
        sys.exit(1)

    # ========== NEW: Progress indicator setup ==========
    from raxe.cli.progress_context import detect_progress_mode
    from raxe.cli.progress import create_progress_indicator

    progress_mode = detect_progress_mode(
        quiet=quiet,
        verbose=verbose,
        no_color=no_color
    )

    progress = create_progress_indicator(progress_mode)
    # ====================================================

    # Create Raxe client (uses config if available)
    try:
        # ========== NEW: Pass progress callback ==========
        raxe = Raxe(progress_callback=progress)
        # =================================================
    except Exception as e:
        display_error("Failed to initialize RAXE", str(e))
        console.print("Try running: [cyan]raxe init[/cyan]")
        sys.exit(1)

    # Continue with existing scan logic...
    # Scan using unified client
    if profile:
        # ... existing profile code ...
    else:
        result = raxe.scan(
            text,
            l1_enabled=not l2_only,
            l2_enabled=not l1_only,
            mode=mode,
            confidence_threshold=confidence if confidence else 0.5,
            explain=explain,
            dry_run=dry_run,
        )

    # Output based on format (existing code continues...)
```

---

### Step 3.2: Integrate into SDK Client

**File:** `/src/raxe/sdk/client.py`

**Modify the `__init__` method (around line 60):**

```python
def __init__(
    self,
    *,
    api_key: str | None = None,
    config_path: Path | None = None,
    telemetry: bool = True,
    l2_enabled: bool = True,
    performance_mode: str = "balanced",
    progress_callback = None,  # NEW parameter
    **kwargs
):
    """Initialize RAXE client.

    Args:
        ... existing args ...
        progress_callback: Optional progress indicator for initialization
        **kwargs: Additional config options passed to ScanConfig
    """

    # ========== NEW: Store progress callback ==========
    from raxe.cli.progress import NullProgress

    self._progress = progress_callback or NullProgress()
    # ==================================================

    # Build configuration with cascade
    if config_path and config_path.exists():
        self.config = ScanConfig.from_file(config_path)
    else:
        self.config = ScanConfig()

    # Apply explicit overrides
    if api_key is not None:
        self.config.api_key = api_key
    self.config.telemetry.enabled = telemetry
    self.config.enable_l2 = l2_enabled

    # Initialize tracking and history components
    self._usage_tracker: UsageTracker | None = None
    self._scan_history: ScanHistoryDB | None = None
    self._streak_tracker = None

    # Initialize suppression manager
    self.suppression_manager = create_suppression_manager(auto_load=True)

    # Preload pipeline (one-time startup cost ~100-200ms)
    logger.info("raxe_client_init_start")

    # ========== NEW: Start progress indicator ==========
    self._progress.start("Initializing RAXE...")
    # ===================================================

    try:
        self.pipeline, self.preload_stats = preload_pipeline(
            config=self.config,
            suppression_manager=self.suppression_manager,
            progress_callback=self._progress  # NEW: Pass through
        )

        # ... existing code ...

        self._initialized = True

        # ========== NEW: Complete progress ==========
        self._progress.complete(
            total_duration_ms=self.preload_stats.duration_ms
        )
        # ===========================================

        logger.info(
            "raxe_client_init_complete",
            rules_loaded=self.preload_stats.rules_loaded
        )
    except Exception as e:
        # ========== NEW: Report error ==========
        self._progress.error("initialization", str(e))
        # =======================================

        logger.error("raxe_client_init_failed", error=str(e))
        raise
```

---

### Step 3.3: Integrate into Preloader

**File:** `/src/raxe/application/preloader.py`

**Modify the `PipelinePreloader` class:**

```python
class PipelinePreloader:
    """Preload and optimize scan pipeline at startup."""

    def __init__(
        self,
        config_path: Path | None = None,
        config: ScanConfig | None = None,
        suppression_manager: object | None = None,
        progress_callback = None,  # NEW parameter
    ):
        """Initialize preloader.

        Args:
            ... existing args ...
            progress_callback: Optional progress indicator
        """
        self.config_path = config_path
        self._config = config
        self.suppression_manager = suppression_manager

        # ========== NEW: Store progress callback ==========
        from raxe.cli.progress import NullProgress
        self._progress = progress_callback or NullProgress()
        # ==================================================

    def preload(self) -> tuple[ScanPipeline, PreloadStats]:
        """Preload all components with progress updates."""
        start_time = time.perf_counter()
        logger.info("Starting pipeline preload")

        # 1. Load configuration
        # ... existing code ...

        # 2. Load pack registry and rules
        # ========== NEW: Update progress ==========
        self._progress.update_component("rules", "loading", 0)
        # =========================================

        # ... existing pack loading code ...
        rules_time = (time.perf_counter() - rules_start) * 1000

        # ========== NEW: Report completion ==========
        self._progress.update_component(
            "rules",
            "complete",
            rules_time,
            metadata={"count": rules_loaded}
        )
        # ===========================================

        # 3. Initialize rule executor
        # ... existing code ...

        # 4. Initialize L2 detector
        # ========== NEW: Update progress ==========
        self._progress.update_component("ml_model", "loading", 0)
        # =========================================

        l2_init_start = time.perf_counter()
        l2_detector = EagerL2Detector(
            config=config,
            use_production=config.use_production_l2,
            confidence_threshold=config.l2_confidence_threshold
        )
        l2_init_time_ms = (time.perf_counter() - l2_init_start) * 1000

        # ========== NEW: Report completion ==========
        self._progress.update_component(
            "ml_model",
            "complete",
            l2_init_time_ms
        )
        # ===========================================

        # 5. Initialize scan merger
        # ... existing code ...

        # 6. Warmup
        # ========== NEW: Update progress ==========
        self._progress.update_component("warmup", "loading", 0)
        # =========================================

        warmup_start = time.perf_counter()
        # ... existing warmup code ...
        warmup_time = (time.perf_counter() - warmup_start) * 1000

        # ========== NEW: Report completion ==========
        self._progress.update_component("warmup", "complete", warmup_time)
        # ===========================================

        # ... rest of existing code ...

        return pipeline, stats
```

**Modify the helper function:**

```python
def preload_pipeline(
    config_path: Path | None = None,
    config: ScanConfig | None = None,
    suppression_manager: object | None = None,
    progress_callback = None,  # NEW parameter
) -> tuple[ScanPipeline, PreloadStats]:
    """Convenience function to preload pipeline.

    Args:
        ... existing args ...
        progress_callback: Optional progress indicator
    """
    preloader = PipelinePreloader(
        config_path,
        config,
        suppression_manager,
        progress_callback  # NEW: Pass through
    )
    return preloader.preload()
```

---

## Phase 4: Testing (1-2 hours)

### Step 4.1: Unit Tests

**File:** `/tests/cli/test_progress.py`

```python
"""Unit tests for progress indicators."""

import pytest
import sys
import io
from raxe.cli.progress import (
    InteractiveProgress,
    SimpleProgress,
    QuietProgress,
    NullProgress,
    create_progress_indicator
)


def test_null_progress_no_output():
    """Test NullProgress produces no output."""
    progress = NullProgress()
    progress.start("test")
    progress.update_component("test", "complete", 100)
    progress.complete(100)
    # Should not crash


def test_simple_progress_no_ansi():
    """Test SimpleProgress has no ANSI codes."""
    captured = io.StringIO()
    original_stderr = sys.stderr
    sys.stderr = captured

    progress = SimpleProgress()
    progress.start("Test initialization")
    progress.update_component("rules", "complete", 100, {"count": 460})
    progress.complete(1000)

    sys.stderr = original_stderr

    output = captured.getvalue()
    assert "\x1b[" not in output  # No ANSI escape codes
    assert "[" in output  # Has timestamps
    assert "Initialization complete" in output


def test_quiet_progress_silent():
    """Test QuietProgress produces no output."""
    captured = io.StringIO()
    original_stderr = sys.stderr
    sys.stderr = captured

    progress = QuietProgress()
    progress.start("Test")
    progress.update_component("rules", "complete", 100)
    progress.complete(100)

    sys.stderr = original_stderr

    output = captured.getvalue()
    assert output == ""  # Completely silent


def test_quiet_progress_shows_errors():
    """Test QuietProgress shows errors."""
    captured = io.StringIO()
    original_stderr = sys.stderr
    sys.stderr = captured

    progress = QuietProgress()
    progress.error("test_component", "Test error")

    sys.stderr = original_stderr

    output = captured.getvalue()
    assert "ERROR" in output
    assert "test_component" in output


def test_factory_creates_correct_type():
    """Test factory creates correct progress type."""
    interactive = create_progress_indicator("interactive")
    assert isinstance(interactive, InteractiveProgress)

    simple = create_progress_indicator("simple")
    assert isinstance(simple, SimpleProgress)

    quiet = create_progress_indicator("quiet")
    assert isinstance(quiet, QuietProgress)

    default = create_progress_indicator("unknown")
    assert isinstance(default, SimpleProgress)  # Safe default


def test_interactive_progress_lifecycle():
    """Test InteractiveProgress full lifecycle."""
    progress = InteractiveProgress()

    progress.start("Test initialization")
    progress.update_component("rules", "complete", 100, {"count": 460})
    progress.update_component("ml_model", "complete", 1000)
    progress.update_component("warmup", "complete", 50)
    progress.complete(1150)

    # Should complete without errors
```

---

### Step 4.2: Integration Tests

**File:** `/tests/cli/test_scan_progress.py`

```python
"""Integration tests for scan command progress."""

import pytest
from click.testing import CliRunner
from raxe.cli.main import cli


def test_scan_shows_progress_text_format():
    """Test scan shows progress in text format."""
    runner = CliRunner()
    result = runner.invoke(cli, ['scan', 'test text'])

    # Should complete successfully
    assert result.exit_code == 0

    # Progress should appear (or have appeared transiently)
    # Result should show scan output
    assert "SAFE" in result.output or "THREAT" in result.output


def test_scan_quiet_mode_no_progress():
    """Test --quiet suppresses progress."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--quiet', 'scan', 'test'])

    # Should only have JSON output
    assert result.exit_code == 0
    assert "Initializing" not in result.output
    assert "has_detections" in result.output


def test_scan_json_format_with_progress():
    """Test JSON format works with progress."""
    runner = CliRunner()
    result = runner.invoke(cli, ['scan', 'test', '--format', 'json'])

    assert result.exit_code == 0
    # Progress goes to stderr, JSON to stdout
    assert "has_detections" in result.output


def test_scan_ci_cd_simple_progress():
    """Test non-TTY produces simple progress."""
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli,
        ['scan', 'test'],
        env={'TERM': 'dumb'}
    )

    # Should use simple progress (no ANSI codes in stderr)
    if result.stderr:
        assert "\x1b[" not in result.stderr

    assert result.exit_code == 0
```

---

### Step 4.3: Manual Testing Checklist

**Interactive Terminal:**
```bash
# Test 1: Standard interactive progress
raxe scan "test"
# Expected: Progress box appears, animates, clears

# Test 2: Verbose mode (progress stays)
raxe --verbose scan "test"
# Expected: Progress box stays visible with details

# Test 3: No color mode
raxe --no-color scan "test"
# Expected: Simple text progress (no colors)
```

**CI/CD Simulation:**
```bash
# Test 4: Piped output
echo "test" | raxe scan --stdin | tee log.txt
# Expected: Plain text progress in log.txt

# Test 5: Non-TTY environment
script -q /dev/null -c "raxe scan test"
# Expected: Simple progress (no spinners)

# Test 6: Quiet mode
raxe --quiet scan "test"
# Expected: Only JSON output, no progress
```

**Error Handling:**
```bash
# Test 7: Missing ML model (should degrade gracefully)
mv ~/.raxe/models ~/.raxe/models.bak
raxe scan "test"
# Expected: Warning about ML model, continues with rules only
mv ~/.raxe/models.bak ~/.raxe/models

# Test 8: Permission error (should show clear error)
chmod 000 ~/.raxe/
raxe scan "test"
# Expected: Clear error message with fix suggestions
chmod 755 ~/.raxe/
```

---

## Phase 5: Documentation (30 min)

### Update User-Facing Docs

**File:** `/docs/user-guides/first-scan.md`

Add section:

```markdown
## Understanding Initialization

When you run your first scan, RAXE performs one-time initialization:

```bash
$ raxe scan "test"
┌─────────────────────────────────────────────────────┐
│ 🔧 Initializing RAXE...                             │
│   ✓ Loaded 460 rules (633ms)                        │
│   ✓ Loaded ML model (2,150ms)                       │
│   ✓ Components ready (150ms)                        │
│ ✓ Ready to scan (Total: 2,933ms, one-time)         │
└─────────────────────────────────────────────────────┘
```

**This initialization is one-time per session.** Subsequent scans are fast (<10ms).

### What's Happening

1. **Loading Rules** (~600ms): Detection patterns are loaded from rule packs
2. **Loading ML Model** (~2,000ms): Machine learning model for L2 detection
3. **Warming Up** (~150ms): Components are tested and caches warmed

### CI/CD Usage

In automated environments, progress is simplified:

```bash
[2025-11-20 10:30:15] Initializing RAXE...
[2025-11-20 10:30:17] Initialization complete (2933ms, one-time)
{
  "has_detections": false,
  "duration_ms": 5
}
```

For completely silent operation, use `--quiet`:

```bash
raxe --quiet scan "$PROMPT"
```
```

---

## Troubleshooting

### Issue: Progress doesn't appear

**Symptoms:** No progress shown, silent 3-5 second pause

**Diagnosis:**
```python
# Add debug logging
import sys
print(f"TTY: {sys.stdout.isatty()}", file=sys.stderr)
print(f"TERM: {os.getenv('TERM')}", file=sys.stderr)

from raxe.cli.progress_context import detect_progress_mode
mode = detect_progress_mode(quiet=False, verbose=False, no_color=False)
print(f"Progress mode: {mode}", file=sys.stderr)
```

**Solutions:**
- Check if running in TTY: `python -c "import sys; print(sys.stdout.isatty())"`
- Force interactive mode: `export TERM=xterm-256color`
- Test with verbose: `raxe --verbose scan "test"`

---

### Issue: ANSI codes in CI/CD logs

**Symptoms:** Log files contain `\x1b[` escape sequences

**Diagnosis:**
```bash
cat log.txt | grep -o '\x1b\['
```

**Solutions:**
- Set `NO_COLOR=1` environment variable
- Use `--no-color` flag: `raxe --no-color scan "test"`
- Check TTY detection: Should auto-detect non-TTY

---

### Issue: Transient progress doesn't clear

**Symptoms:** Progress box remains after initialization

**Diagnosis:**
- Check terminal supports ANSI cursor movement
- Test: `printf "\x1b[5A\x1b[0J"` (should clear 5 lines)

**Solutions:**
- Use verbose mode (progress intentionally stays): `--verbose`
- Check Rich library version: `pip show rich`
- Disable transient: Set `RAXE_SIMPLE_PROGRESS=1`

---

## Performance Checklist

- [ ] Progress rendering overhead <1ms per update
- [ ] No impact on initialization timing (3-5 seconds acceptable)
- [ ] Transient clear takes <10ms
- [ ] Spinner animates smoothly (10 FPS, no dropped frames)
- [ ] Memory usage <15 KB for progress state

---

## Acceptance Criteria

**Must Have (Ship Blocker):**
- ✅ No silent 3-5 second pause
- ✅ Clear progress in interactive terminals
- ✅ Plain text in CI/CD (no ANSI codes)
- ✅ Quiet mode completely silent
- ✅ "(one-time)" messaging shown
- ✅ Graceful error handling

**Should Have (High Priority):**
- ✅ Animated spinners in interactive mode
- ✅ Transient progress (clears after completion)
- ✅ Component-level timing
- ✅ Verbose mode with details

**Nice to Have (Future Enhancement):**
- ⬜ Download progress for models
- ⬜ Parallel component visualization
- ⬜ ETA for long operations

---

## Implementation Checklist

**Phase 1: Core Component**
- [ ] Create `/src/raxe/cli/progress.py`
- [ ] Implement `ProgressIndicator` base class
- [ ] Implement `InteractiveProgress`
- [ ] Implement `SimpleProgress`
- [ ] Implement `QuietProgress`
- [ ] Implement `NullProgress`
- [ ] Create factory function

**Phase 2: Context Detection**
- [ ] Create `/src/raxe/cli/progress_context.py`
- [ ] Implement `detect_progress_mode()`
- [ ] Implement `supports_unicode()`
- [ ] Implement `supports_animation()`

**Phase 3: Integration**
- [ ] Modify `/src/raxe/cli/main.py` scan command
- [ ] Modify `/src/raxe/sdk/client.py` __init__
- [ ] Modify `/src/raxe/application/preloader.py`
- [ ] Update all progress callsites

**Phase 4: Testing**
- [ ] Create `/tests/cli/test_progress.py`
- [ ] Create `/tests/cli/test_scan_progress.py`
- [ ] Run unit tests (pytest tests/cli/test_progress.py)
- [ ] Run integration tests
- [ ] Manual testing checklist

**Phase 5: Documentation**
- [ ] Update user guide
- [ ] Add troubleshooting section
- [ ] Document environment variables
- [ ] Update README with examples

**Ready to Ship:**
- [ ] All tests passing
- [ ] Code review approved
- [ ] Documentation complete
- [ ] Manual testing complete

---

## Questions for Product Owner

1. **Timing Display**: Should we show component timing in all modes, or only verbose?
   - **Recommendation**: Show in interactive (builds trust), hide in CI/CD (reduces noise)

2. **Model Download Progress**: Should we add progress for model downloads?
   - **Recommendation**: Phase 2 feature (not critical for MVP)

3. **Customization**: Should users be able to customize progress messages?
   - **Recommendation**: Not for MVP (adds complexity)

4. **Telemetry**: Should we track initialization timing in telemetry?
   - **Recommendation**: Yes (helps identify performance issues)

---

**Document Status:** ✅ Ready for Implementation
**Estimated Time:** 4-6 hours
**Priority:** High (User-facing UX issue)
**Dependencies:** None (uses existing Rich library)
