"""Policy API client.

Fetches policies from RAXE cloud API for cloud customers.
Caches policies locally for offline operation.
"""
import json
from pathlib import Path
from typing import Protocol

from raxe.domain.policies.models import Policy
from raxe.infrastructure.policies.yaml_loader import YAMLPolicyLoader
from raxe.infrastructure.security.auth import APIKey


class HTTPClient(Protocol):
    """HTTP client protocol for dependency injection.

    Allows testing without real HTTP calls.
    """

    def get(self, url: str, headers: dict[str, str]) -> dict:
        """Execute GET request.

        Args:
            url: URL to fetch
            headers: HTTP headers

        Returns:
            Response data as dictionary

        Raises:
            Exception: On HTTP errors
        """
        ...


class PolicyAPIError(Exception):
    """Error fetching policies from API."""
    pass


def _get_default_api_base() -> str:
    """Get default API base URL from centralized config."""
    from raxe.infrastructure.config.endpoints import get_api_base
    return get_api_base()


class PolicyAPIClient:
    """Fetch policies from RAXE cloud API.

    Policies are cached locally for offline operation.
    Cache is refreshed on each successful fetch.
    """

    def __init__(
        self,
        api_base_url: str = "",  # Will use centralized config if empty
        cache_dir: Path | None = None,
        http_client: HTTPClient | None = None,
    ) -> None:
        """Initialize API client.

        Args:
            api_base_url: Base URL for RAXE API (uses centralized config if empty)
            cache_dir: Directory for policy cache (None = ~/.raxe/cache)
            http_client: HTTP client implementation (None = use requests)
        """
        self.api_base_url = (api_base_url or _get_default_api_base()).rstrip("/")
        self.cache_dir = cache_dir or Path.home() / ".raxe" / "cache"
        self.http_client = http_client or self._default_http_client()
        self.yaml_loader = YAMLPolicyLoader()

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_policies(
        self,
        api_key: APIKey,
        *,
        use_cache_on_error: bool = True,
    ) -> list[Policy]:
        """Fetch policies for customer from API.

        Downloads policies, caches them locally, and returns as Policy objects.

        Args:
            api_key: Validated API key
            use_cache_on_error: If True, return cached policies on API error

        Returns:
            List of Policy objects for customer

        Raises:
            PolicyAPIError: If API call fails and no cache available
        """
        try:
            # Fetch from API
            policies_data = self._fetch_from_api(api_key)

            # Cache response
            self._save_to_cache(api_key.customer_id, policies_data)

            # Parse to domain models
            return self._parse_response(policies_data)

        except Exception as e:
            if use_cache_on_error:
                # Try to load from cache
                try:
                    return self.load_from_cache(api_key.customer_id)
                except Exception:
                    # Cache also failed, re-raise original error
                    raise PolicyAPIError(
                        f"Failed to fetch policies and no cache available: {e}"
                    ) from e
            else:
                raise PolicyAPIError(f"Failed to fetch policies: {e}") from e

    def load_from_cache(self, customer_id: str) -> list[Policy]:
        """Load policies from local cache.

        Args:
            customer_id: Customer ID to load policies for

        Returns:
            List of cached policies

        Raises:
            PolicyAPIError: If cache doesn't exist or is invalid
        """
        cache_file = self._get_cache_path(customer_id)

        if not cache_file.exists():
            raise PolicyAPIError(f"No cached policies for {customer_id}")

        try:
            with open(cache_file) as f:
                policies_data = json.load(f)
            return self._parse_response(policies_data)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            raise PolicyAPIError(f"Invalid policy cache: {e}") from e

    def clear_cache(self, customer_id: str | None = None) -> None:
        """Clear policy cache.

        Args:
            customer_id: Specific customer to clear (None = clear all)
        """
        if customer_id:
            cache_file = self._get_cache_path(customer_id)
            if cache_file.exists():
                cache_file.unlink()
        else:
            # Clear all cache files
            for cache_file in self.cache_dir.glob("policies_*.json"):
                cache_file.unlink()

    def _fetch_from_api(self, api_key: APIKey) -> dict:
        """Fetch policies from API.

        Args:
            api_key: API key for authentication

        Returns:
            Response data as dictionary

        Raises:
            Exception: On HTTP errors
        """
        url = f"{self.api_base_url}/v1/policies"
        headers = {
            "Authorization": f"Bearer {api_key.raw_key}",
            "Content-Type": "application/json",
            "User-Agent": "raxe-ce/1.0.0",
        }

        return self.http_client.get(url, headers)

    def _parse_response(self, data: dict) -> list[Policy]:
        """Parse API response to Policy objects.

        Args:
            data: Response data from API

        Returns:
            List of Policy objects

        Raises:
            ValueError: If response format invalid
        """
        # API returns same format as YAML for consistency
        # Convert to YAML string and use existing parser
        # (This avoids duplicating parsing logic)

        if "policies" not in data:
            raise ValueError("API response missing 'policies' field")

        # Use YAML loader's parsing logic
        return self.yaml_loader._parse_yaml_data(data, "<api>")

    def _save_to_cache(self, customer_id: str, data: dict) -> None:
        """Save policies to local cache.

        Args:
            customer_id: Customer ID
            data: Policy data to cache
        """
        cache_file = self._get_cache_path(customer_id)

        try:
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)
        except OSError:
            # Cache write failed - not critical, just log and continue
            # (Domain layer can't log, but application layer should)
            pass

    def _get_cache_path(self, customer_id: str) -> Path:
        """Get cache file path for customer.

        Args:
            customer_id: Customer ID

        Returns:
            Path to cache file
        """
        # Sanitize customer_id for filename
        safe_id = customer_id.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"policies_{safe_id}.json"

    def _default_http_client(self) -> HTTPClient:
        """Create default HTTP client using requests.

        Returns:
            HTTP client implementation
        """
        try:
            import requests

            class RequestsHTTPClient:
                def get(self, url: str, headers: dict[str, str]) -> dict:
                    response = requests.get(url, headers=headers, timeout=10)
                    response.raise_for_status()
                    return response.json()

            return RequestsHTTPClient()

        except ImportError:
            # requests not available - return stub that raises error
            class NoHTTPClient:
                def get(self, url: str, headers: dict[str, str]) -> dict:
                    raise PolicyAPIError(
                        "HTTP client not available. Install 'requests' package."
                    )

            return NoHTTPClient()
