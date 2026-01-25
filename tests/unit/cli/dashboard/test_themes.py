"""Tests for dashboard themes."""

from __future__ import annotations

from raxe.cli.dashboard.themes import (
    CYBER_THEME,
    MATRIX_THEME,
    RAXE_THEME,
    THEMES,
    get_chroma_color,
    get_severity_color,
    get_severity_style,
    get_theme,
    interpolate_gradient,
    render_gradient_bar,
    render_gradient_text,
    render_logo,
)


class TestThemes:
    """Tests for theme definitions."""

    def test_raxe_theme_exists(self):
        """Test RAXE theme is defined."""
        assert RAXE_THEME is not None
        assert len(RAXE_THEME.gradient) == 6
        assert RAXE_THEME.gradient[0] == "#1CE3FE"  # Cyan
        assert RAXE_THEME.gradient[-1] == "#F002DB"  # Magenta

    def test_matrix_theme_exists(self):
        """Test Matrix theme is defined."""
        assert MATRIX_THEME is not None
        assert "#00FF00" in MATRIX_THEME.gradient  # Green

    def test_cyber_theme_exists(self):
        """Test Cyber theme is defined."""
        assert CYBER_THEME is not None
        assert "#00FFFF" in CYBER_THEME.gradient  # Cyan
        assert "#FF00FF" in CYBER_THEME.gradient  # Magenta

    def test_themes_dict(self):
        """Test THEMES dict contains all themes."""
        assert "raxe" in THEMES
        assert "matrix" in THEMES
        assert "cyber" in THEMES

    def test_get_theme_valid(self):
        """Test get_theme returns correct theme."""
        theme = get_theme("raxe")
        assert theme == RAXE_THEME

        theme = get_theme("matrix")
        assert theme == MATRIX_THEME

    def test_get_theme_invalid_falls_back(self):
        """Test get_theme falls back to RAXE for invalid names."""
        theme = get_theme("nonexistent")
        assert theme == RAXE_THEME


class TestSeverityColors:
    """Tests for severity color functions."""

    def test_get_severity_color_critical(self):
        """Test CRITICAL severity color."""
        color = get_severity_color("CRITICAL", RAXE_THEME)
        assert color == RAXE_THEME.critical

    def test_get_severity_color_high(self):
        """Test HIGH severity color."""
        color = get_severity_color("HIGH", RAXE_THEME)
        assert color == RAXE_THEME.high

    def test_get_severity_color_case_insensitive(self):
        """Test severity colors are case-insensitive."""
        color1 = get_severity_color("critical", RAXE_THEME)
        color2 = get_severity_color("CRITICAL", RAXE_THEME)
        assert color1 == color2

    def test_get_severity_color_unknown(self):
        """Test unknown severity returns muted color."""
        color = get_severity_color("UNKNOWN", RAXE_THEME)
        assert color == RAXE_THEME.muted

    def test_get_severity_style_critical_is_bold(self):
        """Test CRITICAL severity style has bold."""
        style = get_severity_style("CRITICAL", RAXE_THEME)
        assert style.bold is True

    def test_get_severity_style_high_is_bold(self):
        """Test HIGH severity style has bold."""
        style = get_severity_style("HIGH", RAXE_THEME)
        assert style.bold is True


class TestChromaColor:
    """Tests for chroma animation colors."""

    def test_get_chroma_color_cycles(self):
        """Test chroma color cycles through gradient."""
        colors = [get_chroma_color(0, i, RAXE_THEME) for i in range(6)]

        # Should have all gradient colors
        assert set(colors) == set(RAXE_THEME.gradient)

    def test_get_chroma_color_frame_offset(self):
        """Test different frames produce different starting colors."""
        color_frame_0 = get_chroma_color(0, 0, RAXE_THEME)
        color_frame_1 = get_chroma_color(1, 0, RAXE_THEME)

        # Different frames should give different colors at same position
        assert color_frame_0 != color_frame_1


class TestGradientFunctions:
    """Tests for gradient rendering functions."""

    def test_interpolate_gradient_start(self):
        """Test interpolate_gradient at start."""
        color = interpolate_gradient(0.0, RAXE_THEME)
        assert color == RAXE_THEME.gradient[0]

    def test_interpolate_gradient_end(self):
        """Test interpolate_gradient at end."""
        color = interpolate_gradient(1.0, RAXE_THEME)
        assert color == RAXE_THEME.gradient[-1]

    def test_render_gradient_text_length(self):
        """Test render_gradient_text preserves length."""
        text = "HELLO"
        result = render_gradient_text(text, RAXE_THEME)
        assert result.plain == text

    def test_render_gradient_bar_empty(self):
        """Test render_gradient_bar at 0%."""
        result = render_gradient_bar(0.0, 10, RAXE_THEME)
        assert "█" not in result.plain
        assert "░" in result.plain

    def test_render_gradient_bar_full(self):
        """Test render_gradient_bar at 100%."""
        result = render_gradient_bar(1.0, 10, RAXE_THEME)
        assert result.plain.count("█") == 10

    def test_render_gradient_bar_half(self):
        """Test render_gradient_bar at 50%."""
        result = render_gradient_bar(0.5, 10, RAXE_THEME)
        assert result.plain.count("█") == 5


class TestLogo:
    """Tests for logo rendering."""

    def test_render_logo_small(self):
        """Test small logo rendering."""
        result = render_logo(RAXE_THEME, small=True)
        assert "RAXE" in result.plain

    def test_render_logo_large(self):
        """Test large logo rendering."""
        result = render_logo(RAXE_THEME, small=False)
        # Large logo has multiple lines
        assert "\n" in result.plain
