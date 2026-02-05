"""MCP Gateway Configuration.

Configuration for the RAXE MCP Security Gateway that sits between
MCP clients and servers to scan all traffic for threats.

Configuration sources (in priority order):
1. CLI arguments
2. Environment variables (RAXE_MCP_GATEWAY_*)
3. Config file (mcp-security.yaml or ~/.raxe/mcp-gateway.yaml)
4. Default values
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml


@dataclass
class PolicyConfig:
    """Policy for handling threats detected by the gateway.

    Attributes:
        on_threat: Action to take when threat detected
        severity_threshold: Minimum severity to trigger action
        rate_limit_rpm: Requests per minute limit (0 = unlimited)
    """

    on_threat: Literal["log", "block", "warn"] = "log"
    severity_threshold: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "HIGH"
    rate_limit_rpm: int = 60

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicyConfig:
        """Create PolicyConfig from dictionary."""
        return cls(
            on_threat=data.get("on_threat", "log"),
            severity_threshold=data.get("severity_threshold", "HIGH"),
            rate_limit_rpm=data.get("rate_limit_rpm", 60),
        )


@dataclass
class UpstreamConfig:
    """Configuration for an upstream MCP server.

    Attributes:
        name: Human-readable name for the server
        command: Command to execute for stdio transport
        args: Arguments for the command
        url: URL for HTTP transport (mutually exclusive with command)
        scan_tool_calls: Whether to scan tool call arguments
        scan_tool_responses: Whether to scan tool responses
        scan_resources: Whether to scan resource content
        scan_prompts: Whether to scan prompt templates
        policy: Override policy for this upstream (None = use gateway default)
    """

    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    scan_tool_calls: bool = True
    scan_tool_responses: bool = True
    scan_resources: bool = True
    scan_prompts: bool = True
    policy: PolicyConfig | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UpstreamConfig:
        """Create UpstreamConfig from dictionary."""
        policy_data = data.get("policy")
        policy = PolicyConfig.from_dict(policy_data) if policy_data else None

        return cls(
            name=data.get("name", "unnamed"),
            command=data.get("command"),
            args=data.get("args", []),
            url=data.get("url"),
            env=data.get("env", {}),
            scan_tool_calls=data.get("scan_tool_calls", True),
            scan_tool_responses=data.get("scan_tool_responses", True),
            scan_resources=data.get("scan_resources", True),
            scan_prompts=data.get("scan_prompts", True),
            policy=policy,
        )


@dataclass
class GatewayConfig:
    """Configuration for the MCP Security Gateway.

    Attributes:
        listen_transport: Transport type for incoming connections
        listen_port: Port for HTTP transport
        listen_host: Host for HTTP transport
        upstreams: List of upstream server configurations
        default_policy: Default policy for all upstreams
        telemetry_enabled: Enable privacy-preserving telemetry
        l2_enabled: Enable L2 ML detection
        verbose: Enable verbose logging
    """

    listen_transport: Literal["stdio", "http"] = "stdio"
    listen_port: int = 8080
    listen_host: str = "127.0.0.1"
    upstreams: list[UpstreamConfig] = field(default_factory=list)
    default_policy: PolicyConfig = field(default_factory=PolicyConfig)
    telemetry_enabled: bool = True
    l2_enabled: bool = True
    verbose: bool = False

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> GatewayConfig:
        """Load configuration from file and environment.

        Args:
            config_path: Optional path to config file

        Returns:
            Loaded GatewayConfig instance
        """
        config = cls()

        # Try to load from file
        paths_to_try = []
        if config_path:
            paths_to_try.append(Path(config_path))
        paths_to_try.extend(
            [
                Path("mcp-security.yaml"),
                Path.home() / ".raxe" / "mcp-gateway.yaml",
            ]
        )

        for path in paths_to_try:
            if path.exists():
                config = cls._load_from_file(path)
                break

        # Override with environment variables
        config = cls._apply_env(config)

        return config

    @classmethod
    def _load_from_file(cls, path: Path) -> GatewayConfig:
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f) or {}

        gateway_data = data.get("gateway", data)

        # Parse upstreams
        upstreams = []
        for upstream_data in data.get("upstreams", []):
            upstreams.append(UpstreamConfig.from_dict(upstream_data))

        # Parse default policy
        policy_data = gateway_data.get("default_policy", {})
        default_policy = PolicyConfig.from_dict(policy_data)

        return cls(
            listen_transport=gateway_data.get("listen", "stdio"),
            listen_port=gateway_data.get("port", 8080),
            listen_host=gateway_data.get("host", "127.0.0.1"),
            upstreams=upstreams,
            default_policy=default_policy,
            telemetry_enabled=gateway_data.get("telemetry_enabled", True),
            l2_enabled=gateway_data.get("l2_enabled", True),
            verbose=gateway_data.get("verbose", False),
        )

    @classmethod
    def _apply_env(cls, config: GatewayConfig) -> GatewayConfig:
        """Apply environment variable overrides."""
        if env_port := os.environ.get("RAXE_MCP_GATEWAY_PORT"):
            config.listen_port = int(env_port)

        if env_host := os.environ.get("RAXE_MCP_GATEWAY_HOST"):
            config.listen_host = env_host

        if env_telemetry := os.environ.get("RAXE_MCP_GATEWAY_TELEMETRY"):
            config.telemetry_enabled = env_telemetry.lower() in ("true", "1", "yes")

        if env_l2 := os.environ.get("RAXE_MCP_GATEWAY_L2"):
            config.l2_enabled = env_l2.lower() in ("true", "1", "yes")

        if env_on_threat := os.environ.get("RAXE_MCP_GATEWAY_ON_THREAT"):
            if env_on_threat in ("log", "block", "warn"):
                config.default_policy.on_threat = env_on_threat  # type: ignore[assignment]

        if env_threshold := os.environ.get("RAXE_MCP_GATEWAY_SEVERITY_THRESHOLD"):
            if env_threshold in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
                config.default_policy.severity_threshold = env_threshold  # type: ignore[assignment]

        return config

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (safe for logging)."""
        return {
            "listen_transport": self.listen_transport,
            "listen_port": self.listen_port,
            "listen_host": self.listen_host,
            "upstreams_count": len(self.upstreams),
            "default_policy": {
                "on_threat": self.default_policy.on_threat,
                "severity_threshold": self.default_policy.severity_threshold,
            },
            "telemetry_enabled": self.telemetry_enabled,
            "l2_enabled": self.l2_enabled,
        }
