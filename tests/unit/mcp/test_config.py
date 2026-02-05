"""Unit tests for MCP Gateway configuration."""

from __future__ import annotations

import os
import tempfile

from raxe.mcp.config import GatewayConfig, PolicyConfig, UpstreamConfig


class TestPolicyConfig:
    """Tests for PolicyConfig dataclass."""

    def test_default_values(self):
        """Test that default values are safe (log, not block)."""
        policy = PolicyConfig()

        assert policy.on_threat == "log"
        assert policy.severity_threshold == "HIGH"
        assert policy.rate_limit_rpm == 60

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "on_threat": "block",
            "severity_threshold": "CRITICAL",
            "rate_limit_rpm": 120,
        }

        policy = PolicyConfig.from_dict(data)

        assert policy.on_threat == "block"
        assert policy.severity_threshold == "CRITICAL"
        assert policy.rate_limit_rpm == 120

    def test_from_dict_with_defaults(self):
        """Test creation from partial dictionary uses defaults."""
        data = {"on_threat": "warn"}

        policy = PolicyConfig.from_dict(data)

        assert policy.on_threat == "warn"
        assert policy.severity_threshold == "HIGH"  # default
        assert policy.rate_limit_rpm == 60  # default


class TestUpstreamConfig:
    """Tests for UpstreamConfig dataclass."""

    def test_default_scan_settings(self):
        """Test that default scan settings are enabled."""
        upstream = UpstreamConfig(name="test", command="echo")

        assert upstream.scan_tool_calls is True
        assert upstream.scan_tool_responses is True
        assert upstream.scan_resources is True
        assert upstream.scan_prompts is True

    def test_from_dict_minimal(self):
        """Test creation from minimal dictionary."""
        data = {
            "name": "filesystem",
            "command": "npx",
            "args": ["@modelcontextprotocol/server-filesystem", "/data"],
        }

        upstream = UpstreamConfig.from_dict(data)

        assert upstream.name == "filesystem"
        assert upstream.command == "npx"
        assert upstream.args == ["@modelcontextprotocol/server-filesystem", "/data"]
        assert upstream.policy is None

    def test_from_dict_with_policy(self):
        """Test creation with nested policy."""
        data = {
            "name": "secure",
            "command": "server",
            "policy": {
                "on_threat": "block",
                "severity_threshold": "MEDIUM",
            },
        }

        upstream = UpstreamConfig.from_dict(data)

        assert upstream.policy is not None
        assert upstream.policy.on_threat == "block"
        assert upstream.policy.severity_threshold == "MEDIUM"

    def test_from_dict_with_env(self):
        """Test creation with environment variables."""
        data = {
            "name": "with-env",
            "command": "server",
            "env": {
                "API_KEY": "test-key",
                "DEBUG": "true",
            },
        }

        upstream = UpstreamConfig.from_dict(data)

        assert upstream.env == {"API_KEY": "test-key", "DEBUG": "true"}


class TestGatewayConfig:
    """Tests for GatewayConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = GatewayConfig()

        assert config.listen_transport == "stdio"
        assert config.listen_port == 8080
        assert config.listen_host == "127.0.0.1"
        assert config.upstreams == []
        assert config.telemetry_enabled is True
        assert config.l2_enabled is True

    def test_default_policy_is_safe(self):
        """Test that default policy is log-only (safe)."""
        config = GatewayConfig()

        assert config.default_policy.on_threat == "log"
        assert config.default_policy.severity_threshold == "HIGH"

    def test_load_from_yaml_file(self):
        """Test loading configuration from YAML file."""
        yaml_content = """
gateway:
  listen: stdio
  telemetry_enabled: false
  l2_enabled: false
  default_policy:
    on_threat: block
    severity_threshold: CRITICAL

upstreams:
  - name: test-server
    command: echo
    args: ["hello"]
    scan_tool_calls: true
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = GatewayConfig.load(f.name)

                assert config.listen_transport == "stdio"
                assert config.telemetry_enabled is False
                assert config.l2_enabled is False
                assert config.default_policy.on_threat == "block"
                assert config.default_policy.severity_threshold == "CRITICAL"
                assert len(config.upstreams) == 1
                assert config.upstreams[0].name == "test-server"
            finally:
                os.unlink(f.name)

    def test_env_override(self, monkeypatch):
        """Test that environment variables override config."""
        monkeypatch.setenv("RAXE_MCP_GATEWAY_PORT", "9090")
        monkeypatch.setenv("RAXE_MCP_GATEWAY_TELEMETRY", "false")
        monkeypatch.setenv("RAXE_MCP_GATEWAY_ON_THREAT", "block")

        # Create empty config file to avoid loading defaults
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("gateway:\n  listen: stdio\n")
            f.flush()

            try:
                config = GatewayConfig.load(f.name)

                assert config.listen_port == 9090
                assert config.telemetry_enabled is False
                assert config.default_policy.on_threat == "block"
            finally:
                os.unlink(f.name)

    def test_to_dict_safe_for_logging(self):
        """Test that to_dict doesn't expose sensitive data."""
        config = GatewayConfig(
            upstreams=[
                UpstreamConfig(
                    name="test",
                    command="server",
                    env={"SECRET_KEY": "super-secret"},
                )
            ]
        )

        safe_dict = config.to_dict()

        # Should not contain env secrets
        assert "SECRET_KEY" not in str(safe_dict)
        assert "super-secret" not in str(safe_dict)

        # Should contain safe info
        assert safe_dict["upstreams_count"] == 1
        assert safe_dict["listen_transport"] == "stdio"

    def test_load_nonexistent_file_returns_defaults(self):
        """Test that loading nonexistent file returns defaults."""
        config = GatewayConfig.load("/nonexistent/path/config.yaml")

        # Should get default values
        assert config.listen_transport == "stdio"
        assert config.default_policy.on_threat == "log"
