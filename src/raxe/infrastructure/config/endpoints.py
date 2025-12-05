"""
Centralized endpoint configuration for RAXE CLI.

This module provides a single source of truth for all API endpoints used by the CLI.
It supports multiple environments (dev, staging, prod) and provides easy override
mechanisms for developers and enterprise deployments.

Configuration Priority (highest to lowest):
1. Explicit override via set_endpoint() at runtime
2. Environment variables (RAXE_API_BASE, RAXE_TELEMETRY_ENDPOINT, etc.)
3. Config file (~/.raxe/config.yaml or ~/.raxe/endpoints.yaml)
4. Environment detection (based on existing API key prefix)
5. Default values (production endpoints)

Usage:
    from raxe.infrastructure.config.endpoints import get_endpoint, Endpoint, Environment

    # Get telemetry endpoint for current environment
    url = get_endpoint(Endpoint.TELEMETRY)

    # Get endpoint for specific environment
    url = get_endpoint(Endpoint.TELEMETRY, environment=Environment.DEVELOPMENT)

    # Override endpoint at runtime
    set_endpoint(Endpoint.TELEMETRY, "https://custom.api.example.com/v1/telemetry")

    # Test connectivity
    status = test_endpoint(Endpoint.TELEMETRY)
"""

import logging
import os
import socket
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class Environment(Enum):
    """RAXE deployment environments."""
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    TEST = "test"  # For unit testing (local mocks)
    LOCAL = "local"  # For local development server


class Endpoint(Enum):
    """Available API endpoints."""
    API_BASE = "api_base"
    TELEMETRY = "telemetry"
    HEALTH = "health"
    POLICIES = "policies"
    CONSOLE = "console"
    CLI_SESSION = "cli_session"
    CLI_LINK = "cli_link"


# ============================================================================
# Environment-Specific Endpoint Defaults
# ============================================================================

_ENDPOINT_DEFAULTS: dict[Environment, dict[Endpoint, str]] = {
    Environment.PRODUCTION: {
        Endpoint.API_BASE: "https://api.beta.raxe.ai",
        Endpoint.TELEMETRY: "https://api.beta.raxe.ai/v1/telemetry",
        Endpoint.HEALTH: "https://api.beta.raxe.ai/v1/health",
        Endpoint.POLICIES: "https://api.beta.raxe.ai/v1/policies",
        Endpoint.CONSOLE: "https://console.beta.raxe.ai",
        Endpoint.CLI_SESSION: "https://console.beta.raxe.ai/api/cli/session",
        Endpoint.CLI_LINK: "https://console.beta.raxe.ai/api/cli/link",
    },
    Environment.DEVELOPMENT: {
        Endpoint.API_BASE: "https://api.beta.raxe.ai",
        Endpoint.TELEMETRY: "https://api.beta.raxe.ai/v1/telemetry",
        Endpoint.HEALTH: "https://api.beta.raxe.ai/v1/health",
        Endpoint.POLICIES: "https://api.beta.raxe.ai/v1/policies",
        Endpoint.CONSOLE: "http://localhost:3000",
        Endpoint.CLI_SESSION: "http://localhost:3000/api/cli/session",
        Endpoint.CLI_LINK: "http://localhost:3000/api/cli/link",
    },
    Environment.LOCAL: {
        Endpoint.API_BASE: "http://localhost:8080",
        Endpoint.TELEMETRY: "http://localhost:8080/v1/telemetry",
        Endpoint.HEALTH: "http://localhost:8080/v1/health",
        Endpoint.POLICIES: "http://localhost:8080/v1/policies",
        Endpoint.CONSOLE: "http://localhost:3000",
        Endpoint.CLI_SESSION: "http://localhost:3000/api/cli/session",
        Endpoint.CLI_LINK: "http://localhost:3000/api/cli/link",
    },
    Environment.TEST: {
        Endpoint.API_BASE: "http://localhost:8080",
        Endpoint.TELEMETRY: "http://localhost:8080/v1/telemetry",
        Endpoint.HEALTH: "http://localhost:8080/v1/health",
        Endpoint.POLICIES: "http://localhost:8080/v1/policies",
        Endpoint.CONSOLE: "http://localhost:3000",
        Endpoint.CLI_SESSION: "http://localhost:3000/api/cli/session",
        Endpoint.CLI_LINK: "http://localhost:3000/api/cli/link",
    },
    Environment.STAGING: {
        Endpoint.API_BASE: "https://api.beta.raxe.ai",
        Endpoint.TELEMETRY: "https://api.beta.raxe.ai/v1/telemetry",
        Endpoint.HEALTH: "https://api.beta.raxe.ai/v1/health",
        Endpoint.POLICIES: "https://api.beta.raxe.ai/v1/policies",
        Endpoint.CONSOLE: "https://console.beta.raxe.ai",
        Endpoint.CLI_SESSION: "https://console.beta.raxe.ai/api/cli/session",
        Endpoint.CLI_LINK: "https://console.beta.raxe.ai/api/cli/link",
    },
}

# Environment variable names for endpoint overrides
_ENV_VAR_MAPPING: dict[Endpoint, str] = {
    Endpoint.API_BASE: "RAXE_API_BASE",
    Endpoint.TELEMETRY: "RAXE_TELEMETRY_ENDPOINT",
    Endpoint.HEALTH: "RAXE_HEALTH_ENDPOINT",
    Endpoint.POLICIES: "RAXE_POLICIES_ENDPOINT",
    Endpoint.CONSOLE: "RAXE_CONSOLE_URL",
    Endpoint.CLI_SESSION: "RAXE_CLI_SESSION_ENDPOINT",
    Endpoint.CLI_LINK: "RAXE_CLI_LINK_ENDPOINT",
}


# ============================================================================
# Runtime State
# ============================================================================

@dataclass
class _EndpointState:
    """Internal state for endpoint configuration."""
    overrides: dict[Endpoint, str]
    detected_environment: Environment | None
    config_file_path: Path | None

    def __init__(self) -> None:
        self.overrides = {}
        self.detected_environment = None
        self.config_file_path = None


_state = _EndpointState()


# ============================================================================
# Environment Detection
# ============================================================================

def detect_environment() -> Environment:
    """
    Detect the current environment based on available signals.

    Detection priority:
    1. RAXE_ENV environment variable
    2. Config file (~/.raxe/config.yaml core.environment)
    3. API key prefix (raxe_test_ -> TEST, etc.)
    4. Default to DEVELOPMENT

    Returns:
        Detected Environment
    """
    # Check cached value
    if _state.detected_environment is not None:
        return _state.detected_environment

    env_map = {
        "production": Environment.PRODUCTION,
        "prod": Environment.PRODUCTION,
        "staging": Environment.STAGING,
        "stage": Environment.STAGING,
        "development": Environment.DEVELOPMENT,
        "dev": Environment.DEVELOPMENT,
        "test": Environment.TEST,
        "testing": Environment.TEST,
        "local": Environment.LOCAL,
    }

    # 1. Check RAXE_ENV environment variable
    env_str = os.environ.get("RAXE_ENV", "").lower()
    if env_str and env_str in env_map:
        _state.detected_environment = env_map[env_str]
        logger.debug(f"Environment detected from RAXE_ENV: {_state.detected_environment.value}")
        return _state.detected_environment

    # 2. Check config file
    config_path = Path.home() / ".raxe" / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
            config_env = config.get("core", {}).get("environment", "").lower()
            if config_env and config_env in env_map:
                _state.detected_environment = env_map[config_env]
                logger.debug(f"Environment detected from config file: {_state.detected_environment.value}")
                return _state.detected_environment
        except Exception:
            pass

    # 3. Check API key prefix
    api_key = os.environ.get("RAXE_API_KEY", "")
    if not api_key:
        # Try to read from credentials file
        creds_path = Path.home() / ".raxe" / "credentials.json"
        if creds_path.exists():
            try:
                import json
                with open(creds_path) as f:
                    creds = json.load(f)
                    api_key = creds.get("api_key", "")
            except Exception:
                pass

    if api_key.startswith("raxe_test_"):
        _state.detected_environment = Environment.TEST
    elif api_key.startswith("raxe_temp_"):
        # Temp keys (fresh installs) default to production
        _state.detected_environment = Environment.PRODUCTION
    elif api_key.startswith("raxe_live_"):
        _state.detected_environment = Environment.PRODUCTION
    else:
        # Default to production for real users
        _state.detected_environment = Environment.PRODUCTION

    logger.debug(f"Environment detected: {_state.detected_environment.value}")
    return _state.detected_environment


def set_environment(environment: Environment | None) -> None:
    """
    Explicitly set the environment (in-memory only).

    Args:
        environment: The environment to use, or None to clear the override
    """
    _state.detected_environment = environment
    if environment is not None:
        logger.info(f"Environment set to: {environment.value}")
    else:
        logger.info("Environment override cleared")


def save_environment(environment: Environment) -> None:
    """
    Persist environment setting to config file (~/.raxe/config.yaml).

    This ensures the environment persists across CLI invocations.

    Args:
        environment: The environment to persist
    """
    import yaml

    config_path = Path.home() / ".raxe" / "config.yaml"

    # Load existing config or create empty
    config: dict = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            config = {}

    # Update environment in core section
    if "core" not in config:
        config["core"] = {}
    config["core"]["environment"] = environment.value

    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write back
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # Also update in-memory state
    _state.detected_environment = environment
    logger.info(f"Environment saved to config: {environment.value}")


def get_environment() -> Environment:
    """
    Get the current environment.

    Returns:
        Current Environment
    """
    return detect_environment()


# ============================================================================
# Endpoint Resolution
# ============================================================================

def get_endpoint(
    endpoint: Endpoint,
    environment: Environment | None = None,
    use_overrides: bool = True,
) -> str:
    """
    Get the URL for a specific endpoint.

    Resolution priority:
    1. Runtime override (if use_overrides=True and set via set_endpoint)
    2. Environment variable
    3. Config file
    4. Environment-specific default

    Args:
        endpoint: The endpoint type to resolve
        environment: Optional environment override (defaults to detected)
        use_overrides: Whether to check runtime overrides (default True)

    Returns:
        The resolved endpoint URL
    """
    # 1. Check runtime override
    if use_overrides and endpoint in _state.overrides:
        return _state.overrides[endpoint]

    # 2. Check environment variable
    env_var = _ENV_VAR_MAPPING.get(endpoint)
    if env_var:
        env_value = os.environ.get(env_var)
        if env_value:
            return env_value

    # Special case: RAXE_CLOUD_ENDPOINT is a legacy alias for API_BASE
    if endpoint == Endpoint.API_BASE:
        legacy_value = os.environ.get("RAXE_CLOUD_ENDPOINT")
        if legacy_value:
            return legacy_value

    # 3. Check config file (TODO: implement config file loading)
    # This would load from ~/.raxe/config.yaml or ~/.raxe/endpoints.yaml

    # 4. Return environment-specific default
    env = environment or detect_environment()
    return _ENDPOINT_DEFAULTS[env][endpoint]


def set_endpoint(endpoint: Endpoint, url: str) -> None:
    """
    Override an endpoint URL at runtime.

    Args:
        endpoint: The endpoint to override
        url: The new URL to use

    Raises:
        ValueError: If the URL is invalid
    """
    # Validate URL
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}. Must include scheme (http/https) and host.")

    _state.overrides[endpoint] = url
    logger.info(f"Endpoint {endpoint.value} overridden to: {url}")


def reset_endpoint(endpoint: Endpoint | None = None) -> None:
    """
    Reset endpoint override(s) to use default resolution.

    Args:
        endpoint: Specific endpoint to reset, or None to reset all
    """
    if endpoint is None:
        _state.overrides.clear()
        logger.info("All endpoint overrides cleared")
    elif endpoint in _state.overrides:
        del _state.overrides[endpoint]
        logger.info(f"Endpoint {endpoint.value} override cleared")


def reset_all() -> None:
    """Reset all state including environment detection cache."""
    _state.overrides.clear()
    _state.detected_environment = None
    _state.config_file_path = None


# ============================================================================
# Convenience Functions
# ============================================================================

def get_api_base(environment: Environment | None = None) -> str:
    """Get the API base URL."""
    return get_endpoint(Endpoint.API_BASE, environment)


def get_telemetry_endpoint(environment: Environment | None = None) -> str:
    """Get the telemetry endpoint URL."""
    return get_endpoint(Endpoint.TELEMETRY, environment)


def get_health_endpoint(environment: Environment | None = None) -> str:
    """Get the health check endpoint URL."""
    return get_endpoint(Endpoint.HEALTH, environment)


def get_console_url(environment: Environment | None = None) -> str:
    """Get the console base URL."""
    return get_endpoint(Endpoint.CONSOLE, environment)


def get_cli_session_endpoint(environment: Environment | None = None) -> str:
    """Get the CLI session endpoint URL."""
    return get_endpoint(Endpoint.CLI_SESSION, environment)


# ============================================================================
# Endpoint Testing
# ============================================================================

@dataclass
class EndpointStatus:
    """Status of an endpoint connectivity test."""
    endpoint: Endpoint
    url: str
    reachable: bool
    dns_resolved: bool
    response_time_ms: float | None
    error: str | None
    http_status: int | None = None


def test_endpoint(
    endpoint: Endpoint,
    timeout_seconds: float = 5.0,
) -> EndpointStatus:
    """
    Test connectivity to an endpoint.

    Args:
        endpoint: The endpoint to test
        timeout_seconds: Request timeout

    Returns:
        EndpointStatus with connectivity details
    """
    import time

    url = get_endpoint(endpoint)
    parsed = urlparse(url)

    # Test DNS resolution
    dns_resolved = False
    try:
        socket.gethostbyname(parsed.hostname or "")
        dns_resolved = True
    except socket.gaierror:
        return EndpointStatus(
            endpoint=endpoint,
            url=url,
            reachable=False,
            dns_resolved=False,
            response_time_ms=None,
            error=f"DNS resolution failed for {parsed.hostname}",
        )

    # Test HTTP connectivity
    try:
        import urllib.request

        # Use health endpoint for API base
        test_url = url
        if endpoint == Endpoint.API_BASE:
            test_url = f"{url}/v1/health"
        elif endpoint == Endpoint.CONSOLE:
            # Console might not have a simple health endpoint
            pass

        start = time.time()
        req = urllib.request.Request(test_url, method="GET")
        req.add_header("User-Agent", "raxe-cli/endpoint-test")

        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            response_time_ms = (time.time() - start) * 1000
            return EndpointStatus(
                endpoint=endpoint,
                url=url,
                reachable=True,
                dns_resolved=True,
                response_time_ms=response_time_ms,
                error=None,
                http_status=response.status,
            )
    except urllib.error.HTTPError as e:
        response_time_ms = (time.time() - start) * 1000
        # HTTP errors still mean the endpoint is reachable
        return EndpointStatus(
            endpoint=endpoint,
            url=url,
            reachable=True,
            dns_resolved=True,
            response_time_ms=response_time_ms,
            error=f"HTTP {e.code}: {e.reason}",
            http_status=e.code,
        )
    except urllib.error.URLError as e:
        return EndpointStatus(
            endpoint=endpoint,
            url=url,
            reachable=False,
            dns_resolved=dns_resolved,
            response_time_ms=None,
            error=str(e.reason),
        )
    except Exception as e:
        return EndpointStatus(
            endpoint=endpoint,
            url=url,
            reachable=False,
            dns_resolved=dns_resolved,
            response_time_ms=None,
            error=str(e),
        )


def test_all_endpoints(
    environment: Environment | None = None,
    timeout_seconds: float = 5.0,
) -> dict[Endpoint, EndpointStatus]:
    """
    Test connectivity to all endpoints.

    Args:
        environment: Environment to test (defaults to detected)
        timeout_seconds: Request timeout per endpoint

    Returns:
        Dictionary of endpoint to status
    """
    results = {}
    for endpoint in Endpoint:
        results[endpoint] = test_endpoint(endpoint, timeout_seconds)
    return results


# ============================================================================
# Configuration Display
# ============================================================================

def get_all_endpoints(environment: Environment | None = None) -> dict[str, str]:
    """
    Get all endpoint URLs for display purposes.

    Args:
        environment: Environment to get endpoints for (defaults to detected)

    Returns:
        Dictionary of endpoint name to URL
    """
    env = environment or detect_environment()
    return {
        endpoint.value: get_endpoint(endpoint, env)
        for endpoint in Endpoint
    }


def get_endpoint_info() -> dict[str, Any]:
    """
    Get comprehensive endpoint configuration info for display.

    Returns:
        Dictionary with environment, endpoints, overrides, etc.
    """
    env = detect_environment()
    return {
        "environment": env.value,
        "environment_source": _get_environment_source(),
        "endpoints": get_all_endpoints(env),
        "overrides": {
            ep.value: url
            for ep, url in _state.overrides.items()
        },
        "env_vars": {
            ep.value: os.environ.get(env_var, "")
            for ep, env_var in _ENV_VAR_MAPPING.items()
            if os.environ.get(env_var)
        },
    }


def _get_environment_source() -> str:
    """Get the source of environment detection."""
    # Must match detection priority in detect_environment()
    if os.environ.get("RAXE_ENV"):
        return f"RAXE_ENV={os.environ['RAXE_ENV']}"

    # Check config file
    config_path = Path.home() / ".raxe" / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
            config_env = config.get("core", {}).get("environment", "")
            if config_env:
                return f"~/.raxe/config.yaml (core.environment={config_env})"
        except Exception:
            pass

    api_key = os.environ.get("RAXE_API_KEY", "")
    if api_key:
        return f"API key prefix ({api_key[:15]}...)"

    creds_path = Path.home() / ".raxe" / "credentials.json"
    if creds_path.exists():
        return "credentials.json"

    return "default"


# ============================================================================
# Environment Presets
# ============================================================================

def use_production() -> None:
    """Switch to production endpoints."""
    set_environment(Environment.PRODUCTION)


def use_staging() -> None:
    """Switch to staging endpoints."""
    set_environment(Environment.STAGING)


def use_development() -> None:
    """Switch to development endpoints."""
    set_environment(Environment.DEVELOPMENT)


def use_local() -> None:
    """Switch to local console with Cloud Run API (for console development)."""
    set_environment(Environment.LOCAL)
