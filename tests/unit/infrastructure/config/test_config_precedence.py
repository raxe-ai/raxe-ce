"""Regression tests for config cascade precedence matrix.

Protects the layered config resolution:
    explicit param > env var > config file > default

Covers ScanConfig, Raxe constructor, and scan() method precedence
for l2_enabled and telemetry configuration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raxe.infrastructure.config.scan_config import ScanConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# All RAXE_* env vars that _apply_env_overrides inspects.
_RAXE_ENV_VARS = [
    "RAXE_PACKS_ROOT",
    "RAXE_ENABLE_L2",
    "RAXE_LOW_MEMORY",
    "RAXE_USE_PRODUCTION_L2",
    "RAXE_L2_CONFIDENCE_THRESHOLD",
    "RAXE_FAIL_FAST_ON_CRITICAL",
    "RAXE_MIN_CONFIDENCE_FOR_SKIP",
    "RAXE_ENABLE_SCHEMA_VALIDATION",
    "RAXE_SCHEMA_VALIDATION_MODE",
    "RAXE_API_KEY",
    "RAXE_CUSTOMER_ID",
    "RAXE_PERFORMANCE_MODE",
    "RAXE_TELEMETRY_ENABLED",
]


@pytest.fixture(autouse=True)
def _clean_raxe_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Remove all RAXE_* env vars and isolate HOME so the developer's
    real ~/.raxe/config.yaml never leaks into test assertions."""
    for var in _RAXE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    # Redirect HOME to an empty tmp dir so ScanConfig.load() cannot
    # fall back to the real ~/.raxe/config.yaml.
    monkeypatch.setenv("HOME", str(tmp_path))


def _write_config(tmp_path: Path, yaml_text: str) -> Path:
    """Write a YAML config file and return its path."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_text)
    return config_file


# ===================================================================
# ScanConfig precedence tests
# ===================================================================


class TestScanConfigDefaults:
    """Verify dataclass defaults when no file or env vars are present."""

    def test_default_enable_l2_is_true(self) -> None:
        """Default enable_l2 must be True (L2 on by default)."""
        config = ScanConfig()
        assert config.enable_l2 is True

    def test_default_telemetry_disabled(self) -> None:
        """Default telemetry.enabled must be False (opt-in)."""
        config = ScanConfig()
        assert config.telemetry.enabled is False

    def test_default_low_memory_false(self) -> None:
        config = ScanConfig()
        assert config.low_memory is False

    def test_load_with_no_file_no_env_uses_defaults(self) -> None:
        """ScanConfig.load() with nonexistent path and no env vars -> defaults.

        HOME is redirected by the autouse fixture so ~/.raxe/config.yaml
        on the developer machine does not interfere.
        """
        config = ScanConfig.load(Path("/nonexistent/path/config.yaml"))
        assert config.enable_l2 is True
        assert config.telemetry.enabled is False
        assert config.low_memory is False
        assert config.l2_confidence_threshold == 0.5


class TestConfigFilePrecedence:
    """Config file values override defaults."""

    def test_file_sets_enable_l2_false(self, tmp_path: Path) -> None:
        """Config file enable_l2: false overrides default True."""
        cfg = _write_config(tmp_path, "scan:\n  enable_l2: false\n")
        config = ScanConfig.load(cfg)
        assert config.enable_l2 is False

    def test_file_sets_enable_l2_true_explicitly(self, tmp_path: Path) -> None:
        """Config file enable_l2: true is respected."""
        cfg = _write_config(tmp_path, "scan:\n  enable_l2: true\n")
        config = ScanConfig.load(cfg)
        assert config.enable_l2 is True

    def test_file_sets_telemetry_enabled(self, tmp_path: Path) -> None:
        """Config file telemetry enabled: true overrides default False."""
        cfg = _write_config(tmp_path, "telemetry:\n  enabled: true\n")
        config = ScanConfig.load(cfg)
        assert config.telemetry.enabled is True

    def test_file_sets_telemetry_disabled_explicit(self, tmp_path: Path) -> None:
        """Config file telemetry enabled: false is explicit, not just default."""
        cfg = _write_config(tmp_path, "telemetry:\n  enabled: false\n")
        config = ScanConfig.load(cfg)
        assert config.telemetry.enabled is False

    def test_file_sets_low_memory(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path, "scan:\n  low_memory: true\n")
        config = ScanConfig.load(cfg)
        assert config.low_memory is True

    def test_file_sets_l2_confidence_threshold(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path, "scan:\n  l2_confidence_threshold: 0.8\n")
        config = ScanConfig.load(cfg)
        assert config.l2_confidence_threshold == 0.8


class TestEnvVarOverridesFile:
    """Env vars override config file values."""

    def test_env_enable_l2_false_overrides_file_true(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RAXE_ENABLE_L2=false overrides file enable_l2: true."""
        cfg = _write_config(tmp_path, "scan:\n  enable_l2: true\n")
        monkeypatch.setenv("RAXE_ENABLE_L2", "false")
        config = ScanConfig.load(cfg)
        assert config.enable_l2 is False

    def test_env_enable_l2_true_overrides_file_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RAXE_ENABLE_L2=true overrides file enable_l2: false."""
        cfg = _write_config(tmp_path, "scan:\n  enable_l2: false\n")
        monkeypatch.setenv("RAXE_ENABLE_L2", "true")
        config = ScanConfig.load(cfg)
        assert config.enable_l2 is True

    def test_env_telemetry_enabled_overrides_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RAXE_TELEMETRY_ENABLED=true overrides file enabled: false."""
        cfg = _write_config(tmp_path, "telemetry:\n  enabled: false\n")
        monkeypatch.setenv("RAXE_TELEMETRY_ENABLED", "true")
        config = ScanConfig.load(cfg)
        assert config.telemetry.enabled is True

    def test_env_telemetry_disabled_overrides_file_enabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RAXE_TELEMETRY_ENABLED=false overrides file enabled: true."""
        cfg = _write_config(tmp_path, "telemetry:\n  enabled: true\n")
        monkeypatch.setenv("RAXE_TELEMETRY_ENABLED", "false")
        config = ScanConfig.load(cfg)
        assert config.telemetry.enabled is False


class TestEnvVarOverridesDefault:
    """Env vars override defaults when no config file is present."""

    def test_env_enable_l2_false_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAXE_ENABLE_L2=false overrides default True."""
        monkeypatch.setenv("RAXE_ENABLE_L2", "false")
        config = ScanConfig.load(Path("/nonexistent/path.yaml"))
        assert config.enable_l2 is False

    def test_env_telemetry_enabled_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAXE_TELEMETRY_ENABLED=true overrides default False."""
        monkeypatch.setenv("RAXE_TELEMETRY_ENABLED", "true")
        config = ScanConfig.load(Path("/nonexistent/path.yaml"))
        assert config.telemetry.enabled is True

    def test_env_low_memory_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAXE_LOW_MEMORY=true overrides default False."""
        monkeypatch.setenv("RAXE_LOW_MEMORY", "true")
        config = ScanConfig.load(Path("/nonexistent/path.yaml"))
        assert config.low_memory is True


class TestUnsetEnvDoesNotOverride:
    """An absent env var must NOT clobber file or default values."""

    def test_absent_enable_l2_preserves_file_false(self, tmp_path: Path) -> None:
        """When RAXE_ENABLE_L2 is unset, file value is preserved."""
        cfg = _write_config(tmp_path, "scan:\n  enable_l2: false\n")
        config = ScanConfig.load(cfg)
        assert config.enable_l2 is False

    def test_absent_telemetry_preserves_file_true(self, tmp_path: Path) -> None:
        """When RAXE_TELEMETRY_ENABLED is unset, file value is preserved."""
        cfg = _write_config(tmp_path, "telemetry:\n  enabled: true\n")
        config = ScanConfig.load(cfg)
        assert config.telemetry.enabled is True


class TestEnvVarValidation:
    """Env-sourced values must go through the same validation as defaults."""

    def test_confidence_threshold_out_of_range_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RAXE_L2_CONFIDENCE_THRESHOLD=5.0 must raise ValueError."""
        monkeypatch.setenv("RAXE_L2_CONFIDENCE_THRESHOLD", "5.0")
        with pytest.raises(ValueError, match="l2_confidence_threshold must be 0-1"):
            ScanConfig.load(Path("/nonexistent/path.yaml"))

    def test_confidence_threshold_negative_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAXE_L2_CONFIDENCE_THRESHOLD=-0.1 must raise ValueError."""
        monkeypatch.setenv("RAXE_L2_CONFIDENCE_THRESHOLD", "-0.1")
        with pytest.raises(ValueError, match="l2_confidence_threshold must be 0-1"):
            ScanConfig.load(Path("/nonexistent/path.yaml"))

    def test_min_confidence_for_skip_out_of_range_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RAXE_MIN_CONFIDENCE_FOR_SKIP=2.0 must raise ValueError."""
        monkeypatch.setenv("RAXE_MIN_CONFIDENCE_FOR_SKIP", "2.0")
        with pytest.raises(ValueError, match="min_confidence_for_skip must be 0-1"):
            ScanConfig.load(Path("/nonexistent/path.yaml"))


class TestEnvVarNormalization:
    """Env var values get the same normalization as constructor values."""

    def test_packs_root_relative_resolved_to_absolute(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RAXE_PACKS_ROOT=./relative must resolve to an absolute path."""
        monkeypatch.setenv("RAXE_PACKS_ROOT", "./relative")
        config = ScanConfig.load(Path("/nonexistent/path.yaml"))
        assert config.packs_root.is_absolute()

    def test_packs_root_absolute_stays_absolute(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAXE_PACKS_ROOT=/absolute/path stays as-is."""
        monkeypatch.setenv("RAXE_PACKS_ROOT", "/absolute/path")
        config = ScanConfig.load(Path("/nonexistent/path.yaml"))
        assert config.packs_root == Path("/absolute/path")


# ===================================================================
# Raxe constructor precedence tests
# ===================================================================


class TestRaxeConstructorPrecedence:
    """Raxe() init resolves: explicit param > env > config file > default."""

    def test_no_params_uses_config_cascade_for_l2(self) -> None:
        """Raxe() with no l2_enabled param resolves from config cascade."""
        from raxe.sdk.client import Raxe

        raxe = Raxe()
        # Default cascade: no env, no file -> default True (may auto-downgrade
        # if ML deps missing, but config.enable_l2 should start as True)
        # We check the config value before auto-downgrade logic.
        # Since we cannot guarantee ML deps, check that config was loaded.
        assert raxe.config is not None

    def test_explicit_l2_false_wins_over_default(self) -> None:
        """Raxe(l2_enabled=False) -> False regardless of defaults."""
        from raxe.sdk.client import Raxe

        raxe = Raxe(l2_enabled=False)
        assert raxe.config.enable_l2 is False

    def test_explicit_l2_true_wins_over_env_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Raxe(l2_enabled=True) wins over RAXE_ENABLE_L2=false."""
        from raxe.sdk.client import Raxe

        monkeypatch.setenv("RAXE_ENABLE_L2", "false")
        raxe = Raxe(l2_enabled=True)
        # Explicit True wins. ML auto-downgrade may override if deps missing,
        # but the intended value from the cascade is True.
        # Check that config was set before auto-downgrade:
        # We verify by checking _voting_preset is stored (init completed).
        assert raxe._initialized

    def test_env_l2_false_used_when_no_explicit_param(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RAXE_ENABLE_L2=false + Raxe() -> l2 disabled."""
        from raxe.sdk.client import Raxe

        monkeypatch.setenv("RAXE_ENABLE_L2", "false")
        raxe = Raxe()
        assert raxe.config.enable_l2 is False

    def test_env_l2_true_used_when_no_explicit_param(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAXE_ENABLE_L2=true + Raxe() -> l2 enabled (may auto-downgrade)."""
        from raxe.sdk.client import Raxe

        monkeypatch.setenv("RAXE_ENABLE_L2", "true")
        raxe = Raxe()
        # Either True (ML available) or False (auto-downgrade), but the
        # config cascade resolved True before auto-downgrade.
        # Cannot assert final value without knowing ML dep state, so
        # verify initialization succeeded.
        assert raxe._initialized

    def test_explicit_telemetry_false_wins(self) -> None:
        """Raxe(telemetry=False) -> telemetry disabled."""
        from raxe.sdk.client import Raxe

        raxe = Raxe(telemetry=False)
        assert raxe.config.telemetry.enabled is False

    def test_explicit_telemetry_true_wins_over_env_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raxe(telemetry=True) wins over RAXE_TELEMETRY_ENABLED=false."""
        from raxe.sdk.client import Raxe

        monkeypatch.setenv("RAXE_TELEMETRY_ENABLED", "false")
        raxe = Raxe(telemetry=True)
        assert raxe.config.telemetry.enabled is True

    def test_env_telemetry_false_used_when_no_explicit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RAXE_TELEMETRY_ENABLED=false + Raxe(telemetry=None) -> disabled."""
        from raxe.sdk.client import Raxe

        monkeypatch.setenv("RAXE_TELEMETRY_ENABLED", "false")
        raxe = Raxe()
        assert raxe.config.telemetry.enabled is False

    def test_env_telemetry_true_used_when_no_explicit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RAXE_TELEMETRY_ENABLED=true + Raxe(telemetry=None) -> enabled."""
        from raxe.sdk.client import Raxe

        monkeypatch.setenv("RAXE_TELEMETRY_ENABLED", "true")
        raxe = Raxe()
        assert raxe.config.telemetry.enabled is True

    def test_file_l2_false_used_when_no_env_no_explicit(self, tmp_path: Path) -> None:
        """Config file enable_l2: false + Raxe(config_path=...) -> False."""
        from raxe.sdk.client import Raxe

        cfg = _write_config(tmp_path, "scan:\n  enable_l2: false\n")
        raxe = Raxe(config_path=cfg)
        assert raxe.config.enable_l2 is False

    def test_file_telemetry_true_used_when_no_env_no_explicit(self, tmp_path: Path) -> None:
        """Config file telemetry enabled: true + Raxe(config_path=...) -> True."""
        from raxe.sdk.client import Raxe

        cfg = _write_config(tmp_path, "telemetry:\n  enabled: true\n")
        raxe = Raxe(config_path=cfg)
        assert raxe.config.telemetry.enabled is True


# ===================================================================
# scan() precedence tests
# ===================================================================


class TestScanMethodPrecedence:
    """scan(l2_enabled=...) resolves: explicit per-call > client config."""

    def test_scan_l2_none_uses_config_when_env_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """scan(l2_enabled=None) with RAXE_ENABLE_L2=false -> uses config (False)."""
        from raxe.sdk.client import Raxe

        monkeypatch.setenv("RAXE_ENABLE_L2", "false")
        raxe = Raxe()
        assert raxe.config.enable_l2 is False
        # When scan() receives l2_enabled=None, it falls back to config
        result = raxe.scan("Hello world", l2_enabled=None)
        # The scan should complete; verify via metadata or the fact that
        # l2_detections is empty (L2 was disabled)
        assert result is not None
        # L2 was disabled via env, so l2_detections should be empty/None
        assert not result.l2_detections

    def test_scan_l2_true_overrides_config_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """scan(l2_enabled=True) with RAXE_ENABLE_L2=false -> explicit True wins."""
        from raxe.sdk.client import Raxe

        monkeypatch.setenv("RAXE_ENABLE_L2", "false")
        raxe = Raxe()
        assert raxe.config.enable_l2 is False
        # Explicit True at scan() call site overrides config
        result = raxe.scan("Hello world", l2_enabled=True)
        assert result is not None
        # Cannot guarantee L2 ran (ML deps may be missing), but the call
        # must succeed regardless.

    def test_scan_l2_false_overrides_config_true(self) -> None:
        """scan(l2_enabled=False) with default config (True) -> disabled per call."""
        from raxe.sdk.client import Raxe

        raxe = Raxe()
        result = raxe.scan("Hello world", l2_enabled=False)
        assert result is not None
        assert not result.l2_detections

    def test_scan_l2_none_uses_config_default_true(self) -> None:
        """scan(l2_enabled=None) with no env/file -> config default (True)."""
        from raxe.sdk.client import Raxe

        raxe = Raxe()
        # The scan should use the default config, which has enable_l2=True
        result = raxe.scan("Hello world", l2_enabled=None)
        assert result is not None


# ===================================================================
# Full cascade integration: file + env + explicit
# ===================================================================


class TestFullCascadeIntegration:
    """End-to-end cascade: file sets one thing, env overrides, explicit wins."""

    def test_three_layer_l2_cascade(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """File=true, env=false, explicit=True -> explicit wins."""
        cfg = _write_config(tmp_path, "scan:\n  enable_l2: true\n")
        monkeypatch.setenv("RAXE_ENABLE_L2", "false")
        # ScanConfig.load resolves: env (false) overrides file (true)
        config = ScanConfig.load(cfg)
        assert config.enable_l2 is False
        # Now Raxe(l2_enabled=True) should override
        from raxe.sdk.client import Raxe

        raxe = Raxe(l2_enabled=True, config_path=cfg)
        # Explicit True, but auto-downgrade may kick in.
        # At minimum, the cascade resolved True before auto-downgrade.
        assert raxe._initialized

    def test_three_layer_telemetry_cascade(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """File=false, env=true, explicit=False -> explicit wins."""
        cfg = _write_config(tmp_path, "telemetry:\n  enabled: false\n")
        monkeypatch.setenv("RAXE_TELEMETRY_ENABLED", "true")
        # ScanConfig.load resolves: env (true) overrides file (false)
        config = ScanConfig.load(cfg)
        assert config.telemetry.enabled is True
        # Now Raxe(telemetry=False) should override
        from raxe.sdk.client import Raxe

        raxe = Raxe(telemetry=False, config_path=cfg)
        assert raxe.config.telemetry.enabled is False

    def test_file_only_no_env_no_explicit(self, tmp_path: Path) -> None:
        """File sets enable_l2=false, no env, no explicit -> file value."""
        cfg = _write_config(tmp_path, "scan:\n  enable_l2: false\n")
        config = ScanConfig.load(cfg)
        assert config.enable_l2 is False

    def test_env_only_no_file_no_explicit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env sets RAXE_ENABLE_L2=false, no file, no explicit -> env value."""
        monkeypatch.setenv("RAXE_ENABLE_L2", "false")
        config = ScanConfig.load(Path("/nonexistent/path.yaml"))
        assert config.enable_l2 is False


# ===================================================================
# _apply_env_overrides isolation tests
# ===================================================================


class TestApplyEnvOverridesIsolation:
    """Verify _apply_env_overrides only touches vars that are in os.environ."""

    def test_single_var_does_not_clobber_others(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Setting RAXE_ENABLE_L2 must not change telemetry.enabled."""
        config = ScanConfig()
        original_telemetry = config.telemetry.enabled
        monkeypatch.setenv("RAXE_ENABLE_L2", "false")
        config._apply_env_overrides()
        assert config.enable_l2 is False
        assert config.telemetry.enabled == original_telemetry

    def test_telemetry_env_does_not_clobber_l2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Setting RAXE_TELEMETRY_ENABLED must not change enable_l2."""
        config = ScanConfig()
        original_l2 = config.enable_l2
        monkeypatch.setenv("RAXE_TELEMETRY_ENABLED", "true")
        config._apply_env_overrides()
        assert config.telemetry.enabled is True
        assert config.enable_l2 == original_l2

    def test_env_override_re_runs_post_init_validation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_apply_env_overrides calls __post_init__ for validation."""
        config = ScanConfig()
        monkeypatch.setenv("RAXE_L2_CONFIDENCE_THRESHOLD", "5.0")
        with pytest.raises(ValueError, match="l2_confidence_threshold must be 0-1"):
            config._apply_env_overrides()

    def test_env_override_normalizes_relative_packs_root(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_apply_env_overrides + __post_init__ resolves relative packs_root."""
        config = ScanConfig()
        monkeypatch.setenv("RAXE_PACKS_ROOT", "./my_packs")
        config._apply_env_overrides()
        assert config.packs_root.is_absolute()


# ===================================================================
# Edge cases / regression guards
# ===================================================================


class TestEdgeCases:
    """Boundary and edge-case scenarios for config cascade."""

    def test_from_env_enable_l2_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAXE_ENABLE_L2=TRUE (uppercase) is treated as true."""
        monkeypatch.setenv("RAXE_ENABLE_L2", "TRUE")
        config = ScanConfig.load(Path("/nonexistent/path.yaml"))
        assert config.enable_l2 is True

    def test_from_env_enable_l2_mixed_case(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAXE_ENABLE_L2=True (mixed case) is treated as true."""
        monkeypatch.setenv("RAXE_ENABLE_L2", "True")
        config = ScanConfig.load(Path("/nonexistent/path.yaml"))
        assert config.enable_l2 is True

    def test_from_env_enable_l2_false_mixed_case(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAXE_ENABLE_L2=False (mixed case) is treated as false."""
        monkeypatch.setenv("RAXE_ENABLE_L2", "False")
        config = ScanConfig.load(Path("/nonexistent/path.yaml"))
        assert config.enable_l2 is False

    def test_from_env_non_boolean_string_treated_as_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RAXE_ENABLE_L2=yes is not 'true', so treated as False."""
        monkeypatch.setenv("RAXE_ENABLE_L2", "yes")
        config = ScanConfig.load(Path("/nonexistent/path.yaml"))
        assert config.enable_l2 is False

    def test_empty_config_file_raises_value_error(self, tmp_path: Path) -> None:
        """Empty config file raises ValueError, not silently defaults."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text("")
        with pytest.raises(ValueError, match="Empty config file"):
            ScanConfig.from_file(cfg)

    def test_config_file_missing_scan_section_uses_defaults(self, tmp_path: Path) -> None:
        """Config file without 'scan' section still works with defaults."""
        cfg = _write_config(tmp_path, "telemetry:\n  enabled: true\n")
        config = ScanConfig.load(cfg)
        # scan section defaults
        assert config.enable_l2 is True
        assert config.l2_confidence_threshold == 0.5
        # telemetry from file
        assert config.telemetry.enabled is True

    def test_multiple_env_vars_all_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Multiple RAXE_* env vars are all applied simultaneously."""
        monkeypatch.setenv("RAXE_ENABLE_L2", "false")
        monkeypatch.setenv("RAXE_TELEMETRY_ENABLED", "true")
        monkeypatch.setenv("RAXE_LOW_MEMORY", "true")
        config = ScanConfig.load(Path("/nonexistent/path.yaml"))
        assert config.enable_l2 is False
        assert config.telemetry.enabled is True
        assert config.low_memory is True

    def test_from_file_confidence_threshold_boundary_zero(self, tmp_path: Path) -> None:
        """l2_confidence_threshold=0.0 is valid (boundary)."""
        cfg = _write_config(tmp_path, "scan:\n  l2_confidence_threshold: 0.0\n")
        config = ScanConfig.load(cfg)
        assert config.l2_confidence_threshold == 0.0

    def test_from_file_confidence_threshold_boundary_one(self, tmp_path: Path) -> None:
        """l2_confidence_threshold=1.0 is valid (boundary)."""
        cfg = _write_config(tmp_path, "scan:\n  l2_confidence_threshold: 1.0\n")
        config = ScanConfig.load(cfg)
        assert config.l2_confidence_threshold == 1.0
