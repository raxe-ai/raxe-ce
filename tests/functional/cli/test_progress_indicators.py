"""Test CLI progress indicators in different environments."""
import os
import subprocess
import sys
import time

import pytest


class TestCLIProgressIndicators:
    """Test progress indicators in TTY and non-TTY environments."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.raxe_cmd = [sys.executable, "-m", "raxe.cli.main"]

    def test_tty_progress_indicators(self, safe_prompts):
        """Test progress indicators in TTY environment."""
        # Simulate TTY environment
        env = {**os.environ, "TERM": "xterm", "COLUMNS": "80"}

        result = subprocess.run(
            [*self.raxe_cmd, "scan", safe_prompts[0]],
            capture_output=True,
            text=True,
            env=env
        )

        assert result.returncode == 0
        # Should show some progress indication (spinners, bars, etc.)
        # Note: Actual progress indicators might be cleared, so check stderr
        if result.stderr:
            assert any(c in result.stderr for c in ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏", "✓", "✗", "..."])

    def test_non_tty_progress_indicators(self, safe_prompts):
        """Test progress indicators in non-TTY environment (CI/CD)."""
        # Simulate non-TTY environment
        env = {**os.environ}
        env.pop("TERM", None)

        # Use pipe to ensure non-TTY
        process = subprocess.Popen(
            [*self.raxe_cmd, "scan", safe_prompts[0]],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        stdout, stderr = process.communicate()

        assert process.returncode == 0
        # Should not show animated progress in non-TTY
        assert not any(c in stdout + stderr for c in ["⠋", "⠙", "⠹", "⠸"])

    def test_quiet_mode_no_progress(self, safe_prompts):
        """Test quiet mode suppresses all progress indicators."""
        result = subprocess.run(
            [*self.raxe_cmd, "--quiet", "scan", safe_prompts[0]],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        # Should have no progress indicators
        assert not any(c in result.stdout + result.stderr for c in ["⠋", "⠙", "⠹", "⠸", "...", "Initializing"])

    def test_initialization_progress(self, safe_prompts):
        """Test initialization progress is shown on first run."""
        # Clear any cached initialization
        env = {**os.environ, "RAXE_NO_CACHE": "true"}

        result = subprocess.run(
            [*self.raxe_cmd, "scan", safe_prompts[0]],
            capture_output=True,
            text=True,
            env=env
        )

        assert result.returncode == 0
        # Should show initialization message
        output = result.stdout + result.stderr
        assert any(word in output.lower() for word in ["initializ", "loading", "starting"])

    def test_progress_with_multiple_prompts(self, safe_prompts):
        """Test progress indicators with multiple prompts."""
        prompts = safe_prompts[:5]

        result = subprocess.run(
            [*self.raxe_cmd, "scan", *prompts],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        # Should show progress for multiple prompts
        output = result.stdout
        # Should show count or progress
        assert any(str(i) in output for i in range(1, 6))

    def test_progress_context_awareness(self, safe_prompts, threat_prompts):
        """Test progress indicators adapt to context."""
        # Test with safe prompt
        result_safe = subprocess.run(
            [*self.raxe_cmd, "scan", safe_prompts[0]],
            capture_output=True,
            text=True
        )

        # Test with threat prompt
        result_threat = subprocess.run(
            [*self.raxe_cmd, "scan", threat_prompts[0]],
            capture_output=True,
            text=True
        )

        # Should show different indicators for safe vs threat
        assert result_safe.returncode == 0
        assert result_threat.returncode == 1

        # Check for different visual indicators
        safe_output = result_safe.stdout + result_safe.stderr
        threat_output = result_threat.stdout + result_threat.stderr

        # Safe should have positive indicator
        assert any(c in safe_output for c in ["✓", "safe", "ok", "passed"])
        # Threat should have warning indicator
        assert any(c in threat_output for c in ["✗", "threat", "danger", "blocked", "⚠️", "🚨"])

    @pytest.mark.slow
    def test_long_running_progress(self, safe_prompts):
        """Test progress indicators for long-running operations."""
        # Create a very long prompt to simulate longer processing
        long_prompt = safe_prompts[0] * 100

        start_time = time.time()
        result = subprocess.run(
            [*self.raxe_cmd, "scan", long_prompt],
            capture_output=True,
            text=True,
            timeout=10
        )
        duration = time.time() - start_time

        assert result.returncode == 0
        # Even with long prompt, should complete quickly
        assert duration < 5, f"Long prompt took {duration}s"

    def test_progress_in_docker_environment(self, safe_prompts):
        """Test progress indicators work in container environment."""
        # Simulate Docker environment
        env = {**os.environ, "DOCKER_CONTAINER": "true", "CI": "true"}

        result = subprocess.run(
            [*self.raxe_cmd, "scan", safe_prompts[0]],
            capture_output=True,
            text=True,
            env=env
        )

        assert result.returncode == 0
        # Should adapt to container environment (no fancy progress)
        assert not any(c in result.stdout + result.stderr for c in ["⠋", "⠙", "⠹"])

    def test_progress_with_verbose_flag(self, safe_prompts):
        """Test progress with verbose output."""
        result = subprocess.run(
            [*self.raxe_cmd, "--verbose", "scan", safe_prompts[0]],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        # Verbose should show detailed progress
        output = result.stdout + result.stderr
        assert any(word in output.lower() for word in ["initializ", "scan", "complete", "duration", "ms"])

    def test_progress_interruption_handling(self, safe_prompts):
        """Test progress indicators handle interruption gracefully."""
        # Start a scan process
        process = subprocess.Popen(
            [*self.raxe_cmd, "scan", safe_prompts[0] * 1000],  # Long prompt
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Give it a moment to start
        time.sleep(0.1)

        # Terminate it
        process.terminate()
        stdout, stderr = process.communicate(timeout=2)

        # Should handle termination gracefully
        # Check that there's no hanging progress indicator
        output = stdout + stderr
        # Should not have incomplete progress sequences
        assert output.count("Initializing") <= 1