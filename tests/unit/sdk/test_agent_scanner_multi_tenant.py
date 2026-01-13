"""TDD Tests for AgentScanner multi-tenant support.

Tests verify that tenant_id, app_id, and policy_id parameters:
1. Exist in AgentScannerConfig
2. Are passed through to Raxe.scan() calls
3. Work with create_agent_scanner factory
"""

from unittest.mock import Mock

import pytest

from raxe.sdk.agent_scanner import (
    AgentScannerConfig,
    create_agent_scanner,
)


@pytest.fixture
def mock_raxe():
    """Create mock Raxe client for testing."""
    raxe = Mock()
    result = Mock()
    result.has_threats = False
    result.severity = None
    result.total_detections = 0
    result.rule_ids = []
    raxe.scan = Mock(return_value=result)
    return raxe


class TestAgentScannerConfigTenantFields:
    """Test tenant fields in AgentScannerConfig."""

    def test_config_has_tenant_id_field(self):
        """AgentScannerConfig should have optional tenant_id field."""
        config = AgentScannerConfig(tenant_id="acme")
        assert config.tenant_id == "acme"

    def test_config_has_app_id_field(self):
        """AgentScannerConfig should have optional app_id field."""
        config = AgentScannerConfig(app_id="chatbot")
        assert config.app_id == "chatbot"

    def test_config_has_policy_id_field(self):
        """AgentScannerConfig should have optional policy_id field."""
        config = AgentScannerConfig(policy_id="strict")
        assert config.policy_id == "strict"

    def test_config_tenant_fields_default_to_none(self):
        """Tenant fields should default to None (backward compatible)."""
        config = AgentScannerConfig()
        assert config.tenant_id is None
        assert config.app_id is None
        assert config.policy_id is None

    def test_config_all_tenant_fields_together(self):
        """All tenant fields can be set together."""
        config = AgentScannerConfig(
            tenant_id="acme",
            app_id="chatbot",
            policy_id="custom-strict",
        )
        assert config.tenant_id == "acme"
        assert config.app_id == "chatbot"
        assert config.policy_id == "custom-strict"


class TestAgentScannerTenantPassthrough:
    """Test that AgentScanner passes tenant params to Raxe.scan()."""

    def test_scan_prompt_passes_tenant_id(self, mock_raxe):
        """scan_prompt should pass tenant_id to underlying Raxe.scan()."""
        config = AgentScannerConfig(tenant_id="acme")
        scanner = create_agent_scanner(mock_raxe, config)

        scanner.scan_prompt("test prompt")

        mock_raxe.scan.assert_called()
        call_kwargs = mock_raxe.scan.call_args.kwargs
        assert call_kwargs.get("tenant_id") == "acme"

    def test_scan_prompt_passes_app_id(self, mock_raxe):
        """scan_prompt should pass app_id to underlying Raxe.scan()."""
        config = AgentScannerConfig(app_id="chatbot")
        scanner = create_agent_scanner(mock_raxe, config)

        scanner.scan_prompt("test prompt")

        call_kwargs = mock_raxe.scan.call_args.kwargs
        assert call_kwargs.get("app_id") == "chatbot"

    def test_scan_prompt_passes_policy_id(self, mock_raxe):
        """scan_prompt should pass policy_id to underlying Raxe.scan()."""
        config = AgentScannerConfig(policy_id="strict")
        scanner = create_agent_scanner(mock_raxe, config)

        scanner.scan_prompt("test prompt")

        call_kwargs = mock_raxe.scan.call_args.kwargs
        assert call_kwargs.get("policy_id") == "strict"

    def test_scan_prompt_passes_all_tenant_params(self, mock_raxe):
        """scan_prompt should pass all tenant params together."""
        config = AgentScannerConfig(
            tenant_id="acme",
            app_id="chatbot",
            policy_id="strict",
        )
        scanner = create_agent_scanner(mock_raxe, config)

        scanner.scan_prompt("test prompt")

        call_kwargs = mock_raxe.scan.call_args.kwargs
        assert call_kwargs.get("tenant_id") == "acme"
        assert call_kwargs.get("app_id") == "chatbot"
        assert call_kwargs.get("policy_id") == "strict"

    def test_scan_response_passes_tenant_params(self, mock_raxe):
        """scan_response should pass all tenant params."""
        config = AgentScannerConfig(
            tenant_id="acme",
            app_id="chatbot",
            policy_id="strict",
        )
        scanner = create_agent_scanner(mock_raxe, config)

        scanner.scan_response("test response")

        call_kwargs = mock_raxe.scan.call_args.kwargs
        assert call_kwargs.get("tenant_id") == "acme"
        assert call_kwargs.get("app_id") == "chatbot"
        assert call_kwargs.get("policy_id") == "strict"

    def test_scan_tool_result_passes_tenant_params(self, mock_raxe):
        """scan_tool_result should pass tenant params."""
        config = AgentScannerConfig(tenant_id="acme")
        scanner = create_agent_scanner(mock_raxe, config)

        scanner.scan_tool_result("search", "Search result content")

        call_kwargs = mock_raxe.scan.call_args.kwargs
        assert call_kwargs.get("tenant_id") == "acme"


class TestCreateAgentScannerFactory:
    """Test create_agent_scanner factory with tenant params."""

    def test_factory_passes_config_tenant_params(self, mock_raxe):
        """Factory should pass config tenant params to scanner."""
        config = AgentScannerConfig(
            tenant_id="acme",
            app_id="chatbot",
            policy_id="strict",
        )
        scanner = create_agent_scanner(
            mock_raxe,
            config,
            integration_type="langchain",
        )

        # Verify config was passed through
        assert scanner.config.tenant_id == "acme"
        assert scanner.config.app_id == "chatbot"
        assert scanner.config.policy_id == "strict"


class TestBackwardCompatibility:
    """Test backward compatibility - existing code should work unchanged."""

    def test_scanner_works_without_tenant_params(self, mock_raxe):
        """Scanner should work without any tenant parameters (default None)."""
        config = AgentScannerConfig()
        scanner = create_agent_scanner(mock_raxe, config)

        # Should not raise
        scanner.scan_prompt("test prompt")

        # Verify scan was called
        mock_raxe.scan.assert_called()

    def test_factory_works_without_tenant_params(self, mock_raxe):
        """Factory should work without tenant parameters."""
        scanner = create_agent_scanner(
            mock_raxe,
            AgentScannerConfig(),
            integration_type="langchain",
        )

        # Should not raise
        scanner.scan_prompt("test prompt")
