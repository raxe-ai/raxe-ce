"""Tests for global policy presets.

TDD: These tests are written BEFORE implementation.
"""

import pytest

from raxe.domain.tenants.models import PolicyMode, TenantPolicy
from raxe.domain.tenants.presets import (
    GLOBAL_PRESETS,
    POLICY_BALANCED,
    POLICY_MONITOR,
    POLICY_STRICT,
)


class TestMonitorPreset:
    """Tests for POLICY_MONITOR preset."""

    def test_monitor_is_tenant_policy(self) -> None:
        """POLICY_MONITOR is a TenantPolicy instance."""
        assert isinstance(POLICY_MONITOR, TenantPolicy)

    def test_monitor_mode(self) -> None:
        """Monitor preset has MONITOR mode."""
        assert POLICY_MONITOR.mode == PolicyMode.MONITOR

    def test_monitor_no_blocking(self) -> None:
        """Monitor mode has blocking disabled."""
        assert POLICY_MONITOR.blocking_enabled is False

    def test_monitor_is_global(self) -> None:
        """Monitor preset has tenant_id=None (global)."""
        assert POLICY_MONITOR.tenant_id is None

    def test_monitor_policy_id(self) -> None:
        """Monitor preset has policy_id 'monitor'."""
        assert POLICY_MONITOR.policy_id == "monitor"

    def test_monitor_verbose_telemetry(self) -> None:
        """Monitor mode has verbose telemetry for maximum visibility."""
        assert POLICY_MONITOR.telemetry_detail == "verbose"

    def test_monitor_l2_enabled(self) -> None:
        """Monitor mode has L2 enabled for learning."""
        assert POLICY_MONITOR.l2_enabled is True


class TestBalancedPreset:
    """Tests for POLICY_BALANCED preset."""

    def test_balanced_is_tenant_policy(self) -> None:
        """POLICY_BALANCED is a TenantPolicy instance."""
        assert isinstance(POLICY_BALANCED, TenantPolicy)

    def test_balanced_mode(self) -> None:
        """Balanced preset has BALANCED mode."""
        assert POLICY_BALANCED.mode == PolicyMode.BALANCED

    def test_balanced_blocking_enabled(self) -> None:
        """Balanced mode has blocking enabled."""
        assert POLICY_BALANCED.blocking_enabled is True

    def test_balanced_is_global(self) -> None:
        """Balanced preset has tenant_id=None (global)."""
        assert POLICY_BALANCED.tenant_id is None

    def test_balanced_policy_id(self) -> None:
        """Balanced preset has policy_id 'balanced'."""
        assert POLICY_BALANCED.policy_id == "balanced"

    def test_balanced_blocks_high_severity(self) -> None:
        """Balanced blocks HIGH and above."""
        assert POLICY_BALANCED.block_severity_threshold == "HIGH"

    def test_balanced_high_confidence_threshold(self) -> None:
        """Balanced requires 0.85 confidence for blocking."""
        assert POLICY_BALANCED.block_confidence_threshold == 0.85

    def test_balanced_standard_telemetry(self) -> None:
        """Balanced mode has standard telemetry."""
        assert POLICY_BALANCED.telemetry_detail == "standard"


class TestStrictPreset:
    """Tests for POLICY_STRICT preset."""

    def test_strict_is_tenant_policy(self) -> None:
        """POLICY_STRICT is a TenantPolicy instance."""
        assert isinstance(POLICY_STRICT, TenantPolicy)

    def test_strict_mode(self) -> None:
        """Strict preset has STRICT mode."""
        assert POLICY_STRICT.mode == PolicyMode.STRICT

    def test_strict_blocking_enabled(self) -> None:
        """Strict mode has blocking enabled."""
        assert POLICY_STRICT.blocking_enabled is True

    def test_strict_is_global(self) -> None:
        """Strict preset has tenant_id=None (global)."""
        assert POLICY_STRICT.tenant_id is None

    def test_strict_policy_id(self) -> None:
        """Strict preset has policy_id 'strict'."""
        assert POLICY_STRICT.policy_id == "strict"

    def test_strict_blocks_medium_severity(self) -> None:
        """Strict blocks MEDIUM and above."""
        assert POLICY_STRICT.block_severity_threshold == "MEDIUM"

    def test_strict_lower_confidence_threshold(self) -> None:
        """Strict has lower confidence threshold (0.5) for more aggressive blocking."""
        assert POLICY_STRICT.block_confidence_threshold == 0.5

    def test_strict_verbose_telemetry(self) -> None:
        """Strict mode has verbose telemetry for maximum visibility."""
        assert POLICY_STRICT.telemetry_detail == "verbose"


class TestGlobalPresets:
    """Tests for GLOBAL_PRESETS dictionary."""

    def test_global_presets_contains_monitor(self) -> None:
        """GLOBAL_PRESETS contains 'monitor' key."""
        assert "monitor" in GLOBAL_PRESETS
        assert GLOBAL_PRESETS["monitor"] is POLICY_MONITOR

    def test_global_presets_contains_balanced(self) -> None:
        """GLOBAL_PRESETS contains 'balanced' key."""
        assert "balanced" in GLOBAL_PRESETS
        assert GLOBAL_PRESETS["balanced"] is POLICY_BALANCED

    def test_global_presets_contains_strict(self) -> None:
        """GLOBAL_PRESETS contains 'strict' key."""
        assert "strict" in GLOBAL_PRESETS
        assert GLOBAL_PRESETS["strict"] is POLICY_STRICT

    def test_global_presets_has_exactly_three(self) -> None:
        """GLOBAL_PRESETS has exactly 3 presets."""
        assert len(GLOBAL_PRESETS) == 3

    def test_all_presets_are_immutable(self) -> None:
        """All presets are frozen (immutable)."""
        from dataclasses import FrozenInstanceError

        for preset in GLOBAL_PRESETS.values():
            with pytest.raises(FrozenInstanceError):
                preset.name = "Changed"  # type: ignore[misc]

    def test_all_presets_are_global(self) -> None:
        """All presets have tenant_id=None."""
        for preset in GLOBAL_PRESETS.values():
            assert preset.tenant_id is None, f"Preset {preset.policy_id} should be global"
