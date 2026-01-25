"""Tests for dashboard widgets."""

from __future__ import annotations

from datetime import datetime, timezone

from raxe.cli.dashboard.config import ViewState
from raxe.cli.dashboard.data_provider import AlertItem
from raxe.cli.dashboard.themes import RAXE_THEME
from raxe.cli.dashboard.widgets.alert_list import AlertListWidget


class TestAlertListWidget:
    """Tests for AlertListWidget."""

    def test_widget_initialization(self):
        """Test widget can be initialized."""
        widget = AlertListWidget(RAXE_THEME)
        assert widget is not None
        assert widget.max_visible == 15  # Widget default (config default is 8)

    def test_widget_custom_max_visible(self):
        """Test widget with custom max_visible."""
        widget = AlertListWidget(RAXE_THEME, max_visible=10)
        assert widget.max_visible == 10

    def test_render_empty_alerts(self):
        """Test render with no alerts."""
        widget = AlertListWidget(RAXE_THEME)
        state = ViewState()

        lines = widget.render([], state)
        assert len(lines) == 1
        assert "No recent alerts" in lines[0].plain

    def test_render_with_alerts(self):
        """Test render with alerts."""
        widget = AlertListWidget(RAXE_THEME)
        state = ViewState()
        now = datetime.now(timezone.utc)

        alerts = [
            AlertItem(
                scan_id=1,
                timestamp=now,
                severity="HIGH",
                rule_ids=["pi-001"],
                detection_count=1,
                prompt_preview="Test prompt...",
                prompt_hash="sha256:abc123",
            ),
        ]

        lines = widget.render(alerts, state)
        # Should pad to max_visible
        assert len(lines) == widget.max_visible

    def test_selected_alert_indicator(self):
        """Test selected alert shows indicator."""
        widget = AlertListWidget(RAXE_THEME)
        state = ViewState()
        state.selected_index = 0
        now = datetime.now(timezone.utc)

        alerts = [
            AlertItem(
                scan_id=1,
                timestamp=now,
                severity="HIGH",
                rule_ids=["pi-001"],
                detection_count=1,
                prompt_preview="Test prompt...",
                prompt_hash="sha256:abc123",
            ),
        ]

        lines = widget.render(alerts, state)
        # First line should have selection indicator
        assert "▶" in lines[0].plain

    def test_new_alert_flash_indicator(self):
        """Test new alerts show flash indicator."""
        widget = AlertListWidget(RAXE_THEME)
        state = ViewState()
        state.selected_index = 1  # Not this alert
        state.new_alert_ids = {1}  # Mark scan_id 1 as new
        now = datetime.now(timezone.utc)

        alerts = [
            AlertItem(
                scan_id=1,  # This is new
                timestamp=now,
                severity="HIGH",
                rule_ids=["pi-001"],
                detection_count=1,
                prompt_preview="Test prompt...",
                prompt_hash="sha256:abc123",
            ),
            AlertItem(
                scan_id=2,  # This is not new
                timestamp=now,
                severity="MEDIUM",
                rule_ids=["pi-002"],
                detection_count=1,
                prompt_preview="Other prompt...",
                prompt_hash="sha256:def456",
            ),
        ]

        lines = widget.render(alerts, state)
        # First line should have star indicator (for new alert)
        assert "★" in lines[0].plain
        # Second line should have selection indicator
        assert "▶" in lines[1].plain

    def test_severity_abbreviation(self):
        """Test severity abbreviation."""
        widget = AlertListWidget(RAXE_THEME)

        assert widget._severity_abbrev("CRITICAL") == "CRIT"
        assert widget._severity_abbrev("HIGH") == "HIGH"
        assert widget._severity_abbrev("MEDIUM") == "MED"
        assert widget._severity_abbrev("LOW") == "LOW"
        assert widget._severity_abbrev("INFO") == "INFO"
        assert widget._severity_abbrev("unknown") == "UNKN"

    def test_format_rules(self):
        """Test rule formatting."""
        widget = AlertListWidget(RAXE_THEME)

        # Empty
        assert widget._format_rules([]) == ""

        # Single rule (fits in max_width=12)
        assert widget._format_rules(["pi-001"]) == "pi-001"

        # Single long rule - truncated with ellipsis
        result = widget._format_rules(["very-long-rule-name"])
        assert len(result) <= 12
        assert result.endswith("…")

        # Multiple rules - shows first + count
        result = widget._format_rules(["pi-001", "pi-002"])
        assert "+1" in result
        assert result.startswith("pi-001")

        # Many rules
        result = widget._format_rules(["pi-001", "pi-002", "pi-003"])
        assert "+2" in result

    def test_truncate(self):
        """Test text truncation."""
        widget = AlertListWidget(RAXE_THEME)

        # Short text
        assert widget._truncate("hello", 10) == "hello"

        # Long text - truncates at max_len - 2 and adds ".."
        assert widget._truncate("hello world", 8) == "hello .."

    def test_render_footer(self):
        """Test footer rendering."""
        widget = AlertListWidget(RAXE_THEME)
        state = ViewState()

        footer = widget.render_footer([], state)
        assert "Navigate" in footer.plain
        assert "Expand" in footer.plain
