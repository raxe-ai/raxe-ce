"""
HTTP client for calling the RAXE /v1/health endpoint.

Provides functionality to check API key status and retrieve server-side
metadata including rate limits, usage statistics, and trial status.

This module follows Clean Architecture principles - it only handles I/O
operations for the health check endpoint.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _get_default_api_endpoint() -> str:
    """Get default API endpoint from centralized config."""
    from raxe.infrastructure.config.endpoints import get_api_base
    return get_api_base()


def _get_default_console_keys_url() -> str:
    """Get default console keys URL from centralized config."""
    from raxe.infrastructure.config.endpoints import get_console_url
    return f"{get_console_url()}/keys"


# Legacy constant for backwards compatibility (will use centralized config)
DEFAULT_API_ENDPOINT = ""  # Use _get_default_api_endpoint() at runtime

# Request timeout in seconds
DEFAULT_TIMEOUT = 10.0


class HealthCheckError(Exception):
    """Base exception for health check errors."""


class NetworkError(HealthCheckError):
    """Network connectivity error."""


class AuthenticationError(HealthCheckError):
    """Invalid or expired API key."""


class ServerError(HealthCheckError):
    """Server-side error."""


class TimeoutError(HealthCheckError):
    """Request timeout error."""


@dataclass(frozen=True)
class RateLimitInfo:
    """Rate limit information from server.

    Attributes:
        requests_per_minute: Maximum requests allowed per minute
        events_per_day: Maximum events allowed per day
    """
    requests_per_minute: int
    events_per_day: int


@dataclass(frozen=True)
class UsageInfo:
    """Usage information for current day.

    Attributes:
        events_sent: Number of events sent today
        events_remaining: Number of events remaining for today
    """
    events_sent: int
    events_remaining: int


@dataclass(frozen=True)
class FeaturesInfo:
    """Feature flags for the API key.

    Attributes:
        can_disable_telemetry: Whether telemetry can be disabled
        offline_mode: Whether offline mode is available
        extended_retention: Whether extended data retention is enabled
    """
    can_disable_telemetry: bool
    offline_mode: bool
    extended_retention: bool = False


@dataclass(frozen=True)
class TrialStatus:
    """Trial status information for temporary keys.

    Attributes:
        is_trial: Whether this is a trial key
        days_remaining: Days until trial expiration
        scans_during_trial: Total scans performed during trial
        threats_detected_during_trial: Threats detected during trial
    """
    is_trial: bool
    days_remaining: int | None
    scans_during_trial: int
    threats_detected_during_trial: int


@dataclass(frozen=True)
class HealthResponse:
    """Response from /v1/health endpoint.

    Contains comprehensive information about the API key status,
    rate limits, usage, and features.

    Attributes:
        key_type: Type of key (live, test, temp)
        tier: Subscription tier (temporary, community, pro, enterprise)
        days_remaining: Days until key expiration (None if permanent)
        events_today: Number of events sent today
        events_remaining: Events remaining for today
        rate_limit_rpm: Rate limit (requests per minute)
        rate_limit_daily: Daily event limit
        can_disable_telemetry: Whether telemetry can be disabled
        offline_mode: Whether offline mode is available
        server_time: Server timestamp (ISO 8601)
        trial_status: Trial information (for temp keys)
    """
    key_type: str
    tier: str
    days_remaining: int | None
    events_today: int
    events_remaining: int
    rate_limit_rpm: int
    rate_limit_daily: int
    can_disable_telemetry: bool
    offline_mode: bool
    server_time: str
    trial_status: TrialStatus | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> HealthResponse:
        """Parse API response into HealthResponse.

        Args:
            data: Raw JSON response from /v1/health endpoint

        Returns:
            Parsed HealthResponse object

        Raises:
            ValueError: If response format is invalid
        """
        key_data = data.get("key", {})
        rate_limit = key_data.get("rate_limit", {})
        usage = key_data.get("usage_today", {})
        features = key_data.get("features", {})
        trial_data = key_data.get("trial_status", {})

        # Parse trial status if present
        trial_status = None
        if trial_data and trial_data.get("is_trial"):
            trial_status = TrialStatus(
                is_trial=trial_data.get("is_trial", False),
                days_remaining=trial_data.get("days_remaining"),
                scans_during_trial=trial_data.get("scans_during_trial", 0),
                threats_detected_during_trial=trial_data.get("threats_detected_during_trial", 0),
            )

        # Determine days remaining
        # For temp keys, use trial_status days_remaining
        # For permanent keys, this is None
        days_remaining = None
        if trial_status and trial_status.days_remaining is not None:
            days_remaining = trial_status.days_remaining

        return cls(
            key_type=key_data.get("type", "unknown"),
            tier=key_data.get("tier", "unknown"),
            days_remaining=days_remaining,
            events_today=usage.get("events_sent", 0),
            events_remaining=usage.get("events_remaining", 0),
            rate_limit_rpm=rate_limit.get("requests_per_minute", 0),
            rate_limit_daily=rate_limit.get("events_per_day", 0),
            can_disable_telemetry=features.get("can_disable_telemetry", False),
            offline_mode=features.get("offline_mode", False),
            server_time=data.get("server_time", ""),
            trial_status=trial_status,
        )


def check_health(
    api_key: str,
    *,
    endpoint: str = DEFAULT_API_ENDPOINT,
    timeout: float = DEFAULT_TIMEOUT,
) -> HealthResponse:
    """Call /v1/health endpoint and return parsed response.

    Makes a synchronous HTTP GET request to the health endpoint
    to retrieve API key metadata and usage information.

    Args:
        api_key: RAXE API key for authentication
        endpoint: API endpoint URL (default: https://api.raxe.ai)
        timeout: Request timeout in seconds (default: 10.0)

    Returns:
        HealthResponse with key metadata and usage info

    Raises:
        NetworkError: If unable to reach the server
        AuthenticationError: If API key is invalid or expired
        ServerError: If server returns 5xx error
        TimeoutError: If request times out
        HealthCheckError: For other errors

    Example:
        >>> response = check_health("raxe_live_abc123...")
        >>> print(f"Days remaining: {response.days_remaining}")
        >>> print(f"Events today: {response.events_today}")
    """
    url = f"{endpoint.rstrip('/')}/v1/health"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "RAXE-CE/1.0",
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, headers=headers)

            # Handle different status codes
            if response.status_code == 200:
                return HealthResponse.from_api_response(response.json())

            elif response.status_code == 401:
                error_data = _safe_parse_error(response)
                raise AuthenticationError(
                    error_data.get("message", "Invalid or expired API key")
                )

            elif response.status_code == 403:
                error_data = _safe_parse_error(response)
                message = error_data.get("message", "API key expired or revoked")
                console_url = error_data.get("console_url", _get_default_console_keys_url())
                raise AuthenticationError(f"{message}\nGet a new key at: {console_url}")

            elif response.status_code >= 500:
                raise ServerError(
                    f"Server error (HTTP {response.status_code})"
                )

            else:
                error_data = _safe_parse_error(response)
                raise HealthCheckError(
                    f"Unexpected response (HTTP {response.status_code}): "
                    f"{error_data.get('message', 'Unknown error')}"
                )

    except httpx.ConnectError as e:
        logger.debug("Connection error: %s", e)
        raise NetworkError(
            "Could not reach server. Check your network connection."
        ) from e

    except httpx.TimeoutException as e:
        logger.debug("Timeout error: %s", e)
        raise TimeoutError(
            "Request timed out. Server may be unavailable."
        ) from e

    except httpx.HTTPError as e:
        logger.debug("HTTP error: %s", e)
        raise NetworkError(f"Network error: {e}") from e


async def check_health_async(
    api_key: str,
    *,
    endpoint: str = DEFAULT_API_ENDPOINT,
    timeout: float = DEFAULT_TIMEOUT,
) -> HealthResponse:
    """Async version of check_health.

    Makes an asynchronous HTTP GET request to the health endpoint.

    Args:
        api_key: RAXE API key for authentication
        endpoint: API endpoint URL (default: https://api.raxe.ai)
        timeout: Request timeout in seconds (default: 10.0)

    Returns:
        HealthResponse with key metadata and usage info

    Raises:
        NetworkError: If unable to reach the server
        AuthenticationError: If API key is invalid or expired
        ServerError: If server returns 5xx error
        TimeoutError: If request times out
        HealthCheckError: For other errors
    """
    url = f"{endpoint.rstrip('/')}/v1/health"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "RAXE-CE/1.0",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)

            # Handle different status codes
            if response.status_code == 200:
                return HealthResponse.from_api_response(response.json())

            elif response.status_code == 401:
                error_data = _safe_parse_error(response)
                raise AuthenticationError(
                    error_data.get("message", "Invalid or expired API key")
                )

            elif response.status_code == 403:
                error_data = _safe_parse_error(response)
                message = error_data.get("message", "API key expired or revoked")
                console_url = error_data.get("console_url", _get_default_console_keys_url())
                raise AuthenticationError(f"{message}\nGet a new key at: {console_url}")

            elif response.status_code >= 500:
                raise ServerError(
                    f"Server error (HTTP {response.status_code})"
                )

            else:
                error_data = _safe_parse_error(response)
                raise HealthCheckError(
                    f"Unexpected response (HTTP {response.status_code}): "
                    f"{error_data.get('message', 'Unknown error')}"
                )

    except httpx.ConnectError as e:
        logger.debug("Connection error: %s", e)
        raise NetworkError(
            "Could not reach server. Check your network connection."
        ) from e

    except httpx.TimeoutException as e:
        logger.debug("Timeout error: %s", e)
        raise TimeoutError(
            "Request timed out. Server may be unavailable."
        ) from e

    except httpx.HTTPError as e:
        logger.debug("HTTP error: %s", e)
        raise NetworkError(f"Network error: {e}") from e


def _safe_parse_error(response: httpx.Response) -> dict[str, Any]:
    """Safely parse error response JSON.

    Args:
        response: HTTP response object

    Returns:
        Parsed JSON or empty dict if parsing fails
    """
    try:
        return response.json()
    except Exception:
        return {}


__all__ = [
    "AuthenticationError",
    "DEFAULT_API_ENDPOINT",
    "DEFAULT_TIMEOUT",
    "FeaturesInfo",
    "HealthCheckError",
    "HealthResponse",
    "NetworkError",
    "RateLimitInfo",
    "ServerError",
    "TimeoutError",
    "TrialStatus",
    "UsageInfo",
    "check_health",
    "check_health_async",
]
