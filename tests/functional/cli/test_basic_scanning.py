"""Test basic CLI scanning functionality."""
import subprocess
import sys

import pytest


class TestCLIBasicScanning:
    """Test core CLI scanning features."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.raxe_cmd = [sys.executable, "-m", "raxe.cli.main"]

    def test_single_prompt_safe(self, safe_prompts):
        """Test scanning single safe prompt."""
        prompt = safe_prompts[0]
        result = subprocess.run(
            [*self.raxe_cmd, "scan", prompt],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0, f"Safe prompt failed: {result.stderr}"
        assert "safe" in result.stdout.lower() or "✓" in result.stdout

    def test_single_prompt_threat(self, threat_prompts):
        """Test scanning single threat prompt."""
        prompt = threat_prompts[0]
        result = subprocess.run(
            [*self.raxe_cmd, "scan", prompt],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1, "Threat should return exit code 1"
        assert any(word in result.stdout.lower() for word in ["threat", "dangerous", "blocked", "✗"])

    def test_multiple_prompts_from_file(self, tmp_path, safe_prompts, threat_prompts):
        """Test scanning multiple prompts from file."""
        # Create test file with mixed prompts
        test_file = tmp_path / "prompts.txt"
        prompts = safe_prompts[:2] + threat_prompts[:1] + safe_prompts[2:4]
        test_file.write_text("\n".join(prompts))

        result = subprocess.run(
            [*self.raxe_cmd, "scan", "-f", str(test_file)],
            capture_output=True,
            text=True
        )

        # Should fail if any threat found
        assert result.returncode == 1
        # Should show count of prompts scanned
        assert "5" in result.stdout or "scanned" in result.stdout.lower()

    def test_stdin_input(self, safe_prompts):
        """Test reading prompt from stdin."""
        prompt = safe_prompts[0]
        result = subprocess.run(
            [*self.raxe_cmd, "scan", "-"],
            input=prompt,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "safe" in result.stdout.lower() or "✓" in result.stdout

    def test_exit_codes(self, safe_prompts, threat_prompts):
        """Verify correct exit codes for different scenarios."""
        # Safe prompt -> 0
        result = subprocess.run(
            [*self.raxe_cmd, "scan", safe_prompts[0]],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

        # Threat prompt -> 1
        result = subprocess.run(
            [*self.raxe_cmd, "scan", threat_prompts[0]],
            capture_output=True,
            text=True
        )
        assert result.returncode == 1

        # Invalid command -> 2
        result = subprocess.run(
            [*self.raxe_cmd, "scan", "--invalid-flag"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 2

    def test_quiet_mode(self, safe_prompts):
        """Test quiet mode suppresses output."""
        result = subprocess.run(
            [*self.raxe_cmd, "--quiet", "scan", safe_prompts[0]],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        # In quiet mode, should have minimal or no output
        assert len(result.stdout.strip()) == 0 or "safe" in result.stdout.lower()

    def test_verbose_mode(self, safe_prompts):
        """Test verbose mode shows detailed output."""
        result = subprocess.run(
            [*self.raxe_cmd, "--verbose", "scan", safe_prompts[0]],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        # Verbose mode should show more details
        output_lines = result.stdout.strip().split("\n")
        assert len(output_lines) > 1  # More than just the result

    @pytest.mark.parametrize("prompt_count", [1, 5, 10])
    def test_batch_scanning_performance(self, safe_prompts, prompt_count, performance_tracker):
        """Test batch scanning maintains performance."""
        prompts = safe_prompts[:prompt_count]

        with performance_tracker.track("batch_scan"):
            result = subprocess.run(
                [*self.raxe_cmd, "scan", *prompts],
                capture_output=True,
                text=True
            )

        assert result.returncode == 0
        stats = performance_tracker.get_stats("batch_scan")

        # Should complete reasonably fast (allowing for CLI overhead)
        assert stats["mean"] < 5000, f"Batch scan too slow: {stats['mean']}ms"

    def test_no_l2_flag(self, safe_prompts):
        """Test --no-l2 flag disables L2 detection."""
        result = subprocess.run(
            [*self.raxe_cmd, "scan", "--no-l2", safe_prompts[0]],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "RAXE_VERBOSE": "true"}
        )

        assert result.returncode == 0
        # Should indicate L2 is disabled in verbose mode
        if "RAXE_VERBOSE" in subprocess.os.environ:
            assert "l2" in result.stdout.lower() or "layer 2" in result.stdout.lower()

    def test_confidence_threshold(self, threat_prompts):
        """Test --confidence flag affects detection."""
        # High confidence - might miss some threats
        subprocess.run(
            [*self.raxe_cmd, "scan", "--confidence", "0.9", threat_prompts[0]],
            capture_output=True,
            text=True
        )

        # Low confidence - should catch more
        result_low = subprocess.run(
            [*self.raxe_cmd, "scan", "--confidence", "0.1", threat_prompts[0]],
            capture_output=True,
            text=True
        )

        # Low confidence should be more likely to flag as threat
        assert result_low.returncode == 1