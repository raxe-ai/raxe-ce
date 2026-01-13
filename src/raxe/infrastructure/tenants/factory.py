"""Factory functions for tenant repository instantiation.

Provides a single place to get properly configured repositories,
handling base path resolution and caching configuration.

This eliminates the repeated pattern of:
    base_path = get_tenants_base_path()
    repo = YamlXxxRepository(base_path)

Usage:
    from raxe.infrastructure.tenants.factory import get_tenant_repo

    repo = get_tenant_repo()  # Uses default base path
    repo = get_tenant_repo(base_path=tmp_path)  # Custom path for testing
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from raxe.infrastructure.tenants.yaml_repository import (
        CachedPolicyRepository,
        YamlAppRepository,
        YamlPolicyRepository,
        YamlTenantRepository,
    )


class RepositoryFactory:
    """Factory for creating tenant-related repositories.

    Encapsulates base path resolution and optional caching configuration.
    Use the module-level factory functions for convenience.

    Attributes:
        base_path: The resolved base path for tenant storage.

    Example:
        factory = RepositoryFactory()
        tenant_repo = factory.get_tenant_repo()
        policy_repo = factory.get_policy_repo(cached=True)
    """

    def __init__(self, base_path: Path | None = None) -> None:
        """Initialize factory.

        Args:
            base_path: Override base path. If None, uses get_tenants_base_path()
                on first access (lazy resolution).
        """
        self._base_path = base_path
        self._resolved_base_path: Path | None = None

    @property
    def base_path(self) -> Path:
        """Get the resolved base path (lazy initialization)."""
        if self._resolved_base_path is None:
            if self._base_path is not None:
                self._resolved_base_path = self._base_path
            else:
                from raxe.infrastructure.tenants import get_tenants_base_path

                self._resolved_base_path = get_tenants_base_path()
        return self._resolved_base_path

    def get_tenant_repo(self) -> YamlTenantRepository:
        """Get a tenant repository.

        Returns:
            YamlTenantRepository configured with base_path.
        """
        from raxe.infrastructure.tenants.yaml_repository import YamlTenantRepository

        return YamlTenantRepository(self.base_path)

    def get_policy_repo(
        self,
        *,
        cached: bool = False,
        cache_maxsize: int = 128,
    ) -> YamlPolicyRepository | CachedPolicyRepository:
        """Get a policy repository.

        Args:
            cached: If True, return a cached repository wrapper for
                improved performance on repeated lookups.
            cache_maxsize: Maximum cache size (only if cached=True).

        Returns:
            YamlPolicyRepository or CachedPolicyRepository.
        """
        from raxe.infrastructure.tenants.yaml_repository import (
            CachedPolicyRepository,
            YamlPolicyRepository,
        )

        base_repo = YamlPolicyRepository(self.base_path)
        if cached:
            return CachedPolicyRepository(base_repo, cache_maxsize=cache_maxsize)
        return base_repo

    def get_app_repo(self) -> YamlAppRepository:
        """Get an app repository.

        Returns:
            YamlAppRepository configured with base_path.
        """
        from raxe.infrastructure.tenants.yaml_repository import YamlAppRepository

        return YamlAppRepository(self.base_path)

    def get_all_repos(
        self,
    ) -> tuple[YamlTenantRepository, YamlPolicyRepository, YamlAppRepository]:
        """Get all three repositories.

        Convenience method for operations that need all repositories.

        Returns:
            Tuple of (tenant_repo, policy_repo, app_repo).
        """
        return (
            self.get_tenant_repo(),
            self.get_policy_repo(),
            self.get_app_repo(),
        )


# =============================================================================
# Module-level Factory Functions (Convenience API)
# =============================================================================


def get_repository_factory(base_path: Path | None = None) -> RepositoryFactory:
    """Get a repository factory.

    For most use cases, prefer the convenience functions below
    (get_tenant_repo, get_policy_repo, get_app_repo).

    Args:
        base_path: Override base path. If None, uses default from
            get_tenants_base_path().

    Returns:
        RepositoryFactory instance.

    Note:
        Each call creates a new factory instance. This is intentional
        to avoid stale state in long-running processes. The factory
        itself is lightweight.
    """
    return RepositoryFactory(base_path)


def get_tenant_repo(base_path: Path | None = None) -> YamlTenantRepository:
    """Get a tenant repository with default configuration.

    Args:
        base_path: Override base path. If None, uses default.

    Returns:
        YamlTenantRepository instance.

    Example:
        repo = get_tenant_repo()
        tenant = repo.get_tenant("acme")
    """
    return get_repository_factory(base_path).get_tenant_repo()


def get_policy_repo(
    base_path: Path | None = None,
    *,
    cached: bool = False,
    cache_maxsize: int = 128,
) -> YamlPolicyRepository | CachedPolicyRepository:
    """Get a policy repository with default configuration.

    Args:
        base_path: Override base path. If None, uses default.
        cached: If True, return cached repository for better performance.
        cache_maxsize: Maximum cache size (only if cached=True).

    Returns:
        YamlPolicyRepository or CachedPolicyRepository instance.

    Example:
        repo = get_policy_repo()
        policy = repo.get_policy("balanced", tenant_id=None)

        # For hot paths, use caching:
        cached_repo = get_policy_repo(cached=True)
    """
    return get_repository_factory(base_path).get_policy_repo(
        cached=cached, cache_maxsize=cache_maxsize
    )


def get_app_repo(base_path: Path | None = None) -> YamlAppRepository:
    """Get an app repository with default configuration.

    Args:
        base_path: Override base path. If None, uses default.

    Returns:
        YamlAppRepository instance.

    Example:
        repo = get_app_repo()
        app = repo.get_app("chatbot", tenant_id="acme")
    """
    return get_repository_factory(base_path).get_app_repo()
