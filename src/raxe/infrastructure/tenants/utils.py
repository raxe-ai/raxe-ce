"""Utility functions for tenant infrastructure operations.

This module provides shared utilities for tenant, policy, and app management:

Pure Functions (no I/O):
- slugify: Convert names to URL-safe slugs

I/O Functions (require repository access):
- get_available_policies: List policy IDs available for a tenant
- build_policy_registry: Build complete policy registry for resolution
- verify_tenant_exists: Check if tenant exists

These utilities consolidate common patterns used across CLI commands.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from raxe.domain.tenants.models import TenantPolicy


# =============================================================================
# Pure Functions (No I/O)
# =============================================================================


def slugify(name: str, fallback: str = "entity") -> str:
    """Convert a name to a URL-safe slug.

    Transforms human-readable names into lowercase identifiers suitable
    for use in URLs, file paths, and IDs. Uses hyphens as separators.

    Algorithm:
    1. Convert to lowercase and strip whitespace
    2. Replace spaces and underscores with hyphens
    3. Remove non-alphanumeric characters (except hyphens)
    4. Collapse consecutive hyphens
    5. Remove leading/trailing hyphens
    6. Return fallback if result is empty

    Args:
        name: Human-readable name to convert (e.g., "My Cool Project")
        fallback: Value to return if slug is empty after processing.
            Defaults to "entity". Common values: "tenant", "policy", "app".

    Returns:
        URL-safe slug (e.g., "my-cool-project"), or fallback if empty.

    Examples:
        >>> slugify("My Cool Project")
        'my-cool-project'
        >>> slugify("  UPPERCASE  ")
        'uppercase'
        >>> slugify("special@#$chars")
        'specialchars'
        >>> slugify("multiple   spaces___underscores")
        'multiple-spaces-underscores'
        >>> slugify("---")
        'entity'
        >>> slugify("", fallback="policy")
        'policy'
    """
    slug = name.lower().strip()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug or fallback


# =============================================================================
# I/O Functions (Repository Access)
# =============================================================================


def get_available_policies(tenant_id: str, base_path: Path | None = None) -> list[str]:
    """Get list of available policy IDs for a tenant.

    Returns global preset policy IDs plus any tenant-specific custom policies.
    Useful for CLI validation and autocomplete.

    Args:
        tenant_id: Tenant identifier to query policies for.
        base_path: Base path for tenant storage. If None, uses default
            from get_tenants_base_path().

    Returns:
        List of policy IDs (global presets first, then tenant-specific).

    Example:
        >>> get_available_policies("acme")
        ['monitor', 'balanced', 'strict', 'acme-custom-policy']
    """
    from raxe.domain.tenants.presets import GLOBAL_PRESETS
    from raxe.infrastructure.tenants import (
        YamlPolicyRepository,
        get_tenants_base_path,
    )

    if base_path is None:
        base_path = get_tenants_base_path()

    # Start with global presets
    policies = list(GLOBAL_PRESETS.keys())

    # Add tenant-specific policies
    policy_repo = YamlPolicyRepository(base_path)
    tenant_policies = policy_repo.list_policies(tenant_id=tenant_id)
    for p in tenant_policies:
        if p.policy_id not in policies:
            policies.append(p.policy_id)

    return policies


def build_policy_registry(tenant_id: str, base_path: Path | None = None) -> dict[str, TenantPolicy]:
    """Build complete policy registry for a tenant.

    Combines global preset policies with tenant-specific custom policies
    into a single registry suitable for policy resolution.

    Tenant-specific policies with the same ID as global presets will
    override the global preset in the returned registry.

    Args:
        tenant_id: Tenant identifier to build registry for.
        base_path: Base path for tenant storage. If None, uses default
            from get_tenants_base_path().

    Returns:
        Dictionary mapping policy_id to TenantPolicy objects.

    Example:
        >>> registry = build_policy_registry("acme")
        >>> registry["balanced"]  # Global preset
        TenantPolicy(policy_id='balanced', ...)
        >>> registry["acme-custom"]  # Tenant-specific
        TenantPolicy(policy_id='acme-custom', ...)
    """
    from raxe.domain.tenants.presets import GLOBAL_PRESETS
    from raxe.infrastructure.tenants import (
        YamlPolicyRepository,
        get_tenants_base_path,
    )

    if base_path is None:
        base_path = get_tenants_base_path()

    # Start with global presets
    registry: dict[str, TenantPolicy] = dict(GLOBAL_PRESETS)

    # Overlay tenant-specific policies (may override global presets)
    policy_repo = YamlPolicyRepository(base_path)
    tenant_policies = policy_repo.list_policies(tenant_id=tenant_id)
    for p in tenant_policies:
        registry[p.policy_id] = p

    return registry


def verify_tenant_exists(tenant_id: str, base_path: Path | None = None) -> bool:
    """Verify that a tenant exists in storage.

    Args:
        tenant_id: Tenant identifier to check.
        base_path: Base path for tenant storage. If None, uses default
            from get_tenants_base_path().

    Returns:
        True if tenant exists, False otherwise.
    """
    from raxe.infrastructure.tenants import (
        YamlTenantRepository,
        get_tenants_base_path,
    )

    if base_path is None:
        base_path = get_tenants_base_path()

    repo = YamlTenantRepository(base_path)
    return repo.get_tenant(tenant_id) is not None
