"""Unit tests for progress context detection."""

import os
import sys
from unittest.mock import patch

from raxe.cli.progress_context import (
    detect_progress_mode,
    supports_animation,
    supports_unicode,
)


def test_detect_progress_quiet_flag():
    """Test --quiet flag forces quiet mode."""
    mode = detect_progress_mode(quiet=True)
    assert mode == "quiet"


def test_detect_progress_quiet_env():
    """Test RAXE_QUIET env var forces quiet mode."""
    with patch.dict(os.environ, {"RAXE_QUIET": "1"}):
        mode = detect_progress_mode(quiet=False)
        assert mode == "quiet"


def test_detect_progress_non_tty():
    """Test non-TTY forces simple mode."""
    # Mock isatty to return False
    with patch.object(sys.stdout, "isatty", return_value=False):
        mode = detect_progress_mode()
        assert mode == "simple"


def test_detect_progress_dumb_terminal():
    """Test dumb terminal forces simple mode."""
    with patch.dict(os.environ, {"TERM": "dumb"}):
        mode = detect_progress_mode()
        assert mode == "simple"


def test_detect_progress_no_color_flag():
    """Test --no-color flag forces simple mode."""
    mode = detect_progress_mode(no_color=True)
    assert mode == "simple"


def test_detect_progress_no_color_env():
    """Test NO_COLOR env var forces simple mode."""
    with patch.dict(os.environ, {"NO_COLOR": "1"}):
        mode = detect_progress_mode()
        assert mode == "simple"


def test_detect_progress_raxe_no_color():
    """Test RAXE_NO_COLOR env var forces simple mode."""
    with patch.dict(os.environ, {"RAXE_NO_COLOR": "1"}):
        mode = detect_progress_mode()
        assert mode == "simple"


def test_detect_progress_simple_mode_env():
    """Test RAXE_SIMPLE_PROGRESS env var forces simple mode."""
    with patch.dict(os.environ, {"RAXE_SIMPLE_PROGRESS": "1"}):
        mode = detect_progress_mode()
        assert mode == "simple"


def test_supports_unicode_utf8():
    """Test UTF-8 encoding supports unicode."""

    # Create a mock stdout with utf-8 encoding
    class MockStdout:
        encoding = "utf-8"

    with patch.object(sys, "stdout", MockStdout()):
        assert supports_unicode() is True


def test_supports_unicode_ascii_only():
    """Test RAXE_ASCII_ONLY disables unicode."""
    with patch.dict(os.environ, {"RAXE_ASCII_ONLY": "1"}):
        assert supports_unicode() is False


def test_supports_animation_accessible_mode():
    """Test RAXE_ACCESSIBLE_MODE disables animation."""
    with patch.dict(os.environ, {"RAXE_ACCESSIBLE_MODE": "1"}):
        assert supports_animation() is False


def test_supports_animation_no_animation():
    """Test RAXE_NO_ANIMATION disables animation."""
    with patch.dict(os.environ, {"RAXE_NO_ANIMATION": "1"}):
        assert supports_animation() is False


def test_supports_animation_non_tty():
    """Test non-TTY disables animation."""
    with patch.object(sys.stdout, "isatty", return_value=False):
        assert supports_animation() is False


def test_priority_quiet_overrides_all():
    """Test quiet flag has highest priority."""
    # Even with TTY and colors, quiet should win
    with patch.object(sys.stdout, "isatty", return_value=True):
        mode = detect_progress_mode(quiet=True, no_color=False)
        assert mode == "quiet"


def test_priority_no_color_overrides_tty():
    """Test no_color overrides TTY detection."""
    with patch.object(sys.stdout, "isatty", return_value=True):
        mode = detect_progress_mode(quiet=False, no_color=True)
        assert mode == "simple"
