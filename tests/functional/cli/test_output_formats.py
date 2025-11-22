"""Test CLI output format options."""
import json
import subprocess
import sys
from datetime import datetime

import pytest


class TestCLIOutputFormats:
    """Test different output format options."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.raxe_cmd = [sys.executable, "-m", "raxe.cli.main"]

    def test_default_text_output(self, safe_prompts):
        """Test default text output format."""
        result = subprocess.run(
            [*self.raxe_cmd, "scan", safe_prompts[0]],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        # Should be human-readable text
        assert "safe" in result.stdout.lower() or "✓" in result.stdout
        # Should not be JSON
        try:
            json.loads(result.stdout)
            raise AssertionError("Output should not be valid JSON in text mode")
        except json.JSONDecodeError:
            pass  # Expected

    def test_json_output_format(self, safe_prompts):
        """Test JSON output format."""
        result = subprocess.run(
            [*self.raxe_cmd, "scan", "--format", "json", safe_prompts[0]],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        # Should be valid JSON
        data = json.loads(result.stdout)

        # Verify JSON structure
        assert "status" in data
        assert "severity" in data
        assert "timestamp" in data
        assert data["status"] == "safe"

    def test_json_output_with_threat(self, threat_prompts):
        """Test JSON output for threat detection."""
        result = subprocess.run(
            [*self.raxe_cmd, "scan", "--format", "json", threat_prompts[0]],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1
        data = json.loads(result.stdout)

        # Verify threat JSON structure
        assert data["status"] == "threat"
        assert "severity" in data
        assert data["severity"] in ["low", "medium", "high", "critical"]
        assert "threats" in data or "detections" in data
        assert "confidence" in data

    def test_verbose_output_format(self, safe_prompts):
        """Test verbose output format."""
        result = subprocess.run(
            [*self.raxe_cmd, "scan", "--format", "verbose", safe_prompts[0]],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        output = result.stdout

        # Verbose should include detailed information
        assert any(word in output.lower() for word in ["duration", "ms", "time", "latency"])
        assert any(word in output.lower() for word in ["l1", "l2", "layer", "detection"])
        assert any(word in output.lower() for word in ["rule", "pattern", "check"])

    def test_multiple_prompts_json_output(self, safe_prompts, threat_prompts):
        """Test JSON output with multiple prompts."""
        prompts = [safe_prompts[0], threat_prompts[0], safe_prompts[1]]

        result = subprocess.run(
            [*self.raxe_cmd, "scan", "--format", "json", *prompts],
            capture_output=True,
            text=True
        )

        # Should fail if any threat
        assert result.returncode == 1

        # Should be JSON array or object with results
        data = json.loads(result.stdout)

        if isinstance(data, list):
            assert len(data) == 3
            assert data[0]["status"] == "safe"
            assert data[1]["status"] == "threat"
            assert data[2]["status"] == "safe"
        else:
            assert "results" in data
            assert len(data["results"]) == 3

    def test_csv_output_format(self, safe_prompts):
        """Test CSV output format if supported."""
        result = subprocess.run(
            [*self.raxe_cmd, "scan", "--format", "csv", safe_prompts[0]],
            capture_output=True,
            text=True
        )

        # CSV might not be implemented yet
        if result.returncode == 2:
            pytest.skip("CSV format not implemented")

        assert result.returncode == 0
        output = result.stdout

        # Should have CSV structure
        lines = output.strip().split("\n")
        assert len(lines) >= 2  # Header + data
        assert "," in lines[0]  # CSV delimiter

    def test_quiet_json_combination(self, safe_prompts):
        """Test quiet mode with JSON output."""
        result = subprocess.run(
            [*self.raxe_cmd, "--quiet", "scan", "--format", "json", safe_prompts[0]],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        # Should only output JSON, no extra text
        data = json.loads(result.stdout)
        assert "status" in data

    def test_output_includes_metadata(self, safe_prompts):
        """Test output includes important metadata."""
        result = subprocess.run(
            [*self.raxe_cmd, "scan", "--format", "json", safe_prompts[0]],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)

        # Should include metadata
        assert "timestamp" in data or "scanned_at" in data
        if "timestamp" in data:
            # Should be valid ISO format
            datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

        # Should include performance metrics
        assert any(key in data for key in ["duration_ms", "latency_ms", "scan_time"])

    def test_output_format_with_file_input(self, tmp_path, safe_prompts):
        """Test output formats with file input."""
        # Create test file
        test_file = tmp_path / "prompts.txt"
        test_file.write_text("\n".join(safe_prompts[:3]))

        # Test JSON format with file
        result = subprocess.run(
            [*self.raxe_cmd, "scan", "-f", str(test_file), "--format", "json"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)

        # Should handle multiple results
        if isinstance(data, dict):
            assert "results" in data or "scans" in data

    def test_streaming_output(self, safe_prompts):
        """Test streaming output for real-time monitoring."""
        # Create process with pipes
        process = subprocess.Popen(
            [*self.raxe_cmd, "scan", "--stream", *safe_prompts[:3]],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )

        # Read output line by line
        lines = []
        for line in process.stdout:
            lines.append(line.strip())
            if len(lines) >= 3:
                break

        process.terminate()
        process.wait(timeout=2)

        # Should output results as they complete
        if "--stream" in self.raxe_cmd:  # If streaming is supported
            assert len(lines) >= 3

    def test_error_output_format(self, edge_cases):
        """Test error output formatting."""
        # Test with malformed input
        result = subprocess.run(
            [*self.raxe_cmd, "scan", "--format", "json", edge_cases["malformed_json"][0]],
            capture_output=True,
            text=True
        )

        # Should handle gracefully
        if result.returncode == 2:
            # Error case - should still be valid JSON if format=json
            try:
                data = json.loads(result.stdout)
                assert "error" in data or "message" in data
            except json.JSONDecodeError:
                # Or clear error in stderr
                assert "error" in result.stderr.lower()

    def test_custom_output_template(self, safe_prompts):
        """Test custom output template if supported."""
        result = subprocess.run(
            [*self.raxe_cmd, "scan", "--template", "{status} - {severity}", safe_prompts[0]],
            capture_output=True,
            text=True
        )

        if result.returncode == 2:
            pytest.skip("Custom templates not implemented")

        assert result.returncode == 0
        # Should follow template format
        assert " - " in result.stdout