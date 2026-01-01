"""Tests for auth progress display module.

Tests the visual progress display for CLI authentication including:
- AuthState enum and transitions
- AuthProgress dataclass calculations
- Progress bar rendering
- State-based help messages
- Spinner animation
"""

from io import StringIO

from rich.console import Console

from raxe.cli.auth_progress import (
    CRITICAL_THRESHOLD_PCT,
    HELP_THRESHOLD_PCT,
    WARNING_THRESHOLD_PCT,
    AuthProgress,
    AuthState,
    render_auth_progress,
    render_cancelled_message,
    render_timeout_message,
)


class TestAuthState:
    """Test suite for AuthState enum."""

    def test_all_states_exist(self):
        """Test that all expected states are defined."""
        expected_states = [
            "INITIAL",
            "WAITING",
            "HELP",
            "WARNING",
            "CRITICAL",
            "SUCCESS",
            "TIMEOUT",
            "EXPIRED",
            "ERROR",
            "NETWORK_ISSUE",
        ]
        for state in expected_states:
            assert hasattr(AuthState, state)

    def test_state_values_are_strings(self):
        """Test that state values are lowercase strings."""
        for state in AuthState:
            assert isinstance(state.value, str)
            assert state.value == state.value.lower()


class TestAuthProgress:
    """Test suite for AuthProgress dataclass."""

    def test_default_values(self):
        """Test default AuthProgress values."""
        progress = AuthProgress()

        assert progress.connect_url == ""
        assert progress.total_seconds == 300.0
        assert progress.elapsed_seconds == 0.0
        assert progress.state == AuthState.INITIAL
        assert progress.error_message == ""
        assert progress.help_shown is False

    def test_remaining_seconds_calculation(self):
        """Test remaining seconds calculation."""
        progress = AuthProgress(total_seconds=300.0, elapsed_seconds=100.0)

        assert progress.remaining_seconds == 200.0

    def test_remaining_seconds_never_negative(self):
        """Test remaining seconds never goes negative."""
        progress = AuthProgress(total_seconds=300.0, elapsed_seconds=400.0)

        assert progress.remaining_seconds == 0.0

    def test_progress_percent_calculation(self):
        """Test progress percentage calculation."""
        progress = AuthProgress(total_seconds=300.0, elapsed_seconds=150.0)

        assert progress.progress_percent == 50.0

    def test_progress_percent_capped_at_100(self):
        """Test progress percentage caps at 100."""
        progress = AuthProgress(total_seconds=300.0, elapsed_seconds=400.0)

        assert progress.progress_percent == 100.0

    def test_remaining_formatted(self):
        """Test formatted time remaining."""
        progress = AuthProgress(total_seconds=300.0, elapsed_seconds=45.0)

        assert progress.remaining_formatted == "4:15"  # 255 seconds = 4:15

    def test_remaining_formatted_under_minute(self):
        """Test formatted time remaining under one minute."""
        progress = AuthProgress(total_seconds=300.0, elapsed_seconds=270.0)

        assert progress.remaining_formatted == "0:30"  # 30 seconds


class TestAuthProgressStateTransitions:
    """Test suite for AuthProgress state transitions."""

    def test_initial_state_at_start(self):
        """Test initial state at 0% progress."""
        progress = AuthProgress()
        progress.update_elapsed(0)

        assert progress.state == AuthState.INITIAL

    def test_initial_state_under_10_percent(self):
        """Test still in initial state under 10%."""
        progress = AuthProgress(total_seconds=300.0)
        progress.update_elapsed(20)  # ~7%

        assert progress.state == AuthState.INITIAL

    def test_waiting_state_after_10_percent(self):
        """Test transition to waiting state after 10%."""
        progress = AuthProgress(total_seconds=300.0)
        progress.update_elapsed(35)  # ~12%

        assert progress.state == AuthState.WAITING

    def test_help_state_at_50_percent(self):
        """Test transition to help state at 50%."""
        progress = AuthProgress(total_seconds=300.0)
        progress.update_elapsed(150)  # 50%

        assert progress.state == AuthState.HELP

    def test_warning_state_at_75_percent(self):
        """Test transition to warning state at 75%."""
        progress = AuthProgress(total_seconds=300.0)
        progress.update_elapsed(225)  # 75%

        assert progress.state == AuthState.WARNING

    def test_critical_state_at_90_percent(self):
        """Test transition to critical state at 90%."""
        progress = AuthProgress(total_seconds=300.0)
        progress.update_elapsed(270)  # 90%

        assert progress.state == AuthState.CRITICAL

    def test_success_state_not_overridden(self):
        """Test that success state is not overridden by time update."""
        progress = AuthProgress(total_seconds=300.0)
        progress.set_success()
        progress.update_elapsed(150)

        assert progress.state == AuthState.SUCCESS

    def test_error_state_not_overridden(self):
        """Test that error state is not overridden by time update."""
        progress = AuthProgress(total_seconds=300.0)
        progress.set_error("Test error")
        progress.update_elapsed(150)

        assert progress.state == AuthState.ERROR
        assert progress.error_message == "Test error"

    def test_network_issue_set_and_clear(self):
        """Test network issue state can be set and cleared."""
        progress = AuthProgress(total_seconds=300.0)
        progress.update_elapsed(150)  # Should be HELP state

        progress.set_network_issue()
        assert progress.state == AuthState.NETWORK_ISSUE

        progress.clear_network_issue()
        # After clearing, state should be recalculated based on time
        assert progress.state == AuthState.HELP


class TestThresholdConstants:
    """Test suite for threshold constants."""

    def test_help_threshold_is_50_percent(self):
        """Test help threshold is at 50%."""
        assert HELP_THRESHOLD_PCT == 50

    def test_warning_threshold_is_75_percent(self):
        """Test warning threshold is at 75%."""
        assert WARNING_THRESHOLD_PCT == 75

    def test_critical_threshold_is_90_percent(self):
        """Test critical threshold is at 90%."""
        assert CRITICAL_THRESHOLD_PCT == 90


class TestSpinnerAnimation:
    """Test suite for spinner animation."""

    def test_spinner_frame_returns_string(self):
        """Test that spinner frame returns a character."""
        progress = AuthProgress()
        frame = progress.get_spinner_frame()

        assert isinstance(frame, str)
        assert len(frame) == 1

    def test_warning_state_uses_exclamation(self):
        """Test warning state uses exclamation spinner."""
        progress = AuthProgress(total_seconds=300.0)
        progress.update_elapsed(225)  # 75% - WARNING

        frame = progress.get_spinner_frame()
        assert frame == "!"

    def test_critical_state_uses_exclamation(self):
        """Test critical state uses exclamation spinner."""
        progress = AuthProgress(total_seconds=300.0)
        progress.update_elapsed(270)  # 90% - CRITICAL

        frame = progress.get_spinner_frame()
        assert frame == "!"

    def test_network_issue_uses_tilde(self):
        """Test network issue uses tilde spinner."""
        progress = AuthProgress()
        progress.set_network_issue()

        frame = progress.get_spinner_frame()
        assert frame == "~"


class TestRenderAuthProgress:
    """Test suite for render_auth_progress function."""

    def test_renders_panel(self):
        """Test that render returns a Panel."""
        from rich.panel import Panel

        progress = AuthProgress(connect_url="https://test.raxe.ai/connect")
        result = render_auth_progress(progress)

        assert isinstance(result, Panel)

    def test_initial_state_renders(self):
        """Test rendering in initial state."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        progress = AuthProgress(connect_url="https://test.raxe.ai/connect")
        panel = render_auth_progress(progress)
        console.print(panel)

        rendered = output.getvalue()
        assert "Waiting for browser authentication" in rendered
        assert "5:00" in rendered  # Full 5 minutes remaining

    def test_help_state_shows_troubleshooting(self):
        """Test that help state shows troubleshooting info."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        progress = AuthProgress(
            connect_url="https://test.raxe.ai/connect",
            total_seconds=300.0,
        )
        progress.update_elapsed(150)  # 50% - HELP state
        panel = render_auth_progress(progress)
        console.print(panel)

        rendered = output.getvalue()
        assert "Taking a while?" in rendered
        assert "Browser didn't open?" in rendered

    def test_warning_state_shows_time_warning(self):
        """Test that warning state shows time warning."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        progress = AuthProgress(total_seconds=300.0)
        progress.update_elapsed(225)  # 75% - WARNING state
        panel = render_auth_progress(progress)
        console.print(panel)

        rendered = output.getvalue()
        assert "Running low on time!" in rendered

    def test_critical_state_shows_urgent_message(self):
        """Test that critical state shows urgent message."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        progress = AuthProgress(total_seconds=300.0)
        progress.update_elapsed(270)  # 90% - CRITICAL state
        panel = render_auth_progress(progress)
        console.print(panel)

        rendered = output.getvalue()
        assert "Almost out of time!" in rendered

    def test_network_issue_shows_retry_message(self):
        """Test that network issue state shows retry message."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        progress = AuthProgress()
        progress.set_network_issue()
        panel = render_auth_progress(progress)
        console.print(panel)

        rendered = output.getvalue()
        assert "Connection issue" in rendered or "Network hiccup" in rendered

    def test_progress_bar_shows_percentage(self):
        """Test that progress bar shows percentage."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        progress = AuthProgress(total_seconds=300.0)
        progress.update_elapsed(60)  # 20%
        panel = render_auth_progress(progress)
        console.print(panel)

        rendered = output.getvalue()
        assert "20%" in rendered


class TestRenderCancelledMessage:
    """Test suite for cancelled message rendering."""

    def test_cancelled_message_contains_auth_command(self):
        """Test cancelled message mentions raxe auth."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        text = render_cancelled_message()
        console.print(text)

        rendered = output.getvalue()
        assert "raxe auth" in rendered

    def test_cancelled_message_contains_manual_option(self):
        """Test cancelled message mentions manual key setup."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        text = render_cancelled_message()
        console.print(text)

        rendered = output.getvalue()
        assert "raxe config set api_key" in rendered


class TestRenderTimeoutMessage:
    """Test suite for timeout message rendering."""

    def test_timeout_message_contains_retry_instructions(self):
        """Test timeout message contains retry instructions."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        text = render_timeout_message()
        console.print(text)

        rendered = output.getvalue()
        assert "raxe auth" in rendered
        assert "5 minutes" in rendered

    def test_timeout_message_contains_manual_fallback(self):
        """Test timeout message contains manual fallback."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        text = render_timeout_message()
        console.print(text)

        rendered = output.getvalue()
        assert "raxe config set api_key" in rendered
        assert "console.raxe.ai/keys" in rendered
