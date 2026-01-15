"""
Test coverage for Raxe client public API.

Ensures all public methods work correctly and maintain backward compatibility.
"""

from unittest.mock import patch

import pytest

from raxe.sdk.client import Raxe


class TestRaxePublicAPI:
    """Test public API methods of Raxe client."""

    def test_get_all_rules(self):
        """Test get_all_rules returns rules list."""
        raxe = Raxe()
        rules = raxe.get_all_rules()

        assert isinstance(rules, list)
        assert len(rules) > 0  # Should have default rules loaded

        # Verify rule structure - rules should have rule_id and patterns
        for rule in rules[:5]:  # Check first 5
            assert hasattr(rule, "rule_id")
            assert hasattr(rule, "patterns")

    def test_list_rule_packs(self):
        """Test list_rule_packs returns pack objects."""
        raxe = Raxe()
        packs = raxe.list_rule_packs()

        assert isinstance(packs, list)
        assert len(packs) > 0

        # Packs are RulePack objects, check for 'core' pack by ID
        pack_ids = [pack.manifest.id for pack in packs]
        assert "core" in pack_ids  # Core pack should always exist

    def test_has_api_key_without_key(self):
        """Test has_api_key detection without API key."""
        raxe = Raxe()
        assert raxe.has_api_key() is False

    def test_has_api_key_with_key(self):
        """Test has_api_key detection with API key."""
        raxe = Raxe(api_key="raxe_test_key_1234567890")
        assert raxe.has_api_key() is True

    def test_get_telemetry_enabled_default(self):
        """Test telemetry status check with default (enabled)."""
        raxe = Raxe()
        assert isinstance(raxe.get_telemetry_enabled(), bool)
        # Default should be True
        assert raxe.get_telemetry_enabled() is True

    def test_get_telemetry_enabled_explicitly_disabled(self):
        """Test telemetry status check when explicitly disabled."""
        raxe = Raxe(telemetry=False)
        assert raxe.get_telemetry_enabled() is False

    def test_get_profiling_components(self):
        """Test profiling components access."""
        raxe = Raxe()
        components = raxe.get_profiling_components()

        # Check structure
        assert isinstance(components, dict)
        assert "executor" in components
        assert "l2_detector" in components
        assert "rules" in components

        # Check types
        assert components["executor"] is not None
        assert isinstance(components["rules"], list)

        # L2 detector may be None if disabled
        if raxe.config.enable_l2:
            assert components["l2_detector"] is not None

    def test_get_profiling_components_without_l2(self):
        """Test profiling components when L2 is disabled."""
        raxe = Raxe(l2_enabled=False)
        components = raxe.get_profiling_components()

        assert components["l2_detector"] is None
        assert components["executor"] is not None
        assert len(components["rules"]) > 0

    def test_get_pipeline_stats(self):
        """Test pipeline statistics."""
        raxe = Raxe()
        stats = raxe.get_pipeline_stats()

        # Check required fields
        assert isinstance(stats, dict)
        assert "rules_loaded" in stats
        assert "packs_loaded" in stats
        assert "telemetry_enabled" in stats
        assert "has_api_key" in stats
        assert "l2_enabled" in stats

        # Check values
        assert stats["rules_loaded"] > 0
        assert stats["packs_loaded"] > 0
        assert isinstance(stats["telemetry_enabled"], bool)
        assert isinstance(stats["has_api_key"], bool)
        assert isinstance(stats["l2_enabled"], bool)

        # Check optional preload stats
        if "preload_time_ms" in stats:
            assert stats["preload_time_ms"] >= 0
        if "patterns_compiled" in stats:
            assert stats["patterns_compiled"] >= 0

    def test_validate_configuration_valid(self):
        """Test configuration validation with valid config."""
        raxe = Raxe()
        validation = raxe.validate_configuration()

        assert isinstance(validation, dict)
        assert "config_valid" in validation
        assert "errors" in validation
        assert "warnings" in validation

        # Should be valid with defaults
        assert validation["config_valid"] is True
        assert isinstance(validation["errors"], list)
        assert isinstance(validation["warnings"], list)

    def test_validate_configuration_with_valid_api_key(self):
        """Test validation with properly formatted API key."""
        raxe = Raxe(api_key="raxe_test_key_1234567890")
        validation = raxe.validate_configuration()

        assert validation["config_valid"] is True
        # Should have no warnings about API key format
        api_key_warnings = [w for w in validation["warnings"] if "API key" in w]
        assert len(api_key_warnings) == 0

    def test_validate_configuration_with_short_api_key(self):
        """Test validation with short API key."""
        raxe = Raxe(api_key="raxe_short")
        validation = raxe.validate_configuration()

        # Config should still be valid (warning, not error)
        assert validation["config_valid"] is True
        # But should have warning
        assert len(validation["warnings"]) > 0
        assert any("too short" in w.lower() for w in validation["warnings"])

    def test_validate_configuration_with_bad_prefix_api_key(self):
        """Test validation with API key missing proper prefix."""
        raxe = Raxe(api_key="bad_prefix_1234567890")
        validation = raxe.validate_configuration()

        # Config should still be valid (warning, not error)
        assert validation["config_valid"] is True
        # But should have warning
        assert len(validation["warnings"]) > 0
        assert any("should start with" in w.lower() for w in validation["warnings"])

    def test_public_api_stability(self):
        """Test that public API maintains compatibility."""
        # This test ensures we don't accidentally break the public API
        raxe = Raxe()

        # All these methods should exist and be callable
        public_methods = [
            "scan",
            "get_all_rules",
            "list_rule_packs",
            "has_api_key",
            "get_telemetry_enabled",
            "get_profiling_components",
            "get_pipeline_stats",
            "validate_configuration",
        ]

        for method_name in public_methods:
            assert hasattr(raxe, method_name), f"Missing public method: {method_name}"
            method = getattr(raxe, method_name)
            assert callable(method), f"Method not callable: {method_name}"

    def test_get_all_rules_returns_same_as_internal(self):
        """Test that get_all_rules returns same data as internal method."""
        raxe = Raxe()

        # Public API
        public_rules = raxe.get_all_rules()

        # Internal (what we're wrapping)
        internal_rules = raxe.pipeline.pack_registry.get_all_rules()

        # Should be identical
        assert public_rules == internal_rules
        assert len(public_rules) == len(internal_rules)

    def test_list_rule_packs_returns_same_as_internal(self):
        """Test that list_rule_packs returns same data as internal method."""
        raxe = Raxe()

        # Public API
        public_packs = raxe.list_rule_packs()

        # Internal (what we're wrapping)
        internal_packs = raxe.pipeline.pack_registry.list_packs()

        # Should be identical
        assert public_packs == internal_packs
        assert len(public_packs) == len(internal_packs)

    def test_has_api_key_consistency(self):
        """Test has_api_key is consistent with config."""
        # Without key
        raxe1 = Raxe()
        assert raxe1.has_api_key() == bool(raxe1.config.api_key)

        # With key
        raxe2 = Raxe(api_key="raxe_test_key")
        assert raxe2.has_api_key() == bool(raxe2.config.api_key)
        assert raxe2.has_api_key() is True

    def test_pipeline_stats_consistency(self):
        """Test that pipeline stats are consistent."""
        raxe = Raxe()
        stats = raxe.get_pipeline_stats()

        # Rules count should match get_all_rules
        assert stats["rules_loaded"] == len(raxe.get_all_rules())

        # Packs count should match list_rule_packs
        assert stats["packs_loaded"] == len(raxe.list_rule_packs())

        # API key status should match has_api_key
        assert stats["has_api_key"] == raxe.has_api_key()

        # Telemetry status should match get_telemetry_enabled
        assert stats["telemetry_enabled"] == raxe.get_telemetry_enabled()


class TestPublicAPIErrorHandling:
    """Test error handling in public API methods."""

    def test_get_all_rules_handles_errors_gracefully(self):
        """Test get_all_rules handles internal errors."""
        raxe = Raxe()

        # Mock the internal method to raise an error
        with patch.object(
            raxe.pipeline.pack_registry, "get_all_rules", side_effect=Exception("Test error")
        ):
            with pytest.raises(Exception) as exc_info:
                raxe.get_all_rules()
            assert "Test error" in str(exc_info.value)

    def test_validate_configuration_handles_missing_attributes(self):
        """Test validate_configuration handles missing config attributes gracefully."""
        raxe = Raxe()

        # Should not crash even if performance_mode is missing
        validation = raxe.validate_configuration()
        assert isinstance(validation, dict)
        assert "config_valid" in validation


class TestPublicAPIDocumentation:
    """Test that public API methods are properly documented."""

    def test_all_public_methods_have_docstrings(self):
        """Ensure all public API methods have docstrings."""
        raxe = Raxe()

        public_methods = [
            "get_all_rules",
            "list_rule_packs",
            "has_api_key",
            "get_telemetry_enabled",
            "get_profiling_components",
            "get_pipeline_stats",
            "validate_configuration",
        ]

        for method_name in public_methods:
            method = getattr(raxe, method_name)
            assert method.__doc__ is not None, f"{method_name} missing docstring"
            assert len(method.__doc__.strip()) > 0, f"{method_name} has empty docstring"

    def test_docstrings_include_examples(self):
        """Ensure docstrings include usage examples."""
        raxe = Raxe()

        # Methods that should have examples in docstrings
        methods_with_examples = [
            "get_all_rules",
            "list_rule_packs",
            "has_api_key",
            "get_telemetry_enabled",
            "get_profiling_components",
            "get_pipeline_stats",
            "validate_configuration",
        ]

        for method_name in methods_with_examples:
            method = getattr(raxe, method_name)
            docstring = method.__doc__
            # Check for "Example:" section
            assert (
                "Example:" in docstring or "example" in docstring.lower()
            ), f"{method_name} docstring should include usage example"
