"""Tests for event CLI command.

Tests for the `raxe event show` command that looks up scan events by ID.
"""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from raxe.cli.event import EventData, event, format_relative_time, validate_event_id


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_event_data():
    """Create a sample EventData for testing."""
    return EventData(
        event_id="evt_ae041c39a67744fd",
        timestamp="2025-01-15T10:30:00Z",
        severity="high",
        detections=[
            {
                "rule_id": "pi-001",
                "severity": "high",
                "confidence": 0.95,
                "description": "Prompt injection detected",
                "layer": "L1",
            }
        ],
        prompt_hash="sha256:abc123def456",
        prompt_length=42,
        scan_duration_ms=5.2,
    )


class TestValidateEventId:
    """Tests for event ID validation."""

    def test_valid_event_id(self):
        """Test valid event ID format."""
        assert validate_event_id("evt_ae041c39a67744fd") is True

    def test_invalid_event_id_no_prefix(self):
        """Test event ID without evt_ prefix."""
        assert validate_event_id("ae041c39a67744fd") is False

    def test_invalid_event_id_wrong_length(self):
        """Test event ID with wrong hex length."""
        assert validate_event_id("evt_abc123") is False

    def test_invalid_event_id_uppercase(self):
        """Test event ID with uppercase hex chars."""
        assert validate_event_id("evt_AE041C39A67744FD") is False

    def test_invalid_event_id_empty(self):
        """Test empty string as event ID."""
        assert validate_event_id("") is False

    def test_invalid_event_id_non_hex(self):
        """Test event ID with non-hex characters."""
        assert validate_event_id("evt_zzzzzzzzzzzzzzzz") is False


class TestFormatRelativeTime:
    """Tests for relative time formatting."""

    def test_empty_string_returns_empty(self):
        """Test that invalid timestamp returns empty string."""
        assert format_relative_time("") == ""

    def test_invalid_timestamp_returns_empty(self):
        """Test that non-ISO timestamp returns empty string."""
        assert format_relative_time("not-a-timestamp") == ""


class TestEventShow:
    """Tests for raxe event show command."""

    def test_show_invalid_event_id_format(self, runner):
        """Test that invalid event ID format shows error."""
        result = runner.invoke(event, ["show", "invalid-id"])
        assert result.exit_code != 0
        assert "Invalid event ID" in result.output or "format" in result.output.lower()

    def test_show_event_id_too_short(self, runner):
        """Test that short event ID shows error."""
        result = runner.invoke(event, ["show", "evt_abc"])
        assert result.exit_code != 0

    @patch("raxe.cli.event.fetch_event_from_local")
    def test_show_event_not_found(self, mock_local, runner):
        """Test that missing event shows not found message."""
        mock_local.return_value = None

        with patch("raxe.cli.event.fetch_event_from_portal", return_value=None):
            result = runner.invoke(event, ["show", "evt_ae041c39a67744fd"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    @patch("raxe.cli.event.fetch_event_from_local")
    def test_show_event_from_local_rich(self, mock_local, runner, sample_event_data):
        """Test showing event from local database with rich output."""
        mock_local.return_value = sample_event_data

        result = runner.invoke(event, ["show", "evt_ae041c39a67744fd"])

        assert result.exit_code == 0
        assert "evt_ae041c39a67744fd" in result.output

    @patch("raxe.cli.event.fetch_event_from_local")
    def test_show_event_json_format(self, mock_local, runner, sample_event_data):
        """Test showing event with JSON output format."""
        mock_local.return_value = sample_event_data

        result = runner.invoke(event, ["show", "evt_ae041c39a67744fd", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["event_id"] == "evt_ae041c39a67744fd"
        assert data["severity"] == "high"

    @patch("raxe.cli.event.fetch_event_from_local")
    def test_show_event_with_show_prompt(self, mock_local, runner):
        """Test --show-prompt flag shows warning."""
        event_data = EventData(
            event_id="evt_ae041c39a67744fd",
            timestamp="2025-01-15T10:30:00Z",
            severity="none",
            detections=[],
            prompt_hash="sha256:abc123",
            prompt_text="Sensitive prompt content",
        )
        mock_local.return_value = event_data

        result = runner.invoke(event, ["show", "evt_ae041c39a67744fd", "--show-prompt"])

        assert result.exit_code == 0

    def test_show_event_missing_argument(self, runner):
        """Test that missing event_id argument shows usage error."""
        result = runner.invoke(event, ["show"])
        assert result.exit_code != 0


class TestEventDataFromApiResponse:
    """Tests for EventData.from_api_response."""

    def test_from_api_response_full(self):
        """Test creating EventData from complete API response."""
        data = {
            "event_id": "evt_ae041c39a67744fd",
            "timestamp": "2025-01-15T10:30:00Z",
            "severity": "high",
            "detections": [{"rule_id": "pi-001"}],
            "prompt_hash": "sha256:abc",
            "prompt_length": 42,
            "scan_duration_ms": 5.2,
        }
        event_data = EventData.from_api_response(data)
        assert event_data.event_id == "evt_ae041c39a67744fd"
        assert event_data.severity == "high"
        assert event_data.prompt_length == 42

    def test_from_api_response_minimal(self):
        """Test creating EventData from minimal API response."""
        data = {}
        event_data = EventData.from_api_response(data)
        assert event_data.event_id == ""
        assert event_data.severity == "none"
        assert event_data.detections == []

    def test_from_api_response_uses_highest_severity_fallback(self):
        """Test that highest_severity is used when severity is missing."""
        data = {"highest_severity": "critical"}
        event_data = EventData.from_api_response(data)
        assert event_data.severity == "critical"
