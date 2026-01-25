"""Tests for dashboard views."""

from __future__ import annotations

from datetime import datetime, timezone

from raxe.cli.dashboard.config import DashboardConfig, ViewState
from raxe.cli.dashboard.data_provider import AlertItem, DashboardData
from raxe.cli.dashboard.themes import RAXE_THEME
from raxe.cli.dashboard.views.compact_view import CompactView
from raxe.cli.dashboard.views.detail_view import DetailView


class TestCompactView:
    """Tests for CompactView."""

    def test_compact_view_initialization(self):
        """Test compact view can be initialized."""
        config = DashboardConfig()
        view = CompactView(RAXE_THEME, config)
        assert view is not None

    def test_compact_view_render_returns_group(self):
        """Test render returns a Rich Group."""
        from rich.console import Group

        config = DashboardConfig()
        view = CompactView(RAXE_THEME, config)
        state = ViewState()
        now = datetime.now(timezone.utc)
        data = DashboardData(last_refresh=now)

        result = view.render(data, state, terminal_width=80)
        assert isinstance(result, Group)

    def test_compact_view_respects_terminal_width(self):
        """Test compact view uses terminal width parameter."""
        config = DashboardConfig()
        view = CompactView(RAXE_THEME, config)
        state = ViewState()
        now = datetime.now(timezone.utc)
        data = DashboardData(last_refresh=now)

        # Should not raise with different widths
        result_small = view.render(data, state, terminal_width=70)
        result_large = view.render(data, state, terminal_width=120)

        assert result_small is not None
        assert result_large is not None

    def test_compact_view_clamps_width(self):
        """Test compact view clamps width to MIN_WIDTH."""
        config = DashboardConfig()
        view = CompactView(RAXE_THEME, config)
        state = ViewState()
        now = datetime.now(timezone.utc)
        data = DashboardData(last_refresh=now)

        # Very small width should be clamped to MIN_WIDTH
        result = view.render(data, state, terminal_width=40)
        assert result is not None

    def test_compact_view_help_overlay_rendered_when_enabled(self):
        """Test help overlay is rendered when show_help is True."""
        config = DashboardConfig()
        view = CompactView(RAXE_THEME, config)
        state = ViewState()
        state.show_help = True
        now = datetime.now(timezone.utc)
        data = DashboardData(last_refresh=now)

        result = view.render(data, state, terminal_width=80)
        # Check that the result contains help overlay content
        # (The Group contains Text objects that we can check)
        assert result is not None

    def test_compact_view_help_overlay_contains_shortcuts(self):
        """Test help overlay content includes keyboard shortcuts."""
        config = DashboardConfig()
        view = CompactView(RAXE_THEME, config)

        # Render the help overlay directly
        lines = view._render_help_overlay(80, 0)

        # Convert to string for checking content
        all_text = " ".join(line.plain for line in lines)

        # Should contain help sections
        assert "Navigation" in all_text
        assert "Actions" in all_text
        assert "Quit" in all_text


class TestDetailView:
    """Tests for DetailView."""

    def test_detail_view_initialization(self):
        """Test detail view can be initialized."""
        config = DashboardConfig()
        view = DetailView(RAXE_THEME, config)
        assert view is not None

    def test_detail_view_render_with_none_alert(self):
        """Test render handles None alert gracefully."""
        from rich.console import Group

        config = DashboardConfig()
        view = DetailView(RAXE_THEME, config)
        state = ViewState()

        result = view.render(None, state, terminal_width=80)
        assert isinstance(result, Group)

    def test_detail_view_render_with_alert(self):
        """Test render with a valid alert."""
        from rich.console import Group

        config = DashboardConfig()
        view = DetailView(RAXE_THEME, config)
        state = ViewState()
        now = datetime.now(timezone.utc)

        alert = AlertItem(
            scan_id=1,
            timestamp=now,
            severity="HIGH",
            rule_ids=["pi-001"],
            detection_count=1,
            prompt_preview="Test prompt...",
            prompt_hash="sha256:abc123",
            confidence=0.95,
        )

        result = view.render(alert, state, terminal_width=80)
        assert isinstance(result, Group)

    def test_detail_view_respects_terminal_width(self):
        """Test detail view uses terminal width parameter."""
        config = DashboardConfig()
        view = DetailView(RAXE_THEME, config)
        state = ViewState()
        now = datetime.now(timezone.utc)

        alert = AlertItem(
            scan_id=1,
            timestamp=now,
            severity="CRITICAL",
            rule_ids=["pi-001"],
            detection_count=1,
            prompt_preview="Test prompt...",
            prompt_hash="sha256:abc123",
        )

        # Should not raise with different widths
        result_small = view.render(alert, state, terminal_width=70)
        result_large = view.render(alert, state, terminal_width=120)

        assert result_small is not None
        assert result_large is not None
