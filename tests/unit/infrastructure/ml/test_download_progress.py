"""Tests for ML model download progress indicators.

These tests verify the UX for model downloads across different environments:
- Interactive terminals: Rich progress bars
- CI/CD pipelines: Timestamped log lines
- SDK usage: Minimal progress output
- Quiet mode: Silent (errors only)
"""

import io
import os
import sys
from unittest.mock import patch

from raxe.infrastructure.ml.download_progress import (
    MinimalDownloadProgress,
    QuietDownloadProgress,
    RichDownloadProgress,
    SimpleDownloadProgress,
    create_download_progress,
    detect_download_progress_mode,
)


class TestProgressModeDetection:
    """Test automatic progress mode detection based on environment."""

    def test_quiet_mode_via_env_var(self):
        """RAXE_QUIET=1 should trigger quiet mode."""
        with patch.dict(os.environ, {"RAXE_QUIET": "1"}):
            assert detect_download_progress_mode() == "quiet"

    def test_simple_mode_for_non_tty(self):
        """Non-TTY stderr should trigger simple mode."""
        with patch.object(sys.stderr, "isatty", return_value=False):
            # Clear RAXE_QUIET if set
            with patch.dict(os.environ, {"RAXE_QUIET": ""}, clear=False):
                os.environ.pop("RAXE_QUIET", None)
                assert detect_download_progress_mode() == "simple"

    def test_simple_mode_via_env_var(self):
        """RAXE_SIMPLE_PROGRESS=1 should trigger simple mode."""
        with patch.object(sys.stderr, "isatty", return_value=True):
            with patch.dict(os.environ, {"RAXE_SIMPLE_PROGRESS": "1", "RAXE_QUIET": ""}):
                os.environ.pop("RAXE_QUIET", None)
                assert detect_download_progress_mode() == "simple"

    def test_simple_mode_for_dumb_terminal(self):
        """TERM=dumb should trigger simple mode."""
        with patch.object(sys.stderr, "isatty", return_value=True):
            with patch.dict(
                os.environ, {"TERM": "dumb", "RAXE_QUIET": "", "RAXE_SIMPLE_PROGRESS": ""}
            ):
                os.environ.pop("RAXE_QUIET", None)
                os.environ.pop("RAXE_SIMPLE_PROGRESS", None)
                assert detect_download_progress_mode() == "simple"

    def test_rich_mode_for_interactive_terminal(self):
        """Interactive terminal should get rich mode."""
        with patch.object(sys.stderr, "isatty", return_value=True):
            with patch.dict(
                os.environ, {"TERM": "xterm-256color", "RAXE_QUIET": "", "RAXE_SIMPLE_PROGRESS": ""}
            ):
                os.environ.pop("RAXE_QUIET", None)
                os.environ.pop("RAXE_SIMPLE_PROGRESS", None)
                assert detect_download_progress_mode() == "rich"


class TestProgressFactory:
    """Test progress indicator factory."""

    def test_create_rich_progress(self):
        """Factory should create RichDownloadProgress for 'rich' mode."""
        progress = create_download_progress(mode="rich")
        assert isinstance(progress, RichDownloadProgress)

    def test_create_simple_progress(self):
        """Factory should create SimpleDownloadProgress for 'simple' mode."""
        progress = create_download_progress(mode="simple")
        assert isinstance(progress, SimpleDownloadProgress)

    def test_create_minimal_progress(self):
        """Factory should create MinimalDownloadProgress for 'minimal' mode."""
        progress = create_download_progress(mode="minimal")
        assert isinstance(progress, MinimalDownloadProgress)

    def test_create_quiet_progress(self):
        """Factory should create QuietDownloadProgress for 'quiet' mode."""
        progress = create_download_progress(mode="quiet")
        assert isinstance(progress, QuietDownloadProgress)

    def test_force_mode_overrides_detection(self):
        """force_mode should override auto-detection."""
        with patch.dict(os.environ, {"RAXE_QUIET": "1"}):
            progress = create_download_progress(force_mode="rich")
            assert isinstance(progress, RichDownloadProgress)


class TestSimpleDownloadProgress:
    """Test SimpleDownloadProgress for CI/CD environments."""

    def test_start_shows_model_name_and_size(self):
        """Start should show model name and size in MB."""
        stderr = io.StringIO()
        with patch.object(sys, "stderr", stderr):
            progress = SimpleDownloadProgress()
            progress.start("Threat Classifier INT8", 107 * 1024 * 1024)

        output = stderr.getvalue()
        assert "Threat Classifier INT8" in output
        assert "107MB" in output

    def test_updates_at_10_percent_intervals(self):
        """Progress should report at 10% intervals."""
        stderr = io.StringIO()
        with patch.object(sys, "stderr", stderr):
            progress = SimpleDownloadProgress()
            progress.start("Test Model", 100000)

            # These should trigger updates
            progress.update(10000, 100000)  # 10%
            progress.update(20000, 100000)  # 20%
            progress.update(25000, 100000)  # 25% - no update (not at 30%)
            progress.update(30000, 100000)  # 30%

        output = stderr.getvalue()
        assert "10%" in output
        assert "20%" in output
        assert "30%" in output

    def test_complete_shows_duration(self):
        """Complete should show download duration."""
        stderr = io.StringIO()
        with patch.object(sys, "stderr", stderr):
            progress = SimpleDownloadProgress()
            progress._start_time = 100.0
            with patch("time.time", return_value=105.0):
                progress.complete()

        output = stderr.getvalue()
        assert "complete" in output.lower()
        assert "5.0s" in output

    def test_error_shows_message(self):
        """Error should show error message."""
        stderr = io.StringIO()
        with patch.object(sys, "stderr", stderr):
            progress = SimpleDownloadProgress()
            progress.error("Network timeout")

        output = stderr.getvalue()
        assert "Network timeout" in output
        assert "L1 detection" in output  # Fallback message


class TestMinimalDownloadProgress:
    """Test MinimalDownloadProgress for SDK usage."""

    def test_start_shows_raxe_prefix(self):
        """Start message should have [RAXE] prefix."""
        stderr = io.StringIO()
        with patch.object(sys, "stderr", stderr):
            progress = MinimalDownloadProgress()
            progress.start("Test Model", 107 * 1024 * 1024)

        output = stderr.getvalue()
        assert "[RAXE]" in output
        assert "107MB" in output

    def test_updates_throttled_to_500ms(self):
        """Updates should be throttled to every 0.5 seconds."""
        stderr = io.StringIO()
        with patch.object(sys, "stderr", stderr):
            progress = MinimalDownloadProgress()
            progress.start("Test Model", 100000)

            # First update should show
            progress._last_update = 0
            progress.update(50000, 100000)

            # Immediate second update should be throttled
            progress.update(60000, 100000)

        output = stderr.getvalue()
        # Should only have one progress update line (plus start)
        progress_lines = [l for l in output.split("\n") if "Progress:" in l]
        assert len(progress_lines) == 1

    def test_complete_shows_raxe_prefix(self):
        """Complete message should have [RAXE] prefix."""
        stderr = io.StringIO()
        with patch.object(sys, "stderr", stderr):
            progress = MinimalDownloadProgress()
            progress._start_time = 100.0
            with patch("time.time", return_value=130.0):
                progress.complete()

        output = stderr.getvalue()
        assert "[RAXE]" in output
        assert "30.0s" in output


class TestQuietDownloadProgress:
    """Test QuietDownloadProgress for --quiet mode."""

    def test_start_is_silent(self):
        """Start should produce no output."""
        stderr = io.StringIO()
        with patch.object(sys, "stderr", stderr):
            progress = QuietDownloadProgress()
            progress.start("Test Model", 100000)

        assert stderr.getvalue() == ""

    def test_update_is_silent(self):
        """Update should produce no output."""
        stderr = io.StringIO()
        with patch.object(sys, "stderr", stderr):
            progress = QuietDownloadProgress()
            progress.update(50000, 100000)

        assert stderr.getvalue() == ""

    def test_complete_is_silent(self):
        """Complete should produce no output."""
        stderr = io.StringIO()
        with patch.object(sys, "stderr", stderr):
            progress = QuietDownloadProgress()
            progress.complete()

        assert stderr.getvalue() == ""

    def test_error_shows_message(self):
        """Even quiet mode should show errors."""
        stderr = io.StringIO()
        with patch.object(sys, "stderr", stderr):
            progress = QuietDownloadProgress()
            progress.error("Download failed")

        output = stderr.getvalue()
        assert "Download failed" in output


class TestProgressCallback:
    """Test progress callback integration."""

    def test_get_callback_returns_callable(self):
        """get_callback should return a callable."""
        progress = SimpleDownloadProgress()
        callback = progress.get_callback()
        assert callable(callback)

    def test_callback_calls_update(self):
        """Callback should call update method."""
        stderr = io.StringIO()
        with patch.object(sys, "stderr", stderr):
            progress = SimpleDownloadProgress()
            progress.start("Test", 100000)
            callback = progress.get_callback()

            # Call callback like downloader would
            callback(10000, 100000)

        output = stderr.getvalue()
        assert "10%" in output
