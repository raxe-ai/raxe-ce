"""Infrastructure layer for multi-tenant policy management.

This module provides storage implementations for tenant entities:
- YamlTenantRepository: YAML-based tenant storage
- YamlPolicyRepository: YAML-based policy storage
- YamlAppRepository: YAML-based app storage
- CachedPolicyRepository: Cached wrapper for YamlPolicyRepository
- PolicyCache: LRU cache for fast policy lookups

Utilities:
- get_tenants_base_path: Get the base path for tenant storage

Security:
- validate_entity_id: Validates entity IDs to prevent path traversal
- InvalidEntityIdError: Raised when an entity ID is invalid
"""

import os
from pathlib import Path

from raxe.infrastructure.tenants.cache import PolicyCache
from raxe.infrastructure.tenants.yaml_repository import (
    CachedPolicyRepository,
    InvalidEntityIdError,
    YamlAppRepository,
    YamlPolicyRepository,
    YamlTenantRepository,
    validate_entity_id,
)

__all__ = [
    "CachedPolicyRepository",
    "InvalidEntityIdError",
    "PolicyCache",
    "YamlAppRepository",
    "YamlPolicyRepository",
    "YamlTenantRepository",
    "get_tenants_base_path",
    "validate_entity_id",
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
