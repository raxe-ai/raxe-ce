"""Unit tests for progress indicators."""

import io
import sys

import pytest

from raxe.cli.progress import (
    InteractiveProgress,
    NullProgress,
    QuietProgress,
    SimpleProgress,
    create_progress_indicator,
)


def test_null_progress_no_output():
    """Test NullProgress produces no output."""
    progress = NullProgress()
    progress.start("test")
    progress.update_component("test", "complete", 100)
    progress.complete(100)
    # Should not crash, should not output anything


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


def test_simple_progress_shows_rules_count():
    """Test SimpleProgress shows rule count in metadata."""
    captured = io.StringIO()
    original_stderr = sys.stderr
    sys.stderr = captured

    progress = SimpleProgress()
    progress.start("Test")
    progress.update_component("rules", "complete", 633, {"count": 460})

    sys.stderr = original_stderr

    output = captured.getvalue()
    assert "460 rules" in output


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


def test_interactive_progress_with_errors():
    """Test InteractiveProgress handles errors gracefully."""
    progress = InteractiveProgress()

    progress.start("Test initialization")
    progress.update_component("rules", "complete", 100, {"count": 460})
    progress.error("ml_model", "Model not found")

    # Should complete without crashes


def test_simple_progress_timestamps():
    """Test SimpleProgress includes timestamps."""
    captured = io.StringIO()
    original_stderr = sys.stderr
    sys.stderr = captured

    progress = SimpleProgress()
    progress.start("Test")

    sys.stderr = original_stderr

    output = captured.getvalue()
    # Should have timestamp format [YYYY-MM-DD HH:MM:SS]
    assert "[" in output
    assert "]" in output
    assert ":" in output  # Time separator


def test_null_progress_all_methods():
    """Test NullProgress implements all required methods."""
    progress = NullProgress()

    # Should not crash on any method
    progress.start("test")
    progress.update_component("rules", "loading", 0)
    progress.update_component("rules", "complete", 100, {"count": 460})
    progress.update_component("rules", "error", 0)
    progress.complete(100)
    progress.error("component", "message")


def test_interactive_progress_handles_unknown_components():
    """Test InteractiveProgress handles unknown component names."""
    progress = InteractiveProgress()

    progress.start("Test")
    # Unknown component should be ignored gracefully
    progress.update_component("unknown_component", "complete", 100)
    progress.complete(100)


def test_simple_progress_error_format():
    """Test SimpleProgress error format."""
    captured = io.StringIO()
    original_stderr = sys.stderr
    sys.stderr = captured

    progress = SimpleProgress()
    progress.error("ml_model", "Failed to load")

    sys.stderr = original_stderr

    output = captured.getvalue()
    assert "ERROR" in output
    assert "ml_model" in output
    assert "Failed to load" in output
