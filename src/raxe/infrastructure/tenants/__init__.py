"""Infrastructure layer for multi-tenant policy management.

This module provides storage implementations for tenant entities:
- YamlTenantRepository: YAML-based tenant storage
- YamlPolicyRepository: YAML-based policy storage
- YamlAppRepository: YAML-based app storage
- CachedPolicyRepository: Cached wrapper for YamlPolicyRepository
- PolicyCache: LRU cache for fast policy lookups

Factory functions (preferred API):
- get_tenant_repo: Get a tenant repository
- get_policy_repo: Get a policy repository (with optional caching)
- get_app_repo: Get an app repository
- get_repository_factory: Get factory for creating repositories

Utilities:
- get_tenants_base_path: Get the base path for tenant storage
- slugify: Convert names to URL-safe slugs
- get_available_policies: List available policy IDs for a tenant
- build_policy_registry: Build policy registry for resolution
- verify_tenant_exists: Check if tenant exists

Security:
- validate_entity_id: Validates entity IDs to prevent path traversal
- InvalidEntityIdError: Raised when an entity ID is invalid
"""

import os
from pathlib import Path

from raxe.infrastructure.tenants.cache import PolicyCache
from raxe.infrastructure.tenants.factory import (
    RepositoryFactory,
    get_app_repo,
    get_policy_repo,
    get_repository_factory,
    get_tenant_repo,
)
from raxe.infrastructure.tenants.utils import (
    build_policy_registry,
    get_available_policies,
    slugify,
    verify_tenant_exists,
)
from raxe.infrastructure.tenants.yaml_repository import (
    CachedPolicyRepository,
    InvalidEntityIdError,
    YamlAppRepository,
    YamlPolicyRepository,
    YamlTenantRepository,
    validate_entity_id,
)

__all__ = [
    # Repository classes
    "CachedPolicyRepository",
    # Security
    "InvalidEntityIdError",
    "PolicyCache",
    "RepositoryFactory",
    "YamlAppRepository",
    "YamlPolicyRepository",
    "YamlTenantRepository",
    # Utilities
    "build_policy_registry",
    # Factory functions (preferred API)
    "get_app_repo",
    "get_available_policies",
    "get_policy_repo",
    "get_repository_factory",
    "get_tenant_repo",
    "get_tenants_base_path",
    "slugify",
    "validate_entity_id",
    "verify_tenant_exists",
]


def get_tenants_base_path() -> Path:
    """Get the base path for tenant storage.

    Can be overridden with RAXE_TENANTS_DIR environment variable.
    This is the canonical location for this function - all modules should
    import from here to avoid duplication.

    Returns:
        Path to tenant storage directory (default: ~/.raxe/tenants/)
    """
    env_path = os.getenv("RAXE_TENANTS_DIR")
    if env_path:
        return Path(env_path)
    return Path.home() / ".raxe" / "tenants"
