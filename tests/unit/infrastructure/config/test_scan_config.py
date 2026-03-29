"""Tests for ScanConfig layered precedence and env overrides."""

from __future__ import annotations

import os
from pathlib import Path

from raxe.infrastructure.config.scan_config import ScanConfig


class TestScanConfigLoad:
    """Test ScanConfig.load() layered precedence: env > file > defaults."""

    def test_defaults_when_no_file_no_env(self):
        """ScanConfig.load() with no file and no env vars → defaults."""
        config = ScanConfig.load(Path("/nonexistent/path.yaml"))
        assert config.enable_l2 is True
        assert config.l2_confidence_threshold == 0.5
        assert config.fail_fast_on_critical is False

    def test_file_overrides_defaults(self, tmp_path):
        """Config file values override defaults."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("scan:\n" "  enable_l2: false\n" "  l2_confidence_threshold: 0.8\n")
        config = ScanConfig.load(config_file)
        assert config.enable_l2 is False
        assert config.l2_confidence_threshold == 0.8

    def test_env_overrides_file(self, tmp_path, monkeypatch):
        """Environment variables override config file values."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("scan:\n" "  enable_l2: false\n")
        monkeypatch.setenv("RAXE_ENABLE_L2", "true")
        config = ScanConfig.load(config_file)
        # Env var (true) should override file (false)
        assert config.enable_l2 is True

    def test_env_overrides_defaults(self, monkeypatch):
        """Env vars override defaults even when no config file exists."""
        monkeypatch.setenv("RAXE_ENABLE_L2", "false")
        config = ScanConfig.load(Path("/nonexistent/path.yaml"))
        assert config.enable_l2 is False

    def test_unset_env_does_not_override_file(self, tmp_path):
        """Env var that is NOT set does not override config file value."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("scan:\n" "  enable_l2: false\n")
        # Ensure env var is not set
        os.environ.pop("RAXE_ENABLE_L2", None)
        config = ScanConfig.load(config_file)
        assert config.enable_l2 is False

    def test_explicit_path_preferred_over_home(self, tmp_path, monkeypatch):
        """Explicit config_path is preferred over ~/.raxe/config.yaml."""
        config_file = tmp_path / "explicit.yaml"
        config_file.write_text("scan:\n" "  l2_confidence_threshold: 0.99\n")
        config = ScanConfig.load(config_file)
        assert config.l2_confidence_threshold == 0.99

    def test_invalid_performance_mode_falls_back(self, tmp_path):
        """Invalid PerformanceMode in config file falls back to FAIL_OPEN."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("performance:\n" "  mode: balanced\n")
        # Should not raise
        config = ScanConfig.load(config_file)
        assert config.performance.mode.value == "fail_open"


class TestApplyEnvOverrides:
    """Test _apply_env_overrides() only overrides explicitly-set vars."""

    def test_apply_l2_threshold(self, monkeypatch):
        config = ScanConfig()
        monkeypatch.setenv("RAXE_L2_CONFIDENCE_THRESHOLD", "0.75")
        config._apply_env_overrides()
        assert config.l2_confidence_threshold == 0.75

    def test_apply_api_key(self, monkeypatch):
        config = ScanConfig()
        monkeypatch.setenv("RAXE_API_KEY", "test_key")
        config._apply_env_overrides()
        assert config.api_key == "test_key"
        assert config.telemetry.api_key == "test_key"

    def test_apply_telemetry_enabled(self, monkeypatch):
        config = ScanConfig()
        monkeypatch.setenv("RAXE_TELEMETRY_ENABLED", "true")
        config._apply_env_overrides()
        assert config.telemetry.enabled is True

    def test_no_env_no_change(self):
        """When no RAXE_* env vars are set, config is unchanged."""
        # Clear any that might be set
        for key in list(os.environ):
            if key.startswith("RAXE_"):
                os.environ.pop(key)
        config = ScanConfig()
        original_l2 = config.enable_l2
        config._apply_env_overrides()
        assert config.enable_l2 == original_l2
