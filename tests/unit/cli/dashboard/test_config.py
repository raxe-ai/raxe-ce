"""Tests for dashboard configuration."""

from __future__ import annotations

from raxe.cli.dashboard.config import DashboardConfig, ViewState


class TestDashboardConfig:
    """Tests for DashboardConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = DashboardConfig()

        assert config.refresh_interval_seconds == 2.0
        assert config.cache_ttl_seconds == 1.0
        assert config.history_days == 30
        assert config.max_alerts_visible == 8  # Matches sidebar height
        assert config.theme == "raxe"
        assert config.show_logo is True
        assert config.enable_animations is False  # Disabled for performance

    def test_custom_values(self):
        """Test custom configuration values."""
        config = DashboardConfig(
            refresh_interval_seconds=1.0,
            theme="matrix",
            enable_animations=False,
        )

        assert config.refresh_interval_seconds == 1.0
        assert config.theme == "matrix"
        assert config.enable_animations is False

    def test_keybindings_default(self):
        """Test default keybindings are set."""
        config = DashboardConfig()

        assert "quit" in config.keybindings
        assert "refresh" in config.keybindings
        assert config.keybindings["quit"] == "q"


class TestViewState:
    """Tests for ViewState."""

    def test_default_state(self):
        """Test default view state."""
        state = ViewState()

        assert state.mode == "compact"
        assert state.selected_index == 0
        assert state.selected_alert_id is None
        assert state.frame_count == 0
        assert state.show_help is False
        assert state.status_message is None

    def test_mode_switching(self):
        """Test mode can be switched."""
        state = ViewState()
        state.mode = "detail"

        assert state.mode == "detail"

    def test_selection_tracking(self):
        """Test selection tracking."""
        state = ViewState()
        state.selected_index = 5
        state.selected_alert_id = 123

        assert state.selected_index == 5
        assert state.selected_alert_id == 123

    def test_status_message(self):
        """Test status message tracking."""
        state = ViewState()
        state.status_message = "Export complete"
        state.status_message_time = 1234567890.0

        assert state.status_message == "Export complete"
        assert state.status_message_time == 1234567890.0

    def test_new_alert_tracking(self):
        """Test new alert flash animation tracking."""
        state = ViewState()

        # Defaults should be empty set and 0
        assert state.known_alert_ids == set()
        assert state.new_alert_ids == set()
        assert state.new_alert_flash_until == 0.0

    def test_new_alert_flash_tracking(self):
        """Test tracking alerts for flash animation."""
        state = ViewState()
        state.known_alert_ids = {1, 2, 3}
        state.new_alert_ids = {4, 5}
        state.new_alert_flash_until = 1234567890.0

        assert 4 in state.new_alert_ids
        assert 5 in state.new_alert_ids
        assert 1 not in state.new_alert_ids

    def test_help_overlay_toggle(self):
        """Test help overlay can be toggled."""
        state = ViewState()
        assert state.show_help is False

        state.show_help = True
        assert state.show_help is True

        state.show_help = False
        assert state.show_help is False
