"""Tests for centralized endpoint configuration module.

This module tests the endpoint configuration system including:
- Environment detection from API keys and environment variables
- Endpoint resolution for different environments
- Override behavior with explicit endpoints and env vars
- Convenience functions for specific endpoint types
"""

from __future__ import annotations

import os
from unittest.mock import patch

from raxe.infrastructure.config.endpoints import (
    Endpoint,
    Environment,
    detect_environment,
    get_all_endpoints,
    get_api_base,
    get_cli_session_endpoint,
    get_console_url,
    get_endpoint,
    get_health_endpoint,
    get_telemetry_endpoint,
    reset_all,
    set_environment,
)

# =============================================================================
# Environment Detection Tests
# =============================================================================


class TestEnvironmentDetection:
    """Tests for environment detection logic."""

    def test_default_environment_is_production(self) -> None:
        """Default environment should be production when no signals present."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {}, clear=True):
            env = detect_environment()
            assert env == Environment.PRODUCTION

    def test_raxe_env_takes_precedence(self) -> None:
        """RAXE_ENV environment variable takes precedence over API key detection."""
        reset_all()  # Clear cached state
        with patch.dict(
            os.environ, {"RAXE_ENV": "production", "RAXE_API_KEY": "raxe_temp_xxx"}, clear=True
        ):
            env = detect_environment()
            assert env == Environment.PRODUCTION

    def test_detects_production_from_live_key(self) -> None:
        """Detect production environment from raxe_live_ API key prefix."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_API_KEY": "raxe_live_abc123def456"}, clear=True):
            env = detect_environment()
            assert env == Environment.PRODUCTION

    def test_detects_production_from_temp_key(self) -> None:
        """Detect production environment from raxe_temp_ API key prefix (fresh installs)."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_API_KEY": "raxe_temp_abc123def456"}, clear=True):
            env = detect_environment()
            assert env == Environment.PRODUCTION

    def test_detects_test_from_test_key(self) -> None:
        """Detect test environment from raxe_test_ API key prefix."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_API_KEY": "raxe_test_abc123def456"}, clear=True):
            env = detect_environment()
            assert env == Environment.TEST

    def test_environment_case_insensitive(self) -> None:
        """Environment names are case-insensitive."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_ENV": "PRODUCTION"}, clear=True):
            env = detect_environment()
            assert env == Environment.PRODUCTION

        reset_all()  # Clear cached state for second assertion
        with patch.dict(os.environ, {"RAXE_ENV": "Development"}, clear=True):
            env = detect_environment()
            assert env == Environment.DEVELOPMENT


# =============================================================================
# Endpoint Resolution Tests
# =============================================================================


class TestEndpointResolution:
    """Tests for endpoint URL resolution."""

    def test_production_endpoints(self) -> None:
        """Production environment returns api.beta.raxe.ai endpoints."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_ENV": "production"}, clear=True):
            telemetry = get_telemetry_endpoint()
            api_base = get_api_base()
            console = get_console_url()

            assert "api.beta.raxe.ai" in telemetry
            assert "api.beta.raxe.ai" in api_base
            assert "console.beta.raxe.ai" in console

    def test_development_endpoints(self) -> None:
        """Development environment returns beta.raxe.ai endpoints."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_ENV": "development"}, clear=True):
            telemetry = get_telemetry_endpoint()
            api_base = get_api_base()

            assert "api.beta.raxe.ai" in telemetry
            assert "/v1/telemetry" in telemetry
            assert "api.beta.raxe.ai" in api_base

    def test_local_endpoints(self) -> None:
        """Local environment returns localhost endpoints."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_ENV": "local"}, clear=True):
            telemetry = get_telemetry_endpoint()
            api_base = get_api_base()
            console = get_console_url()

            assert "localhost:8080" in telemetry
            assert "localhost:8080" in api_base
            assert "localhost:3000" in console

    def test_explicit_environment_override(self) -> None:
        """Explicitly passing environment overrides detection."""
        reset_all()  # Clear cached state
        # Even with production env var, explicit local should work
        with patch.dict(os.environ, {"RAXE_ENV": "production"}, clear=True):
            telemetry = get_telemetry_endpoint(environment=Environment.LOCAL)
            assert "localhost" in telemetry

    def test_get_all_endpoints(self) -> None:
        """get_all_endpoints returns dict with all endpoint types."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_ENV": "development"}, clear=True):
            endpoints = get_all_endpoints()

            assert "telemetry" in endpoints
            assert "api_base" in endpoints
            assert "console" in endpoints
            assert "health" in endpoints
            assert "policies" in endpoints
            assert "cli_session" in endpoints
            assert "cli_link" in endpoints


# =============================================================================
# Environment Override Tests
# =============================================================================


class TestEnvironmentOverride:
    """Tests for set_environment override functionality."""

    def test_set_environment_overrides_detection(self) -> None:
        """set_environment temporarily overrides environment detection."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_ENV": "production"}, clear=True):
            # Before override - will detect production
            assert detect_environment() == Environment.PRODUCTION

            # Set override to local
            set_environment(Environment.LOCAL)
            assert detect_environment() == Environment.LOCAL

            # Clear override - now it will return cached production value
            # (because we never cleared the cache, just set it to None)
            set_environment(None)
            reset_all()  # Need to clear cache to re-detect
            assert detect_environment() == Environment.PRODUCTION

    def test_set_environment_affects_endpoints(self) -> None:
        """set_environment affects all endpoint getters."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_ENV": "production"}, clear=True):
            set_environment(Environment.LOCAL)

            telemetry = get_telemetry_endpoint()
            assert "localhost" in telemetry

            # Clean up
            reset_all()


# =============================================================================
# Telemetry Endpoint Override Tests
# =============================================================================


class TestTelemetryEndpointOverride:
    """Tests for RAXE_TELEMETRY_ENDPOINT env var override."""

    def test_env_var_overrides_default(self) -> None:
        """RAXE_TELEMETRY_ENDPOINT overrides default endpoint."""
        reset_all()  # Clear cached state
        custom_endpoint = "https://custom.example.com/v1/telemetry"
        with patch.dict(
            os.environ,
            {"RAXE_TELEMETRY_ENDPOINT": custom_endpoint, "RAXE_ENV": "production"},
            clear=True,
        ):
            telemetry = get_telemetry_endpoint()
            assert telemetry == custom_endpoint

    def test_empty_env_var_uses_default(self) -> None:
        """Empty RAXE_TELEMETRY_ENDPOINT uses default."""
        reset_all()  # Clear cached state
        with patch.dict(
            os.environ, {"RAXE_TELEMETRY_ENDPOINT": "", "RAXE_ENV": "development"}, clear=True
        ):
            telemetry = get_telemetry_endpoint()
            assert "api.beta.raxe.ai" in telemetry


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for individual endpoint getter functions."""

    def test_get_health_endpoint(self) -> None:
        """get_health_endpoint returns correct URL."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_ENV": "development"}, clear=True):
            health = get_health_endpoint()
            assert "/v1/health" in health
            assert "api.beta.raxe.ai" in health

    def test_get_policy_endpoint(self) -> None:
        """Policies endpoint returns correct URL."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_ENV": "development"}, clear=True):
            policy = get_endpoint(Endpoint.POLICIES)
            assert "/v1/policies" in policy

    def test_get_cli_session_endpoint(self) -> None:
        """get_cli_session_endpoint returns correct URL."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_ENV": "development"}, clear=True):
            session = get_cli_session_endpoint()
            assert "/api/cli/session" in session
            assert "localhost:3000" in session

    def test_get_cli_link_endpoint(self) -> None:
        """CLI link endpoint returns correct URL."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_ENV": "development"}, clear=True):
            link = get_endpoint(Endpoint.CLI_LINK)
            assert "/cli/link" in link


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_unknown_environment_defaults_to_production(self) -> None:
        """Unknown RAXE_ENV value defaults to production."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_ENV": "unknown_env"}, clear=True):
            env = detect_environment()
            assert env == Environment.PRODUCTION

    def test_partial_api_key_ignored(self) -> None:
        """API key without proper prefix is ignored for detection."""
        reset_all()  # Clear cached state
        with patch.dict(os.environ, {"RAXE_API_KEY": "invalid_key_format"}, clear=True):
            env = detect_environment()
            # Should fall back to default (production)
            assert env == Environment.PRODUCTION

    def test_endpoint_enum_values(self) -> None:
        """Endpoint enum has expected values."""
        assert Endpoint.TELEMETRY.value == "telemetry"
        assert Endpoint.API_BASE.value == "api_base"
        assert Endpoint.CONSOLE.value == "console"
        assert Endpoint.HEALTH.value == "health"
        assert Endpoint.POLICIES.value == "policies"
        assert Endpoint.CLI_SESSION.value == "cli_session"
        assert Endpoint.CLI_LINK.value == "cli_link"

    def test_environment_enum_values(self) -> None:
        """Environment enum has expected values."""
        assert Environment.PRODUCTION.value == "production"
        assert Environment.STAGING.value == "staging"
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.TEST.value == "test"
        assert Environment.LOCAL.value == "local"
