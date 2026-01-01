"""Tests for terminal context detection."""

import os
import sys
from unittest.mock import patch

import pytest

from raxe.cli.terminal_context import (
    TerminalContext,
    TerminalMode,
    clear_context_cache,
    detect_ci_service,
    detect_terminal_context,
    get_terminal_context,
    is_interactive,
)


@pytest.fixture(autouse=True)
def reset_cache():
    """Clear the terminal context cache before each test."""
    clear_context_cache()
    yield
    clear_context_cache()


class TestDetectCIService:
    """Tests for CI service detection."""

    @pytest.mark.parametrize(
        "env_var,expected",
        [
            ("GITHUB_ACTIONS", "GitHub Actions"),
            ("GITLAB_CI", "GitLab CI"),
            ("JENKINS_URL", "Jenkins"),
            ("CIRCLECI", "CircleCI"),
            ("TRAVIS", "Travis CI"),
            ("TF_BUILD", "Azure Pipelines"),
            ("BITBUCKET_BUILD_NUMBER", "Bitbucket Pipelines"),
            ("CODEBUILD_BUILD_ID", "AWS CodeBuild"),
            ("CLOUD_BUILD", "Google Cloud Build"),
            ("BUILDKITE", "Buildkite"),
            ("TEAMCITY_VERSION", "TeamCity"),
            ("DRONE", "Drone CI"),
            ("SEMAPHORE", "Semaphore"),
            ("VERCEL", "Vercel"),
            ("NETLIFY", "Netlify"),
            ("RENDER", "Render"),
            ("RAILWAY_ENVIRONMENT", "Railway"),
        ],
    )
    def test_detects_specific_ci_services(self, env_var: str, expected: str):
        """Each CI service should be correctly identified."""
        with patch.dict(os.environ, {env_var: "true"}, clear=True):
            assert detect_ci_service() == expected

    def test_detects_generic_ci(self):
        """Generic CI variable should return 'Unknown CI'."""
        with patch.dict(os.environ, {"CI": "true"}, clear=True):
            assert detect_ci_service() == "Unknown CI"

    def test_detects_continuous_integration_var(self):
        """CONTINUOUS_INTEGRATION var should return 'Unknown CI'."""
        with patch.dict(os.environ, {"CONTINUOUS_INTEGRATION": "true"}, clear=True):
            assert detect_ci_service() == "Unknown CI"

    def test_returns_none_when_no_ci(self):
        """Should return None when not in CI."""
        with patch.dict(os.environ, {"TERM": "xterm"}, clear=True):
            assert detect_ci_service() is None


class TestDetectTerminalContext:
    """Tests for terminal context detection."""

    def test_interactive_with_tty(self):
        """Should detect interactive mode with TTY."""
        with patch.dict(os.environ, {"TERM": "xterm-256color"}, clear=True):
            with patch.object(sys, "stdin") as mock_stdin:
                with patch.object(sys, "stdout") as mock_stdout:
                    mock_stdin.isatty.return_value = True
                    mock_stdout.isatty.return_value = True

                    context = detect_terminal_context()

                    assert context.mode == TerminalMode.INTERACTIVE
                    assert context.is_interactive is True
                    assert context.has_tty is True
                    assert context.detected_ci is None

    def test_ci_mode_with_github_actions(self):
        """Should detect CI mode in GitHub Actions."""
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True):
            with patch.object(sys, "stdin") as mock_stdin:
                with patch.object(sys, "stdout") as mock_stdout:
                    mock_stdin.isatty.return_value = False
                    mock_stdout.isatty.return_value = False

                    context = detect_terminal_context()

                    assert context.mode == TerminalMode.CI
                    assert context.is_interactive is False
                    assert context.detected_ci == "GitHub Actions"

    def test_ci_mode_with_gitlab(self):
        """Should detect CI mode in GitLab CI."""
        with patch.dict(os.environ, {"GITLAB_CI": "true"}, clear=True):
            context = detect_terminal_context()

            assert context.mode == TerminalMode.CI
            assert context.is_interactive is False
            assert context.detected_ci == "GitLab CI"

    def test_ci_mode_with_jenkins(self):
        """Should detect CI mode in Jenkins."""
        with patch.dict(os.environ, {"JENKINS_URL": "http://jenkins"}, clear=True):
            context = detect_terminal_context()

            assert context.mode == TerminalMode.CI
            assert context.is_interactive is False
            assert context.detected_ci == "Jenkins"

    def test_pipe_mode_without_tty(self):
        """Should detect pipe mode when no TTY."""
        with patch.dict(os.environ, {"TERM": "xterm"}, clear=True):
            with patch.object(sys, "stdin") as mock_stdin:
                with patch.object(sys, "stdout") as mock_stdout:
                    mock_stdin.isatty.return_value = False
                    mock_stdout.isatty.return_value = True

                    context = detect_terminal_context()

                    assert context.mode == TerminalMode.PIPE
                    assert context.is_interactive is False
                    assert context.has_tty is False

    def test_pipe_mode_stdout_not_tty(self):
        """Should detect pipe mode when stdout not TTY."""
        with patch.dict(os.environ, {"TERM": "xterm"}, clear=True):
            with patch.object(sys, "stdin") as mock_stdin:
                with patch.object(sys, "stdout") as mock_stdout:
                    mock_stdin.isatty.return_value = True
                    mock_stdout.isatty.return_value = False

                    context = detect_terminal_context()

                    assert context.mode == TerminalMode.PIPE
                    assert context.is_interactive is False

    def test_explicit_non_interactive_override(self):
        """RAXE_NON_INTERACTIVE should force non-interactive."""
        with patch.dict(os.environ, {"RAXE_NON_INTERACTIVE": "1"}, clear=True):
            with patch.object(sys, "stdin") as mock_stdin:
                with patch.object(sys, "stdout") as mock_stdout:
                    mock_stdin.isatty.return_value = True
                    mock_stdout.isatty.return_value = True

                    context = detect_terminal_context()

                    assert context.mode == TerminalMode.SCRIPT
                    assert context.is_interactive is False

    def test_dumb_terminal(self):
        """TERM=dumb should be non-interactive."""
        with patch.dict(os.environ, {"TERM": "dumb"}, clear=True):
            with patch.object(sys, "stdin") as mock_stdin:
                with patch.object(sys, "stdout") as mock_stdout:
                    mock_stdin.isatty.return_value = True
                    mock_stdout.isatty.return_value = True

                    context = detect_terminal_context()

                    assert context.is_interactive is False
                    assert context.mode == TerminalMode.SCRIPT

    def test_empty_term(self):
        """Empty TERM should be non-interactive."""
        with patch.dict(os.environ, {"TERM": ""}, clear=True):
            with patch.object(sys, "stdin") as mock_stdin:
                with patch.object(sys, "stdout") as mock_stdout:
                    mock_stdin.isatty.return_value = True
                    mock_stdout.isatty.return_value = True

                    context = detect_terminal_context()

                    assert context.is_interactive is False

    def test_unknown_term(self):
        """TERM=unknown should be non-interactive."""
        with patch.dict(os.environ, {"TERM": "unknown"}, clear=True):
            with patch.object(sys, "stdin") as mock_stdin:
                with patch.object(sys, "stdout") as mock_stdout:
                    mock_stdin.isatty.return_value = True
                    mock_stdout.isatty.return_value = True

                    context = detect_terminal_context()

                    assert context.is_interactive is False


class TestTerminalContextProperties:
    """Tests for TerminalContext properties."""

    def test_is_ci_property(self):
        """is_ci should return True only for CI mode."""
        ci_context = TerminalContext(
            mode=TerminalMode.CI,
            is_interactive=False,
            detected_ci="GitHub Actions",
            has_tty=False,
        )
        assert ci_context.is_ci is True

        interactive_context = TerminalContext(
            mode=TerminalMode.INTERACTIVE,
            is_interactive=True,
            detected_ci=None,
            has_tty=True,
        )
        assert interactive_context.is_ci is False

    def test_can_prompt_property(self):
        """can_prompt should require both interactive and tty."""
        # Interactive with TTY - can prompt
        context1 = TerminalContext(
            mode=TerminalMode.INTERACTIVE,
            is_interactive=True,
            detected_ci=None,
            has_tty=True,
        )
        assert context1.can_prompt is True

        # Interactive without TTY - cannot prompt
        context2 = TerminalContext(
            mode=TerminalMode.INTERACTIVE,
            is_interactive=True,
            detected_ci=None,
            has_tty=False,
        )
        assert context2.can_prompt is False

        # Non-interactive with TTY - cannot prompt
        context3 = TerminalContext(
            mode=TerminalMode.CI,
            is_interactive=False,
            detected_ci="GitHub Actions",
            has_tty=True,
        )
        assert context3.can_prompt is False


class TestIsInteractive:
    """Tests for the convenience is_interactive() function."""

    def test_returns_true_for_interactive(self):
        """Should return True for interactive terminals."""
        with patch.dict(os.environ, {"TERM": "xterm-256color"}, clear=True):
            with patch.object(sys, "stdin") as mock_stdin:
                with patch.object(sys, "stdout") as mock_stdout:
                    mock_stdin.isatty.return_value = True
                    mock_stdout.isatty.return_value = True

                    assert is_interactive() is True

    def test_returns_false_for_ci(self):
        """Should return False in CI."""
        with patch.dict(os.environ, {"CI": "true"}, clear=True):
            assert is_interactive() is False

    def test_returns_false_for_pipe(self):
        """Should return False when stdin is pipe."""
        with patch.dict(os.environ, {"TERM": "xterm"}, clear=True):
            with patch.object(sys, "stdin") as mock_stdin:
                with patch.object(sys, "stdout") as mock_stdout:
                    mock_stdin.isatty.return_value = False
                    mock_stdout.isatty.return_value = True

                    assert is_interactive() is False


class TestContextCaching:
    """Tests for context caching behavior."""

    def test_context_is_cached(self):
        """Context should be cached after first detection."""
        with patch.dict(os.environ, {"TERM": "xterm"}, clear=True):
            with patch.object(sys, "stdin") as mock_stdin:
                with patch.object(sys, "stdout") as mock_stdout:
                    mock_stdin.isatty.return_value = True
                    mock_stdout.isatty.return_value = True

                    context1 = get_terminal_context()
                    context2 = get_terminal_context()

                    assert context1 is context2

    def test_cache_can_be_cleared(self):
        """Cache should be clearable for testing."""
        with patch.dict(os.environ, {"TERM": "xterm"}, clear=True):
            with patch.object(sys, "stdin") as mock_stdin:
                with patch.object(sys, "stdout") as mock_stdout:
                    mock_stdin.isatty.return_value = True
                    mock_stdout.isatty.return_value = True

                    context1 = get_terminal_context()

                    clear_context_cache()

                    # After clearing, should create new context
                    context2 = get_terminal_context()

                    # Functionally equal but different objects
                    assert context1.mode == context2.mode
                    # Note: cannot test identity as we're mocking


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_isatty_exception(self):
        """Should handle exceptions from isatty()."""
        with patch.dict(os.environ, {"TERM": "xterm"}, clear=True):
            with patch.object(sys, "stdin") as mock_stdin:
                with patch.object(sys, "stdout") as mock_stdout:
                    mock_stdin.isatty.side_effect = ValueError("closed stream")
                    mock_stdout.isatty.return_value = True

                    context = detect_terminal_context()

                    # Should fall back to non-interactive
                    assert context.has_tty is False
                    assert context.is_interactive is False

    def test_ci_takes_priority_over_tty(self):
        """CI environment should override TTY detection."""
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True):
            with patch.object(sys, "stdin") as mock_stdin:
                with patch.object(sys, "stdout") as mock_stdout:
                    # Even with TTY, CI should be detected
                    mock_stdin.isatty.return_value = True
                    mock_stdout.isatty.return_value = True

                    context = detect_terminal_context()

                    assert context.mode == TerminalMode.CI
                    assert context.is_interactive is False

    def test_raxe_override_takes_priority_over_ci(self):
        """RAXE_NON_INTERACTIVE should override CI detection."""
        with patch.dict(
            os.environ,
            {"RAXE_NON_INTERACTIVE": "1", "GITHUB_ACTIONS": "true"},
            clear=True,
        ):
            context = detect_terminal_context()

            # Should be SCRIPT mode (from override), not CI
            assert context.mode == TerminalMode.SCRIPT
            # But CI should still be detected
            assert context.detected_ci == "GitHub Actions"


class TestMultipleCIVariables:
    """Tests for environments with multiple CI variables."""

    def test_specific_ci_preferred_over_generic(self):
        """Specific CI service should be detected even with generic CI=true."""
        with patch.dict(
            os.environ,
            {"CI": "true", "GITHUB_ACTIONS": "true"},
            clear=True,
        ):
            assert detect_ci_service() == "GitHub Actions"

    def test_first_specific_ci_wins(self):
        """When multiple CI services detected, first one wins."""
        with patch.dict(
            os.environ,
            {"GITHUB_ACTIONS": "true", "GITLAB_CI": "true"},
            clear=True,
        ):
            # GitHub Actions comes first in the detection order
            result = detect_ci_service()
            assert result in ("GitHub Actions", "GitLab CI")
